from __future__ import annotations

from typing import Any, cast

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.schemas import (
    CompileResponse,
    ErrorResponse,
    PaperEvidenceGraphResponse,
    PathwayProposalResponse,
    SimulateResponse,
)
from services.domain import PathwayId
from services.pathway.models import GraphComposeRequest

client = TestClient(app)
PATHWAY = PathwayId("egfr_erbb_demo")
PATHWAY_ID = str(PATHWAY)


def test_health_and_pathway_contract_endpoints() -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["pathways"] == [PATHWAY_ID]

    pathways = client.get("/pathways")
    assert pathways.status_code == 200
    assert pathways.json()["pathways"][0]["pathway_id"] == PATHWAY_ID

    contract = client.get(f"/pathways/{PATHWAY_ID}/contract")
    assert contract.status_code == 200
    body = cast(dict[str, Any], contract.json())
    assert {item["value"] for item in body["contract"]["modules"]} == {"cbl_turnover"}
    assert {item["value"] for item in body["contract"]["modifier_relations"]} == {
        "activates_edge",
        "inhibits_edge",
    }
    assert {
        "Compound directly inhibits receptor kinase activity.",
        "Compound promotes CBL-mediated receptor degradation.",
    }.issubset({item["value"] for item in body["contract"]["prediction_claims"]})


def test_annotation_evidence_graph_and_proposal_endpoints() -> None:
    listing = client.get("/annotation-graphs")
    assert listing.status_code == 200
    assert listing.json()["paper_ids"] == ["PMC3693219", "PMC5131886"]

    graph_response = client.get("/annotation-graphs/PMC5131886")
    assert graph_response.status_code == 200
    graph = PaperEvidenceGraphResponse.model_validate_json(graph_response.text).graph
    assert graph.paper_id == "PMC5131886"
    assert len(graph.edges) == 4
    assert any(link.relation == "equation_defines" for link in graph.links)
    assert any(link.relation == "simulation_parameter_for" for link in graph.links)

    proposal_response = client.get("/annotation-graphs/PMC5131886/proposal")
    assert proposal_response.status_code == 200
    proposal = PathwayProposalResponse.model_validate_json(proposal_response.text).proposal
    assert proposal.proposal_kind == "new_pathway"
    assert proposal.executable is False
    assert all(edge.provenance is not None for edge in proposal.proposed_edges)


def test_frontend_uses_pathway_workbench_controls() -> None:
    index = client.get("/")
    assert index.status_code == 200
    assert "text/html" in index.headers["content-type"]
    assert 'id="pathway"' in index.text
    assert 'id="configuration"' in index.text
    assert 'id="claim-effect"' in index.text
    assert 'id="claim-target"' in index.text
    assert 'id="claim-module"' in index.text
    assert 'id="prediction-claim"' in index.text
    assert "Predict graph patch and run" in index.text
    assert "claim-text" not in index.text
    assert "runClaimPrediction" not in index.text
    assert "claim-mediator" not in index.text
    assert "graph/build" not in index.text

    app_js = client.get("/web/app.js")
    assert app_js.status_code == 200
    assert "/graph/compose" in app_js.text
    toy_start = app_js.text.index("async function runToyModel()")
    toy_end = app_js.text.index("function modifierRelations()", toy_start)
    toy_block = app_js.text[toy_start:toy_end]
    assert "/predict/operators/apply" in toy_block
    assert "selectedPredictionClaim()" in toy_block
    assert "target_edge_id" not in toy_block
    assert "desired_relation" not in toy_block
    assert "rememberStructuredTarget" in app_js.text
    assert "structuredPredictionClaim" not in app_js.text
    assert "predictionKeywordHints" not in app_js.text
    assert "latestGraph = response.graph" in toy_block
    assert "latestCompiled = response.compiled_model" in toy_block
    assert "latestSimulation = response.simulation" in toy_block
    assert "renderAll()" in toy_block
    assert "/pathways/" in app_js.text
    assert "document.getElementById('claim-text')" not in app_js.text
    assert "state_binding" not in app_js.text


def test_compose_compile_simulate_api_flow() -> None:
    composed = client.post(
        "/graph/compose",
        json=GraphComposeRequest(pathway_id=PATHWAY, configuration="cbl_degradation").model_dump(mode="json"),
    )
    assert composed.status_code == 200
    graph = composed.json()["graph"]
    assert "CBL_active" in {node["id"] for node in graph["nodes"]}

    compiled_response = client.post("/model/compile", json={"pathway_id": PATHWAY_ID, "graph": graph})
    assert compiled_response.status_code == 200
    compiled = CompileResponse.model_validate_json(compiled_response.text)
    assert compiled.ok is True
    assert len(compiled.model.modifiers) == 2

    sim_response = client.post(
        "/simulate",
        json={
            "compiled_model": compiled.model.model_dump(mode="json"),
            "settings": {"t_end": 24, "n_points": 61},
        },
    )
    assert sim_response.status_code == 200
    sim = SimulateResponse.model_validate_json(sim_response.text)
    assert sim.ok is True
    assert sim.result.biological_logic


