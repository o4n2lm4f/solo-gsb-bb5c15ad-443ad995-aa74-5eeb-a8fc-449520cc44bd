"""Cross-entry analysis: same-name collisions and hierarchy conflicts.

Everything here operates on the canonical paths produced by
:mod:`app.normalizer`; no filesystem access is involved.
"""

from __future__ import annotations

from typing import Iterable

from .normalizer import CANONICAL_SEPARATOR


def find_collisions(canonical_paths: Iterable[str | None]) -> list[dict]:
    """Group entries that normalize to the same canonical path.

    Returns one group per colliding canonical path, ordered by first
    occurrence in the input; indices inside each group follow input order.
    Entries without a canonical path (unsafe escapes) never collide.
    """
    groups: dict[str, list[int]] = {}
    for index, canonical_path in enumerate(canonical_paths):
        if canonical_path is None:
            continue
        groups.setdefault(canonical_path, []).append(index)
    return [
        {"canonical_path": canonical_path, "indices": indices}
        for canonical_path, indices in groups.items()
        if len(indices) > 1
    ]


def find_hierarchy_conflicts(
    entry_types: list[str],
    canonical_paths: list[str | None],
) -> list[dict]:
    """Find files that occupy an ancestor path of other entries.

    A *file* whose canonical path is a proper ancestor of another entry's
    canonical path blocks that entry: the other entry would need a
    directory where the file already sits. Reported in input order of the
    blocking file; blocked indices follow input order.
    """
    conflicts: list[dict] = []
    for index, (entry_type, canonical_path) in enumerate(
        zip(entry_types, canonical_paths)
    ):
        if entry_type != "file" or canonical_path is None:
            continue
        prefix = canonical_path + CANONICAL_SEPARATOR
        blocked = [
            other
            for other, other_path in enumerate(canonical_paths)
            if other != index
            and other_path is not None
            and other_path.startswith(prefix)
        ]
        if blocked:
            conflicts.append(
                {
                    "file_index": index,
                    "canonical_path": canonical_path,
                    "blocked_indices": blocked,
                }
            )
    return conflicts
