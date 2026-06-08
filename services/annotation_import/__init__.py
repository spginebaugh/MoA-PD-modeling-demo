"""Paper annotation ingestion and evidence graph generation."""

from services.annotation_import.curated_graph_builder import build_curated_paper_moa_graph
from services.annotation_import.graph_builder import build_paper_evidence_graph
from services.annotation_import.loader import ANNOTATION_DIR, list_annotation_bundles, load_annotation_bundle
from services.annotation_import.models import CuratedPaperMoaGraph, PaperEvidenceGraph
from services.annotation_import.pathway_patch import build_pathway_proposal

__all__ = [
    "ANNOTATION_DIR",
    "CuratedPaperMoaGraph",
    "PaperEvidenceGraph",
    "build_curated_paper_moa_graph",
    "build_paper_evidence_graph",
    "build_pathway_proposal",
    "list_annotation_bundles",
    "load_annotation_bundle",
]
