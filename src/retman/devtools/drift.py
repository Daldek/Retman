"""The drift check: Retman's static descriptions against the installed tool.

It is *conformance by execution*. The operation's real call builder runs over the
grid of the manifest's choices (``retman.devtools.grid``), every call it produces
is validated offline by the tool itself through the operation's client (the
planning half only, as at plan time), and the tool's verdicts are read against
the manifest and the tool's catalog. Nothing is downloaded or written: the
check runs under a guard that records any network attempt and any file created.

======  =============================================================  ========
Check   What it finds                                                   Severity
======  =============================================================  ========
X1      a declared command the catalog lacks / is no data command /     error
        the builder emits an undeclared one
X2      a rejection that is not an answer the user can change (missing  error
        option, unknown option, rejection naming no parameter); the
        rejected pairs of the cartesian grid are only reported          info
X3      a manifest option the tool accepts at no point of the grid      error
X4      a value the tool accepts for a bound option that the manifest   error
        neither offers nor lists in ``excluded`` (coverage invariant)
X5      a stale ``excluded`` entry                                      warning
X6      a default on a tool-required option / an optional parameter     warning
        behind a tool-required option
X7      the client's ``lookup`` takes a command with effects, the       error
        offline check touched the network or wrote a file; a download   warning
        operation with neither ``check`` nor a reasoned ``no_check``,
        a ``no_check`` no command needs
X8      an error code without ``[errors.<code>]`` text; a document      error
        schema the client does not know
X9      catalog data commands no operation uses                         info
X10     no complete eval-command row with free values for the           warning
        operation, so its grid could not be built
======  =============================================================  ========
"""

import copy
import importlib.metadata
import json
import tempfile
from collections import Counter
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

from retman.adapters.catalog import (
    CallBuilder,
    CatalogCall,
    PlanClient,
    PlanView,
    ToolContext,
    ToolError,
    create_client,
    load_reference,
    route_error,
)
from retman.devtools import grid
from retman.devtools.guard import OfflineGuard
from retman.devtools.model import Reader, ToolCatalog, load_reader
from retman.eval.dataset import EvalCommand
from retman.i18n.loader import load_texts
from retman.registry.loader import version_matches
from retman.registry.manifest import ManifestSpec, OperationSpec, ParamSpec

Severity = Literal["error", "warning", "info"]
ToolStatus = Literal["checked", "skipped", "missing", "unsupported", "failed"]

# Checks that run in the light form shown by ``retman doctor check``; X10 so that an
# operation that could not be checked says so instead of looking fine
LIGHT_CHECKS = frozenset({"X1", "X4", "X7", "X10"})
# Longest detail quoted from a tool's message in a finding
_DETAIL_LENGTH = 160
# Examples of network attempts and created files named in a finding
_EXAMPLES = 5


@dataclass(frozen=True)
class Finding:
    """One result of the check: which check, how serious and what to say.

    ``key`` names the text of ``[scaffold.finding]`` in ``src/retman/i18n/pl.toml``,
    ``args`` fill its placeholders; ``check`` is ``T`` for what concerns the whole
    tool (missing, no reader).
    """

    check: str
    severity: Severity
    tool: str
    key: str
    args: Mapping[str, str] = field(default_factory=dict)
    operation: str | None = None


@dataclass
class ToolReport:
    """The outcome of checking one tool."""

    tool: str
    status: ToolStatus
    version: str | None = None
    supported: str = ""
    operations: int = 0
    points: int = 0
    calls: int = 0
    findings: list[Finding] = field(default_factory=list)

    def count(self, severity: Severity) -> int:
        """Count the findings of that severity."""
        return sum(1 for finding in self.findings if finding.severity == severity)


@dataclass
class _Run:
    """One grid point: the builder's calls and the tool's verdict on each."""

    values: dict[str, Any]
    calls: list[CatalogCall] = field(default_factory=list)
    outcomes: list[Exception | None] = field(default_factory=list)
    error: Exception | None = None

    @property
    def accepted(self) -> bool:
        """Whether the builder worked and the tool took every call."""
        return self.error is None and all(item is None for item in self.outcomes)


