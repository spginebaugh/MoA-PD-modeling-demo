"""Assemble topology links around converted evidence graph records."""

from __future__ import annotations

from services.annotation_import.graph_ids import coalesce_anchor_ids, defined_equation_symbols, link_id
from services.annotation_import.models import (
    AnnotationBundle,
    ContextScope,
    EvidenceAnchor,
    EvidenceEquation,
    EvidenceGraphEdge,
    EvidenceGraphLink,
    EvidenceGraphNode,
    EvidenceParameter,
    EvidenceSimulationModel,
    EvidenceSimulationParameter,
    ReviewStatus,
    SourceRecordType,
)
from services.annotation_import.node_factory import (
    add_node,
    context_has_signal,
    context_node,
    equation_node,
    evidence_anchor_node,
    figure_annotation_node,
    mechanism_edge_node,
    parameter_node,
    quantity_node_for_record,
    scientific_symbol_node,
    simulation_model_node,
    simulation_parameter_node,
    study_design_node,
)
from services.annotation_import.provenance import context_scope, paper_provenance
from services.annotation_import.review_policy import study_translation_stage
from services.domain.base import JsonValue


def connect_evidence_graph(
    *,
    bundle: AnnotationBundle,
    nodes: dict[str, EvidenceGraphNode],
    edges: list[EvidenceGraphEdge],
    parameters: list[EvidenceParameter],
    equations: list[EvidenceEquation],
    simulation_models: list[EvidenceSimulationModel],
    simulation_parameters: list[EvidenceSimulationParameter],
    anchors: dict[str, EvidenceAnchor],
) -> list[EvidenceGraphLink]:
    links: dict[str, EvidenceGraphLink] = {}
    parameter_by_source_record = {parameter.source_record_id: parameter for parameter in parameters}
    equation_by_id = {equation.equation_id: equation for equation in equations}
    figure_by_id = {figure.figure_annotation_id: figure for figure in bundle.figure_annotations}

    for anchor in bundle.evidence_anchors:
        add_node(nodes, evidence_anchor_node(bundle, anchor, anchors))

    for edge in edges:
        add_node(nodes, mechanism_edge_node(bundle, edge, nodes, anchors))
        _add_link(
            links,
            bundle=bundle,
            source=edge.edge_id,
            target=edge.source,
            relation="causal_source",
            source_record_type="mechanism_edge",
            source_record_id=edge.source_record_id,
            evidence_anchor_ids=edge.evidence_anchor_ids,
            anchors=anchors,
            context=edge.context,
            validation_status=edge.validation_status,
            confidence=edge.confidence,
            review_status=edge.review_status,
            warnings=edge.warnings,
            metadata={"edge_id": edge.edge_id, "relation": edge.relation},
        )
        _add_link(
            links,
            bundle=bundle,
            source=edge.edge_id,
            target=edge.target,
            relation="causal_target",
            source_record_type="mechanism_edge",
            source_record_id=edge.source_record_id,
            evidence_anchor_ids=edge.evidence_anchor_ids,
            anchors=anchors,
            context=edge.context,
            validation_status=edge.validation_status,
            confidence=edge.confidence,
            review_status=edge.review_status,
            warnings=edge.warnings,
            metadata={"edge_id": edge.edge_id, "relation": edge.relation},
        )
        _add_record_support_links(
            links,
            nodes=nodes,
            bundle=bundle,
            record_node_id=edge.edge_id,
            source_record_type="mechanism_edge",
            source_record_id=edge.source_record_id,
            evidence_anchor_ids=edge.evidence_anchor_ids,
            anchors=anchors,
            context=edge.context,
            validation_status=edge.validation_status,
            confidence=edge.confidence,
            review_status=edge.review_status,
            warnings=edge.warnings,
        )

    for parameter in parameters:
        add_node(nodes, parameter_node(parameter))
        _add_record_support_links(
            links,
            nodes=nodes,
            bundle=bundle,
            record_node_id=parameter.parameter_id,
            source_record_type=parameter.source_record_type,
            source_record_id=parameter.source_record_id,
            evidence_anchor_ids=parameter.evidence_anchor_ids,
            anchors=anchors,
            context=parameter.context,
            validation_status=parameter.validation_status,
            confidence=parameter.confidence,
            review_status=parameter.review_status,
            warnings=parameter.warnings,
        )
        quantity = quantity_node_for_record(
            bundle=bundle,
            label=parameter.subject or parameter.name,
            family=parameter.family,
            role=parameter.source_record_type,
            evidence_anchor_ids=parameter.evidence_anchor_ids,
            context=parameter.context,
            anchors=anchors,
        )
        add_node(nodes, quantity)
        _add_link(
            links,
            bundle=bundle,
            source=parameter.parameter_id,
            target=quantity.node_id,
            relation="parameter_for",
            source_record_type=parameter.source_record_type,
            source_record_id=parameter.source_record_id,
            evidence_anchor_ids=parameter.evidence_anchor_ids,
            anchors=anchors,
            context=parameter.context,
            validation_status=parameter.validation_status,
            confidence=parameter.confidence,
            review_status=parameter.review_status,
            warnings=parameter.warnings,
            metadata={"family": parameter.family, "value": parameter.value, "unit": parameter.unit},
        )
        source_candidate_id = parameter.metadata.get("source_candidate_id")
        if isinstance(source_candidate_id, str):
            candidate = parameter_by_source_record.get(source_candidate_id)
            if candidate is not None:
                _add_link(
                    links,
                    bundle=bundle,
                    source=parameter.parameter_id,
                    target=candidate.parameter_id,
                    relation="derived_from_candidate",
                    source_record_type=parameter.source_record_type,
                    source_record_id=parameter.source_record_id,
                    evidence_anchor_ids=parameter.evidence_anchor_ids,
                    anchors=anchors,
                    context=parameter.context,
                    validation_status=parameter.validation_status,
                    confidence=parameter.confidence,
                    review_status=parameter.review_status,
                    warnings=parameter.warnings,
                )

    for equation in equations:
        add_node(nodes, equation_node(equation))
        _add_record_support_links(
            links,
            nodes=nodes,
            bundle=bundle,
            record_node_id=equation.equation_id,
            source_record_type="equation",
            source_record_id=equation.equation_id,
            evidence_anchor_ids=equation.evidence_anchor_ids,
            anchors=anchors,
            context=equation.context,
            validation_status=equation.validation_status,
            confidence=None,
            review_status=equation.review_status,
            warnings=(),
        )
        defined_symbols = defined_equation_symbols(equation.expression_text)
        for variable in equation.variables:
            quantity = quantity_node_for_record(
                bundle=bundle,
                label=variable.symbol,
                family="equation_variable",
                role=variable.meaning,
                evidence_anchor_ids=equation.evidence_anchor_ids,
                context=equation.context,
                anchors=anchors,
            )
            add_node(nodes, quantity)
            relation = "equation_defines" if variable.symbol in defined_symbols else "equation_uses_variable"
            _add_link(
                links,
                bundle=bundle,
                source=equation.equation_id,
                target=quantity.node_id,
                relation=relation,
                source_record_type="equation",
                source_record_id=equation.equation_id,
                evidence_anchor_ids=equation.evidence_anchor_ids,
                anchors=anchors,
                context=equation.context,
                validation_status=equation.validation_status,
                confidence=None,
                review_status=equation.review_status,
                metadata={"symbol": variable.symbol, "meaning": variable.meaning},
            )

    for model in simulation_models:
        add_node(nodes, simulation_model_node(model))
        _add_record_support_links(
            links,
            nodes=nodes,
            bundle=bundle,
            record_node_id=model.simulation_model_id,
            source_record_type="simulation_model",
            source_record_id=model.simulation_model_id,
            evidence_anchor_ids=model.evidence_anchor_ids,
            anchors=anchors,
            context=model.context,
            validation_status=model.validation_status,
            confidence=None,
            review_status=model.review_status,
            warnings=(),
        )
        for equation in equations:
            if model.model_type and equation.model_type and model.model_type == equation.model_type:
                _add_link(
                    links,
                    bundle=bundle,
                    source=model.simulation_model_id,
                    target=equation.equation_id,
                    relation="model_has_equation",
                    source_record_type="simulation_model",
                    source_record_id=model.simulation_model_id,
                    evidence_anchor_ids=coalesce_anchor_ids(
                        model.evidence_anchor_ids, equation.evidence_anchor_ids
                    ),
                    anchors=anchors,
                    context=model.context,
                    validation_status=model.validation_status,
                    confidence=None,
                    review_status="review_only",
                    metadata={"model_type": model.model_type},
                )

    for simulation_parameter in simulation_parameters:
        add_node(nodes, simulation_parameter_node(simulation_parameter))
        _add_record_support_links(
            links,
            nodes=nodes,
            bundle=bundle,
            record_node_id=simulation_parameter.simulation_parameter_id,
            source_record_type="simulation_parameter",
            source_record_id=simulation_parameter.simulation_parameter_id,
            evidence_anchor_ids=simulation_parameter.evidence_anchor_ids,
            anchors=anchors,
            context=simulation_parameter.context,
            validation_status=simulation_parameter.validation_status,
            confidence=None,
            review_status=simulation_parameter.review_status,
            warnings=simulation_parameter.warnings,
        )
        quantity = quantity_node_for_record(
            bundle=bundle,
            label=simulation_parameter.parameter_name,
            family=simulation_parameter.family,
            role=simulation_parameter.role,
            evidence_anchor_ids=simulation_parameter.evidence_anchor_ids,
            context=simulation_parameter.context,
            anchors=anchors,
        )
        add_node(nodes, quantity)
        _add_link(
            links,
            bundle=bundle,
            source=simulation_parameter.simulation_parameter_id,
            target=quantity.node_id,
            relation="simulation_parameter_for",
            source_record_type="simulation_parameter",
            source_record_id=simulation_parameter.simulation_parameter_id,
            evidence_anchor_ids=simulation_parameter.evidence_anchor_ids,
            anchors=anchors,
            context=simulation_parameter.context,
            validation_status=simulation_parameter.validation_status,
            confidence=None,
            review_status=simulation_parameter.review_status,
            warnings=simulation_parameter.warnings,
            metadata={
                "family": simulation_parameter.family,
                "role": simulation_parameter.role,
                "value": simulation_parameter.value,
                "unit": simulation_parameter.unit,
            },
        )
        if simulation_parameter.linked_observation_id:
            linked_parameter = parameter_by_source_record.get(simulation_parameter.linked_observation_id)
            if linked_parameter is not None:
                _add_link(
                    links,
                    bundle=bundle,
                    source=simulation_parameter.simulation_parameter_id,
                    target=linked_parameter.parameter_id,
                    relation="derived_from_observation",
                    source_record_type="simulation_parameter",
                    source_record_id=simulation_parameter.simulation_parameter_id,
                    evidence_anchor_ids=simulation_parameter.evidence_anchor_ids,
                    anchors=anchors,
                    context=simulation_parameter.context,
                    validation_status=simulation_parameter.validation_status,
                    confidence=None,
                    review_status=simulation_parameter.review_status,
                    warnings=simulation_parameter.warnings,
                )
        if (
            simulation_parameter.linked_equation_id
            and simulation_parameter.linked_equation_id in equation_by_id
        ):
            _add_link(
                links,
                bundle=bundle,
                source=simulation_parameter.simulation_parameter_id,
                target=simulation_parameter.linked_equation_id,
                relation="variable_in_equation",
                source_record_type="simulation_parameter",
                source_record_id=simulation_parameter.simulation_parameter_id,
                evidence_anchor_ids=simulation_parameter.evidence_anchor_ids,
                anchors=anchors,
                context=simulation_parameter.context,
                validation_status=simulation_parameter.validation_status,
                confidence=None,
                review_status=simulation_parameter.review_status,
                warnings=simulation_parameter.warnings,
            )
        if (
            simulation_parameter.linked_figure_annotation_id
            and simulation_parameter.linked_figure_annotation_id in figure_by_id
        ):
            _add_link(
                links,
                bundle=bundle,
                source=simulation_parameter.simulation_parameter_id,
                target=simulation_parameter.linked_figure_annotation_id,
                relation="derived_from_figure",
                source_record_type="simulation_parameter",
                source_record_id=simulation_parameter.simulation_parameter_id,
                evidence_anchor_ids=simulation_parameter.evidence_anchor_ids,
                anchors=anchors,
                context=simulation_parameter.context,
                validation_status=simulation_parameter.validation_status,
                confidence=None,
                review_status=simulation_parameter.review_status,
                warnings=simulation_parameter.warnings,
            )

    for figure in bundle.figure_annotations:
        scope = context_scope(figure.context, figure.evidence_anchor_ids, anchors, figure.caption)
        add_node(nodes, figure_annotation_node(bundle, figure, scope, anchors))
        _add_record_support_links(
            links,
            nodes=nodes,
            bundle=bundle,
            record_node_id=figure.figure_annotation_id,
            source_record_type="figure_annotation",
            source_record_id=figure.figure_annotation_id,
            evidence_anchor_ids=figure.evidence_anchor_ids,
            anchors=anchors,
            context=scope,
            validation_status=figure.validation_status,
            confidence=None,
            review_status="accepted_for_evidence_graph"
            if figure.validation_status == "verified"
            else "review_only",
            warnings=(),
        )

    for symbol in bundle.scientific_symbols:
        scope = context_scope(symbol.scope, symbol.evidence_anchor_ids, anchors, symbol.raw_symbol)
        add_node(nodes, scientific_symbol_node(bundle, symbol, scope, anchors))
        _add_record_support_links(
            links,
            nodes=nodes,
            bundle=bundle,
            record_node_id=symbol.symbol_id,
            source_record_type="scientific_symbol",
            source_record_id=symbol.symbol_id,
            evidence_anchor_ids=symbol.evidence_anchor_ids,
            anchors=anchors,
            context=scope,
            validation_status=None,
            confidence=symbol.interpretation_confidence,
            review_status="accepted_for_evidence_graph",
            warnings=(),
        )
        if symbol.source_observation_id:
            linked_parameter = parameter_by_source_record.get(symbol.source_observation_id)
            if linked_parameter is not None:
                _add_link(
                    links,
                    bundle=bundle,
                    source=symbol.symbol_id,
                    target=linked_parameter.parameter_id,
                    relation="symbol_for_observation",
                    source_record_type="scientific_symbol",
                    source_record_id=symbol.symbol_id,
                    evidence_anchor_ids=symbol.evidence_anchor_ids,
                    anchors=anchors,
                    context=scope,
                    validation_status=None,
                    confidence=symbol.interpretation_confidence,
                    review_status="accepted_for_evidence_graph",
                )

    for study_design in bundle.study_designs:
        scope = context_scope(study_design.context, study_design.evidence_anchor_ids, anchors)
        scope = scope.model_copy(
            update={
                "species": study_design.species or scope.species,
                "translation_stage": study_translation_stage(study_design) or scope.translation_stage,
                "model_system": study_design.study_type or scope.model_system,
            }
        )
        add_node(nodes, study_design_node(bundle, study_design, scope, anchors))
        _add_record_support_links(
            links,
            nodes=nodes,
            bundle=bundle,
            record_node_id=study_design.design_id,
            source_record_type="study_design",
            source_record_id=study_design.design_id,
            evidence_anchor_ids=study_design.evidence_anchor_ids,
            anchors=anchors,
            context=scope,
            validation_status=study_design.validation_status,
            confidence=None,
            review_status="accepted_for_evidence_graph"
            if study_design.validation_status == "verified"
            else "review_only",
            warnings=(),
        )

    # Keep dangling generated references visible for review when no typed source node exists.
    for simulation_parameter in simulation_parameters:
        if (
            simulation_parameter.linked_observation_id
            and simulation_parameter.linked_observation_id not in parameter_by_source_record
        ):
            _add_unresolved_source_link(
                links,
                bundle=bundle,
                source=simulation_parameter.simulation_parameter_id,
                target=simulation_parameter.linked_observation_id,
                relation="unresolved_observation_reference",
                simulation_parameter=simulation_parameter,
                anchors=anchors,
            )
        if (
            simulation_parameter.linked_equation_id
            and simulation_parameter.linked_equation_id not in equation_by_id
        ):
            _add_unresolved_source_link(
                links,
                bundle=bundle,
                source=simulation_parameter.simulation_parameter_id,
                target=simulation_parameter.linked_equation_id,
                relation="unresolved_equation_reference",
                simulation_parameter=simulation_parameter,
                anchors=anchors,
            )

    return list(links.values())


