import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Hostel & Transport Rules Assistant"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    DATABASE_URL: str = "sqlite:///./assistant.db"
    UPLOAD_DIR: str = os.path.join(os.getcwd(), "uploads")
    
    # Retrieval & RAG defaults
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 80
    TOP_K_RETRIEVAL: int = 4
    SIMILARITY_THRESHOLD: float = 0.25
    
    # LLM Settings
    DEFAULT_MODEL: str = "grounded-rag-v1"
    OPENAI_API_KEY: str | None = None


settings = Settings()
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
