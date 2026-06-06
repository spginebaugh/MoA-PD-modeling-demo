"""Data-defined graph-patch operator prediction service."""

from __future__ import annotations

from collections.abc import Sequence

from services.domain import (
    EdgeId,
    EdgePatchCandidate,
    ModelWarning,
    ModuleId,
    OperatorId,
    OperatorPrediction,
    OperatorPredictionInput,
    OperatorProbability,
    PredictionDiagnostics,
    RelationId,
    WarningCategory,
    WarningSeverity,
)
from services.pathway.composer import compose_graph
from services.pathway.loader import load_pathway
from services.pathway.models import GraphComposeRequest, PredictionGuardrail

from .candidates import CandidatePatch, generate_edge_patch_candidates
from .features import (
    active_claim_text_for_keywords,
    claim_keywords_used,
    matches_any_keyword,
    matches_keywords,
    negated_claim_keywords_used,
)
from .train import ScoredPatch

LOW_SUPPORT_SCORE_THRESHOLD = 0.35
LOW_SUPPORT_MARGIN_THRESHOLD = 0.03


def _warning(
    message: str,
    *,
    category: WarningCategory = WarningCategory.OTHER,
    severity: WarningSeverity = WarningSeverity.WARNING,
) -> ModelWarning:
    return ModelWarning(category=category, severity=severity, message=message)


def _matched_guardrails(request: OperatorPredictionInput) -> tuple[PredictionGuardrail, ...]:
    pathway = load_pathway(request.pathway_id)
    matched: list[PredictionGuardrail] = []
    for guardrail in pathway.prediction.guardrails:
        all_ok = not guardrail.when_all_keywords or matches_keywords(request.claim_text, guardrail.when_all_keywords)
        any_ok = not guardrail.when_any_keywords or matches_any_keyword(request.claim_text, guardrail.when_any_keywords)
        if all_ok and any_ok:
            matched.append(guardrail)
    return tuple(matched)


def _prediction_graph(request: OperatorPredictionInput, guardrails: tuple[PredictionGuardrail, ...]):
    if request.graph is not None:
        return request.graph
    include_modules = {str(module) for module in request.include_modules}
    for guardrail in guardrails:
        include_modules.update(str(module) for module in guardrail.include_modules)
    return compose_graph(
        GraphComposeRequest(
            pathway_id=request.pathway_id,
            include_modules=tuple(ModuleId(module) for module in sorted(include_modules)),
            exclude_modules=tuple(ModuleId(str(module)) for module in request.exclude_modules),
            source_claim=request.claim_text or None,
        )
    )


def _patch_to_candidate(patch: CandidatePatch, score: float, features: tuple[str, ...]) -> EdgePatchCandidate:
    return EdgePatchCandidate(
        edge_id=patch.edge_id,
        source=patch.source,
        target=patch.target,
        relation=patch.relation,
        sign=patch.sign,
        operator=patch.operator,
        score=min(max(score, 0.0), 1.0),
        rationale=patch.rationale,
        feature_summary=features,
    )


def _structured_context_score(candidate: CandidatePatch, request: OperatorPredictionInput) -> tuple[float, tuple[str, ...]]:
    score = 0.0
    features: list[str] = []
    if request.target_edge_id is not None and candidate.target == request.target_edge_id:
        score += 0.12
        features.append(f"selected_target:{candidate.target}")
    if request.desired_relation is not None and candidate.relation == request.desired_relation:
        score += 0.08
        features.append(f"selected_relation:{candidate.relation}")
    if (
        request.target_edge_id is not None
        and request.desired_relation is not None
        and candidate.target == request.target_edge_id
        and candidate.relation == request.desired_relation
    ):
        score += 0.1
        features.append("selected_patch_match")
    return score, tuple(features)


def _training_score(candidate: CandidatePatch, request: OperatorPredictionInput) -> tuple[float, tuple[str, ...]]:
    pathway = load_pathway(request.pathway_id)
    active = active_claim_text_for_keywords(request.claim_text).lower()
    score = 0.1
    features: list[str] = []
    context_score, context_features = _structured_context_score(candidate, request)
    score += context_score
    features.extend(context_features)
    for case in pathway.prediction.training_cases:
        keyword_hits = [keyword for keyword in case.keywords if keyword.lower() in active]
        if keyword_hits:
            score += 0.1 * len(keyword_hits)
            features.extend(f"training_keyword:{keyword}" for keyword in keyword_hits)
        for positive in case.positives:
            if (
                positive.get("target_edge") == str(candidate.target)
                and positive.get("relation") == str(candidate.relation)
                and keyword_hits
            ):
                score += 0.45
                features.append(f"training_positive:{candidate.target}:{candidate.relation}")
    return min(score, 0.95), tuple(dict.fromkeys(features))


