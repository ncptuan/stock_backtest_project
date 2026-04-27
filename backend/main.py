from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from backend.settings import settings

_INDEX_HTML = Path(__file__).parent.parent / 'static' / 'index.html'


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: cache_dir đã được tạo bởi settings.model_post_init
    yield
    # Shutdown: nothing to clean up yet


def create_app() -> FastAPI:
    app = FastAPI(
        title="Stock Backtest Project",
        lifespan=lifespan,
        docs_url="/docs" if not settings.app_password else None,
        redoc_url="/redoc" if not settings.app_password else None,
        openapi_url="/openapi.json" if not settings.app_password else None,
    )

    # Routes — đăng ký từ routes/
    from backend.routes import fetch, ohlcv  # noqa: E402
    from backend.routes.sessions import router as sessions_router  # noqa: E402
    from backend.routes.export import router as export_router  # noqa: E402

    app.include_router(ohlcv.router)
    app.include_router(fetch.router)
    app.include_router(sessions_router)
    app.include_router(export_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def serve_index():
        html = _INDEX_HTML.read_text(encoding='utf-8')
        supabase_flag = 'true' if settings.supabase_enabled else 'false'
        html = html.replace('{{ supabase_enabled }}', supabase_flag)
        return HTMLResponse(content=html)

    return app


app = create_app()
