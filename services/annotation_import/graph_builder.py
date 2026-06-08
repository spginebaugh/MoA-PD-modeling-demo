"""Build non-executable paper evidence graphs from annotation bundles."""

from __future__ import annotations

import hashlib
import re
from collections import Counter

from services.annotation_import.models import (
    AnnotationBundle,
    ContextScope,
    EquationRecord,
    EvidenceAnchor,
    EvidenceEquation,
    EvidenceGraphEdge,
    EvidenceGraphNode,
    EvidenceParameter,
    EvidenceSimulationModel,
    EvidenceSimulationParameter,
    MechanismChain,
    MechanismStep,
    MechanismVerification,
    NormalizedEntity,
    PaperEvidenceGraph,
    ParameterCandidate,
    ParameterObservation,
    ReviewStatus,
    SimulationModelRecord,
    SimulationParameterRecord,
    WarningRecord,
)
from services.annotation_import.provenance import anchor_index, context_scope, paper_provenance
from services.domain.base import JsonValue

_SLUG_PATTERN = re.compile(r"[^a-zA-Z0-9_]+")


def build_paper_evidence_graph(bundle: AnnotationBundle) -> PaperEvidenceGraph:
    anchors = anchor_index(bundle.evidence_anchors)
    warnings = list(_projection_warnings(bundle))
    warnings.extend(_readiness_warnings(bundle))

    verification_by_step = {
        (verification.mechanism_chain_id, verification.mechanism_step_id): verification
        for verification in bundle.mechanism_verifications
    }

    nodes: dict[str, EvidenceGraphNode] = {}
    edges: list[EvidenceGraphEdge] = []
    for chain in bundle.mechanism_chains:
        for step in chain.steps:
            verification = verification_by_step.get((chain.mechanism_chain_id, step.step_id))
            edge_nodes, edge = _mechanism_step_to_edge(bundle, chain, step, verification, anchors)
            for node in edge_nodes:
                nodes.setdefault(node.node_id, node)
            edges.append(edge)

    parameters = [
        *(_candidate_to_parameter(bundle, candidate, anchors) for candidate in bundle.parameter_candidates),
        *(_observation_to_parameter(bundle, observation, anchors) for observation in bundle.observations),
    ]
    equations = [_equation_to_evidence(bundle, equation, anchors) for equation in bundle.equations]
    simulation_models = [
        _simulation_model_to_evidence(bundle, model, anchors) for model in bundle.simulation_models
    ]
    simulation_parameters = [
        _simulation_parameter_to_evidence(bundle, parameter, anchors)
        for parameter in bundle.simulation_parameters
    ]

    return PaperEvidenceGraph(
        paper_id=bundle.paper.paper_id,
        title=bundle.paper.title,
        source=bundle.paper.source,
        nodes=tuple(nodes.values()),
        edges=tuple(edges),
        parameters=tuple(parameters),
        equations=tuple(equations),
        simulation_models=tuple(simulation_models),
        simulation_parameters=tuple(simulation_parameters),
        evidence_anchors=bundle.evidence_anchors,
        warnings=tuple(warnings),
        summary=_summary(
            bundle, edges, parameters, equations, simulation_models, simulation_parameters, warnings
        ),
    )