def _add_record_support_links(
    links: dict[str, EvidenceGraphLink],
    *,
    nodes: dict[str, EvidenceGraphNode],
    bundle: AnnotationBundle,
    record_node_id: str,
    source_record_type: SourceRecordType,
    source_record_id: str,
    evidence_anchor_ids: tuple[str, ...],
    anchors: dict[str, EvidenceAnchor],
    context: ContextScope,
    validation_status: str | None,
    confidence: str | float | None,
    review_status: ReviewStatus,
    warnings: tuple[str, ...],
) -> None:
    for anchor_id in evidence_anchor_ids:
        _add_link(
            links,
            bundle=bundle,
            source=record_node_id,
            target=anchor_id,
            relation="has_evidence",
            source_record_type=source_record_type,
            source_record_id=source_record_id,
            evidence_anchor_ids=(anchor_id,),
            anchors=anchors,
            context=context,
            validation_status=validation_status,
            confidence=confidence,
            review_status=review_status,
            warnings=warnings,
        )
    if context_has_signal(context):
        node = context_node(bundle, source_record_type, source_record_id, context, anchors)
        add_node(nodes, node)
        _add_link(
            links,
            bundle=bundle,
            source=record_node_id,
            target=node.node_id,
            relation="has_context",
            source_record_type=source_record_type,
            source_record_id=source_record_id,
            evidence_anchor_ids=evidence_anchor_ids,
            anchors=anchors,
            context=context,
            validation_status=validation_status,
            confidence=confidence,
            review_status=review_status,
            warnings=warnings,
        )


