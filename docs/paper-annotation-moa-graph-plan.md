# Paper Annotation MOA Graph Implementation Plan

## Summary

The paper annotation JSON bundles should not replace the current EGFR/ERBB pathway graph directly. They are evidence inventories with extracted observations, mechanisms, equations, context, and provenance. The existing app runtime expects curated executable pathway definitions in `data/pathways/*.json`, with typed causal graph nodes, edges, state bindings, parameters, initial conditions, homeostasis terms, presentation metadata, and drug-effect patches.

The right implementation is a new annotation ingestion and mapping layer that can:

- Read paper annotation bundles from a data-owned location.
- Produce a paper-derived evidence graph and provenance index.
- Separate "evidence-supported causal claims" from "review-only observations" and "calibration endpoints."
- Optionally generate pathway patches or proposed pathway definitions after explicit curation.
- Keep the existing EGFR pathway as a curated executable model until enough annotation-backed evidence exists to support an executable replacement.

This document describes how to implement that layer without making runtime code depend on JSON files stored under `docs/`.

## Implementation Status

This plan is now implemented for the prototype as a review-artifact pipeline:

- Raw annotation bundles live under `data/paper_annotations/`.
- Data-owned context and proposal rules live under `data/annotation_rules/`.
- Evidence graph artifacts are generated under `data/annotation_graphs/`.
- Review-only pathway proposal artifacts are generated under `data/pathway_proposals/`.
- Importer code lives under `services/annotation_import/`.
- CLI entry points live under `scripts/import_paper_annotations.py`, `scripts/build_paper_evidence_graph.py`, and `scripts/propose_pathway_from_annotations.py`.
- Focused tests cover loading, source-of-truth handling, evidence graph generation, proposal generation, and runtime pathway isolation.

The implementation still does not promote generated proposals into executable runtime pathways, and it does not add API/UI surfaces. Those remain manual curation or future product work.

Production annotation-import code is intentionally generic. Paper-specific pathway IDs, overlay node match terms, disease/state term rules, and proposal classifications are configuration data under `data/annotation_rules/`, not Python branches.

## Storage Rule

Code should not read JSON annotation bundles from `docs/`.

`docs/` should remain for human-readable documentation, design notes, screenshots, and explanatory examples. If the application or import scripts need to consume the annotation bundles directly, the files should be moved into a data-owned directory as part of the implementation.

Recommended location:

```text
data/paper_annotations/
  PMC3693219.json
  PMC5131886.json
```

Alternative if we expect multiple versions/runs:

```text
data/paper_annotations/
  PMC3693219/
    scientific_bundle.json
    manifest.json
  PMC5131886/
    scientific_bundle.json
    manifest.json
```

The second layout is better if annotation pipelines will be rerun or if we need to retain model/version metadata. The first layout is acceptable for a small prototype.

Any future loader should use a constant such as:

```text
ANNOTATION_DIR = ROOT / "data" / "paper_annotations"
```

and should reject paths outside that directory unless an explicit one-off CLI argument is provided for local experimentation.

## Current Repository Constraints

The current runtime has three important constraints:

1. Pathway definitions are loaded from `data/pathways/*.json`.
2. Graphs are composed from pathway JSON through `services.pathway`.
3. The compiler expects a validated `MoAGraph`, not arbitrary annotation KG edges.

The existing EGFR pathway includes:

- executable states, such as `Drug`, `EGFR_total`, `pEGFR`, `pERK`, `pAKT`, and `Phenotype`
- causal graph edges with relation, sign, evidence, operator, and optional expression IR
- curated drug-effect patches targeting structural edges
- parameter priors and generated defaults
- initial conditions
- homeostasis terms
- presentation metadata

The annotation bundles include different kinds of objects:

- paper metadata
- paper-map context packs
- evidence anchors
- parameter candidates
- verified observations
- scientific symbols
- mechanism chains
- mechanism verifications
- equations
- simulation models and readiness plans
- KG projection nodes/edges

Those objects are useful, but they are not already an executable pathway.

## Source Of Truth Rule

Use the top-level typed arrays in each annotation bundle as the authoritative source for extraction:

- `mechanism_chains`
- `mechanism_verifications`
- `parameter_candidates`
- `verified_observations`
- `equations`
- `simulation_models`
- `simulation_parameters`
- `evidence_anchors`
- `simulation_readiness`

