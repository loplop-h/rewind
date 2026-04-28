"""Unit tests for :mod:`rewind.config`."""

from __future__ import annotations

from pathlib import Path

import pytest

from rewind.config import (
    DEFAULT_MAX_BLOB_BYTES,
    DEFAULT_RETENTION_SESSIONS,
    Config,
)


def test_from_env_uses_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("REWIND_HOME", str(tmp_path / "custom"))
    config = Config.from_env()
    assert config.home == (tmp_path / "custom").resolve()


def test_from_env_default_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("REWIND_HOME", raising=False)
    monkeypatch.setattr("rewind.config.Path.home", lambda: tmp_path)
    config = Config.from_env()
    assert config.home == (tmp_path / ".rewind").resolve()


def test_session_dir_rejects_bad_ids(rewind_home: Path) -> None:
    config = Config.from_env()
    with pytest.raises(ValueError):
        config.session_dir("bad/id")
    with pytest.raises(ValueError):
        config.session_dir("")


def test_load_returns_defaults_when_no_config(rewind_home: Path) -> None:
    config = Config.load()
    assert config.retention_sessions == DEFAULT_RETENTION_SESSIONS
    assert config.max_blob_bytes == DEFAULT_MAX_BLOB_BYTES
    assert not config.capture_disabled


def test_load_applies_known_overrides(rewind_home: Path) -> None:
    cfg_path = rewind_home / "config.toml"
    cfg_path.write_text(
        "retention_sessions = 7\nmax_blob_bytes = 1024\ncapture_disabled = true\n",
        encoding="utf-8",
    )
    config = Config.load()
    assert config.retention_sessions == 7
    assert config.max_blob_bytes == 1024
    assert config.capture_disabled is True


def test_load_preserves_unknown_keys_in_extra(rewind_home: Path) -> None:
    cfg_path = rewind_home / "config.toml"
    cfg_path.write_text('future_feature = "on"\n', encoding="utf-8")
    config = Config.load()
    assert config.extra.get("future_feature") == "on"


def test_load_ignores_malformed_toml(rewind_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg_path = rewind_home / "config.toml"
    cfg_path.write_text("not valid toml = =\n", encoding="utf-8")
    config = Config.load()
    err = capsys.readouterr().err
    assert "ignoring malformed config" in err
    assert config.retention_sessions == DEFAULT_RETENTION_SESSIONS


def test_ensure_dirs_creates_home_and_sessions(rewind_home: Path) -> None:
    config = Config.from_env()
    config.ensure_dirs()
    assert config.home.is_dir()
    assert config.sessions_dir.is_dir()


def test_paths_are_absolute(rewind_home: Path) -> None:
    config = Config.from_env()
    assert config.home.is_absolute()
    assert config.sessions_dir.is_absolute()
    assert config.config_file.is_absolute()
    assert config.current_session_file.is_absolute()