def _rank_candidates(candidates: tuple[CandidatePatch, ...], request: OperatorPredictionInput) -> tuple[ScoredPatch, ...]:
    scored: list[ScoredPatch] = []
    for candidate in candidates:
        score, features = _training_score(candidate, request)
        scored.append(
            ScoredPatch(
                patch=_patch_to_candidate(candidate, score, features),
                score=score,
                model_score=score,
                feature_summary=features,
            )
        )
    return tuple(sorted(scored, key=lambda item: item.score, reverse=True))


def _constrained_candidates(
    candidates: tuple[CandidatePatch, ...],
    request: OperatorPredictionInput,
) -> tuple[CandidatePatch, ...]:
    constrained = candidates
    if request.target_edge_id is not None:
        constrained = tuple(candidate for candidate in constrained if candidate.target == request.target_edge_id)
    if request.desired_relation is not None:
        constrained = tuple(candidate for candidate in constrained if candidate.relation == request.desired_relation)
    return constrained


def _guardrail_matches_structured_request(
    guardrail: PredictionGuardrail,
    request: OperatorPredictionInput,
) -> bool:
    if request.target_edge_id is None and request.desired_relation is None:
        return True
    for recommendation in guardrail.recommendations:
        target_matches = (
            request.target_edge_id is None
            or EdgeId(str(recommendation["target_edge"])) == request.target_edge_id
        )
        relation_matches = (
            request.desired_relation is None
            or RelationId(str(recommendation["relation"])) == request.desired_relation
        )
        if target_matches and relation_matches:
            return True
    return False


def _recommendations_from_guardrails(
    ranked: Sequence[ScoredPatch],
    guardrails: tuple[PredictionGuardrail, ...],
    request: OperatorPredictionInput,
) -> tuple[EdgePatchCandidate, ...]:
    selected: list[EdgePatchCandidate] = []
    for guardrail in guardrails:
        if not _guardrail_matches_structured_request(guardrail, request):
            continue
        for recommendation in guardrail.recommendations:
            target = EdgeId(str(recommendation["target_edge"]))
            relation = RelationId(str(recommendation["relation"]))
            match = next(
                (item for item in ranked if item.patch.target == target and item.patch.relation == relation),
                None,
            )
            if match is None:
                continue
            selected.append(
                match.to_candidate().model_copy(
                    update={
                        "score": max(match.score, 0.85),
                        "rationale": guardrail.rationale,
                        "feature_summary": (*match.feature_summary, f"guardrail:{guardrail.id}"),
                    }
                )
            )
    by_id: dict[EdgeId, EdgePatchCandidate] = {}
    for candidate in selected:
        by_id[candidate.edge_id] = candidate
    return tuple(by_id.values())


def _operator_probabilities(ranked: Sequence[ScoredPatch]) -> tuple[OperatorProbability, ...]:
    scores: dict[OperatorId, float] = {
        OperatorId("edge_activation"): 0.0,
        OperatorId("edge_inhibition"): 0.0,
    }
    for item in ranked:
        scores[item.patch.operator] = max(scores.get(item.patch.operator, 0.0), item.score)
    total = sum(scores.values())
    normalized = dict.fromkeys(scores, 1.0 / len(scores)) if total <= 0.0 else {operator: score / total for operator, score in scores.items()}
    return tuple(
        OperatorProbability(operator=operator, probability=probability)
        for operator, probability in sorted(normalized.items(), key=lambda item: item[1], reverse=True)
    )


def _confidence_for_operator(probabilities: tuple[OperatorProbability, ...], operator: OperatorId) -> float:
    return next(item.probability for item in probabilities if item.operator == operator)