Treat `kg_projection` as a derived inspection/provenance projection only. It can be useful for debugging bundle generation, but importer output should not depend on it. It should not be used to create causal edges, mechanism nodes, verification counts, normalized disease/context fields, or executable pathway content.

This rule matters because `kg_projection` is a noisy superset:

- In `PMC3693219`, the top-level `mechanism_chains` array is empty, but `kg_projection` contains two `tktype:MechanismChain` fragments and three `tktype:MechanismVerification` nodes. The fragments are not usable causal mechanism records.
- In `PMC5131886`, the top-level arrays contain three mechanism chains, four mechanism steps, and four verifications. `kg_projection` contains five `tktype:MechanismChain` nodes and ten `tktype:MechanismVerification` nodes, including equation text and sentence fragments.
- Some projected ontology nodes are plainly wrong for context extraction, such as non-disease concepts projected as diseases.

Implementation rule:

```text
causal_edges = build_from(bundle.mechanism_chains)
verification_join = build_from(bundle.mechanism_verifications)
projection_edges = ignored_for_causal_extraction
```

## Interpretation Of The Provided Bundles

### `PMC3693219`

This paper is relevant to erlotinib, EGFR-mutant lung cancer, dosing schedules, PK effects, and acquired resistance. However, the annotation bundle does not provide enough mechanism structure to rebuild the EGFR causal pathway.

Important signals from the bundle:

- top-level mechanism chains: none
- top-level mechanism verifications: none
- equations: none
- simulation models: none
- simulation parameters: present, mostly figure-derived calibration or validation endpoints
- curated PD/MOA endpoint evidence: missing in the readiness summary
- mechanism or MOA: missing
- model structure: missing
- simulation readiness: blocked by missing evidence

`kg_projection` does contain mechanism-looking nodes for this paper, but they are noisy sentence fragments and must be ignored for causal extraction. The correct top-level result is zero accepted mechanism edges.

The bundle does contain dose, PK, toxicity, figure-derived calibration endpoints, and disease/context annotations. Many extracted inputs are review-only or unsafe for direct model use because units, subject scope, or claim support are incomplete.

Best use:

- Evidence overlay for an erlotinib resistance/dosing story.
- Source of dosing schedule candidates, PK exposure context, resistance-probability endpoints, plasma-concentration endpoints, and gaps.
- Not a source for replacing the EGFR pathway's biological signaling scaffold.

### `PMC5131886`

This paper is much more usable as a paper-derived MOA/PKPD evidence graph, but it describes sunitinib, VEGFR2, HCC, tumor growth inhibition, and time-to-tumor progression. It is not an EGFR replacement.

Important evidence:

- top-level mechanism content: three chains, four steps, and four verifications
- active sunitinib/metabolite concentration inhibits sVEGFR2 release/production
- sVEGFR2 dynamics link drug exposure to tumor growth inhibition
- delta sVEGFR2 inhibits the HCC tumor growth-rate constant
- TTP is modeled from biomarker exposure or hazard relationships
- some equations and model forms are present
- nine `simulation_models` records are present, but they are sparse
- sixty-eight `simulation_parameters` records contain the richer quantitative/model-structure extraction
- several PD parameters are present but still require review for exact values, units, and context

`kg_projection` has extra mechanism and verification nodes for this paper. Ignore those extras and join only the top-level `mechanism_verifications` records to top-level mechanism steps.

Best use:

- Separate sunitinib/VEGFR2/HCC paper-derived evidence graph.
- Candidate for a new non-EGFR pathway or evidence browser.
- Source of model equations and PD relationships after curation.

## Target Architecture

Add a new annotation ingestion subsystem that stays separate from the pathway runtime until curated output is generated.

Suggested package:

```text
services/annotation_import/
  __init__.py
  loader.py
  models.py
  provenance.py
  graph_builder.py
  rules.py
  pathway_patch.py       # review-only proposal generation
  validation.py
```

Suggested scripts:

```text
scripts/import_paper_annotations.py
scripts/build_paper_evidence_graph.py
scripts/propose_pathway_from_annotations.py
```

Suggested output locations:

```text
data/paper_annotations/          # raw annotation bundles
data/annotation_rules/           # data-owned context/proposal rules
data/annotation_graphs/          # normalized non-executable evidence graphs
data/pathway_proposals/          # generated review artifacts, not runtime pathways
```

Only curated pathway definitions should go into:

```text
data/pathways/
```

