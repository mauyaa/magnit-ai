from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "MAGAI_"}

    database_url: str = "postgresql+asyncpg://localhost:5432/magai"
    gemini_api_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    frontend_base_url: str = "http://localhost:3000"
    vercel_api_token: str = ""
    agy_model: str = "gemini-2.5-flash"
    debug: bool = False


settings = Settings()
