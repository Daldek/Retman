"""``retman-scaffold``: the drift check X1-X10, drafts, the CLI and the doctor line.

Everything runs on the dummy tool with a hand-made catalog and a programmed
validation, offline; the real tools are met only by ``tests/tools/test_conformance``.
"""

import ast
import contextlib
import json
import socket
import tomllib
from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from retman.adapters.catalog import CatalogCall, ToolContext, ToolDocument, ToolError
from retman.devtools import grid
from retman.devtools.draft import MAX_OPTIONS, build_draft
from retman.devtools.drift import Finding, ToolReport, check_tools, light_findings
from retman.devtools.guard import OfflineGuard
from retman.devtools.light import light_lines
from retman.devtools.model import (
    CommandInfo,
    OptionInfo,
    Reader,
    ScaffoldError,
    ToolCatalog,
    Verdict,
    load_reader,
)
from retman.devtools.report import finding_text
from retman.devtools.scaffold import main
from retman.doctor import run_doctor
from retman.eval.dataset import EvalCommand
from retman.i18n.loader import load_core_texts
from retman.registry.manifest import ManifestSpec, OperationSpec
from retman.testing import FakeToolClient

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
TOOL = "dummy_tool"
TEXTS = load_core_texts("pl")


# --- a tool to check: catalog, validation rules, builders, rows ----------------


def make_catalog(**changes: Any) -> ToolCatalog:
    """A catalog like Kartograf's in miniature: a download and a query command."""
    download = CommandInfo(
        "elevation download",
        "elevation",
        "Download elevation data",
        options=(
            OptionInfo("product", required=True, allowed=("nmt", "nmpt")),
            OptionInfo("sheet"),
            OptionInfo("geometry"),
            OptionInfo("layer"),
            OptionInfo("resolution", allowed=("0.5m", "1m", "2m", "5m", "100m")),
            OptionInfo("vertical_crs", allowed=("EVRF2007", "KRON86")),
        ),
        network=True,
        writes=True,
        result_schema="dummy-download/1",
    )
    availability = CommandInfo(
        "elevation availability", "elevation", "Availability", network=True, data=False
    )
    catalog = ToolCatalog(
        TOOL,
        "1.2.0",
        {item.id: item for item in (download, availability)},
        error_codes=("invalid_input", "no_coverage", "usage_error"),
        unreachable_errors={"usage_error": "the command line only"},
        known_schemas=("dummy-download/1",),
    )
    return replace(catalog, **changes)


def reject(
    call: CatalogCall, detail: str, *, option: str | None = None, **more: Any
) -> ToolError:
    return ToolError(TOOL, "invalid_input", detail, option=option, call=call, **more)


def tool_rule(call: CatalogCall) -> ToolError | None:
    """What the tool accepts: pairs of resolution and height system, 100 m alone."""
    options = call.options
    if "product" not in options:
        return reject(call, "product is required", option="product")
    resolution, crs = options.get("resolution"), options.get("vertical_crs")
    if resolution == "2m":
        return reject(call, "no 2 m here", option="resolution")
    if resolution == "100m" and crs is not None:
        return reject(
            call, "100 m has no height system", options=("resolution", "vertical_crs")
        )
    if resolution == "5m" and crs == "KRON86":
        return reject(
            call, "5 m is EVRF2007 only", options=("resolution", "vertical_crs")
        )
    if resolution != "100m" and crs is None:
        return reject(call, "the height system is required", option="vertical_crs")
    return None


