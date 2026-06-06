"""Predictor evaluation helpers are intentionally minimal after the data-driven refactor."""

from __future__ import annotations

from services.domain import OperatorPredictionInput
from services.predictor.predict import predict_operator


def score_claim(input: OperatorPredictionInput) -> float:
    prediction, _warnings = predict_operator(input)
    return prediction.confidence
