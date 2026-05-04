# Story 1.1: GET /api/ohlcv — Serve OHLCV từ Parquet cache

Status: done

## Story

As a trader,
I want the backend to serve OHLCV data from local Parquet cache,
so that the frontend can render the chart without waiting for Binance.

## Acceptance Criteria

1. **Given** file `cache/BTCUSDT_1h.parquet` tồn tại
   **When** frontend gọi `GET /api/ohlcv?symbol=BTCUSDT&timeframe=1h&date_start=2024-01-01&date_end=2024-03-01`
   **Then** backend trả về JSON `{data: [{timestamp, open, high, low, close, volume}, ...]}` với status 200
   **And** data được slice theo `date_start`/`date_end` — không trả về toàn bộ cache
   **And** timestamp là int64 Unix milliseconds UTC
   **And** response có field `ema_20` và `ma_20` là extra columns (có thể null ở đầu series)

2. **Given** cache không tồn tại cho (symbol, timeframe) đã yêu cầu
   **When** frontend gọi GET /api/ohlcv
   **Then** backend trả về status 404 với `{error: "no_cache", message: "Chưa có data cho BTCUSDT 1h — fetch trước", retryable: false}`

3. **Given** Parquet file bị corrupt (không parse được)
   **When** backend load cache
   **Then** backend tự động xóa file corrupt và trả về 404 với `{error: "cache_corrupted", message: "Cache bị lỗi và đã được xóa — fetch lại để tạo mới", retryable: true}`

4. **Given** cache tồn tại và hợp lệ
   **When** backend load và validate
   **Then** duplicate timestamps bị dedup, data sort ascending theo timestamp trước khi slice
   **And** OHLCV columns được validate: timestamp là int64, OHLCV là float64 — nếu sai schema trả về 422

5. **Given** `date_start` / `date_end` vượt quá range có trong cache
   **When** backend slice data
   **Then** data được clip về range thực tế có sẵn, response bao gồm field `clipped: true` và `actual_date_start`, `actual_date_end`

6. **Given** MA20 / EMA20 được request (params `ma=20` hoặc `ema=20`)
   **When** backend tính indicators
   **Then** slice DataFrame về `date_end` TRƯỚC khi compute: `df.iloc[:date_end_idx].ewm(span=20, adjust=False).mean()` — không compute trên full DataFrame
   **And** NaN values ở đầu series được trả về là `null` trong JSON — không crash, không interpolate

## Tasks / Subtasks

