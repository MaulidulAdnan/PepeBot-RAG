from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    INTERNAL_API_KEY: str
    GEMINI_API_KEY: str
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIM: int = 768
    LLM_MODEL: str = "gemini-3.5-flash-lite"
    RETRIEVAL_THRESHOLD: float = 0.65
    TOP_K: int = 4

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings() # type: ignore