# Executable Paper MOA Graph Roadmap

## Purpose

This document describes what is required to turn the paper-annotation MOA review artifacts into executable pathway models.

The annotation-import review artifacts are intentionally non-executable. They preserve evidence, context, parameters, model forms, and provenance from:

- `data/paper_annotations/PMC3693219.json`
- `data/paper_annotations/PMC5131886.json`

The primary current outputs are:

- `data/curated_annotation_graphs/combined.paper_moa_graph.json`
- `data/curated_annotation_graphs/PMC3693219.curated_moa_graph.json`
- `data/curated_annotation_graphs/PMC5131886.curated_moa_graph.json`
- `docs/paper-annotation-moa-graph-summary.md`

The first hand-curated runtime pathway derived from those artifacts is:

- `data/pathways/sunitinib_vegfr2_hcc_demo.json`
- `tests/test_executable_paper_moa_pathway.py`

The review artifacts answer: "What causal, PK, PD, context, equation, and provenance evidence did the annotations contain?"

Executable pathway artifacts must answer a stricter question: "Can the graph be loaded, compiled into executable equations, simulated, and interpreted without relying on unresolved review-only assumptions?"

## Implementation Status

As of June 8, 2026, the first executable slice is implemented for `PMC5131886` as `sunitinib_vegfr2_hcc_demo`.

What is executable now:

- normalized active sunitinib/SU12662 exposure
- plasma sVEGFR2 biomarker response
- Delta sVEGFR2 relaxation approximation
- tumor growth-rate signal suppression
- normalized tumor-volume endpoint

What remains deferred:

- full parent/metabolite PK
- oral repeated dosing
- dimensional unit reconciliation
- calibration against figure-derived endpoints
- TTP hazard and TTP probability
- automatic promotion from annotation graph to runtime pathway JSON

Validation currently covered by tests:

- pathway loading and pathway registry exposure
- context, endpoint, state, and parameter source checks
- paper provenance on runtime nodes and edges
- compile without error-severity warnings
- executable expression IR only
- finite nonnegative simulation output
- expected PD directionality under active exposure
- `PMC3693219` remains non-promoted as a runtime pathway

One runtime cleanup was also needed: compiler logic-check merging is now idempotent by check id, because composed graph metadata and pathway definitions can both carry the same pathway-owned logic checks.

## Current State

### Review Artifact Status

The annotation-import pipeline has two layers:

1. Evidence graph generation from top-level annotation arrays.
2. Curated paper MOA graph generation from paper-specific rule files.

The evidence graph builder consumes top-level records such as:

- `mechanism_chains`
- `mechanism_verifications`
- `parameter_candidates`
- `observations`
- `equations`
- `simulation_models`
- `simulation_parameters`
- `evidence_anchors`
- `simulation_readiness_plans`

It intentionally ignores `kg_projection` as a source for causal extraction because the projection contains noisy or duplicated mechanism-like fragments.

The curated graph layer then selects and organizes a subset of the evidence graph into review artifacts with nodes, causal/model edges, parameters, equations, contexts, evidence anchors, and provenance.

### Paper-Specific Status

#### `PMC5131886`

This is the viable source for the first executable paper-derived pathway.

Current curated graph:

- Graph kind: `curated_moa`
- Nodes: 17
- Edges: 10
- Parameters: 30
- Equations/model forms: 7
- Candidate causal edges: 6
- Runtime executable: `false`

The curated graph itself remains a review artifact. The implemented runtime subset is `data/pathways/sunitinib_vegfr2_hcc_demo.json`.

Current prioritized chain:

```text
sunitinib_dose
  -> sunitinib_plasma
  -> active_unbound_concentration
  -> sVEGFR2 production/release
  -> sVEGFR2 plasma biomarker
  -> Delta_sVEGFR2
  -> tumor_growth_rate
  -> tumor_volume
  -> ttp_hazard
  -> ttp_probability
```

The implemented executable subset is:

