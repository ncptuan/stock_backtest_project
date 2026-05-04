# Story P1-1.2: POST /api/fetch — Async Binance fetch với SSE progress

Status: done

## Story

As a trader,
I want to trigger a data fetch from Binance with real-time progress,
so that I can see how long the download will take without the UI freezing.

## Acceptance Criteria

1. **Given** trader muốn fetch BTCUSDT 1h
   **When** frontend gọi `POST /api/fetch` với body `{symbol, timeframe, date_start, date_end}`
   **Then** backend trả về `202 Accepted` với `{job_id: "..."}` ngay lập tức (non-blocking)
   **And** fetch chạy async trong background — server vẫn nhận và xử lý requests khác bình thường

2. **Given** fetch job đang chạy cho cùng `(symbol, timeframe)`
   **When** frontend gọi `POST /api/fetch` lần nữa với cùng symbol+timeframe
   **Then** backend trả về `409 Conflict` với `{message: "Fetch already in progress", code: "FETCH_IN_PROGRESS", retryable: false}`
   **And** job đang chạy không bị ảnh hưởng

3. **Given** fetch job đang chạy (job_id đã có)
   **When** frontend connect `GET /api/fetch-stream/{job_id}` (SSE)
   **Then** backend stream JSON events qua SSE `data: {"type":"progress","percent":45,"status":"Fetching page 12/50"}\n\n`
   **And** khi fetch hoàn thành: `data: {"type":"done","rows":52000}\n\n`
   **And** khi fetch lỗi: `data: {"type":"error","message":"..."}\n\n`

4. **Given** SSE connection mở và fetch đang chạy
   **When** 15 giây trôi qua mà không có progress event
   **Then** backend gửi heartbeat `data: {"type":"ping"}\n\n` để giữ connection qua proxy

5. **Given** job_id không tồn tại
   **When** frontend gọi `GET /api/fetch-stream/{job_id}` hoặc `GET /api/fetch-status/{job_id}`
   **Then** backend trả về `404` với `{message: "Job not found", code: "JOB_NOT_FOUND", retryable: false}`

6. **Given** fetch job đang chạy
   **When** frontend gọi `GET /api/fetch-status/{job_id}` (polling fallback khi SSE không dùng được)
   **Then** backend trả về JSON `{job_id, status, percent, status_text}` với status 200
   **And** status là một trong: `"running"`, `"done"`, `"error"`

7. **Given** fetch job đang chạy
   **When** frontend gọi `DELETE /api/fetch/{job_id}`
   **Then** background task bị cancel, temp file được cleanup nếu có
   **And** backend trả về `204 No Content`
   **And** job entry được xóa khỏi active jobs dict

8. **Given** fetch hoàn thành thành công
   **When** Binance trả về data hợp lệ
   **Then** data được lưu xuống `cache/{symbol}_{timeframe}.parquet` (plain write — Story 1.3 sẽ upgrade sang atomic write)
   **And** GET /api/ohlcv cho cùng (symbol, timeframe) sau đó serve được data vừa fetch

## Tasks / Subtasks