The first implementation slice builds the loader, models, provenance helpers, evidence graph builder, validation, and evidence graph script. The proposal generator remains downstream of evidence graph generation and writes review artifacts only.

## Data Model

Define internal Pydantic models for the subset of annotation fields we actually use. Do not model the full bundle initially.

Minimum models:

- `AnnotationBundle`
- `PaperInfo`
- `EvidenceAnchor`
- `MechanismChain`
- `MechanismStep`
- `MechanismVerification`
- `ParameterObservation`
- `EquationRecord`
- `SimulationModelRecord`
- `SimulationParameterRecord`
- `SimulationReadinessPlan`
- `ContextScope`
- `PaperProvenance`

The models should tolerate extra fields because the annotation bundles are large and likely to evolve.

Required normalized output model:

```text
PaperEvidenceGraph
  paper_id
  title
  nodes
  edges
  parameters
  equations
  simulation_models
  simulation_parameters
  evidence_anchors
  warnings
```

Where `nodes` and `edges` are evidence graph records, not necessarily executable `MoAGraph` records.

Each important node or edge should include:

- paper id
- source object id, such as mechanism chain id, observation id, equation id
- evidence anchor ids
- quoted or summarized evidence text
- section/chunk/table/figure provenance when available
- context fields: species, clinical/preclinical/in vitro, disease, state, assay, tissue, matrix, drug/analyte
- validation status
- confidence or trust level
- review status

`SimulationParameterRecord` should preserve the annotation role rather than flattening all values into ordinary parameters. Expected roles include:

- `model_structure`
- `equation_variable`
- `model_input`
- `calibration_or_validation_endpoint`

For `PMC3693219`, the calibration/validation endpoints are the main data path for the erlotinib dosing/resistance overlay. For `PMC5131886`, `simulation_parameters` are the main path for model quantities, equation variables, model inputs, and digitized endpoints; `simulation_models` provide useful anchors such as model type and platform, but are not rich enough by themselves.

## Graph Types

Use two distinct graph concepts.

### 1. Paper Evidence Graph

This is a provenance-rich graph generated from annotations. It can include:

- drug nodes
- biomarker nodes
- target/pathway nodes
- disease/context nodes
- model quantity nodes
- parameter nodes
- equation nodes
- evidence anchor nodes

Edges can represent:

- causal mechanism steps, such as `inhibits`, `activates`, or `drives`
- model-derived relationships
- parameter-for relationships
- equation-defines relationships
- has-context relationships
- has-evidence relationships

This graph does not need executable state bindings.

### 2. Executable Pathway Graph

This is the current `MoAGraph`/`PathwayDefinition` format. It requires:

- executable state bindings
- valid source and target references
- one evidence entry per non-hypothesis edge
- parameter priors or generated defaults
- initial conditions
- compile-compatible relation/operator/expression choices

Only curated or explicitly accepted annotation-derived claims should become executable pathway graph edges.

## Mapping Rules

### Mechanism Chains To Evidence Edges

For each mechanism step:

1. Consume provided `normalized_subject` and `normalized_object` records when present.
2. Map predicate to a relation.
3. Preserve the original predicate in metadata.
4. Attach evidence anchors.
5. Attach verification verdict by joining top-level verification records on `(mechanism_chain_id, mechanism_step_id)`.
6. Attach context: species, disease, assay, clinical/preclinical state, and state labels.

Do not source mechanism steps or verification records from `kg_projection`.

Normalization rule:

- Use the bundle-provided normalized entity id, label, ontology/source, and match score.
- Apply a match-score gate before using normalized entities for canonical graph ids.
- If the normalized entity is missing or below threshold, retain the raw label and mark the node for review.
- Do not perform a second free-form normalization pass as part of the initial importer.

Example from `PMC5131886`:

```text
sunitinib_active_concentration --inhibits--> sVEGFR2_release
```

Metadata:

```text
paper_id: PMC5131886
mechanism_chain_id: moa:PMC5131886:e759bfdd41c057e9
mechanism_step_id: step:PMC5131886:05f1ecda4b6b0995
verification_id: top-level mechanism verification matching the chain and step ids
verification_verdict: verified_therapeutic_moa
relation_class: drug_target_or_pathway_moa
evidence_anchor_ids:
  - anchor:PMC5131886:chunk_001:moa5
context:
  species: human
  disease: HCC
  setting: clinical
```

### Parameters

Parameter observations should not automatically become `ParameterPrior` records.

