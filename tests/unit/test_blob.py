"""Tests for the content-addressed blob store."""

from __future__ import annotations

from pathlib import Path

import pytest

from rewind.store.blob import BlobStore, hash_bytes, hash_path


@pytest.fixture()
def store(tmp_path: Path) -> BlobStore:
    s = BlobStore(tmp_path)
    s.ensure_dirs()
    return s


def test_write_bytes_returns_sha256(store: BlobStore) -> None:
    digest = store.write_bytes(b"hello world")
    assert digest == hash_bytes(b"hello world")
    assert store.has(digest)


def test_write_bytes_is_idempotent(store: BlobStore) -> None:
    d1 = store.write_bytes(b"abc")
    d2 = store.write_bytes(b"abc")
    assert d1 == d2
    assert store.read_bytes(d1) == b"abc"


def test_write_path_streams_large_content(store: BlobStore, tmp_path: Path) -> None:
    payload = (b"\xff" * 4096) + b"\n" + (b"\x00" * 8192)
    src = tmp_path / "big.bin"
    src.write_bytes(payload)
    digest, size = store.write_path(src)
    assert size == len(payload)
    assert store.read_bytes(digest) == payload


def test_write_path_raises_when_missing(store: BlobStore, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        store.write_path(tmp_path / "missing.bin")


def test_path_for_validates_digest(store: BlobStore) -> None:
    with pytest.raises(ValueError):
        store.path_for("zzz")
    with pytest.raises(ValueError):
        store.path_for("g" * 64)
    valid = store.write_bytes(b"")
    assert store.path_for(valid).parent.is_dir()


def test_hash_path_matches_hash_bytes(tmp_path: Path) -> None:
    payload = b"two-paths-one-hash"
    src = tmp_path / "x.bin"
    src.write_bytes(payload)
    by_path, size = hash_path(src)
    assert by_path == hash_bytes(payload)
    assert size == len(payload)


def test_read_bytes_missing_raises(store: BlobStore) -> None:
    with pytest.raises(FileNotFoundError):
        store.read_bytes("0" * 64)
