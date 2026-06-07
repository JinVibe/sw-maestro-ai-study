from __future__ import annotations

from fastapi import Request

from app.config import Settings
from app.orchestrator_service import OrchestratorService
from app.session_store import SessionStore


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_sessions(request: Request) -> SessionStore:
    return request.app.state.sessions


def get_orchestrator(request: Request) -> OrchestratorService:
    return request.app.state.orchestrator