Promote a parameter only if:

- validation status is verified
- value is numeric
- unit is present when required
- drug/analyte or biological target scope is clear
- species/context is clear enough for the model
- source evidence is primary or supporting, not only background
- the parameter maps to a known model quantity

Otherwise, keep it in the evidence graph as a review-only parameter.

For `PMC3693219`, most dose and PK values should remain review-only until units and context are corrected. For `PMC5131886`, several PD table values need manual table-cell review before promotion because some extracted values appear to reflect definition text or row parsing rather than the actual estimate.

### Simulation Models And Simulation Parameters

Do not ignore the `simulation_models` and `simulation_parameters` arrays. They carry much of the quantitative content that is absent from ordinary mechanism chains.

Use `simulation_models` to capture:

- model type, such as population PK model or PKPD model
- platform, when present, such as Monolix
- model-level context and anchor ids
- links to equations or parameter groups when present

Use `simulation_parameters` to capture:

- compartments and analytes
- equation variables and linked equation ids
- model inputs
- calibration or validation endpoints, especially digitized figure points
- values, units, source figures/tables, and extraction warnings

These records should become evidence graph records first. Promotion into executable parameters requires the same numeric/unit/context review as ordinary parameter observations.

### Equations

Equations should first be stored as display/model-form records:

```text
equation_id
expression_text
variables
model_type
evidence_anchor_ids
validation_status
```

Do not immediately convert them into executable expression IR. The current expression IR supports a useful subset, but the paper equations may need:

- ODE state mapping
- compartment naming
- unit reconciliation
- parameter binding
- initial conditions
- dosing input definition
- time-varying exposure inputs

After curation, an equation can become:

- a display-only equation attached to a graph edge
- a homeostasis term
- an edge expression override
- a new model module

### Species And Context

Every important edge and parameter should carry context metadata. Minimum context fields:

```text
species
translation_stage
disease
disease_subtype
state
assay
matrix
tissue_or_organ
cell_line
model_system
drug_or_analyte
source_section
source_anchor_ids
```

Use conservative values:

- If the paper says patients, use `human` and `clinical`.
- If the paper mentions mice or xenograft, use `mouse`, `xenograft`, and `preclinical`.
- If the context is unclear, set `unknown` or omit the field and add a warning.

Do not infer species from ontology normalization alone.

## Proposed Implementation Phases

### Phase 1: Move Data And Add Loader

Status: required first implementation slice.

Actions:

1. Create `data/paper_annotations/`.
2. Move annotation JSON bundles out of `docs/`.
3. Add a loader under `services/annotation_import/loader.py`.
4. Add tests proving the loader reads from `data/paper_annotations/` and not from `docs/`.

Expected behavior:

- `load_annotation_bundle("PMC3693219")` reads `data/paper_annotations/PMC3693219.json`.
- Unknown paper ids raise a clear error.
- The loader does not accept path traversal.
- The loader does not scan `docs/`.

### Phase 2: Build A Paper Evidence Graph

Status: required first implementation slice.

Actions:

1. Define normalized evidence graph models.
2. Convert top-level mechanism chains into evidence edges.
3. Join top-level mechanism verifications by `(mechanism_chain_id, mechanism_step_id)`.
4. Convert parameter observations into parameter nodes.
5. Convert simulation models and simulation parameters into evidence graph records.
6. Convert equations into equation nodes.
7. Attach provenance and evidence anchors.
8. Emit warnings for unsupported or unsafe records.
9. Emit warnings when `kg_projection` contains mechanism-like records that were intentionally ignored.

Output:

```text
data/annotation_graphs/PMC3693219.evidence_graph.json
data/annotation_graphs/PMC5131886.evidence_graph.json
```

This output is reviewable and can be displayed or inspected without claiming executability.

### Phase 3: Add Review Classification

Status: early follow-up. This can be implemented with Phase 2 if it stays small, but it should not expand into pathway generation.

Classify every extracted edge/parameter/equation as one of:

```text
accepted_for_evidence_graph
candidate_for_pathway_patch
review_only
rejected
```

Suggested rules:

- Verified therapeutic MOA edges can be candidates.
- Model-derived PD relations can be candidates, but should be marked as model-derived.
- Paper-supported-only claims stay evidence graph entries unless manually promoted.
- Missing units or missing biological scope forces review-only.
- Background-only parameter evidence forces review-only.
- Unsupported or mis-normalized entities force review-only.

