# Paper Annotation MOA Graph Summary

## Executive Summary

This is the final review artifact for the two paper annotation bundles. It keeps `PMC5131886` as a curated sunitinib/VEGFR2/HCC causal PK/PD/MOA graph and `PMC3693219` as a non-causal erlotinib PK/dosing/resistance overlay because no trusted top-level mechanism chains were available for causal extraction.

The artifacts remain non-executable review outputs. Runtime pathway loading is unchanged.

## Per-Paper Graphs

| Paper | Graph kind | Nodes | Edges | Parameters | Equations | Interpretation |
| --- | --- | --- | --- | --- | --- | --- |
| PMC3693219 | overlay | 13 | 0 | 20 | 0 | No trusted top-level mechanism chains were available, so this graph is an erlotinib PK/dosing/resistance overlay with no promoted causal MOA edges. |
| PMC5131886 | curated_moa | 17 | 10 | 30 | 7 | Curated sunitinib PK/PD/MOA chain connects active exposure to sVEGFR2 suppression, tumor-growth inhibition, and time-to-tumor-progression model outputs. |

## Causal Edge Evidence

| Paper | Edge | Relation | Role | Support | Status | Evidence anchors |
| --- | --- | --- | --- | --- | --- | --- |
| PMC5131886 | sunitinib_dose -> sunitinib_plasma | drives | dosing_to_parent_exposure | review_only_context | review_only | anchor:PMC5131886:chunk_002:s15m1 |
| PMC5131886 | sunitinib_plasma -> active_unbound_concentration | contributes_to | parent_concentration_to_active_unbound_exposure | model_form_supported | candidate_for_pathway_patch | anchor:PMC5131886:figure_001:moa5, anchor:PMC5131886:figure_002:figure |
| PMC5131886 | su12662_plasma -> active_unbound_concentration | contributes_to | metabolite_concentration_to_active_unbound_exposure | model_form_supported | candidate_for_pathway_patch | anchor:PMC5131886:figure_001:moa5, anchor:PMC5131886:figure_002:figure |
| PMC5131886 | active_unbound_concentration -> svegfr2_production | inhibits | exposure_to_biomarker_production | model_derived_pd_relation | candidate_for_pathway_patch | anchor:PMC5131886:figure_001:moa5, anchor:PMC5131886:chunk_001:moa5 |
| PMC5131886 | svegfr2_production -> svegfr2_biomarker | drives | biomarker_process_to_measured_biomarker | model_form_supported | candidate_for_pathway_patch | anchor:PMC5131886:figure_001:moa5, anchor:PMC5131886:figure_002:figure |
| PMC5131886 | svegfr2_biomarker -> delta_svegfr2 | defines_change_from_baseline | biomarker_to_baseline_delta | model_form_supported | candidate_for_pathway_patch | anchor:PMC5131886:figure_001:moa6, anchor:PMC5131886:figure_002:figure |
| PMC5131886 | delta_svegfr2 -> tumor_growth_rate | inhibits | biomarker_delta_to_tumor_growth_rate | model_derived_pd_relation | candidate_for_pathway_patch | anchor:PMC5131886:figure_001:moa6, anchor:PMC5131886:table_002:r5c1, anchor:PMC5131886:chunk_019:s7m1 |
| PMC5131886 | tumor_growth_rate -> tumor_volume | drives | growth_rate_to_tumor_volume_endpoint | model_endpoint_supported | review_only | anchor:PMC5131886:chunk_019:sim9, anchor:PMC5131886:figure_002:figure |
| PMC5131886 | delta_svegfr2 -> ttp_hazard | predicts | biomarker_exposure_to_ttp_hazard | model_form_supported | review_only | anchor:PMC5131886:table_002:r10c1, anchor:PMC5131886:supplementary_061:eq12_1 |
| PMC5131886 | ttp_hazard -> ttp_probability | drives | hazard_to_time_to_event_endpoint | model_form_supported | review_only | anchor:PMC5131886:supplementary_061:eq12_1 |

## PK Parameter Evidence

