from pathlib import Path

from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = {"env_prefix": "MAGAI_", "env_file": ".env"}

    database_url: str = "postgresql+asyncpg://localhost:5432/magai"
    gemini_api_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    frontend_base_url: str = "http://localhost:3000"
    vercel_api_token: str = ""
    agy_model: str = "gemini-3.1-pro-preview"
    site_url: str = "http://localhost:8000"
    widgets_dir: str = str(PROJECT_ROOT / "workspace")
    debug: bool = False

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"


settings = Settings()