@dataclass
class _Binding:
    """What a builder does with one option of one command.

    ``params`` are the choice parameters the option follows, ``values`` what the
    grid sent for it, ``calls`` the distinct calls that carry it (to probe).
    """

    params: set[str] = field(default_factory=set)
    values: set[str] = field(default_factory=set)
    calls: dict[str, CatalogCall] = field(default_factory=dict)


def _brief(error: object) -> str:
    """Shorten a message to its first line, short enough for one report line."""
    line = str(error).strip().splitlines()[0] if str(error).strip() else ""
    return line if len(line) <= _DETAIL_LENGTH else line[: _DETAIL_LENGTH - 1] + "…"


def _call_key(call: CatalogCall) -> str:
    return json.dumps([call.command, call.options], sort_keys=True, default=str)


def _texts_of(value: object) -> list[str]:
    """Return the values of an option as the tool's text (a list gives one per item)."""
    items = value if isinstance(value, list | tuple) else [value]
    return [str(item) for item in items]


class _Validator:
    """The tool's offline verdict per call, asked once for each distinct call."""

    def __init__(self, view: PlanClient) -> None:
        self._view = view
        self._memo: dict[str, Exception | None] = {}

    @property
    def asked(self) -> int:
        """Number of distinct calls validated."""
        return len(self._memo)

    def __call__(self, call: CatalogCall) -> Exception | None:
        key = _call_key(call)
        if key not in self._memo:
            try:
                self._view.validate(call)
                self._memo[key] = None
            except Exception as error:
                # ToolError is the contract; anything else is the client's bug
                self._memo[key] = error
        return self._memo[key]


