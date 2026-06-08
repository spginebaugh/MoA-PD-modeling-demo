"""Build review-only pathway proposal artifacts from paper evidence graphs."""

from __future__ import annotations

import argparse
from pathlib import Path

from services.annotation_import.loader import ROOT
from services.annotation_import.models import PaperEvidenceGraph
from services.annotation_import.pathway_patch import build_pathway_proposal
from services.annotation_import.validation import assert_valid_pathway_proposal

DEFAULT_INPUT_DIR = ROOT / "data" / "annotation_graphs"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "pathway_proposals"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paper_ids", nargs="*", help="Paper ids to propose. Defaults to all evidence graphs.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    graph_paths = _graph_paths(args.input_dir, tuple(args.paper_ids))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for graph_path in graph_paths:
        graph = PaperEvidenceGraph.model_validate_json(graph_path.read_text())
        proposal = build_pathway_proposal(graph)
        assert_valid_pathway_proposal(proposal)
        output_path = args.output_dir / f"{graph.paper_id}.{proposal.proposal_kind}.proposal.json"
        output_path.write_text(proposal.model_dump_json(indent=2) + "\n")
        print(output_path)


def _graph_paths(input_dir: Path, paper_ids: tuple[str, ...]) -> tuple[Path, ...]:
    if paper_ids:
        return tuple(input_dir / f"{paper_id}.evidence_graph.json" for paper_id in paper_ids)
    return tuple(sorted(input_dir.glob("*.evidence_graph.json")))


if __name__ == "__main__":
    main()