| Paper | Parameter | Group | Value | Unit | Target | Status | Blockers |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PMC3693219 | Standard erlotinib daily dose | pk_model_input | 150.0 | mg/day | dosing_schedule | review_only | route_interval_scope_requires_review |
| PMC3693219 | High-dose pulse erlotinib | pk_model_input | 1600.0 | mg | dosing_schedule | review_only | schedule_scope_requires_review |
| PMC3693219 | Erlotinib plasma concentration endpoint | pk_exposure_endpoint | 4.0 | uM | erlotinib_exposure | review_only | calibration_endpoint_not_parameter_prior |
| PMC3693219 | Erlotinib half-life candidate 18 h | pk_model_input | 18.0 | h | erlotinib_half_life | review_only | population_scope_requires_review |
| PMC3693219 | Erlotinib half-life candidate 40 h | pk_model_input | 40.0 | h | erlotinib_half_life | review_only | population_scope_requires_review |
| PMC3693219 | Elimination rate constant - smokers 150 mg | pk_model_input | 0.106 | h^-1 | erlotinib_elimination_rate_constant | review_only | figure_derived_pk_parameter_needs_review |
| PMC3693219 | Elimination rate constant - smokers 300 mg | pk_model_input | 0.085 | h^-1 | erlotinib_elimination_rate_constant | review_only | figure_derived_pk_parameter_needs_review |
| PMC3693219 | Elimination rate constant - nonsmokers 150 mg | pk_model_input | 0.051 | h^-1 | erlotinib_elimination_rate_constant | review_only | figure_derived_pk_parameter_needs_review |
| PMC3693219 | Elimination rate constant - nonsmokers 300 mg | pk_model_input | 0.042 | h^-1 | erlotinib_elimination_rate_constant | review_only | figure_derived_pk_parameter_needs_review |
| PMC3693219 | Hamilton et al Cmax endpoint | pk_exposure_endpoint | 3.3 | uM | erlotinib_cmax_endpoint | review_only | calibration_endpoint_not_parameter_prior |
| PMC3693219 | Trial 248-005 Cmax endpoint | pk_exposure_endpoint | 22.7 | uM | erlotinib_cmax_endpoint | review_only | calibration_endpoint_not_parameter_prior |
| PMC3693219 | Smoker 150 mg plasma endpoint | pk_exposure_endpoint | 3.0 | uM | smoker_exposure_context | review_only | calibration_endpoint_not_parameter_prior |
| PMC3693219 | Nonsmoker 150 mg plasma endpoint | pk_exposure_endpoint | 4.0 | uM | nonsmoker_exposure_context | review_only | calibration_endpoint_not_parameter_prior |
| PMC3693219 | 50 mg/day erlotinib concentration endpoint | pk_exposure_endpoint | 1.6 | uM | dosing_schedule | review_only | calibration_endpoint_not_parameter_prior |
| PMC5131886 | Sunitinib dose regimen | pk_model_input | 50.0 | mg/day | sunitinib_dose | review_only | route_schedule_context_requires_manual_review |
| PMC5131886 | Sunitinib plasma concentration endpoint | pk_exposure_endpoint | 15.0 | ug/L | sunitinib_plasma | review_only | calibration_endpoint_not_parameter_prior |
| PMC5131886 | SU12662 plasma concentration endpoint | pk_exposure_endpoint | 13.0 | ug/L | su12662_plasma | review_only | calibration_endpoint_not_parameter_prior |
| PMC5131886 | Population PK model structure | pk_model_structure |  |  | pk_model_structure | review_only | model_structure_not_parameter_prior |
| PMC5131886 | PKPD model structure | pk_model_structure |  |  | pk_model_structure | review_only | model_structure_not_parameter_prior |
| PMC5131886 | Monolix model platform | pk_model_structure |  |  | pk_model_structure | review_only | platform_not_parameter_prior |
| PMC5131886 | Plasma compartment | pk_model_structure |  |  | plasma_compartment | review_only | model_structure_not_parameter_prior |
| PMC5131886 | CL equation variable | pk_equation_variable |  |  | pk_equation_variables | review_only | missing_value, missing_unit, equation_variable_not_parameter_prior |
| PMC5131886 | V1 equation variable | pk_equation_variable |  |  | pk_equation_variables | review_only | missing_value, missing_unit, equation_variable_not_parameter_prior |
| PMC5131886 | Q equation variable | pk_equation_variable |  |  | pk_equation_variables | review_only | missing_value, missing_unit, equation_variable_not_parameter_prior |
| PMC5131886 | V2 equation variable | pk_equation_variable |  |  | pk_equation_variables | review_only | missing_value, missing_unit, equation_variable_not_parameter_prior |
| PMC5131886 | k10 equation variable | pk_equation_variable |  |  | pk_equation_variables | review_only | missing_value, missing_unit, equation_variable_not_parameter_prior |
| PMC5131886 | k12 equation variable | pk_equation_variable |  |  | pk_equation_variables | review_only | missing_value, missing_unit, equation_variable_not_parameter_prior |
| PMC5131886 | k21 equation variable | pk_equation_variable |  |  | pk_equation_variables | review_only | missing_value, missing_unit, equation_variable_not_parameter_prior |
| PMC5131886 | Observed sunitinib plasma concentration endpoint | pk_exposure_endpoint | 180.0 | ug/L | sunitinib_plasma | review_only | calibration_endpoint_not_parameter_prior |
| PMC5131886 | Predicted sunitinib plasma concentration endpoint | pk_exposure_endpoint | 150.0 | ug/L | sunitinib_plasma | review_only | calibration_endpoint_not_parameter_prior |
| PMC5131886 | Observed SU12662 plasma concentration endpoint | pk_exposure_endpoint | 53.0 | ug/L | su12662_plasma | review_only | calibration_endpoint_not_parameter_prior |
| PMC5131886 | Predicted SU12662 plasma concentration endpoint | pk_exposure_endpoint | 30.0 | ug/L | su12662_plasma | review_only | calibration_endpoint_not_parameter_prior |

## PD Parameter Evidence

