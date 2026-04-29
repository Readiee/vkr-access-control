from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.dependencies import get_cache_manager
from api.routers import access, integration, policies, progress, sandbox, verification
from core.config import settings

APP_TITLE = "OntoRule API"
APP_DESCRIPTION = (
    "Микросервис управления семантическими правилами доступа к образовательному контенту. "
    "Работает с OWL-онтологией через Owlready2, запускает Pellet Reasoner "
    "и кэширует результаты логического вывода в Redis."
)
APP_VERSION = "2.2.0-dev"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    # файл онтологии мог измениться между запусками; пустой кэш безопаснее устаревшего
    cache = get_cache_manager()
    cache.ensure_version_consistency()
    cache.publish_ontology_version()
    yield


app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION, version=APP_VERSION, lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(integration.router)
app.include_router(policies.router)
app.include_router(access.router)
app.include_router(progress.router)
app.include_router(verification.router)
app.include_router(sandbox.router)


@app.get("/", tags=["Health"])
async def health_check() -> dict:
    return {"status": "ok", "version": APP_VERSION}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HTTP_HOST,
        port=settings.HTTP_PORT,
        reload=settings.HTTP_RELOAD,
    )
