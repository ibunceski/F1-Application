import logging
import uuid
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.middleware.request_id import RequestIdMiddleware, configure_request_id_logging
from app.ml import load_all_models, model_store
from app.routers import analysis, drivers, model_lab, predictions, races, results, seasons, teams

configure_request_id_logging()
logger = logging.getLogger(__name__)

models_loaded = False

app = FastAPI(
    title="F1 Race Prediction Platform API",
    version="1.0.0",
    description="REST API for F1 race analytics and ML predictions",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _request_id(request: Request) -> str:
    existing = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    if existing:
        return existing
    generated = str(uuid.uuid4())
    request.state.request_id = generated
    return generated


def _error_response(request: Request, status_code: int, message: str, error: str | None = None) -> JSONResponse:
    request_id = _request_id(request)
    response = JSONResponse(
        status_code=status_code,
        content={
            "error": error or HTTPStatus(status_code).phrase,
            "message": message,
            "request_id": request_id,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        },
    )
    response.headers["X-Request-ID"] = request_id
    return response


def _detail_to_message(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    return "Request validation failed"


@app.middleware("http")
async def api_key_authentication(request: Request, call_next):
    if (
        settings.ENVIRONMENT == "production"
        and request.method != "OPTIONS"
        and request.url.path.startswith(settings.API_V1_PREFIX)
    ):
        if not settings.API_KEY:
            logger.critical("Production API_KEY is not configured")
            return _error_response(request, status.HTTP_500_INTERNAL_SERVER_ERROR, "API key authentication is not configured")
        if request.headers.get("X-API-Key") != settings.API_KEY:
            return _error_response(request, status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key", "Unauthorized")
    return await call_next(request)


@app.on_event("startup")
async def startup_event() -> None:
    global models_loaded
    logger.info("Starting F1 Prediction Platform API")
    try:
        await init_db()
        logger.info("Database connection verified")
        load_all_models()
        models_loaded = model_store.is_ready()
        if models_loaded:
            logger.info("ML models loaded successfully")
        else:
            logger.warning("ML models were not fully loaded")
    except Exception:
        logger.exception("Failed to start F1 Prediction Platform API")
        raise


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return _error_response(request, exc.status_code, _detail_to_message(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("Validation error for %s %s: %s", request.method, request.url.path, exc.errors())
    return _error_response(request, status.HTTP_422_UNPROCESSABLE_ENTITY, "Request validation failed", "Validation Error")


@app.exception_handler(Exception)
async def internal_server_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error for %s %s", request.method, request.url.path)
    return _error_response(request, status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")


app.include_router(seasons.router, prefix=settings.API_V1_PREFIX)
app.include_router(races.router, prefix=settings.API_V1_PREFIX)
app.include_router(drivers.router, prefix=settings.API_V1_PREFIX)
app.include_router(teams.router, prefix=settings.API_V1_PREFIX)
app.include_router(results.router, prefix=settings.API_V1_PREFIX)
app.include_router(analysis.router, prefix=settings.API_V1_PREFIX)
app.include_router(predictions.router, prefix=settings.API_V1_PREFIX)
app.include_router(model_lab.router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "db": "connected",
        "models": "loaded" if models_loaded else "not_loaded",
    }
