"""Generic vocabulary shared by the pathway runtime.

Pathway-specific state names, node types, graph recipes, and route concepts are
intentionally absent from this module. Those values come from pathway JSON.
"""

from __future__ import annotations

from enum import StrEnum


class Sign(StrEnum):
    POSITIVE = "+"
    NEGATIVE = "-"
    UNKNOWN = "?"


EDGE_TARGET_RELATIONS = frozenset({"inhibits_edge", "activates_edge"})

NEGATIVE_EDGE_RELATIONS = frozenset(
    {
        "inhibits",
        "dephosphorylates",
        "degrades",
        "inhibits_edge",
    }
)

POSITIVE_EDGE_RELATIONS = frozenset(
    {
        "activates",
        "phosphorylates",
        "dimerizes",
        "ubiquitinates",
        "drives_phenotype",
        "delays_signal",
        "activates_edge",
        "synthesis",
    }
)


def relation_default_sign(relation: str) -> Sign:
    if relation in NEGATIVE_EDGE_RELATIONS:
        return Sign.NEGATIVE
    if relation in POSITIVE_EDGE_RELATIONS:
        return Sign.POSITIVE
    return Sign.UNKNOWN


POSITIVE_OPERATOR_KINDS = frozenset(
    {
        "activation",
        "phosphorylation",
        "dimerization",
        "ubiquitination",
        "phenotype_drive",
        "delay",
        "edge_activation",
        "constant_input",
        "synthesis",
    }
)

NEGATIVE_OPERATOR_KINDS = frozenset(
    {
        "inhibition",
        "dephosphorylation",
        "degradation",
        "edge_inhibition",
        "pk_elimination",
        "baseline_degradation",
        "first_order_loss",
        "phenotype_turnover_loss",
        "source_consumption",
    }
)

OPERATOR_RELATION_BY_KIND: dict[str, str] = {
    "activation": "activates",
    "inhibition": "inhibits",
    "phosphorylation": "phosphorylates",
    "dephosphorylation": "dephosphorylates",
    "degradation": "degrades",
    "dimerization": "dimerizes",
    "ubiquitination": "ubiquitinates",
    "phenotype_drive": "drives_phenotype",
    "delay": "delays_signal",
    "edge_inhibition": "inhibits_edge",
    "edge_activation": "activates_edge",
}


class EvidenceSourceType(StrEnum):
    CLAIM = "claim"
    CURATED_ASSUMPTION = "curated_assumption"
    PAPER = "paper"
    ASSAY = "assay"
    DATABASE = "database"
    EXPERT_REVIEW = "expert_review"
    OTHER = "other"


class WarningCategory(StrEnum):
    MISSING_EVIDENCE = "missing_evidence"
    LOW_CONFIDENCE = "low_confidence"
    UNSUPPORTED_RELATION = "unsupported_relation"
    MISSING_CAUSAL_PATH = "missing_causal_path"
    MISSING_PARAMETER_PRIOR = "missing_parameter_prior"
    SIMULATOR_INCOMPATIBLE_STATE = "simulator_incompatible_state"
    COMBINED_MECHANISM = "combined_mechanism"
    UNSTABLE_SIMULATION = "unstable_simulation"
    OTHER = "other"


class WarningSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