def test_default_simulation_exposure_decays_drug_bolus() -> None:
    composed = client.post(
        "/graph/compose",
        json=GraphComposeRequest(pathway_id=PATHWAY, configuration="direct_kinase_inhibition").model_dump(mode="json"),
    )
    graph = composed.json()["graph"]
    compiled_response = client.post("/model/compile", json={"pathway_id": PATHWAY_ID, "graph": graph})
    compiled = CompileResponse.model_validate_json(compiled_response.text)

    default_response = client.post(
        "/simulate",
        json={
            "compiled_model": compiled.model.model_dump(mode="json"),
            "settings": {"dose": 1.0, "t_end": 24, "n_points": 61},
        },
    )
    default_sim = SimulateResponse.model_validate_json(default_response.text).result
    default_drug = next(series for series in default_sim.series if series.state == "Drug")
    assert default_sim.settings.exposure_mode == "bolus"
    assert default_drug.values[0] == 1.0
    assert default_drug.values[-1] < 0.1

    sustained_response = client.post(
        "/simulate",
        json={
            "compiled_model": compiled.model.model_dump(mode="json"),
            "settings": {"dose": 1.0, "t_end": 24, "n_points": 61, "exposure_mode": "constant"},
        },
    )
    sustained_sim = SimulateResponse.model_validate_json(sustained_response.text).result
    sustained_drug = next(series for series in sustained_sim.series if series.state == "Drug")
    assert sustained_drug.values[-1] == 1.0


def test_invalid_graph_returns_useful_error() -> None:
    composed = client.post("/graph/compose", json={"pathway_id": PATHWAY_ID, "configuration": "base_signaling"})
    assert composed.status_code == 200
    graph = composed.json()["graph"]
    graph["edges"][0]["source"] = "missing"

    response = client.post("/model/compile", json={"pathway_id": PATHWAY_ID, "graph": graph})
    assert response.status_code == 422
    body = ErrorResponse.model_validate_json(response.text)
    assert body.ok is False
    assert body.errors
    assert "missing" in body.errors[0].message


def test_prediction_apply_api_flow() -> None:
    response = client.post(
        "/predict/operators/apply",
        json={
            "input": {
                "pathway_id": PATHWAY_ID,
                "claim_text": "Compound promotes CBL-mediated EGFR degradation rather than directly inhibiting kinase activity.",
            },
            "settings": {"t_end": 24, "n_points": 61},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["prediction"]["diagnostics"]["included_modules"] == ["cbl_turnover"]
    assert len(body["compiled_model"]["modifiers"]) == 2


def test_prediction_apply_respects_selected_ligand_target_with_cbl_module() -> None:
    response = client.post(
        "/predict/operators/apply",
        json={
            "input": {
                "pathway_id": PATHWAY_ID,
                "claim_text": (
                    "Compound inhibits CBL-mediated receptor turnover module "
                    "EGF ligand -> EGFR active dimer."
                ),
                "include_modules": ["cbl_turnover"],
                "target_edge_id": "e_ligand_dimerizes_egfr",
                "desired_relation": "inhibits_edge",
            },
            "settings": {"t_end": 24, "n_points": 61},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert [(item["relation"], item["target"]) for item in body["prediction"]["recommendations"]] == [
        ("inhibits_edge", "e_ligand_dimerizes_egfr")
    ]


def test_prediction_apply_cbl_selected_edge_returns_turnover_pair() -> None:
    response = client.post(
        "/predict/operators/apply",
        json={
            "input": {
                "pathway_id": PATHWAY_ID,
                "claim_text": (
                    "Compound activates CBL-mediated receptor turnover module "
                    "Active CBL E3 ligase -> Ubiquitinated EGFR."
                ),
                "include_modules": ["cbl_turnover"],
                "target_edge_id": "e_cbl_ubiquitinates_egfr",
                "desired_relation": "activates_edge",
            },
            "settings": {"t_end": 24, "n_points": 61},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert [(item["relation"], item["target"]) for item in body["prediction"]["recommendations"]] == [
        ("activates_edge", "e_cbl_ubiquitinates_egfr"),
        ("activates_edge", "e_ubiquitinated_egfr_degrades_total"),
    ]
    assert len(body["compiled_model"]["modifiers"]) == 2


def test_prediction_apply_rejects_low_support_claim() -> None:
    response = client.post(
        "/predict/operators/apply",
        json={
            "input": {
                "pathway_id": PATHWAY_ID,
                "claim_text": "Compound promotes receptor degradation.",
            },
            "settings": {"t_end": 24, "n_points": 61},
        },
    )
    assert response.status_code == 422
    body = ErrorResponse.model_validate_json(response.text)
    assert body.ok is False
    assert body.errors[0].category == "low_confidence"
    assert "low-support" in body.errors[0].message