### Phase 4: Generate Pathway Proposals, Not Runtime Pathways

Status: implemented as review artifact generation. Runtime promotion remains deferred.

Generate files under `data/pathway_proposals/`, for example:

```text
data/pathway_proposals/PMC5131886.new_pathway.proposal.json
data/pathway_proposals/PMC3693219.overlay.proposal.json
```

These should be explicit review artifacts. They should not be loaded by the app until accepted and copied into `data/pathways/`.

Proposal content:

- proposed nodes
- proposed causal edges
- proposed parameters
- proposed equations/model forms
- required missing inputs
- provenance for each proposed item
- reasons why each item is or is not executable

The proposal generator should be driven by the evidence graph records, especially `simulation_models` and `simulation_parameters`, rather than by a hand-written scaffold. Hand-written scaffold examples in this document are illustrative only.

Proposal classification and paper-specific target IDs should be read from `data/annotation_rules/proposals/{paper_id}.json`. Context term extraction rules should be read from `data/annotation_rules/context/default.json`. If no proposal rule exists, the generic fallback is conservative: candidate mechanism edges may produce a new-pathway review proposal, and papers without candidate edges remain evidence-only.

### Phase 5: Optional EGFR Overlay

Status: implemented as a review-only overlay proposal. Runtime modification of `egfr_erbb_demo` remains deferred.

For `PMC3693219`, create an overlay proposal rather than a replacement graph.

Possible overlay nodes:

- Erlotinib exposure
- dosing schedule
- smoker/fast metabolizer state
- nonsmoker/slow metabolizer state
- sensitive tumor cell population
- resistant tumor cell population
- probability of acquired resistance

Possible overlay evidence:

- dose schedule candidates
- plasma concentration figure-derived endpoints
- resistant population figure-derived endpoints
- review gaps for model equations and PK parameters

This overlay should not modify the current EGFR signaling graph automatically. It can be a separate evidence layer or a proposed module requiring curation.

### Phase 6: Optional Sunitinib/VEGFR2/HCC Pathway

Status: implemented as a review-only new-pathway proposal. Runtime pathway promotion remains deferred.

For `PMC5131886`, a new pathway proposal is more appropriate.

Possible executable scaffold after curation:

```text
Sunitinib_dose
Sunitinib_plasma
SU12662_plasma
Active_unbound_concentration
sVEGFR2
Delta_sVEGFR2
Tumor_growth_rate
Tumor_volume
TTP_hazard
TTP_probability
```

Possible causal edges:

```text
Sunitinib_plasma + SU12662_plasma -> Active_unbound_concentration
Active_unbound_concentration inhibits sVEGFR2 production
sVEGFR2 dynamics influence Delta_sVEGFR2
Delta_sVEGFR2 inhibits Tumor_growth_rate
Tumor_growth_rate drives Tumor_volume
sVEGFR2 exposure drives TTP_hazard or TTP_probability
```

This should be a separate pathway id, such as:

```text
sunitinib_vegfr2_hcc_demo
```

not a replacement for:

```text
egfr_erbb_demo
```

## API And UI Considerations

Do not mix paper evidence graphs into existing pathway endpoints immediately.

Defer new API endpoints and UI screens until the Phase 1 and Phase 2 evidence graph output is useful enough to inspect repeatedly. For the first slice, command-line generation plus JSON review artifacts are sufficient.

Potential new API endpoints:

```text
GET /annotation-bundles
GET /annotation-bundles/{paper_id}
GET /annotation-graphs/{paper_id}
GET /pathway-proposals
GET /pathway-proposals/{proposal_id}
```

Potential UI views:

- evidence graph viewer
- mechanism chain table
- parameter evidence table
- equation/model-form table
- provenance inspector
- pathway proposal review page

The existing graph compose, compile, and simulate endpoints should continue to operate only on valid pathway definitions and composed `MoAGraph` objects.

## Validation Strategy

Add validation at three levels.

### Loader Validation

- file exists under `data/paper_annotations`
- JSON is parseable
- required top-level fields exist
- paper id matches filename

### Evidence Graph Validation

- every evidence edge has paper provenance
- every mechanism-derived edge has at least one evidence anchor
- every mechanism-derived edge comes from top-level `mechanism_chains`, not `kg_projection`
- every verification verdict is joined from top-level `mechanism_verifications` by chain id and step id
- every parameter node has source observation or candidate id
- every simulation parameter record preserves its role and source id
- every equation node has source equation id and expression text
- records with missing unit/context are marked review-only

