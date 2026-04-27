# Story 1.1: Thêm Supabase Config vào Backend Settings

Status: ready-for-dev

## Story

As a developer,
I want Supabase credentials và SUPABASE_ENABLED flag được load từ env vars qua Pydantic Settings,
so that toàn bộ Phase 2 features có thể bật/tắt bằng 1 flag mà không ảnh hưởng Phase 1.

## Acceptance Criteria

1. **Given** file `.env` có `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ENABLED=false` — **When** FastAPI server khởi động — **Then** `Settings` object có đủ 4 fields mới, không raise validation error.

2. **Given** `SUPABASE_ENABLED=false` trong `.env` — **When** bất kỳ Phase 1 feature nào được dùng (fetch OHLCV, replay, draw) — **Then** Phase 1 hoạt động bình thường — không có bất kỳ error hay warning nào liên quan Supabase.

3. **Given** `SUPABASE_ENABLED=true` nhưng `SUPABASE_URL` bị bỏ trống — **When** FastAPI server khởi động — **Then** server raise `ValidationError` với message rõ ràng chỉ ra field nào bị thiếu.

4. **Given** `.env.example` trong repo — **When** developer xem file này — **Then** thấy đủ 4 env vars mới với comment giải thích từng field (URL, anon key, service key, enabled flag).

## Tasks / Subtasks

