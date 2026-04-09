"""Build and version metadata helpers for panel surfaces."""

from __future__ import annotations

import os
from pathlib import Path


DEFAULT_PANEL_RELEASE_VERSION = "1.1.0"
_SAFE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


def _sanitize_token(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    cleaned = "".join(ch for ch in raw if ch in _SAFE_CHARS)
    return cleaned or None


def _resolve_git_dir(repo_root: Path) -> Path | None:
    dot_git = repo_root / ".git"
    if dot_git.is_dir():
        return dot_git
    if dot_git.is_file():
        marker = dot_git.read_text(encoding="utf-8").strip()
        prefix = "gitdir:"
        if marker.startswith(prefix):
            target = marker[len(prefix) :].strip()
            return (repo_root / target).resolve()
    return None


def _read_git_ref(repo_root: Path) -> str | None:
    git_dir = _resolve_git_dir(repo_root)
    if git_dir is None:
        return None
    head_path = git_dir / "HEAD"
    if not head_path.exists():
        return None
    head_value = head_path.read_text(encoding="utf-8").strip()
    if not head_value:
        return None
    if head_value.startswith("ref:"):
        ref_name = head_value.split(":", 1)[1].strip()
        ref_path = git_dir / ref_name
        if ref_path.exists():
            return _sanitize_token(ref_path.read_text(encoding="utf-8").strip()[:12])
        packed_refs = git_dir / "packed-refs"
        if packed_refs.exists():
            for line in packed_refs.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("^"):
                    continue
                sha, _, name = line.partition(" ")
                if name.strip() == ref_name:
                    return _sanitize_token(sha[:12])
        return None
    return _sanitize_token(head_value[:12])


def get_build_info() -> dict[str, str | None]:
    repo_root = Path(__file__).resolve().parent.parent
    release_version = _sanitize_token(os.getenv("MC_NETPROBE_RELEASE_VERSION")) or DEFAULT_PANEL_RELEASE_VERSION
    build_ref = (
        _sanitize_token(os.getenv("MC_NETPROBE_BUILD_REF"))
        or _sanitize_token(os.getenv("MC_NETPROBE_GIT_SHA"))
        or _sanitize_token(os.getenv("SOURCE_COMMIT"))
        or _read_git_ref(repo_root)
    )
    display_label = f"v{release_version}"
    if build_ref:
        display_label = f"{display_label} · {build_ref}"
    header_label = f"v{release_version}"
    if build_ref:
        header_label = f"{header_label}+{build_ref}"
    return {
        "release_version": release_version,
        "build_ref": build_ref,
        "display_label": display_label,
        "header_label": header_label,
    }


def get_panel_build_info() -> dict[str, str | None]:
    return get_build_info()
