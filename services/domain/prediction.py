"""Typed graph-patch prediction domain."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ._validation import duplicate_items
from .base import STRICT_MODEL_CONFIG, Probability
from .graph import MoAGraph
from .identifiers import EdgeId, NodeId, OperatorId, PathwayId, RelationId
from .vocabulary import EDGE_TARGET_RELATIONS, OPERATOR_RELATION_BY_KIND, Sign, relation_default_sign


class OperatorPredictionInput(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    pathway_id: PathwayId
    claim_text: str = ""
    graph: MoAGraph | None = None
    include_modules: tuple[str, ...] = ()
    exclude_modules: tuple[str, ...] = ()
    source_node_id: NodeId | None = None
    target_edge_id: EdgeId | None = None
    desired_relation: RelationId | None = None


class OperatorProbability(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    operator: OperatorId
    probability: Probability


class EdgeRecommendation(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    edge_id: EdgeId
    source: NodeId
    target: EdgeId
    relation: RelationId
    sign: Sign
    operator: OperatorId
    support_score: Probability
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def relation_sign_and_operator_are_compatible(self) -> EdgeRecommendation:
        if str(self.relation) not in EDGE_TARGET_RELATIONS:
            raise ValueError("Prediction recommendations must be edge-modifier graph patches")
        expected_relation = OPERATOR_RELATION_BY_KIND.get(str(self.operator))
        if expected_relation is not None and str(self.relation) != expected_relation:
            raise ValueError(
                f"Recommendation operator {self.operator!r} requires relation {expected_relation!r}, got {self.relation!r}"
            )
        expected_sign = relation_default_sign(str(self.relation))
        if expected_sign != Sign.UNKNOWN and self.sign != expected_sign:
            raise ValueError(f"Recommendation relation {self.relation!r} requires sign {expected_sign!r}")
        return self


class EdgePatchCandidate(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    edge_id: EdgeId
    source: NodeId
    target: EdgeId
    relation: RelationId
    sign: Sign
    operator: OperatorId
    score: Probability
    rationale: str = Field(min_length=1)
    feature_summary: tuple[str, ...] = ()

    @model_validator(mode="after")
    def relation_sign_and_operator_are_compatible(self) -> EdgePatchCandidate:
        if str(self.relation) not in EDGE_TARGET_RELATIONS:
            raise ValueError("Edge patch candidates must target an existing causal edge")
        expected_relation = OPERATOR_RELATION_BY_KIND.get(str(self.operator))
        if expected_relation is not None and str(self.relation) != expected_relation:
            raise ValueError(
                f"Candidate operator {self.operator!r} requires relation {expected_relation!r}, got {self.relation!r}"
            )
        expected_sign = relation_default_sign(str(self.relation))
        if expected_sign != Sign.UNKNOWN and self.sign != expected_sign:
            raise ValueError(f"Candidate relation {self.relation!r} requires sign {expected_sign!r}")
        return self

    def to_recommendation(self) -> EdgeRecommendation:
        return EdgeRecommendation(
            edge_id=self.edge_id,
            source=self.source,
            target=self.target,
            relation=self.relation,
            sign=self.sign,
            operator=self.operator,
            support_score=self.score,
            rationale=self.rationale,
        )


class PredictionDiagnostics(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    decision_source: Literal["model", "guardrail", "abstain"]
    guardrail_applied: bool = False
    model_confidence: Probability
    model_score: Probability | None = None
    top_score: Probability
    score_margin: Probability
    low_support: bool = False
    matched_positive_features: tuple[str, ...] = ()
    claim_keywords_used: tuple[str, ...] = ()
    negated_claim_keywords_used: tuple[str, ...] = ()
    included_modules: tuple[str, ...] = ()


class OperatorPrediction(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    predicted_operator: OperatorId
    confidence: Probability
    probabilities: tuple[OperatorProbability, ...]
    recommendations: tuple[EdgeRecommendation, ...]
    candidates: tuple[EdgePatchCandidate, ...]
    diagnostics: PredictionDiagnostics
    model_recommendations: tuple[EdgeRecommendation, ...]
    guardrail_recommendations: tuple[EdgeRecommendation, ...] = ()

    @model_validator(mode="after")
    def probabilities_are_normalized(self) -> OperatorPrediction:
        operators = tuple(item.operator for item in self.probabilities)
        duplicate_operators = tuple(operator for operator in duplicate_items(operators))
        if duplicate_operators:
            raise ValueError(f"Duplicate operator probabilities: {list(duplicate_operators)}")

        probabilities_by_operator = {item.operator: item.probability for item in self.probabilities}
        if self.predicted_operator not in probabilities_by_operator:
            raise ValueError("predicted_operator must appear in probabilities")
        total = sum(probabilities_by_operator.values())
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"Operator probabilities must sum to 1.0, got {total}")
        confidence = probabilities_by_operator[self.predicted_operator]
        if abs(confidence - self.confidence) > 1e-12:
            raise ValueError("confidence must equal the predicted operator probability")
        if not self.recommendations:
            raise ValueError("OperatorPrediction requires at least one recommendation")
        recommendation_ids = tuple(recommendation.edge_id for recommendation in self.recommendations)
        duplicate_recommendations = tuple(edge_id for edge_id in duplicate_items(recommendation_ids))
        if duplicate_recommendations:
            raise ValueError(f"Duplicate recommendation edge ids: {list(duplicate_recommendations)}")
        if any(recommendation.operator != self.predicted_operator for recommendation in self.recommendations):
            raise ValueError("all recommendations must match predicted_operator")
        if not self.model_recommendations:
            raise ValueError("OperatorPrediction requires at least one model recommendation")
        for recommendation in (*self.model_recommendations, *self.guardrail_recommendations):
            if recommendation.operator not in probabilities_by_operator:
                raise ValueError("recommendation operator must appear in probabilities")
        return self
