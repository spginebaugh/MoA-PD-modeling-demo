# Paper Annotation MOA Graph Completion Audit

## Purpose

This document originally tracked the work still needed to satisfy the paper-derived MOA graph requirement for:

- `data/paper_annotations/PMC3693219.json`
- `data/paper_annotations/PMC5131886.json`

It now records the implemented state and the remaining non-required follow-up options. The requirement was to use the annotation files to build a causal MOA graph that includes mechanism relationships, PK/PD parameters, species/context/state, equations or model forms, and paper/chunk provenance, while prioritizing causal MOA evidence rather than listing associations.

## Implemented Outputs

Primary final artifacts:

- `data/curated_annotation_graphs/combined.paper_moa_graph.json`
- `docs/paper-annotation-moa-graph-summary.md`

Supporting generated artifacts:

- `data/annotation_graphs/PMC3693219.evidence_graph.json`
- `data/annotation_graphs/PMC5131886.evidence_graph.json`
- `data/curated_annotation_graphs/PMC3693219.curated_moa_graph.json`
- `data/curated_annotation_graphs/PMC5131886.curated_moa_graph.json`
- `data/pathway_proposals/PMC3693219.overlay.proposal.json`
- `data/pathway_proposals/PMC5131886.new_pathway.proposal.json`

The combined artifact is the easiest JSON file to inspect. The markdown summary is the easiest reviewer-facing deliverable.

## Current Coverage

The generated combined artifact contains:

| Measure | Count |
| --- | ---: |
| Papers | 2 |
| Curated paper graphs | 2 |
| Causal edges | 10 |
| Parameters | 50 |
| Equations/model forms | 7 |
| Context rows | 70 |
| Provenance rows | 88 |

Parameter groups now represented:

| Group | Count |
| --- | ---: |
| `pk_model_input` | 9 |
| `pk_exposure_endpoint` | 12 |
| `pk_equation_variable` | 7 |
| `pk_model_structure` | 4 |
| `pd_parameter` | 3 |
| `pd_model_input` | 2 |
| `pd_model_structure` | 1 |
| `pd_endpoint` | 4 |
| `pd_equation_variable` | 2 |
| `calibration_or_validation_endpoint` | 5 |
| `review_only_candidate_input` | 1 |

## Paper-Specific Result

### `PMC5131886`

`PMC5131886` is the paper with a curated causal PK/PD/MOA graph.

Implemented graph shape:

- Graph kind: `curated_moa`
- Nodes: 17
- Edges: 10
- Parameters: 30
- Equations/model forms: 7
- Candidate pathway-patch causal edges: 6
- Runtime executable: `false`

Prioritized causal chain:

```text
sunitinib_dose
  -> sunitinib_plasma
  -> active_unbound_concentration
  -> sVEGFR2 production/release
  -> sVEGFR2 plasma biomarker
  -> delta_sVEGFR2
  -> tumor_growth_rate
  -> tumor_volume
  -> ttp_hazard
  -> ttp_probability
```

The strongest promoted causal edges are the model-supported exposure-to-biomarker and biomarker-to-tumor-growth relationships:

- `sunitinib_plasma -> active_unbound_concentration`
- `su12662_plasma -> active_unbound_concentration`
- `active_unbound_concentration inhibits svegfr2_production`
- `svegfr2_production -> svegfr2_biomarker`
- `svegfr2_biomarker -> delta_svegfr2`
- `delta_svegfr2 inhibits tumor_growth_rate`

The TTP and tumor-volume edges remain review-only where the evidence supports model linkage but not a fully executable pathway binding.

### `PMC3693219`

`PMC3693219` is intentionally represented as an erlotinib PK/dosing/resistance overlay, not as a promoted causal MOA graph.

Implemented graph shape:

- Graph kind: `overlay`
- Nodes: 13
- Edges: 0
- Parameters: 20
- Equations/model forms: 0
- Runtime executable: `false`

This paper has no trusted top-level `mechanism_chains` in the annotation bundle. Mechanism-looking fragments from `kg_projection` remain ignored by design, so no causal MOA edges are promoted. The overlay still surfaces the relevant PK, dosing, resistance, smoker/nonsmoker, pulse dosing, withdrawal, half-life, elimination-rate, Cmax, and tumor-population evidence as review-only records with provenance.

## Requirement Mapping

### Mechanism Of Action Relationships

Implemented:

- `PMC5131886` contains 10 curated mechanism/model edges, with 6 prioritized as `candidate_for_pathway_patch`.
- Each curated edge has source record ids, evidence anchors, provenance, context, causal role, support level, review status, and rationale.
- `PMC3693219` has 0 promoted causal edges because the required top-level mechanism source evidence is absent.

### PK Parameters And Source Evidence

Implemented:

