"""Pathway-owned executable schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from services.domain import (
    BiologicalContext,
    DrugEffectId,
    Edge,
    EdgeId,
    GraphId,
    GraphMetadata,
    InitialConditions,
    MoAGraph,
    ModelWarning,
    ModuleId,
    Node,
    NodeId,
    OperatorId,
    ParameterCatalog,
    ParameterId,
    ParameterPrior,
    PathwayId,
    RelationId,
    Sign,
    StateId,
    TermId,
)
from services.domain.base import STRICT_MODEL_CONFIG, JsonValue
from services.domain.expressions import Expression
from services.domain.parameters import GeneratedParameterDefaults


class DisplayOption(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    value: str
    label: str


class GraphFragment(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    graph_id: GraphId
    label: str
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]


class HomeostasisTermDefinition(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    state: StateId
    term_id: TermId
    operator: OperatorId
    sign: Sign
    expression: Expression
    description: str = Field(min_length=1)
    source_edges: tuple[EdgeId, ...] = ()


class PathwayModule(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    id: ModuleId
    label: str
    default_included: bool = False
    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()
    homeostasis: tuple[HomeostasisTermDefinition, ...] = ()
    logic_checks: tuple[dict[str, JsonValue], ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class PathwayConfiguration(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    id: str
    label: str
    include_modules: tuple[ModuleId, ...] = ()
    exclude_modules: tuple[ModuleId, ...] = ()
    drug_effects: tuple[DrugEffectId, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class DrugEffectPatch(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    id: EdgeId
    source_node: NodeId
    target_edge: EdgeId
    relation: RelationId
    sign: Sign
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    modifier_template: str | None = None
    parameters: dict[str, ParameterId] = Field(default_factory=dict)
    expression: Expression | None = None
    rationale: str = Field(default="Pathway-defined drug effect.", min_length=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class DrugEffectDefinition(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    id: DrugEffectId
    label: str
    patches: tuple[DrugEffectPatch, ...]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class AdHocEdgeModifier(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    source_node: NodeId | None = None
    target_edge: EdgeId
    relation: RelationId
    sign: Sign | None = None
    edge_id: EdgeId | None = None
    confidence: float = Field(default=0.65, ge=0.0, le=1.0)
    expression: Expression | None = None
    parameters: dict[str, ParameterId] = Field(default_factory=dict)
    rationale: str = "User-defined edge modifier."
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ParameterBlock(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    priors: dict[ParameterId, ParameterPrior]
    generated_defaults: GeneratedParameterDefaults = Field(default_factory=GeneratedParameterDefaults)

    @model_validator(mode="after")
    def ids_match_keys(self) -> ParameterBlock:
        for key, prior in self.priors.items():
            if prior.id != key:
                raise ValueError(f"Parameter prior key {key!r} does not match prior id {prior.id!r}")
        return self

    def catalog(self) -> ParameterCatalog:
        return ParameterCatalog(priors=self.priors)


class PlotStateStyle(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    state: StateId
    label: str
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


class GraphNodeLayout(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    node: NodeId
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class NodeTypeStyle(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    node_type: str
    fill: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    stroke: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    text: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


class EdgeRelationStyle(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    relation: str
    label: str
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    marker: Literal["arrow", "tee"] = "arrow"


class PresentationDefinition(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    plot_states: tuple[PlotStateStyle, ...] = ()
    graph_layout: tuple[GraphNodeLayout, ...] = ()
    node_type_styles: tuple[NodeTypeStyle, ...] = ()
    edge_relation_styles: tuple[EdgeRelationStyle, ...] = ()
    endpoint_states: tuple[StateId, ...] = ()


class PredictionTrainingCase(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    claim: str
    positives: tuple[dict[str, str], ...]
    keywords: tuple[str, ...] = ()


class PredictionGuardrail(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    id: str
    when_all_keywords: tuple[str, ...] = ()
    when_any_keywords: tuple[str, ...] = ()
    include_modules: tuple[ModuleId, ...] = ()
    recommendations: tuple[dict[str, str], ...]
    rationale: str

    @field_validator("when_all_keywords", "when_any_keywords")
    @classmethod
    def lower_keywords(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(value.lower() for value in values)


class PredictionDefinition(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    enabled: bool = True
    keyword_patterns: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    allowed_modifier_relations: tuple[RelationId, ...] = (RelationId("inhibits_edge"), RelationId("activates_edge"))
    training_cases: tuple[PredictionTrainingCase, ...] = ()
    guardrails: tuple[PredictionGuardrail, ...] = ()


class PathwayDefinition(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    pathway_id: PathwayId
    label: str
    version: str = "1.0"
    context: BiologicalContext = Field(default_factory=BiologicalContext)
    base_graph: GraphFragment
    modules: dict[ModuleId, PathwayModule] = Field(default_factory=dict)
    configurations: dict[str, PathwayConfiguration] = Field(default_factory=dict)
    drug_effects: dict[DrugEffectId, DrugEffectDefinition] = Field(default_factory=dict)
    parameters: ParameterBlock
    initial_conditions: InitialConditions
    homeostasis: tuple[HomeostasisTermDefinition, ...] = ()
    presentation: PresentationDefinition = Field(default_factory=PresentationDefinition)
    prediction: PredictionDefinition = Field(default_factory=PredictionDefinition)
    logic_checks: tuple[dict[str, JsonValue], ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def ids_match_keys(self) -> PathwayDefinition:
        for key, module in self.modules.items():
            if module.id != key:
                raise ValueError(f"Module key {key!r} does not match id {module.id!r}")
        for key, configuration in self.configurations.items():
            if configuration.id != key:
                raise ValueError(f"Configuration key {key!r} does not match id {configuration.id!r}")
        for key, effect in self.drug_effects.items():
            if effect.id != key:
                raise ValueError(f"Drug effect key {key!r} does not match id {effect.id!r}")
        return self

    def empty_graph_metadata(self) -> GraphMetadata:
        return GraphMetadata(
            pathway_id=self.pathway_id,
            endpoint_states=self.presentation.endpoint_states,
        )


class PathwaySummary(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    pathway_id: PathwayId
    label: str
    version: str
    configurations: tuple[DisplayOption, ...]


class GraphComposeRequest(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    pathway_id: PathwayId
    configuration: str | None = None
    include_modules: tuple[ModuleId, ...] = ()
    exclude_modules: tuple[ModuleId, ...] = ()
    drug_effects: tuple[DrugEffectId, ...] = ()
    ad_hoc_modifiers: tuple[AdHocEdgeModifier, ...] = ()
    source_claim: str | None = None


class PathwayContract(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    pathway_id: PathwayId
    label: str
    configurations: tuple[DisplayOption, ...]
    modules: tuple[DisplayOption, ...]
    default_modules: tuple[ModuleId, ...]
    drug_effects: tuple[DisplayOption, ...]
    modifier_relations: tuple[DisplayOption, ...]
    prediction_claims: tuple[DisplayOption, ...] = ()
    presentation: PresentationDefinition
    warnings: tuple[ModelWarning, ...] = ()


def graph_from_fragment(pathway: PathwayDefinition, fragment: GraphFragment, metadata: GraphMetadata) -> MoAGraph:
    return MoAGraph(
        graph_id=fragment.graph_id,
        label=fragment.label,
        context=pathway.context,
        nodes=fragment.nodes,
        edges=fragment.edges,
        metadata=metadata,
        version=pathway.version,
    )