class _Engine:
    """The checks of one tool whose catalog, client and builders are loaded."""

    def __init__(
        self,
        manifest: ManifestSpec,
        directory: Path,
        *,
        catalog: ToolCatalog,
        view: PlanClient,
        rows: Sequence[EvalCommand],
        settings: Mapping[str, Any],
        scratch: Path,
        light: bool,
    ) -> None:
        self.manifest = manifest
        self.directory = directory
        self.tool = manifest["tool"]
        self.catalog = catalog
        self.view = view
        self.rows = rows
        self.settings = settings
        self.scratch = scratch
        self.light = light
        self.checks = LIGHT_CHECKS if light else None
        self.validator = _Validator(view)
        self.findings: list[Finding] = []
        self.points = 0
        self._seen: set[str] = set()

    # --- bookkeeping -----------------------------------------------------

    def add(
        self,
        check: str,
        severity: Severity,
        key: str,
        operation: str | None = None,
        *,
        once: Sequence[str] | None = None,
        **args: object,
    ) -> None:
        """Record a finding; ``once`` names the args that make two findings equal."""
        if self.checks is not None and check not in self.checks and check != "T":
            return
        shown = {name: str(value) for name, value in args.items()}
        identity = {name: shown[name] for name in (once if once is not None else shown)}
        marker = json.dumps([check, key, operation, identity], sort_keys=True)
        if marker in self._seen:
            return
        self._seen.add(marker)
        self.findings.append(Finding(check, severity, self.tool, key, shown, operation))

    # --- one operation ---------------------------------------------------

    def operation(self, spec: OperationSpec, builder: CallBuilder) -> None:
        """Run the checks that need the operation's grid."""
        op = spec["id"]
        commands = spec.get("commands", [])
        for command in commands:
            info = self.catalog.commands.get(command)
            if info is None:
                self.add(
                    "X1",
                    "error",
                    "x1_command_missing",
                    op,
                    command=command,
                    version=self.catalog.version,
                )
            elif not info.data:
                self.add("X1", "error", "x1_command_not_data", op, command=command)
        if not self.light:
            downloads = [
                command
                for command in commands
                if (info := self.catalog.commands.get(command)) is not None
                and info.network
                and info.writes
            ]
            if downloads and "check" not in spec and "no_check" not in spec:
                self.add(
                    "X7", "warning", "x7_no_check", op, commands=", ".join(downloads)
                )
            elif "no_check" in spec and not downloads:
                self.add("X7", "warning", "x7_no_check_stale", op)
        runs = self._runs(spec, builder)
        if runs is None:
            return
        self._calls(spec, runs)
        if not self.light:
            self._grid(spec, runs)
        bound = self._bindings(spec, runs)
        self._coverage(spec, bound)
        if not self.light:
            self._excluded(spec, bound)
            self._required(spec, bound)

    def _runs(self, spec: OperationSpec, builder: CallBuilder) -> list[_Run] | None:
        op = spec["id"]
        free = [param for param in spec["params"] if param["type"] == "free"]
        samples = grid.free_samples(spec, self.rows)
        if not free:
            samples = [{}]
        elif not samples:
            self.add(
                "X10",
                "warning",
                "x10_no_samples",
                op,
                params=", ".join(param["name"] for param in free),
            )
            if any(param.get("required") and "default" not in param for param in free):
                return None
            samples = [{}]
        points, reduced = grid.points(spec, samples, reduced=self.light)
        if reduced and not self.light:
            self.add(
                "X2", "warning", "x2_grid_reduced", op, limit=grid.MAX_CHOICE_POINTS
            )
        if not points:
            self.add("X10", "warning", "x10_no_points", op)
            return None
        context = ToolContext(
            tool=self.tool,
            settings=self.settings,
            project_dir=self.scratch / "project",
            output_dir=None,
            inputs={
                item["name"]: self.scratch / "inputs" / f"{item['name']}.dat"
                for item in spec["inputs"]
            },
            client=self.view,
            specs={param["name"]: param for param in spec["params"]},
        )
        runs: list[_Run] = []
        for values in points:
            run = _Run(values)
            try:
                run.calls = list(builder(copy.deepcopy(values), context))
            except Exception as error:
                run.error = error
            else:
                run.outcomes = [self.validator(call) for call in run.calls]
            runs.append(run)
        self.points += len(runs)
        return runs

    def _calls(self, spec: OperationSpec, runs: list[_Run]) -> None:
        """X1 (undeclared commands) and X2 (what the tool's rejections mean)."""
        op = spec["id"]
        declared = set(spec.get("commands", []))
        matrix: dict[tuple[str, ...], set[int]] = {}
        for index, run in enumerate(runs):
            point = grid.describe_point(spec, run.values)
            if run.error is not None:
                self.add(
                    "X2",
                    "error",
                    "x2_builder_error",
                    op,
                    once=("error",),
                    point=point,
                    error=_brief(f"{type(run.error).__name__}: {run.error}"),
                )
                continue
            for call, outcome in zip(run.calls, run.outcomes, strict=True):
                if call.command not in declared:
                    self.add(
                        "X1",
                        "error",
                        "x1_undeclared_command",
                        op,
                        command=call.command,
                    )
                if outcome is None:
                    continue
                routed = self._rejection(spec, call, outcome, point)
                if routed:
                    matrix.setdefault(routed, set()).add(index)
        for routed, indexes in matrix.items():
            self.add(
                "X2",
                "info",
                "x2_matrix",
                op,
                params=", ".join(routed),
                rejected=len(indexes),
                points=len(runs),
            )
        if runs and not any(run.accepted for run in runs):
            self.add("X2", "error", "x2_nothing_accepted", op, points=len(runs))

    def _rejection(
        self, spec: OperationSpec, call: CatalogCall, error: Exception, point: str
    ) -> tuple[str, ...]:
        """Judge a rejected call; the parameters it routes to if the user can fix it.

        Anything but an answer the user can change is drift and is recorded;
        the empty tuple is returned for it.
        """
        op = spec["id"]
        if not isinstance(error, ToolError):
            self.add(
                "X2",
                "error",
                "x2_unexpected_error",
                op,
                once=("command", "error"),
                command=call.command,
                point=point,
                error=_brief(f"{type(error).__name__}: {error}"),
            )
            return ()
        info = self.catalog.commands.get(call.command)
        if info is None:
            # The command is missing from the catalog: X1 says so for the operation
            return ()
        named = [name for name in (error.option, *error.options) if name]
        known = {option.name for option in info.options}
        for option in named:
            if option == "command":
                self.add(
                    "X1",
                    "error",
                    "x1_command_rejected",
                    op,
                    once=("command",),
                    command=call.command,
                    detail=_brief(error.detail),
                )
                return ()
            if option not in call.options:
                self.add(
                    "X2",
                    "error",
                    "x2_missing_option",
                    op,
                    once=("command", "option"),
                    command=call.command,
                    option=option,
                    point=point,
                )
                return ()
            if option not in known:
                self.add(
                    "X2",
                    "error",
                    "x2_unknown_option",
                    op,
                    once=("command", "option"),
                    command=call.command,
                    option=option,
                    point=point,
                )
                return ()
        routed = route_error(call, error, [param["name"] for param in spec["params"]])
        if not named:
            self.add(
                "X2",
                "error",
                "x2_unattributed",
                op,
                once=("command", "detail"),
                command=call.command,
                point=point,
                detail=_brief(error.detail),
            )
        elif not routed:
            self.add(
                "X2",
                "error",
                "x2_unroutable",
                op,
                once=("command", "option"),
                command=call.command,
                option=", ".join(named),
                point=point,
                detail=_brief(error.detail),
            )
        return tuple(routed)

    def _grid(self, spec: OperationSpec, runs: list[_Run]) -> None:
        """X3: a choice option the tool accepts at no point is dead."""
        if not any(run.accepted for run in runs):
            return
        choices = {
            param["name"] for param in spec["params"] if param["type"] == "choice"
        }
        accepted: dict[str, set[str]] = {}
        for run in runs:
            if run.accepted:
                for name in choices & run.values.keys():
                    accepted.setdefault(name, set()).add(run.values[name])
        for param in spec["params"]:
            if param["type"] != "choice":
                continue
            dead = [
                key
                for key in param["options"]
                if key not in accepted.get(param["name"], set())
            ]
            if dead:
                self.add(
                    "X3",
                    "error",
                    "x3_dead_option",
                    spec["id"],
                    param=param["name"],
                    options=", ".join(dead),
                )

    # --- coverage --------------------------------------------------------

    def _bindings(
        self, spec: OperationSpec, runs: list[_Run]
    ) -> dict[tuple[str, str], _Binding]:
        """Which options of which commands follow a choice parameter, and how.

        An option follows a parameter by name or through ``CatalogCall.params``.
        What the manifest *offers* the tool for it is what the grid sent plus the
        tool values of the parameters' own options (``tool_values``, identity
        where absent): a value that only a gated call carries (the PMAXTP method
        goes to ``pmaxtp sync`` only with the store) may be missing from a grid
        that does not combine everything, but the manifest offers it all the same.
        """
        by_name = {param["name"]: param for param in spec["params"]}
        bound: dict[tuple[str, str], _Binding] = {}
        for run in runs:
            for call in run.calls:
                for option, value in call.options.items():
                    name = call.params.get(option, option)
                    param = by_name.get(name)
                    if param is None or param["type"] != "choice":
                        continue
                    if name not in run.values:
                        continue
                    binding = bound.setdefault((call.command, option), _Binding())
                    binding.params.add(name)
                    binding.values.update(_texts_of(value))
                    binding.calls.setdefault(_call_key(call), call)
        for binding in bound.values():
            for name in binding.params:
                param = by_name[name]
                tool_values = param.get("tool_values", {})
                binding.values.update(
                    tool_values.get(key, key) for key in param["options"]
                )
        return bound

    def _accepted(
        self,
        bound: Mapping[tuple[str, str], _Binding],
        command: str,
        option: str,
        value: str,
    ) -> bool:
        """Whether the tool takes ``value`` for the option in a call like the grid's.

        The probe is a call of the grid with the option set to ``value``. A value
        that needs another option left out (NMT 100 m takes no vertical CRS) is
        also tried with the optional options that follow a choice dropped, one at
        a time and all together.
        """
        info = self.catalog.commands.get(command)
        companions = [
            other
            for name, other in bound
            if name == command
            and other != option
            and not (
                info is not None
                and (described := info.option(other)) is not None
                and described.required
            )
        ]
        for call in bound[(command, option)].calls.values():
            options = {**call.options, option: value}
            present = [name for name in companions if name in options]
            variants = [options]
            variants.extend(
                {key: item for key, item in options.items() if key != name}
                for name in present
            )
            if len(present) > 1:
                variants.append(
                    {key: item for key, item in options.items() if key not in present}
                )
            if any(
                self.validator(replace(call, options=variant)) is None
                for variant in variants
            ):
                return True
        return False

    def _coverage(
        self, spec: OperationSpec, bound: Mapping[tuple[str, str], _Binding]
    ) -> None:
        """X4: a value the tool accepts must be offered or listed in ``excluded``."""
        excluded = spec.get("excluded", {})
        for (command, option), binding in bound.items():
            info = self.catalog.commands.get(command)
            described = info.option(option) if info is not None else None
            if described is None or described.allowed is None:
                continue
            skipped = {
                value for param in binding.params for value in excluded.get(param, {})
            }
            for value in described.allowed:
                if value in binding.values or value in skipped:
                    continue
                if self._accepted(bound, command, option, value):
                    self.add(
                        "X4",
                        "error",
                        "x4_gap",
                        spec["id"],
                        param=", ".join(sorted(binding.params)),
                        command=command,
                        option=option,
                        value=value,
                        version=self.catalog.version,
                    )

    def _excluded(
        self, spec: OperationSpec, bound: Mapping[tuple[str, str], _Binding]
    ) -> None:
        """X5: an ``excluded`` entry the tool no longer knows or never accepts."""
        for param, entries in spec.get("excluded", {}).items():
            followed = [
                (command, option, binding)
                for (command, option), binding in bound.items()
                if param in binding.params
            ]
            enumerated = [
                (command, option, binding, described.allowed)
                for command, option, binding in followed
                if (info := self.catalog.commands.get(command)) is not None
                and (described := info.option(option)) is not None
                and described.allowed is not None
            ]
            if not enumerated:
                continue
            for value in entries:
                if not any(value in allowed for *_, allowed in enumerated):
                    self.add(
                        "X5",
                        "warning",
                        "x5_excluded_unknown",
                        spec["id"],
                        param=param,
                        value=value,
                    )
                elif not any(
                    self._accepted(bound, command, option, value)
                    for command, option, binding, allowed in enumerated
                    if value in allowed
                ):
                    self.add(
                        "X5",
                        "warning",
                        "x5_excluded_rejected",
                        spec["id"],
                        param=param,
                        value=value,
                    )

    def _required(
        self, spec: OperationSpec, bound: Mapping[tuple[str, str], _Binding]
    ) -> None:
        """X6: a default or an optional parameter behind a tool-required option."""
        by_name: dict[str, ParamSpec] = {p["name"]: p for p in spec["params"]}
        for (command, option), binding in bound.items():
            info = self.catalog.commands.get(command)
            described = info.option(option) if info is not None else None
            if described is None or not described.required:
                continue
            for name in sorted(binding.params):
                param = by_name[name]
                if "default" in param:
                    self.add(
                        "X6",
                        "warning",
                        "x6_default_on_required",
                        spec["id"],
                        param=name,
                        command=command,
                        option=option,
                    )
                elif not param.get("required"):
                    self.add(
                        "X6",
                        "warning",
                        "x6_optional_for_required",
                        spec["id"],
                        param=name,
                        command=command,
                        option=option,
                    )

    # --- the whole tool --------------------------------------------------

    def lookups(self) -> None:
        """X7: the client must refuse ``lookup`` of every command with effects.

        ``lookup`` is the one call of the offline client half that reads the tool
        for real, so it must never reach a command that uses the network or writes
        (the empty options are the worst case of an option-conditioned entry).
        """
        for info in self.catalog.commands.values():
            if not info.effects:
                continue
            try:
                self.view.lookup(CatalogCall(info.id, {}))
            except ToolError:
                continue
            except Exception as error:
                self.add(
                    "X7",
                    "error",
                    "x7_lookup_unexpected",
                    None,
                    command=info.id,
                    error=_brief(f"{type(error).__name__}: {error}"),
                )
            else:
                self.add(
                    "X7",
                    "error",
                    "x7_lookup_effects",
                    None,
                    command=info.id,
                    effects=", ".join(info.effects),
                )

    def texts_and_schemas(self, referenced: set[str]) -> None:
        """X8: a Polish text for every error code, and only known document schemas."""
        needed = [
            code
            for code in self.catalog.error_codes
            if code not in self.catalog.unreachable_errors
        ]
        for language, filename in self.manifest["translations"].items():
            try:
                texts = load_texts(self.directory / filename)
            except (OSError, ValueError) as error:
                self.add(
                    "X8",
                    "error",
                    "x8_translation_unreadable",
                    None,
                    file=filename,
                    error=_brief(error),
                )
                continue
            missing = [code for code in needed if not texts.has(f"errors.{code}")]
            if missing:
                self.add(
                    "X8",
                    "error",
                    "x8_error_text_missing",
                    None,
                    file=filename,
                    language=language,
                    codes=", ".join(missing),
                )
        for command in sorted(referenced):
            info = self.catalog.commands.get(command)
            if info is None:
                continue
            for schema in (info.result_schema, info.check_schema):
                if schema and schema not in self.catalog.known_schemas:
                    self.add(
                        "X8",
                        "error",
                        "x8_unknown_schema",
                        None,
                        command=command,
                        schema=schema,
                        known=", ".join(self.catalog.known_schemas),
                    )

    def unexposed(self, referenced: set[str]) -> None:
        """X9: catalog data commands that no operation uses."""
        missing = sorted(
            info.id
            for info in self.catalog.commands.values()
            if info.data and info.id not in referenced
        )
        if missing:
            self.add(
                "X9",
                "info",
                "x9_unexposed",
                None,
                count=len(missing),
                commands=", ".join(missing),
            )


