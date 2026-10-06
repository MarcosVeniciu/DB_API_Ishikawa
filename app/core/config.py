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


settings = Settings()