### Pathway Proposal Validation

- every proposed executable edge maps to valid proposed nodes
- every proposed executable parameter has value, unit, source, and context
- every proposed equation references known states/parameters or is display-only
- missing required model inputs are listed explicitly
- no proposal is silently promoted into `data/pathways`

## Testing Plan

Add focused unit tests:

```text
tests/test_annotation_loader.py
tests/test_annotation_evidence_graph.py
tests/test_annotation_pathway_proposal.py
```

Key tests:

- loader rejects reading from `docs/`
- loader reads valid bundles from `data/paper_annotations/`
- `PMC3693219` produces zero accepted mechanism edges from top-level `mechanism_chains` and warns that projection mechanism fragments were ignored
- `PMC5131886` produces four top-level mechanism-step evidence records for sunitinib/sVEGFR2/TGI/TTP relationships
- `PMC5131886` ignores the extra mechanism and verification nodes in `kg_projection`
- verification verdicts are attached only by exact `(mechanism_chain_id, mechanism_step_id)` joins
- parameters missing units or context are review-only
- simulation parameters are preserved with role, value, unit, source id, and review status
- equations remain display/model-form records unless explicitly curated
- generated pathway proposals are not listed by `list_pathways()`
- annotation-import production code does not hardcode paper-specific pathway IDs, drug names, disease names, or overlay node IDs

Existing pathway runtime tests should remain unchanged.

## Provenance Requirements

Every important item should preserve:

```text
paper_id
paper_title
source_record_type
source_record_id
evidence_anchor_ids
source_section
source_chunk_id
source_table_or_figure
quote_or_sentence
simulation_model_id
simulation_parameter_id
verification_id
verification_verdict
relation_class
validation_status
trust_level
warnings
```

For executable pathway promotion, provenance should be represented in the existing `Evidence` shape:

```text
source_type: paper
source_label: PMC5131886
description: short evidence summary
reference: evidence anchor or paper id
confidence: numeric confidence if available
```

Additional details can go in edge metadata extension.

## Migration Plan For Existing Files

When implementation starts:

1. Create `data/paper_annotations/`.
2. Move:

```text
docs/PMC3693219.json -> data/paper_annotations/PMC3693219.json
docs/PMC5131886.json -> data/paper_annotations/PMC5131886.json
```

3. Update any documentation references to point to `data/paper_annotations/`.
4. Add `.gitignore` rules only if future bundles are too large or generated locally.
5. Keep this document in `docs/` as the human-readable plan.

Do not add application code that opens `docs/PMC3693219.json` or `docs/PMC5131886.json`.

## Recommended Near-Term Scope

Start with non-executable evidence graph generation.

Do not attempt to create a fully executable pathway in the first implementation step. The most valuable first deliverable is a transparent evidence graph that shows:

- what causal MOA claims were extracted
- which claims have verification support
- which parameters are usable versus review-only
- which equations or model forms exist
- which species/context/state fields support each item
- where the missing evidence blocks simulation

Concretely, Phase 1 and Phase 2 are the foundation. Pathway proposal generation should remain downstream of the generated evidence graph. API endpoints, UI views, and runtime promotion should remain deferred until the review statuses are credible.

After that, use `PMC5131886` as a candidate for a new sunitinib/VEGFR2/HCC pathway proposal. Use `PMC3693219` as an erlotinib resistance/dosing overlay proposal on top of, or adjacent to, the existing EGFR pathway.

## Non-Goals

This implementation should not:

- auto-replace `egfr_erbb_demo`
- treat annotation KG edges as executable pathway edges without curation
- source causal mechanism records from `kg_projection`
- re-normalize entities when the bundle already provides a sufficient normalized entity and match score
- infer missing species or disease context from weak ontology matches
- promote parameters with missing units or unclear scope
- compile paper equations into executable IR without state and parameter binding review
- read runtime data from `docs/`
- hardcode paper-specific pathway IDs, disease terms, drug terms, or overlay-node matching in production annotation-import code

## Final Recommendation

Implement annotation ingestion as a curation and provenance layer first. Keep the current EGFR pathway as the executable demo. Move raw annotation bundles to `data/paper_annotations/` before any code consumes them. Build paper evidence graphs and pathway proposals as separate artifacts, then manually promote only the supported and reviewed pieces into executable pathway definitions.
