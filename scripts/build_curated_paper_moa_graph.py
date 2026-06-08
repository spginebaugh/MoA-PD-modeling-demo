"""Build curated paper MOA graph review artifacts from annotation evidence graphs."""

from __future__ import annotations

import argparse
from pathlib import Path

from services.annotation_import.curated_graph_builder import build_curated_paper_moa_graph
from services.annotation_import.graph_builder import build_paper_evidence_graph
from services.annotation_import.loader import ROOT, list_annotation_bundles, load_annotation_bundle
from services.annotation_import.rules import list_curated_graph_rules
from services.annotation_import.validation import (
    assert_valid_curated_paper_moa_graph,
    assert_valid_evidence_graph,
)

DEFAULT_OUTPUT_DIR = ROOT / "data" / "curated_annotation_graphs"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paper_ids", nargs="*", help="Paper ids to build. Defaults to curated graph rules.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    paper_ids = tuple(args.paper_ids) or list_curated_graph_rules() or list_annotation_bundles()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for paper_id in paper_ids:
        evidence_graph = build_paper_evidence_graph(load_annotation_bundle(paper_id))
        assert_valid_evidence_graph(evidence_graph)
        curated_graph = build_curated_paper_moa_graph(evidence_graph)
        assert_valid_curated_paper_moa_graph(curated_graph)
        output_path = args.output_dir / f"{paper_id}.curated_moa_graph.json"
        output_path.write_text(curated_graph.model_dump_json(indent=2) + "\n")
        print(output_path)


if __name__ == "__main__":
    main()