| Paper | Parameter | Group | Value | Unit | Target | Status | Blockers |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PMC3693219 | Probability of acquired resistance endpoint | calibration_or_validation_endpoint | 6e-06 |  | resistance_probability | review_only | missing_model_structure, calibration_endpoint_not_parameter_prior |
| PMC3693219 | Resistant tumor cell population endpoint | calibration_or_validation_endpoint | 5000.0 | cells | resistant_population | review_only | calibration_endpoint_not_parameter_prior |
| PMC3693219 | Sensitive tumor cell population endpoint | calibration_or_validation_endpoint | 550000.0 | cells | sensitive_population | review_only | calibration_endpoint_not_parameter_prior |
| PMC3693219 | 1600 mg/wk resistance probability endpoint | calibration_or_validation_endpoint | 0.5 |  | resistance_probability | review_only | missing_unit, calibration_endpoint_not_parameter_prior |
| PMC3693219 | Withdrawal total population endpoint | calibration_or_validation_endpoint | 360000.0 | cells | withdrawal_schedule | review_only | calibration_endpoint_not_parameter_prior |
| PMC5131886 | sVEGFR2 baseline level | pd_parameter | 18.3 | ug/L | delta_svegfr2 | review_only | needs_table_figure_reconciliation, validation_status_needs_review |
| PMC5131886 | Delta sVEGFR2 effect IC50 | pd_parameter | 1.83 | L | curated_edge:PMC5131886:delta_svegfr2_inhibits_tumor_growth_rate | review_only | unit_or_table_row_semantics_uncertain |
| PMC5131886 | Slope hazard Delta AUC0-24h sVEGFR2 | pd_parameter | 0.03 |  | curated_edge:PMC5131886:delta_svegfr2_predicts_ttp_hazard | review_only | missing_unit |
| PMC5131886 | Tumor compartment | pd_model_structure |  |  | tumor_compartment | review_only | model_structure_not_parameter_prior |
| PMC5131886 | Slope effect of active concentration on sVEGFR2 | pd_model_input | 2.0 | L | curated_edge:PMC5131886:active_unbound_inhibits_svegfr2_production | review_only | unit_or_table_row_semantics_uncertain |
| PMC5131886 | kd review-only candidate | pd_model_input | 4.0 |  | tumor_growth_rate | review_only | missing_unit, pd_scope_requires_review |
| PMC5131886 | Observed sVEGFR2 plasma endpoint | pd_endpoint | 36.0 | ug/L | svegfr2_endpoint_family | review_only | calibration_endpoint_not_parameter_prior |
| PMC5131886 | Predicted sVEGFR2 plasma endpoint | pd_endpoint | 18.0 | ug/L | svegfr2_endpoint_family | review_only | calibration_endpoint_not_parameter_prior |
| PMC5131886 | Observed tumor volume endpoint | pd_endpoint | 370.0 | mm3 | tumor_volume_endpoint_family | review_only | calibration_endpoint_not_parameter_prior |
| PMC5131886 | Placebo tumor volume endpoint | pd_endpoint | 960.0 | mm3 | tumor_volume_endpoint_family | review_only | calibration_endpoint_not_parameter_prior |
| PMC5131886 | Z2 AUC hazard equation variable | pd_equation_variable |  |  | ttp_hazard | review_only | missing_value, missing_unit, equation_variable_not_parameter_prior |
| PMC5131886 | AUC hazard equation variable | pd_equation_variable |  |  | ttp_hazard | review_only | missing_value, missing_unit, equation_variable_not_parameter_prior |

## Equations And Model Forms

| Paper | Equation | Binding | Target | Status | Model form |
| --- | --- | --- | --- | --- | --- |
| PMC5131886 | ACub = fub_D * C_D + fub_M * C_M | equation_defines_node | active_unbound_concentration | candidate_for_pathway_patch | active unbound parent plus metabolite exposure calculation |
| PMC5131886 | dR/dt = kin * (1 - E_ACub) - kout * R | equation_parameterizes_edge | curated_edge:PMC5131886:active_unbound_inhibits_svegfr2_production | review_only | indirect response model with zero-order production and first-order removal |
| PMC5131886 | Delta_sVEGFR2 = sVEGFR2 - R0 | equation_defines_node | delta_svegfr2 | candidate_for_pathway_patch | difference from baseline biomarker concentration |
| PMC5131886 | kg_effect = kg * inhibition(Delta_sVEGFR2) | equation_parameterizes_edge | curated_edge:PMC5131886:delta_svegfr2_inhibits_tumor_growth_rate | review_only | tumor growth inhibition model driven by delta sVEGFR2 |
| PMC5131886 | DDT_Hazard = Z0* exp ( Z1*TTP+Z2*AUC) | equation_defines_hazard | ttp_hazard | review_only | TTP hazard model using TTP and AUC terms |
| PMC5131886 | k10 = CL/V1 k12 | model_form_for_node | sunitinib_plasma | review_only | PK compartment rate relation |
| PMC5131886 | k21 = Q/V2 | model_form_for_node | sunitinib_plasma | review_only | PK compartment rate relation |

## Context And State

