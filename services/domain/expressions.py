"""Typed expression IR for executable and display-only compiled equations."""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from .base import STRICT_MODEL_CONFIG
from .identifiers import ParameterId, StateId


class DisplayExpression(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    text: str = Field(min_length=1)
    executable: Literal[False] = False


class Constant(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    kind: Literal["constant"] = "constant"
    value: float

    @field_validator("value")
    @classmethod
    def finite_value(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Expression constant must be finite")
        return value


class StateRef(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    kind: Literal["state_ref"] = "state_ref"
    state: StateId


class ParameterRef(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    kind: Literal["parameter_ref"] = "parameter_ref"
    parameter: ParameterId


class Add(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    kind: Literal["add"] = "add"
    terms: tuple[Expression, ...] = Field(min_length=1)


class Multiply(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    kind: Literal["multiply"] = "multiply"
    factors: tuple[Expression, ...] = Field(min_length=1)


class Divide(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    kind: Literal["divide"] = "divide"
    numerator: Expression
    denominator: Expression


class Power(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    kind: Literal["power"] = "power"
    base: Expression
    exponent: float

    @field_validator("exponent")
    @classmethod
    def finite_exponent(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Expression exponent must be finite")
        return value


class HillInhibition(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    kind: Literal["hill_inhibition"] = "hill_inhibition"
    signal: Expression
    half_max: Expression


class SaturatingActivation(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    kind: Literal["saturating_activation"] = "saturating_activation"
    signal: Expression
    half_max: Expression


class FirstOrderLoss(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    kind: Literal["first_order_loss"] = "first_order_loss"
    state: StateId
    rate: ParameterId


Expression = Annotated[
    Constant
    | StateRef
    | ParameterRef
    | Add
    | Multiply
    | Divide
    | Power
    | HillInhibition
    | SaturatingActivation
    | FirstOrderLoss,
    Field(discriminator="kind"),
]


class ExpressionEnvelope(BaseModel):
    """Boundary wrapper used by tests and artifact validation for expression IR."""

    model_config = STRICT_MODEL_CONFIG

    expression: Expression


ExecutableOrDisplayExpression = Expression | DisplayExpression


def const(value: float) -> Constant:
    return Constant(value=value)


def state_ref(state: StateId | str) -> StateRef:
    return StateRef(state=StateId(str(state)))


def parameter_ref(parameter: ParameterId | str) -> ParameterRef:
    return ParameterRef(parameter=ParameterId(str(parameter)))


def display(expression: str) -> DisplayExpression:
    return DisplayExpression(text=expression, executable=False)


def add(*terms: Expression) -> Expression:
    if not terms:
        return Constant(value=0.0)
    if len(terms) == 1:
        return terms[0]
    return Add(terms=tuple(terms))


def mul(*factors: Expression) -> Expression:
    if not factors:
        return Constant(value=1.0)
    if len(factors) == 1:
        return factors[0]
    return Multiply(factors=tuple(factors))


def div(numerator: Expression, denominator: Expression) -> Divide:
    return Divide(numerator=numerator, denominator=denominator)


def power(base: Expression, exponent: float) -> Power:
    return Power(base=base, exponent=exponent)


def neg(expression: Expression) -> Expression:
    return mul(Constant(value=-1.0), expression)


def hill_inhibition(signal: Expression, half_max: Expression) -> HillInhibition:
    return HillInhibition(signal=signal, half_max=half_max)


def saturating_activation(signal: Expression, half_max: Expression) -> SaturatingActivation:
    return SaturatingActivation(signal=signal, half_max=half_max)


def drug_activation(
    alpha: Expression,
    kd: Expression,
    drug: Expression,
) -> Add:
    return Add(
        terms=(
            Constant(value=1.0),
            Multiply(
                factors=(
                    alpha,
                    Divide(
                        numerator=drug,
                        denominator=Add(terms=(kd, drug)),
                    ),
                )
            ),
        )
    )


def expression_children(expression: Expression) -> tuple[Expression, ...]:
    if isinstance(expression, Add):
        return expression.terms
    if isinstance(expression, Multiply):
        return expression.factors
    if isinstance(expression, Divide):
        return (expression.numerator, expression.denominator)
    if isinstance(expression, Power):
        return (expression.base,)
    if isinstance(expression, HillInhibition | SaturatingActivation):
        return (expression.signal, expression.half_max)
    return ()


def iter_expression_nodes(expression: Expression | DisplayExpression) -> Iterator[Expression]:
    if isinstance(expression, DisplayExpression):
        return

    stack = [expression]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(expression_children(node)))


def expression_parameters(expression: Expression | DisplayExpression) -> tuple[ParameterId, ...]:
    parameters: list[ParameterId] = []
    seen: set[ParameterId] = set()
    for node in iter_expression_nodes(expression):
        if isinstance(node, ParameterRef):
            parameter = node.parameter
        elif isinstance(node, FirstOrderLoss):
            parameter = node.rate
        else:
            continue
        if parameter not in seen:
            seen.add(parameter)
            parameters.append(parameter)
    return tuple(parameters)


def expression_states(expression: Expression | DisplayExpression) -> tuple[StateId, ...]:
    states: list[StateId] = []
    seen: set[StateId] = set()
    for node in iter_expression_nodes(expression):
        if isinstance(node, StateRef | FirstOrderLoss):
            state = node.state
        else:
            continue
        if state not in seen:
            seen.add(state)
            states.append(state)
    return tuple(states)


def evaluate_expression(
    expression: Expression,
    states: Mapping[StateId, float],
    parameters: Mapping[ParameterId, float],
) -> float:
    """Interpret executable expression IR against state and parameter values."""
    match expression:
        case Constant(value=value):
            return value
        case StateRef(state=state):
            return float(states[state])
        case ParameterRef(parameter=parameter):
            return float(parameters[parameter])
        case Add(terms=terms):
            return sum(evaluate_expression(term, states, parameters) for term in terms)
        case Multiply(factors=factors):
            product = 1.0
            for factor in factors:
                product *= evaluate_expression(factor, states, parameters)
            return product
        case Divide(numerator=numerator, denominator=denominator):
            numerator_value = evaluate_expression(numerator, states, parameters)
            denominator_value = evaluate_expression(denominator, states, parameters)
            return numerator_value / max(denominator_value, 1e-12)
        case Power(base=base, exponent=exponent):
            return evaluate_expression(base, states, parameters) ** exponent
        case HillInhibition(signal=signal_expression, half_max=half_max_expression):
            signal = max(evaluate_expression(signal_expression, states, parameters), 0.0)
            half_max = max(evaluate_expression(half_max_expression, states, parameters), 1e-12)
            return 1.0 / (1.0 + signal / half_max)
        case SaturatingActivation(signal=signal_expression, half_max=half_max_expression):
            signal = max(evaluate_expression(signal_expression, states, parameters), 0.0)
            half_max = max(evaluate_expression(half_max_expression, states, parameters), 1e-12)
            return signal / (half_max + signal)
        case FirstOrderLoss(state=state, rate=rate):
            return -float(parameters[rate]) * float(states[state])
    raise TypeError(f"Unsupported expression node: {type(expression).__name__}")


def render_expression(expression: Expression | DisplayExpression) -> str:
    """Render expression IR as readable math without making strings executable."""

    if isinstance(expression, DisplayExpression):
        return expression.text
    return _render_expression(expression)


def _format_number(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def _needs_parentheses(expression: Expression) -> bool:
    return isinstance(expression, Add)


def _render_factor(expression: Expression) -> str:
    rendered = _render_expression(expression)
    return f"({rendered})" if _needs_parentheses(expression) else rendered


def _render_expression(expression: Expression) -> str:
    match expression:
        case Constant(value=value):
            return _format_number(value)
        case StateRef(state=state):
            return str(state)
        case ParameterRef(parameter=parameter):
            return str(parameter)
        case Add(terms=terms):
            rendered_terms = [_render_expression(term) for term in terms]
            text = " + ".join(rendered_terms)
            return text.replace("+ - ", "- ").replace("+ -", "- ")
        case Multiply(factors=factors):
            if factors and isinstance(factors[0], Constant) and factors[0].value == -1.0:
                remaining = factors[1:]
                if not remaining:
                    return "-1"
                return "- " + " * ".join(_render_factor(factor) for factor in remaining)
            return " * ".join(_render_factor(factor) for factor in factors)
        case Divide(numerator=numerator, denominator=denominator):
            numerator_text = _render_factor(numerator)
            denominator_text = _render_factor(denominator)
            return f"{numerator_text} / {denominator_text}"
        case Power(base=base, exponent=exponent):
            return f"{_render_factor(base)}^{_format_number(exponent)}"
        case HillInhibition(signal=signal, half_max=half_max):
            return f"1 / (1 + {_render_expression(signal)} / {_render_expression(half_max)})"
        case SaturatingActivation(signal=signal, half_max=half_max):
            signal_text = _render_expression(signal)
            return f"{signal_text} / ({_render_expression(half_max)} + {signal_text})"
        case FirstOrderLoss(state=state, rate=rate):
            return f"- {rate} * {state}"
    raise TypeError(f"Unsupported expression node: {type(expression).__name__}")


for model in (
    Add,
    Multiply,
    Divide,
    Power,
    HillInhibition,
    SaturatingActivation,
):
    model.model_rebuild()