```text
active_unbound_concentration inhibits sVEGFR2 production
sVEGFR2 production drives sVEGFR2 biomarker
sVEGFR2 biomarker defines Delta_sVEGFR2
Delta_sVEGFR2 inhibits tumor_growth_rate
tumor_growth_rate drives tumor_volume
```

The TTP hazard and TTP probability edges remain deferred until we support the needed hazard/AUC/time-to-event model forms.

#### `PMC3693219`

This paper should not be promoted directly into an executable causal MOA pathway from the current annotation bundle.

Current curated graph:

- Graph kind: `overlay`
- Nodes: 13
- Edges: 0
- Parameters: 20
- Equations/model forms: 0
- Runtime executable: `false`

Reason:

- No trusted top-level `mechanism_chains`.
- No top-level mechanism verifications.
- No extracted equations.
- No explicit model structure.
- Many values are dosing, exposure, resistance, or figure-derived calibration endpoints.

Best executable use later:

- A dosing/resistance calibration overlay for an already curated EGFR/erlotinib model.
- Not a standalone causal MOA pathway unless additional trusted mechanism/model evidence is added.

## What "Executable" Means

There are three different bars. We should be explicit about which one we are targeting.

### 1. Loadable Pathway Definition

A loadable pathway is a JSON file under:

```text
data/pathways/
```

It must validate as `PathwayDefinition`.

This requires:

- `pathway_id`
- `label`
- `context`
- `base_graph`
- `parameters`
- `initial_conditions`
- optional `homeostasis`
- optional `modules`
- optional `drug_effects`
- optional `presentation`
- optional `prediction`
- metadata

This is the lowest executable bar. It proves that the runtime can load the artifact, but it does not prove the pathway compiles or simulates well.

### 2. Compilable Graph

A compilable graph must pass:

```text
compose_graph(...) -> MoAGraph
compile_graph(...) -> CompiledModel
```

This requires:

- every executable node has a unique `state` binding
- every edge source and target resolves to a node or edge as appropriate
- every non-hypothesis edge has evidence
- edge signs are compatible with relations
- every executable state has an initial condition
- every homeostasis term and edge expression references known states and parameters
- generated parameters either have defaults or are supplied before simulation

This proves that we can transform the pathway into executable equation IR.

### 3. Simulation-Ready Model

A simulation-ready model must pass:

```text
validate_simulation_ready(...)
simulate(...)
```

This requires:

- no display-only expressions in executable state equations
- no missing required parameter priors
- no expressions referencing states outside the model
- ODE solve behavior that is numerically stable enough for intended use
- biologically interpretable outputs

This is the real target if we want to use the graph for prediction, dose-response exploration, or mechanistic comparison.

## Runtime Schema Requirements

An executable paper-derived pathway must be converted into the pathway runtime schema, not just a curated annotation schema.

### Nodes

Current curated graph nodes need to become runtime `Node` records.

Each executable node needs:

- stable `id`
- human-readable `label`
- node `type`
- optional aliases
- optional roles, including `drug` for the exposure/drug node
- `state` binding if it participates in simulation
- metadata with paper provenance and source ids

Example runtime node shape:

```json
{
  "id": "ActiveExposure",
  "label": "Active unbound sunitinib plus SU12662 exposure",
  "type": "pk_exposure",
  "roles": ["drug"],
  "state": {
    "id": "ActiveExposure",
    "executable": true,
    "initial": 0.0
  },
  "metadata": {
    "extension": {
      "paper_id": "PMC5131886",
      "curated_node_id": "active_unbound_concentration"
    }
  }
}
```

### Edges

Curated paper MOA edges need to become runtime `Edge` records.

Each executable edge needs:

- stable `id`
- source node id
- target node id or target edge id
- relation
- sign
- confidence
- evidence
- operator
- expression IR or a relation/operator that the compiler can convert into generic IR
- provenance metadata

Important relation/sign notes:

