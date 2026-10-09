from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    llm_provider: str = "anthropic"  # anthropic | gemini
    anthropic_api_key: str = ""
    llm_extraction_model: str = "claude-sonnet-5-5"
    llm_classification_model: str = "claude-haiku-5-5"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    llm_min_interval_s: float = 0.0  # throttle between calls (free Gemini tier is rate limited)
    prompt_version: str = "v2"
    contradiction_detection: bool = True  # flag conflicting statements across the tender package
    contradiction_max_pairs: int = 20  # candidate pairs sent to the model per analysis (most similar first)
    classify_batch_size: int = 6  # requirements per classification call
    llm_cache: bool = True  # reuse identical LLM calls (same prompt + model); saves quota on re-runs
    extraction_gap_pass: bool = True  # second extraction pass that only looks for missed requirements

    embedding_backend: str = "local"  # local | hash
    embedding_model: str = "BAAI/bge-m3"

    cors_origins: str = "http://localhost:3000"  # comma-separated; set to the deployed frontend URL(s)
    database_url: str = "sqlite:///./bidbridge.db"
    storage_dir: str = "./storage"
    max_upload_mb: int = 50
    max_files_per_analysis: int = 10

    ocr_enabled: bool = True
    ocr_langs: str = "eng+aze"
    min_chars_per_page: int = 40  # below this a page is treated as image-only


    @property
    def extraction_model(self) -> str:
        return self.gemini_model if self.llm_provider == "gemini" else self.llm_extraction_model

    @property
    def classification_model(self) -> str:
        return self.gemini_model if self.llm_provider == "gemini" else self.llm_classification_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