- `PMC3693219` now includes standard dose, high-dose pulse, 300 mg/day dose, 50 mg/day maintenance endpoint, plasma concentration endpoints, Cmax endpoints, half-life candidates, smoker/nonsmoker endpoints, and elimination-rate constants.
- `PMC5131886` now includes dose, parent/metabolite plasma endpoints, observed/predicted exposure endpoints, population PK model structure, PKPD model structure, Monolix platform, plasma compartment, and CL/V1/Q/V2/k10/k12/k21 equation-variable records.
- All unsafe, figure-derived, incomplete, or unit-ambiguous records are marked `review_only` with promotion blockers.

### PD Parameters And Source Evidence

Implemented:

- `PMC3693219` includes resistance probability, resistant/sensitive population endpoints, pulse-resistance probability, and withdrawal population endpoint.
- `PMC5131886` includes sVEGFR2 baseline, delta sVEGFR2 effect IC50, active-concentration slope effect, kd review candidate, observed/predicted sVEGFR2 endpoints, tumor-volume endpoints, and hazard equation variables.
- PD records are bound to the relevant node or edge and retain anchors/provenance.

### Species, Context, And Biological State

Implemented:

- Curated nodes, edges, parameters, and equations now require species/stage/model-system context or an explicit warning path.
- The curated artifacts include human clinical context for both papers where supported.
- Disease/state context is represented where annotated, including HCC, advanced HCC, EGFR-mutant lung cancer, baseline, treated, resistant, sensitive population, smoker/nonsmoker, pulse dosing, withdrawal, and placebo/untreated contexts.
- `docs/paper-annotation-moa-graph-summary.md` includes a reviewer-facing context/state table.

### Equations And Model Forms

Implemented:

- `PMC5131886` has 7 connected equation/model-form records:
  - Active unbound concentration calculation.
  - sVEGFR2 indirect response model.
  - Delta sVEGFR2 definition.
  - Tumor growth-rate effect model.
  - TTP hazard model.
  - PK compartment rate relation `k10 = CL/V1 k12`.
  - PK compartment rate relation `k21 = Q/V2`.
- Equations are bound to relevant nodes or edges and remain non-executable review artifacts.
- The malformed or incomplete extracted PK equation text is flagged for manual review.
- `PMC3693219` has no extracted equations, which is preserved as a missing-input condition rather than invented.

### Paper/Chunk Provenance

Implemented:

- The primary artifact uses `CuratedPaperMoaGraph`, preserving all provenance records rather than relying on the lighter `PathwayProposal` provenance shape.
- Every curated edge, parameter, and equation must have evidence anchors and provenance.
- Source record ids now fail validation if they cannot be resolved.
- The summary report includes a provenance coverage section and table with paper, item, source record, source section, chunk/table/figure, and evidence anchors.

## Code And Validation Changes

Implemented changes:

- Expanded curated graph rules in:
  - `data/annotation_rules/curated_graphs/PMC3693219.json`
  - `data/annotation_rules/curated_graphs/PMC5131886.json`
- Strengthened source resolution and validation in:
  - `services/annotation_import/curated_graph_builder.py`
  - `services/annotation_import/validation.py`
- Added combined artifact/report generation in:
  - `scripts/build_paper_moa_graph_summary.py`
- Updated tests for expanded graph coverage and summary artifact validation in:
  - `tests/test_curated_paper_moa_graph.py`
  - `tests/test_annotation_pathway_proposal.py`

The stricter validation now rejects missing curated source records and requires anchors, provenance, and species/stage/model-system context for important curated records unless an explicit warning explains the exception.

## Verification

Regenerated artifacts with:

```bash
uv run --locked python scripts/build_paper_evidence_graph.py
uv run --locked python scripts/build_curated_paper_moa_graph.py
uv run --locked python scripts/propose_pathway_from_annotations.py
uv run --locked python scripts/build_paper_moa_graph_summary.py
```

Verified with:

```bash
uv run --locked pytest -q
make typecheck
```

Results:

- `37` tests passed.
- `basedpyright` reported `0 errors, 0 warnings, 0 notes`.

## What Still Needs To Do

No required implementation work remains for the stated graph-building requirement.

Optional future work:

- Add a UI review surface for the combined artifact.
- Expand `PathwayProposal` to preserve multiple provenance records if a downstream consumer needs proposals to be the authoritative artifact.
- Manually curate executable parameter bindings, units, state variables, dosing inputs, and initial conditions before promoting any record into runtime pathways.
- Promote a subset of `PMC5131886` only after manual scientific review. The generated artifacts intentionally remain non-executable.

## Non-Goals Preserved

The implementation still does not:

- Promote generated proposals into `data/pathways/`.
- Treat `kg_projection` fragments as trusted causal mechanism records.
- Replace the runtime `egfr_erbb_demo` pathway.
- Compile extracted equations into executable expression IR.
- Promote parameters with missing units, unclear scope, or figure-only calibration status as model-safe priors.
- Infer missing species or disease context from weak ontology normalization.