def _low_support(
    top_score: float,
    score_margin: float,
    matched_keywords: tuple[str, ...],
    matched_features: tuple[str, ...],
) -> bool:
    if not matched_keywords:
        return True
    if not any(feature.startswith("training_positive:") for feature in matched_features):
        return True
    if top_score < LOW_SUPPORT_SCORE_THRESHOLD:
        return True
    return top_score < 0.55 and score_margin < LOW_SUPPORT_MARGIN_THRESHOLD


def _warnings(guardrail_applied: bool, low_support: bool) -> tuple[ModelWarning, ...]:
    warnings = [
        _warning(
            "Toy data-defined graph-patch predictor: use as a compiler suggestion layer, not as evidence of biological truth."
        )
    ]
    if guardrail_applied:
        warnings.append(_warning("Data-defined guardrail applied; final recommendations are rule-based."))
    if low_support:
        warnings.append(
            _warning(
                "Prediction is low-support: no curated training example or graph candidate closely matches the claim; manual review recommended.",
                category=WarningCategory.LOW_CONFIDENCE,
            )
        )
    return tuple(warnings)


def predict_operator(request: OperatorPredictionInput) -> tuple[OperatorPrediction, tuple[ModelWarning, ...]]:
    pathway = load_pathway(request.pathway_id)
    if not pathway.prediction.enabled:
        raise ValueError(f"Prediction is disabled for pathway {request.pathway_id}")
    guardrails = _matched_guardrails(request)
    graph = _prediction_graph(request, guardrails)
    raw_candidates = generate_edge_patch_candidates(graph, pathway.prediction, source_node_id=request.source_node_id)
    candidates = _constrained_candidates(raw_candidates, request)
    if not candidates:
        raise ValueError("Prediction graph produced no edge-patch candidates matching the selected target/effect")

    ranked = list(_rank_candidates(candidates, request))
    if not ranked:
        raise ValueError("Prediction ranker produced no scored edge-patch candidates")

    guardrail_ranked = _rank_candidates(raw_candidates, request)
    guardrail_candidates = _recommendations_from_guardrails(guardrail_ranked, guardrails, request)
    model_top = ranked[0].to_candidate()
    final_candidates = guardrail_candidates or (model_top,)
    final_operators = tuple(dict.fromkeys(candidate.operator for candidate in final_candidates))
    if len(final_operators) > 1:
        raise ValueError(
            "Matched prediction guardrails recommend incompatible operators: "
            + ", ".join(str(operator) for operator in final_operators)
            + ". Narrow the selected target/effect or revise the claim."
        )
    final_operator = final_candidates[0].operator
    ranked_candidates = tuple(item.to_candidate() for item in ranked)
    second_score = ranked[1].score if len(ranked) > 1 else 0.0
    score_margin = max(ranked[0].score - second_score, 0.0)
    used_keywords = claim_keywords_used(request.claim_text, pathway.prediction)
    low_support = _low_support(ranked[0].score, score_margin, used_keywords, ranked[0].feature_summary)
    decision_source = "guardrail" if guardrail_candidates else "abstain" if low_support else "model"
    probabilities = _operator_probabilities(ranked)
    confidence = _confidence_for_operator(probabilities, final_operator)
    model_recommendations = (model_top.to_recommendation(),)
    recommendations = tuple(candidate.to_recommendation() for candidate in final_candidates)
    guardrail_recommendations = tuple(candidate.to_recommendation() for candidate in guardrail_candidates)
    included_modules = tuple(sorted({str(module) for guardrail in guardrails for module in guardrail.include_modules}))

    prediction = OperatorPrediction(
        predicted_operator=final_operator,
        confidence=confidence,
        probabilities=probabilities,
        recommendations=recommendations,
        candidates=ranked_candidates,
        diagnostics=PredictionDiagnostics(
            decision_source=decision_source,
            guardrail_applied=bool(guardrail_candidates),
            model_confidence=_confidence_for_operator(probabilities, model_top.operator),
            model_score=ranked[0].model_score,
            top_score=ranked[0].score,
            score_margin=score_margin,
            low_support=low_support,
            matched_positive_features=ranked[0].feature_summary,
            claim_keywords_used=used_keywords,
            negated_claim_keywords_used=negated_claim_keywords_used(request.claim_text, pathway.prediction),
            included_modules=included_modules,
        ),
        model_recommendations=model_recommendations,
        guardrail_recommendations=guardrail_recommendations,
    )
    return prediction, _warnings(guardrail_applied=bool(guardrail_candidates), low_support=low_support)
