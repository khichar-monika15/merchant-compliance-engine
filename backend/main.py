from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine

from backend.api import routes, websocket
from backend.config import get_settings
from backend.models.database import Base

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Init SQLite
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    # Warm up Playwright (browser is launched per-crawl, this just validates the install)
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            await browser.close()
    except Exception as e:
        # Through the logger, so LOG_LEVEL governs it like everything else.
        logging.getLogger(__name__).warning("Playwright browser not available: %s", e)

    yield

    # Cleanup (browser instances close themselves after each crawl)


def create_app() -> FastAPI:
    # LOG_LEVEL was configurable, documented, and did nothing: basicConfig was never called, so
    # the root logger stayed unconfigured and routes.py's logger.warning went nowhere.
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = FastAPI(
        title="Merchant Compliance Intelligence Engine",
        description="AI-powered merchant pre-qualification for Razorpay onboarding",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routes.router)
    app.include_router(websocket.router)

    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built SPA from the API process, when a build exists.

    The API client is same-origin, and `/api` and `/ws` used to exist only through the Vite dev
    proxy, so the documented `npm run build` produced a bundle where every call 404'd. Mounting
    the build here means one process serves both and there is no second origin to configure.

    Mounted last, so it cannot shadow `/api` or `/ws`. Unknown non-API paths fall back to
    index.html because the router is client-side; unknown `/api` paths keep 404ing.
    """
    index = _FRONTEND_DIST / "index.html"
    if not index.is_file():
        return

    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    assets = _FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith(("api/", "ws/")):
            raise HTTPException(status_code=404)
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
