"""Review classification and warning policy for annotation evidence graphs."""

from __future__ import annotations

from services.annotation_import.models import (
    AnnotationBundle,
    ContextScope,
    MechanismStep,
    MechanismVerification,
    ReviewStatus,
    SimulationParameterRecord,
    StudyDesignRecord,
    WarningRecord,
)


def projection_warnings(bundle: AnnotationBundle) -> tuple[WarningRecord, ...]:
    mechanism_projection_count = projection_node_count(bundle, "tktype:MechanismChain")
    verification_projection_count = projection_node_count(bundle, "tktype:MechanismVerification")
    top_level_step_count = sum(len(chain.steps) for chain in bundle.mechanism_chains)
    top_level_verification_count = len(bundle.mechanism_verifications)
    warnings: list[WarningRecord] = []
    if mechanism_projection_count and mechanism_projection_count != top_level_step_count:
        warnings.append(
            WarningRecord(
                code="kg_projection_mechanisms_ignored",
                message=(
                    f"Ignored {mechanism_projection_count} projected mechanism nodes; "
                    f"used {top_level_step_count} top-level mechanism steps."
                ),
                source_record_type="kg_projection",
            )
        )
    if verification_projection_count and verification_projection_count != top_level_verification_count:
        warnings.append(
            WarningRecord(
                code="kg_projection_verifications_ignored",
                message=(
                    f"Ignored {verification_projection_count} projected verification nodes; "
                    f"used {top_level_verification_count} top-level verification records."
                ),
                source_record_type="kg_projection",
            )
        )
    return tuple(warnings)


def readiness_warnings(bundle: AnnotationBundle) -> tuple[WarningRecord, ...]:
    warnings: list[WarningRecord] = []
    if not bundle.mechanism_chains:
        warnings.append(
            WarningRecord(
                code="no_top_level_mechanism_chains",
                message="No top-level mechanism chains were available for causal extraction.",
                source_record_type="mechanism_chains",
            )
        )
    for plan in bundle.simulation_readiness_plans:
        if plan.readiness_status and plan.readiness_status != "ready":
            warnings.append(
                WarningRecord(
                    code="simulation_readiness_not_ready",
                    message=f"Simulation readiness is {plan.readiness_status}: {plan.decision_reason or 'review required'}.",
                    source_record_type="simulation_readiness_plan",
                    source_record_id=plan.plan_id,
                )
            )
        for missing in plan.missing_inputs:
            name = missing.get("name")
            reason = missing.get("reason")
            severity = missing.get("severity")
            if isinstance(name, str):
                warnings.append(
                    WarningRecord(
                        code="missing_model_input",
                        message=f"Missing {name}: {reason}"
                        if isinstance(reason, str)
                        else f"Missing {name}.",
                        severity="error" if severity == "blocking" else "warning",
                        source_record_type="simulation_readiness_plan",
                        source_record_id=plan.plan_id,
                    )
                )
    return tuple(warnings)


def mechanism_warnings(
    step: MechanismStep,
    verification: MechanismVerification | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if not step.evidence_anchor_ids:
        warnings.append("missing_evidence_anchor")
    if verification is None:
        warnings.append("missing_top_level_verification")
    else:
        warnings.extend(verification.issues)
    return tuple(warnings)


def parameter_warnings(
    value: float | None,
    unit: str | None,
    scope: ContextScope,
    validation_status: str | None,
    existing_warnings: tuple[str, ...],
) -> tuple[str, ...]:
    warnings = list(existing_warnings)
    if value is None:
        warnings.append("missing_value")
    if unit is None:
        warnings.append("missing_unit")
    if validation_status is not None and validation_status != "verified":
        warnings.append(f"validation_status:{validation_status}")
    if not (scope.species or scope.translation_stage or scope.model_system):
        warnings.append("missing_species_or_translation_context")
    return tuple(dict.fromkeys(warnings))


def simulation_parameter_warnings(
    parameter: SimulationParameterRecord,
    scope: ContextScope,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if parameter.validation_status != "verified":
        warnings.append(f"validation_status:{parameter.validation_status or 'unknown'}")
    if parameter.value is None and parameter.role not in {"model_structure"}:
        warnings.append("missing_value")
    if parameter.unit is None:
        warnings.append("missing_unit")
    if parameter.role == "calibration_or_validation_endpoint":
        warnings.append("calibration_or_validation_endpoint")
    if not (scope.species or scope.translation_stage or scope.model_system):
        warnings.append("missing_species_or_translation_context")
    return tuple(dict.fromkeys(warnings))


def mechanism_review_status(
    verification: MechanismVerification | None,
    warnings: tuple[str, ...],
) -> ReviewStatus:
    if "missing_evidence_anchor" in warnings:
        return "review_only"
    if verification is None:
        return "review_only"
    if verification.verdict in {"verified_therapeutic_moa", "model_derived_pd_relation"}:
        return "candidate_for_pathway_patch"
    if verification.verdict == "paper_supported_only":
        return "accepted_for_evidence_graph"
    return "review_only"


def simulation_parameter_review_status(
    parameter: SimulationParameterRecord,
    warnings: tuple[str, ...],
) -> ReviewStatus:
    if warnings:
        return "review_only"
    if parameter.role in {"model_input", "equation_variable", "model_structure", "candidate_model_input"}:
        return "candidate_for_pathway_patch"
    return "accepted_for_evidence_graph"


def relation_for_predicate(predicate: str) -> str:
    lowered = predicate.lower()
    if "inhibit" in lowered or "decreas" in lowered or "suppress" in lowered:
        return "inhibits"
    if "bind" in lowered:
        return "binds"
    if "activat" in lowered or "increase" in lowered or "drive" in lowered:
        return "activates"
    if "predict" in lowered:
        return "predicts"
    return "relates_to"


def projection_node_count(bundle: AnnotationBundle, node_type: str) -> int:
    nodes = bundle.kg_projection.get("nodes")
    if not isinstance(nodes, list):
        return 0
    count = 0
    for node in nodes:
        if isinstance(node, dict) and node.get("node_type") == node_type:
            count += 1
    return count


def study_translation_stage(study_design: StudyDesignRecord) -> str | None:
    if study_design.study_type in {"clinical", "in_vitro"}:
        return study_design.study_type.replace("_", " ")
    if study_design.study_type == "animal":
        return "preclinical"
    return None
