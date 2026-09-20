"""Pure in-memory path normalization following Windows target rules.

This module never touches the filesystem. Every rule is applied to the
raw string alone, so results are identical no matter which platform hosts
the service.

Normalization pipeline for one raw entry path:

1. Unicode NFC, so canonically-equivalent inputs compare equal.
2. Root-prefix detection: drive-letter paths (``C:...``) and absolute
   paths (``/...``, ``\\...``, UNC ``\\\\server\\share``) are unsafe.
3. Both ``/`` and ``\\`` act as separators; ``.`` segments are dropped and
   ``..`` pops the previous segment. A ``..`` that would climb above the
   archive root is an out-of-bounds escape and marks the entry unsafe.
4. Windows strips trailing spaces and dots from every segment.
5. Segments whose base name (text before the first dot) is a reserved
   DOS device name (CON, PRN, AUX, NUL, COM1-9, LPT1-9) are flagged.

The canonical path joins the surviving segments with the Windows
separator ``\\`` and folds case (Windows paths are case-insensitive).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Issue codes surfaced to API callers.
ABSOLUTE_PATH = "absolute_path"
DRIVE_LETTER_PATH = "drive_letter_path"
PARENT_ESCAPE = "parent_escape"
RESERVED_DEVICE_NAME = "reserved_device_name"
EMPTY_SEGMENT = "empty_segment"

#: Issue codes that make an entry unsafe to unpack.
UNSAFE_ISSUES = frozenset({ABSOLUTE_PATH, DRIVE_LETTER_PATH, PARENT_ESCAPE})

#: Base names Windows reserves for devices. A segment whose base name
#: (text before the first dot) matches one of these, in any case, cannot
#: be created on a Windows target.
RESERVED_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

#: Canonical separator used to join normalized segments (Windows style).
CANONICAL_SEPARATOR = "\\"

_DRIVE_PREFIX_RE = re.compile(r"^[A-Za-z]:")
_SEPARATOR_RE = re.compile(r"[/\\]+")

# Characters Windows silently strips from the end of every path segment.
_TRAILING_STRIP_CHARS = " ."


@dataclass
class NormalizedPath:
    """Result of normalizing one raw archive entry path."""

    canonical_path: str | None
    safe: bool
    issues: list[str] = field(default_factory=list)


def _is_reserved_segment(segment: str) -> bool:
    """Return True if a normalized segment names a reserved DOS device."""
    # Windows matches the base name before the first dot and also ignores
    # trailing spaces there, so "nul .dat" is still NUL.
    base = segment.split(".", 1)[0].rstrip(_TRAILING_STRIP_CHARS)
    return base.upper() in RESERVED_DEVICE_NAMES


def normalize_path(raw_path: str) -> NormalizedPath:
    """Normalize one raw archive entry path under Windows target rules.

    Returns a :class:`NormalizedPath` with the canonical path (``None``
    when the path escapes the archive root or has no usable segments),
    a ``safe`` flag, and the list of issue codes encountered.
    """
    issues: list[str] = []

    # 1. Unicode NFC so canonically-equivalent inputs compare equal.
    path = unicodedata.normalize("NFC", raw_path)

    # 2. Root prefixes that make a path unsafe on a Windows target.
    #    The prefix is stripped so a best-effort canonical path can still
    #    be reported for the relative remainder.
    if _DRIVE_PREFIX_RE.match(path):
        issues.append(DRIVE_LETTER_PATH)
        path = path[2:]
    elif path.startswith(("/", "\\")):
        issues.append(ABSOLUTE_PATH)
        path = path.lstrip("/\\")

    # 3. Split on both separator kinds and resolve dot segments in memory.
    segments: list[str] = []
    reserved_seen = False
    escaped = False
    for raw_segment in _SEPARATOR_RE.split(path):
        if raw_segment in ("", "."):
            continue
        if raw_segment == "..":
            if segments:
                segments.pop()
            else:
                # ".." above the archive root: out of bounds.
                issues.append(PARENT_ESCAPE)
                escaped = True
                break
            continue
        # 4. Windows strips trailing spaces and dots from each segment.
        segment = raw_segment.rstrip(_TRAILING_STRIP_CHARS)
        if not segment:
            if EMPTY_SEGMENT not in issues:
                issues.append(EMPTY_SEGMENT)
            continue
        # 5. Reserved DOS device names in any path position.
        if not reserved_seen and _is_reserved_segment(segment):
            issues.append(RESERVED_DEVICE_NAME)
            reserved_seen = True
        segments.append(segment)

    # 6. Canonical form: Windows separator + case-insensitive folding.
    if escaped or not segments:
        canonical_path = None
    else:
        canonical_path = CANONICAL_SEPARATOR.join(
            segment.casefold() for segment in segments
        )

    safe = not any(issue in UNSAFE_ISSUES for issue in issues)
    return NormalizedPath(canonical_path=canonical_path, safe=safe, issues=issues)
