"""Contract tests of the result envelope ``retman-result/1`` (AGI-4.2, AGI-3.2)."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from nogat_schemas import validator

from retman import __version__
from retman._errors import OUTCOMES
from retman.catalog import CommandResult, Item, Notice, Output, status_of
from retman.exceptions import RetmanError


def _envelope(output: Output, command: str = "doctor check") -> dict[str, Any]:
    return CommandResult(command, "retman-doctor/1", output).to_dict()


def _violations(document: object) -> list[str]:
    return [e.message for e in validator("result-1").iter_errors(document)]


OK = Item("a", "ok")
FAILED = Item("b", "failed", "source_unavailable", "backend_connection", "no answer")


class TestEnvelope:
    """Every envelope obeys the Nogat schema ``result-1``."""

    def test_a_plain_result_is_ok_and_carries_the_fixed_fields(self) -> None:
        envelope = _envelope(Output({"sections": []}))

        assert _violations(envelope) == []
        assert envelope["schema"] == "retman-result/1"
        assert (envelope["tool"], envelope["version"]) == ("retman", __version__)
        assert (envelope["command"], envelope["check"], envelope["status"]) == (
            "doctor check",
            False,
            "ok",
        )
        assert envelope["result"] == {"schema": "retman-doctor/1", "sections": []}
        assert (envelope["items"], envelope["notices"]) == ([], [])
        assert "page" not in envelope

    def test_units_that_all_passed_are_ok(self) -> None:
        envelope = _envelope(Output({}, items=[OK, Item("c", "ok")]))

        assert (_violations(envelope), envelope["status"]) == ([], "ok")

    def test_some_failed_units_make_it_partial_and_it_names_both_kinds(self) -> None:
        envelope = _envelope(Output({}, items=[OK, FAILED]))

        assert _violations(envelope) == []
        assert envelope["status"] == "partial"
        assert [item["status"] for item in envelope["items"]] == ["ok", "failed"]
        assert envelope["items"][1] == {
            "id": "b",
            "status": "failed",
            "code": "source_unavailable",
            "reason": "backend_connection",
            "message": "no answer",
        }

    def test_only_failed_units_make_it_failed(self) -> None:
        envelope = _envelope(Output({}, items=[FAILED, FAILED]))

        assert (_violations(envelope), envelope["status"]) == ([], "failed")

    def test_a_cancelled_call_has_no_result(self) -> None:
        envelope = _envelope(Output(None, cancelled=True), "plan run")

        assert _violations(envelope) == []
        assert (envelope["status"], envelope["result"]) == ("cancelled", None)

    def test_a_check_run_says_so(self) -> None:
        envelope = _envelope(Output({"targets": []}, check=True), "config init")

        assert _violations(envelope) == []
        assert envelope["check"] is True

    def test_notices_carry_a_level_a_code_and_a_message(self) -> None:
        notice = Notice("warning", "operation_warning", "Dane wymagają źródła.")
        envelope = _envelope(Output({}, notices=[notice]))

        assert _violations(envelope) == []
        assert envelope["notices"] == [
            {
                "level": "warning",
                "code": "operation_warning",
                "message": "Dane wymagają źródła.",
            }
        ]

    def test_a_truncated_page_names_the_cursor_of_the_next_one(self) -> None:
        page = {"total": 40, "next_cursor": "Mg==", "truncated": True}
        envelope = _envelope(Output({}, page=page), "results list")

        assert _violations(envelope) == []
        assert envelope["page"] == page

    def test_a_schema_override_names_the_document_of_a_plan(self) -> None:
        output = Output({"targets": []}, check=True, schema="retman-targets/1")

        assert _envelope(output, "config init")["result"]["schema"] == (
            "retman-targets/1"
        )

    def test_the_envelope_is_one_line_of_json_that_keeps_polish_letters(self) -> None:
        result = CommandResult(
            "doctor check", "retman-doctor/1", Output({"text": "ąęł"})
        )

        text = result.to_json()

        assert "\n" not in text and "ąęł" in text
        assert json.loads(text) == result.to_dict()

    def test_the_view_is_never_part_of_the_document(self) -> None:
        output = Output({"a": 1}, view=lambda texts: "terminal text")

        assert "view" not in json.dumps(_envelope(output))

    def test_a_result_that_is_no_document_is_refused(self) -> None:
        with pytest.raises(TypeError, match="document"):
            _envelope(Output([1, 2]))  # type: ignore[arg-type]


class TestUnits:
    """The rules for ``items`` and for the status they make (AGI-4.2)."""

    def test_the_status_follows_from_the_units(self) -> None:
        assert status_of([]) == "ok"
        assert status_of([OK]) == "ok"
        assert status_of([OK, FAILED]) == "partial"
        assert status_of([FAILED]) == "failed"

    def test_a_failed_unit_needs_a_code_of_the_registry(self) -> None:
        with pytest.raises(ValueError, match="registry code"):
            Item("x", "failed")
        with pytest.raises(ValueError, match="registry code"):
            Item("x", "failed", "not_a_code")

    def test_a_unit_that_passed_has_no_code(self) -> None:
        with pytest.raises(ValueError, match="no error code"):
            Item("x", "ok", "io_error")

    def test_a_notice_has_a_known_level_a_snake_case_code_and_a_message(self) -> None:
        with pytest.raises(ValueError, match="level"):
            Notice("error", "x", "m")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="snake_case"):
            Notice("info", "Not Snake", "m")
        with pytest.raises(ValueError, match="empty"):
            Notice("info", "x", "  ")

    def test_the_exit_code_of_a_status_is_the_one_of_the_registry(self) -> None:
        for status, items, cancelled in (
            ("ok", [], False),
            ("partial", [OK, FAILED], False),
            ("failed", [FAILED], False),
            ("cancelled", [], True),
        ):
            result = CommandResult(
                "doctor check",
                "retman-doctor/1",
                Output({}, items=items, cancelled=cancelled),
            )
            assert (result.status, result.exit_code) == (status, OUTCOMES[status])


class TestFiles:
    """A command that wrote files lists them with size and checksum (DEV-19.19)."""

    def test_each_file_has_a_path_a_size_a_digest_and_a_status(
        self, tmp_path: Path
    ) -> None:
        written = tmp_path / "a.txt"
        written.write_bytes(b"abc")
        replaced = tmp_path / "b.txt"
        replaced.write_bytes(b"")

        envelope = _envelope(Output({}, files=[written, replaced], replaced=[replaced]))

        assert _violations(envelope) == []
        assert envelope["result"]["files"] == [
            {
                "path": str(written),
                "size_bytes": 3,
                "sha256": hashlib.sha256(b"abc").hexdigest(),
                "status": "written",
            },
            {
                "path": str(replaced),
                "size_bytes": 0,
                "sha256": hashlib.sha256(b"").hexdigest(),
                "status": "replaced",
            },
        ]

    def test_a_file_that_does_not_exist_is_an_internal_error(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(RetmanError) as caught:
            _envelope(Output({}, files=[tmp_path / "gone.txt"]))

        assert caught.value.code == "internal_error"
        assert caught.value.details["reason"] == "missing_output_file"

    def test_a_file_named_twice_is_listed_once(self, tmp_path: Path) -> None:
        written = tmp_path / "a.txt"
        written.write_bytes(b"x")

        envelope = _envelope(Output({}, files=[written, written]))

        assert len(envelope["result"]["files"]) == 1