- [ ] Task 1: Tạo cấu trúc thư mục dự án (AC: #1, #2)
  - [ ] Tạo `backend/` directory với `__init__.py` (nếu cần)
  - [ ] Tạo `backend/routes/` với `__init__.py`
  - [ ] Tạo `backend/services/` với `__init__.py`
  - [ ] Tạo `frontend/`, `static/`, `tests/`, `cache/` directories
  - [ ] Tạo `pyproject.toml` với uv deps + pytest config

- [ ] Task 2: Tạo `backend/settings.py` với Pydantic Settings đầy đủ (AC: #1, #2, #3)
  - [ ] Implement `class Settings(BaseSettings)` với tất cả Phase 1 fields
  - [ ] Thêm 4 Phase 2 fields: `supabase_url`, `supabase_key`, `supabase_service_key`, `supabase_enabled`
  - [ ] Thêm `@model_validator` để enforce: nếu `supabase_enabled=true` thì `supabase_url` không được trống
  - [ ] Tạo singleton `settings = Settings()` ở cuối file
  - [ ] Verify `cache_dir.mkdir(parents=True, exist_ok=True)` trong validator

- [ ] Task 3: Tạo `backend/main.py` minimal app factory (AC: #1, #2)
  - [ ] FastAPI app factory với lifespan context
  - [ ] Đăng ký routes (ohlcv, fetch — stub files)
  - [ ] `/health` endpoint
  - [ ] Zero business logic trong file này

- [ ] Task 4: Tạo `backend/models.py` với Pydantic models cốt lõi (AC: #1)
  - [ ] `OHLCVBar`, `APIResponse[T]`, `ErrorResponse` models
  - [ ] Generic `APIResponse` với `data: T | None` và `error: ErrorResponse | None`

- [ ] Task 5: Cập nhật `.env.example` (AC: #4)
  - [ ] Phase 1 vars: `HOST`, `PORT`, `CACHE_DIR`, `APP_PASSWORD`
  - [ ] Phase 2 vars mới: `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ENABLED`
  - [ ] Comment rõ cho từng var, đặc biệt ghi rõ: "SUPABASE_URL: URL của Supabase Backtest project — KHÔNG phải production bot"

- [ ] Task 6: Tạo `.gitignore` chuẩn (AC: #2)
  - [ ] Include: `cache/`, `static/app.js`, `.env`, `__pycache__/`, `node_modules/`, `.venv/`, `*.parquet`, `*.parquet.tmp`

- [ ] Task 7: Viết tests cho Settings validation (AC: #1, #2, #3)
  - [ ] `tests/test_settings.py`: test `SUPABASE_ENABLED=false` không raise error
  - [ ] Test `SUPABASE_ENABLED=true` + `SUPABASE_URL=""` → raise `ValidationError`
  - [ ] Test tất cả 4 fields load đúng từ env vars

## Dev Notes

### ⚠️ CRITICAL: Đây là story đầu tiên — greenfield project

Không có code nào tồn tại trước. Dev agent phải:
1. Tạo **toàn bộ project scaffold** từ đầu theo structure trong architecture.md
2. `backend/settings.py` là **foundation** — mọi module Phase 1 và Phase 2 đều import từ đây
3. Phải setup đúng `pyproject.toml` với `uv` ngay từ đầu

### File cần tạo trong story này

```
stock_backtest_project/
├── backend/
│   ├── __init__.py          # Empty
│   ├── main.py              # App factory + /health endpoint (MINIMAL)
│   ├── models.py            # OHLCVBar, APIResponse[T], ErrorResponse
│   ├── settings.py          # *** TRỌNG TÂM CỦA STORY NÀY ***
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── ohlcv.py         # Stub — chỉ placeholder route
│   │   └── fetch.py         # Stub — chỉ placeholder route
│   └── services/
│       ├── __init__.py
│       └── (các file service — tạo sau)
├── frontend/               # Empty dir — frontend stories sau
├── static/
│   └── index.html          # Minimal placeholder
├── tests/
│   ├── conftest.py         # Fixtures cơ bản
│   └── test_settings.py    # Tests cho story này
├── cache/                  # Empty dir (gitignored)
├── .env.example
├── .gitignore
├── pyproject.toml
└── Procfile
```

### `backend/settings.py` — Exact Implementation

```python
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Cache
    cache_dir: Path = Path("./cache")

    # Auth
    app_password: str = ""  # empty = no auth

    # Phase 2: Supabase Backtest DB (KHÔNG phải production bot DB)
    supabase_url: str = ""
    supabase_key: str = ""           # anon key — signal_comparisons (RLS disabled)
    supabase_service_key: str = ""   # service role key — signal_cases (RLS enabled)
    supabase_enabled: bool = False

    @model_validator(mode="after")
    def validate_supabase_config(self) -> "Settings":
        if self.supabase_enabled and not self.supabase_url:
            raise ValueError(
                "SUPABASE_URL is required when SUPABASE_ENABLED=true. "
                "Set SUPABASE_URL in .env to your Supabase Backtest project URL."
            )
        return self

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def model_post_init(self, __context: object) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
```

**Lưu ý quan trọng:**
- `supabase_url` và `supabase_key` được khai báo trong Phase 1 Architecture ADR-11 với giá trị `""` — đây là Phase 2 implement thực sự chúng
- Dùng `pydantic-settings` (không phải `pydantic` BaseModel trực tiếp) để load từ `.env`
- `settings = Settings()` là singleton — tất cả modules import `from backend.settings import settings`
- **Không bao giờ dùng** `os.getenv()` trực tiếp trong bất kỳ module nào khác
- `model_config` dùng cú pháp Pydantic v2 (không phải `class Config` của v1)

### `pyproject.toml` — Required Dependencies

```toml
[project]
name = "stock_backtest_project"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "fastapi==0.135.3",
    "uvicorn[standard]",
    "pyarrow==24.0.0",
    "ccxt==4.5.48",
    "python-dotenv",
    "pydantic-settings",
    "httpx",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio",
    "httpx",
]

[tool.pytest.ini_options]
pythonpath = ["backend"]
asyncio_mode = "auto"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**httpx** phải include vì Phase 2 (Story 4.1) dùng để gọi Supabase REST API trực tiếp — không dùng `supabase-py`.

### `.env.example` — Exact Content

```dotenv
# Server
HOST=0.0.0.0
PORT=8000
CACHE_DIR=./cache
APP_PASSWORD=   # Leave empty for no auth (local dev)

# Phase 2: Supabase Backtest DB
# QUAN TRỌNG: Đây là Supabase BACKTEST project — KHÔNG phải production bot DB
SUPABASE_URL=https://your-project.supabase.co   # URL của Supabase Backtest project
SUPABASE_KEY=your-anon-key                       # Anon key — dùng cho signal_comparisons (RLS disabled)
SUPABASE_SERVICE_KEY=your-service-role-key       # Service role key — dùng cho signal_cases (RLS enabled)
SUPABASE_ENABLED=false                           # Set true để bật Supabase integration
```

### ADR-11: Settings Access Pattern

```python
# ✅ ĐÚNG — direct import singleton
from backend.settings import settings

def some_service_function():
    path = settings.cache_dir / "file.parquet"
    if settings.supabase_enabled:
        ...

# ❌ SAI — FastAPI Depends cho settings
async def route(s: Settings = Depends(get_settings)): ...

# ❌ SAI — os.getenv() trực tiếp
import os
url = os.getenv("SUPABASE_URL")
```

### Phase 1 vs Phase 2 Isolation

`supabase_enabled: bool = False` đảm bảo Phase 1 hoàn toàn không bị ảnh hưởng:
- Khi `SUPABASE_ENABLED=false` (hoặc không set): Settings load thành công ngay cả khi không có Supabase vars
- Chỉ khi `SUPABASE_ENABLED=true` mới enforce validation `supabase_url` không trống
- Phase 2 routes/services sẽ check `settings.supabase_enabled` trước khi thực thi

### Validation Logic — Quyết định quan trọng

Story này chỉ validate `supabase_url` (không validate `supabase_key` và `supabase_service_key` tại startup). Lý do:
- Key validation xảy ra lúc export (Story 4.3) — không tại startup — để tránh fail server khi keys chưa configured nhưng `SUPABASE_ENABLED=true`
- `supabase_url` là minimum required để biết đang connect đến project nào — format validation sẽ implement ở Story 4.3

### `backend/main.py` — Structure

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from backend.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: cache_dir đã được tạo bởi settings.model_post_init
    yield
    # Shutdown: nothing to clean up yet


def create_app() -> FastAPI:
    app = FastAPI(
        title="Stock Backtest Project",
        docs_url="/docs" if not settings.app_password else None,
    )

    app.router.lifespan_context = lifespan

    # Routes — đăng ký từ routes/
    from backend.routes import ohlcv, fetch  # noqa: E402
    app.include_router(ohlcv.router)
    app.include_router(fetch.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
```

### `backend/models.py` — Core Models

```python
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ErrorResponse(BaseModel):
    message: str
    code: str        # "FETCH_FAILED", "CACHE_CORRUPT", etc.
    retryable: bool


class APIResponse(BaseModel, Generic[T]):
    data: T | None = None
    error: ErrorResponse | None = None
```

**Lưu ý:** Cả `data` và `error` đều PHẢI luôn present trong response — không được omit một trong hai (architecture safety-critical pattern).

### Procfile

```
web: uv run uvicorn backend.main:app --reload --port 8000
assets: npx esbuild frontend/main.ts --bundle --outfile=static/app.js --watch --sourcemap
```

### Liên quan đến Story 1.2 (next)

Story 1.2 sẽ thêm `replayStateChanged` và `tradeCompleted` events vào `frontend/types.ts` (EventMap). Story này không cần implement bất kỳ TypeScript code nào — chỉ tập trung vào backend settings.

### Project Structure Notes

- **File gốc architecture.md** (section "Complete Project Directory Structure"): `backend/exceptions.py` được đề cập nhưng không phải scope của story này — tạo sau khi có actual exceptions cần raise
- **Stub routes** (`backend/routes/ohlcv.py`, `backend/routes/fetch.py`): chỉ tạo file với `router = APIRouter()` và 1 placeholder comment — không implement logic
- **Không tạo** `frontend/` TypeScript files trong story này — chỉ tạo directory

### References

- Settings schema: [docs/project-context.md#7-yêu-cầu-phase-2-supabase-integration](docs/project-context.md) — Section 7
- ADR-11: [_bmad-output/planning-artifacts/architecture.md](../planning-artifacts/architecture.md) — ADR-11: Pydantic Settings
- ADR-09: [_bmad-output/planning-artifacts/architecture.md](../planning-artifacts/architecture.md) — ADR-09: Backend Module Structure
- Supabase schema: [docs/user_database](docs/user_database) — signal_comparisons + signal_cases tables
- Phase 2 FRs: [_bmad-output/planning-artifacts/epics.md](../planning-artifacts/epics.md) — FR27, FR28, Story 1.1
- pyproject.toml format: Architecture section "Verified Dependencies (April 2026)"

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