def tolerant_builder(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """The dummy builder, but one that copes with an unset height system."""
    from dummy_tool.calls import fetch_dem

    (call,) = fetch_dem(
        {**params, "vertical_crs": params.get("vertical_crs", "evrf2007")}, ctx
    )
    if "vertical_crs" not in params:
        call = replace(
            call,
            options={k: v for k, v in call.options.items() if k != "vertical_crs"},
        )
    return [call]


def other_command_builder(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    from dummy_tool.calls import fetch_dem

    (call,) = fetch_dem(params, ctx)
    return [replace(call, command="elevation fetch")]


def failing_builder(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    raise KeyError("nothing to build")


NESTED = ("resolution", "vertical_crs")


def nested_builder(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """The dummy call with the resolution and the height system inside ``settings``.

    As ``project add`` carries the options of another command; the routes of the
    call name the options by their paths.
    """
    from dummy_tool.calls import fetch_dem

    (call,) = fetch_dem(params, ctx)
    options = {
        name: value for name, value in call.options.items() if name not in NESTED
    }
    options["settings"] = {name: call.options[name] for name in NESTED}
    routes = {f"settings.{name}": name for name in NESTED}
    return [replace(call, options=options, params={**call.params, **routes})]


def unrouted_builder(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """``nested_builder`` without the routes: no parameter answers the options."""
    (call,) = nested_builder(params, ctx)
    return [replace(call, params={})]


def nested_rule(call: CatalogCall) -> ToolError | None:
    """``tool_rule`` for the options inside ``settings``, naming them by path."""
    settings = call.options["settings"]
    assert isinstance(settings, dict)
    rejected = tool_rule(replace(call, options={**call.options, **settings}))
    if rejected is None:
        return None
    named = (name for name in (rejected.option, *rejected.options) if name)
    paths = tuple(f"settings.{name}" if name in settings else name for name in named)
    return reject(call, rejected.detail, options=paths)


def nested_catalog() -> ToolCatalog:
    """The catalog of the dummy tool whose download takes the option ``settings``."""
    catalog = make_catalog()
    download = catalog.commands["elevation download"]
    nested = replace(download, options=(*download.options, OptionInfo("settings")))
    return replace(catalog, commands={**catalog.commands, download.id: nested})


def nested_edit(manifest: ManifestSpec) -> None:
    operation(manifest)["calls"] = "test_scaffold:nested_builder"


def row(
    identifier: str, operation: str, params: dict[str, Any], *clarify: str
) -> EvalCommand:
    tag = "incomplete" if clarify else "complete"
    return EvalCommand(
        identifier, "polecenie", operation, params, list(clarify), [tag], None
    )


def sheet(code: str) -> dict[str, Any]:
    return {"type": "sheet", "code": code}


def sample_rows() -> list[EvalCommand]:
    """Two complete rows of ``fetch_dem`` with differently shaped sheet codes."""
    return [
        row("a", "fetch_dem", {"area": sheet("N-34-130-D-d-2-4"), "resolution": "1m"}),
        row("b", "fetch_dem", {"area": sheet("7.171.21"), "resolution": "5m"}),
    ]


@pytest.fixture
def dummy(monkeypatch: pytest.MonkeyPatch) -> tuple[ManifestSpec, Path]:
    """A copy of the dummy tool's manifest (a test may change it) and its folder."""
    monkeypatch.syspath_prepend(str(FIXTURES))
    from dummy_tool.manifest import MANIFEST

    return deepcopy(MANIFEST), FIXTURES / TOOL


def operation(manifest: ManifestSpec, name: str = "fetch_dem") -> Any:
    return next(item for item in manifest["operations"] if item["id"] == name)


def param(manifest: ManifestSpec, name: str) -> Any:
    return next(item for item in operation(manifest)["params"] if item["name"] == name)


def reader_of(catalog: ToolCatalog) -> Reader:
    return Reader(
        lambda: catalog,
        lambda command, options: Verdict(True),
        lambda root: {"store_dir": str(root / "store")},
    )


def run(
    dummy: tuple[ManifestSpec, Path],
    *,
    rule: Callable[[CatalogCall], ToolError | None] = tool_rule,
    catalog: ToolCatalog | None = None,
    rows: list[EvalCommand] | None = None,
    edit: Callable[[ManifestSpec], None] | None = None,
    client: FakeToolClient | None = None,
    **options: Any,
) -> ToolReport:
    """Check the dummy tool; every finding must have a text that fits its arguments."""
    manifest, folder = dummy
    if edit is not None:
        edit(manifest)
    (report,) = check_tools(
        [(manifest, folder)],
        commands=sample_rows() if rows is None else rows,
        version_lookup=lambda _: "1.2.0",
        readers={TOOL: reader_of(catalog if catalog is not None else make_catalog())},
        clients={
            TOOL: client
            if client is not None
            else FakeToolClient(validation={"elevation download": rule})
        },
        **options,
    )
    for finding in report.findings:
        assert not finding_text(finding, TEXTS).startswith(finding.key), finding
    return report


def keys(report: ToolReport, severity: str | None = None) -> list[str]:
    return [
        item.key
        for item in report.findings
        if severity is None or item.severity == severity
    ]


def only(report: ToolReport, key: str) -> Finding:
    found = [item for item in report.findings if item.key == key]
    assert len(found) == 1, keys(report)
    return found[0]


# --- the grid -------------------------------------------------------------------


def test_choice_points_prune_by_depends_on_and_leave_optionals_unset(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    spec = operation(dummy[0], "make_dem")

    points, reduced = grid.choice_points(spec)

    # style is required; detail has a default and applies to "smooth" only
    assert not reduced
    assert sorted(map(json.dumps, points)) == sorted(
        json.dumps(item)
        for item in (
            {"style": "raw"},
            {"style": "smooth", "detail": "high"},
            {"style": "smooth", "detail": "low"},
        )
    )
    spec["params"][1] = {**spec["params"][1], "required": False}
    unset, _ = grid.choice_points(spec)
    assert {} in unset


def test_choice_points_vary_one_choice_at_a_time_when_the_product_is_huge(
    dummy: tuple[ManifestSpec, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(grid, "MAX_CHOICE_POINTS", 3)

    points, reduced = grid.choice_points(operation(dummy[0]))

    # a base point, two other resolutions, one other height system (not 3 x 2)
    assert reduced
    assert len(points) == 4
    assert {"resolution": "0_5m", "vertical_crs": "evrf2007"} in points


def test_free_samples_take_complete_rows_without_geometry_files(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    rows = [
        *sample_rows(),
        row("c", "fetch_dem", {"area": sheet("N-34-130-D-d-2-3")}, "resolution"),
        row(
            "d",
            "fetch_dem",
            {"area": {"type": "geometry", "path": "a.shp", "layer": None}},
        ),
        row("e", "make_dem", {"area": sheet("M-34-12-A-a-1-2")}),
    ]

    samples = grid.free_samples(operation(dummy[0]), rows)

    # the incomplete row, the geometry file and the other operation are left out
    assert samples == [{"area": sheet("N-34-130-D-d-2-4")}, {"area": sheet("7.171.21")}]


def test_free_samples_keep_few_per_shape_but_every_shape(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    same = [
        row(f"s{n}", "fetch_dem", {"area": sheet(f"N-34-130-D-d-2-{n}")})
        for n in range(1, 6)
    ]
    other = row("t", "fetch_dem", {"area": sheet("7.171.21")})

    samples = grid.free_samples(operation(dummy[0]), [*same, other])

    assert [item["area"]["code"] for item in samples] == [
        "N-34-130-D-d-2-1",
        "7.171.21",
        "N-34-130-D-d-2-2",
    ]


def test_points_skip_samples_that_leave_a_required_value_out(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    spec = operation(dummy[0])

    points, _ = grid.points(spec, [{}, {"area": sheet("N-34-130-D-d-2-4")}])

    assert len(points) == 6
    assert all("area" in point for point in points)


def test_points_cover_yes_no_parameters_and_fill_free_defaults() -> None:
    spec = cast(
        OperationSpec,
        {
            "id": "x",
            "params": [
                {"name": "flag", "type": "bool"},
                {
                    "name": "count",
                    "type": "free",
                    "extractor": "duration",
                    "default": 3,
                },
            ],
        },
    )

    points, _ = grid.points(spec, [{}])

    # an optional yes/no may stay unset; a free default is what the pipeline sets
    assert sorted(map(json.dumps, points)) == sorted(
        json.dumps(point)
        for point in (
            {"count": 3},
            {"flag": False, "count": 3},
            {"flag": True, "count": 3},
        )
    )


# --- the check: a conforming tool ------------------------------------------------


def test_conforming_tool_has_no_errors_or_warnings(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    report = run(dummy)

    assert report.status == "checked"
    assert (report.operations, report.points) == (1, 12)
    assert keys(report, "error") == [] and keys(report, "warning") == []
    # the rejected pair 5 m + KRON86 is an answer the user can change: information
    matrix = only(report, "x2_matrix")
    assert matrix.severity == "info"
    assert matrix.args["params"] == "resolution, vertical_crs"
    assert matrix.args["rejected"] == "2"


def test_check_never_runs_a_command_only_validates_and_looks_up(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    client = FakeToolClient(validation={"elevation download": tool_rule})

    run(dummy, client=client)

    assert client.network_calls == []
    assert {method for method, _ in client.calls} == {"validate", "lookup"}


# --- X1: commands ----------------------------------------------------------------


def test_command_missing_from_the_catalog_is_an_error(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def edit(manifest: ManifestSpec) -> None:
        operation(manifest)["commands"] = ["elevation fetch"]

    report = run(dummy, edit=edit)

    assert only(report, "x1_command_missing").args["command"] == "elevation fetch"
    # the builder still emits the command that is no longer declared
    assert "x1_undeclared_command" in keys(report, "error")


def test_command_that_validate_does_not_take_is_an_error(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def edit(manifest: ManifestSpec) -> None:
        operation(manifest)["commands"] = [
            "elevation download",
            "elevation availability",
        ]

    assert "x1_command_not_data" in keys(run(dummy, edit=edit), "error")


def test_builder_emitting_an_undeclared_command_is_an_error(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def edit(manifest: ManifestSpec) -> None:
        operation(manifest)["calls"] = "test_scaffold:other_command_builder"

    report = run(dummy, edit=edit)

    assert only(report, "x1_undeclared_command").args["command"] == "elevation fetch"


def test_tool_that_rejects_the_command_itself_is_an_error(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def rule(call: CatalogCall) -> ToolError | None:
        return reject(call, "not a data command", option="command")

    assert "x1_command_rejected" in keys(run(dummy, rule=rule), "error")


# --- X2: what the tool's rejections mean -----------------------------------------


def test_option_the_tool_requires_but_the_builder_omits_is_drift(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def edit(manifest: ManifestSpec) -> None:
        operation(manifest)["calls"] = "test_scaffold:tolerant_builder"
        del param(manifest, "vertical_crs")["required"]

    report = run(dummy, edit=edit)

    missing = only(report, "x2_missing_option")
    assert (missing.severity, missing.args["option"]) == ("error", "vertical_crs")


def test_option_the_tool_no_longer_knows_is_drift(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    catalog = make_catalog()
    download = catalog.commands["elevation download"]
    without = replace(
        download, options=tuple(o for o in download.options if o.name != "resolution")
    )

    report = run(dummy, catalog=replace(catalog, commands={download.id: without}))

    assert only(report, "x2_unknown_option").args["option"] == "resolution"


def test_rejection_of_an_option_the_operation_fixes_is_drift(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def rule(call: CatalogCall) -> ToolError | None:
        return reject(call, "nmt is gone", option="product")

    report = run(dummy, rule=rule)

    # no parameter of the operation names "product": no answer of the user helps
    assert only(report, "x2_unroutable").args["option"] == "product"
    assert "x2_nothing_accepted" in keys(report, "error")


def test_rejection_that_names_no_option_is_drift(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def rule(call: CatalogCall) -> ToolError | None:
        return reject(call, "something is wrong")

    assert "x2_unattributed" in keys(run(dummy, rule=rule), "error")


def test_rejection_inside_an_option_that_a_parameter_answers_is_information(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    report = run(dummy, rule=nested_rule, catalog=nested_catalog(), edit=nested_edit)

    assert keys(report, "error") == [] and keys(report, "warning") == []
    # the paths settings.resolution and settings.vertical_crs are routed like the
    # plain options of the conforming tool
    matrix = only(report, "x2_matrix")
    assert matrix.args["params"] == "resolution, vertical_crs"
    assert matrix.args["rejected"] == "2"


def test_rejection_inside_an_option_that_no_parameter_answers_is_drift(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def edit(manifest: ManifestSpec) -> None:
        operation(manifest)["calls"] = "test_scaffold:unrouted_builder"

    report = run(dummy, rule=nested_rule, catalog=nested_catalog(), edit=edit)

    unroutable = only(report, "x2_unroutable")
    assert unroutable.args["option"] == "settings.resolution, settings.vertical_crs"


def test_rejection_of_an_option_the_call_lacks_inside_another_is_drift(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def rule(call: CatalogCall) -> ToolError | None:
        return reject(call, "the height is required", option="settings.height")

    report = run(dummy, rule=rule, catalog=nested_catalog(), edit=nested_edit)

    assert only(report, "x2_missing_option").args["option"] == "settings.height"


def test_rejection_inside_an_option_the_tool_does_not_know_is_drift(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    # the catalog of the dummy tool has no option "settings"
    report = run(dummy, rule=nested_rule, edit=nested_edit)

    assert only(report, "x2_unknown_option").args["option"] == "settings.resolution"


def test_failure_that_is_no_tool_error_is_reported(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def rule(call: CatalogCall) -> ToolError | None:
        raise RuntimeError("the client leaked its own exception")

    report = run(dummy, rule=rule)

    assert only(report, "x2_unexpected_error").severity == "error"


def test_builder_that_raises_is_reported_once_per_error(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def edit(manifest: ManifestSpec) -> None:
        operation(manifest)["calls"] = "test_scaffold:failing_builder"

    report = run(dummy, edit=edit)

    assert keys(report).count("x2_builder_error") == 1
    assert "KeyError" in only(report, "x2_builder_error").args["error"]


def test_builder_that_cannot_be_loaded_is_reported(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def edit(manifest: ManifestSpec) -> None:
        operation(manifest)["calls"] = "no_such_module:builder"

    assert "x2_builder_unloadable" in keys(run(dummy, edit=edit), "error")


def test_grid_is_reduced_and_says_so_when_the_product_is_huge(
    dummy: tuple[ManifestSpec, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(grid, "MAX_CHOICE_POINTS", 3)

    report = run(dummy)

    assert only(report, "x2_grid_reduced").severity == "warning"


# --- X3: dead options -------------------------------------------------------------


def test_option_the_tool_accepts_at_no_point_is_dead(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def rule(call: CatalogCall) -> ToolError | None:
        if call.options.get("resolution") == "0.5m":
            return reject(call, "0.5 m is gone", option="resolution")
        return tool_rule(call)

    dead = only(run(dummy, rule=rule), "x3_dead_option")

    assert (dead.args["param"], dead.args["options"]) == ("resolution", "0_5m")


# --- X4 / X5: coverage -------------------------------------------------------------


def accepting_2m(call: CatalogCall) -> ToolError | None:
    return None if call.options.get("resolution") == "2m" else tool_rule(call)


def test_value_the_tool_accepts_but_the_manifest_lacks_is_a_gap(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    gap = only(run(dummy, rule=accepting_2m), "x4_gap")

    assert (gap.severity, gap.args["value"], gap.args["param"]) == (
        "error",
        "2m",
        "resolution",
    )


def test_excluded_value_is_no_gap(dummy: tuple[ManifestSpec, Path]) -> None:
    def edit(manifest: ManifestSpec) -> None:
        operation(manifest)["excluded"]["resolution"]["2m"] = "not offered"

    assert "x4_gap" not in keys(run(dummy, rule=accepting_2m, edit=edit))


def test_value_rejected_in_every_scope_of_the_operation_is_no_gap(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    # the catalog lists 2m, but this tool refuses it for the operation's sheets
    assert "x4_gap" not in keys(run(dummy))


def test_value_accepted_only_without_a_companion_option_is_a_gap(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def edit(manifest: ManifestSpec) -> None:
        operation(manifest)["excluded"] = {}

    # 100 m is taken only without a height system, which the calls always send
    report = run(dummy, edit=edit)

    assert only(report, "x4_gap").args["value"] == "100m"


def test_exclusion_of_a_value_that_is_taken_only_without_a_companion_is_not_stale(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    assert "x5_excluded_rejected" not in keys(run(dummy))


def test_exclusion_of_a_value_the_tool_never_takes_is_stale(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def rule(call: CatalogCall) -> ToolError | None:
        if call.options.get("resolution") == "100m":
            return reject(call, "100 m is gone", option="resolution")
        return tool_rule(call)

    stale = only(run(dummy, rule=rule), "x5_excluded_rejected")

    assert (stale.severity, stale.args["value"]) == ("warning", "100m")


def test_exclusion_of_a_value_missing_from_the_catalog_is_stale(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def edit(manifest: ManifestSpec) -> None:
        operation(manifest)["excluded"]["resolution"]["3m"] = "not in the catalog"

    stale = only(run(dummy, edit=edit), "x5_excluded_unknown")

    assert stale.args["value"] == "3m"


# --- X6: required options ----------------------------------------------------------


def test_default_behind_an_option_the_tool_requires_is_a_warning(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    catalog = make_catalog()
    download = catalog.commands["elevation download"]
    required = replace(
        download,
        options=tuple(
            replace(o, required=True) if o.name == "vertical_crs" else o
            for o in download.options
        ),
    )

    def edit(manifest: ManifestSpec) -> None:
        crs = param(manifest, "vertical_crs")
        crs["default"] = "evrf2007"

    report = run(
        dummy, catalog=replace(catalog, commands={download.id: required}), edit=edit
    )

    assert only(report, "x6_default_on_required").severity == "warning"


def test_optional_parameter_behind_an_option_the_tool_requires_is_a_warning(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    catalog = make_catalog()
    download = catalog.commands["elevation download"]
    required = replace(
        download,
        options=tuple(
            replace(o, required=True) if o.name == "vertical_crs" else o
            for o in download.options
        ),
    )

    def edit(manifest: ManifestSpec) -> None:
        operation(manifest)["calls"] = "test_scaffold:tolerant_builder"
        del param(manifest, "vertical_crs")["required"]

    report = run(
        dummy, catalog=replace(catalog, commands={download.id: required}), edit=edit
    )

    assert only(report, "x6_optional_for_required").args["param"] == "vertical_crs"


# --- X7: effects ---------------------------------------------------------------------


def test_lookup_that_takes_a_command_with_effects_is_an_error(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    client = FakeToolClient(
        validation={"elevation download": tool_rule},
        documents={"lookup:elevation download": {"rows": []}},
    )

    leak = only(run(dummy, client=client), "x7_lookup_effects")

    assert (leak.severity, leak.args["command"]) == ("error", "elevation download")
    assert leak.args["effects"] == "network, writes"


def test_lookup_that_fails_without_a_tool_error_is_an_error(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    class Careless(FakeToolClient):
        def lookup(self, call: CatalogCall) -> ToolDocument:
            raise RuntimeError("no ToolError")

    client = Careless(validation={"elevation download": tool_rule})

    assert "x7_lookup_unexpected" in keys(run(dummy, client=client), "error")


def test_network_attempt_during_the_check_is_refused_and_recorded(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def rule(call: CatalogCall) -> ToolError | None:
        with contextlib.suppress(OSError):
            socket.create_connection(("tool-server.invalid", 443), timeout=1)
        return tool_rule(call)

    attempt = only(run(dummy, rule=rule), "x7_network_attempt")

    assert attempt.severity == "error"
    assert attempt.args["address"] == "tool-server.invalid"


def test_files_created_during_the_check_are_reported_and_stay_out_of_the_project(
    dummy: tuple[ManifestSpec, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def rule(call: CatalogCall) -> ToolError | None:
        Path(".tool_cache.db").write_text("stray", encoding="utf-8")
        return tool_rule(call)

    created = only(run(dummy, rule=rule), "x7_files_created")

    assert created.severity == "error"
    assert ".tool_cache.db" in created.args["files"]
    assert not (tmp_path / ".tool_cache.db").exists()


def test_download_operation_without_a_check_step_is_a_warning(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def edit(manifest: ManifestSpec) -> None:
        del operation(manifest)["check"]

    missing = only(run(dummy, edit=edit), "x7_no_check")

    assert (missing.severity, missing.args["commands"]) == (
        "warning",
        "elevation download",
    )


def test_download_operation_that_says_why_it_has_no_check_is_not_warned_about(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def edit(manifest: ManifestSpec) -> None:
        del operation(manifest)["check"]
        operation(manifest)["no_check"] = "the tool has nothing to ask the source"

    report = run(dummy, edit=edit)

    assert keys(report, "warning") == [] and keys(report, "error") == []


def test_no_check_that_no_command_of_the_operation_needs_is_stale(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    catalog = make_catalog()
    download = catalog.commands["elevation download"]
    read_only = replace(download, writes=False)

    def edit(manifest: ManifestSpec) -> None:
        del operation(manifest)["check"]
        operation(manifest)["no_check"] = "the tool has nothing to ask the source"

    report = run(
        dummy,
        catalog=replace(catalog, commands={**catalog.commands, download.id: read_only}),
        edit=edit,
    )

    assert only(report, "x7_no_check_stale").severity == "warning"
    assert "x7_no_check" not in keys(report)


def test_guard_records_attempts_lists_new_files_and_restores_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    watched, work = tmp_path / "watched", tmp_path / "work"
    watched.mkdir()
    work.mkdir()
    (watched / "old.txt").write_text("old", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    resolver, connector = socket.getaddrinfo, socket.socket.connect

    with OfflineGuard(watched, cwd=work) as guard:
        with pytest.raises(OSError, match="refused"):
            socket.getaddrinfo("remote.invalid", 80)
        # the loopback is no way out
        assert socket.getaddrinfo("localhost", 80)
        Path("made.txt").write_text("new", encoding="utf-8")
        (watched / "sub").mkdir()
        (watched / "sub" / "new.txt").write_text("new", encoding="utf-8")

    assert guard.attempts == ["remote.invalid"]
    assert guard.created == ["sub", str(Path("sub") / "new.txt")]
    assert (work / "made.txt").exists() and not (tmp_path / "made.txt").exists()
    assert Path.cwd() == tmp_path
    assert (socket.getaddrinfo, socket.socket.connect) == (resolver, connector)


# --- X8: texts and schemas -----------------------------------------------------------


def test_error_code_without_a_polish_text_is_an_error(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    catalog = make_catalog(
        error_codes=("invalid_input", "usage_error", "quota_exceeded")
    )

    missing = only(run(dummy, catalog=catalog), "x8_error_text_missing")

    # usage_error is exempt (command line only) and invalid_input has its text
    assert missing.args["codes"] == "quota_exceeded"
    assert missing.args["file"] == "pl.toml"


def test_translation_file_that_cannot_be_read_is_an_error(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def edit(manifest: ManifestSpec) -> None:
        manifest["translations"] = {"pl": "absent.toml"}

    assert "x8_translation_unreadable" in keys(run(dummy, edit=edit), "error")


def test_document_schema_the_client_does_not_know_is_an_error(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    catalog = make_catalog()
    download = catalog.commands["elevation download"]
    newer = replace(download, result_schema="dummy-download/2")

    report = run(dummy, catalog=replace(catalog, commands={download.id: newer}))

    unknown = only(report, "x8_unknown_schema")
    assert (unknown.args["schema"], unknown.args["known"]) == (
        "dummy-download/2",
        "dummy-download/1",
    )


# --- X9 / X10: what is not covered -----------------------------------------------


def test_data_commands_no_operation_uses_are_information(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    catalog = make_catalog()
    commands = {
        **catalog.commands,
        "elevation list": CommandInfo("elevation list", "elevation"),
    }

    unexposed = only(
        run(dummy, catalog=replace(catalog, commands=commands)), "x9_unexposed"
    )

    assert (unexposed.severity, unexposed.args["commands"]) == (
        "info",
        "elevation list",
    )


def test_operation_without_complete_rows_is_skipped_with_a_warning(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    rows = [row("c", "fetch_dem", {"area": sheet("N-34-130-D-d-2-3")}, "resolution")]

    report = run(dummy, rows=rows)

    assert only(report, "x10_no_samples").args["params"] == "area"
    assert report.points == 0
    assert keys(report, "error") == []


def test_samples_that_never_make_a_point_are_a_warning(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def edit(manifest: ManifestSpec) -> None:
        # a second required free value that no row states
        operation(manifest)["params"].append(
            {"name": "year", "type": "free", "extractor": "area", "required": True}
        )

    assert "x10_no_points" in keys(run(dummy, edit=edit), "warning")


# --- tools: which are checked, light form ----------------------------------------


def test_operation_filter_runs_no_tool_wide_check(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    catalog = make_catalog(error_codes=("invalid_input", "quota_exceeded"))

    narrow = run(dummy, catalog=catalog, operations=["fetch_dem"])
    wide = run(dummy, catalog=catalog, operations=["fetch_dem"], tool_level=True)

    assert "x8_error_text_missing" not in keys(narrow)
    assert "x8_error_text_missing" in keys(wide)


def test_light_check_varies_one_choice_at_a_time_and_reports_coverage_only(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    report = run(dummy, rule=accepting_2m, light=True)

    # one sample and a base point with three variations, no matrix, no dead options
    assert report.points == 4
    assert keys(report) == ["x4_gap"]


def test_light_findings_are_none_for_a_tool_without_calls_or_reader(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    manifest, folder = dummy
    bare = deepcopy(manifest)
    bare["operations"] = [o for o in bare["operations"] if "calls" not in o]

    assert light_findings(bare, folder, "1.2.0", commands=[]) is None
    # there is no reader module for the dummy tool
    assert load_reader(TOOL) is None
    assert light_findings(manifest, folder, "1.2.0", commands=[]) is None


@pytest.mark.parametrize(
    ("lookup_error", "require", "severity", "key"),
    [
        (ModuleNotFoundError, False, "info", "tool_missing"),
        (ModuleNotFoundError, True, "error", "tool_missing"),
    ],
)
def test_tool_that_is_not_installed_is_skipped_or_an_error_in_ci(
    dummy: tuple[ManifestSpec, Path],
    lookup_error: type[Exception],
    require: bool,
    severity: str,
    key: str,
) -> None:
    import importlib.metadata

    def missing(_: str) -> str:
        raise importlib.metadata.PackageNotFoundError(TOOL)

    manifest, folder = dummy
    (report,) = check_tools(
        [(manifest, folder)], commands=[], version_lookup=missing, require_tools=require
    )

    assert report.status == "missing"
    assert [(f.severity, f.key) for f in report.findings] == [(severity, key)]
    assert not finding_text(report.findings[0], TEXTS).startswith(key)


def test_tool_outside_the_supported_versions_is_skipped(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    manifest, folder = dummy
    (report,) = check_tools(
        [(manifest, folder)], commands=[], version_lookup=lambda _: "2.0.0"
    )

    assert (report.status, report.version) == ("unsupported", "2.0.0")
    assert keys(report) == ["tool_unsupported"]


def test_tool_without_calls_has_no_catalog_to_check(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def edit(manifest: ManifestSpec) -> None:
        manifest["operations"] = [o for o in manifest["operations"] if "calls" not in o]

    report = run(dummy, edit=edit)

    assert (report.status, keys(report)) == ("skipped", ["tool_no_calls"])


def test_tool_without_a_reader_cannot_be_checked(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    manifest, folder = dummy
    (report,) = check_tools(
        [(manifest, folder)], commands=[], version_lookup=lambda _: "1.2.0", readers={}
    )

    assert (report.status, keys(report, "error")) == ("failed", ["tool_no_reader"])


def test_catalog_that_cannot_be_read_is_an_error(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    def broken() -> ToolCatalog:
        raise ImportError("the tool is broken")

    manifest, folder = dummy
    reader = Reader(broken, lambda c, o: Verdict(True), lambda root: {})
    (report,) = check_tools(
        [(manifest, folder)],
        commands=[],
        version_lookup=lambda _: "1.2.0",
        readers={TOOL: reader},
    )

    assert report.status == "failed"
    assert "the tool is broken" in only(report, "catalog_unreadable").args["error"]


def test_client_that_cannot_be_built_is_an_error(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    manifest, folder = dummy
    manifest["client"] = "no_such_module:create_client"
    (report,) = check_tools(
        [(manifest, folder)],
        commands=sample_rows(),
        version_lookup=lambda _: "1.2.0",
        readers={TOOL: reader_of(make_catalog())},
    )

    assert report.status == "failed"
    assert "no_such_module" in only(report, "client_failed").args["error"]


def test_client_is_built_by_the_manifest_from_scratch_settings(
    dummy: tuple[ManifestSpec, Path], dummy_client: ModuleType, tmp_path: Path
) -> None:
    dummy_client.PROGRAM["validation"] = {"elevation download": tool_rule}
    manifest, folder = dummy
    (report,) = check_tools(
        [(manifest, folder)],
        commands=sample_rows(),
        version_lookup=lambda _: "1.2.0",
        readers={TOOL: reader_of(make_catalog())},
    )

    (settings,) = dummy_client.BUILT
    store = Path(settings["store_dir"])
    # a scratch folder of the check: not below the project, and gone afterwards
    assert not store.is_relative_to(Path.cwd()) and not store.exists()
    assert keys(report, "error") == []


# --- the command line --------------------------------------------------------------


@pytest.fixture
def cli(
    dummy: tuple[ManifestSpec, Path], capsys: pytest.CaptureFixture[str]
) -> Callable[..., tuple[int, str, str]]:
    """``retman-scaffold`` on the dummy tool: exit code, standard output, errors."""

    def invoke(
        *argv: str,
        rule: Callable[[CatalogCall], ToolError | None] = tool_rule,
        reader: Reader | None = None,
        version: str = "1.2.0",
        **options: Any,
    ) -> tuple[int, str, str]:
        manifest, folder = dummy
        code = main(
            list(argv),
            manifests=[(manifest, folder)],
            version_lookup=lambda _: version,
            readers={TOOL: reader or reader_of(make_catalog())},
            clients={TOOL: FakeToolClient(validation={"elevation download": rule})},
            commands=sample_rows(),
            **options,
        )
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return invoke


def test_check_of_a_conforming_tool_exits_zero_and_hides_information(
    cli: Callable[..., tuple[int, str, str]],
) -> None:
    code, out, err = cli("--check")

    assert (code, err) == (0, "")
    assert (
        "dummy_tool 1.2.0 (obsługiwane >=1.2,<2): operacje 1, punkty siatki 12" in out
    )
    assert "Kontrola rozjazdów przeszła: błędy 0, ostrzeżenia 0, informacje 1." in out
    assert "x2" not in out and "--verbose" in out


def test_verbose_check_shows_the_information_lines(
    cli: Callable[..., tuple[int, str, str]],
) -> None:
    code, out, _ = cli("--check", "--verbose")

    assert code == 0
    assert "· X2" in out and "resolution, vertical_crs" in out


def test_check_with_errors_exits_one_and_names_the_problem(
    cli: Callable[..., tuple[int, str, str]],
) -> None:
    code, out, _ = cli("--check", rule=accepting_2m)

    assert code == 1
    assert "✗ X4" in out and "„2m”" in out
    assert "Kontrola rozjazdów wykryła błędy: błędy 1" in out


def test_check_json_is_a_document_with_findings_and_the_exit_code(
    cli: Callable[..., tuple[int, str, str]],
) -> None:
    code, out, _ = cli("--check", "--json", rule=accepting_2m)

    document = json.loads(out)
    assert (code, document["exit_code"], document["schema"]) == (
        1,
        1,
        "retman-scaffold-check/1",
    )
    (tool,) = document["tools"]
    assert (tool["tool"], tool["status"], tool["points"]) == (TOOL, "checked", 12)
    gap = next(f for f in tool["findings"] if f["check"] == "X4")
    assert gap["severity"] == "error" and gap["args"]["value"] == "2m"
    assert "„2m”" in gap["text"]


def test_missing_tool_is_skipped_unless_ci_requires_it(
    cli: Callable[..., tuple[int, str, str]],
) -> None:
    skipped = cli("--check", "--verbose", version="2.0.0")
    required = cli("--check", "--require-tools", version="2.0.0")

    assert skipped[0] == 0 and "poza obsługiwanym zakresem" in skipped[1]
    assert required[0] == 1 and "✗ T" in required[1]


def test_check_can_be_limited_to_one_tool_and_operation(
    cli: Callable[..., tuple[int, str, str]],
) -> None:
    assert cli("--check", "--tool", TOOL, "--operation", "fetch_dem")[0] == 0
    code, _, err = cli("--check", "--tool", "other")
    assert (code, "Nieznane narzędzie „other”" in err) == (2, True)
    code, _, err = cli("--check", "--operation", "nope")
    assert (code, "Nieznana operacja „nope”" in err) == (2, True)


def test_check_takes_samples_from_a_commands_file(
    dummy: tuple[ManifestSpec, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record = {
        "id": "a",
        "command": "polecenie",
        "operation": "fetch_dem",
        "params": {"area": sheet("N-34-130-D-d-2-4")},
        "tags": ["complete"],
    }
    path = tmp_path / "commands.jsonl"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    code = main(
        ["--check", "--commands", str(path)],
        manifests=[dummy],
        version_lookup=lambda _: "1.2.0",
        readers={TOOL: reader_of(make_catalog())},
        clients={TOOL: FakeToolClient(validation={"elevation download": tool_rule})},
    )

    # one sample times the six combinations of resolution and height system
    assert code == 0 and "punkty siatki 6," in capsys.readouterr().out


def test_check_says_so_when_the_commands_file_is_malformed(
    dummy: tuple[ManifestSpec, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "commands.jsonl"
    path.write_text("this is not JSON\n", encoding="utf-8")

    code = main(
        ["--check", "--commands", str(path)],
        manifests=[dummy],
        version_lookup=lambda _: "1.2.0",
        readers={TOOL: reader_of(make_catalog())},
    )

    captured = capsys.readouterr()
    assert (code, captured.out) == (1, "")
    assert "Nie można odczytać zbioru poleceń retman-eval" in captured.err


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "Podaj --check albo polecenie list lub draft"),
        (["--check", "list", TOOL], "--check nie łączy się"),
        (["draft", TOOL, "x", "--fix", "product"], "wymaga postaci nazwa=wartość"),
    ],
)
def test_usage_mistakes_exit_two_with_a_polish_message(
    cli: Callable[..., tuple[int, str, str]], argv: list[str], message: str
) -> None:
    code, out, err = cli(*argv)

    assert (code, out) == (2, "")
    assert err.startswith("Błędne użycie:") and message in err


def test_list_shows_every_command_with_its_operations_and_a_suggested_use(
    cli: Callable[..., tuple[int, str, str]],
) -> None:
    code, out, _ = cli("list", TOOL)

    lines = out.splitlines()
    assert code == 0 and lines[0] == "dummy_tool 1.2.0: komend w katalogu: 2"
    download = next(line for line in lines if line.startswith("elevation download"))
    assert "sieć, zapis" in download and "fetch_dem" in download
    assert "operacja pobierająca dane" in download
    assert "zapytanie sieciowe spoza komend danych" in next(
        line for line in lines if line.startswith("elevation availability")
    )


def test_list_of_a_tool_without_a_reader_fails_with_a_message(
    dummy: tuple[ManifestSpec, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["list", TOOL], manifests=[dummy], readers={})

    assert code == 1
    assert "nie ma czytnika katalogu" in capsys.readouterr().err


# --- drafts -------------------------------------------------------------------------

# What a catalog like Kartograf's accepts for NMT sheets: the pairs of resolution and
# height system; 100 m takes none
VALID_PAIRS = {
    ("0.15m", "EVRF2007"),
    ("0.5m", "EVRF2007"),
    ("0.5m", "KRON86"),
    ("1m", "EVRF2007"),
    ("1m", "KRON86"),
    ("5m", "EVRF2007"),
    ("100m", None),
}


def draft_catalog() -> ToolCatalog:
    command = CommandInfo(
        "elevation download",
        "elevation",
        "Download elevation data",
        options=(
            OptionInfo("product", required=True, allowed=("nmt", "nmpt")),
            OptionInfo("sheet", description="Sheet code"),
            OptionInfo("bbox"),
            OptionInfo("bbox_crs", allowed=("EPSG:2180", "EPSG:4326")),
            OptionInfo(
                "resolution",
                allowed=("0.15m", "0.5m", "1m", "2m", "5m", "100m"),
                description="Grid size",
            ),
            OptionInfo("vertical_crs", allowed=("EVRF2007", "KRON86")),
            OptionInfo("workers", kind="int", minimum=1, maximum=16),
            OptionInfo("cutout", kind="flag"),
        ),
        examples=(
            {
                "product": "nmt",
                "sheet": "N-34-130-D-d-2-4",
                "resolution": "1m",
                "vertical_crs": "EVRF2007",
            },
        ),
    )
    return ToolCatalog(TOOL, "1.2.0", {command.id: command})


def draft_reader(
    valid: Callable[[Any, Any], bool] = lambda resolution, crs: (
        (resolution, crs) in VALID_PAIRS
    ),
) -> Reader:
    def validate(command: str, options: Any) -> Verdict:
        if options.get("product") != "nmt":
            return Verdict(False, option="product", detail="nmt only here")
        ok = valid(options.get("resolution"), options.get("vertical_crs"))
        return Verdict(ok, detail="" if ok else "pair rejected")

    return Reader(draft_catalog, validate, lambda root: {})


def test_draft_narrows_choices_to_what_the_tool_accepts() -> None:
    draft = build_draft(
        draft_catalog(),
        draft_reader(),
        "elevation download",
        fix={"product": "nmt"},
        only=["sheet", "resolution", "vertical_crs"],
        operation_id="download_dem_sheet",
    )

    entry = ast.literal_eval(draft.manifest[draft.manifest.index("\n{") + 1 :])
    params = {p["name"]: p for p in entry["params"]}
    assert (entry["id"], entry["commands"], list(params)) == (
        "download_dem_sheet",
        ["elevation download"],
        ["area", "resolution", "vertical_crs"],
    )
    assert params["area"]["accepts"] == ["sheet"]
    # 2 m is in the catalog but in no accepted pair; dots become underscores
    assert params["resolution"]["options"] == ["0_15m", "0_5m", "1m", "5m", "100m"]
    assert params["resolution"]["tool_values"] == {"0_15m": "0.15m", "0_5m": "0.5m"}
    # 100 m takes no height system: it applies under every other resolution
    assert params["vertical_crs"]["depends_on"] == {
        "resolution": ["0_15m", "0_5m", "1m", "5m"]
    }
    assert params["vertical_crs"]["required"] is True
    assert (
        "valid pairs (resolution/vertical_crs): 0.15m/EVRF2007  0.5m/EVRF2007,KRON86"
        in draft.manifest
    )
    assert "100m/-" in draft.manifest


def test_draft_builder_compiles_and_translations_have_every_required_key() -> None:
    draft = build_draft(
        draft_catalog(),
        draft_reader(),
        "elevation download",
        fix={"product": "nmt", "cutout": True},
        only=["sheet", "resolution", "vertical_crs", "workers"],
        operation_id="dem",
    )

    compile(draft.builder, "<draft>", "exec")
    assert (
        'options: dict[str, object] = {"product": "nmt", "cutout": True}'
        in draft.builder
    )
    assert 'options["sheet"] = area["code"]' in draft.builder
    assert 'if "vertical_crs" in params:' in draft.builder
    assert 'params={"sheet": "area"}' in draft.builder
    texts = tomllib.loads(draft.translations)["operations"]["dem"]
    assert set(texts) == {"label", "description", "params"}
    area, resolution = texts["params"]["area"], texts["params"]["resolution"]
    assert set(area) == {"label", "question", "example"}
    assert set(resolution) == {"label", "question", "model_question", "options"}
    assert set(resolution["options"]) == {
        "0_15m",
        "0_5m",
        "1m",
        "5m",
        "100m",
        "unspecified",
    }
    assert set(resolution["options"]["1m"]) == {"label", "description"}
    assert set(resolution["options"]["unspecified"]) == {"description"}
    # the numeric option keeps its bounds, the manifest keeps its markers
    assert (
        '"range": [1, 16]' in draft.manifest and '"extractor": "TODO"' in draft.manifest
    )


def test_draft_says_so_when_the_tool_rejects_every_probe() -> None:
    draft = build_draft(
        draft_catalog(),
        draft_reader(valid=lambda resolution, crs: False),
        "elevation download",
        fix={"product": "nmt"},
        only=["resolution"],
    )

    assert (
        "choices not narrowed: the tool rejected every probe (pair rejected)"
        in draft.manifest
    )
    # nothing was dropped: the whole catalog list is offered
    assert '"options": ["0_15m", "0_5m", "1m", "2m", "5m", "100m"]' in draft.manifest


def test_draft_marks_a_choice_with_more_options_than_a_decision_offers() -> None:
    catalog = draft_catalog()
    command = catalog.commands["elevation download"]
    many = tuple(f"{n}m" for n in range(1, 11))
    options = tuple(
        replace(o, allowed=many) if o.name == "resolution" else o
        for o in command.options
    )
    catalog = replace(catalog, commands={command.id: replace(command, options=options)})

    draft = build_draft(
        catalog,
        draft_reader(valid=lambda resolution, crs: True),
        "elevation download",
        fix={"product": "nmt"},
        only=["resolution"],
    )

    assert (
        MAX_OPTIONS == 9
        and f"SPLIT_REQUIRED: 10 options, more than the {MAX_OPTIONS}" in draft.manifest
    )


@pytest.mark.parametrize(
    ("command", "fix", "only", "message"),
    [
        ("elevation fetch", {}, None, "unknown command 'elevation fetch'"),
        ("elevation download", {"colour": "red"}, None, "has no option 'colour'"),
        ("elevation download", {}, ["colour"], "has no option 'colour'"),
        (
            "elevation download",
            {"product": "nmt"},
            ["product"],
            "both fixed and exposed",
        ),
    ],
)
def test_draft_refuses_unknown_commands_and_contradictory_options(
    command: str, fix: dict[str, object], only: list[str] | None, message: str
) -> None:
    with pytest.raises(ScaffoldError, match=message):
        build_draft(draft_catalog(), draft_reader(), command, fix=fix, only=only)


def test_draft_on_the_command_line_prints_or_writes_and_never_overwrites(
    dummy: tuple[ManifestSpec, Path],
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    argv = [
        "draft",
        TOOL,
        "elevation download",
        "--fix",
        "product=nmt",
        "--only",
        "sheet,resolution",
        "--only",
        "vertical_crs",
        "--id",
        "download_dem_sheet",
    ]
    options: dict[str, Any] = {
        "manifests": [dummy],
        "readers": {TOOL: draft_reader()},
        "tools_dir": tmp_path,
    }

    assert main(argv, **options) == 0
    printed = capsys.readouterr().out
    assert (
        '"id": "download_dem_sheet"' in printed
        and "[operations.download_dem_sheet]" in printed
    )
    assert not (tmp_path / TOOL).exists()

    assert main([*argv, "--write"], **options) == 0
    folder = tmp_path / TOOL / "_drafts"
    assert sorted(p.name for p in folder.iterdir()) == [
        "download_dem_sheet.py",
        "download_dem_sheet.toml",
    ]
    assert tomllib.loads(
        (folder / "download_dem_sheet.toml").read_text(encoding="utf-8")
    )
    assert b"\r" not in (folder / "download_dem_sheet.py").read_bytes()
    capsys.readouterr()

    assert main([*argv, "--write"], **options) == 1
    assert "Plik szkicu już istnieje" in capsys.readouterr().err


# --- retman doctor -----------------------------------------------------------------


def conformance(
    dummy: tuple[ManifestSpec, Path],
    rule: Callable[[CatalogCall], ToolError | None],
    seen: list[str] | None = None,
) -> Callable[[ManifestSpec, Path, str], list[Finding] | None]:
    """The light check of ``retman doctor`` for the dummy tool, as it takes it."""
    client = FakeToolClient(validation={"elevation download": rule})

    def check(
        manifest: ManifestSpec, directory: Path, version: str
    ) -> list[Finding] | None:
        if seen is not None:
            seen.append(manifest["tool"])
        return light_findings(
            manifest,
            directory,
            version,
            commands=sample_rows(),
            reader=reader_of(make_catalog()),
            client=client,
        )

    return check


def doctor_lines(report: Any, section: str = "conformance") -> list[tuple[str, str]]:
    return [
        (check.status, check.text)
        for found in report.sections
        if found.key == section
        for check in found.checks
    ]


def test_doctor_shows_that_the_descriptions_fit_the_installed_tool(
    dummy: tuple[ManifestSpec, Path], tmp_path: Path
) -> None:
    report, _ = run_doctor(
        tmp_path / "absent.toml",
        tmp_path,
        manifests=[dummy],
        version_lookup=lambda _: "1.2.0",
        conformance=conformance(dummy, tool_rule),
    )

    assert doctor_lines(report) == [
        (
            "ok",
            "dummy_tool 1.2.0: komendy z manifestu są w katalogu narzędzia, "
            "a jego wartości są oferowane albo wyłączone (X1, X4)",
        )
    ]


def test_doctor_names_a_value_a_newer_tool_offers_without_blocking(
    dummy: tuple[ManifestSpec, Path], tmp_path: Path
) -> None:
    report, texts = run_doctor(
        tmp_path / "absent.toml",
        tmp_path,
        manifests=[dummy],
        version_lookup=lambda _: "1.2.0",
        conformance=conformance(dummy, accepting_2m),
    )

    ((status, text),) = doctor_lines(report)
    assert status == "error" and "„2m”" in text and "przyjmuje wartość" in text
    section = next(s for s in report.sections if s.key == "conformance")
    assert (
        section.checks[0].hint
        == "uruchom retman-scaffold --check; opisy tego narzędzia wymagają przeglądu"
    )
    # a drifted description is the author's to fix, not a reason to stop working
    assert not section.checks[0].blocking
    assert "Zgodność opisów z narzędziami" in report.to_text(texts)


def test_doctor_checks_only_tools_in_use_and_never_real_tools_by_default(
    dummy: tuple[ManifestSpec, Path], tmp_path: Path
) -> None:
    seen: list[str] = []

    unused, _ = run_doctor(
        tmp_path / "absent.toml",
        tmp_path,
        manifests=[dummy],
        version_lookup=lambda _: "9.9.9",
        conformance=conformance(dummy, tool_rule, seen),
    )
    # injected manifests without an injected check: no tool is touched
    default, _ = run_doctor(
        tmp_path / "absent.toml",
        tmp_path,
        manifests=[dummy],
        version_lookup=lambda _: "1.2.0",
    )

    assert seen == []  # version outside the supported range: not in use
    assert doctor_lines(unused) == [] and doctor_lines(default) == []


def test_doctor_names_the_operations_it_could_not_check_in_one_line(
    dummy: tuple[ManifestSpec, Path], tmp_path: Path
) -> None:
    def unchecked(
        manifest: ManifestSpec, directory: Path, version: str
    ) -> list[Finding] | None:
        return light_findings(
            manifest,
            directory,
            version,
            commands=[],
            reader=reader_of(make_catalog()),
            client=FakeToolClient(validation={"elevation download": tool_rule}),
        )

    report, _ = run_doctor(
        tmp_path / "absent.toml",
        tmp_path,
        manifests=[dummy],
        version_lookup=lambda _: "1.2.0",
        conformance=unchecked,
    )

    ((status, text),) = doctor_lines(report)
    assert status == "warning"
    assert "nie sprawdzono zgodności operacji (1)" in text and "fetch_dem" in text


def test_light_lines_show_the_hint_on_the_first_problem_only(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    manifest, folder = dummy
    gap = {
        "param": "resolution",
        "command": "elevation download",
        "option": "resolution",
        "value": "2m",
        "version": "1.2.0",
    }
    findings = [
        Finding("X4", "error", TOOL, "x4_gap", gap, "fetch_dem"),
        Finding("X1", "error", TOOL, "x1_command_missing", gap, "fetch_dem"),
        Finding("X10", "warning", TOOL, "x10_no_samples", {"params": "area"}, "other"),
        Finding("X10", "warning", TOOL, "x10_no_points", {}, "other"),
    ]

    lines = light_lines(manifest, folder, "1.2.0", TEXTS, lambda *_: findings)

    assert [line.status for line in lines] == ["error", "error", "warning"]
    assert [line.hint is not None for line in lines] == [True, False, False]
    # the operation that could not be checked is named once, however it failed
    assert lines[-1].text.count("other") == 1


def test_doctor_warns_when_the_check_cannot_run(
    dummy: tuple[ManifestSpec, Path], tmp_path: Path
) -> None:
    from retman.exceptions import EvalDatasetError

    def broken(
        manifest: ManifestSpec, directory: Path, version: str
    ) -> list[Finding] | None:
        raise EvalDatasetError(["commands.jsonl: unreadable"])

    report, _ = run_doctor(
        tmp_path / "absent.toml",
        tmp_path,
        manifests=[dummy],
        version_lookup=lambda _: "1.2.0",
        conformance=broken,
    )

    ((status, text),) = doctor_lines(report)
    assert status == "warning" and "nie udało się sprawdzić zgodności" in text


# --- light form: values that only a gated call carries -----------------------------


def gated_catalog(
    methods: tuple[str, ...] = ("POT", "AMP"),
    variables: tuple[str, ...] = ("H", "Q", "T"),
) -> ToolCatalog:
    """Like IMGWTools in miniature: a ``method`` on two commands, a gated ``params``."""
    catalog = make_catalog()
    method = (OptionInfo("method", allowed=methods),)
    extra = (
        CommandInfo("pmaxtp fetch", "pmaxtp", options=method, network=True),
        CommandInfo("pmaxtp sync", "pmaxtp", options=method, network=True, writes=True),
        CommandInfo(
            "datasets download",
            "datasets",
            options=(
                OptionInfo("dataset", required=True, allowed=("daily", "semiannual")),
                OptionInfo("params", allowed=variables),
            ),
            network=True,
            writes=True,
        ),
    )
    return replace(catalog, commands={**catalog.commands, **{c.id: c for c in extra}})


def method_builder(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """The method goes to ``pmaxtp sync`` only when the store is used."""
    method = ctx.tool_value("method", params["method"])
    command = "pmaxtp sync" if params["storage"] == "store" else "pmaxtp fetch"
    return [CatalogCall(command, {"method": method})]


def variable_builder(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """The variable (a built value, no ``tool_values`` entry) suits one dataset only."""
    options: dict[str, object] = {"dataset": params["dataset"]}
    if "variable" in params:
        options["params"] = params["variable"].upper()
    return [CatalogCall("datasets download", options, params={"params": "variable"})]


GATED_OPERATIONS: list[dict[str, Any]] = [
    {
        "id": "method_like",
        "category": "test",
        "description": "A method that only one of the two commands carries",
        "inputs": [],
        "outputs": ["dem"],
        "params": [
            {
                "name": "storage",
                "type": "choice",
                "options": ["live", "store"],
                "required": True,
            },
            {
                "name": "method",
                "type": "choice",
                "options": ["pot", "amp"],
                "tool_values": {"pot": "POT", "amp": "AMP"},
                "required": True,
            },
        ],
        "calls": "test_scaffold:method_builder",
        "commands": ["pmaxtp fetch", "pmaxtp sync"],
    },
    {
        "id": "variable_like",
        "category": "test",
        "description": "A variable that applies to one dataset only",
        "inputs": [],
        "outputs": ["dem"],
        "params": [
            {
                "name": "dataset",
                "type": "choice",
                "options": ["daily", "semiannual"],
                "required": True,
            },
            {
                "name": "variable",
                "type": "choice",
                "options": ["h", "q", "t"],
                "depends_on": {"dataset": ["semiannual"]},
            },
        ],
        "calls": "test_scaffold:variable_builder",
        "commands": ["datasets download"],
    },
]


def light_gated(
    dummy: tuple[ManifestSpec, Path], catalog: ToolCatalog | None = None
) -> ToolReport:
    """The light check of the two gated operations against a catalog."""

    def add(manifest: ManifestSpec) -> None:
        manifest["operations"].extend(deepcopy(GATED_OPERATIONS))  # type: ignore[arg-type]

    return run(
        dummy,
        catalog=catalog or gated_catalog(),
        edit=add,
        light=True,
        operations=["method_like", "variable_like"],
    )


def test_one_at_a_time_grid_varies_a_gated_parameter_where_it_applies() -> None:
    spec = cast(OperationSpec, GATED_OPERATIONS[1])

    points, reduced = grid.choice_points(spec, reduced=True)

    # "variable" does not apply to the base dataset: without help none of its
    # values would ever be sent
    assert not reduced
    assert [p for p in points if "variable" in p] == [
        {"dataset": "semiannual", "variable": "h"},
        {"dataset": "semiannual", "variable": "q"},
        {"dataset": "semiannual", "variable": "t"},
    ]
    assert {"dataset": "daily"} in points


def test_light_check_does_not_mistake_a_gated_value_for_one_the_manifest_lacks(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    report = light_gated(dummy)

    # the method AMP never meets the store in a one-at-a-time grid, yet the
    # manifest offers it; Q and T are variables of the semiannual dataset only
    assert report.points > 0
    assert keys(report) == []


def test_light_check_still_reports_a_new_value_of_a_gated_option(
    dummy: tuple[ManifestSpec, Path],
) -> None:
    newer = gated_catalog(methods=("POT", "AMP", "NEW"), variables=("H", "Q", "T", "X"))

    report = light_gated(dummy, newer)

    gaps = sorted(
        (f.args["command"], f.args["option"], f.args["value"])
        for f in report.findings
        if f.key == "x4_gap"
    )
    assert gaps == [
        ("datasets download", "params", "X"),
        ("pmaxtp fetch", "method", "NEW"),
        ("pmaxtp sync", "method", "NEW"),
    ]
    assert keys(report, "error") == ["x4_gap"] * 3