- `inhibits` must use negative sign.
- `activates`, `drives_phenotype`, and similar positive relations must use positive sign.
- Custom relation strings that are not in the runtime sign vocabulary return unknown sign unless the edge explicitly supplies a compatible sign.
- If a relation is semantically causal but unsupported by compiler defaults, either map it to an existing relation/operator or add compiler support.

Candidate mappings:

| Curated relation | Executable relation | Notes |
| --- | --- | --- |
| `inhibits` | `inhibits` | Supported as a negative causal relation. |
| `drives` | `activates` or `drives_phenotype` | Pick based on target state meaning. |
| `contributes_to` | `activates` | Use only if it can be represented as positive source contribution. |
| `defines_change_from_baseline` | derived/algebraic expression or state update | Not directly supported as a structural causal relation. |
| `predicts` | defer or map to display-only | TTP hazard prediction is not currently simulation-ready. |

### Evidence

Runtime `Evidence` should retain paper provenance.

Minimum fields:

- `source_type: "paper"`
- `source_label`, for example `PMC5131886`
- `description`, using a concise evidence summary
- `reference`, ideally paper URL or paper id
- `confidence`

Put detailed provenance in metadata:

- source record ids
- evidence anchor ids
- section
- chunk id
- table or figure id
- quote or sentence
- verification id
- verification verdict
- review status
- curation rationale

### Parameters

Runtime parameters must be `ParameterPrior` records.

Each executable expression parameter needs:

- id
- numeric value
- optional lower and upper bounds
- units
- source evidence

Review-only parameters cannot be used directly. They need manual promotion or explicit defaulting.

Current blocker:

- All curated parameters are currently marked `review_only`.
- Several values are figure-derived calibration endpoints, not true priors.
- Several model inputs or equation variables have missing values or missing units.

### Initial Conditions

Every executable state must have a nonnegative initial condition.

Options:

1. Use paper-supported baseline values where available.
2. Normalize states to baseline value `1.0`.
3. Use `0.0` for inactive drug/exposure states.
4. Use small positive values for states that cannot start at zero without eliminating dynamics.

Initial conditions must be documented as one of:

- paper-supported
- derived from paper value
- normalized assumption
- expert assumption
- generated default for prototype execution

### Homeostasis Terms

The current compiler can compile structural edge terms, but realistic ODE behavior usually needs homeostasis terms for production, degradation, removal, relaxation, and baseline turnover.

For a sunitinib/sVEGFR2/tumor-volume executable slice, likely terms are:

- exposure elimination or constant exposure input
- sVEGFR2 zero-order production
- sVEGFR2 first-order removal
- tumor-volume baseline growth
- tumor-volume loss or net-growth modulation

Without homeostasis, the compiled model may load and run but produce meaningless drift or one-way accumulation.

### Presentation Metadata

To make the executable pathway usable in the existing app, add:

- plot states
- endpoint states
- graph layout
- node type styles
- edge relation styles
- named configurations

Minimum plot states for a first slice:

- `ActiveExposure`
- `sVEGFR2`
- `DeltaSVEGFR2`
- `TumorGrowthRate`
- `TumorVolume`

## Scientific Curation Required Before Promotion

### Parameter Promotion

Each parameter should move through this decision:

```text
raw annotation record
  -> curated review parameter
  -> manually reviewed executable prior
  -> runtime ParameterPrior
```

Promotion criteria:

- numeric value is verified
- unit is known and compatible with the state scale
- target node or edge is known
- species/context is compatible with the executable model
- source evidence is primary paper evidence or explicitly accepted supporting evidence
- not merely a calibration endpoint unless intentionally used for calibration
- provenance is retained

Important `PMC5131886` parameters needing review:

- sunitinib dose regimen
- parent sunitinib concentration records
- SU12662 concentration records
- active unbound concentration formula inputs
- free fractions for parent and metabolite
- sVEGFR2 baseline `R0`
- sVEGFR2 production/removal rates, such as `kin` and `kout`
- Delta sVEGFR2 effect parameters, such as `IC50`
- tumor growth-rate parameters, such as `kg` and `kd`
- hazard model variables and coefficients, if TTP is included

