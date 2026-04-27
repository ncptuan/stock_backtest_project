# Story 1.3: GET /api/sessions — Danh Sách Parquet Sessions

Status: done

## Story

As a trader,
I want backend trả về danh sách sessions Parquet trong local cache,
so that frontend có thể hiển thị sessions mà không cần Narron tự tìm file trong filesystem.

## Acceptance Criteria

1. **Given** thư mục `cache/` chứa files `BTCUSDT_4h_20260420.parquet` và `ETHUSDT_1h_20260415.parquet` — **When** `GET /api/sessions` được gọi — **Then** trả về array 2 objects: `[{"filename": "BTCUSDT_4h_20260420.parquet", "symbol": "BTCUSDT", "timeframe": "4h", "date": "2026-04-20", "exported": false}, ...]`.

2. **Given** thư mục `cache/` trống hoặc không tồn tại — **When** `GET /api/sessions` được gọi — **Then** trả về `[]` với HTTP 200 — không phải 404.

3. **Given** thư mục `cache/` chứa file tên không match pattern `{SYMBOL}_{timeframe}_{YYYYMMDD}.parquet` — **When** `GET /api/sessions` được gọi — **Then** file đó bị skip — không crash endpoint, không xuất hiện trong response.

4. **Given** `SUPABASE_ENABLED=false` — **When** `GET /api/sessions` được gọi — **Then** endpoint vẫn hoạt động bình thường và trả về session list (endpoint không phụ thuộc vào Supabase flag).

5. **Given** `exported` field trong response — **When** một session chưa từng export — **Then** `exported: false` — logic track `exported` state sẽ được implement ở story sau (Story 3.3), hiện tại hardcode `false`.

## Tasks / Subtasks

