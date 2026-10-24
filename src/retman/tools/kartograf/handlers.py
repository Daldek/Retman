"""Operations whose run needs more than the generic catalog runner.

``download_sheet_hierarchy`` is the only one: NMT and NMPT sheets are plain
``elevation download`` calls, but an orthophoto comes in three colour variants
(RGB, CIR, B/W) that Kartograf's ``imagery download`` cannot choose between (it is
RGB only). The colour exists only on the provider class, so the orthophoto is
downloaded through ``GugikOrtoProvider`` and ``DownloadManager`` into the same
store, with the same environment (store, cache, workers, update mode) as every
other call.
"""

import hashlib
import json
from contextlib import closing
from pathlib import Path
from typing import Any

import kartograf

from retman.adapters.catalog import (
    ToolContext,
    ToolError,
    ToolNotice,
    notice_warnings,
    run_calls,
)
from retman.exceptions import RetmanError
from retman.registry.manifest import (
    HandlerOutput,
    HandlerWarning,
    ToolAudit,
    ToolAuditCall,
)
from retman.tools.kartograf.calls import download_sheet_hierarchy as build_calls
from retman.tools.kartograf.client import (
    TOOL,
    metadata_cache,
    translated,
    update_mode,
)
from retman.tools.kartograf.describe import data_dates

# Messages of failed sheets shown in an error (the audit document has them all)
_SHOWN_ERRORS = 3
# Schema of the summary Retman saves for an orthophoto download (the provider route
# has no ``kartograf-download/1`` document)
_SCHEMA = "retman-orthophoto-download/1"
_DOCUMENT = "tool_1_imagery_download.json"


def download_sheet_hierarchy(
    params: dict[str, Any], inputs: dict[str, Path], output_dir: Path, ctx: ToolContext
) -> HandlerOutput:
    """NMT and NMPT through the command layer, the orthophoto in its colour."""
    if params["product"] != "orthophoto":
        if ctx.operation is None:
            raise RetmanError(
                "download_sheet_hierarchy needs its operation in the context"
            )
        return run_calls(ctx.operation, params, inputs, output_dir, ctx)
    return _download_orthophoto(params, output_dir, ctx)


def _download_orthophoto(
    params: dict[str, Any], output_dir: Path, ctx: ToolContext
) -> HandlerOutput:
    """The orthophoto sheets of a sheet code in the colour the user chose.

    The call the preview validated gives the sheet and the target scale (PL-1992
    codes take none: a coarser code expands into its 1:10000 sheets by itself);
    the colour is the one thing Kartograf's command cannot say.
    """
    area = params["area"]
    (call,) = build_calls(params, ctx)
    if area["type"] != "sheet":
        raise ToolError(TOOL, "orthophoto_needs_sheet", area["type"], call=call)
    color = ctx.tool_value("color", params["color"])
    code = area["code"]
    target = call.options.get("scale")
    update = update_mode(ctx.settings)
    with translated(call), closing(metadata_cache(ctx.settings)) as cache:
        provider = kartograf.GugikOrtoProvider(cache=cache, color=color)
        manager = kartograf.DownloadManager(
            output_dir=ctx.store_dir,
            provider=provider,
            workers=ctx.settings["workers"],
        )
        result = (
            manager.download_hierarchy(code, str(target), update=update)
            if target is not None
            else manager.download_sheet(code, update=update)
        )
    delivered = [item for sheet in sorted(result.files) for item in result.files[sheet]]
    paths = [item.path for item in delivered] or list(result.succeeded)
    if not paths:
        # Every sheet failed: one with no data of this variant is a state of the
        # data, anything else a failure worth repeating
        messages = [
            result.errors[sheet] for sheet in result.failed if sheet in result.errors
        ]
        code_ = (
            "no_coverage" if result.no_coverage == result.failed else "download_failed"
        )
        raise ToolError(
            TOOL, code_, "; ".join(messages[:_SHOWN_ERRORS]) or code, call=call
        )
    hard = result.hard_failures
    notices = [ToolNotice(n.level, n.code, n.text) for n in result.notices]
    warnings: list[HandlerWarning] = []
    if result.no_coverage:
        warnings.append(
            {
                "key": "no_coverage_sheets",
                "args": {
                    "count": str(len(result.no_coverage)),
                    "total": str(result.total),
                },
            }
        )
    if hard:
        warnings.append(
            {
                "key": "failed_sheets",
                "args": {
                    "count": str(len(hard)),
                    "total": str(result.total),
                    "units": ", ".join(hard),
                },
            }
        )
    if _incomplete(paths):
        warnings.append({"key": "incomplete_campaign", "args": {}})
    operation = ctx.operation
    if operation is not None:
        warnings.extend(notice_warnings(operation, ctx.tool, notices))
    command_line = (
        f"DownloadManager(output_dir={str(ctx.store_dir)!r}, "
        f"provider=GugikOrtoProvider(color={color!r}), "
        f"workers={ctx.settings['workers']}), "
        + (
            f"download_hierarchy({code!r}, {str(target)!r}, update={update!r})"
            if target is not None
            else f"download_sheet({code!r}, update={update!r})"
        )
    )
    document = {
        "schema": _SCHEMA,
        "color": color,
        "sheet": code,
        "scale": target,
        "total": result.total,
        "files": [
            {
                "unit": sheet,
                "path": str(item.path),
                "version_path": str(item.version_path),
                "label": item.label,
                "status": item.status,
                "sha256": item.sha256,
            }
            for sheet in sorted(result.files)
            for item in result.files[sheet]
        ],
        "no_coverage": sorted(result.no_coverage),
        "failed": {sheet: result.errors.get(sheet, "") for sheet in hard},
        "notices": [
            {"level": n.level, "code": n.code, "text": n.text} for n in notices
        ],
    }
    data = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (output_dir / _DOCUMENT).write_bytes(data)
    audit_call: ToolAuditCall = {
        "command": call.command,
        "options": {**call.options, "color": color},
        "command_line": command_line,
        "schema": _SCHEMA,
        "status": "partial" if result.failed else "ok",
        "files": [
            {
                "path": str(item.path),
                "sha256": item.sha256,
                "version": item.label,
                "status": item.status,
            }
            for item in delivered
        ],
        "document_file": _DOCUMENT,
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    audit: ToolAudit = {
        "tool": ctx.tool,
        "version": operation.version
        if operation is not None
        else kartograf.__version__,
        "calls": [audit_call],
    }
    return {
        "values": {
            "color": color,
            "file_count": len(paths),
            "sheet_count": len(paths),
            "expected_sheets": result.total,
            "data_dates": data_dates(item.label for item in delivered),
            "bytes": sum(path.stat().st_size for path in paths),
        },
        "files": {"orthophoto": paths},
        "warnings": warnings,
        "tool": audit,
    }


def _incomplete(paths: list[Path]) -> bool:
    """Whether the newest flight GUGiK declares for some sheet is not a full one.

    The command layer reports this as a notice; the provider route does not, but
    the sidecar of every file says it (``full_sheet``).
    """
    for path in paths:
        try:
            if kartograf.read_sidecar(path).full_sheet is False:
                return True
        except kartograf.InvalidSidecarError:
            continue
    return False