| Paper | Species | Stage | Disease | Subtype | State | Matrix/Tissue | Model system | Drug/analyte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated | plasma | clinical PK/model-derived simulation | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated |  | clinical/model-derived dosing | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | resistant | plasma | model-derived resistance simulation | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | resistant | plasma | model-derived tumor population simulation | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated | plasma | model-derived tumor population simulation | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer | EGFR-mutant |  |  | clinical |  |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated | plasma | clinical PK/model-derived simulation | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated | plasma; tumor, plasma | model-derived dosing simulation | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated, withdrawal | plasma | model-derived dosing simulation | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated | plasma | clinical PK/model-derived simulation | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated |  | clinical PK | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated | plasma; plasma | clinical PK/model-derived simulation | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated | plasma; tumor, plasma | clinical/model-derived dosing | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated | plasma; tumor, plasma | model-derived dosing simulation | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated | plasma | clinical PK/model-derived simulation | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | resistant | plasma | model-derived tumor population simulation | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated | plasma | model-derived tumor population simulation | Erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated |  | clinical PK | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated |  | clinical PK | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated | plasma | clinical PK/model-derived simulation | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated |  | clinical/model-derived dosing | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated | plasma | model-derived dosing simulation | erlotinib |
| PMC3693219 | human | clinical | EGFR-mutant lung cancer |  | treated, withdrawal | plasma | model-derived tumor population simulation | erlotinib |
| PMC5131886 | human | clinical | HCC | advanced HCC | treated | kidney, tumor | clinical | sunitinib |
| PMC5131886 | human | clinical | HCC |  | treated | plasma | clinical | sunitinib |
| PMC5131886 | human | clinical | HCC |  | treated | plasma | clinical | SU12662 |
| PMC5131886 | human | clinical | HCC |  | treated |  | clinical | sunitinib, SU12662 |
| PMC5131886 | human | clinical | HCC |  | treated |  | clinical |  |
| PMC5131886 | human | clinical | HCC |  | treated | plasma | clinical | sVEGFR2 |
| PMC5131886 | human | clinical | HCC |  | baseline, treated | plasma | clinical | sVEGFR2 |
| PMC5131886 | human | clinical | HCC |  | baseline, treated |  | clinical |  |
| PMC5131886 | human | clinical | HCC |  | treated | tumor | clinical |  |
| PMC5131886 | human | clinical | HCC |  | treated |  | clinical |  |
| PMC5131886 | human | clinical | HCC |  | treated |  | population PK/PKPD model |  |
| PMC5131886 | human | clinical | HCC |  | treated |  | population PK model |  |
| PMC5131886 | human | clinical | HCC |  | treated | plasma | population PK model |  |
| PMC5131886 | human | clinical | HCC |  | treated | tumor | PKPD/tumor growth model |  |
| PMC5131886 | human | clinical | HCC |  | treated | plasma | clinical PKPD model | sVEGFR2 |
| PMC5131886 | human | clinical | HCC |  | treated | plasma; tumor | clinical PKPD/tumor growth model | sunitinib |
| PMC5131886 | human | clinical | HCC |  | treated | kidney, tumor | clinical |  |
| PMC5131886 | human | clinical | HCC |  | treated | plasma | clinical | sunitinib |
| PMC5131886 | human | clinical | HCC |  | treated |  | clinical |  |
| PMC5131886 | human | clinical | HCC |  | baseline, treated | plasma | clinical |  |
| PMC5131886 | human | clinical | HCC |  | baseline, treated |  | clinical |  |
| PMC5131886 | human | clinical | HCC |  | treated |  | clinical |  |
| PMC5131886 | human | clinical | HCC |  | treated | tumor | clinical |  |
| PMC5131886 | human | clinical | HCC |  | treated |  | clinical |  |
| PMC5131886 | human | clinical | HCC |  | treated | kidney, tumor |  | sunitinib |
| PMC5131886 | human | clinical | HCC |  | baseline | plasma; plasma, tumor | clinical | sVEGFR2 |
| PMC5131886 | human | clinical | HCC |  | treated |  | cmc_formulation |  |
| PMC5131886 | human | clinical | HCC |  | treated | tumor |  |  |
| PMC5131886 | human | clinical | HCC |  | treated |  | population PK model |  |
| PMC5131886 | human | clinical | HCC |  | treated |  | PKPD model |  |
| PMC5131886 | human | clinical | HCC |  | treated |  | Monolix |  |
| PMC5131886 | human | clinical | HCC |  | treated | plasma | population PK model |  |
| PMC5131886 | human | clinical | HCC |  | treated | tumor | PKPD/tumor growth model |  |
| PMC5131886 | human | clinical | HCC |  | treated |  | population PK model |  |
| PMC5131886 | human | clinical | HCC |  | treated |  | population PK model |  |
| PMC5131886 | human | clinical | HCC |  | treated | plasma | clinical PK/model-derived simulation | sunitinib |
| PMC5131886 | human | clinical | HCC |  | treated | plasma | clinical PK/model-derived simulation | SU12662 |
| PMC5131886 | human | clinical | HCC |  | treated | plasma; tumor | clinical PKPD model | sVEGFR2 |
| PMC5131886 | human | clinical | HCC |  | treated | tumor | PKPD/tumor growth model |  |
| PMC5131886 | human | clinical | HCC |  | untreated, placebo | plasma; tumor | clinical PKPD/tumor growth model | sunitinib |
| PMC5131886 | human | clinical | HCC |  | treated |  | time-to-event model |  |
| PMC5131886 | human | clinical | HCC |  | treated |  |  |  |
| PMC5131886 | human | clinical | HCC |  | baseline, treated |  |  |  |
| PMC5131886 | human | clinical | HCC |  | treated |  |  |  |
| PMC5131886 | human | clinical | HCC |  | treated |  |  |  |
| PMC5131886 | human | clinical | HCC |  | treated |  |  |  |
| PMC5131886 | human | clinical | HCC |  | treated |  |  |  |