- [x] Task 1: Thêm `SessionItem` model vào `backend/models.py` (AC: #1, #2)
  - [x] Thêm class `SessionItem(BaseModel)` với 5 fields: `filename`, `symbol`, `timeframe`, `date`, `exported`
  - [x] Verify không phá vỡ existing models (`OHLCVBar`, `APIResponse[T]`, `ErrorResponse`)

- [x] Task 2: Tạo `backend/routes/sessions.py` (AC: #1, #2, #3, #4, #5)
  - [x] Tạo APIRouter với prefix `/api`
  - [x] Implement `GET /sessions` endpoint — scan `settings.cache_dir` với `Path.glob("*.parquet")`
  - [x] Implement filename parser với regex `^([A-Z0-9]+)_([A-Za-z0-9]+)_(\d{8})\.parquet$`
  - [x] Implement date formatter: `20260420` → `"2026-04-20"`
  - [x] Skip files không match pattern (no exception raise)
  - [x] Handle `cache_dir` không tồn tại → return `[]` (không 404, không crash)
  - [x] Return `APIResponse[list[SessionItem]]` với `data=sessions, error=None`

- [x] Task 3: Đăng ký sessions router trong `backend/main.py` (AC: #1)
  - [x] Import `sessions_router` từ `backend.routes.sessions`
  - [x] `app.include_router(sessions_router)` trong `create_app()`
  - [x] Verify `/api/sessions` path đúng (prefix `/api` từ router, endpoint `/sessions`)

- [x] Task 4: Viết tests `tests/test_sessions.py` (AC: #1, #2, #3, #4)
  - [x] Test: 2 valid Parquet files → 2 SessionItems đúng fields
  - [x] Test: cache dir trống → `[]` với HTTP 200
  - [x] Test: cache dir không tồn tại → `[]` với HTTP 200
  - [x] Test: file tên không match pattern → bị skip, không xuất hiện
  - [x] Test: `exported` field luôn là `false`
  - [x] Test: thứ tự sorted (alphabetical, consistent)
  - [x] Dùng `tmp_path` fixture của pytest để isolate test cache dirs

## Dev Notes

### ⚠️ CRITICAL: Không đọc nội dung Parquet file

Story 1.3 chỉ **parse filename** — KHÔNG mở file, KHÔNG đọc nội dung Parquet. Đây là requirement NFR1 (< 200ms) và là quyết định thiết kế rõ ràng từ PRD:

> "GET /api/sessions: parse filename only — không đọc file content"

`pyarrow.parquet.read_table()` KHÔNG được gọi trong story này. `Path.glob("*.parquet")` → regex parse → return. Period.

### Filename Pattern — Phase 2 Sessions

Phase 2 session files dùng pattern **khác** với Phase 1 Parquet cache:

| | Phase 1 cache | Phase 2 sessions |
|---|---|---|
| Pattern | `{SYMBOL_NORMALIZED}_{TIMEFRAME}.parquet` | `{SYMBOL}_{timeframe}_{YYYYMMDD}.parquet` |
| Example | `BTC_USDT_4h.parquet` | `BTCUSDT_4h_20260420.parquet` |
| Symbol | `BTC_USDT` (slash → underscore) | `BTCUSDT` (no separator) |
| Date | ❌ không có | ✅ YYYYMMDD |

Phase 2 session files là các snapshot Parquet của một replay session cụ thể — **khác về naming** với Phase 1 raw OHLCV cache. Dev không được nhầm lẫn hai loại này.

**Regex chính xác:**
```python
import re

SESSION_FILENAME_PATTERN = re.compile(
    r"^([A-Z0-9]+)_([A-Za-z0-9]+)_(\d{8})\.parquet$"
)
```

Matching examples:
- `BTCUSDT_4h_20260420.parquet` → symbol=`BTCUSDT`, timeframe=`4h`, date_raw=`20260420`
- `ETHUSDT_1h_20260415.parquet` → symbol=`ETHUSDT`, timeframe=`1h`, date_raw=`20260415`
- `BTC_USDT_4h.parquet` → **KHÔNG match** (Phase 1 file, bị skip — đúng behavior)
- `random_file.parquet` → **KHÔNG match**, bị skip — đúng behavior
- `BTCUSDT_4h_20260420.parquet.tmp` → **KHÔNG match** (`.tmp` extension), bị skip

### `backend/models.py` — Thêm `SessionItem`

```python
# Thêm vào cuối models.py (sau các models hiện có)

class SessionItem(BaseModel):
    """Một Parquet session file trong cache/ — metadata từ filename only."""
    filename: str           # "BTCUSDT_4h_20260420.parquet"
    symbol: str             # "BTCUSDT"
    timeframe: str          # "4h"
    date: str               # "2026-04-20" (YYYY-MM-DD format)
    exported: bool          # hardcode False — Story 3.3 sẽ implement tracking
```

### `backend/routes/sessions.py` — Implementation Đầy Đủ

```python
import re
from pathlib import Path

from fastapi import APIRouter

from backend.models import APIResponse, SessionItem
from backend.settings import settings

router = APIRouter(prefix="/api")

SESSION_FILENAME_PATTERN = re.compile(
    r"^([A-Z0-9]+)_([A-Za-z0-9]+)_(\d{8})\.parquet$"
)


def _parse_session_filename(filename: str) -> SessionItem | None:
    """Parse session metadata từ filename. Return None nếu không match pattern."""
    match = SESSION_FILENAME_PATTERN.match(filename)
    if not match:
        return None

    symbol, timeframe, date_raw = match.groups()
    # "20260420" → "2026-04-20"
    date_formatted = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}"

    return SessionItem(
        filename=filename,
        symbol=symbol,
        timeframe=timeframe,
        date=date_formatted,
        exported=False,  # Story 3.3 sẽ implement tracking
    )


@router.get("/sessions", response_model=APIResponse[list[SessionItem]])
async def list_sessions() -> APIResponse[list[SessionItem]]:
    """
    Trả về danh sách Parquet session files trong cache directory.
    Chỉ parse filename — không đọc nội dung file.
    """
    cache_dir: Path = settings.cache_dir

    # Handle missing cache dir gracefully — không 404
    if not cache_dir.exists():
        return APIResponse(data=[], error=None)

    sessions: list[SessionItem] = []
    for path in sorted(cache_dir.glob("*.parquet")):
        session = _parse_session_filename(path.name)
        if session is not None:
            sessions.append(session)

    return APIResponse(data=sessions, error=None)
```

**Lý do `sorted()`:** Đảm bảo consistent ordering cho UI (alphabetical by filename = by date asc). `Path.glob()` không đảm bảo thứ tự.

### `backend/main.py` — Thêm Router Registration

Trong `create_app()`, thêm sessions router sau các stub routes từ Story 1.1:

```python
from backend.routes.sessions import router as sessions_router

def create_app() -> FastAPI:
    app = FastAPI(...)

    # Phase 1 stub routes (từ Story 1.1)
    app.include_router(ohlcv_router)
    app.include_router(fetch_router)

    # Phase 2 routes
    app.include_router(sessions_router)  # ← THÊM DÒNG NÀY

    return app
```

### `tests/test_sessions.py` — Test Implementation

```python
import pytest
from fastapi.testclient import TestClient
from pathlib import Path


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    """TestClient với cache_dir isolated trong tmp_path."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path / "cache")
    (tmp_path / "cache").mkdir(parents=True)

    from backend.main import create_app
    return TestClient(create_app())


def test_list_sessions_two_valid_files(client, tmp_path):
    cache = tmp_path / "cache"
    (cache / "BTCUSDT_4h_20260420.parquet").touch()
    (cache / "ETHUSDT_1h_20260415.parquet").touch()

    response = client.get("/api/sessions")
    assert response.status_code == 200

    data = response.json()["data"]
    assert len(data) == 2

    btc = next(s for s in data if s["symbol"] == "BTCUSDT")
    assert btc["filename"] == "BTCUSDT_4h_20260420.parquet"
    assert btc["timeframe"] == "4h"
    assert btc["date"] == "2026-04-20"
    assert btc["exported"] is False


def test_list_sessions_empty_cache(client):
    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert response.json()["data"] == []
    assert response.json()["error"] is None


def test_list_sessions_cache_dir_missing(tmp_path, monkeypatch):
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path / "nonexistent")

    from backend.main import create_app
    c = TestClient(create_app())

    response = c.get("/api/sessions")
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_list_sessions_skips_non_matching_files(client, tmp_path):
    cache = tmp_path / "cache"
    # Phase 1 file — KHÔNG match Phase 2 pattern
    (cache / "BTC_USDT_4h.parquet").touch()
    # Temp file — KHÔNG match
    (cache / "BTCUSDT_4h_20260420.parquet.tmp").touch()
    # Non-parquet
    (cache / "readme.txt").touch()
    # Valid Phase 2 file
    (cache / "BTCUSDT_4h_20260420.parquet").touch()

    response = client.get("/api/sessions")
    data = response.json()["data"]

    assert len(data) == 1
    assert data[0]["filename"] == "BTCUSDT_4h_20260420.parquet"


def test_list_sessions_supabase_disabled_still_works(client, tmp_path, monkeypatch):
    """Endpoint không phụ thuộc SUPABASE_ENABLED."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "supabase_enabled", False)

    cache = tmp_path / "cache"
    (cache / "BTCUSDT_4h_20260420.parquet").touch()

    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
```

### APIResponse Wrapper — Pattern từ Architecture

Story này sử dụng `APIResponse[list[SessionItem]]` wrapper — đây là contract **bắt buộc** từ ADR-17:

```python
# ✅ ĐÚNG — luôn dùng APIResponse wrapper
return APIResponse(data=sessions, error=None)

# ❌ SAI — return list trực tiếp
return sessions
```

Frontend và tests đều expect `response.json()["data"]` và `response.json()["error"]` — không phải raw array.

### Settings Access Pattern

```python
# ✅ ĐÚNG — import singleton trực tiếp
from backend.settings import settings

cache_dir: Path = settings.cache_dir

# ❌ SAI — FastAPI Depends (overkill cho settings)
# ❌ SAI — os.getenv("CACHE_DIR") trực tiếp
```

### Files Cần Tạo / Sửa Trong Story Này

| File | Action | Notes |
|------|--------|-------|
| `backend/models.py` | **MODIFY** | Thêm `SessionItem` class |
| `backend/routes/sessions.py` | **CREATE NEW** | Phase 2 route mới |
| `backend/main.py` | **MODIFY** | Thêm router registration |
| `tests/test_sessions.py` | **CREATE NEW** | Tests cho story này |

> **Không tạo service file riêng** — logic quá đơn giản (glob + regex). YAGNI principle per PRD.

### Backward-Compatibility với Phase 1

- Phase 1 routes (`/api/ohlcv`, `/api/fetch`) hoàn toàn không bị ảnh hưởng
- `SessionItem` model mới — additive, không modify existing models
- `settings.cache_dir` đã tồn tại từ Story 1.1 — không cần thay đổi Settings
- `SUPABASE_ENABLED=false` (Phase 1 default) không ảnh hưởng endpoint này

### Edge Case — Concurrent File Access

`Path.glob("*.parquet")` chỉ đọc directory listing, không mở files. Thread-safe trên macOS/Linux. Không cần file locking.

### NFR1: Performance

> NFR1 (Medium): Session list load < 200ms (filename parse only, local machine)

Implementation này đảm bảo < 200ms vì:
1. Chỉ đọc directory listing — không mở file nào
2. Regex matching là O(n) với n = số files
3. 100 files = ~1ms trên local SSD
4. Không có I/O blocking (không await) — dù endpoint là `async`, không có coroutine await nào

### References

- [epics.md - Story 1.3 Acceptance Criteria](_bmad-output/planning-artifacts/epics.md#story-13-get-apisessions--danh-sách-parquet-sessions)
- [prd-phase2-supabase.md - GET /api/sessions API Contract](_bmad-output/planning-artifacts/prd-phase2-supabase.md#session-list--get-apisessions)
- [architecture.md - ADR-09: Backend Module Structure](_bmad-output/planning-artifacts/architecture.md#adr-09-backend-module-structure)
- [architecture.md - ADR-17: Error Response Format](_bmad-output/planning-artifacts/architecture.md#adr-17-error-response-format)
- [architecture.md - ADR-11: Pydantic Settings](_bmad-output/planning-artifacts/architecture.md#adr-11-pydantic-settings)
- [1-1-them-supabase-config-vao-backend-settings.md - Settings + models.py patterns](_bmad-output/implementation-artifacts/1-1-them-supabase-config-vao-backend-settings.md)
- PRD NFR1: Session list load < 200ms

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

Không có issues — implementation straightforward theo spec.

### Completion Notes List

- ✅ Task 1: `SessionItem(BaseModel)` thêm vào `backend/models.py` — 5 fields, không phá vỡ existing models
- ✅ Task 2: `backend/routes/sessions.py` — APIRouter prefix `/api`, GET /sessions, regex parse, date format, skip non-match, handle missing dir
- ✅ Task 3: `backend/main.py` — thêm `sessions_router` registration sau stub routes
- ✅ Task 4: 7 tests — 2 valid files, empty cache, missing dir, skip non-matching, supabase_disabled, exported=false, sorted order
- Tests chạy: 15 passed (7 new + 8 regression), 0 failed, 0 errors (0.18s)

### File List

- `backend/models.py` (sửa — thêm `SessionItem` model)
- `backend/routes/sessions.py` (tạo mới — GET /api/sessions, regex parser, APIResponse wrapper)
- `backend/main.py` (sửa — đăng ký sessions_router)
- `tests/test_sessions.py` (tạo mới — 7 tests cho AC#1–#5)

### Review Findings

- [x] [Review][Patch] Path traversal: `cache_dir / filename` trong `preview_session` không validate containment — fixed: containment check trước `.exists()` [`backend/routes/sessions.py`]
- [x] [Review][Patch] `cache_dir.exists()` không check `is_dir()` — fixed: đổi thành `cache_dir.is_dir()` [`backend/routes/sessions.py`]
- [x] [Review][Patch] Symlinks trong cache_dir follow ra ngoài tree — fixed: guard `path.resolve().is_relative_to(resolved_cache)` trong for loop [`backend/routes/sessions.py`]
- [x] [Review][Patch] Exception detail leaked trong preview_session response — fixed: message tĩnh + `logger.exception()` server-side [`backend/routes/sessions.py`]
- [x] [Review][Patch] `sorted()` sort theo full path — fixed: `key=lambda p: p.name` [`backend/routes/sessions.py`]
- [x] [Review][Defer] Regex `\d{8}` không validate calendar date thực [`backend/routes/sessions.py:13`] — deferred, pre-existing — defer sang Story 4.3

## Change Log

| Date | Change | Author |
|---|---|---|
| 2026-04-27 | Story 1.3 implemented: SessionItem model, GET /api/sessions route (filename-only parse, regex pattern, sorted output), router registration, 7 tests pass. Toàn bộ 15 tests pass (no regression). | claude-sonnet-4-6 |
| 2026-04-27 | Code review: 5 patch findings, 1 deferred, 3 dismissed | claude-sonnet-4-6 |
