"""Models for raw paper annotation bundles and normalized evidence graphs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from services.domain.base import STRICT_MODEL_CONFIG, JsonValue

TOLERANT_MODEL_CONFIG = ConfigDict(extra="allow", frozen=True)
NORMALIZATION_MATCH_THRESHOLD = 0.9

type JsonDict = dict[str, JsonValue]
type ReviewStatus = Literal[
    "accepted_for_evidence_graph",
    "candidate_for_pathway_patch",
    "review_only",
    "rejected",
]
type ProposalKind = Literal["new_pathway", "overlay", "evidence_only"]
type SourceRecordType = Literal[
    "mechanism_step",
    "mechanism_edge",
    "parameter_candidate",
    "observation",
    "equation",
    "simulation_model",
    "simulation_parameter",
    "simulation_readiness_plan",
    "evidence_anchor",
    "scientific_symbol",
    "study_design",
    "figure_annotation",
    "model_quantity",
    "context_scope",
    "paper",
]


class PaperInfo(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    paper_id: str
    title: str
    source: str | None = None
    extracted_at: str | None = None


class EvidenceAnchor(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    anchor_id: str
    paper_id: str
    source_type: str | None = None
    chunk_id: str | None = None
    section: str | None = None
    quote: str | None = None
    table_id: str | None = None
    row_id: str | None = None
    column_id: str | None = None
    cell_id: str | None = None
    row_header: str | None = None
    column_header: str | None = None
    column_path: tuple[str, ...] = ()
    figure_id: str | None = None
    panel_id: str | None = None
    metadata: JsonDict = Field(default_factory=dict)


class NormalizedEntity(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    normalized_label: str | None = None
    concept_type: str | None = None
    canonical_id: str | None = None
    source_ontology: str | None = None
    match_method: str | None = None
    match_score: float | None = None

    @property
    def is_usable(self) -> bool:
        return (
            self.canonical_id is not None
            and self.normalized_label is not None
            and self.match_score is not None
            and self.match_score >= NORMALIZATION_MATCH_THRESHOLD
        )


class MechanismStep(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    step_id: str
    subject: str
    predicate: str
    object: str
    quote: str | None = None
    evidence_anchor_ids: tuple[str, ...] = ()
    context: JsonDict = Field(default_factory=dict)


class MechanismChain(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    mechanism_chain_id: str
    paper_id: str
    subject: str | None = None
    outcome: str | None = None
    steps: tuple[MechanismStep, ...] = ()


class MechanismVerification(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    verification_id: str
    mechanism_chain_id: str
    mechanism_step_id: str
    paper_id: str
    verdict: str
    relation_class: str | None = None
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    normalized_subject: NormalizedEntity | None = None
    normalized_object: NormalizedEntity | None = None
    evidence_anchor_ids: tuple[str, ...] = ()
    confidence: str | float | None = None
    issues: tuple[str, ...] = ()


class ParameterCandidate(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    candidate_id: str
    paper_id: str
    family: str | None = None
    parameter: str
    value: float | None = None
    value_text: str | None = None
    unit: str | None = None
    subject_hint: str | None = None
    anchor_ids: tuple[str, ...] = ()
    confidence: str | float | None = None
    warnings: tuple[str, ...] = ()
    context: JsonDict = Field(default_factory=dict)


class ParameterObservation(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    observation_id: str
    paper_id: str
    family: str | None = None
    parameter: str
    value: float | None = None
    value_text: str | None = None
    unit: str | None = None
    subject: str | None = None
    source_candidate_id: str | None = None
    evidence_anchor_ids: tuple[str, ...] = ()
    validation_status: str | None = None
    validation_warnings: tuple[str, ...] = ()
    trust_level: str | None = None
    context: JsonDict = Field(default_factory=dict)


class EquationVariable(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    symbol: str
    meaning: str | None = None


class EquationRecord(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    equation_id: str
    paper_id: str
    model_type: str | None = None
    expression: str
    variables: tuple[EquationVariable, ...] = ()
    evidence_anchor_ids: tuple[str, ...] = ()
    validation_status: str | None = None


class SimulationModelRecord(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    simulation_id: str
    paper_id: str
    model_type: str | None = None
    platform: str | None = None
    population: str | None = None
    scenario: str | None = None
    analytes: tuple[str, ...] = ()
    compartments: tuple[str, ...] = ()
    validation_metric: str | None = None
    evidence_anchor_ids: tuple[str, ...] = ()
    validation_status: str | None = None
    context: JsonDict = Field(default_factory=dict)


class SimulationParameterRecord(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    simulation_parameter_id: str
    paper_id: str
    parameter_name: str
    family: str | None = None
    role: str
    value: float | None = None
    value_text: str | None = None
    unit: str | None = None
    source_type: str | None = None
    provenance_status: str | None = None
    required_for: str | None = None
    linked_observation_id: str | None = None
    linked_equation_id: str | None = None
    linked_figure_annotation_id: str | None = None
    evidence_anchor_ids: tuple[str, ...] = ()
    validation_status: str | None = None
    context: JsonDict = Field(default_factory=dict)


class SimulationReadinessPlan(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    plan_id: str
    paper_id: str
    model_goal: str | None = None
    model_type: str | None = None
    readiness_status: str | None = None
    readiness_score: float | None = None
    simulation_decision: str | None = None
    decision_reason: str | None = None
    missing_inputs: tuple[JsonDict, ...] = ()
    assumptions_needed: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()
    evidence_anchor_ids: tuple[str, ...] = ()
    validation_status: str | None = None
    context: JsonDict = Field(default_factory=dict)


class ScientificSymbolRecord(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    symbol_id: str
    paper_id: str
    raw_symbol: str
    normalized_symbol: str | None = None
    unicode_symbol: str | None = None
    latex_symbol: str | None = None
    base_symbol: str | None = None
    semantic_role: str | None = None
    analyte: str | None = None
    parent_analyte: str | None = None
    interpretation_confidence: str | float | None = None
    evidence_anchor_ids: tuple[str, ...] = ()
    source_observation_id: str | None = None
    scope: JsonDict = Field(default_factory=dict)


class StudyDesignRecord(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    design_id: str
    paper_id: str
    study_type: str | None = None
    phase: str | None = None
    species: str | None = None
    population: str | None = None
    sample_size: int | None = None
    arms: tuple[JsonDict, ...] = ()
    dosing: str | None = None
    route: str | None = None
    duration: str | None = None
    endpoints: tuple[str, ...] = ()
    evidence_anchor_ids: tuple[str, ...] = ()
    validation_status: str | None = None
    context: JsonDict = Field(default_factory=dict)


class FigureAnnotationRecord(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    figure_annotation_id: str
    paper_id: str
    figure_id: str | None = None
    figure_label: str | None = None
    caption: str | None = None
    source_url: str | None = None
    image_asset_status: str | None = None
    image_analysis_status: str | None = None
    visual_evidence_types: tuple[str, ...] = ()
    panels: tuple[JsonDict, ...] = ()
    extracted_numeric_mentions: tuple[JsonDict, ...] = ()
    evidence_anchor_ids: tuple[str, ...] = ()
    validation_status: str | None = None
    context: JsonDict = Field(default_factory=dict)


class AnnotationBundle(BaseModel):
    model_config = TOLERANT_MODEL_CONFIG

    paper: PaperInfo
    evidence_anchors: tuple[EvidenceAnchor, ...] = ()
    parameter_candidates: tuple[ParameterCandidate, ...] = ()
    observations: tuple[ParameterObservation, ...] = ()
    mechanism_chains: tuple[MechanismChain, ...] = ()
    mechanism_verifications: tuple[MechanismVerification, ...] = ()
    equations: tuple[EquationRecord, ...] = ()
    simulation_models: tuple[SimulationModelRecord, ...] = ()
    simulation_parameters: tuple[SimulationParameterRecord, ...] = ()
    simulation_readiness_plans: tuple[SimulationReadinessPlan, ...] = ()
    scientific_symbols: tuple[ScientificSymbolRecord, ...] = ()
    study_designs: tuple[StudyDesignRecord, ...] = ()
    figure_annotations: tuple[FigureAnnotationRecord, ...] = ()
    kg_projection: JsonDict = Field(default_factory=dict)
    summary: JsonDict = Field(default_factory=dict)

    @model_validator(mode="after")
    def paper_ids_are_consistent(self) -> AnnotationBundle:
        for collection in (
            self.evidence_anchors,
            self.parameter_candidates,
            self.observations,
            self.mechanism_chains,
            self.mechanism_verifications,
            self.equations,
            self.simulation_models,
            self.simulation_parameters,
            self.simulation_readiness_plans,
            self.scientific_symbols,
            self.study_designs,
            self.figure_annotations,
        ):
            for item in collection:
                if item.paper_id != self.paper.paper_id:
                    raise ValueError(
                        f"Record for {item.paper_id!r} does not match paper {self.paper.paper_id!r}"
                    )
        return self


class ContextScope(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    species: str | None = None
    translation_stage: str | None = None
    disease: str | None = None
    disease_subtype: str | None = None
    state: str | None = None
    assay: str | None = None
    matrix: str | None = None
    tissue_or_organ: str | None = None
    cell_line: str | None = None
    model_system: str | None = None
    drug_or_analyte: str | None = None
    source_section: str | None = None
    source_anchor_ids: tuple[str, ...] = ()


class PaperProvenance(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    paper_id: str
    paper_title: str
    source_record_type: SourceRecordType
    source_record_id: str
    evidence_anchor_ids: tuple[str, ...] = ()
    source_section: str | None = None
    source_chunk_id: str | None = None
    source_table_or_figure: str | None = None
    quote_or_sentence: str | None = None
    simulation_model_id: str | None = None
    simulation_parameter_id: str | None = None
    verification_id: str | None = None
    verification_verdict: str | None = None
    relation_class: str | None = None
    validation_status: str | None = None
    trust_level: str | None = None
    warnings: tuple[str, ...] = ()


class WarningRecord(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"
    source_record_type: str | None = None
    source_record_id: str | None = None


class EvidenceGraphNode(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    node_id: str
    label: str
    node_type: str
    paper_id: str
    source_record_type: SourceRecordType
    source_record_id: str
    evidence_anchor_ids: tuple[str, ...] = ()
    context: ContextScope = Field(default_factory=ContextScope)
    validation_status: str | None = None
    confidence: str | float | None = None
    review_status: ReviewStatus
    provenance: PaperProvenance
    metadata: JsonDict = Field(default_factory=dict)


class EvidenceGraphEdge(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    edge_id: str
    source: str
    target: str
    relation: str
    predicate: str
    paper_id: str
    source_record_type: Literal["mechanism_step"] = "mechanism_step"
    source_record_id: str
    evidence_anchor_ids: tuple[str, ...] = ()
    context: ContextScope = Field(default_factory=ContextScope)
    verification_id: str | None = None
    verification_verdict: str | None = None
    relation_class: str | None = None
    validation_status: str | None = None
    confidence: str | float | None = None
    review_status: ReviewStatus
    provenance: PaperProvenance
    warnings: tuple[str, ...] = ()
    metadata: JsonDict = Field(default_factory=dict)


class EvidenceGraphLink(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    link_id: str
    source: str
    target: str
    relation: str
    paper_id: str
    source_record_type: SourceRecordType
    source_record_id: str
    evidence_anchor_ids: tuple[str, ...] = ()
    context: ContextScope = Field(default_factory=ContextScope)
    validation_status: str | None = None
    confidence: str | float | None = None
    review_status: ReviewStatus
    provenance: PaperProvenance
    warnings: tuple[str, ...] = ()
    metadata: JsonDict = Field(default_factory=dict)


class EvidenceParameter(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    parameter_id: str
    paper_id: str
    source_record_type: Literal["parameter_candidate", "observation"]
    source_record_id: str
    name: str
    family: str | None = None
    value: float | None = None
    value_text: str | None = None
    unit: str | None = None
    subject: str | None = None
    evidence_anchor_ids: tuple[str, ...] = ()
    context: ContextScope = Field(default_factory=ContextScope)
    validation_status: str | None = None
    confidence: str | float | None = None
    review_status: ReviewStatus
    provenance: PaperProvenance
    warnings: tuple[str, ...] = ()
    metadata: JsonDict = Field(default_factory=dict)


class EvidenceEquation(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    equation_id: str
    paper_id: str
    expression_text: str
    variables: tuple[EquationVariable, ...] = ()
    model_type: str | None = None
    evidence_anchor_ids: tuple[str, ...] = ()
    context: ContextScope = Field(default_factory=ContextScope)
    validation_status: str | None = None
    review_status: ReviewStatus
    provenance: PaperProvenance
    metadata: JsonDict = Field(default_factory=dict)


class EvidenceSimulationModel(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    simulation_model_id: str
    paper_id: str
    model_type: str | None = None
    platform: str | None = None
    population: str | None = None
    scenario: str | None = None
    analytes: tuple[str, ...] = ()
    compartments: tuple[str, ...] = ()
    evidence_anchor_ids: tuple[str, ...] = ()
    context: ContextScope = Field(default_factory=ContextScope)
    validation_status: str | None = None
    review_status: ReviewStatus
    provenance: PaperProvenance
    metadata: JsonDict = Field(default_factory=dict)


class EvidenceSimulationParameter(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    simulation_parameter_id: str
    paper_id: str
    parameter_name: str
    family: str | None = None
    role: str
    value: float | None = None
    value_text: str | None = None
    unit: str | None = None
    source_type: str | None = None
    provenance_status: str | None = None
    required_for: str | None = None
    linked_observation_id: str | None = None
    linked_equation_id: str | None = None
    linked_figure_annotation_id: str | None = None
    evidence_anchor_ids: tuple[str, ...] = ()
    context: ContextScope = Field(default_factory=ContextScope)
    validation_status: str | None = None
    review_status: ReviewStatus
    provenance: PaperProvenance
    warnings: tuple[str, ...] = ()
    metadata: JsonDict = Field(default_factory=dict)


class PaperEvidenceGraph(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    paper_id: str
    title: str
    source: str | None = None
    nodes: tuple[EvidenceGraphNode, ...] = ()
    edges: tuple[EvidenceGraphEdge, ...] = ()
    links: tuple[EvidenceGraphLink, ...] = ()
    parameters: tuple[EvidenceParameter, ...] = ()
    equations: tuple[EvidenceEquation, ...] = ()
    simulation_models: tuple[EvidenceSimulationModel, ...] = ()
    simulation_parameters: tuple[EvidenceSimulationParameter, ...] = ()
    evidence_anchors: tuple[EvidenceAnchor, ...] = ()
    warnings: tuple[WarningRecord, ...] = ()
    summary: JsonDict = Field(default_factory=dict)


class ProposedNode(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    node_id: str
    label: str
    node_type: str
    source_evidence_ids: tuple[str, ...] = ()
    review_status: ReviewStatus
    reason: str
    evidence_anchor_ids: tuple[str, ...] = ()
    context: ContextScope = Field(default_factory=ContextScope)
    provenance: PaperProvenance | None = None
    warnings: tuple[str, ...] = ()
    metadata: JsonDict = Field(default_factory=dict)


class ProposedEdge(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    edge_id: str
    source: str
    target: str
    relation: str
    source_evidence_id: str
    verification_verdict: str | None = None
    review_status: ReviewStatus
    reason: str
    evidence_anchor_ids: tuple[str, ...] = ()
    context: ContextScope = Field(default_factory=ContextScope)
    provenance: PaperProvenance | None = None
    warnings: tuple[str, ...] = ()
    metadata: JsonDict = Field(default_factory=dict)


class ProposedParameter(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    parameter_id: str
    name: str
    role: str
    source_evidence_id: str
    value: float | None = None
    unit: str | None = None
    review_status: ReviewStatus
    reason: str
    evidence_anchor_ids: tuple[str, ...] = ()
    context: ContextScope = Field(default_factory=ContextScope)
    provenance: PaperProvenance | None = None
    warnings: tuple[str, ...] = ()
    metadata: JsonDict = Field(default_factory=dict)


class ProposedEquation(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    equation_id: str
    expression_text: str
    source_evidence_id: str
    review_status: ReviewStatus
    reason: str
    evidence_anchor_ids: tuple[str, ...] = ()
    context: ContextScope = Field(default_factory=ContextScope)
    provenance: PaperProvenance | None = None
    metadata: JsonDict = Field(default_factory=dict)


class MissingInput(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    name: str
    reason: str
    severity: str | None = None


class PathwayProposal(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    proposal_id: str
    paper_id: str
    title: str
    proposal_kind: ProposalKind
    target_pathway_id: str | None = None
    proposed_pathway_id: str | None = None
    proposed_nodes: tuple[ProposedNode, ...] = ()
    proposed_edges: tuple[ProposedEdge, ...] = ()
    proposed_parameters: tuple[ProposedParameter, ...] = ()
    proposed_equations: tuple[ProposedEquation, ...] = ()
    required_missing_inputs: tuple[MissingInput, ...] = ()
    provenance_warnings: tuple[WarningRecord, ...] = ()
    executable: bool = False
    promotion_note: str = "Review artifact only; not loaded by pathway runtime."


class TermRule(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    value: str
    terms: tuple[str, ...]


class ContextExtractionRules(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    species: tuple[TermRule, ...] = ()
    translation_stage: tuple[TermRule, ...] = ()
    model_system: tuple[TermRule, ...] = ()
    disease: tuple[TermRule, ...] = ()
    disease_subtype: tuple[TermRule, ...] = ()
    state: tuple[TermRule, ...] = ()


class OverlayNodeRule(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    node_id: str
    label: str
    node_type: str = "model_quantity"
    match_terms: tuple[str, ...]
    max_source_evidence_ids: int = Field(default=20, ge=1)
    review_status: ReviewStatus = "review_only"
    reason: str


class AnnotationProposalRule(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    paper_id: str
    proposal_kind: ProposalKind
    target_pathway_id: str | None = None
    proposed_pathway_id: str | None = None
    overlay_nodes: tuple[OverlayNodeRule, ...] = ()
