"""FastAPI entry point: python -m uvicorn agents.main:app --port 8000."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from .agent import IncidentCoordinator
from .config import Settings
from .database import MongoDatabase, TicketNotFoundError, create_mongo_client
from .model import create_model
from .schemas import AnalyzeTicketRequest, CoordinationResult, ErrorResponse


logger = logging.getLogger(__name__)


def create_app(coordinator: IncidentCoordinator | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if coordinator is not None:
            app.state.coordinator = coordinator
            yield
            return

        settings = Settings.from_env()
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
        client = create_mongo_client(settings)
        try:
            database = MongoDatabase(client[settings.mongodb_db_name])
            app.state.coordinator = IncidentCoordinator(database, create_model(settings), model_name=settings.model)
            logger.info("Agent ready with model %s.", settings.model)
            yield
        finally:
            client.close()

    app = FastAPI(title="Paperdesk incident coordination agent", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def invalid_body(_request, _error):
        return JSONResponse(
            status_code=400,
            content={"message": "Provide only ticketId as a valid MongoDB ObjectId."},
        )

    @app.post(
        "/analyze-ticket",
        response_model=CoordinationResult,
        responses={
            400: {"model": ErrorResponse, "description": "Invalid ticket ID or body."},
            404: {"model": ErrorResponse, "description": "Ticket not found."},
            502: {"model": ErrorResponse, "description": "Analysis failed."},
            503: {"model": ErrorResponse, "description": "Database unavailable."},
            "default": {"model": ErrorResponse},
        },
    )
    def analyze_ticket(body: AnalyzeTicketRequest):
        try:
            return app.state.coordinator.analyze(body.ticketId)
        except TicketNotFoundError:
            return JSONResponse(status_code=404, content={"message": "Ticket not found."})
        except PyMongoError:
            return JSONResponse(
                status_code=503, content={"message": "Database unavailable."}
            )
        except Exception:
            logger.exception("Ticket analysis failed.")
            return JSONResponse(status_code=502, content={"message": "Analysis failed."})

    return app


app = create_app()
