"""Application configuration via pydantic-settings.

Settings are loaded in this priority order (later wins):
  1. Defaults declared on the class
  2. Values in `.env`
  3. Environment variables
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ENROLLMENT_",
        case_sensitive=False,
    )
    default_list_limit: int = 50
    db_url: str = "sqlite+aiosqlite:///./enrollment.db"

    # App identity
    app_name: str = "Subject Enrollment Service"
    app_version: str = "0.4.0"
    api_prefix: str = "/api/v1"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Logging
    log_level: str = "INFO"


settings = Settings()
