"""Compose executable graphs from pathway definitions."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import cast

from services.domain import (
    DrugEffectId,
    Edge,
    EdgeId,
    EdgeMetadata,
    Evidence,
    EvidenceSourceType,
    GraphId,
    GraphMetadata,
    MoAGraph,
    ModuleId,
    Node,
    NodeId,
    RelationId,
    Sign,
    StateId,
    relation_default_sign,
)
from services.domain._validation import duplicate_items
from services.domain.base import JsonValue
from services.domain.vocabulary import WarningCategory, WarningSeverity
from services.domain.warnings import ModelWarning

from .loader import load_pathway
from .models import (
    AdHocEdgeModifier,
    DisplayOption,
    DrugEffectPatch,
    GraphComposeRequest,
    PathwayContract,
    PathwayDefinition,
)

_ID_SAFE = re.compile(r"[^A-Za-z0-9_.:-]+")


def _warning(message: str, *, details: dict[str, JsonValue] | None = None) -> ModelWarning:
    return ModelWarning(
        category=WarningCategory.OTHER,
        severity=WarningSeverity.WARNING,
        message=message,
        details={} if details is None else details,
    )


def _drug_node_id(nodes: tuple[Node, ...]) -> NodeId:
    for node in nodes:
        if "drug" in node.roles:
            return node.id
    for node in nodes:
        if str(node.type) == "perturbation":
            return node.id
    raise ValueError("Composed graph must contain a drug/perturbation node before adding drug effects")


def _drug_state(nodes: tuple[Node, ...]) -> StateId | None:
    drug = _drug_node_id(nodes)
    node = next(item for item in nodes if item.id == drug)
    return None if node.state is None else node.state.id


def _merge_unique_nodes(items: list[Node], additions: tuple[Node, ...]) -> None:
    existing = {node.id for node in items}
    overlap = [node.id for node in additions if node.id in existing]
    if overlap:
        raise ValueError(f"Duplicate node ids while composing graph: {overlap}")
    items.extend(additions)


def _merge_unique_edges(items: list[Edge], additions: tuple[Edge, ...]) -> None:
    existing = {edge.id for edge in items}
    overlap = [edge.id for edge in additions if edge.id in existing]
    if overlap:
        raise ValueError(f"Duplicate edge ids while composing graph: {overlap}")
    items.extend(additions)


def _edge_metadata(
    template: str | None,
    parameters: Mapping[str, object],
    extra: Mapping[str, JsonValue],
) -> EdgeMetadata:
    extension: dict[str, JsonValue] = {}
    if template is not None:
        extension["modifier_template"] = template
    if parameters:
        extension["parameters"] = {key: str(value) for key, value in parameters.items()}
    extension.update(extra)
    return EdgeMetadata(extension=extension)


def _edge_from_effect_patch(patch: DrugEffectPatch, effect_label: str) -> Edge:
    return Edge(
        id=patch.id,
        source=patch.source_node,
        target=patch.target_edge,
        relation=patch.relation,
        sign=patch.sign,
        confidence=patch.confidence,
        evidence=(
            Evidence(
                source_type=EvidenceSourceType.CURATED_ASSUMPTION,
                source_label=effect_label,
                description=patch.rationale,
                confidence=patch.confidence,
            ),
        ),
        operator=None,
        expression=patch.expression,
        is_hypothesis=True,
        hypothesis_rationale=patch.rationale,
        metadata=_edge_metadata(patch.modifier_template, dict(patch.parameters), patch.metadata),
    )


def _safe_modifier_edge_id(source: NodeId, relation: RelationId, target: EdgeId) -> EdgeId:
    raw = f"e_{source}_{relation}_{target}"
    return EdgeId(_ID_SAFE.sub("_", raw))


def _edge_from_ad_hoc(patch: AdHocEdgeModifier, source_node: NodeId) -> Edge:
    sign = patch.sign if patch.sign is not None else relation_default_sign(str(patch.relation))
    if sign == Sign.UNKNOWN:
        raise ValueError(f"Ad hoc modifier relation {patch.relation!r} needs an explicit sign")
    edge_id = patch.edge_id or _safe_modifier_edge_id(source_node, patch.relation, patch.target_edge)
    return Edge(
        id=edge_id,
        source=patch.source_node or source_node,
        target=patch.target_edge,
        relation=patch.relation,
        sign=sign,
        confidence=patch.confidence,
        evidence=(
            Evidence(
                source_type=EvidenceSourceType.CLAIM,
                source_label="ad_hoc_modifier",
                description=patch.rationale,
                confidence=patch.confidence,
            ),
        ),
        expression=patch.expression,
        is_hypothesis=True,
        hypothesis_rationale=patch.rationale,
        metadata=_edge_metadata(None, dict(patch.parameters), patch.metadata),
    )


def _configuration_modules(
    pathway: PathwayDefinition,
    request: GraphComposeRequest,
) -> tuple[str | None, set[ModuleId], list[DrugEffectId]]:
    modules = {module.id for module in pathway.modules.values() if module.default_included}
    drug_effects: list[DrugEffectId] = []
    selected_configuration: str | None = None
    if request.configuration is not None:
        configuration = pathway.configurations.get(request.configuration)
        if configuration is None:
            raise ValueError(
                f"Unknown configuration {request.configuration!r} for pathway {pathway.pathway_id}"
            )
        selected_configuration = configuration.id
        modules.update(configuration.include_modules)
        modules.difference_update(configuration.exclude_modules)
        drug_effects.extend(configuration.drug_effects)

    modules.update(request.include_modules)
    modules.difference_update(request.exclude_modules)
    drug_effects.extend(request.drug_effects)
    return selected_configuration, modules, drug_effects


def compose_graph(request: GraphComposeRequest) -> MoAGraph:
    pathway = load_pathway(request.pathway_id)
    selected_configuration, module_ids, drug_effect_ids = _configuration_modules(pathway, request)

    nodes = list(pathway.base_graph.nodes)
    edges = list(pathway.base_graph.edges)
    logic_checks: list[dict[str, JsonValue]] = list(pathway.logic_checks)
    homeostasis_marker: list[str] = []
    for module_id in sorted(module_ids, key=str):
        module = pathway.modules.get(module_id)
        if module is None:
            raise ValueError(f"Unknown module {module_id!r} for pathway {pathway.pathway_id}")
        _merge_unique_nodes(nodes, module.nodes)
        _merge_unique_edges(edges, module.edges)
        logic_checks.extend(module.logic_checks)
        homeostasis_marker.extend(str(term.term_id) for term in module.homeostasis)

    source_node = _drug_node_id(tuple(nodes))
    for effect_id in drug_effect_ids:
        effect = pathway.drug_effects.get(effect_id)
        if effect is None:
            raise ValueError(f"Unknown drug effect {effect_id!r} for pathway {pathway.pathway_id}")
        _merge_unique_edges(
            edges,
            tuple(_edge_from_effect_patch(patch, effect.label) for patch in effect.patches),
        )
    _merge_unique_edges(
        edges, tuple(_edge_from_ad_hoc(patch, source_node) for patch in request.ad_hoc_modifiers)
    )

    duplicate_effects = duplicate_items(drug_effect_ids)
    if duplicate_effects:
        raise ValueError(f"Duplicate drug effects in compose request: {list(duplicate_effects)}")

    graph_suffix = selected_configuration or "custom"
    metadata = GraphMetadata(
        pathway_id=pathway.pathway_id,
        configuration=selected_configuration,
        included_modules=tuple(str(module) for module in sorted(module_ids, key=str)),
        drug_effects=tuple(str(effect) for effect in drug_effect_ids),
        operations=tuple(homeostasis_marker),
        drug_state=_drug_state(tuple(nodes)),
        endpoint_states=pathway.presentation.endpoint_states,
        extension={"logic_checks": cast(JsonValue, logic_checks)},
    )
    return MoAGraph(
        graph_id=GraphId(f"{pathway.pathway_id}_{graph_suffix}"),
        label=pathway.configurations[selected_configuration].label
        if selected_configuration
        else f"{pathway.label} custom graph",
        context=pathway.context,
        nodes=tuple(nodes),
        edges=tuple(edges),
        source_claim=request.source_claim,
        version=pathway.version,
        metadata=metadata,
    )


def contract_for_pathway(pathway: PathwayDefinition) -> PathwayContract:
    modifier_labels = {
        "activates_edge": "Activates edge",
        "inhibits_edge": "Inhibits edge",
    }
    return PathwayContract(
        pathway_id=pathway.pathway_id,
        label=pathway.label,
        configurations=tuple(
            DisplayOption(value=str(item.id), label=item.label) for item in pathway.configurations.values()
        ),
        modules=tuple(
            DisplayOption(value=str(item.id), label=item.label) for item in pathway.modules.values()
        ),
        default_modules=tuple(module.id for module in pathway.modules.values() if module.default_included),
        drug_effects=tuple(
            DisplayOption(value=str(item.id), label=item.label) for item in pathway.drug_effects.values()
        ),
        modifier_relations=tuple(
            DisplayOption(value=str(relation), label=modifier_labels.get(str(relation), str(relation)))
            for relation in pathway.prediction.allowed_modifier_relations
        ),
        prediction_claims=tuple(
            DisplayOption(value=case.claim, label=case.claim.removeprefix("Compound "))
            for case in pathway.prediction.training_cases
        ),
        presentation=pathway.presentation,
        warnings=(
            _warning(
                "Pathway contract is data-defined; unsupported graph operations should be rejected at composition or compile time."
            ),
        ),
    )
