"""Load pathway definitions from data/pathways."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from services.domain import PathwayId

from .models import DisplayOption, PathwayDefinition, PathwaySummary

ROOT = Path(__file__).resolve().parents[2]
PATHWAY_DIR = ROOT / "data" / "pathways"


@lru_cache(maxsize=32)
def load_pathway(pathway_id: PathwayId | str) -> PathwayDefinition:
    pathway = PathwayId(str(pathway_id))
    path = PATHWAY_DIR / f"{pathway}.json"
    if not path.exists():
        raise ValueError(f"Unknown pathway_id {pathway!r}")
    return PathwayDefinition.model_validate_json(path.read_text())


def list_pathways() -> tuple[PathwaySummary, ...]:
    summaries: list[PathwaySummary] = []
    for path in sorted(PATHWAY_DIR.glob("*.json")):
        pathway = PathwayDefinition.model_validate_json(path.read_text())
        summaries.append(
            PathwaySummary(
                pathway_id=pathway.pathway_id,
                label=pathway.label,
                version=pathway.version,
                configurations=tuple(
                    DisplayOption(value=str(configuration.id), label=configuration.label)
                    for configuration in pathway.configurations.values()
                ),
            )
        )
    return tuple(summaries)
