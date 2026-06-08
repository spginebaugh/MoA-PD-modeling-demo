"""Build final paper MOA graph summary artifacts from curated annotation graphs."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import cast

from services.annotation_import.curated_graph_builder import build_curated_paper_moa_graph
from services.annotation_import.graph_builder import build_paper_evidence_graph
from services.annotation_import.loader import ROOT, load_annotation_bundle
from services.annotation_import.models import (
    ContextScope,
    CuratedPaperMoaEdge,
    CuratedPaperMoaEquation,
    CuratedPaperMoaGraph,
    CuratedPaperMoaParameter,
    PaperProvenance,
)
from services.annotation_import.validation import (
    assert_valid_curated_paper_moa_graph,
    assert_valid_evidence_graph,
)
from services.domain.base import JsonValue

DEFAULT_PAPER_IDS = ("PMC3693219", "PMC5131886")
DEFAULT_OUTPUT_PATH = ROOT / "data" / "curated_annotation_graphs" / "combined.paper_moa_graph.json"
DEFAULT_REPORT_PATH = ROOT / "docs" / "paper-annotation-moa-graph-summary.md"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paper_ids", nargs="*", help="Paper ids to summarize. Defaults to the two curated papers.")
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()

    paper_ids = tuple(args.paper_ids) or DEFAULT_PAPER_IDS
    graphs = tuple(_build_curated_graph(paper_id) for paper_id in paper_ids)
    combined = _combined_artifact(graphs)

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(json.dumps(combined, indent=2, sort_keys=True) + "\n")
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(_markdown_report(combined, graphs))
    print(args.output_path)
    print(args.report_path)


def _build_curated_graph(paper_id: str) -> CuratedPaperMoaGraph:
    evidence_graph = build_paper_evidence_graph(load_annotation_bundle(paper_id))
    assert_valid_evidence_graph(evidence_graph)
    curated_graph = build_curated_paper_moa_graph(evidence_graph)
    assert_valid_curated_paper_moa_graph(curated_graph)
    return curated_graph


def _combined_artifact(graphs: tuple[CuratedPaperMoaGraph, ...]) -> dict[str, JsonValue]:
    causal_edges: list[dict[str, JsonValue]] = [_edge_row(graph, edge) for graph in graphs for edge in graph.edges]
    parameters: list[dict[str, JsonValue]] = [
        _parameter_row(graph, parameter) for graph in graphs for parameter in graph.parameters
    ]
    equations: list[dict[str, JsonValue]] = [
        _equation_row(graph, equation) for graph in graphs for equation in graph.equations
    ]
    contexts: list[dict[str, JsonValue]] = [
        _context_row(graph, context, index) for graph in graphs for index, context in enumerate(graph.contexts)
    ]
    provenance: list[dict[str, JsonValue]] = [
        _provenance_row(graph, item_type, item_id, record)
        for graph in graphs
        for item_type, item_id, records in _provenance_sources(graph)
        for record in records
    ]
    missing_inputs: list[dict[str, JsonValue]] = [
        {
            "paper_id": graph.paper_id,
            "name": missing.name,
            "reason": missing.reason,
            "severity": missing.severity,
        }
        for graph in graphs
        for missing in graph.missing_inputs
    ]
    review_status_counts = Counter(
        row["review_status"] for row in (*causal_edges, *parameters, *equations) if isinstance(row["review_status"], str)
    )
    parameter_group_counts = Counter(
        row["parameter_group"] for row in parameters if isinstance(row["parameter_group"], str)
    )
    graph_rows: list[JsonValue] = [
        cast(dict[str, JsonValue], graph.model_dump(mode="json")) for graph in graphs
    ]
    tables: dict[str, JsonValue] = {
        "causal_edges": cast(JsonValue, causal_edges),
        "parameters": cast(JsonValue, parameters),
        "equations": cast(JsonValue, equations),
        "contexts": cast(JsonValue, contexts),
        "missing_inputs": cast(JsonValue, missing_inputs),
        "provenance": cast(JsonValue, provenance),
    }

    return {
        "artifact_id": "combined.paper_moa_graph",
        "title": "Combined paper annotation MOA graph review artifact",
        "paper_ids": [graph.paper_id for graph in graphs],
        "runtime_executable": False,
        "primary_artifact_type": "curated_paper_moa_graphs",
        "summary": {
            "paper_count": len(graphs),
            "curated_graph_count": len(graphs),
            "causal_edge_count": len(causal_edges),
            "parameter_count": len(parameters),
            "equation_count": len(equations),
            "context_count": len(contexts),
            "provenance_record_count": len(provenance),
            "review_status_counts": dict(sorted(review_status_counts.items())),
            "parameter_group_counts": dict(sorted(parameter_group_counts.items())),
            "runtime_executable": False,
        },
        "causal_prioritization": _causal_prioritization(graphs),
        "graphs": graph_rows,
        "tables": tables,
    }


def _causal_prioritization(graphs: tuple[CuratedPaperMoaGraph, ...]) -> dict[str, JsonValue]:
    by_paper: dict[str, JsonValue] = {}
    for graph in graphs:
        candidate_edges = tuple(edge for edge in graph.edges if edge.review_status == "candidate_for_pathway_patch")
        by_paper[graph.paper_id] = {
            "graph_kind": graph.graph_kind,
            "causal_edge_count": len(graph.edges),
            "candidate_edge_count": len(candidate_edges),
            "runtime_executable": graph.executable,
            "interpretation": _paper_interpretation(graph),
            "priority_edges": [
                {
                    "edge_id": edge.edge_id,
                    "source": edge.source,
                    "target": edge.target,
                    "relation": edge.relation,
                    "causal_role": edge.causal_role,
                    "support_level": edge.support_level,
                    "review_status": edge.review_status,
                    "reason": edge.reason,
                    "evidence_anchor_ids": list(edge.evidence_anchor_ids),
                    "source_record_ids": list(edge.source_record_ids),
                }
                for edge in candidate_edges
            ],
        }
    return by_paper


def _paper_interpretation(graph: CuratedPaperMoaGraph) -> str:
    if graph.paper_id == "PMC3693219":
        return (
            "No trusted top-level mechanism chains were available, so this graph is an "
            "erlotinib PK/dosing/resistance overlay with no promoted causal MOA edges."
        )
    if graph.paper_id == "PMC5131886":
        return (
            "Curated sunitinib PK/PD/MOA chain connects active exposure to sVEGFR2 suppression, "
            "tumor-growth inhibition, and time-to-tumor-progression model outputs."
        )
    return "Curated paper-specific review graph."


def _edge_row(graph: CuratedPaperMoaGraph, edge: CuratedPaperMoaEdge) -> dict[str, JsonValue]:
    edge_id = edge.edge_id
    return {
        "paper_id": graph.paper_id,
        "item_type": "edge",
        "edge_id": edge_id,
        "source": edge.source,
        "target": edge.target,
        "relation": edge.relation,
        "causal_role": edge.causal_role,
        "support_level": edge.support_level,
        "review_status": edge.review_status,
        "reason": edge.reason,
        "context": _context_summary(edge.context),
        "source_record_ids": list(edge.source_record_ids),
        "supporting_mechanism_step_ids": list(edge.supporting_mechanism_step_ids),
        "supporting_parameter_ids": list(edge.supporting_parameter_ids),
        "supporting_equation_ids": list(edge.supporting_equation_ids),
        "evidence_anchor_ids": list(edge.evidence_anchor_ids),
        "provenance_count": len(edge.provenance),
    }


def _parameter_row(
    graph: CuratedPaperMoaGraph,
    parameter: CuratedPaperMoaParameter,
) -> dict[str, JsonValue]:
    return {
        "paper_id": graph.paper_id,
        "item_type": "parameter",
        "parameter_id": parameter.parameter_id,
        "name": parameter.name,
        "role": parameter.role,
        "parameter_group": _parameter_group(parameter),
        "symbol": parameter.symbol,
        "value": parameter.value,
        "unit": parameter.unit,
        "target_node_id": parameter.target_node_id,
        "target_edge_id": parameter.target_edge_id,
        "review_status": parameter.review_status,
        "reason": parameter.reason,
        "promotion_blockers": list(parameter.promotion_blockers),
        "context": _context_summary(parameter.context),
        "source_record_ids": list(parameter.source_record_ids),
        "evidence_anchor_ids": list(parameter.evidence_anchor_ids),
        "provenance_count": len(parameter.provenance),
    }


def _equation_row(graph: CuratedPaperMoaGraph, equation: CuratedPaperMoaEquation) -> dict[str, JsonValue]:
    return {
        "paper_id": graph.paper_id,
        "item_type": "equation",
        "equation_id": equation.equation_id,
        "binding_type": equation.binding_type,
        "target_node_id": equation.target_node_id,
        "target_edge_id": equation.target_edge_id,
        "model_form": equation.model_form,
        "expression_text": equation.expression_text,
        "review_status": equation.review_status,
        "reason": equation.reason,
        "context": _context_summary(equation.context),
        "source_record_ids": list(equation.source_record_ids),
        "evidence_anchor_ids": list(equation.evidence_anchor_ids),
        "provenance_count": len(equation.provenance),
    }


def _context_row(graph: CuratedPaperMoaGraph, context: ContextScope, index: int) -> dict[str, JsonValue]:
    return {
        "paper_id": graph.paper_id,
        "context_index": index,
        "species": context.species,
        "translation_stage": context.translation_stage,
        "disease": context.disease,
        "disease_subtype": context.disease_subtype,
        "state": context.state,
        "assay": context.assay,
        "matrix": context.matrix,
        "tissue_or_organ": context.tissue_or_organ,
        "cell_line": context.cell_line,
        "model_system": context.model_system,
        "drug_or_analyte": context.drug_or_analyte,
        "source_anchor_ids": list(context.source_anchor_ids),
    }


def _provenance_sources(
    graph: CuratedPaperMoaGraph,
) -> tuple[tuple[str, str, tuple[PaperProvenance, ...]], ...]:
    rows: list[tuple[str, str, tuple[PaperProvenance, ...]]] = []
    rows.extend(("edge", edge.edge_id, edge.provenance) for edge in graph.edges)
    rows.extend(("parameter", parameter.parameter_id, parameter.provenance) for parameter in graph.parameters)
    rows.extend(("equation", equation.equation_id, equation.provenance) for equation in graph.equations)
    return tuple(rows)


def _provenance_row(
    graph: CuratedPaperMoaGraph,
    item_type: str,
    item_id: str,
    record: PaperProvenance,
) -> dict[str, JsonValue]:
    return {
        "paper_id": graph.paper_id,
        "item_type": item_type,
        "item_id": item_id,
        "source_record_type": record.source_record_type,
        "source_record_id": record.source_record_id,
        "evidence_anchor_ids": list(record.evidence_anchor_ids),
        "source_section": record.source_section,
        "source_chunk_id": record.source_chunk_id,
        "source_table_or_figure": record.source_table_or_figure,
        "quote_or_sentence": record.quote_or_sentence,
        "verification_id": record.verification_id,
        "verification_verdict": record.verification_verdict,
        "validation_status": record.validation_status,
        "trust_level": record.trust_level,
        "warnings": list(record.warnings),
    }


def _parameter_group(parameter: CuratedPaperMoaParameter) -> str:
    explicit = parameter.metadata.get("parameter_group")
    if isinstance(explicit, str):
        return explicit
    role = parameter.role.lower()
    name = parameter.name.lower()
    if role.startswith("pk_") or "plasma" in name or "dose" in name:
        return "pk_exposure_endpoint" if "endpoint" in role or "plasma" in name else "pk_model_input"
    if "equation_variable" in role:
        return "equation_variable"
    if role == "calibration_or_validation_endpoint":
        return "calibration_or_validation_endpoint"
    if role.startswith("pd_") or "tumor" in name or "svegfr2" in name or "hazard" in name:
        return "pd_parameter"
    return role


def _context_summary(context: object) -> str:
    if not isinstance(context, ContextScope):
        return ""
    parts = [
        context.species,
        context.translation_stage,
        context.disease,
        context.disease_subtype,
        context.state,
        context.matrix,
        context.tissue_or_organ,
        context.model_system,
        context.drug_or_analyte,
    ]
    return "; ".join(part for part in parts if part)


def _markdown_report(combined: dict[str, JsonValue], graphs: tuple[CuratedPaperMoaGraph, ...]) -> str:
    tables = combined["tables"]
    if not isinstance(tables, dict):
        raise ValueError("Combined artifact tables were not generated.")
    edges = cast(list[dict[str, JsonValue]], tables["causal_edges"])
    parameters = cast(list[dict[str, JsonValue]], tables["parameters"])
    equations = cast(list[dict[str, JsonValue]], tables["equations"])
    contexts = cast(list[dict[str, JsonValue]], tables["contexts"])
    missing_inputs = cast(list[dict[str, JsonValue]], tables["missing_inputs"])
    provenance = cast(list[dict[str, JsonValue]], tables["provenance"])

    lines = [
        "# Paper Annotation MOA Graph Summary",
        "",
        "## Executive Summary",
        "",
        (
            "This is the final review artifact for the two paper annotation bundles. It keeps "
            "`PMC5131886` as a curated sunitinib/VEGFR2/HCC causal PK/PD/MOA graph and "
            "`PMC3693219` as a non-causal erlotinib PK/dosing/resistance overlay because no "
            "trusted top-level mechanism chains were available for causal extraction."
        ),
        "",
        "The artifacts remain non-executable review outputs. Runtime pathway loading is unchanged.",
        "",
        "## Per-Paper Graphs",
        "",
        _markdown_table(
            ("Paper", "Graph kind", "Nodes", "Edges", "Parameters", "Equations", "Interpretation"),
            [
                (
                    graph.paper_id,
                    graph.graph_kind,
                    str(len(graph.nodes)),
                    str(len(graph.edges)),
                    str(len(graph.parameters)),
                    str(len(graph.equations)),
                    _paper_interpretation(graph),
                )
                for graph in graphs
            ],
        ),
        "",
        "## Causal Edge Evidence",
        "",
        _markdown_table(
            ("Paper", "Edge", "Relation", "Role", "Support", "Status", "Evidence anchors"),
            [
                (
                    str(row["paper_id"]),
                    f"{row['source']} -> {row['target']}",
                    str(row["relation"]),
                    str(row["causal_role"]),
                    str(row["support_level"]),
                    str(row["review_status"]),
                    ", ".join(cast(list[str], row["evidence_anchor_ids"])),
                )
                for row in edges
            ],
        ),
        "",
        "## PK Parameter Evidence",
        "",
        _markdown_table(
            ("Paper", "Parameter", "Group", "Value", "Unit", "Target", "Status", "Blockers"),
            [
                _parameter_markdown_row(row)
                for row in parameters
                if str(row["parameter_group"]).startswith("pk")
            ],
        ),
        "",
        "## PD Parameter Evidence",
        "",
        _markdown_table(
            ("Paper", "Parameter", "Group", "Value", "Unit", "Target", "Status", "Blockers"),
            [
                _parameter_markdown_row(row)
                for row in parameters
                if str(row["parameter_group"]).startswith("pd")
                or row["parameter_group"] == "calibration_or_validation_endpoint"
            ],
        ),
        "",
        "## Equations And Model Forms",
        "",
        _markdown_table(
            ("Paper", "Equation", "Binding", "Target", "Status", "Model form"),
            [
                (
                    str(row["paper_id"]),
                    str(row["expression_text"]),
                    str(row["binding_type"]),
                    str(row["target_node_id"] or row["target_edge_id"] or ""),
                    str(row["review_status"]),
                    str(row["model_form"] or ""),
                )
                for row in equations
            ],
        ),
        "",
        "## Context And State",
        "",
        _markdown_table(
            ("Paper", "Species", "Stage", "Disease", "Subtype", "State", "Matrix/Tissue", "Model system", "Drug/analyte"),
            [
                (
                    str(row["paper_id"]),
                    str(row["species"] or ""),
                    str(row["translation_stage"] or ""),
                    str(row["disease"] or ""),
                    str(row["disease_subtype"] or ""),
                    str(row["state"] or ""),
                    _join_nonempty(row["matrix"], row["tissue_or_organ"]),
                    str(row["model_system"] or ""),
                    str(row["drug_or_analyte"] or ""),
                )
                for row in contexts
            ],
        ),
        "",
        "## Missing Inputs And Review Blockers",
        "",
        _markdown_table(
            ("Paper", "Missing input", "Severity", "Reason"),
            [
                (
                    str(row["paper_id"]),
                    str(row["name"]),
                    str(row["severity"] or ""),
                    str(row["reason"]),
                )
                for row in missing_inputs
            ],
        ),
        "",
        "## Provenance Coverage",
        "",
        (
            f"The combined artifact includes {len(provenance)} provenance rows. Each curated edge, "
            "parameter, and equation retains source record ids and evidence anchors."
        ),
        "",
        _markdown_table(
            ("Paper", "Item", "Source record", "Section", "Chunk/table/figure", "Evidence anchors"),
            [
                (
                    str(row["paper_id"]),
                    f"{row['item_type']}:{row['item_id']}",
                    f"{row['source_record_type']}:{row['source_record_id']}",
                    str(row["source_section"] or ""),
                    _join_nonempty(row["source_chunk_id"], row["source_table_or_figure"]),
                    ", ".join(cast(list[str], row["evidence_anchor_ids"])),
                )
                for row in provenance
            ],
        ),
        "",
        "## Primary JSON Artifact",
        "",
        "`data/curated_annotation_graphs/combined.paper_moa_graph.json`",
        "",
    ]
    return "\n".join(lines)


def _parameter_markdown_row(row: dict[str, JsonValue]) -> tuple[str, ...]:
    target = str(row["target_node_id"] or row["target_edge_id"] or "")
    blockers = ", ".join(cast(list[str], row["promotion_blockers"]))
    return (
        str(row["paper_id"]),
        str(row["name"]),
        str(row["parameter_group"]),
        "" if row["value"] is None else str(row["value"]),
        "" if row["unit"] is None else str(row["unit"]),
        target,
        str(row["review_status"]),
        blockers,
    )


def _markdown_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    if not rows:
        return "_No rows._"
    header = "| " + " | ".join(_cell(value) for value in headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join((header, separator, *body))


def _cell(value: str) -> str:
    return value.replace("|", "/").replace("\n", " ")


def _join_nonempty(*values: JsonValue) -> str:
    return "; ".join(str(value) for value in values if isinstance(value, str) and value)


if __name__ == "__main__":
    main()
