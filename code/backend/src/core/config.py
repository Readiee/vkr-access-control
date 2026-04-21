from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_BACKEND_ROOT = Path(__file__).resolve().parents[2]      # code/backend/
_ONTOLOGIES_DIR = _BACKEND_ROOT.parent / "onto" / "ontologies"
DEFAULT_ONTOLOGY_PATH = str(_ONTOLOGIES_DIR / "edu_ontology_with_rules.owl")


class Settings(BaseSettings):
    APP_ENV: str = "dev"
    ONTOLOGY_FILE_PATH: str = DEFAULT_ONTOLOGY_PATH
    REDIS_URL: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