def _skip(tool: str, status: ToolStatus, key: str, **args: object) -> ToolReport:
    """Report a tool that is not checked, with the finding that says why."""
    return ToolReport(tool, status, findings=[_tool_finding(tool, "info", key, **args)])


def _tool_finding(tool: str, severity: Severity, key: str, **args: object) -> Finding:
    return Finding("T", severity, tool, key, {k: str(v) for k, v in args.items()})


def check_tool(
    manifest: ManifestSpec,
    directory: Path,
    *,
    version: str,
    reader: Reader,
    commands: Sequence[EvalCommand],
    client: PlanClient | None = None,
    operations: Collection[str] | None = None,
    light: bool = False,
    tool_level: bool | None = None,
) -> ToolReport:
    """Check one installed tool against its manifest (X1-X10, all offline).

    Parameters
    ----------
    manifest, directory
        The tool's manifest and the folder of its translation files.
    version : str
        The installed version (the catalog's own version is reported by the tool).
    reader : Reader
        Reads the tool's catalog and names the settings for its client.
    commands : Sequence[EvalCommand]
        The eval command set; its complete rows give the free values.
    client : PlanClient, optional
        The offline client; by default built by the manifest's ``client`` factory
        from scratch settings.
    operations : Collection[str], optional
        Only these operations (and no tool-wide checks unless ``tool_level``).
    light : bool, optional
        The form of ``retman doctor check``: X1, X4 and the offline guard, on a grid
        varied one choice at a time and a single sample.
    tool_level : bool, optional
        Run X7 (``lookup``), X8 and X9; by default when no operation filter is set
        and not in the light form.
    """
    tool = manifest["tool"]
    selected = [
        spec
        for spec in manifest["operations"]
        if "calls" in spec and (operations is None or spec["id"] in operations)
    ]
    if not any("calls" in spec for spec in manifest["operations"]):
        return _skip(tool, "skipped", "tool_no_calls")
    report = ToolReport(
        tool,
        "checked",
        version,
        manifest["supported_versions"],
        operations=len(selected),
    )
    try:
        catalog = reader.read_catalog()
    except Exception as error:
        report.status = "failed"
        report.findings.append(
            _tool_finding(tool, "error", "catalog_unreadable", error=_brief(error))
        )
        return report
    with tempfile.TemporaryDirectory(prefix="retman-scaffold-") as folder:
        scratch = Path(folder).resolve()
        settings = reader.scratch_settings(scratch)
        try:
            if client is None:
                if "client" not in manifest:
                    raise LookupError("the manifest declares no client")
                client = create_client(manifest["client"], settings)
        except Exception as error:
            report.status = "failed"
            report.findings.append(
                _tool_finding(tool, "error", "client_failed", error=_brief(error))
            )
            return report
        engine = _Engine(
            manifest,
            directory,
            catalog=catalog,
            view=PlanView(client),
            rows=commands,
            settings=settings,
            scratch=scratch,
            light=light,
        )
        builders: list[tuple[OperationSpec, CallBuilder]] = []
        for spec in selected:
            try:
                builders.append((spec, load_reference(spec["calls"])))
            except Exception as error:
                engine.add(
                    "X2",
                    "error",
                    "x2_builder_unloadable",
                    spec["id"],
                    reference=spec["calls"],
                    error=_brief(f"{type(error).__name__}: {error}"),
                )
        wide = (
            tool_level if tool_level is not None else operations is None and not light
        )
        # Everything the tool does runs below the guard: its folder is a scratch
        # folder and any network attempt is refused and recorded
        guard = OfflineGuard(scratch, cwd=None if light else _scratch_cwd(scratch))
        with guard:
            for spec, builder in builders:
                engine.operation(spec, builder)
            if wide:
                engine.lookups()
        for address in guard.attempts[:_EXAMPLES]:
            engine.add("X7", "error", "x7_network_attempt", None, address=address)
        if guard.created:
            more = len(guard.created) > _EXAMPLES
            engine.add(
                "X7",
                "error",
                "x7_files_created",
                None,
                files=", ".join(guard.created[:_EXAMPLES]) + (", …" if more else ""),
            )
        if wide:
            referenced = {
                command
                for spec in manifest["operations"]
                for command in spec.get("commands", [])
            }
            engine.texts_and_schemas(referenced)
            engine.unexposed(referenced)
        report.points = engine.points
        report.calls = engine.validator.asked
        report.findings.extend(engine.findings)
    return report


