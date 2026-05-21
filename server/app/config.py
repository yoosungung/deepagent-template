from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/postgres"
    DEEPAGENT_MODEL_PROVIDER: str = "openai"
    DEEPAGENT_MODEL_NAME: str = "gpt-4o"
    
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    
    OPIK_PROJECT_NAME: str = "si-agent-scaffolding"
    OPIK_API_KEY: Optional[str] = None
    OPIK_URL_OVERRIDE: Optional[str] = None

    NAVER_CLIENT_ID: Optional[str] = None
    NAVER_CLIENT_SECRET: Optional[str] = None

    PORT: int = 8000
    HOST: str = "0.0.0.0"

settings = Settings()