- [x] Task 1: Tạo `backend/services/binance.py` — Binance API client (AC: #1, #3, #8)
  - [x] Hàm `async def fetch_ohlcv(symbol, timeframe, date_start, date_end, on_progress) -> pd.DataFrame`
  - [x] Gọi `GET https://api.binance.com/api/v3/klines` — public API, không cần API key
  - [x] Timeframe mapping: `{"5m":"5m","30m":"30m","1h":"1h","4h":"4h","1D":"1d"}` — Binance dùng lowercase "1d"
  - [x] Single-request implementation (tối đa 1000 candles) — Story 1.4 sẽ thêm full pagination
  - [x] Convert response sang DataFrame với columns: `timestamp(int64), open, high, low, close, volume(float64)`
  - [x] Gọi `on_progress(percent: int, status_text: str)` sau khi nhận response
  - [x] Dùng `httpx.AsyncClient` — async-native, không dùng `requests` (blocking)

- [x] Task 2: Tạo `backend/services/job_manager.py` — Job tracking + lock (AC: #2, #4, #6, #7)
  - [x] Global `_active_tasks: dict[tuple[str, str], asyncio.Task]` — key là `(symbol, timeframe)`
  - [x] Global `_job_progress: dict[str, dict]` — key là `job_id`, value `{status, percent, status_text, error}`
  - [x] Global `_job_key_map: dict[str, tuple[str, str]]` — map job_id → (symbol, timeframe)
  - [x] Hàm `start_job(symbol, timeframe, coro) -> str` — trả về job_id (UUID4), 409 nếu key đã có
  - [x] Hàm `cancel_job(job_id) -> bool` — cancel task, cleanup, trả về True nếu cancelled
  - [x] Hàm `get_progress(job_id) -> dict | None`
  - [x] Hàm `update_progress(job_id, percent, status_text)`
  - [x] Hàm `complete_job(job_id, rows)` — set status "done", xóa khỏi _active_tasks
  - [x] Hàm `fail_job(job_id, message)` — set status "error", xóa khỏi _active_tasks

- [x] Task 3: Thêm `write_ohlcv` vào `backend/services/cache.py` (AC: #8)
  - [x] Hàm `write_ohlcv(df: pd.DataFrame, symbol: str, timeframe: str, cache_dir: Path) -> None`
  - [x] Gọi `df.to_parquet(path)` — plain write, không atomic (Story 1.3 sẽ upgrade)
  - [x] Đảm bảo `cache_dir` tồn tại (`cache_dir.mkdir(parents=True, exist_ok=True)`) trước khi write

- [x] Task 4: Cập nhật `backend/models.py` — thêm Fetch models (AC: #1, #2, #6)
  - [x] `FetchRequest(BaseModel)`: `symbol: str`, `timeframe: str`, `date_start: str`, `date_end: str`
  - [x] `FetchJobResponse(BaseModel)`: `job_id: str`
  - [x] `FetchStatusResponse(BaseModel)`: `job_id: str`, `status: Literal["running","done","error"]`, `percent: int`, `status_text: str`, `error: str | None = None`, `rows: int | None = None`

- [x] Task 5: Implement `backend/routes/fetch.py` — 4 endpoints (AC: #1–#7)
  - [x] `POST /api/fetch` → `FetchJobResponse`, status 202
  - [x] `GET /api/fetch-stream/{job_id}` → `StreamingResponse` (SSE)
  - [x] `GET /api/fetch-status/{job_id}` → `FetchStatusResponse` (polling fallback)
  - [x] `DELETE /api/fetch/{job_id}` → 204
  - [x] Background coroutine `_run_fetch_job` với CancelledError handling

- [x] Task 6: Viết `tests/test_fetch_route.py` (AC: #1–#7)
  - [x] Test `POST /api/fetch` happy path: trả về 202 + job_id hợp lệ
  - [x] Test `POST /api/fetch` 409 conflict: gọi 2 lần cùng symbol+timeframe
  - [x] Test `POST /api/fetch` 422 invalid timeframe: timeframe = "2h"
  - [x] Test `GET /api/fetch-status/{job_id}` khi job đang running
  - [x] Test `GET /api/fetch-status/{job_id}` 404 cho job_id không tồn tại
  - [x] Test `DELETE /api/fetch/{job_id}` → 204 + job bị xóa
  - [x] Mock `binance.fetch_ohlcv` trong tất cả tests (không gọi Binance thật)

## Dev Notes

### Context brownfield quan trọng

Project đã có Phase 2 hoàn chỉnh và Story P1-1.1 đang in-progress. Các file sau **đã tồn tại** và KHÔNG được sửa ngoài scope:
- `backend/settings.py` — `cache_dir: Path = Path("./cache")` đã có
- `backend/main.py` — đã register `fetch.router` via `app.include_router(fetch.router)` — **không cần thay đổi**
- `backend/models.py` — đã có `OHLCVBar`, `OHLCVResponse`, `ErrorResponse`, `APIResponse` — **mở rộng, không viết lại**
- `backend/routes/ohlcv.py` — đã implemented (Story 1.1) — **không touch**
- `backend/services/cache.py` — có `read_ohlcv`, `_cache_path`, `CacheCorruptError` — **thêm `write_ohlcv` vào file này**

File `backend/routes/fetch.py` hiện là **placeholder**:
```python
from fastapi import APIRouter

router = APIRouter()

# Placeholder — POST /api/fetch and GET /api/fetch-stream will be implemented in a later story
```
→ Xóa comment placeholder và implement đầy đủ.

### API contract (ADR-20b + ADR-16)

```
POST /api/fetch          body: {symbol, timeframe, date_start, date_end}
                         → 202 {job_id: "uuid4-string"}
                         → 409 {message, code: "FETCH_IN_PROGRESS", retryable: false}

GET  /api/fetch-stream/{job_id}
                         → SSE text/event-stream
                         data: {"type":"progress","percent":45,"status":"Fetching page 12/50"}\n\n
                         data: {"type":"ping"}\n\n
                         data: {"type":"done","rows":52000}\n\n
                         data: {"type":"error","message":"..."}\n\n

GET  /api/fetch-status/{job_id}
                         → 200 {job_id, status, percent, status_text, rows?, error?}
                         → 404 {message, code: "JOB_NOT_FOUND"}

DELETE /api/fetch/{job_id}
                         → 204 No Content
                         → 404 nếu job không tồn tại
```

Không có `/api/v1/` prefix — ADR-16 quy định no versioning.

### Binance API pattern

```python
# backend/services/binance.py
import asyncio
import httpx
import pandas as pd
from datetime import datetime, timezone
from typing import Callable, Awaitable

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

TIMEFRAME_MAP = {
    "5m": "5m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1D": "1d",   # Binance dùng "1d" lowercase
}

async def fetch_ohlcv(
    symbol: str,
    timeframe: str,
    date_start: str,
    date_end: str,
    on_progress: Callable[[int, str], None],
) -> pd.DataFrame:
    interval = TIMEFRAME_MAP[timeframe]
    start_ms = _date_to_ms(date_start)
    end_ms = _date_to_ms(date_end)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(BINANCE_KLINES_URL, params={
            "symbol": symbol,
            "interval": interval,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 1000,  # Story 1.4 sẽ thêm full pagination
        })
        resp.raise_for_status()
        raw = resp.json()

    on_progress(100, f"Fetched {len(raw)} candles")

    # Convert to DataFrame — Binance klines format:
    # [open_time, open, high, low, close, volume, close_time, ...]
    df = pd.DataFrame(raw, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore"
    ])
    df = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    df["timestamp"] = df["timestamp"].astype("int64")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype("float64")

    return df

def _date_to_ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)
```

**Lưu ý:** Dùng `httpx.AsyncClient` — KHÔNG dùng `requests` (blocking). `httpx` đã có trong pyproject.toml dependencies.

### Job Manager pattern (Gap 10 + Gap 11)

```python
# backend/services/job_manager.py
import asyncio
import uuid

_active_tasks: dict[tuple[str, str], asyncio.Task] = {}
_job_progress: dict[str, dict] = {}
_job_key_map: dict[str, tuple[str, str]] = {}

def start_job(symbol: str, timeframe: str) -> str:
    """Trả về job_id. Raise ValueError nếu job đang chạy (caller map sang 409)."""
    key = (symbol, timeframe)
    if key in _active_tasks and not _active_tasks[key].done():
        raise ValueError("FETCH_IN_PROGRESS")
    job_id = str(uuid.uuid4())
    _job_key_map[job_id] = key
    _job_progress[job_id] = {
        "status": "running",
        "percent": 0,
        "status_text": "Starting...",
        "error": None,
        "rows": None,
    }
    return job_id

def register_task(job_id: str, task: asyncio.Task) -> None:
    key = _job_key_map[job_id]
    _active_tasks[key] = task

def update_progress(job_id: str, percent: int, status_text: str) -> None:
    if job_id in _job_progress:
        _job_progress[job_id]["percent"] = percent
        _job_progress[job_id]["status_text"] = status_text

def complete_job(job_id: str, rows: int) -> None:
    key = _job_key_map.get(job_id)
    if key and key in _active_tasks:
        del _active_tasks[key]
    if job_id in _job_progress:
        _job_progress[job_id]["status"] = "done"
        _job_progress[job_id]["percent"] = 100
        _job_progress[job_id]["rows"] = rows

def fail_job(job_id: str, message: str) -> None:
    key = _job_key_map.get(job_id)
    if key and key in _active_tasks:
        del _active_tasks[key]
    if job_id in _job_progress:
        _job_progress[job_id]["status"] = "error"
        _job_progress[job_id]["error"] = message

def cancel_job(job_id: str) -> bool:
    key = _job_key_map.get(job_id)
    if not key:
        return False
    task = _active_tasks.get(key)
    if task and not task.done():
        task.cancel()
        del _active_tasks[key]
    if job_id in _job_progress:
        del _job_progress[job_id]
    if job_id in _job_key_map:
        del _job_key_map[job_id]
    return True

def get_progress(job_id: str) -> dict | None:
    return _job_progress.get(job_id)
```

**CRITICAL:** Global dicts này sống trong memory của uvicorn process. Restart server = mất state. Đây là acceptable cho MVP single-user tool.

### SSE StreamingResponse pattern (Gap 5 + Gap 9)

```python
# backend/routes/fetch.py
import asyncio
import json
from fastapi.responses import StreamingResponse

async def _sse_generator(job_id: str):
    """Generator cho SSE stream với heartbeat."""
    HEARTBEAT_INTERVAL = 15  # seconds
    POLL_INTERVAL = 0.5      # check progress mỗi 500ms

    last_heartbeat = asyncio.get_event_loop().time()

    while True:
        progress = job_manager.get_progress(job_id)
        if progress is None:
            # Job không còn tồn tại
            yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
            return

        status = progress["status"]

        if status == "done":
            yield f"data: {json.dumps({'type': 'done', 'rows': progress.get('rows', 0)})}\n\n"
            return
        elif status == "error":
            yield f"data: {json.dumps({'type': 'error', 'message': progress.get('error', 'Unknown error')})}\n\n"
            return
        else:
            # Gửi progress event
            yield f"data: {json.dumps({'type': 'progress', 'percent': progress['percent'], 'status': progress['status_text']})}\n\n"

        now = asyncio.get_event_loop().time()
        if now - last_heartbeat >= HEARTBEAT_INTERVAL:
            yield f"data: {json.dumps({'type': 'ping'})}\n\n"
            last_heartbeat = now

        await asyncio.sleep(POLL_INTERVAL)

@router.get("/api/fetch-stream/{job_id}")
async def fetch_stream(job_id: str):
    progress = job_manager.get_progress(job_id)
    if progress is None:
        raise HTTPException(status_code=404, detail={"message": "Job not found", "code": "JOB_NOT_FOUND", "retryable": False})

    return StreamingResponse(
        _sse_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Tắt nginx buffering cho SSE
        },
    )
```

**SSE format chuẩn:** Mỗi event kết thúc bằng 2 newlines `\n\n`. Field là `data:`. Không cần `id:` hay `event:` trong MVP.

### Background task và CancelledError cleanup (Gap 11)

```python
# background coroutine trong fetch.py
async def _run_fetch_job(job_id: str, symbol: str, timeframe: str, date_start: str, date_end: str):
    try:
        def on_progress(percent: int, status_text: str):
            job_manager.update_progress(job_id, percent, status_text)

        df = await binance.fetch_ohlcv(symbol, timeframe, date_start, date_end, on_progress)
        cache.write_ohlcv(df, symbol, timeframe, settings.cache_dir)
        job_manager.complete_job(job_id, rows=len(df))

    except asyncio.CancelledError:
        # Cleanup: xóa temp files nếu có (Story 1.3 sẽ add atomic write)
        # Hiện tại không có temp file → không cần cleanup
        job_manager.fail_job(job_id, "Cancelled")
        raise  # PHẢI re-raise CancelledError — không swallow

    except Exception as e:
        job_manager.fail_job(job_id, str(e))
```

**CRITICAL:** `asyncio.CancelledError` PHẢI được re-raised sau cleanup. Nếu swallow CancelledError, asyncio task không thực sự cancel được.

### `write_ohlcv` thêm vào cache.py

```python
def write_ohlcv(df: pd.DataFrame, symbol: str, timeframe: str, cache_dir: Path) -> None:
    """Plain write — Story 1.3 sẽ upgrade sang atomic write (temp → rename)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(symbol, timeframe, cache_dir)
    df.to_parquet(path, index=False)
```

**Note:** Story 1.3 sẽ replace implementation này thành atomic write pattern. Dev không cần implement atomic write tại đây.

### POST /api/fetch endpoint pattern

```python
@router.post("/api/fetch", status_code=202)
async def start_fetch(req: FetchRequest) -> FetchJobResponse:
    # Normalize symbol
    symbol = req.symbol.upper().replace("/", "")

    # Validate timeframe
    valid_timeframes = {"5m", "30m", "1h", "4h", "1D"}
    if req.timeframe not in valid_timeframes:
        raise HTTPException(
            status_code=422,
            detail={"message": f"Invalid timeframe '{req.timeframe}'", "code": "INVALID_TIMEFRAME", "retryable": False}
        )

    # Start job (409 nếu đang chạy)
    try:
        job_id = job_manager.start_job(symbol, req.timeframe)
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail={"message": "Fetch already in progress", "code": "FETCH_IN_PROGRESS", "retryable": False}
        )

    # Schedule background task
    task = asyncio.create_task(
        _run_fetch_job(job_id, symbol, req.timeframe, req.date_start, req.date_end)
    )
    job_manager.register_task(job_id, task)

    return FetchJobResponse(job_id=job_id)
```

### Testing pattern — mock Binance

```python
# tests/test_fetch_route.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
import pandas as pd

@pytest.fixture
def app():
    from backend.main import create_app
    return create_app()

@pytest.fixture(autouse=True)
def reset_job_manager():
    """Reset global state trước mỗi test để tránh state leak."""
    from backend.services import job_manager
    job_manager._active_tasks.clear()
    job_manager._job_progress.clear()
    job_manager._job_key_map.clear()
    yield
    job_manager._active_tasks.clear()
    job_manager._job_progress.clear()
    job_manager._job_key_map.clear()

@pytest.mark.asyncio
async def test_post_fetch_happy_path(app):
    mock_df = pd.DataFrame({
        "timestamp": [1704067200000],
        "open": [42000.0], "high": [42500.0],
        "low": [41800.0], "close": [42200.0], "volume": [100.0],
    })
    with patch("backend.routes.fetch.binance.fetch_ohlcv", new_callable=AsyncMock, return_value=mock_df):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/fetch", json={
                "symbol": "BTCUSDT", "timeframe": "1h",
                "date_start": "2024-01-01", "date_end": "2024-03-01"
            })
    assert resp.status_code == 202
    assert "job_id" in resp.json()

@pytest.mark.asyncio
async def test_post_fetch_409_conflict(app):
    # Manually inject a "running" job for (BTCUSDT, 1h)
    from backend.services import job_manager
    import asyncio
    job_id = job_manager.start_job("BTCUSDT", "1h")
    # Create a never-completing task to simulate running job
    task = asyncio.create_task(asyncio.sleep(9999))
    job_manager.register_task(job_id, task)
    task.cancel()  # cancel sau khi register để test cleanup

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/fetch", json={
            "symbol": "BTCUSDT", "timeframe": "1h",
            "date_start": "2024-01-01", "date_end": "2024-03-01"
        })
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "FETCH_IN_PROGRESS"
```

**Lưu ý quan trọng:** Test fixtures phải dùng `autouse=True` fixture để reset global state của `job_manager`. Không reset state = test order dependent failures.

### Project Structure Notes

**Files cần tạo mới:**
- `backend/services/binance.py` — async Binance API client
- `backend/services/job_manager.py` — job tracking, lock, cancellation
- `tests/test_fetch_route.py` — 7+ test cases

**Files cần modify:**
- `backend/routes/fetch.py` — implement 4 endpoints (xóa placeholder comment)
- `backend/models.py` — thêm `FetchRequest`, `FetchJobResponse`, `FetchStatusResponse`
- `backend/services/cache.py` — thêm hàm `write_ohlcv` (cuối file)

**Files KHÔNG được touch:**
- `backend/main.py` — đã register fetch.router đúng rồi
- `backend/settings.py` — cache_dir đã có
- `backend/routes/ohlcv.py` — Story 1.1, không liên quan
- Bất kỳ Phase 2 file nào (`routes/export.py`, `routes/sessions.py`, `services/supabase.py`, `services/preview.py`)

### Dependencies check

Kiểm tra `pyproject.toml` — cần có:
- `httpx` — cho async Binance API calls
- `pandas` và `pyarrow` — cho Parquet read/write (đã có từ Story 1.1)
- `fastapi` — đã có
- `pytest-asyncio` — đã có (từ ADR-10)

Nếu `httpx` chưa có trong dependencies: `uv add httpx` hoặc thêm vào pyproject.toml.

### Story 1.2 vs Stories kế tiếp — boundary rõ ràng

| Feature | Story 1.2 (này) | Story kế tiếp |
|---------|----------------|--------------|
| Async endpoint + SSE | ✓ | |
| Job lock (409) | ✓ | |
| Cancellable task | ✓ | |
| Basic Binance fetch (1 request) | ✓ | |
| Plain Parquet write | ✓ | |
| **Atomic write** (temp → rename) | | Story 1.3 |
| **Full pagination** (1000 candles/page loop) | | Story 1.4 |
| **Rate-limit handling** (429 retry) | | Story 1.4 |
| **Partial batch validation** | | Story 1.4 |
| **Data gap detection** | | Story 1.5 |

Dev không cần implement pagination hay atomic write trong story này — chỉ cần đảm bảo basic flow end-to-end hoạt động.

### Lưu ý về pyproject.toml và asyncio_mode

`pyproject.toml` phải có:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

Nếu chưa có, test async sẽ không chạy được. Kiểm tra trước khi viết tests.

### References

- Architecture ADR-05 (Async Fetch): `_bmad-output/planning-artifacts/architecture.md#ADR-05`
- Architecture Gap 5 (SSE progress): `_bmad-output/planning-artifacts/architecture.md#Gap-5`
- Architecture Gap 9 (SSE heartbeat + fallback): `_bmad-output/planning-artifacts/architecture.md#Gap-9`
- Architecture Gap 10 (Job lock): `_bmad-output/planning-artifacts/architecture.md#Gap-10`
- Architecture Gap 11 (Cancellable asyncio.Task): `_bmad-output/planning-artifacts/architecture.md#Gap-11`
- Architecture ADR-09 (module structure): `_bmad-output/planning-artifacts/architecture.md#ADR-09`
- Architecture ADR-10 (testing strategy): `_bmad-output/planning-artifacts/architecture.md#ADR-10`
- Architecture ADR-16 (no versioning): `_bmad-output/planning-artifacts/architecture.md#ADR-16`
- Architecture ADR-20b (API docs): `_bmad-output/planning-artifacts/architecture.md#ADR-20b`
- Epic story definition: `_bmad-output/planning-artifacts/epics-phase1.md#Story-1.2`
- Previous story (Story 1.1): `_bmad-output/implementation-artifacts/p1-1-1-get-api-ohlcv-serve-ohlcv-tu-parquet-cache.md`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6 (2026-04-29)

### Debug Log References

- Test `test_post_fetch_409_conflict`: `asyncio.shield(Future)` không phải coroutine, không thể dùng với `create_task` trực tiếp — sửa bằng cách dùng async function thay thế.
- Test `test_fetch_writes_cache`: `client.get()` được gọi sau khi context manager đóng — sửa bằng cách move vào trong `async with` block.

### Completion Notes List

- ✅ `backend/services/binance.py`: async `fetch_ohlcv()` dùng `httpx.AsyncClient`, timeframe mapping, convert sang DataFrame với đúng dtypes.
- ✅ `backend/services/job_manager.py`: Global in-memory job tracking — `start_job`, `register_task`, `update_progress`, `complete_job`, `fail_job`, `cancel_job`, `get_progress`.
- ✅ `backend/services/cache.py`: Thêm `write_ohlcv()` — plain write (atomic write sẽ implement trong Story 1.3).
- ✅ `backend/models.py`: Thêm `FetchRequest`, `FetchJobResponse`, `FetchStatusResponse`.
- ✅ `backend/routes/fetch.py`: 4 endpoints (POST, GET stream SSE, GET status, DELETE). Background task với CancelledError re-raise. SSE heartbeat 15s.
- ✅ `tests/test_fetch_route.py`: 10 tests bao phủ ACs #1–#7 — 10/10 pass, 113/113 total pass.

### Change Log

- 2026-04-29: Implement Story P1-1-2 — POST /api/fetch async Binance fetch với SSE progress. Tạo binance.py, job_manager.py, cập nhật cache.py, models.py, fetch.py, viết 10 tests.

### File List

- `backend/services/binance.py` — NEW
- `backend/services/job_manager.py` — NEW
- `backend/services/cache.py` — MODIFIED (thêm write_ohlcv)
- `backend/models.py` — MODIFIED (thêm FetchRequest, FetchJobResponse, FetchStatusResponse)
- `backend/routes/fetch.py` — MODIFIED (implement 4 endpoints từ placeholder)
- `tests/test_fetch_route.py` — NEW

---

### Review Findings

- [x] [Review][Decision→Patch] F18: Thêm `_SYMBOL_RE` validation vào `_cache_path()` và `_tmp_path()` trong cache.py; route validate symbol trước khi tạo task (chọn A) [`backend/services/cache.py`](backend/services/cache.py) [`backend/routes/fetch.py`](backend/routes/fetch.py)
- [x] [Review][Patch] F2: Heartbeat timer đổi tên `last_event_time`, reset sau mỗi progress event → chỉ ping khi không có progress trong 15s [`backend/routes/fetch.py`](backend/routes/fetch.py)
- [x] [Review][Patch] F3: `asyncio.get_event_loop()` → `asyncio.get_running_loop()` [`backend/routes/fetch.py`](backend/routes/fetch.py)
- [x] [Review][Patch] F4: `cancel_job()` cleanup progress/key_map/_active_tasks bằng `.pop()` — task's `fail_job` là no-op (intended) [`backend/services/job_manager.py`](backend/services/job_manager.py)
- [x] [Review][Patch] F5: `complete_job`/`fail_job` dùng `_job_key_map.pop(job_id, None)` để cleanup entry [`backend/services/job_manager.py`](backend/services/job_manager.py)
- [x] [Review][Patch] F6: `on_progress(100,...)` gọi SAU DataFrame construction + handle empty `raw=[]` [`backend/services/binance.py`](backend/services/binance.py)
- [x] [Review][Patch] F7+F8: Thêm `model_validator` vào `FetchRequest` — validate date format + `date_start <= date_end` [`backend/models.py`](backend/models.py)
- [x] [Review][Patch] F9: `write_ohlcv` return early nếu `len(df) == 0`; `read_ohlcv` return `None` nếu empty [`backend/services/cache.py`](backend/services/cache.py)
- [x] [Review][Patch] F10: `_VALID_TIMEFRAMES = set(binance.TIMEFRAME_MAP.keys())` — derive từ source of truth [`backend/routes/fetch.py`](backend/routes/fetch.py)
- [x] [Review][Defer] F1: Race window giữa `start_job()` và `register_task()` — safe trong single-loop asyncio, không có `await` giữa 2 lời gọi — deferred, benign today
- [x] [Review][Defer] F11: `complete_job` không xóa stale `_active_tasks` entry cho job done — deferred, không ảnh hưởng correctness
- [x] [Review][Defer] F12: Binance HTTP error body leak vào `error` field — deferred, single-user tool
- [x] [Review][Defer] F14: AC5 race: job bị cancel giữa 404 guard và generator poll → SSE error event — deferred, tiny window trong single-loop asyncio
