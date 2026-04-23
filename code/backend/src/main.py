"""FastAPI-приложение Semantic Rules API."""
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import access, policies, integration, progress, sandbox, verification

APP_TITLE = "OntoRule API"
APP_DESCRIPTION = (
    "Микросервис управления семантическими правилами доступа к образовательному контенту. "
    "Работает с OWL-онтологией через Owlready2, запускает Pellet Reasoner "
    "и кэширует результаты логического вывода в Redis."
)
APP_VERSION = "2.2.0-dev"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION, version=APP_VERSION)

# Настройка CORS 
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
async def health_check():
    return {"status": "ok", "version": APP_VERSION}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