### Equation Promotion

Each equation/model form should move through this decision:

```text
display/model-form text
  -> curated mathematical form
  -> expression IR
  -> compiled state equation or edge expression
```

Current equations/model forms:

- Active unbound concentration calculation.
- sVEGFR2 indirect response model.
- Delta sVEGFR2 from baseline.
- Tumor growth-rate effect model.
- TTP hazard model.
- PK compartment rate relation for `k10`.
- PK compartment rate relation for `k21`.

Promotion recommendations:

- Promote active unbound exposure only if free fractions and concentration state definitions are curated.
- Promote sVEGFR2 indirect response only after `kin`, `kout`, and exposure effect form are fixed.
- Promote Delta sVEGFR2 either as an explicit state or by extending runtime support for derived algebraic variables.
- Promote tumor growth effect only after choosing the tumor-volume state equation.
- Defer TTP hazard until the expression IR supports hazard/AUC/time-to-event terms.
- Preserve malformed PK equation text as evidence until corrected manually.

### Context Promotion

Every executable pathway should have a coherent context:

- species: likely `human`
- translation stage: `clinical`
- disease: `HCC`
- disease subtype: `advanced HCC`, if used
- model system: clinical PK/PD model
- matrix: plasma for sVEGFR2 and drug/metabolite concentration states
- tissue: tumor for tumor-volume state

Current issue:

Some context rows inherit noisy fields from evidence anchors, such as `western_blot`, `xenograft`, or mixed tissue labels in otherwise clinical rows. Before execution, contexts should be curated into a single coherent model context plus state-specific metadata.

## Recommended First Executable Slice

The first executable slice should be deliberately smaller than the full curated review graph.

### Scope

Create:

```text
data/pathways/sunitinib_vegfr2_hcc_demo.json
```

Do not include:

- `PMC3693219` as an executable pathway.
- TTP hazard/probability.
- full oral dosing schedules.
- full two-compartment PK unless parameters are manually curated.

### State Variables

Suggested first executable states:

| State | Meaning | Initial condition |
| --- | --- | --- |
| `ActiveExposure` | normalized active unbound exposure | `0.0` |
| `sVEGFR2` | normalized plasma sVEGFR2 biomarker | `1.0` |
| `DeltaSVEGFR2` | normalized change from baseline | `0.0` |
| `TumorGrowthRate` | normalized tumor growth-rate signal | `1.0` |
| `TumorVolume` | normalized tumor volume | `1.0` |

Possible non-executable or metadata-only nodes:

- `SunitinibDose`
- `SunitinibPlasma`
- `SU12662Plasma`
- `TTPHazard`
- `TTPProbability`

### Causal Edges

Suggested first executable edges:

```text
ActiveExposure inhibits sVEGFR2
sVEGFR2 drives DeltaSVEGFR2
DeltaSVEGFR2 inhibits TumorGrowthRate
TumorGrowthRate drives TumorVolume
```

This is a simplified executable chain. It should explicitly note that:

- active exposure is normalized
- parent/metabolite PK is collapsed into one exposure state
- TTP is omitted
- parameter values are prototype priors unless manually reviewed

### Candidate Expressions

Use supported expression IR only.

Example active exposure loss:

```text
dActiveExposure/dt = -kel_active * ActiveExposure
```

Example sVEGFR2 dynamics:

```text
dsVEGFR2/dt = kin_svegfr2 * inhibition(ActiveExposure, K_active_svegfr2) - kout_svegfr2 * sVEGFR2
```

Example Delta sVEGFR2 approximation:

```text
dDeltaSVEGFR2/dt = k_delta * max-like response from baseline difference
```

Current expression IR does not support `max` or direct algebraic state assignment, so a first implementation would need either:

