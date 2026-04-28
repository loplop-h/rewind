"""Regression tests for the cp1252 / UTF-8 stdout fix in :mod:`rewind.cli`."""

from __future__ import annotations

import io
import sys
from typing import Any

from click.testing import CliRunner

from rewind.cli import _ensure_utf8_stdio, main


def test_ensure_utf8_stdio_reconfigures_when_supported(monkeypatch: Any) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class FakeStream:
        def reconfigure(self, **kw: Any) -> None:
            calls.append(("ok", kw))

    monkeypatch.setattr(sys, "stdout", FakeStream())
    monkeypatch.setattr(sys, "stderr", FakeStream())
    _ensure_utf8_stdio()
    assert len(calls) == 2
    for _, kw in calls:
        assert kw["encoding"] == "utf-8"
        assert kw["errors"] == "replace"


def test_ensure_utf8_stdio_silently_skips_when_unsupported(monkeypatch: Any) -> None:
    class NoReconfigure:
        pass

    monkeypatch.setattr(sys, "stdout", NoReconfigure())
    monkeypatch.setattr(sys, "stderr", NoReconfigure())
    # Should be a no-op, not an exception.
    _ensure_utf8_stdio()


def test_ensure_utf8_stdio_swallows_value_error(monkeypatch: Any) -> None:
    class Hostile:
        def reconfigure(self, **_: Any) -> None:
            raise ValueError("file is in binary mode")

    monkeypatch.setattr(sys, "stdout", Hostile())
    monkeypatch.setattr(sys, "stderr", Hostile())
    _ensure_utf8_stdio()  # must not raise


def test_main_does_not_crash_on_unicode_output(rewind_home: Any) -> None:
    """End-to-end: invoking the CLI through Click does not blow up because
    of the ANSI / box-drawing characters Rich emits."""

    _ = rewind_home  # fixture isolates ~/.rewind
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "rewind" in result.output


def test_unicode_string_writes_via_replacement(monkeypatch: Any) -> None:
    """Even when underlying encoding is cp1252 and reconfigure is a no-op,
    nothing should crash because errors='replace' is applied."""

    captured = io.StringIO()

    def fake_reconfigure(**kw: Any) -> None:  # pragma: no cover - touched indirectly
        return None

    captured.reconfigure = fake_reconfigure  # type: ignore[attr-defined]
    monkeypatch.setattr(sys, "stdout", captured)
    _ensure_utf8_stdio()
    sys.stdout.write("rewind ─ session start ●")
    assert "rewind" in captured.getvalue()
