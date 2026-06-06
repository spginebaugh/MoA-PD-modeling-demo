"""Generic operator helpers for graph-derived equations."""

from __future__ import annotations

from services.domain import (
    Constant,
    Divide,
    Expression,
    FirstOrderLoss,
    HillInhibition,
    ParameterId,
    ParameterRef,
    SaturatingActivation,
    StateId,
    StateRef,
    add,
    drug_activation,
    mul,
    neg,
)


def p(value: str | ParameterId) -> ParameterRef:
    return ParameterRef(parameter=ParameterId(str(value)))


def s(value: str | StateId) -> StateRef:
    return StateRef(state=StateId(str(value)))


def c(value: float) -> Constant:
    return Constant(value=value)


def sat(signal: Expression, half_max: Expression) -> SaturatingActivation:
    return SaturatingActivation(signal=signal, half_max=half_max)


def hill(signal: Expression, half_max: Expression) -> HillInhibition:
    return HillInhibition(signal=signal, half_max=half_max)


def first_order_loss(state: StateId | str, rate: ParameterId | str) -> FirstOrderLoss:
    return FirstOrderLoss(state=StateId(str(state)), rate=ParameterId(str(rate)))


def hill_inhibition_by_drug(drug_state: StateId, half_max: ParameterId) -> HillInhibition:
    return hill(s(drug_state), p(half_max))


def drug_activation_by_state(drug_state: StateId, alpha: ParameterId, kd: ParameterId) -> Expression:
    return drug_activation(p(alpha), p(kd), s(drug_state))


def saturable_source_term(rate: ParameterId, source_state: StateId, half_max: ParameterId) -> Expression:
    return mul(p(rate), sat(s(source_state), p(half_max)))


def source_target_loss(rate: ParameterId, source_state: StateId, target_state: StateId) -> Expression:
    return neg(mul(p(rate), s(source_state), s(target_state)))


def delay_term(source_state: StateId, target_state: StateId, tau: ParameterId) -> Expression:
    return Divide(numerator=add(s(source_state), neg(s(target_state))), denominator=p(tau))