def _mechanism_step_to_edge(
    bundle: AnnotationBundle,
    chain: MechanismChain,
    step: MechanismStep,
    verification: MechanismVerification | None,
    anchors: dict[str, EvidenceAnchor],
) -> tuple[tuple[EvidenceGraphNode, EvidenceGraphNode], EvidenceGraphEdge]:
    anchor_ids = _coalesce_anchor_ids(
        step.evidence_anchor_ids, verification.evidence_anchor_ids if verification else ()
    )
    scope = context_scope(step.context, anchor_ids, anchors, step.quote)
    subject_node = _node_for_entity(
        bundle=bundle,
        raw_label=step.subject,
        normalized=verification.normalized_subject if verification else None,
        source_record_id=step.step_id,
        evidence_anchor_ids=anchor_ids,
        scope=scope,
        anchors=anchors,
    )
    object_node = _node_for_entity(
        bundle=bundle,
        raw_label=step.object,
        normalized=verification.normalized_object if verification else None,
        source_record_id=step.step_id,
        evidence_anchor_ids=anchor_ids,
        scope=scope,
        anchors=anchors,
    )
    edge_warnings = tuple(_mechanism_warnings(step, verification))
    review_status = _mechanism_review_status(verification, edge_warnings)
    provenance = paper_provenance(
        bundle.paper,
        "mechanism_step",
        step.step_id,
        anchor_ids,
        anchors,
        quote_or_sentence=step.quote,
        verification_id=verification.verification_id if verification else None,
        verification_verdict=verification.verdict if verification else None,
        relation_class=verification.relation_class if verification else None,
        validation_status=verification.verdict if verification else None,
        trust_level=str(verification.confidence)
        if verification and verification.confidence is not None
        else None,
        warnings=edge_warnings,
    )
    edge = EvidenceGraphEdge(
        edge_id=f"edge:{bundle.paper.paper_id}:{_slug(step.step_id)}",
        source=subject_node.node_id,
        target=object_node.node_id,
        relation=_relation_for_predicate(step.predicate),
        predicate=step.predicate,
        paper_id=bundle.paper.paper_id,
        source_record_id=step.step_id,
        evidence_anchor_ids=anchor_ids,
        context=scope,
        verification_id=verification.verification_id if verification else None,
        verification_verdict=verification.verdict if verification else None,
        relation_class=verification.relation_class if verification else None,
        validation_status=verification.verdict if verification else None,
        confidence=verification.confidence if verification else None,
        review_status=review_status,
        provenance=provenance,
        warnings=edge_warnings,
        metadata={
            "mechanism_chain_id": chain.mechanism_chain_id,
            "raw_subject": step.subject,
            "raw_object": step.object,
            "executable": False,
        },
    )
    return (subject_node, object_node), edge


