"""Project paths."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def digests_dir() -> Path:
    d = project_root() / "digests"
    d.mkdir(parents=True, exist_ok=True)
    return d


def x_raw_dir() -> Path:
    d = project_root() / "x_raw"
    d.mkdir(parents=True, exist_ok=True)
    return d
