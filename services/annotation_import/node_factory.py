"""Factory helpers for evidence graph nodes."""

from __future__ import annotations

from services.annotation_import.graph_ids import anchor_label, context_node_id, quantity_node_id
from services.annotation_import.models import (
    AnnotationBundle,
    ContextScope,
    EvidenceAnchor,
    EvidenceEquation,
    EvidenceGraphEdge,
    EvidenceGraphNode,
    EvidenceParameter,
    EvidenceSimulationModel,
    EvidenceSimulationParameter,
    FigureAnnotationRecord,
    ReviewStatus,
    ScientificSymbolRecord,
    SourceRecordType,
    StudyDesignRecord,
)
from services.annotation_import.provenance import context_scope, paper_provenance


def evidence_anchor_node(
    bundle: AnnotationBundle,
    anchor: EvidenceAnchor,
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceGraphNode:
    scope = context_scope({}, (anchor.anchor_id,), anchors, anchor.quote)
    provenance = paper_provenance(
        bundle.paper,
        "evidence_anchor",
        anchor.anchor_id,
        (anchor.anchor_id,),
        anchors,
        quote_or_sentence=anchor.quote,
        validation_status=anchor.source_type,
    )
    return EvidenceGraphNode(
        node_id=anchor.anchor_id,
        label=anchor_label(anchor),
        node_type="evidence_anchor",
        paper_id=bundle.paper.paper_id,
        source_record_type="evidence_anchor",
        source_record_id=anchor.anchor_id,
        evidence_anchor_ids=(anchor.anchor_id,),
        context=scope,
        validation_status=anchor.source_type,
        confidence=None,
        review_status="accepted_for_evidence_graph",
        provenance=provenance,
        metadata={
            "source_type": anchor.source_type,
            "chunk_id": anchor.chunk_id,
            "table_id": anchor.table_id,
            "figure_id": anchor.figure_id,
            "panel_id": anchor.panel_id,
            "row_id": anchor.row_id,
            "column_id": anchor.column_id,
            "cell_id": anchor.cell_id,
        },
    )


def mechanism_edge_node(
    bundle: AnnotationBundle,
    edge: EvidenceGraphEdge,
    nodes: dict[str, EvidenceGraphNode],
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceGraphNode:
    source_node = nodes.get(edge.source)
    target_node = nodes.get(edge.target)
    source_label = source_node.label if source_node is not None else edge.source
    target_label = target_node.label if target_node is not None else edge.target
    provenance = paper_provenance(
        bundle.paper,
        "mechanism_edge",
        edge.source_record_id,
        edge.evidence_anchor_ids,
        anchors,
        quote_or_sentence=edge.provenance.quote_or_sentence,
        verification_id=edge.verification_id,
        verification_verdict=edge.verification_verdict,
        relation_class=edge.relation_class,
        validation_status=edge.validation_status,
        trust_level=str(edge.confidence) if edge.confidence is not None else None,
        warnings=edge.warnings,
    )
    return EvidenceGraphNode(
        node_id=edge.edge_id,
        label=f"{source_label} {edge.relation} {target_label}",
        node_type="mechanism_edge",
        paper_id=bundle.paper.paper_id,
        source_record_type="mechanism_edge",
        source_record_id=edge.source_record_id,
        evidence_anchor_ids=edge.evidence_anchor_ids,
        context=edge.context,
        validation_status=edge.validation_status,
        confidence=edge.confidence,
        review_status=edge.review_status,
        provenance=provenance,
        metadata={
            "source": edge.source,
            "target": edge.target,
            "relation": edge.relation,
            "predicate": edge.predicate,
            "relation_class": edge.relation_class,
            "verification_id": edge.verification_id,
            "verification_verdict": edge.verification_verdict,
            "executable": False,
        },
    )


def parameter_node(parameter: EvidenceParameter) -> EvidenceGraphNode:
    return EvidenceGraphNode(
        node_id=parameter.parameter_id,
        label=parameter.name,
        node_type=f"{parameter.family or 'unknown'}_parameter",
        paper_id=parameter.paper_id,
        source_record_type=parameter.source_record_type,
        source_record_id=parameter.source_record_id,
        evidence_anchor_ids=parameter.evidence_anchor_ids,
        context=parameter.context,
        validation_status=parameter.validation_status,
        confidence=parameter.confidence,
        review_status=parameter.review_status,
        provenance=parameter.provenance,
        metadata={
            **parameter.metadata,
            "family": parameter.family,
            "subject": parameter.subject,
            "value": parameter.value,
            "value_text": parameter.value_text,
            "unit": parameter.unit,
        },
    )


def equation_node(equation: EvidenceEquation) -> EvidenceGraphNode:
    return EvidenceGraphNode(
        node_id=equation.equation_id,
        label=equation.expression_text,
        node_type="equation",
        paper_id=equation.paper_id,
        source_record_type="equation",
        source_record_id=equation.equation_id,
        evidence_anchor_ids=equation.evidence_anchor_ids,
        context=equation.context,
        validation_status=equation.validation_status,
        confidence=None,
        review_status=equation.review_status,
        provenance=equation.provenance,
        metadata={**equation.metadata, "model_type": equation.model_type},
    )


def simulation_model_node(model: EvidenceSimulationModel) -> EvidenceGraphNode:
    return EvidenceGraphNode(
        node_id=model.simulation_model_id,
        label=model.model_type or model.simulation_model_id,
        node_type="simulation_model",
        paper_id=model.paper_id,
        source_record_type="simulation_model",
        source_record_id=model.simulation_model_id,
        evidence_anchor_ids=model.evidence_anchor_ids,
        context=model.context,
        validation_status=model.validation_status,
        confidence=None,
        review_status=model.review_status,
        provenance=model.provenance,
        metadata={
            **model.metadata,
            "platform": model.platform,
            "population": model.population,
            "scenario": model.scenario,
            "analytes": list(model.analytes),
            "compartments": list(model.compartments),
        },
    )


def simulation_parameter_node(parameter: EvidenceSimulationParameter) -> EvidenceGraphNode:
    return EvidenceGraphNode(
        node_id=parameter.simulation_parameter_id,
        label=parameter.parameter_name,
        node_type="simulation_parameter",
        paper_id=parameter.paper_id,
        source_record_type="simulation_parameter",
        source_record_id=parameter.simulation_parameter_id,
        evidence_anchor_ids=parameter.evidence_anchor_ids,
        context=parameter.context,
        validation_status=parameter.validation_status,
        confidence=None,
        review_status=parameter.review_status,
        provenance=parameter.provenance,
        metadata={
            **parameter.metadata,
            "family": parameter.family,
            "role": parameter.role,
            "value": parameter.value,
            "value_text": parameter.value_text,
            "unit": parameter.unit,
            "source_type": parameter.source_type,
            "provenance_status": parameter.provenance_status,
            "required_for": parameter.required_for,
            "linked_observation_id": parameter.linked_observation_id,
            "linked_equation_id": parameter.linked_equation_id,
            "linked_figure_annotation_id": parameter.linked_figure_annotation_id,
        },
    )


def figure_annotation_node(
    bundle: AnnotationBundle,
    figure: FigureAnnotationRecord,
    scope: ContextScope,
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceGraphNode:
    review_status: ReviewStatus = (
        "accepted_for_evidence_graph" if figure.validation_status == "verified" else "review_only"
    )
    provenance = paper_provenance(
        bundle.paper,
        "figure_annotation",
        figure.figure_annotation_id,
        figure.evidence_anchor_ids,
        anchors,
        quote_or_sentence=figure.caption,
        validation_status=figure.validation_status,
    )
    return EvidenceGraphNode(
        node_id=figure.figure_annotation_id,
        label=figure.figure_label or figure.figure_id or figure.figure_annotation_id,
        node_type="figure_annotation",
        paper_id=bundle.paper.paper_id,
        source_record_type="figure_annotation",
        source_record_id=figure.figure_annotation_id,
        evidence_anchor_ids=figure.evidence_anchor_ids,
        context=scope,
        validation_status=figure.validation_status,
        confidence=None,
        review_status=review_status,
        provenance=provenance,
        metadata={
            "figure_id": figure.figure_id,
            "source_url": figure.source_url,
            "image_asset_status": figure.image_asset_status,
            "image_analysis_status": figure.image_analysis_status,
            "visual_evidence_types": list(figure.visual_evidence_types),
            "extracted_numeric_mention_count": len(figure.extracted_numeric_mentions),
        },
    )


def scientific_symbol_node(
    bundle: AnnotationBundle,
    symbol: ScientificSymbolRecord,
    scope: ContextScope,
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceGraphNode:
    provenance = paper_provenance(
        bundle.paper,
        "scientific_symbol",
        symbol.symbol_id,
        symbol.evidence_anchor_ids,
        anchors,
        quote_or_sentence=symbol.raw_symbol,
        trust_level=str(symbol.interpretation_confidence)
        if symbol.interpretation_confidence is not None
        else None,
    )
    return EvidenceGraphNode(
        node_id=symbol.symbol_id,
        label=symbol.normalized_symbol or symbol.raw_symbol,
        node_type="scientific_symbol",
        paper_id=bundle.paper.paper_id,
        source_record_type="scientific_symbol",
        source_record_id=symbol.symbol_id,
        evidence_anchor_ids=symbol.evidence_anchor_ids,
        context=scope,
        validation_status=None,
        confidence=symbol.interpretation_confidence,
        review_status="accepted_for_evidence_graph",
        provenance=provenance,
        metadata={
            "raw_symbol": symbol.raw_symbol,
            "unicode_symbol": symbol.unicode_symbol,
            "latex_symbol": symbol.latex_symbol,
            "base_symbol": symbol.base_symbol,
            "semantic_role": symbol.semantic_role,
            "analyte": symbol.analyte,
            "parent_analyte": symbol.parent_analyte,
            "source_observation_id": symbol.source_observation_id,
        },
    )


def study_design_node(
    bundle: AnnotationBundle,
    study_design: StudyDesignRecord,
    scope: ContextScope,
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceGraphNode:
    review_status: ReviewStatus = (
        "accepted_for_evidence_graph" if study_design.validation_status == "verified" else "review_only"
    )
    provenance = paper_provenance(
        bundle.paper,
        "study_design",
        study_design.design_id,
        study_design.evidence_anchor_ids,
        anchors,
        validation_status=study_design.validation_status,
    )
    label_parts = tuple(
        part
        for part in (
            study_design.study_type,
            study_design.phase,
            study_design.species,
            ", ".join(study_design.endpoints) if study_design.endpoints else None,
        )
        if part
    )
    return EvidenceGraphNode(
        node_id=study_design.design_id,
        label=" / ".join(label_parts) or study_design.design_id,
        node_type="study_design",
        paper_id=bundle.paper.paper_id,
        source_record_type="study_design",
        source_record_id=study_design.design_id,
        evidence_anchor_ids=study_design.evidence_anchor_ids,
        context=scope,
        validation_status=study_design.validation_status,
        confidence=None,
        review_status=review_status,
        provenance=provenance,
        metadata={
            "study_type": study_design.study_type,
            "phase": study_design.phase,
            "species": study_design.species,
            "population": study_design.population,
            "sample_size": study_design.sample_size,
            "dosing": study_design.dosing,
            "route": study_design.route,
            "duration": study_design.duration,
            "endpoints": list(study_design.endpoints),
        },
    )


def quantity_node_for_record(
    *,
    bundle: AnnotationBundle,
    label: str,
    family: str | None,
    role: str | None,
    evidence_anchor_ids: tuple[str, ...],
    context: ContextScope,
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceGraphNode:
    node_id = quantity_node_id(bundle.paper.paper_id, label)
    provenance = paper_provenance(
        bundle.paper,
        "model_quantity",
        node_id,
        evidence_anchor_ids,
        anchors,
        quote_or_sentence=label,
    )
    return EvidenceGraphNode(
        node_id=node_id,
        label=label,
        node_type="model_quantity",
        paper_id=bundle.paper.paper_id,
        source_record_type="model_quantity",
        source_record_id=node_id,
        evidence_anchor_ids=evidence_anchor_ids,
        context=context,
        validation_status=None,
        confidence=None,
        review_status="accepted_for_evidence_graph",
        provenance=provenance,
        metadata={"family": family, "role": role, "executable": False},
    )


def context_node(
    bundle: AnnotationBundle,
    source_record_type: SourceRecordType,
    source_record_id: str,
    context: ContextScope,
    anchors: dict[str, EvidenceAnchor],
) -> EvidenceGraphNode:
    node_id = context_node_id(bundle.paper.paper_id, context)
    provenance = paper_provenance(
        bundle.paper,
        source_record_type,
        source_record_id,
        context.source_anchor_ids,
        anchors,
    )
    return EvidenceGraphNode(
        node_id=node_id,
        label=context_label(context),
        node_type="context_scope",
        paper_id=bundle.paper.paper_id,
        source_record_type="context_scope",
        source_record_id=node_id,
        evidence_anchor_ids=context.source_anchor_ids,
        context=context,
        validation_status="extracted",
        confidence=None,
        review_status="accepted_for_evidence_graph",
        provenance=provenance,
        metadata=context.model_dump(mode="json"),
    )


def add_node(nodes: dict[str, EvidenceGraphNode], node: EvidenceGraphNode) -> None:
    nodes.setdefault(node.node_id, node)


def context_has_signal(context: ContextScope) -> bool:
    payload = context.model_dump(mode="json")
    return any(
        value
        for key, value in payload.items()
        if key not in {"source_anchor_ids", "source_section"} and value is not None
    )


def context_label(context: ContextScope) -> str:
    values = tuple(
        value
        for value in (
            context.species,
            context.translation_stage,
            context.disease,
            context.disease_subtype,
            context.state,
            context.assay,
            context.matrix,
            context.tissue_or_organ,
            context.cell_line,
            context.model_system,
            context.drug_or_analyte,
        )
        if value
    )
    return " | ".join(values) or context.source_section or "context"