- a relaxation term that drives `DeltaSVEGFR2` from `sVEGFR2`, or
- an expression IR extension for derived/algebraic states.

Example tumor-growth signal:

```text
dTumorGrowthRate/dt = baseline recovery - inhibition_by_DeltaSVEGFR2
```

Example tumor volume:

```text
dTumorVolume/dt = kg_effect * TumorVolume
```

This may require allowing signed growth terms carefully so negative values do not cause invalid state behavior. The current simulator clips state values at zero, but that should not be the primary safety mechanism.

## Required Code Work

### Phase 1: Manual Executable Pathway JSON

Status: complete for the first normalized `PMC5131886` slice.

Create a hand-curated pathway file first. Do not generate it automatically yet.

Tasks:

1. Add `data/pathways/sunitinib_vegfr2_hcc_demo.json`.
2. Define a small base graph with executable states.
3. Add runtime evidence records with paper provenance.
4. Add parameter priors.
5. Add initial conditions.
6. Add homeostasis terms.
7. Add presentation metadata.
8. Add a default configuration.

Validation:

```bash
uv run --locked python - <<'PY'
from services.pathway.loader import load_pathway
load_pathway("sunitinib_vegfr2_hcc_demo")
PY
```

### Phase 2: Compose And Compile

Status: complete for the first normalized `PMC5131886` slice.

Tasks:

1. Compose the graph through `compose_graph`.
2. Compile with `compile_graph`.
3. Inspect warnings.
4. Add missing generated parameter defaults or explicit priors.
5. Ensure all state equations use executable expression IR.

Validation:

```bash
uv run --locked python - <<'PY'
from services.domain import PathwayId
from services.pathway.composer import compose_graph
from services.pathway.models import GraphComposeRequest
from services.pathway.loader import load_pathway
from services.equation_compiler.compiler import compile_graph

request = GraphComposeRequest(pathway_id=PathwayId("sunitinib_vegfr2_hcc_demo"))
graph = compose_graph(request)
pathway = load_pathway("sunitinib_vegfr2_hcc_demo")
model = compile_graph(graph, pathway)
print(model.graph_id)
print([w.message for w in model.warnings])
PY
```

### Phase 3: Simulate

Status: complete for the first normalized `PMC5131886` slice.

Tasks:

1. Validate simulation readiness.
2. Run a short normalized simulation.
3. Check that active exposure suppresses sVEGFR2.
4. Check that sVEGFR2 suppression reduces tumor-growth signal.
5. Check that tumor-volume behavior is stable and interpretable.

Validation:

```bash
uv run --locked python - <<'PY'
from services.domain import PathwayId, SimulationInput, SimulationSettings
from services.pathway.composer import compose_graph
from services.pathway.models import GraphComposeRequest
from services.pathway.loader import load_pathway
from services.equation_compiler.compiler import compile_graph
from services.simulator.validation import validate_simulation_ready
from services.simulator.simulate import simulate

request = GraphComposeRequest(pathway_id=PathwayId("sunitinib_vegfr2_hcc_demo"))
graph = compose_graph(request)
model = compile_graph(graph, load_pathway("sunitinib_vegfr2_hcc_demo"))
errors = validate_simulation_ready(model)
if errors:
    raise SystemExit([error.message for error in errors])
result = simulate(SimulationInput(model=model, settings=SimulationSettings(t_end=48, n_points=121)))
print(result.graph_id)
print([(summary.state, summary.final_fraction_change_from_baseline) for summary in result.summaries])
PY
```

### Phase 4: Add Tests

Status: complete for the first normalized `PMC5131886` slice.

Add focused tests rather than broad snapshot checks.

Suggested tests:

1. Runtime pathway list includes `sunitinib_vegfr2_hcc_demo`.
2. Pathway JSON validates as `PathwayDefinition`.
3. Composed graph has expected nodes, edges, and endpoint states.
4. Every executable edge has paper evidence and provenance metadata.
5. `compile_graph` returns no error-severity warnings.
6. `validate_simulation_ready` returns no errors.
7. A treated simulation produces finite nonnegative series.
8. Active exposure changes sVEGFR2 in the expected direction.
9. Tumor-volume output is finite and stable across the default run.
10. `PMC3693219` remains non-executable unless an explicit executable pathway file is added.

