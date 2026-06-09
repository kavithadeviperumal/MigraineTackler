from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google Gemini
    google_api_key: str = ""

    # OpenAI
    openai_api_key: str = ""

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

    # Apple Shortcuts
    shortcuts_api_key: str = ""

    # Gmail SMTP (use an App Password, not your main Gmail password)
    smtp_host:    str = "smtp.gmail.com"
    smtp_port:    int = 587
    smtp_user:    str = ""   # your Gmail address
    smtp_password: str = ""  # Gmail App Password
    alert_email:  str = ""   # address to receive alerts (can be same as smtp_user)

    # App
    log_level: str = "INFO"


settings = Settings()

# Inject into os.environ so the Google GenAI SDK can find the key
import os as _os
if settings.google_api_key:
    _os.environ["GOOGLE_API_KEY"] = settings.google_api_key
