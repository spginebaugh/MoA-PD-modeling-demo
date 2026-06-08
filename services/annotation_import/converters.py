"""Convert annotation records into evidence graph records."""

from __future__ import annotations

from services.annotation_import.graph_ids import coalesce_anchor_ids, raw_node_id, slug
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
    ParameterCandidate,
    ParameterObservation,
    ReviewStatus,
    SimulationModelRecord,
    SimulationParameterRecord,
)
from services.annotation_import.provenance import context_scope, paper_provenance
from services.annotation_import.review_policy import (
    mechanism_review_status,
    mechanism_warnings,
    parameter_warnings,
    relation_for_predicate,
    simulation_parameter_review_status,
    simulation_parameter_warnings,
)


def mechanism_step_to_edge(
    bundle: AnnotationBundle,
    chain: MechanismChain,
    step: MechanismStep,
    verification: MechanismVerification | None,
    anchors: dict[str, EvidenceAnchor],
) -> tuple[tuple[EvidenceGraphNode, EvidenceGraphNode], EvidenceGraphEdge]:
    anchor_ids = coalesce_anchor_ids(
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
    edge_warnings = tuple(mechanism_warnings(step, verification))
    review_status = mechanism_review_status(verification, edge_warnings)
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
        edge_id=f"edge:{bundle.paper.paper_id}:{slug(step.step_id)}",
        source=subject_node.node_id,
        target=object_node.node_id,
        relation=relation_for_predicate(step.predicate),
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


def candidate_to_parameter(
    bundle: AnnotationBundle,
    candidate: ParameterCandidate,
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceParameter:
    anchor_ids = candidate.anchor_ids
    scope = context_scope(candidate.context, anchor_ids, anchors, candidate.parameter)
    warnings = tuple(parameter_warnings(candidate.value, candidate.unit, scope, None, candidate.warnings))
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
        parameter_id=f"parameter:{slug(candidate.candidate_id)}",
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


def observation_to_parameter(
    bundle: AnnotationBundle,
    observation: ParameterObservation,
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceParameter:
    anchor_ids = observation.evidence_anchor_ids
    scope = context_scope(observation.context, anchor_ids, anchors, observation.parameter)
    warnings = tuple(
        parameter_warnings(
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
        parameter_id=f"parameter:{slug(observation.observation_id)}",
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


def equation_to_evidence(
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


def simulation_model_to_evidence(
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


def simulation_parameter_to_evidence(
    bundle: AnnotationBundle,
    parameter: SimulationParameterRecord,
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceSimulationParameter:
    scope = context_scope(parameter.context, parameter.evidence_anchor_ids, anchors, parameter.parameter_name)
    warnings = tuple(simulation_parameter_warnings(parameter, scope))
    review_status = simulation_parameter_review_status(parameter, warnings)
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
        node_id = normalized.canonical_id or raw_node_id(bundle.paper.paper_id, raw_label)
        label = normalized.normalized_label or raw_label
        node_type = normalized.concept_type or "Entity"
    else:
        node_id = raw_node_id(bundle.paper.paper_id, raw_label)
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
