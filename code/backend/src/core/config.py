from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_ONTOLOGIES_DIR = _BACKEND_ROOT.parent / "onto" / "ontologies"
DEFAULT_ONTOLOGY_PATH = str(_ONTOLOGIES_DIR / "edu_ontology_with_rules.owl")


class Settings(BaseSettings):
    """Конфигурация приложения. Источники: .env -> переменные окружения -> defaults."""

    APP_ENV: str = "dev"
    ONTOLOGY_FILE_PATH: str = DEFAULT_ONTOLOGY_PATH
    REDIS_URL: str = "redis://localhost:6379/0"

    HTTP_HOST: str = "0.0.0.0"
    HTTP_PORT: int = 8000
    HTTP_RELOAD: bool = True

    # в .env задаётся JSON-массивом: CORS_ORIGINS=["https://..."]
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
