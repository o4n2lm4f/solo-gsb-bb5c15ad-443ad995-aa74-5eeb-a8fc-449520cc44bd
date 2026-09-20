"""FastAPI application exposing the archive path precheck service."""

from __future__ import annotations

from fastapi import FastAPI

from . import __version__
from .analysis import find_collisions, find_hierarchy_conflicts
from .models import (
    EntryResult,
    PrecheckRequest,
    PrecheckResponse,
)
from .normalizer import normalize_path

app = FastAPI(
    title="Archive Path Precheck API",
    version=__version__,
    description=(
        "Validates archive entry paths against Windows target rules, "
        "entirely in memory: canonical paths, same-name collision groups, "
        "and file-vs-ancestor hierarchy conflicts."
    ),
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/precheck", response_model=PrecheckResponse, tags=["precheck"])
def precheck(request: PrecheckRequest) -> PrecheckResponse:
    """Normalize and cross-check a batch of archive entry paths.

    The per-entry ``results`` preserve the input order. No filesystem is
    touched at any point.
    """
    normalized = [normalize_path(entry.path) for entry in request.entries]
    canonical_paths = [item.canonical_path for item in normalized]
    entry_types = [entry.type for entry in request.entries]

    results = [
        EntryResult(
            index=index,
            path=entry.path,
            type=entry.type,
            canonical_path=item.canonical_path,
            safe=item.safe,
            issues=item.issues,
        )
        for index, (entry, item) in enumerate(zip(request.entries, normalized))
    ]

    return PrecheckResponse(
        results=results,
        collisions=find_collisions(canonical_paths),
        hierarchy_conflicts=find_hierarchy_conflicts(entry_types, canonical_paths),
    )
