"""Build paper evidence graph review artifacts from annotation bundles."""

from __future__ import annotations

import argparse
from pathlib import Path

from services.annotation_import.graph_builder import build_paper_evidence_graph
from services.annotation_import.loader import ROOT, list_annotation_bundles, load_annotation_bundle
from services.annotation_import.validation import assert_valid_evidence_graph

DEFAULT_OUTPUT_DIR = ROOT / "data" / "annotation_graphs"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paper_ids", nargs="*", help="Paper ids to build. Defaults to all bundles.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    paper_ids = tuple(args.paper_ids) or list_annotation_bundles()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for paper_id in paper_ids:
        bundle = load_annotation_bundle(paper_id)
        graph = build_paper_evidence_graph(bundle)
        assert_valid_evidence_graph(graph)
        output_path = args.output_dir / f"{paper_id}.evidence_graph.json"
        output_path.write_text(graph.model_dump_json(indent=2) + "\n")
        print(output_path)


if __name__ == "__main__":
    main()