def _scratch_cwd(scratch: Path) -> Path:
    """Create and return the scratch working folder."""
    folder = scratch / "cwd"
    folder.mkdir()
    return folder


def check_tools(
    manifests: Iterable[tuple[ManifestSpec, Path]],
    *,
    commands: Sequence[EvalCommand],
    version_lookup: Callable[[str], str] = importlib.metadata.version,
    readers: Mapping[str, Reader] | None = None,
    clients: Mapping[str, PlanClient] | None = None,
    tools: Collection[str] | None = None,
    operations: Collection[str] | None = None,
    require_tools: bool = False,
    light: bool = False,
    tool_level: bool | None = None,
) -> list[ToolReport]:
    """Check every tool that is installed in a version its manifest supports.

    A tool that is not installed, or in an unsupported version, is skipped: an
    information line, or an error with ``require_tools`` (CI wants the check to
    have run). A tool whose operations declare no ``calls`` has no catalog to
    check against.

    Parameters
    ----------
    manifests : Iterable[tuple[ManifestSpec, Path]]
        Tool manifests with the folders of their translations.
    commands : Sequence[EvalCommand]
        The eval command set (free values of the complete rows).
    version_lookup : Callable[[str], str], optional
        Installed version of a distribution; an injection for offline tests.
    readers, clients : Mapping[str, ...], optional
        Per tool: the catalog reader and the client to use instead of the
        defaults (``retman.devtools.readers`` and the manifest's factory).
    tools, operations : Collection[str], optional
        Restrict the check to these tools / operations.
    require_tools : bool, optional
        Missing or unsupported tools are errors.
    light : bool, optional
        The light form of ``retman doctor check`` (see ``check_tool``).
    tool_level : bool, optional
        Run the tool-wide checks (X7 ``lookup``, X8, X9) even with an operation
        filter; see ``check_tool``.
    """
    reports: list[ToolReport] = []
    for manifest, directory in manifests:
        tool = manifest["tool"]
        if tools is not None and tool not in tools:
            continue
        supported = manifest["supported_versions"]
        try:
            version = version_lookup(manifest["distribution"])
        except importlib.metadata.PackageNotFoundError:
            reports.append(
                _unavailable(tool, "missing", None, supported, require_tools)
            )
            continue
        if not version_matches(version, supported):
            reports.append(
                _unavailable(tool, "unsupported", version, supported, require_tools)
            )
            continue
        if not any("calls" in spec for spec in manifest["operations"]):
            reports.append(_skip(tool, "skipped", "tool_no_calls"))
            continue
        reader = (
            readers[tool]
            if readers is not None and tool in readers
            else load_reader(tool)
        )
        if reader is None:
            report = ToolReport(tool, "failed", version, supported)
            report.findings.append(_tool_finding(tool, "error", "tool_no_reader"))
            reports.append(report)
            continue
        reports.append(
            check_tool(
                manifest,
                directory,
                version=version,
                reader=reader,
                commands=commands,
                client=clients.get(tool) if clients is not None else None,
                operations=operations,
                light=light,
                tool_level=tool_level,
            )
        )
    return reports


