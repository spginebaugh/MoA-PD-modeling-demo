"""Data-driven graph-to-equation compiler."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping
from typing import Protocol

from services.domain import (
    Add,
    CompiledModel,
    CompiledModelMetadata,
    Constant,
    DisplayExpression,
    Edge,
    EdgeId,
    EquationTerm,
    ExecutableOrDisplayExpression,
    Expression,
    GeneratedParameter,
    MoAGraph,
    ModelWarning,
    ModifierId,
    ModifierTerm,
    ModuleId,
    NodeId,
    OperatorId,
    ParameterCatalog,
    ParameterId,
    RelationId,
    Sign,
    SourceGraphEdge,
    SourceGraphNode,
    StateEquation,
    StateId,
    TermId,
    WarningCategory,
    WarningSeverity,
    edge_source,
    expression_parameters,
    mul,
    relation_default_sign,
    state_source,
)
from services.domain.base import JsonValue
from services.domain.warnings import WarningSource
from services.pathway.loader import load_pathway
from services.pathway.models import HomeostasisTermDefinition, PathwayDefinition

from .operators import (
    delay_term,
    drug_activation_by_state,
    hill_inhibition_by_drug,
    p,
    s,
    saturable_source_term,
    source_target_loss,
)

GRAPH_DERIVED_EXECUTION_MODEL = "graph_derived_expression_ir_v2"


class _ParameterSource(Protocol):
    parameters: tuple[ParameterId, ...]
    source_edges: tuple[EdgeId, ...]
    operator: OperatorId


def _term_id(value: str) -> TermId:
    return TermId(value)


def _parameter_id(value: str) -> ParameterId:
    return ParameterId(value)


def _operator_id(value: str) -> OperatorId:
    return OperatorId(value)


def _warning(
    category: WarningCategory,
    message: str,
    *,
    source: WarningSource | None = None,
    severity: WarningSeverity = WarningSeverity.WARNING,
    details: Mapping[str, JsonValue] | None = None,
) -> ModelWarning:
    return ModelWarning(
        category=category,
        severity=severity,
        message=message,
        source=source,
        details={} if details is None else dict(details),
    )


def _causal_edges(graph: MoAGraph) -> tuple[Edge, ...]:
    return graph.structural_edges()


def _edge_modifiers(graph: MoAGraph) -> tuple[Edge, ...]:
    return graph.modifier_edges()


def _path_exists(graph: MoAGraph, start: StateId, end: StateId) -> bool:
    start_node = graph.node_for_state(start)
    end_node = graph.node_for_state(end)
    if start_node is None or end_node is None:
        return False
    adjacency: dict[NodeId, list[NodeId]] = defaultdict(list)
    for edge in _causal_edges(graph):
        adjacency[edge.source].append(NodeId(str(edge.target)))
    queue: deque[NodeId] = deque([start_node.id])
    seen = {start_node.id}
    while queue:
        node = queue.popleft()
        if node == end_node.id:
            return True
        for nxt in adjacency.get(node, []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return False


def _states(graph: MoAGraph) -> tuple[StateId, ...]:
    return tuple(node.state.id for node in graph.nodes if node.state is not None and node.state.executable)


def _homeostatic_terms(
    graph: MoAGraph,
    pathway: PathwayDefinition,
    states: frozenset[StateId],
) -> tuple[EquationTerm, ...]:
    definitions: list[HomeostasisTermDefinition] = list(pathway.homeostasis)
    for module_id in graph.metadata.included_modules:
        module = pathway.modules.get(ModuleId(str(module_id)))
        if module is not None:
            definitions.extend(module.homeostasis)

    terms: list[EquationTerm] = []
    for definition in definitions:
        if definition.state not in states:
            continue
        terms.append(
            EquationTerm(
                state=definition.state,
                term_id=definition.term_id,
                expression=definition.expression,
                operator=definition.operator,
                sign=definition.sign,
                source_edges=definition.source_edges,
                modifiers=(),
                parameters=expression_parameters(definition.expression),
                description=definition.description,
            )
        )
    return tuple(terms)


def _evidence_quality_warnings(graph: MoAGraph) -> tuple[ModelWarning, ...]:
    warnings: list[ModelWarning] = []
    for edge in graph.edges:
        if edge.confidence < 0.5:
            warnings.append(
                _warning(
                    WarningCategory.LOW_CONFIDENCE,
                    f"Edge {edge.id} has low confidence ({edge.confidence:.2f}); evidence may be insufficient.",
                    source=edge_source(edge.id),
                    details={"confidence": edge.confidence},
                )
            )
        low_evidence = tuple(
            evidence
            for evidence in edge.evidence
            if evidence.confidence is not None and evidence.confidence < 0.5
        )
        if low_evidence:
            warnings.append(
                _warning(
                    WarningCategory.LOW_CONFIDENCE,
                    f"Edge {edge.id} has low-confidence evidence; treat the compiled term as tentative.",
                    source=edge_source(edge.id),
                )
            )
    return tuple(warnings)


def _expression_ir(expression: ExecutableOrDisplayExpression) -> Expression:
    if isinstance(expression, DisplayExpression):
        raise TypeError("Graph-derived compiler expected executable expression IR")
    return expression


def _state_equations(
    states: tuple[StateId, ...], terms: tuple[EquationTerm, ...]
) -> tuple[StateEquation, ...]:
    terms_by_state: dict[StateId, list[EquationTerm]] = {state: [] for state in states}
    for term in terms:
        terms_by_state.setdefault(term.state, []).append(term)

    equations: list[StateEquation] = []
    for state in states:
        state_terms = tuple(terms_by_state[state])
        expression = (
            Add(terms=tuple(_expression_ir(term.expression) for term in state_terms))
            if state_terms
            else Constant(value=0.0)
        )
        source_edges = tuple(
            sorted({edge_id for term in state_terms for edge_id in (*term.source_edges, *term.modifiers)})
        )
        parameters = expression_parameters(expression)
        equations.append(
            StateEquation(
                state=state,
                terms=tuple(term.term_id for term in state_terms),
                expression=expression,
                source_edges=source_edges,
                parameters=parameters,
            )
        )
    return tuple(equations)


def _modifier_parameters(edge: Edge, target_edge: Edge) -> dict[str, ParameterId]:
    raw = edge.metadata.extension.get("parameters", {})
    if not isinstance(raw, dict):
        raw = {}
    values = {str(key): ParameterId(str(value)) for key, value in raw.items()}
    if "half_max" not in values:
        values["half_max"] = ParameterId(f"Ki_{target_edge.id}")
    if "alpha" not in values:
        values["alpha"] = ParameterId(f"alpha_{target_edge.id}")
    if "kd" not in values:
        values["kd"] = ParameterId(f"KD_{target_edge.id}")
    return values


def _compile_modifier(edge: Edge, target_edge: Edge, drug_state: StateId | None) -> ModifierTerm:
    if edge.expression is not None:
        expression = edge.expression
    else:
        if drug_state is None:
            raise ValueError("Edge modifier compilation requires a graph drug_state or drug node role")
        params = _modifier_parameters(edge, target_edge)
        template = edge.metadata.extension.get("modifier_template")
        if str(edge.relation) == "inhibits_edge" or template == "hill_inhibition":
            expression = hill_inhibition_by_drug(drug_state, params["half_max"])
        elif str(edge.relation) == "activates_edge" or template == "drug_activation":
            expression = drug_activation_by_state(drug_state, params["alpha"], params["kd"])
        else:
            raise ValueError(f"Unsupported edge modifier relation {edge.relation!r}")

    operator = _operator_id("edge_inhibition" if str(edge.relation) == "inhibits_edge" else "edge_activation")
    desc = edge.description or f"Drug modifier {edge.relation} on reaction edge {target_edge.id}."
    return ModifierTerm(
        modifier_id=ModifierId(str(edge.id)),
        target_edge=target_edge.id,
        expression=expression,
        operator=operator,
        source_edges=(edge.id, target_edge.id),
        parameters=expression_parameters(expression),
        description=desc,
    )


def _compile_modifiers(graph: MoAGraph) -> tuple[ModifierTerm, ...]:
    edge_map = graph.edge_map()
    drug_state = graph.drug_state()
    modifier_terms: list[ModifierTerm] = []
    for edge in _edge_modifiers(graph):
        target_edge = edge_map[EdgeId(str(edge.target))]
        modifier_terms.append(_compile_modifier(edge, target_edge, drug_state))
    return tuple(modifier_terms)


def _modifiers_by_target(modifiers: tuple[ModifierTerm, ...]) -> dict[EdgeId, tuple[ModifierTerm, ...]]:
    grouped: dict[EdgeId, list[ModifierTerm]] = defaultdict(list)
    for modifier in modifiers:
        grouped[modifier.target_edge].append(modifier)
    return {edge_id: tuple(items) for edge_id, items in grouped.items()}


def _modifier_ids(modifiers: tuple[ModifierTerm, ...]) -> tuple[EdgeId, ...]:
    return tuple(EdgeId(str(modifier.modifier_id)) for modifier in modifiers)


def _modifier_expression_ir(modifier: ModifierTerm) -> Expression:
    if isinstance(modifier.expression, DisplayExpression):
        raise TypeError(f"Modifier {modifier.modifier_id} is not executable expression IR.")
    return modifier.expression


def _apply_modifiers(expression: Expression, modifiers: tuple[ModifierTerm, ...]) -> Expression:
    if not modifiers:
        return expression
    return mul(expression, *(_modifier_expression_ir(modifier) for modifier in modifiers))


def _target_state(graph: MoAGraph, edge: Edge) -> StateId:
    state = graph.edge_target_state(edge)
    if state is None:
        raise ValueError(f"Edge {edge.id} target {edge.target!r} has no executable state binding.")
    return state


def _source_state(graph: MoAGraph, edge: Edge) -> StateId:
    state = graph.edge_source_state(edge)
    if state is None:
        raise ValueError(f"Edge {edge.id} source {edge.source!r} has no executable state binding.")
    return state


def _generic_operator_for_relation(relation: RelationId, edge_operator: OperatorId | None) -> OperatorId:
    if edge_operator is not None:
        return edge_operator
    mapping = {
        "activates": "activation",
        "inhibits": "inhibition",
        "phosphorylates": "phosphorylation",
        "dephosphorylates": "dephosphorylation",
        "degrades": "degradation",
        "dimerizes": "dimerization",
        "ubiquitinates": "ubiquitination",
        "drives_phenotype": "phenotype_drive",
        "delays_signal": "delay",
    }
    return OperatorId(mapping.get(str(relation), str(relation)))


def _generic_expression(graph: MoAGraph, edge: Edge, operator: OperatorId) -> Expression:
    target_state = _target_state(graph, edge)
    source_state = _source_state(graph, edge)
    base = f"{edge.source}_to_{edge.target}"
    match str(operator):
        case "activation" | "dimerization" | "ubiquitination" | "phenotype_drive":
            return saturable_source_term(
                _parameter_id(f"k_{base}"), source_state, _parameter_id(f"K_{edge.source}")
            )
        case "phosphorylation":
            return mul(p(f"k_{base}"), s(source_state))
        case "inhibition":
            return source_target_loss(_parameter_id(f"k_{base}"), source_state, target_state)
        case "dephosphorylation" | "degradation":
            return source_target_loss(_parameter_id(f"k_{base}"), source_state, target_state)
        case "delay":
            return delay_term(source_state, target_state, _parameter_id(f"tau_{base}"))
        case _:
            return saturable_source_term(
                _parameter_id(f"k_{base}"), source_state, _parameter_id(f"K_{edge.source}")
            )


def _compile_causal_edge_terms(
    graph: MoAGraph,
    edge: Edge,
    modifiers: tuple[ModifierTerm, ...],
    warnings: list[ModelWarning],
) -> tuple[EquationTerm, ...]:
    target_state = graph.edge_target_state(edge)
    if target_state is None:
        warnings.append(
            _warning(
                WarningCategory.SIMULATOR_INCOMPATIBLE_STATE,
                f"Edge {edge.id} does not target an executable state; no term generated.",
                source=edge_source(edge.id),
                severity=WarningSeverity.ERROR,
            )
        )
        return ()
    operator = _generic_operator_for_relation(edge.relation, edge.operator)
    expression = (
        edge.expression if edge.expression is not None else _generic_expression(graph, edge, operator)
    )
    sign = edge.sign if edge.sign != Sign.UNKNOWN else relation_default_sign(str(edge.relation))
    try:
        return (
            EquationTerm(
                state=target_state,
                term_id=_term_id(f"term_{edge.id}_{operator}"),
                expression=_apply_modifiers(expression, modifiers),
                operator=operator,
                sign=sign,
                source_edges=(edge.id,),
                modifiers=_modifier_ids(modifiers),
                parameters=expression_parameters(_apply_modifiers(expression, modifiers)),
                description=edge.description or f"{operator} term for {target_state} from edge {edge.id}.",
            ),
        )
    except Exception as exc:
        warnings.append(
            _warning(
                WarningCategory.SIMULATOR_INCOMPATIBLE_STATE,
                f"Failed compiling edge {edge.id}: {exc}",
                source=edge_source(edge.id),
                severity=WarningSeverity.ERROR,
            )
        )
        return ()


def _compile_graph_terms(
    graph: MoAGraph,
    modifiers: tuple[ModifierTerm, ...],
    warnings: list[ModelWarning],
) -> tuple[EquationTerm, ...]:
    terms: list[EquationTerm] = []
    modifiers_by_target = _modifiers_by_target(modifiers)
    for edge in _causal_edges(graph):
        terms.extend(_compile_causal_edge_terms(graph, edge, modifiers_by_target.get(edge.id, ()), warnings))
    return tuple(terms)


def _record_generated_parameter(
    generated: dict[ParameterId, GeneratedParameter],
    item: _ParameterSource,
    parameter: ParameterId,
    pathway: PathwayDefinition,
) -> None:
    existing = generated.get(parameter)
    source_edges = tuple(sorted(set((existing.source_edges if existing else ()) + item.source_edges)))
    default_value = pathway.parameters.generated_defaults.value_for(parameter)
    generated[parameter] = GeneratedParameter(
        id=parameter,
        source_edges=source_edges,
        operator=item.operator,
        has_prior=False,
        required_for_execution=default_value is None,
        default_value=default_value,
    )


def _generated_parameter_catalog(
    base_catalog: ParameterCatalog,
    terms: tuple[EquationTerm, ...],
    modifiers: tuple[ModifierTerm, ...],
    pathway: PathwayDefinition,
) -> tuple[ParameterCatalog, tuple[ModelWarning, ...]]:
    known = base_catalog.known_parameter_ids()
    generated: dict[ParameterId, GeneratedParameter] = {}
    for item in (*terms, *modifiers):
        for parameter in item.parameters:
            if parameter in known:
                continue
            _record_generated_parameter(generated, item, parameter, pathway)

    if not generated:
        return base_catalog, ()

    missing_defaults = tuple(
        sorted(parameter for parameter, item in generated.items() if item.default_value is None)
    )
    warnings: list[ModelWarning] = []
    if missing_defaults:
        warnings.append(
            _warning(
                WarningCategory.MISSING_PARAMETER_PRIOR,
                "Compiled model registered generated parameters without defaults: "
                + ", ".join(str(parameter) for parameter in missing_defaults)
                + ". They must be supplied before graph-derived execution.",
                details={"parameters": [str(parameter) for parameter in missing_defaults]},
            )
        )
    return base_catalog.with_generated(tuple(generated.values())), tuple(warnings)


def _append_model_structure_warnings(graph: MoAGraph, warnings: list[ModelWarning]) -> None:
    drug_state = graph.drug_state()
    for endpoint in graph.metadata.endpoint_states:
        if endpoint not in _states(graph):
            continue
        if drug_state is None or not _path_exists(graph, drug_state, endpoint):
            modifier_path = False
            edge_map = graph.edge_map()
            for modifier in graph.modifier_edges():
                target = edge_map[EdgeId(str(modifier.target))]
                target_state = graph.edge_target_state(target)
                source_state = graph.edge_source_state(target)
                modifier_path = modifier_path or any(
                    state is not None and (state == endpoint or _path_exists(graph, state, endpoint))
                    for state in (source_state, target_state)
                )
            if not modifier_path:
                warnings.append(
                    _warning(
                        WarningCategory.MISSING_CAUSAL_PATH,
                        f"No causal path or drug edge modifier to endpoint state {endpoint} was detected.",
                        source=state_source(endpoint),
                    )
                )


def _initial_conditions_for_states(
    pathway: PathwayDefinition, graph: MoAGraph, states: tuple[StateId, ...]
) -> dict[StateId, float]:
    initials = dict(pathway.initial_conditions.values)
    for node in graph.nodes:
        if node.state is not None and node.state.initial is not None:
            initials[node.state.id] = node.state.initial
    missing = [state for state in states if state not in initials]
    if missing:
        raise ValueError(f"Missing initial conditions for composed states: {missing}")
    return {state: float(initials[state]) for state in states}


def _logic_checks_from_graph(graph: MoAGraph, pathway: PathwayDefinition) -> tuple[dict[str, JsonValue], ...]:
    checks: list[dict[str, JsonValue]] = []
    seen_ids: set[str] = set()

    def append_once(item: Mapping[str, JsonValue]) -> None:
        normalized = {str(key): value for key, value in item.items()}
        check_id = normalized.get("id")
        if isinstance(check_id, str):
            if check_id in seen_ids:
                return
            seen_ids.add(check_id)
        checks.append(normalized)

    for item in pathway.logic_checks:
        append_once(item)
    raw = graph.metadata.extension.get("logic_checks", ())
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                append_once(item)
    return tuple(checks)


def compile_graph(graph: MoAGraph, pathway: PathwayDefinition | None = None) -> CompiledModel:
    pathway = load_pathway(graph.metadata.pathway_id) if pathway is None else pathway
    states = _states(graph)
    state_set = frozenset(states)
    terms: list[EquationTerm] = list(_homeostatic_terms(graph, pathway, state_set))
    warnings: list[ModelWarning] = list(_evidence_quality_warnings(graph))
    modifiers = _compile_modifiers(graph)
    terms.extend(_compile_graph_terms(graph, modifiers, warnings))

    base_catalog = pathway.parameters.catalog()
    term_tuple = tuple(terms)
    parameter_catalog, parameter_warnings = _generated_parameter_catalog(
        base_catalog, term_tuple, modifiers, pathway
    )
    warnings.extend(parameter_warnings)
    _append_model_structure_warnings(graph, warnings)

    equations = _state_equations(states, term_tuple)
    initial_conditions = _initial_conditions_for_states(pathway, graph, states)
    logic_checks = _logic_checks_from_graph(graph, pathway)
    return CompiledModel(
        graph_id=graph.graph_id,
        label=graph.label,
        states=states,
        terms=term_tuple,
        modifiers=modifiers,
        equations=equations,
        parameter_catalog=parameter_catalog,
        warnings=tuple(warnings),
        metadata=CompiledModelMetadata(
            pathway_id=pathway.pathway_id,
            selected_configuration=graph.metadata.configuration,
            included_modules=graph.metadata.included_modules,
            drug_effects=graph.metadata.drug_effects,
            drug_state=graph.drug_state(),
            endpoint_states=tuple(
                state for state in pathway.presentation.endpoint_states if state in state_set
            ),
            plot_states=tuple(
                state.state for state in pathway.presentation.plot_states if state.state in state_set
            ),
            initial_conditions=initial_conditions,
            logic_checks=logic_checks,
            graph_summary=graph.summarize(),
            execution_model=GRAPH_DERIVED_EXECUTION_MODEL,
            expressions_execute_directly=True,
            source_graph_nodes=tuple(
                SourceGraphNode(
                    id=node.id,
                    type=str(node.type),
                    state=None if node.state is None else node.state.id,
                    roles=node.roles,
                )
                for node in graph.nodes
            ),
            source_graph_edges=tuple(SourceGraphEdge.from_graph_edge(edge) for edge in graph.edges),
            notes=(
                "EquationTerm.expression and StateEquation.expression are executable expression IR. "
                "Pathway-specific biology comes from the loaded pathway JSON.",
            ),
        ),
    )
