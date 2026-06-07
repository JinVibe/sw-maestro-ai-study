from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.orchestrator_service import OrchestratorService
from app.routers import feedbacks, library, recommendations, sessions
from app.session_store import SessionStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    app.state.settings = settings
    app.state.sessions = SessionStore()
    # 카탈로그 1회 로드 (네트워크 없음). LLM/iTunes 클라이언트는 추천 시 생성.
    app.state.orchestrator = OrchestratorService(catalog_path=settings.catalog_path)
    yield


app = FastAPI(title="향수곡 추천 백엔드", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(recommendations.router)
app.include_router(feedbacks.router)
app.include_router(library.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
