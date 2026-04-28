"""Content-addressed blob storage.

Each snapshot of a file's bytes is stored under a directory tree keyed by
the sha256 of its content. Identical content across snapshots is stored
once. Blobs are immutable.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

CHUNK_SIZE = 64 * 1024


class BlobStore:
    """Filesystem-backed content-addressed blob store.

    Layout::

        <root>/blobs/<aa>/<bb>/<full-sha256>

    Where ``aa`` is the first two hex chars of the hash and ``bb`` the next two.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._blobs_dir = root / "blobs"

    @property
    def root(self) -> Path:
        return self._root

    @property
    def blobs_dir(self) -> Path:
        return self._blobs_dir

    def ensure_dirs(self) -> None:
        self._blobs_dir.mkdir(parents=True, exist_ok=True)

    def write_bytes(self, content: bytes) -> str:
        """Store ``content`` and return its sha256 hex digest."""

        digest = hashlib.sha256(content).hexdigest()
        target = self._path_for(digest)
        if target.exists():
            return digest
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_bytes(content)
        tmp.replace(target)
        return digest

    def write_path(self, source: Path) -> tuple[str, int]:
        """Hash ``source`` and store its content. Return (digest, size_bytes).

        Streams the file in chunks so very large files do not blow memory.
        """

        if not source.is_file():
            raise FileNotFoundError(source)
        hasher = hashlib.sha256()
        size = 0
        with source.open("rb") as fh:
            while True:
                chunk = fh.read(CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)
                size += len(chunk)
        digest = hasher.hexdigest()
        target = self._path_for(digest)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".tmp")
            with tmp.open("wb") as out, source.open("rb") as inp:
                while True:
                    chunk = inp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    out.write(chunk)
            tmp.replace(target)
        return digest, size

    def read_bytes(self, digest: str) -> bytes:
        """Return the bytes for ``digest`` or raise :class:`FileNotFoundError`."""

        target = self._path_for(digest)
        return target.read_bytes()

    def has(self, digest: str) -> bool:
        return self._path_for(digest).exists()

    def path_for(self, digest: str) -> Path:
        return self._path_for(digest)

    def _path_for(self, digest: str) -> Path:
        if len(digest) != 64 or not all(c in "0123456789abcdef" for c in digest):
            raise ValueError(f"not a sha256 hex digest: {digest!r}")
        return self._blobs_dir / digest[0:2] / digest[2:4] / digest


def hash_bytes(content: bytes) -> str:
    """Compute the sha256 hex digest of ``content``."""

    return hashlib.sha256(content).hexdigest()


def hash_path(path: Path) -> tuple[str, int]:
    """Compute the sha256 hex digest of the file at ``path``. Returns (digest, size)."""

    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size
