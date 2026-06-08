"""Readiness checks for executing graph-derived compiled models."""

from __future__ import annotations

from collections.abc import Mapping

from services.domain import (
    CompiledModel,
    DisplayExpression,
    ModelWarning,
    ParameterId,
    WarningCategory,
    WarningSeverity,
    expression_parameters,
    expression_states,
)
from services.domain.base import JsonValue

SUPPORTED_EXECUTION_MODEL = "graph_derived_expression_ir_v2"


def _error(
    category: WarningCategory, message: str, *, details: dict[str, JsonValue] | None = None
) -> ModelWarning:
    return ModelWarning(
        category=category,
        severity=WarningSeverity.ERROR,
        message=message,
        details={} if details is None else details,
    )


def validate_simulation_ready(
    model: CompiledModel,
    parameter_overrides: Mapping[ParameterId, float] | None = None,
) -> tuple[ModelWarning, ...]:
    """Return typed error diagnostics that make a compiled model unsafe to simulate."""

    overrides = frozenset(parameter_overrides or {})
    errors: list[ModelWarning] = [
        warning for warning in model.warnings if warning.severity == WarningSeverity.ERROR
    ]

    if model.metadata.execution_model != SUPPORTED_EXECUTION_MODEL:
        errors.append(
            _error(
                WarningCategory.SIMULATOR_INCOMPATIBLE_STATE,
                "Compiled model execution_model is not supported by the graph-derived simulator.",
                details={
                    "execution_model": model.metadata.execution_model,
                    "supported_execution_model": SUPPORTED_EXECUTION_MODEL,
                },
            )
        )

    if not model.metadata.expressions_execute_directly:
        errors.append(
            _error(
                WarningCategory.SIMULATOR_INCOMPATIBLE_STATE,
                "Compiled model must mark expressions as directly executable for graph-derived simulation.",
            )
        )

    display_equations = tuple(
        str(equation.state)
        for equation in model.equations
        if isinstance(equation.expression, DisplayExpression)
    )
    if display_equations:
        errors.append(
            _error(
                WarningCategory.SIMULATOR_INCOMPATIBLE_STATE,
                "Compiled model contains display-only state equations.",
                details={"states": list(display_equations)},
            )
        )

    referenced_parameters = frozenset(
        parameter for equation in model.equations for parameter in expression_parameters(equation.expression)
    )
    missing_required_parameters = tuple(
        sorted(
            parameter
            for parameter in referenced_parameters
            if parameter not in model.parameter_catalog.priors
            and parameter not in model.parameter_catalog.values()
            and parameter not in overrides
        )
    )
    if missing_required_parameters:
        errors.append(
            _error(
                WarningCategory.MISSING_PARAMETER_PRIOR,
                "Generated parameters required for execution must be supplied as parameter_overrides.",
                details={"parameters": [str(parameter_id) for parameter_id in missing_required_parameters]},
            )
        )

    missing_states = tuple(
        sorted(
            {
                str(state)
                for equation in model.equations
                for state in expression_states(equation.expression)
                if state not in model.states
            }
        )
    )
    if missing_states:
        errors.append(
            _error(
                WarningCategory.SIMULATOR_INCOMPATIBLE_STATE,
                "Compiled equations reference states outside model.states.",
                details={"states": list(missing_states)},
            )
        )

    return tuple(errors)
