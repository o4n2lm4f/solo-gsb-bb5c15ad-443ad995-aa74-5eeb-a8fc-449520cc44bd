"""Pydantic request/response schemas for the precheck API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Entry(BaseModel):
    """One archive entry to precheck."""

    path: str = Field(..., description="Raw entry path as stored in the archive.")
    type: Literal["file", "directory"] = Field(
        ..., description="Entry kind: 'file' or 'directory'."
    )


class PrecheckRequest(BaseModel):
    """Batch of archive entries to validate, processed in input order."""

    entries: list[Entry] = Field(default_factory=list)


class EntryResult(BaseModel):
    """Per-entry normalization result, mirroring the input order."""

    index: int
    path: str = Field(..., description="Original raw path, echoed back.")
    type: str
    canonical_path: str | None = Field(
        ...,
        description=(
            "Normalized Windows-target path (NFC, '\\' separators, case-folded, "
            "trailing spaces/dots stripped). Null when the path escapes the "
            "archive root or has no usable segments."
        ),
    )
    safe: bool = Field(
        ...,
        description=(
            "False when the path is absolute, has a drive-letter prefix, or "
            "escapes the archive root via '..'."
        ),
    )
    issues: list[str] = Field(
        default_factory=list, description="Machine-readable issue codes."
    )


class CollisionGroup(BaseModel):
    """Entries that normalize to the same canonical path."""

    canonical_path: str
    indices: list[int]


class HierarchyConflict(BaseModel):
    """A file entry occupying an ancestor path of other entries."""

    file_index: int
    canonical_path: str
    blocked_indices: list[int]


class PrecheckResponse(BaseModel):
    """Full precheck report for a batch of archive entries."""

    results: list[EntryResult]
    collisions: list[CollisionGroup]
    hierarchy_conflicts: list[HierarchyConflict]