def _add_unresolved_source_link(
    links: dict[str, EvidenceGraphLink],
    *,
    bundle: AnnotationBundle,
    source: str,
    target: str,
    relation: str,
    simulation_parameter: EvidenceSimulationParameter,
    anchors: dict[str, EvidenceAnchor],
) -> None:
    _add_link(
        links,
        bundle=bundle,
        source=source,
        target=target,
        relation=relation,
        source_record_type="simulation_parameter",
        source_record_id=simulation_parameter.simulation_parameter_id,
        evidence_anchor_ids=simulation_parameter.evidence_anchor_ids,
        anchors=anchors,
        context=simulation_parameter.context,
        validation_status=simulation_parameter.validation_status,
        confidence=None,
        review_status="review_only",
        warnings=(*simulation_parameter.warnings, "unresolved_linked_record"),
    )


def _add_link(
    links: dict[str, EvidenceGraphLink],
    *,
    bundle: AnnotationBundle,
    source: str,
    target: str,
    relation: str,
    source_record_type: SourceRecordType,
    source_record_id: str,
    evidence_anchor_ids: tuple[str, ...],
    anchors: dict[str, EvidenceAnchor],
    context: ContextScope,
    validation_status: str | None,
    confidence: str | float | None,
    review_status: ReviewStatus,
    warnings: tuple[str, ...] = (),
    metadata: dict[str, JsonValue] | None = None,
) -> None:
    provenance = paper_provenance(
        bundle.paper,
        source_record_type,
        source_record_id,
        evidence_anchor_ids,
        anchors,
        validation_status=validation_status,
        trust_level=str(confidence) if confidence is not None else None,
        warnings=warnings,
    )
    generated_link_id = link_id(bundle.paper.paper_id, source, relation, target, source_record_id)
    links.setdefault(
        generated_link_id,
        EvidenceGraphLink(
            link_id=generated_link_id,
            source=source,
            target=target,
            relation=relation,
            paper_id=bundle.paper.paper_id,
            source_record_type=source_record_type,
            source_record_id=source_record_id,
            evidence_anchor_ids=evidence_anchor_ids,
            context=context,
            validation_status=validation_status,
            confidence=confidence,
            review_status=review_status,
            provenance=provenance,
            warnings=warnings,
            metadata={} if metadata is None else metadata,
        ),
    )
