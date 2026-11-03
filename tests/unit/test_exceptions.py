"""Registry codes, reasons and error documents of the exceptions (DEV-11.1, ERR-1)."""

from pathlib import Path

import pytest

from retman.adapters.catalog import CatalogCall, ToolError
from retman.doctor import Check, DoctorReport, Section
from retman.exceptions import (
    ConfigError,
    PlanIncompleteError,
    RetmanError,
    UsageError,
    error_document,
)


@pytest.mark.parametrize(
    ("tool_code", "code", "reason", "exit_code"),
    [
        # A code of the registry passes through; the reason is the tool's own
        ("no_data", "no_data", None, 14),
        ("source_unavailable", "source_unavailable", None, 5),
        ("validation_error", "validation_error", None, 2),
        ("unsupported", "unsupported", None, 15),
        ("cancelled", "cancelled", None, 130),
        ("not_found", "not_found", None, 3),
        # The words only Retman's clients use refine a registry code
        ("store_write_unsupported", "store_unavailable", "store_write_unsupported", 8),
        ("not_offline", "internal_error", "not_offline", 1),
        ("not_read_only", "internal_error", "not_read_only", 1),
        # Anything else is an internal error that names the code
        ("quota_exceeded", "internal_error", "quota_exceeded", 1),
    ],
)
def test_tool_error_maps_the_code_of_the_tool_to_the_registry(
    tool_code: str, code: str, reason: str | None, exit_code: int
) -> None:
    error = ToolError("kartograf", tool_code, "detail")

    assert (error.code, error.exit_code) == (code, exit_code)
    assert error.details.get("reason") == reason
    assert error.tool_code == tool_code
    assert error.details["tool"] == "kartograf"


def test_tool_error_keeps_the_reason_the_tool_gives_for_a_registry_code() -> None:
    error = ToolError("imgwtools", "conflict", "x", details={"reason": "not_atomic"})

    assert (error.code, error.details["reason"]) == ("conflict", "not_atomic")
    assert error.details["tool_details"] == {"reason": "not_atomic"}


def test_tool_error_records_the_command_when_the_call_is_set_later() -> None:
    error = ToolError("kartograf", "no_data", "x")
    assert "tool_command" not in error.details

    error.call = CatalogCall("elevation download", {})

    assert error.details["tool_command"] == "elevation download"


def test_a_code_outside_the_registry_is_refused() -> None:
    with pytest.raises(ValueError, match="made_up"):
        RetmanError("x", code="made_up")  # type: ignore[arg-type]


def test_the_class_reason_comes_first_and_the_raise_site_may_replace_it() -> None:
    assert list(UsageError("x", details={"option": "a"}).details) == [
        "reason",
        "option",
    ]
    assert PlanIncompleteError("x", details={"reason": "no_check"}).details == {
        "reason": "no_check"
    }


def test_a_missing_or_existing_settings_file_has_its_own_code(tmp_path: Path) -> None:
    missing = ConfigError(tmp_path / "nogat.toml", ["missing_file"])
    existing = ConfigError(tmp_path / "nogat.toml", ["already_exists"])
    invalid = ConfigError(tmp_path / "nogat.toml", ["missing_key", "invalid_value"])

    assert [e.code for e in (missing, existing, invalid)] == [
        "not_found",
        "conflict",
        "validation_error",
    ]
    assert invalid.details["problems"] == ["missing_key", "invalid_value"]


def test_the_document_of_a_file_system_error_names_errno_and_path() -> None:
    document = error_document(FileNotFoundError(2, "No such file", "/x/y"))

    assert (document["code"], document["exit_code"]) == ("io_error", 9)
    assert document["details"] == {"errno": "ENOENT", "path": "/x/y"}


def test_the_document_of_a_bug_names_the_exception_and_has_no_command() -> None:
    document = error_document(RuntimeError("boom"))

    assert (document["code"], document["exit_code"]) == ("internal_error", 1)
    assert document["details"] == {"exception": "RuntimeError"}
    assert "command" not in document and "hint" in document


def test_the_document_leaves_out_an_empty_hint_and_translates_only_the_title() -> None:
    english = error_document(UsageError("bad"), "plan run")
    polish = error_document(UsageError("bad"), lang="pl")

    assert "hint" not in english and english["command"] == "plan run"
    assert english["message"] == polish["message"] == "bad"
    assert english["title"] != polish["title"]


def test_a_language_other_than_pl_or_en_is_refused() -> None:
    with pytest.raises(ValueError, match="de"):
        error_document(UsageError("x"), lang="de")  # type: ignore[arg-type]


def _check(status: str, *, blocking: bool = False) -> Check:
    code = "io_error" if blocking else None
    return Check(status, "text", blocking=blocking, code=code)  # type: ignore[arg-type]


def test_doctor_is_partial_when_a_check_blocks_and_failed_when_none_passed() -> None:
    clean = DoctorReport("1", [Section("a", "A", [_check("ok")])])
    partial = DoctorReport(
        "1", [Section("a", "A", [_check("ok"), _check("error", blocking=True)])]
    )
    failed = DoctorReport("1", [Section("a", "A", [_check("error", blocking=True)])])

    assert (clean.exit_code, partial.exit_code, failed.exit_code) == (0, 10, 11)