## Missing Inputs And Review Blockers

| Paper | Missing input | Severity | Reason |
| --- | --- | --- | --- |
| PMC3693219 | top_level_mechanism_chains | warning | No trusted top-level mechanism chains are available for causal extraction. |
| PMC3693219 | model_structure | warning | No explicit PBPK/PKPD/popPK/QSP model structure was detected. |
| PMC3693219 | pk_exposure_parameters | error | No model-safe PK/PBPK exposure parameters are available. |
| PMC3693219 | model_equations_or_template | warning | No equations or named simulation model were extracted. |
| PMC5131886 | pk_exposure_parameters | warning | No model-safe PK/PBPK exposure parameters are available; concentration records are calibration endpoints. |
| PMC5131886 | dosing_regimen | warning | Route/schedule/dose regimen is present but not model-safe. |
| PMC5131886 | mouse_pk_for_species_translation | warning | Preclinical/xenograft context appears in annotations but mouse exposure inputs are not curated. |

## Provenance Coverage

The combined artifact includes 88 provenance rows. Each curated edge, parameter, and equation retains source record ids and evidence anchors.

| Paper | Item | Source record | Section | Chunk/table/figure | Evidence anchors |
| --- | --- | --- | --- | --- | --- |
| PMC3693219 | parameter:curated_parameter:PMC3693219:standard_daily_dose | simulation_parameter:simulation_parameter:PMC3693219:c410a409b17cc9c9 | FIGURE 5 | figure_005; F5 | anchor:PMC3693219:figure_005:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:pulse_dose | simulation_parameter:simulation_parameter:PMC3693219:1b16b614a9128402 | FIGURE 5 | figure_005; F5 | anchor:PMC3693219:figure_005:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:plasma_concentration_endpoint | simulation_parameter:simulation_parameter:PMC3693219:0982f1c0ae1c27b1 | FIGURE 3 | figure_003; F3 | anchor:PMC3693219:figure_003:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:resistance_probability_endpoint | simulation_parameter:simulation_parameter:PMC3693219:200d539196227d55 | FIGURE 3 | figure_003; F3 | anchor:PMC3693219:figure_003:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:resistant_population_endpoint | simulation_parameter:simulation_parameter:PMC3693219:08385310bd0e4f16 | FIGURE 3 | figure_003; F3 | anchor:PMC3693219:figure_003:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:sensitive_population_endpoint | simulation_parameter:simulation_parameter:PMC3693219:24fded06a3b2147b | FIGURE 5 | figure_005; F5 | anchor:PMC3693219:figure_005:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:half_life_18h | observation:obs:PMC3693219:3358c2283df08130 | Body | chunk_002 | anchor:PMC3693219:chunk_002:s4m1 |
| PMC3693219 | parameter:curated_parameter:PMC3693219:half_life_18h | simulation_parameter:simulation_parameter:PMC3693219:1d82c54c4d09ab22 | Body | chunk_002 | anchor:PMC3693219:chunk_002:s4m1 |
| PMC3693219 | parameter:curated_parameter:PMC3693219:half_life_40h | observation:obs:PMC3693219:dfed009b71e8ff68 | Body | chunk_002 | anchor:PMC3693219:chunk_002:s4m2 |
| PMC3693219 | parameter:curated_parameter:PMC3693219:half_life_40h | simulation_parameter:simulation_parameter:PMC3693219:3e04930e3383a7c7 | Body | chunk_002 | anchor:PMC3693219:chunk_002:s4m2 |
| PMC3693219 | parameter:curated_parameter:PMC3693219:elim_k_smokers_150 | simulation_parameter:simulation_parameter:PMC3693219:881a3bc1c6ca6a93 | FIGURE 1 | figure_001; F1 | anchor:PMC3693219:figure_001:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:elim_k_smokers_300 | simulation_parameter:simulation_parameter:PMC3693219:b7eb1593be3272eb | FIGURE 1 | figure_001; F1 | anchor:PMC3693219:figure_001:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:elim_k_nonsmokers_150 | simulation_parameter:simulation_parameter:PMC3693219:1712979aa21708c8 | FIGURE 1 | figure_001; F1 | anchor:PMC3693219:figure_001:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:elim_k_nonsmokers_300 | simulation_parameter:simulation_parameter:PMC3693219:17b42cb3d6e42735 | FIGURE 1 | figure_001; F1 | anchor:PMC3693219:figure_001:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:hamilton_cmax_endpoint | simulation_parameter:simulation_parameter:PMC3693219:0868ae127afd0fad | FIGURE 1 | figure_001; F1 | anchor:PMC3693219:figure_001:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:trial_248_005_cmax_endpoint | simulation_parameter:simulation_parameter:PMC3693219:1b12a489281480b6 | FIGURE 1 | figure_001; F1 | anchor:PMC3693219:figure_001:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:smoker_150_plasma_endpoint | simulation_parameter:simulation_parameter:PMC3693219:21dd53ffc548f80f | FIGURE 3 | figure_003; F3 | anchor:PMC3693219:figure_003:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:nonsmoker_150_plasma_endpoint | simulation_parameter:simulation_parameter:PMC3693219:0982f1c0ae1c27b1 | FIGURE 3 | figure_003; F3 | anchor:PMC3693219:figure_003:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:dose_300_mg_daily | observation:obs:PMC3693219:bb49aeea2f7c379b | Pharmacokinetic Effects Alter the Dynamics of Resistance | chunk_007 | anchor:PMC3693219:chunk_007:s5m2 |
| PMC3693219 | parameter:curated_parameter:PMC3693219:dose_300_mg_daily | observation:obs:PMC3693219:06fecfb948f70388 | Pharmacokinetic Effects Alter the Dynamics of Resistance | chunk_007 | anchor:PMC3693219:chunk_007:s15m1 |
| PMC3693219 | parameter:curated_parameter:PMC3693219:maintenance_50_mg_concentration_endpoint | simulation_parameter:simulation_parameter:PMC3693219:869da90f28dc00ed | FIGURE 2 | figure_002; F2 | anchor:PMC3693219:figure_002:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:pulse_probability_resistance_endpoint | simulation_parameter:simulation_parameter:PMC3693219:4dca50b6660c163e | FIGURE 3 | figure_003; F3 | anchor:PMC3693219:figure_003:figure |
| PMC3693219 | parameter:curated_parameter:PMC3693219:withdrawal_population_endpoint | simulation_parameter:simulation_parameter:PMC3693219:1c95cf7e297dd0f8 | FIGURE 5 | figure_005; F5 | anchor:PMC3693219:figure_005:figure |
| PMC5131886 | edge:curated_edge:PMC5131886:dose_to_sunitinib_plasma | observation:obs:PMC5131886:43214157cd0a65ff | Body | chunk_002 | anchor:PMC5131886:chunk_002:s15m1 |
| PMC5131886 | edge:curated_edge:PMC5131886:sunitinib_plasma_to_active_unbound | mechanism_step:step:PMC5131886:27fa15d47ecb84da | Figure 1 | figure_001 | anchor:PMC5131886:figure_001:moa5 |
| PMC5131886 | edge:curated_edge:PMC5131886:sunitinib_plasma_to_active_unbound | simulation_parameter:simulation_parameter:PMC5131886:03ac85c6f0bc4f7c | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | edge:curated_edge:PMC5131886:su12662_plasma_to_active_unbound | mechanism_step:step:PMC5131886:27fa15d47ecb84da | Figure 1 | figure_001 | anchor:PMC5131886:figure_001:moa5 |
| PMC5131886 | edge:curated_edge:PMC5131886:su12662_plasma_to_active_unbound | simulation_parameter:simulation_parameter:PMC5131886:7e49718692ac32c2 | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | edge:curated_edge:PMC5131886:active_unbound_inhibits_svegfr2_production | mechanism_step:step:PMC5131886:27fa15d47ecb84da | Figure 1 | figure_001 | anchor:PMC5131886:figure_001:moa5 |
| PMC5131886 | edge:curated_edge:PMC5131886:active_unbound_inhibits_svegfr2_production | mechanism_step:step:PMC5131886:05f1ecda4b6b0995 | Abstract | chunk_001 | anchor:PMC5131886:chunk_001:moa5 |
| PMC5131886 | edge:curated_edge:PMC5131886:svegfr2_production_drives_biomarker | mechanism_step:step:PMC5131886:27fa15d47ecb84da | Figure 1 | figure_001 | anchor:PMC5131886:figure_001:moa5 |
| PMC5131886 | edge:curated_edge:PMC5131886:svegfr2_production_drives_biomarker | simulation_parameter:simulation_parameter:PMC5131886:76cce742eb8dbe47 | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | edge:curated_edge:PMC5131886:svegfr2_to_delta_svegfr2 | mechanism_step:step:PMC5131886:d0ac7603ff3f2325 | Figure 1 | figure_001 | anchor:PMC5131886:figure_001:moa6 |
| PMC5131886 | edge:curated_edge:PMC5131886:svegfr2_to_delta_svegfr2 | simulation_parameter:simulation_parameter:PMC5131886:556c9768d5621cc3 | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | edge:curated_edge:PMC5131886:svegfr2_to_delta_svegfr2 | simulation_parameter:simulation_parameter:PMC5131886:63ea798bd0197392 | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | edge:curated_edge:PMC5131886:delta_svegfr2_inhibits_tumor_growth_rate | mechanism_step:step:PMC5131886:d0ac7603ff3f2325 | Figure 1 | figure_001 | anchor:PMC5131886:figure_001:moa6 |
| PMC5131886 | edge:curated_edge:PMC5131886:delta_svegfr2_inhibits_tumor_growth_rate | simulation_parameter:simulation_parameter:PMC5131886:b9e399006482a232 | Table 2 | table_002; psp412084-tbl-0002 | anchor:PMC5131886:table_002:r5c1 |
| PMC5131886 | edge:curated_edge:PMC5131886:delta_svegfr2_inhibits_tumor_growth_rate | simulation_parameter:simulation_parameter:PMC5131886:d9a2875ae08b8179 | Tumor growth inhibition model | chunk_019 | anchor:PMC5131886:chunk_019:s7m1 |
| PMC5131886 | edge:curated_edge:PMC5131886:tumor_growth_rate_drives_tumor_volume | simulation_model:simulation:PMC5131886:05ab0b1801332e16 | Tumor growth inhibition model | chunk_019 | anchor:PMC5131886:chunk_019:sim9 |
| PMC5131886 | edge:curated_edge:PMC5131886:tumor_growth_rate_drives_tumor_volume | simulation_parameter:simulation_parameter:PMC5131886:34731f9af2b0b435 | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | edge:curated_edge:PMC5131886:tumor_growth_rate_drives_tumor_volume | simulation_parameter:simulation_parameter:PMC5131886:5870934d4a4a9ec7 | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | edge:curated_edge:PMC5131886:delta_svegfr2_predicts_ttp_hazard | simulation_parameter:simulation_parameter:PMC5131886:05e6b2f90cab61c4 | Table 2 | table_002; psp412084-tbl-0002 | anchor:PMC5131886:table_002:r10c1 |
| PMC5131886 | edge:curated_edge:PMC5131886:delta_svegfr2_predicts_ttp_hazard | equation:eq:PMC5131886:ece40d8b730a6d9b | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq12_1 |
| PMC5131886 | edge:curated_edge:PMC5131886:ttp_hazard_drives_ttp_probability | simulation_parameter:simulation_parameter:PMC5131886:d6ac5922bf5437b1 | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq12_1 |
| PMC5131886 | edge:curated_edge:PMC5131886:ttp_hazard_drives_ttp_probability | simulation_parameter:simulation_parameter:PMC5131886:e17d8934bdafa104 | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq12_1 |
| PMC5131886 | edge:curated_edge:PMC5131886:ttp_hazard_drives_ttp_probability | equation:eq:PMC5131886:ece40d8b730a6d9b | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq12_1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:dose_50_mg_daily | observation:obs:PMC5131886:43214157cd0a65ff | Body | chunk_002 | anchor:PMC5131886:chunk_002:s15m1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:sunitinib_plasma_endpoint | simulation_parameter:simulation_parameter:PMC5131886:03ac85c6f0bc4f7c | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | parameter:curated_parameter:PMC5131886:su12662_plasma_endpoint | simulation_parameter:simulation_parameter:PMC5131886:7e49718692ac32c2 | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | parameter:curated_parameter:PMC5131886:svegfr2_baseline_r0 | simulation_parameter:simulation_parameter:PMC5131886:63ea798bd0197392 | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | parameter:curated_parameter:PMC5131886:tgi_ic50 | simulation_parameter:simulation_parameter:PMC5131886:d9a2875ae08b8179 | Tumor growth inhibition model | chunk_019 | anchor:PMC5131886:chunk_019:s7m1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:tgi_ic50 | observation:obs:PMC5131886:c52fafe15e0c7632 | Tumor growth inhibition model | chunk_019 | anchor:PMC5131886:chunk_019:s7m1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:slope_hazard_delta_auc_svegfr2 | simulation_parameter:simulation_parameter:PMC5131886:05e6b2f90cab61c4 | Table 2 | table_002; psp412084-tbl-0002 | anchor:PMC5131886:table_002:r10c1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:slope_hazard_delta_auc_svegfr2 | observation:obs:PMC5131886:4676d2dab946af5a | Table 2 | table_002; psp412084-tbl-0002 | anchor:PMC5131886:table_002:r10c1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:population_pk_model_structure | simulation_parameter:simulation_parameter:PMC5131886:e4c44b2bc3130b86 | supp_2071 | supplementary_060 | anchor:PMC5131886:supplementary_060:sim5 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:pkpd_model_structure | simulation_parameter:simulation_parameter:PMC5131886:dd600f1f47ee8209 | supp_2017 | supplementary_051 | anchor:PMC5131886:supplementary_051:sim21 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:monolix_platform | simulation_parameter:simulation_parameter:PMC5131886:e98288b948c16208 | Data analysis | chunk_012 | anchor:PMC5131886:chunk_012:sim5 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:plasma_compartment | simulation_parameter:simulation_parameter:PMC5131886:655170ee3e735046 | Biomarker dynamics | chunk_018 | anchor:PMC5131886:chunk_018:sim1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:tumor_compartment | simulation_parameter:simulation_parameter:PMC5131886:2a99b15f749b8927 | Figure 2 | figure_002 | anchor:PMC5131886:figure_002:sim5 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:pk_variable_cl | simulation_parameter:simulation_parameter:PMC5131886:99668a066e814199 | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq3_1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:pk_variable_v1 | simulation_parameter:simulation_parameter:PMC5131886:3cec07cf5ad1b024 | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq3_1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:pk_variable_q | simulation_parameter:simulation_parameter:PMC5131886:33a10367c3d94cf3 | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq3_2 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:pk_variable_v2 | simulation_parameter:simulation_parameter:PMC5131886:1a53f2132f547baf | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq3_2 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:pk_variable_k10 | simulation_parameter:simulation_parameter:PMC5131886:8709c763926142af | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq3_1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:pk_variable_k12 | simulation_parameter:simulation_parameter:PMC5131886:3761087c9f4dd447 | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq3_1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:pk_variable_k21 | simulation_parameter:simulation_parameter:PMC5131886:50bfb5ae8bacb17d | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq3_2 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:sunitinib_observed_plasma_endpoint | simulation_parameter:simulation_parameter:PMC5131886:4fc85b696909940f | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | parameter:curated_parameter:PMC5131886:sunitinib_predicted_plasma_endpoint | simulation_parameter:simulation_parameter:PMC5131886:cd90cbc6cf906a22 | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | parameter:curated_parameter:PMC5131886:su12662_observed_plasma_endpoint | simulation_parameter:simulation_parameter:PMC5131886:d1f39ba1783bb406 | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | parameter:curated_parameter:PMC5131886:su12662_predicted_plasma_endpoint | simulation_parameter:simulation_parameter:PMC5131886:eca77cef32067794 | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | parameter:curated_parameter:PMC5131886:alpha_slope_acub_on_svegfr2 | simulation_parameter:simulation_parameter:PMC5131886:dfccb203dcf5ad53 | Table 2 | table_002; psp412084-tbl-0002 | anchor:PMC5131886:table_002:r2c1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:alpha_slope_acub_on_svegfr2 | observation:obs:PMC5131886:5139b60b0049e4a6 | Table 2 | table_002; psp412084-tbl-0002 | anchor:PMC5131886:table_002:r2c1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:kd_review_candidate | simulation_parameter:simulation_parameter:PMC5131886:3cc293d705608e3d | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:s2m1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:kd_review_candidate | observation:obs:PMC5131886:52d44db97187875f | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:s2m1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:svegfr2_observed_endpoint | simulation_parameter:simulation_parameter:PMC5131886:ba06755d727bb0dd | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | parameter:curated_parameter:PMC5131886:svegfr2_predicted_endpoint | simulation_parameter:simulation_parameter:PMC5131886:fb57a36b1fef03f6 | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | parameter:curated_parameter:PMC5131886:tumor_volume_observed_endpoint | simulation_parameter:simulation_parameter:PMC5131886:de5919a059d778eb | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | parameter:curated_parameter:PMC5131886:tumor_volume_placebo_endpoint | simulation_parameter:simulation_parameter:PMC5131886:5870934d4a4a9ec7 | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | parameter:curated_parameter:PMC5131886:hazard_variable_z2_auc | simulation_parameter:simulation_parameter:PMC5131886:fe61aa3cc7f09f37 | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq12_1 |
| PMC5131886 | parameter:curated_parameter:PMC5131886:hazard_variable_auc | simulation_parameter:simulation_parameter:PMC5131886:ce7acad9b1e2424c | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq12_1 |
| PMC5131886 | equation:curated_equation:PMC5131886:active_unbound_concentration | mechanism_step:step:PMC5131886:27fa15d47ecb84da | Figure 1 | figure_001 | anchor:PMC5131886:figure_001:moa5 |
| PMC5131886 | equation:curated_equation:PMC5131886:svegfr2_indirect_response | mechanism_step:step:PMC5131886:27fa15d47ecb84da | Figure 1 | figure_001 | anchor:PMC5131886:figure_001:moa5 |
| PMC5131886 | equation:curated_equation:PMC5131886:delta_svegfr2 | mechanism_step:step:PMC5131886:d0ac7603ff3f2325 | Figure 1 | figure_001 | anchor:PMC5131886:figure_001:moa6 |
| PMC5131886 | equation:curated_equation:PMC5131886:delta_svegfr2 | simulation_parameter:simulation_parameter:PMC5131886:63ea798bd0197392 | Figure 2 | figure_002; psp412084-fig-0002 | anchor:PMC5131886:figure_002:figure |
| PMC5131886 | equation:curated_equation:PMC5131886:tgi_growth_rate_effect | mechanism_step:step:PMC5131886:d0ac7603ff3f2325 | Figure 1 | figure_001 | anchor:PMC5131886:figure_001:moa6 |
| PMC5131886 | equation:eq:PMC5131886:ece40d8b730a6d9b | equation:eq:PMC5131886:ece40d8b730a6d9b | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq12_1 |
| PMC5131886 | equation:eq:PMC5131886:f40c3d716a3c69c2 | equation:eq:PMC5131886:f40c3d716a3c69c2 | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq3_1 |
| PMC5131886 | equation:eq:PMC5131886:4d9cbb929eb262d6 | equation:eq:PMC5131886:4d9cbb929eb262d6 | supp_2077 | supplementary_061 | anchor:PMC5131886:supplementary_061:eq3_2 |

## Primary JSON Artifact

`data/curated_annotation_graphs/combined.paper_moa_graph.json`
