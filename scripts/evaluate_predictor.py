"""Report toy graph-patch predictor behavior for configured pathway claims."""

from __future__ import annotations

import json

from services.domain import OperatorPredictionInput
from services.pathway.loader import list_pathways, load_pathway
from services.predictor.predict import predict_operator


def main() -> None:
    report: dict[str, object] = {}
    for summary in list_pathways():
        pathway = load_pathway(summary.pathway_id)
        cases: list[dict[str, object]] = []
        for case in pathway.prediction.training_cases:
            prediction, warnings = predict_operator(
                OperatorPredictionInput(pathway_id=pathway.pathway_id, claim_text=case.claim)
            )
            cases.append(
                {
                    "claim": case.claim,
                    "predicted_operator": str(prediction.predicted_operator),
                    "recommendations": [item.model_dump(mode="json") for item in prediction.recommendations],
                    "decision_source": prediction.diagnostics.decision_source,
                    "warnings": [item.model_dump(mode="json") for item in warnings],
                }
            )
        report[str(pathway.pathway_id)] = {"cases": cases}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
