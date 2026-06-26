from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.features.widgets.routes import router as widgets_router
from app.features.payments.routes import router as payments_router
from app.features.users.routes import router as users_router
from app.platform.config.settings import settings
from app.platform.db.session import async_session_factory


def create_app() -> FastAPI:
    app = FastAPI(title="MagnetAI", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.frontend_base_url,
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        try:
            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
            return {"status": "ok", "database": "connected"}
        except Exception as e:
            return {"status": "error", "database": str(e)}

    app.include_router(users_router)
    app.include_router(widgets_router)
    app.include_router(payments_router)

    return app
