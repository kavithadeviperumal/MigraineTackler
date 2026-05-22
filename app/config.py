from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google Gemini
    google_api_key: str = ""

    # LangSmith
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "migrainetackler"

    # Weather
    openweather_api_key: str = ""
    openweather_city: str = "Austin"
    openweather_country_code: str = "US"

    # AQI
    airnow_api_key: str = ""
    airnow_zip: str = "78701"

    # Database (PostgreSQL — set DATABASE_URL in environment)
    database_url: str = ""

    # Auth
    jwt_secret_key: str = "dev-secret-change-me-in-production"
    jwt_expire_days: int = 30

    # App
    log_level: str = "INFO"


settings = Settings()

# Inject into os.environ so the Google GenAI SDK can find the key
import os as _os
if settings.google_api_key:
    _os.environ["GOOGLE_API_KEY"] = settings.google_api_key