def _unavailable(
    tool: str,
    status: ToolStatus,
    version: str | None,
    supported: str,
    require_tools: bool,
) -> ToolReport:
    key = "tool_missing" if status == "missing" else "tool_unsupported"
    return ToolReport(
        tool,
        status,
        version,
        supported,
        findings=[
            _tool_finding(
                tool,
                "error" if require_tools else "info",
                key,
                version=version or "",
                supported=supported,
            )
        ],
    )


def light_findings(
    manifest: ManifestSpec,
    directory: Path,
    version: str,
    *,
    commands: Sequence[EvalCommand],
    reader: Reader | None = None,
    client: PlanClient | None = None,
) -> list[Finding] | None:
    """Return the findings of the light check shown by ``doctor check`` (X1, X4).

    Returns
    -------
    list[Finding] or None
        ``None`` when there is nothing to check against: no operation of the tool
        declares ``calls``, or the scaffold has no reader for the tool.
    """
    if not any("calls" in spec for spec in manifest["operations"]):
        return None
    reader = reader if reader is not None else load_reader(manifest["tool"])
    if reader is None:
        return None
    report = check_tool(
        manifest,
        directory,
        version=version,
        reader=reader,
        commands=commands,
        client=client,
        light=True,
    )
    return report.findings


def count_problems(reports: Iterable[ToolReport]) -> Counter[Severity]:
    """How many findings of each severity the reports hold."""
    counter: Counter[Severity] = Counter()
    for report in reports:
        counter.update(finding.severity for finding in report.findings)
    return counter
