"""Load data-owned rules for annotation evidence review artifacts."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from services.annotation_import.loader import ROOT
from services.annotation_import.models import AnnotationProposalRule, ContextExtractionRules, CuratedGraphRule

ANNOTATION_RULE_DIR = ROOT / "data" / "annotation_rules"
CONTEXT_RULE_PATH = ANNOTATION_RULE_DIR / "context" / "default.json"
PROPOSAL_RULE_DIR = ANNOTATION_RULE_DIR / "proposals"
CURATED_GRAPH_RULE_DIR = ANNOTATION_RULE_DIR / "curated_graphs"


@lru_cache(maxsize=1)
def load_context_rules() -> ContextExtractionRules:
    if not CONTEXT_RULE_PATH.exists():
        return ContextExtractionRules()
    return ContextExtractionRules.model_validate_json(CONTEXT_RULE_PATH.read_text())


@lru_cache(maxsize=64)
def load_proposal_rule(paper_id: str) -> AnnotationProposalRule | None:
    path = proposal_rule_path(paper_id)
    if not path.exists():
        return None
    rule = AnnotationProposalRule.model_validate_json(path.read_text())
    if rule.paper_id != path.stem:
        raise ValueError(f"Proposal rule filename {path.name!r} does not match paper_id {rule.paper_id!r}")
    return rule


def proposal_rule_path(paper_id: str) -> Path:
    path = (PROPOSAL_RULE_DIR / f"{paper_id}.json").resolve()
    root = PROPOSAL_RULE_DIR.resolve()
    if root not in (path, *path.parents):
        raise ValueError(f"Proposal rule path for {paper_id!r} escapes {PROPOSAL_RULE_DIR}")
    return path


def list_proposal_rules() -> tuple[str, ...]:
    if not PROPOSAL_RULE_DIR.exists():
        return ()
    return tuple(sorted(path.stem for path in PROPOSAL_RULE_DIR.glob("*.json") if path.is_file()))


@lru_cache(maxsize=64)
def load_curated_graph_rule(paper_id: str) -> CuratedGraphRule | None:
    path = curated_graph_rule_path(paper_id)
    if not path.exists():
        return None
    rule = CuratedGraphRule.model_validate_json(path.read_text())
    if rule.paper_id != path.stem:
        raise ValueError(
            f"Curated graph rule filename {path.name!r} does not match paper_id {rule.paper_id!r}"
        )
    return rule


def curated_graph_rule_path(paper_id: str) -> Path:
    path = (CURATED_GRAPH_RULE_DIR / f"{paper_id}.json").resolve()
    root = CURATED_GRAPH_RULE_DIR.resolve()
    if root not in (path, *path.parents):
        raise ValueError(f"Curated graph rule path for {paper_id!r} escapes {CURATED_GRAPH_RULE_DIR}")
    return path


def list_curated_graph_rules() -> tuple[str, ...]:
    if not CURATED_GRAPH_RULE_DIR.exists():
        return ()
    return tuple(sorted(path.stem for path in CURATED_GRAPH_RULE_DIR.glob("*.json") if path.is_file()))
