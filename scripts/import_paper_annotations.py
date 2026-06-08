"""Validate paper annotation bundles in data/paper_annotations."""

from __future__ import annotations

import argparse
import json

from services.annotation_import.loader import list_annotation_bundles, load_annotation_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paper_ids", nargs="*", help="Paper ids to validate. Defaults to all bundles.")
    args = parser.parse_args()

    paper_ids = tuple(args.paper_ids) or list_annotation_bundles()
    summaries: list[dict[str, object]] = []
    for paper_id in paper_ids:
        bundle = load_annotation_bundle(paper_id)
        summaries.append(
            {
                "paper_id": bundle.paper.paper_id,
                "title": bundle.paper.title,
                "evidence_anchor_count": len(bundle.evidence_anchors),
                "mechanism_chain_count": len(bundle.mechanism_chains),
                "mechanism_step_count": sum(len(chain.steps) for chain in bundle.mechanism_chains),
                "mechanism_verification_count": len(bundle.mechanism_verifications),
                "equation_count": len(bundle.equations),
                "simulation_model_count": len(bundle.simulation_models),
                "simulation_parameter_count": len(bundle.simulation_parameters),
            }
        )
    print(json.dumps({"bundles": summaries}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
