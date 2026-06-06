"""Presentation helpers for pathway-owned UI metadata."""

from __future__ import annotations

from services.pathway.loader import load_pathway
from services.pathway.models import PresentationDefinition


def presentation_contract(pathway_id: str) -> PresentationDefinition:
    return load_pathway(pathway_id).presentation
