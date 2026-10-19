"""Application configuration. All values come from environment variables (see .env.example)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(PROJECT_DIR / ".env"), extra="ignore")

    app_env: str = "development"  # development | demo | production
    app_version: str = "3.0.0"
    # Public URL used in any absolute link the API returns. Never hardcode localhost in public content.
    public_base_url: str = ""
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'jansetu.db'}"
    secret_key: str = "change-me-in-env"
    token_ttl_minutes: int = 480
    cors_origins: str = ""  # comma separated; empty = same-origin only

    upload_dir: str = str(BACKEND_DIR / "data" / "uploads")
    max_upload_mb: int = 5

    # AI provider (optional). Empty = offline rule-based demo classifier (clearly labelled).
    llm_provider: str = ""  # "" | "openai_compatible"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    triage_confidence_threshold: float = 0.55

    # Speech / translation / OCR providers (optional adapters)
    stt_provider: str = ""  # e.g. "bhashini" (requires credentials)
    translation_provider: str = ""
    ocr_provider: str = ""

    # Messaging / OTP providers. "demo" shows the OTP on screen and is clearly labelled simulated.
    otp_provider: str = "demo"
    sms_provider: str = ""
    whatsapp_provider: str = ""

    # Background jobs
    enable_background_jobs: bool = True
    escalation_interval_seconds: int = 60
    monitoring_interval_seconds: int = 60

    rate_limit_per_minute: int = 300
    auth_rate_limit_per_minute: int = 30

    transcript_retention_days: int = 90

    # First start: create/upgrade the schema and load demo data automatically when the database is empty.
    auto_init_db: bool = True
    auto_seed_demo: bool = True

    # Maps. Default basemap: CARTO (OpenStreetMap data); falls back to the OpenStreetMap tile server automatically.
    # For production use a government / licensed tile server (e.g. Bhuvan, MapmyIndia) via these settings.
    map_tile_url: str = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
    map_tile_url_dark: str = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    map_fallback_tile_url: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    map_attribution: str = "&copy; OpenStreetMap contributors &copy; CARTO"
    field_location_ttl_minutes: int = 15

    def model_post_init(self, __context) -> None:
        # Hosting platforms (Render, Heroku) hand out postgres:// URLs; SQLAlchemy needs the driver name.
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        # Relative SQLite paths are resolved against backend/ so the app works from any working directory.
        if url.startswith("sqlite:///./") or (url.startswith("sqlite:///") and not url.startswith("sqlite:////")
                                                and ":" not in url[10:12] and not url.startswith("sqlite:///:memory:")):
            rel = url[len("sqlite:///"):]
            url = f"sqlite:///{(BACKEND_DIR / rel).resolve()}"
        object.__setattr__(self, "database_url", url)
        if not Path(self.upload_dir).is_absolute():
            object.__setattr__(self, "upload_dir", str((BACKEND_DIR / self.upload_dir).resolve()))

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def ai_mode(self) -> str:
        if self.llm_provider and self.llm_api_key and self.llm_model:
            return "llm"
        return "rule_based_demo"


@lru_cache
def get_settings() -> Settings:
    return Settings()