### Phase 5: Optional Generator

Status: not started.

Only after the hand-curated pathway is stable should we add a generator from curated annotation graph to pathway JSON.

Generator inputs:

- curated graph artifact
- executable curation rule file
- parameter promotion decisions
- state mapping rules
- equation IR mappings
- context normalization choices

Generator output:

- a runtime pathway JSON draft under a non-runtime review location first, for example:

```text
data/pathway_proposals/sunitinib_vegfr2_hcc.executable_pathway.proposal.json
```

Promotion into `data/pathways/` should remain manual.

## Required Scientific Decisions

These decisions should be recorded before the first executable pathway is merged.

### State Scale

Choose one:

1. Fully dimensional states.
2. Normalized baseline-relative states.
3. Hybrid, with exposure dimensional and PD states normalized.

Recommendation for first slice:

- Use normalized baseline-relative PD states.
- Use normalized active exposure.
- Preserve dimensional values as evidence metadata and calibration targets, not direct state values.

### Exposure Model

Choose one:

1. Constant exposure.
2. Bolus exposure with first-order elimination.
3. Full oral repeated dosing.
4. Two-compartment parent/metabolite PK.

Recommendation for first slice:

- Use normalized bolus or constant active exposure.
- Defer parent/metabolite PK until parameter values are manually curated.

### Delta sVEGFR2 Handling

Choose one:

1. Make `DeltaSVEGFR2` an explicit executable state with relaxation dynamics.
2. Add expression IR support for algebraic derived variables.
3. Remove `DeltaSVEGFR2` as a state and connect `sVEGFR2` directly to tumor growth.

Recommendation for first slice:

- Use explicit state with simple relaxation if we want a graph node.
- Otherwise connect `sVEGFR2` directly to tumor-growth inhibition and keep Delta as evidence metadata.

### TTP Handling

Choose one:

1. Defer TTP completely.
2. Represent TTP as display-only endpoint metadata.
3. Extend expression IR for hazard and AUC.

Recommendation for first slice:

- Defer TTP execution.
- Keep TTP hazard/probability in curated review artifacts.

### Tumor Growth Model

Choose one:

1. Use a simple exponential tumor-volume model.
2. Use logistic or carrying-capacity dynamics.
3. Use paper-specific tumor growth inhibition equation after manual curation.

Recommendation for first slice:

- Use a normalized simple growth model with explicit caveats.
- Promote paper-specific model only after verifying parameter values and units.

## Required Runtime Extensions For Full Paper Fidelity

The first executable slice can avoid runtime extensions. Full fidelity likely needs these additions.

### Expression IR Extensions

Potential new expression nodes:

- exponential function, for TTP hazard
- logarithm, if model equations require it
- min/max or clamp
- algebraic derived variables
- time variable reference
- AUC/integral state helper
- piecewise or event-based dosing functions

### Dosing Support

Potential simulator additions:

- repeated oral dosing
- absorption compartment
- bioavailability
- lag time
- parent/metabolite conversion
- schedule definitions, such as daily, weekly pulse, withdrawal, maintenance

### Parameter Estimation Or Calibration

Potential fitting workflow:

- mark figure-derived endpoints as calibration targets
- fit uncertain parameters to endpoint records
- preserve posterior or fitted priors
- separate fitted values from paper-observed priors

### Unit System

Potential unit workflow:

- normalize units during import
- store original units
- store executable units
- validate unit compatibility for expressions
- fail promotion if unit conversion is ambiguous

## Why `PMC3693219` Should Stay Non-Executable For Now

`PMC3693219` contains useful erlotinib evidence:

