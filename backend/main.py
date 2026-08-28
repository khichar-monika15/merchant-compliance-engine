from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine

from backend.api import routes, websocket
from backend.config import get_settings
from backend.models.database import Base


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
        print(f"[WARN] Playwright browser not available: {e}")

    yield

    # Cleanup (browser instances close themselves after each crawl)


def create_app() -> FastAPI:
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

    return app


app = create_app()