def _node_for_entity(
    bundle: AnnotationBundle,
    raw_label: str,
    normalized: NormalizedEntity | None,
    source_record_id: str,
    evidence_anchor_ids: tuple[str, ...],
    scope: ContextScope,
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceGraphNode:
    usable_normalization = normalized is not None and normalized.is_usable
    if usable_normalization and normalized is not None:
        node_id = normalized.canonical_id or _raw_node_id(bundle.paper.paper_id, raw_label)
        label = normalized.normalized_label or raw_label
        node_type = normalized.concept_type or "Entity"
    else:
        node_id = _raw_node_id(bundle.paper.paper_id, raw_label)
        label = raw_label
        node_type = "Entity"
    review_status: ReviewStatus = "accepted_for_evidence_graph" if usable_normalization else "review_only"
    warnings = () if usable_normalization else ("missing_or_low_confidence_normalization",)
    provenance = paper_provenance(
        bundle.paper,
        "mechanism_step",
        source_record_id,
        evidence_anchor_ids,
        anchors,
        warnings=warnings,
    )
    return EvidenceGraphNode(
        node_id=node_id,
        label=label,
        node_type=node_type,
        paper_id=bundle.paper.paper_id,
        source_record_type="mechanism_step",
        source_record_id=source_record_id,
        evidence_anchor_ids=evidence_anchor_ids,
        context=scope,
        validation_status="normalized" if usable_normalization else "surface_only",
        confidence=normalized.match_score if usable_normalization and normalized else None,
        review_status=review_status,
        provenance=provenance,
        metadata={
            "raw_label": raw_label,
            "canonical_id": normalized.canonical_id if normalized else None,
            "source_ontology": normalized.source_ontology if normalized else None,
            "match_method": normalized.match_method if normalized else None,
            "match_score": normalized.match_score if normalized else None,
        },
    )


def _candidate_to_parameter(
    bundle: AnnotationBundle,
    candidate: ParameterCandidate,
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceParameter:
    anchor_ids = candidate.anchor_ids
    scope = context_scope(candidate.context, anchor_ids, anchors, candidate.parameter)
    warnings = tuple(_parameter_warnings(candidate.value, candidate.unit, scope, None, candidate.warnings))
    provenance = paper_provenance(
        bundle.paper,
        "parameter_candidate",
        candidate.candidate_id,
        anchor_ids,
        anchors,
        quote_or_sentence=candidate.value_text,
        validation_status=None,
        trust_level=str(candidate.confidence) if candidate.confidence is not None else None,
        warnings=warnings,
    )
    return EvidenceParameter(
        parameter_id=f"parameter:{_slug(candidate.candidate_id)}",
        paper_id=bundle.paper.paper_id,
        source_record_type="parameter_candidate",
        source_record_id=candidate.candidate_id,
        name=candidate.parameter,
        family=candidate.family,
        value=candidate.value,
        value_text=candidate.value_text,
        unit=candidate.unit,
        subject=candidate.subject_hint,
        evidence_anchor_ids=anchor_ids,
        context=scope,
        validation_status=None,
        confidence=candidate.confidence,
        review_status="review_only" if warnings else "accepted_for_evidence_graph",
        provenance=provenance,
        warnings=warnings,
        metadata={"executable": False},
    )


def _observation_to_parameter(
    bundle: AnnotationBundle,
    observation: ParameterObservation,
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceParameter:
    anchor_ids = observation.evidence_anchor_ids
    scope = context_scope(observation.context, anchor_ids, anchors, observation.parameter)
    warnings = tuple(
        _parameter_warnings(
            observation.value,
            observation.unit,
            scope,
            observation.validation_status,
            observation.validation_warnings,
        )
    )
    review_status: ReviewStatus = "review_only" if warnings else "accepted_for_evidence_graph"
    provenance = paper_provenance(
        bundle.paper,
        "observation",
        observation.observation_id,
        anchor_ids,
        anchors,
        quote_or_sentence=observation.value_text,
        validation_status=observation.validation_status,
        trust_level=observation.trust_level,
        warnings=warnings,
    )
    return EvidenceParameter(
        parameter_id=f"parameter:{_slug(observation.observation_id)}",
        paper_id=bundle.paper.paper_id,
        source_record_type="observation",
        source_record_id=observation.observation_id,
        name=observation.parameter,
        family=observation.family,
        value=observation.value,
        value_text=observation.value_text,
        unit=observation.unit,
        subject=observation.subject,
        evidence_anchor_ids=anchor_ids,
        context=scope,
        validation_status=observation.validation_status,
        confidence=observation.trust_level,
        review_status=review_status,
        provenance=provenance,
        warnings=warnings,
        metadata={
            "source_candidate_id": observation.source_candidate_id,
            "executable": False,
        },
    )


def _equation_to_evidence(
    bundle: AnnotationBundle,
    equation: EquationRecord,
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceEquation:
    scope = context_scope({}, equation.evidence_anchor_ids, anchors, equation.expression)
    review_status: ReviewStatus = (
        "accepted_for_evidence_graph" if equation.validation_status == "verified" else "review_only"
    )
    provenance = paper_provenance(
        bundle.paper,
        "equation",
        equation.equation_id,
        equation.evidence_anchor_ids,
        anchors,
        quote_or_sentence=equation.expression,
        validation_status=equation.validation_status,
    )
    return EvidenceEquation(
        equation_id=equation.equation_id,
        paper_id=bundle.paper.paper_id,
        expression_text=equation.expression,
        variables=equation.variables,
        model_type=equation.model_type,
        evidence_anchor_ids=equation.evidence_anchor_ids,
        context=scope,
        validation_status=equation.validation_status,
        review_status=review_status,
        provenance=provenance,
        metadata={
            "display_only": True,
            "executable": False,
        },
    )


def _simulation_model_to_evidence(
    bundle: AnnotationBundle,
    model: SimulationModelRecord,
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceSimulationModel:
    scope = context_scope(model.context, model.evidence_anchor_ids, anchors, model.model_type)
    review_status: ReviewStatus = (
        "accepted_for_evidence_graph" if model.validation_status == "verified" else "review_only"
    )
    provenance = paper_provenance(
        bundle.paper,
        "simulation_model",
        model.simulation_id,
        model.evidence_anchor_ids,
        anchors,
        quote_or_sentence=model.scenario,
        simulation_model_id=model.simulation_id,
        validation_status=model.validation_status,
    )
    return EvidenceSimulationModel(
        simulation_model_id=model.simulation_id,
        paper_id=bundle.paper.paper_id,
        model_type=model.model_type,
        platform=model.platform,
        population=model.population,
        scenario=model.scenario,
        analytes=model.analytes,
        compartments=model.compartments,
        evidence_anchor_ids=model.evidence_anchor_ids,
        context=scope,
        validation_status=model.validation_status,
        review_status=review_status,
        provenance=provenance,
        metadata={
            "validation_metric": model.validation_metric,
            "executable": False,
        },
    )


def _simulation_parameter_to_evidence(
    bundle: AnnotationBundle,
    parameter: SimulationParameterRecord,
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceSimulationParameter:
    scope = context_scope(parameter.context, parameter.evidence_anchor_ids, anchors, parameter.parameter_name)
    warnings = tuple(_simulation_parameter_warnings(parameter, scope))
    review_status = _simulation_parameter_review_status(parameter, warnings)
    provenance = paper_provenance(
        bundle.paper,
        "simulation_parameter",
        parameter.simulation_parameter_id,
        parameter.evidence_anchor_ids,
        anchors,
        quote_or_sentence=parameter.value_text,
        simulation_parameter_id=parameter.simulation_parameter_id,
        validation_status=parameter.validation_status,
        warnings=warnings,
    )
    return EvidenceSimulationParameter(
        simulation_parameter_id=parameter.simulation_parameter_id,
        paper_id=bundle.paper.paper_id,
        parameter_name=parameter.parameter_name,
        family=parameter.family,
        role=parameter.role,
        value=parameter.value,
        value_text=parameter.value_text,
        unit=parameter.unit,
        source_type=parameter.source_type,
        provenance_status=parameter.provenance_status,
        required_for=parameter.required_for,
        linked_observation_id=parameter.linked_observation_id,
        linked_equation_id=parameter.linked_equation_id,
        linked_figure_annotation_id=parameter.linked_figure_annotation_id,
        evidence_anchor_ids=parameter.evidence_anchor_ids,
        context=scope,
        validation_status=parameter.validation_status,
        review_status=review_status,
        provenance=provenance,
        warnings=warnings,
        metadata={"executable": False},
    )


def _projection_warnings(bundle: AnnotationBundle) -> tuple[WarningRecord, ...]:
    mechanism_projection_count = _projection_node_count(bundle, "tktype:MechanismChain")
    verification_projection_count = _projection_node_count(bundle, "tktype:MechanismVerification")
    top_level_step_count = sum(len(chain.steps) for chain in bundle.mechanism_chains)
    top_level_verification_count = len(bundle.mechanism_verifications)
    warnings: list[WarningRecord] = []
    if mechanism_projection_count and mechanism_projection_count != top_level_step_count:
        warnings.append(
            WarningRecord(
                code="kg_projection_mechanisms_ignored",
                message=(
                    f"Ignored {mechanism_projection_count} projected mechanism nodes; "
                    f"used {top_level_step_count} top-level mechanism steps."
                ),
                source_record_type="kg_projection",
            )
        )
    if verification_projection_count and verification_projection_count != top_level_verification_count:
        warnings.append(
            WarningRecord(
                code="kg_projection_verifications_ignored",
                message=(
                    f"Ignored {verification_projection_count} projected verification nodes; "
                    f"used {top_level_verification_count} top-level verification records."
                ),
                source_record_type="kg_projection",
            )
        )
    return tuple(warnings)


def _readiness_warnings(bundle: AnnotationBundle) -> tuple[WarningRecord, ...]:
    warnings: list[WarningRecord] = []
    if not bundle.mechanism_chains:
        warnings.append(
            WarningRecord(
                code="no_top_level_mechanism_chains",
                message="No top-level mechanism chains were available for causal extraction.",
                source_record_type="mechanism_chains",
            )
        )
    for plan in bundle.simulation_readiness_plans:
        if plan.readiness_status and plan.readiness_status != "ready":
            warnings.append(
                WarningRecord(
                    code="simulation_readiness_not_ready",
                    message=f"Simulation readiness is {plan.readiness_status}: {plan.decision_reason or 'review required'}.",
                    source_record_type="simulation_readiness_plan",
                    source_record_id=plan.plan_id,
                )
            )
        for missing in plan.missing_inputs:
            name = missing.get("name")
            reason = missing.get("reason")
            severity = missing.get("severity")
            if isinstance(name, str):
                warnings.append(
                    WarningRecord(
                        code="missing_model_input",
                        message=f"Missing {name}: {reason}"
                        if isinstance(reason, str)
                        else f"Missing {name}.",
                        severity="error" if severity == "blocking" else "warning",
                        source_record_type="simulation_readiness_plan",
                        source_record_id=plan.plan_id,
                    )
                )
    return tuple(warnings)


def _mechanism_warnings(
    step: MechanismStep,
    verification: MechanismVerification | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if not step.evidence_anchor_ids:
        warnings.append("missing_evidence_anchor")
    if verification is None:
        warnings.append("missing_top_level_verification")
    else:
        warnings.extend(verification.issues)
    return tuple(warnings)


def _parameter_warnings(
    value: float | None,
    unit: str | None,
    scope: ContextScope,
    validation_status: str | None,
    existing_warnings: tuple[str, ...],
) -> tuple[str, ...]:
    warnings = list(existing_warnings)
    if value is None:
        warnings.append("missing_value")
    if unit is None:
        warnings.append("missing_unit")
    if validation_status is not None and validation_status != "verified":
        warnings.append(f"validation_status:{validation_status}")
    if not (scope.species or scope.translation_stage or scope.model_system):
        warnings.append("missing_species_or_translation_context")
    return tuple(dict.fromkeys(warnings))


def _simulation_parameter_warnings(
    parameter: SimulationParameterRecord,
    scope: ContextScope,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if parameter.validation_status != "verified":
        warnings.append(f"validation_status:{parameter.validation_status or 'unknown'}")
    if parameter.value is None and parameter.role not in {"model_structure"}:
        warnings.append("missing_value")
    if parameter.unit is None:
        warnings.append("missing_unit")
    if parameter.role == "calibration_or_validation_endpoint":
        warnings.append("calibration_or_validation_endpoint")
    if not (scope.species or scope.translation_stage or scope.model_system):
        warnings.append("missing_species_or_translation_context")
    return tuple(dict.fromkeys(warnings))


def _mechanism_review_status(
    verification: MechanismVerification | None,
    warnings: tuple[str, ...],
) -> ReviewStatus:
    if "missing_evidence_anchor" in warnings:
        return "review_only"
    if verification is None:
        return "review_only"
    if verification.verdict in {"verified_therapeutic_moa", "model_derived_pd_relation"}:
        return "candidate_for_pathway_patch"
    if verification.verdict == "paper_supported_only":
        return "accepted_for_evidence_graph"
    return "review_only"


def _simulation_parameter_review_status(
    parameter: SimulationParameterRecord,
    warnings: tuple[str, ...],
) -> ReviewStatus:
    if warnings:
        return "review_only"
    if parameter.role in {"model_input", "equation_variable", "model_structure", "candidate_model_input"}:
        return "candidate_for_pathway_patch"
    return "accepted_for_evidence_graph"


def _relation_for_predicate(predicate: str) -> str:
    lowered = predicate.lower()
    if "inhibit" in lowered or "decreas" in lowered or "suppress" in lowered:
        return "inhibits"
    if "bind" in lowered:
        return "binds"
    if "activat" in lowered or "increase" in lowered or "drive" in lowered:
        return "activates"
    if "predict" in lowered:
        return "predicts"
    return "relates_to"


def _projection_node_count(bundle: AnnotationBundle, node_type: str) -> int:
    nodes = bundle.kg_projection.get("nodes")
    if not isinstance(nodes, list):
        return 0
    count = 0
    for node in nodes:
        if isinstance(node, dict) and node.get("node_type") == node_type:
            count += 1
    return count


def _coalesce_anchor_ids(primary: tuple[str, ...], fallback: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*primary, *fallback)))


def _raw_node_id(paper_id: str, label: str) -> str:
    digest = hashlib.sha1(label.encode("utf-8")).hexdigest()[:10]
    return f"raw:{paper_id}:{_slug(label)}:{digest}"


def _slug(value: str) -> str:
    slug = _SLUG_PATTERN.sub("_", value).strip("_").lower()
    return slug[:80] or hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _summary(
    bundle: AnnotationBundle,
    edges: list[EvidenceGraphEdge],
    parameters: list[EvidenceParameter],
    equations: list[EvidenceEquation],
    simulation_models: list[EvidenceSimulationModel],
    simulation_parameters: list[EvidenceSimulationParameter],
    warnings: list[WarningRecord],
) -> dict[str, JsonValue]:
    edge_status_counts = Counter(edge.review_status for edge in edges)
    parameter_status_counts = Counter(parameter.review_status for parameter in parameters)
    simulation_parameter_roles = Counter(parameter.role for parameter in simulation_parameters)
    return {
        "top_level_mechanism_chain_count": len(bundle.mechanism_chains),
        "top_level_mechanism_step_count": sum(len(chain.steps) for chain in bundle.mechanism_chains),
        "top_level_mechanism_verification_count": len(bundle.mechanism_verifications),
        "kg_projection_mechanism_node_count": _projection_node_count(bundle, "tktype:MechanismChain"),
        "kg_projection_verification_node_count": _projection_node_count(
            bundle, "tktype:MechanismVerification"
        ),
        "edge_count": len(edges),
        "parameter_count": len(parameters),
        "equation_count": len(equations),
        "simulation_model_count": len(simulation_models),
        "simulation_parameter_count": len(simulation_parameters),
        "evidence_anchor_count": len(bundle.evidence_anchors),
        "warning_count": len(warnings),
        "edge_review_status_counts": dict(sorted(edge_status_counts.items())),
        "parameter_review_status_counts": dict(sorted(parameter_status_counts.items())),
        "simulation_parameter_role_counts": dict(sorted(simulation_parameter_roles.items())),
        "runtime_executable": False,
    }
