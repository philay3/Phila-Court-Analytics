"""Neutral filesystem helpers shared across the pipeline.

Home to path guards that both the evaluation harness and the production
extraction stage rely on. Kept dependency-free (stdlib only, no PDF
libraries) so any module — production or eval — can import it without
pulling in extractor dependencies. No import-time side effects.
"""

from __future__ import annotations

from pathlib import Path


def inside_git_worktree(path: Path) -> bool:
    """True if ``path`` or any ancestor contains a ``.git`` entry.

    ``.git`` may be a plain file rather than a directory (linked worktrees,
    submodules), so this checks for any filesystem entry, not just a dir.
    Callers use this to refuse writing artifacts (extracted text, reports)
    anywhere inside a repository, where they could be committed by accident.
    """
    resolved = path.resolve()
    return any(
        (candidate / ".git").exists() for candidate in (resolved, *resolved.parents)
    )
