from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/v1"
    DATABASE_URL: str = (
        "postgresql+psycopg://db_user:db_secret_pass@localhost:5433/db_ishikawa"
    )
    SERVICE_TOKEN: str = "local-dev-service-token-change-in-production"

    # Seed de dados
    SEED_ON_STARTUP: bool = False
    SEED_DATA_PATH: str = "app/resources/test_data/farms.json"

    # Pool de conexões e resiliência (PostgreSQL / Supavisor)
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_PREPARE_THRESHOLD: Optional[int] = None


settings = Settings()
