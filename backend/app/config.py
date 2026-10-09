from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    anthropic_api_key: str = ""
    llm_extraction_model: str = "claude-sonnet-5-5"
    llm_classification_model: str = "claude-haiku-5-5"
    prompt_version: str = "v1"

    embedding_backend: str = "local"  # local | hash
    embedding_model: str = "BAAI/bge-m3"

    database_url: str = "sqlite:///./bidbridge.db"
    storage_dir: str = "./storage"
    max_upload_mb: int = 50
    max_files_per_analysis: int = 10

    ocr_enabled: bool = True
    ocr_langs: str = "eng+aze"
    min_chars_per_page: int = 40  # below this a page is treated as image-only


@lru_cache
def get_settings() -> Settings:
    return Settings()
