from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str
    ONTOLOGY_FILE_PATH: str
    REDIS_URL: str

    model_config = SettingsConfigDict(
        env_file="../.env", 
        env_file_encoding='utf-8',
        extra='ignore'
    )


settings = Settings()
