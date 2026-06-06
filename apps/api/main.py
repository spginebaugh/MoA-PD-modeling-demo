"""FastAPI app for the data-driven MoA graph -> mechanistic PD prototype."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import NoReturn

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import TypeAdapter, ValidationError
from pydantic_core import ErrorDetails

from apps.api.schemas import (
    ApiError,
    ApplyPredictionRequest,
    ApplyPredictionResponse,
    CompileRequest,
    CompileResponse,
    CompileStatus,
    ErrorLocation,
    ErrorResponse,
    GraphComposeResponse,
    HealthResponse,
    PathwayContractResponse,
    PathwayResponse,
    PathwaysResponse,
    PredictOperatorsRequest,
    PredictOperatorsResponse,
    SimulateRequest,
    SimulateResponse,
)
from services.domain import (
    CompiledModel,
    ModelWarning,
    ParameterId,
    SimulationInput,
    WarningCategory,
    WarningSeverity,
)
from services.domain.base import JsonValue
from services.equation_compiler.compiler import compile_graph
from services.pathway.composer import compose_graph, contract_for_pathway
from services.pathway.loader import list_pathways, load_pathway
from services.pathway.models import GraphComposeRequest
from services.predictor.graph_patch import apply_edge_recommendations
from services.predictor.predict import predict_operator
from services.simulator.simulate import simulate
from services.simulator.validation import validate_simulation_ready

ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "apps" / "web"
ERROR_RESPONSES: dict[int | str, dict[str, object]] = {422: {"model": ErrorResponse}}
ERROR_LOCATION_PATH_ADAPTER = TypeAdapter(tuple[str | int, ...])


class ApiBoundaryError(Exception):
    def __init__(
        self,
        errors: Iterable[ApiError],
        warnings: Iterable[ModelWarning] = (),
    ) -> None:
        self.errors = tuple(errors)
        self.warnings = tuple(warnings)


app = FastAPI(
    title="MoA graph to mechanistic PD model prototype",
    version="3.0.0",
    description="Data-driven typed MoA graph compiler with ODE simulation and toy graph-patch prediction.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
if WEB_DIR.exists():
    app.mount("/web", StaticFiles(directory=str(WEB_DIR)), name="web")


def _clean_validation_message(message: str) -> str:
    return message.removeprefix("Value error, ")


def _category_for_message(message: str) -> WarningCategory:
    lower = message.lower()
    if "unsupported" in lower or "unknown" in lower:
        return WarningCategory.UNSUPPORTED_RELATION
    if "parameter" in lower:
        return WarningCategory.MISSING_PARAMETER_PRIOR
    if "simulation" in lower or "simulator" in lower or "execution_model" in lower:
        return WarningCategory.SIMULATOR_INCOMPATIBLE_STATE
    return WarningCategory.OTHER


def _location_from_raw(raw_location: object) -> ErrorLocation | None:
    if not isinstance(raw_location, (tuple, list)):
        return None
    try:
        path = ERROR_LOCATION_PATH_ADAPTER.validate_python(raw_location, strict=True)
    except ValidationError:
        return None
    return ErrorLocation(path=path) if path else None


def _api_error(
    message: str,
    *,
    category: WarningCategory | None = None,
    location: ErrorLocation | None = None,
    details: dict[str, JsonValue] | None = None,
) -> ApiError:
    return ApiError(
        category=_category_for_message(message) if category is None else category,
        severity=WarningSeverity.ERROR,
        message=message,
        location=location,
        details={} if details is None else details,
    )


def _api_error_from_warning(warning: ModelWarning) -> ApiError:
    return ApiError(
        category=warning.category,
        severity=WarningSeverity.ERROR,
        message=warning.message,
        source=warning.source,
        details=warning.details,
    )


def _api_errors_from_validation_details(details: Iterable[ErrorDetails]) -> tuple[ApiError, ...]:
    errors: list[ApiError] = []
    for detail in details:
        message = _clean_validation_message(str(detail.get("msg", "Request validation failed.")))
        error_type = str(detail.get("type", ""))
        errors.append(
            _api_error(
                message,
                location=_location_from_raw(detail.get("loc", ())),
                details={"type": error_type} if error_type else None,
            )
        )
    return tuple(errors)


def _api_errors_from_validation_error(exc: ValidationError) -> tuple[ApiError, ...]:
    return _api_errors_from_validation_details(exc.errors())


def _api_error_from_value_error(exc: ValueError) -> ApiError:
    return _api_error(_clean_validation_message(str(exc)))


def _error_json_response(errors: Iterable[ApiError], warnings: Iterable[ModelWarning] = ()) -> JSONResponse:
    payload = ErrorResponse(errors=tuple(errors), warnings=tuple(warnings))
    return JSONResponse(status_code=422, content=payload.model_dump(mode="json"))


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    del request
    return _error_json_response(_api_errors_from_validation_details(exc.errors()))


@app.exception_handler(ApiBoundaryError)
async def api_boundary_exception_handler(request: Request, exc: ApiBoundaryError) -> JSONResponse:
    del request
    return _error_json_response(exc.errors, exc.warnings)


def _raise_api_boundary_error(exc: ValidationError | ValueError) -> NoReturn:
    if isinstance(exc, ValidationError):
        raise ApiBoundaryError(_api_errors_from_validation_error(exc)) from exc
    raise ApiBoundaryError((_api_error_from_value_error(exc),)) from exc


def _compile_response(model: CompiledModel) -> CompileResponse:
    errors = tuple(warning for warning in model.warnings if warning.severity == WarningSeverity.ERROR)
    warnings = tuple(warning for warning in model.warnings if warning.severity != WarningSeverity.ERROR)
    return CompileResponse(
        ok=not errors,
        status=CompileStatus.READY if not errors else CompileStatus.DIAGNOSTIC_ONLY,
        model=model,
        warnings=warnings,
        errors=errors,
    )


def _raise_if_diagnostic_compile(model: CompiledModel) -> None:
    errors = tuple(warning for warning in model.warnings if warning.severity == WarningSeverity.ERROR)
    if errors:
        raise ApiBoundaryError(_api_error_from_warning(warning) for warning in errors)


def _raise_if_simulation_not_ready(model: CompiledModel, parameter_overrides: dict[ParameterId, float]) -> None:
    errors = validate_simulation_ready(model, parameter_overrides)
    if errors:
        raise ApiBoundaryError(_api_error_from_warning(warning) for warning in errors)


@app.get("/", response_class=HTMLResponse, response_model=None)
def index() -> FileResponse | HTMLResponse:
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>MoA PD Prototype API</h1><p>Open /docs for API docs.</p>")


@app.get("/health", response_model=HealthResponse, responses=ERROR_RESPONSES)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="moa-pd-prototype",
        pathways=tuple(summary.pathway_id for summary in list_pathways()),
    )


@app.get("/pathways", response_model=PathwaysResponse, responses=ERROR_RESPONSES)
def pathways() -> PathwaysResponse:
    return PathwaysResponse(pathways=list_pathways())


@app.get("/pathways/{pathway_id}", response_model=PathwayResponse, responses=ERROR_RESPONSES)
def pathway(pathway_id: str) -> PathwayResponse:
    try:
        return PathwayResponse(pathway=load_pathway(pathway_id))
    except (ValidationError, ValueError) as exc:
        _raise_api_boundary_error(exc)


@app.get("/pathways/{pathway_id}/contract", response_model=PathwayContractResponse, responses=ERROR_RESPONSES)
def pathway_contract(pathway_id: str) -> PathwayContractResponse:
    try:
        return PathwayContractResponse(contract=contract_for_pathway(load_pathway(pathway_id)))
    except (ValidationError, ValueError) as exc:
        _raise_api_boundary_error(exc)


@app.post("/graph/compose", response_model=GraphComposeResponse, responses=ERROR_RESPONSES)
def graph_compose(request: GraphComposeRequest) -> GraphComposeResponse:
    try:
        return GraphComposeResponse(graph=compose_graph(request))
    except (ValidationError, ValueError) as exc:
        _raise_api_boundary_error(exc)


@app.post("/graph/patch", response_model=GraphComposeResponse, responses=ERROR_RESPONSES)
def graph_patch(request: GraphComposeRequest) -> GraphComposeResponse:
    try:
        return GraphComposeResponse(graph=compose_graph(request))
    except (ValidationError, ValueError) as exc:
        _raise_api_boundary_error(exc)


@app.post("/model/compile", response_model=CompileResponse, responses=ERROR_RESPONSES)
def model_compile(request: CompileRequest) -> CompileResponse:
    try:
        return _compile_response(compile_graph(request.graph, load_pathway(request.pathway_id)))
    except (ValidationError, ValueError) as exc:
        _raise_api_boundary_error(exc)


def _compiled_model_from_simulate_request(request: SimulateRequest) -> CompiledModel:
    if request.compiled_model is not None:
        return request.compiled_model
    if request.graph is not None and request.pathway_id is not None:
        model = compile_graph(request.graph, load_pathway(request.pathway_id))
        _raise_if_diagnostic_compile(model)
        return model
    raise ValueError("Provide graph plus pathway_id, or compiled_model.")


@app.post("/simulate", response_model=SimulateResponse, responses=ERROR_RESPONSES)
def simulate_endpoint(request: SimulateRequest) -> SimulateResponse:
    try:
        compiled_model = _compiled_model_from_simulate_request(request)
        _raise_if_simulation_not_ready(compiled_model, request.parameter_overrides)
        simulation_input = SimulationInput(
            model=compiled_model,
            settings=request.settings,
            parameter_overrides=request.parameter_overrides,
            initial_condition_overrides=request.initial_condition_overrides,
        )
        result = simulate(simulation_input)
        return SimulateResponse(result=result, warnings=result.warnings)
    except (ValidationError, ValueError) as exc:
        _raise_api_boundary_error(exc)


@app.post("/predict/operators", response_model=PredictOperatorsResponse, responses=ERROR_RESPONSES)
def predict_operators(request: PredictOperatorsRequest) -> PredictOperatorsResponse:
    try:
        prediction, warnings = predict_operator(request.input)
        return PredictOperatorsResponse(prediction=prediction, warnings=warnings)
    except (ValidationError, ValueError) as exc:
        _raise_api_boundary_error(exc)


@app.post("/predict/operators/apply", response_model=ApplyPredictionResponse, responses=ERROR_RESPONSES)
def predict_operators_apply(request: ApplyPredictionRequest) -> ApplyPredictionResponse:
    try:
        prediction, prediction_warnings = predict_operator(request.input)
        if not request.allow_low_support and (
            prediction.diagnostics.decision_source == "abstain" or prediction.diagnostics.low_support
        ):
            raise ApiBoundaryError(
                (
                    _api_error(
                        "Prediction abstained or is low-support; inspect /predict/operators output or set allow_low_support=true to apply anyway.",
                        category=WarningCategory.LOW_CONFIDENCE,
                    ),
                ),
                prediction_warnings,
            )
        patched_graph = apply_edge_recommendations(
            request.input.graph,
            prediction.recommendations,
            claim_text=request.input.claim_text,
            decision_source=prediction.diagnostics.decision_source,
            pathway_id=str(request.input.pathway_id),
            include_modules=prediction.diagnostics.included_modules or request.input.include_modules,
        )
        pathway = load_pathway(request.input.pathway_id)
        compiled_model = compile_graph(patched_graph, pathway)
        _raise_if_diagnostic_compile(compiled_model)
        _raise_if_simulation_not_ready(compiled_model, request.parameter_overrides)
        simulation = simulate(
            SimulationInput(
                model=compiled_model,
                settings=request.settings,
                parameter_overrides=request.parameter_overrides,
                initial_condition_overrides=request.initial_condition_overrides,
            )
        )
        return ApplyPredictionResponse(
            prediction=prediction,
            graph=patched_graph,
            compiled_model=compiled_model,
            simulation=simulation,
            warnings=(*prediction_warnings, *compiled_model.warnings, *simulation.warnings),
        )
    except (ValidationError, ValueError) as exc:
        _raise_api_boundary_error(exc)
