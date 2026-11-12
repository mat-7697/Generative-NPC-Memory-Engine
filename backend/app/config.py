from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL
    database_url: str = "postgresql://postgres:password@localhost:5432/npc_memory_engine"
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_user: str = "postgres"
    pg_password: str = "password"
    pg_database: str = "npc_memory_engine"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "npc_memories"

    # JWT
    jwt_secret: str = "change-this-to-a-random-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # Gemini LLM
    gemini_api_key: str = ""
    google_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    llm_provider: str = "gemini"  # 'gemini' or 'mock'

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # App
    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"
    rate_limit_login: str = "5/minute"
    rate_limit_chat: str = "20/minute"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