- dosing schedules
- plasma concentration endpoints
- half-life candidates
- elimination-rate constants
- smoker/nonsmoker exposure differences
- resistance probability endpoints
- resistant and sensitive tumor population endpoints
- withdrawal and pulse-dose scenarios

But it lacks the minimum information needed for a standalone executable causal MOA model:

- no top-level mechanism chains
- no top-level mechanism verifications
- no equations
- no named simulation model
- no trusted model structure
- no model-safe PK exposure parameter set

Executable use should wait until one of these is available:

1. a curated erlotinib/EGFR runtime pathway already exists and the paper is added as calibration/overlay evidence
2. additional paper evidence supplies mechanism chains and model equations
3. a manual expert-curated model structure is accepted as an assumption

## Provenance Requirements For Executable Promotion

Every executable edge, parameter, equation, initial condition, and homeostasis term should carry provenance.

Minimum provenance metadata:

```json
{
  "paper_id": "PMC5131886",
  "curated_graph_id": "curated:PMC5131886:sunitinib_vegfr2_hcc_moa",
  "source_record_ids": ["step:PMC5131886:27fa15d47ecb84da"],
  "evidence_anchor_ids": ["anchor:PMC5131886:figure_001:moa5"],
  "source_section": "Figure 1",
  "source_chunk_id": "figure_001",
  "source_table_or_figure": "figure_001",
  "verification_verdict": "model_derived_pd_relation",
  "review_status": "candidate_for_pathway_patch",
  "curation_note": "Accepted as executable after manual review."
}
```

If a runtime value is an assumption rather than directly paper-supported, record:

- assumption type
- reason
- reviewer
- date or version
- affected state/edge/parameter
- evidence that motivated the assumption

## Acceptance Criteria

The first executable pathway should be considered complete only when all criteria below pass.

### Structural Acceptance

- A new pathway JSON exists under `data/pathways/`.
- It validates as `PathwayDefinition`.
- It appears in `list_pathways()`.
- `compose_graph()` succeeds.
- All graph edges resolve to known nodes or edges.
- All non-hypothesis executable edges have evidence.

### Compilation Acceptance

- `compile_graph()` succeeds.
- Compiled model contains executable expression IR.
- No error-severity warnings are emitted.
- Every generated parameter has a prior, default, or required override.
- Every executable state has an initial condition.

### Simulation Acceptance

- `validate_simulation_ready()` returns no errors.
- `simulate()` runs with default settings.
- Timecourse values are finite and nonnegative.
- Treated and untreated simulations differ in expected states.
- Biological logic checks pass or warnings are documented.

### Scientific Acceptance

- State definitions are documented.
- Unit conventions are documented.
- Parameter priors are reviewed and traceable.
- Calibration endpoints are not mislabeled as priors.
- Simplifications are explicitly listed.
- TTP and omitted PK components are listed as deferred work.

## Suggested Implementation Order

Completed for the first slice:

1. Create a hand-curated `sunitinib_vegfr2_hcc_demo` pathway JSON with normalized states.
2. Use only the active-exposure to sVEGFR2 to tumor-volume subset.
3. Preserve all paper provenance in evidence and metadata.
4. Add parameter priors as explicit prototype assumptions where paper values are not safe.
5. Compile and simulate the pathway.
6. Add tests for load, compose, compile, simulate, and expected directionality.

Remaining:

1. Revisit parameter values and equations with manual scientific review.
2. Add generator support only after the manual pathway is stable.
3. Extend expression IR and dosing support if full PK/TTP fidelity is required.

## Bottom Line

The current artifacts are sufficient to justify a paper-derived executable prototype for `PMC5131886`, but not sufficient to auto-promote the full graph. The implemented first executable model is a deliberately small, normalized, manually curated sunitinib/VEGFR2/HCC pathway that preserves provenance and marks assumptions clearly.

`PMC3693219` should remain a non-executable erlotinib PK/dosing/resistance overlay until additional mechanism and model-structure evidence is curated.
