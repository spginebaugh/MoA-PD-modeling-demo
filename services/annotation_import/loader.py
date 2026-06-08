"""Load annotation bundles from data-owned storage."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from services.annotation_import.models import AnnotationBundle

ROOT = Path(__file__).resolve().parents[2]
ANNOTATION_DIR = ROOT / "data" / "paper_annotations"
_PAPER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
_REQUIRED_TOP_LEVEL_FIELDS = (
    "paper",
    "evidence_anchors",
    "parameter_candidates",
    "observations",
    "mechanism_chains",
    "mechanism_verifications",
    "equations",
    "simulation_models",
    "simulation_parameters",
    "simulation_readiness_plans",
    "kg_projection",
    "summary",
)


def _validate_paper_id(paper_id: str) -> str:
    if not paper_id or not _PAPER_ID_PATTERN.fullmatch(paper_id):
        raise ValueError(f"Invalid paper_id {paper_id!r}")
    return paper_id


def annotation_bundle_path(paper_id: str) -> Path:
    safe_paper_id = _validate_paper_id(paper_id)
    path = (ANNOTATION_DIR / f"{safe_paper_id}.json").resolve()
    root = ANNOTATION_DIR.resolve()
    if root not in (path, *path.parents):
        raise ValueError(f"Annotation path for {paper_id!r} escapes {ANNOTATION_DIR}")
    return path


@lru_cache(maxsize=32)
def load_annotation_bundle(paper_id: str) -> AnnotationBundle:
    path = annotation_bundle_path(paper_id)
    if not path.exists():
        raise ValueError(f"Unknown annotation paper_id {paper_id!r}")
    payload: object = json.loads(path.read_text())
    validate_required_top_level_fields(payload, path)
    bundle = AnnotationBundle.model_validate(payload)
    if bundle.paper.paper_id != path.stem:
        raise ValueError(
            f"Annotation filename {path.name!r} does not match paper_id {bundle.paper.paper_id!r}"
        )
    return bundle


def list_annotation_bundles() -> tuple[str, ...]:
    if not ANNOTATION_DIR.exists():
        return ()
    return tuple(sorted(path.stem for path in ANNOTATION_DIR.glob("*.json") if path.is_file()))


def validate_required_top_level_fields(payload: object, path: Path) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"Annotation bundle {path.name!r} must be a JSON object")
    missing = tuple(field for field in _REQUIRED_TOP_LEVEL_FIELDS if field not in payload)
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Annotation bundle {path.name!r} is missing required fields: {joined}")
