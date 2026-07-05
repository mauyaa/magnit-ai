import mimetypes
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.features.leads.routes import router as leads_router
from app.features.widgets.routes import router as widgets_router
from app.features.payments.routes import router as payments_router
from app.features.users.routes import router as users_router
from app.platform.clients.deployment import build_widget_html
from app.platform.config.settings import settings
from app.platform.db.session import async_session_factory


def create_app() -> FastAPI:
    import app.features.widgets.models  # noqa: E402,F401 - ensure models are registered
    import app.features.leads.models  # noqa: E402,F401
    import app.features.users.models  # noqa: E402,F401
    app = FastAPI(title="MagnetAI", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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

    if settings.widgets_dir and os.path.isdir(settings.widgets_dir):
        app.mount("/widget-dist", StaticFiles(directory=settings.widgets_dir), name="widget-dist")

    @app.get("/embed/{widget_id}", response_class=HTMLResponse)
    async def embed_widget(widget_id: str):
        dist_dir = os.path.join(settings.widgets_dir, widget_id, "dist")
        index_path = os.path.join(dist_dir, "index.html")
        if os.path.exists(index_path):
            with open(index_path) as f:
                html = f.read()
            prefix = f'/widget-dist/{widget_id}/dist'
            html = html.replace('="./assets/', f'="{prefix}/assets/')
            html = html.replace('="/assets/', f'="{prefix}/assets/')
            html = html.replace("='./assets/", f"='{prefix}/assets/")
            html = html.replace("='/assets/", f"='{prefix}/assets/")
            html = html.replace('="./assets', f'="{prefix}/assets')
            return HTMLResponse(content=html)

        tsx_path = os.path.join(settings.widgets_dir, widget_id, "Widget.tsx")
        if os.path.exists(tsx_path):
            with open(tsx_path) as f:
                return HTMLResponse(content=build_widget_html(f.read()))

        raise HTTPException(status_code=404, detail="widget_not_found")

    app.include_router(users_router)
    app.include_router(widgets_router)
    app.include_router(payments_router)
    app.include_router(leads_router)

    return app