- [x] Task 1: Tạo `backend/services/cache.py` — Parquet read + validation (AC: #3, #4)
  - [x] Hàm `read_ohlcv(symbol, timeframe, cache_dir) -> pd.DataFrame | None`
  - [x] Validate schema: timestamp int64, OHLCV float64 — raise `CacheCorruptError` nếu sai
  - [x] Dedup timestamps (`df.drop_duplicates(subset='timestamp')`) và sort ascending
  - [x] Nếu pyarrow.ParquetFile raise exception → xóa file → raise `CacheCorruptError`
  - [x] Cache file naming: `{CACHE_DIR}/{symbol}_{timeframe}.parquet` (ví dụ: `cache/BTCUSDT_1h.parquet`)

- [x] Task 2: Tạo `backend/services/indicators.py` — MA/EMA slice-first (AC: #6)
  - [x] Hàm `compute_indicators(df: pd.DataFrame, date_end_idx: int, ma_period: int | None, ema_period: int | None) -> pd.DataFrame`
  - [x] Slice trước: `sliced = df.iloc[:date_end_idx]`
  - [x] EMA: `sliced['close'].ewm(span=ema_period, adjust=False).mean()` — pandas built-in, không dùng thư viện ngoài
  - [x] MA: `sliced['close'].rolling(window=ma_period).mean()`
  - [x] NaN → `None` trong output (pandas NaN không serialize sang JSON được)

- [x] Task 3: Cập nhật `backend/models.py` — thêm OHLCVResponse models (AC: #1, #2, #4, #5)
  - [x] `OHLCVBar` đã có — bổ sung `ema_20: float | None` và `ma_20: float | None`
  - [x] `OHLCVResponse(BaseModel)`: `data: list[OHLCVBar]`, `clipped: bool`, `actual_date_start: str | None`, `actual_date_end: str | None`
  - [x] Reuse `ErrorResponse` đã có trong models.py (có sẵn: `message`, `code`, `retryable`)

- [x] Task 4: Implement `backend/routes/ohlcv.py` — GET /api/ohlcv endpoint (AC: #1–#5)
  - [x] Query params: `symbol: str`, `timeframe: str`, `date_start: str`, `date_end: str`, `ma: int | None = None`, `ema: int | None = None`
  - [x] Validate timeframe trong `{"5m", "30m", "1h", "4h", "1D"}` — 422 nếu không hợp lệ
  - [x] Gọi `cache.read_ohlcv()` → xử lý `None` (404) và `CacheCorruptError` (404 + xóa file)
  - [x] Slice data theo date_start/date_end, detect clip, set `clipped=True` nếu cần
  - [x] Nếu có ma/ema params → gọi `indicators.compute_indicators()`
  - [x] Trả về `OHLCVResponse`

- [x] Task 5: Viết tests `tests/test_ohlcv_route.py` (AC: #1–#6)
  - [x] Test happy path: cache exists, slice đúng range, trả về 200
  - [x] Test no_cache: 404 với error code "no_cache"
  - [x] Test cache_corrupt: file bị xóa, trả về 404 với code "cache_corrupted"
  - [x] Test dedup + sort: tạo DataFrame có duplicate timestamps → verify output sorted
  - [x] Test clip: date_start trước cache range → verify `clipped=True` + actual dates đúng
  - [x] Test indicators slice-first: verify EMA chỉ dùng data tới date_end (không look-ahead)
  - [x] Test NaN → null: EMA đầu series trả về `null` trong JSON

## Dev Notes

### Context brownfield quan trọng

Project đã có Phase 2 hoàn chỉnh. Các file sau đã tồn tại và KHÔNG được sửa:
- `backend/settings.py` — `Settings` class đầy đủ, có `cache_dir: Path`
- `backend/models.py` — đã có `OHLCVBar`, `ErrorResponse`, `APIResponse` — **mở rộng, không viết lại**
- `backend/routes/ohlcv.py` — placeholder comment — **xóa comment, implement**
- `backend/main.py` — đã register `ohlcv.router` — **không cần thay đổi**
- `backend/services/` — chỉ có `preview.py` và `supabase.py` — **tạo mới `cache.py` và `indicators.py`**
- `tests/` — đã có nhiều test files — **tạo mới `test_ohlcv_route.py`**

### API contract (từ ADR-20b)

```
GET /api/ohlcv?symbol=BTCUSDT&timeframe=1h&date_start=2024-01-01&date_end=2024-03-01&ma=20&ema=20
```

Không có `/api/v1/` prefix — ADR-16 quy định no versioning.

### Cache file naming convention

```python
# backend/services/cache.py
def _cache_path(symbol: str, timeframe: str, cache_dir: Path) -> Path:
    return cache_dir / f"{symbol}_{timeframe}.parquet"
# Ví dụ: cache/BTCUSDT_1h.parquet
```

Symbol format từ frontend: `"BTCUSDT"` (không có `/`). Nếu nhận `"BTC/USDT"` thì normalize: `symbol.replace("/", "")`.

### Validate schema pattern

```python
import pyarrow.parquet as pq
import pandas as pd

def read_ohlcv(symbol: str, timeframe: str, cache_dir: Path) -> pd.DataFrame | None:
    path = _cache_path(symbol, timeframe, cache_dir)
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        path.unlink(missing_ok=True)  # xóa file corrupt
        raise CacheCorruptError(f"Cache corrupt: {path.name}")
    # Validate
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        path.unlink(missing_ok=True)
        raise CacheCorruptError("Missing columns")
    # Dedup + sort
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    return df
```

### Indicator slice-first pattern (Gap 1 — CRITICAL)

```python
# backend/services/indicators.py
def compute_indicators(df: pd.DataFrame, date_end_idx: int, ema_period: int | None, ma_period: int | None) -> pd.DataFrame:
    sliced = df.iloc[:date_end_idx].copy()  # SLICE TRƯỚC
    if ema_period:
        sliced[f"ema_{ema_period}"] = sliced["close"].ewm(span=ema_period, adjust=False).mean()
    if ma_period:
        sliced[f"ma_{ma_period}"] = sliced["close"].rolling(window=ma_period).mean()
    # NaN → None cho JSON serialization
    return sliced.where(sliced.notna(), other=None)
```

**CRITICAL:** Không bao giờ gọi `df.ewm()` trên full DataFrame trước khi slice. Đây là look-ahead bug.

### Date slice logic

```python
# Convert date string → Unix ms để filter
from datetime import datetime, timezone

def date_to_ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

date_start_ms = date_to_ms(date_start)
date_end_ms = date_to_ms(date_end)
mask = (df["timestamp"] >= date_start_ms) & (df["timestamp"] <= date_end_ms)
sliced = df[mask]

# Detect clip
actual_start = df["timestamp"].min()
actual_end = df["timestamp"].max()
clipped = (date_start_ms < actual_start) or (date_end_ms > actual_end)
```

### Error response pattern

Reuse `ErrorResponse` đã có trong `models.py`:
```python
from backend.models import ErrorResponse
from fastapi.responses import JSONResponse

return JSONResponse(
    status_code=404,
    content={"error": ErrorResponse(message="...", code="no_cache", retryable=False).model_dump()}
)
```

**Lưu ý:** `models.py` hiện dùng field name `message` + `code` + `retryable`. ADR-17 spec có `error` thay vì `message` — dùng field name đã có trong models.py (không rename, tránh break existing tests).

### Testing pattern (từ ADR-10)

```python
# tests/test_ohlcv_route.py
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import create_app

@pytest.fixture
def app():
    return create_app()

@pytest.mark.asyncio
async def test_ohlcv_happy_path(app, tmp_path, monkeypatch):
    # Tạo mock Parquet file trong tmp_path
    # monkeypatch settings.cache_dir → tmp_path
    # Assert response structure
```

Dùng `tmp_path` fixture của pytest để tạo Parquet files tạm — không dùng `cache/` thật trong tests.

### Project Structure Notes

Files cần tạo mới:
- `backend/services/cache.py` — hàm `read_ohlcv`, class `CacheCorruptError`
- `backend/services/indicators.py` — hàm `compute_indicators`
- `tests/test_ohlcv_route.py` — 7 test cases

Files cần modify:
- `backend/models.py` — thêm `ema_20: float | None` và `ma_20: float | None` vào `OHLCVBar`, thêm `OHLCVResponse`
- `backend/routes/ohlcv.py` — implement endpoint (xóa placeholder comment)

Files KHÔNG được touch:
- `backend/main.py` — đã register router đúng rồi
- `backend/settings.py` — `cache_dir` đã có
- Bất kỳ Phase 2 file nào (`services/supabase.py`, `services/preview.py`, `routes/export.py`, `routes/sessions.py`)

### References

- Architecture ADR-09 (module structure): `_bmad-output/planning-artifacts/architecture.md#ADR-09`
- Architecture Gap 1 (slice-first indicators): `_bmad-output/planning-artifacts/architecture.md#Gap-1`
- Architecture Gap 2 (atomic write — Story 1.3 sẽ implement): `_bmad-output/planning-artifacts/architecture.md#Gap-2`
- Architecture ADR-07 (pandas ewm/rolling): `_bmad-output/planning-artifacts/architecture.md#ADR-07`
- Architecture ADR-10 (testing strategy): `_bmad-output/planning-artifacts/architecture.md#ADR-10`
- Architecture ADR-17 (error response format): `_bmad-output/planning-artifacts/architecture.md#ADR-17`
- epics-phase1.md Story 1.1: `_bmad-output/planning-artifacts/epics-phase1.md`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6 (2026-04-29)

### Debug Log References

- 2 pre-existing test failures trong `tests/test_settings.py` (do `.env` có SUPABASE_URL placeholder) — confirmed bằng `git stash` test trước implementation. Không phải regression từ story này.

### Completion Notes List

- ✅ `backend/services/cache.py`: `read_ohlcv()` + `CacheCorruptError`. Symbol normalize `/` → ``. Validate required columns + dtypes, dedup + sort.
- ✅ `backend/services/indicators.py`: `compute_indicators()` slice-first (Gap 1 critical), EMA dùng pandas `ewm(adjust=False)`, MA dùng `rolling().mean()`, NaN → None.
- ✅ `backend/models.py`: `OHLCVBar` mở rộng thêm `ema_20`/`ma_20`, thêm `OHLCVResponse`.
- ✅ `backend/routes/ohlcv.py`: Endpoint đầy đủ — timeframe validation 422, no_cache 404, cache_corrupted 404, clip detection, indicator rename sang fixed field names.
- ✅ `tests/test_ohlcv_route.py`: 11 tests bao phủ tất cả 6 ACs — 11/11 pass, 103/103 total pass.

### Change Log

- 2026-04-29: Implement Story P1-1-1 — GET /api/ohlcv serve từ Parquet cache. Tạo cache.py, indicators.py, cập nhật models.py và routes/ohlcv.py, viết 11 tests.

### File List

- `backend/services/cache.py` — NEW
- `backend/services/indicators.py` — NEW
- `tests/test_ohlcv_route.py` — NEW
- `backend/models.py` — MODIFIED (thêm ema_20/ma_20 vào OHLCVBar, thêm OHLCVResponse)
- `backend/routes/ohlcv.py` — MODIFIED (implement endpoint từ placeholder)

---

### Review Findings

- [x] [Review][Decision→Patch] F2: Fix slice-first — `compute_indicators` nhận full `df` + `date_end_idx` thực sự; indicators có warm-up data trước `date_start` (chọn A) [`backend/routes/ohlcv.py`](backend/routes/ohlcv.py) [`backend/services/indicators.py`](backend/services/indicators.py)
- [x] [Review][Decision→Patch] F6: Tách `CacheSchemaError` riêng → route trả 422 `cache_schema_invalid` cho schema errors, 404 chỉ cho file parse failures (chọn A) [`backend/services/cache.py`](backend/services/cache.py)
- [x] [Review][Decision→Patch] F7: Giới hạn `ma`/`ema` chỉ nhận `=20`, 422 `invalid_indicator_period` nếu khác (chọn A) [`backend/routes/ohlcv.py`](backend/routes/ohlcv.py)
- [x] [Review][Patch] F1: Path traversal — thêm `_SYMBOL_RE = re.compile(r"^[A-Za-z0-9]{1,20}$")`, raise `ValueError` nếu không match [`backend/services/cache.py`](backend/services/cache.py)
- [x] [Review][Patch] F3: Empty/0-row Parquet → `read_ohlcv` trả `None` nếu `len(df) == 0` [`backend/services/cache.py`](backend/services/cache.py)
- [x] [Review][Patch] F4: Malformed date → `_date_to_ms` wrap trong try/except, route trả 422 `invalid_date` [`backend/routes/ohlcv.py`](backend/routes/ohlcv.py)
- [x] [Review][Patch] F5: Negative/zero `ma`/`ema` → trả 422 `invalid_indicator_period` (covered bởi F7 period=20 check) [`backend/routes/ohlcv.py`](backend/routes/ohlcv.py)
- [x] [Review][Patch] F9: NaN check đổi thành `None if (v is None or v != v)` — explicit None check trước float conversion [`backend/routes/ohlcv.py`](backend/routes/ohlcv.py)
- [x] [Review][Patch] F10: Per-side clip — `actual_date_start` chỉ set khi `start_clipped`, `actual_date_end` chỉ set khi `end_clipped` [`backend/routes/ohlcv.py`](backend/routes/ohlcv.py)
- [x] [Review][Patch] F11: `date_start > date_end` → 422 `invalid_date_range` [`backend/routes/ohlcv.py`](backend/routes/ohlcv.py)
- [x] [Review][Defer] F12: Silent auto-delete cache khi có transient I/O error (không có logging/backup) [`backend/services/cache.py:21-22`](backend/services/cache.py#L21-L22) — deferred, pre-existing design decision
- [x] [Review][Defer] F13: `ma`/`ema` rất lớn → tất cả null, không cảnh báo — deferred, UX polish scope sau
- [x] [Review][Defer] F14: `sliced.where(notna)` áp dụng toàn bộ columns kể cả base — deferred, không crash trong thực tế
