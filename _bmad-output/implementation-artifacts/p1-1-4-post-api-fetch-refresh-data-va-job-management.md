# Story P1-1.4: POST /api/fetch — Full pagination, refresh data + job management

Status: done

## Story

As a trader,
I want to fetch years of Binance data reliably and update my cache incrementally,
So that I can have complete OHLCV history without managing API limits or re-downloading data I already have.

## Acceptance Criteria

1. **Given** cần fetch date range dài hơn 1000 candles (ví dụ: 2 năm BTCUSDT 1h = ~17,520 bars)
   **When** frontend gọi `POST /api/fetch` với `date_start` và `date_end` hợp lệ
   **Then** backend tự động paginate qua tất cả pages (mỗi page = 1000 candles)
   **And** SSE stream gửi progress cập nhật theo từng page: `{"type":"progress","percent":35,"status":"Fetching page 7/50"}`
   **And** khi hoàn thành tất cả pages: `{"type":"done","rows":17520}`
   **And** data được ghép (concat) và lưu xuống cache với atomic write (Story 1.3)
   **And** user không cần biết giới hạn 1000 candles/request (NFR21)

2. **Given** sau mỗi page Binance trả về data
   **When** backend nhận response
   **Then** backend validate `len(received_rows) == expected_rows` cho page đó
   **And** nếu số hàng nhận được ít hơn expected (partial response), retry page đó tối đa 3 lần trước khi tiếp tục
   **And** nếu retry 3 lần vẫn thiếu, ghi log warning và tiếp tục với data hiện có (không abort toàn bộ job)
   *(Gap-8: batch validation)*

3. **Given** Binance trả về HTTP 429 (rate-limit exceeded)
   **When** backend nhận 429 response khi đang fetch
   **Then** backend đọc header `Retry-After` (nếu có) và wait đúng số giây đó
   **And** nếu không có `Retry-After` header, wait mặc định 60 giây
   **And** sau khi wait, retry request đó (không tính vào retry budget của lỗi khác)
   **And** SSE stream gửi event: `{"type":"progress","percent":35,"status":"Rate limited — waiting 60s"}`
   **And** backend không vượt quá 1200 request weight/phút (NFR19)

4. **Given** fetch page gặp lỗi mạng hoặc Binance 5xx
   **When** lỗi xảy ra
   **Then** backend retry tối đa 3 lần với exponential backoff: 1s → 2s → 4s
   **And** sau 3 lần thất bại, SSE gửi `{"type":"error","message":"Fetch failed after 3 retries: <error>"}`
   **And** job được mark là `"error"`, temp file `.parquet.tmp` được xóa (cleanup)
   **And** SSE stream đóng lại

5. **Given** cache file cho (symbol, timeframe) đã tồn tại với data cũ
   **When** frontend gọi `POST /api/fetch` với thêm param `mode=refresh`
   **Then** backend đọc cache hiện tại và lấy `max_timestamp` của bar cuối cùng
   **And** chỉ fetch bars mới hơn `max_timestamp + interval_ms` (không re-download data đã có)
   **And** merge data mới vào DataFrame hiện có: concat → dedup → sort → atomic write
   **And** SSE progress: `{"type":"progress","percent":0,"status":"Refreshing from 2024-12-01..."}`
   **And** nếu cache rỗng hoặc không tồn tại, `mode=refresh` tự động fallback sang `mode=full`
   **And** nếu `date_end` không được truyền trong `mode=refresh`, mặc định là ngày hôm nay (UTC)

6. **Given** job đã hoàn thành (status "done" hoặc "error") từ 5 phút trước
   **When** bất kỳ request mới nào đến server
   **Then** job entry cũ được tự động xóa khỏi `_job_progress` dict (lazy cleanup)
   **And** `GET /api/fetch-status/{job_id}` cho job đã expired → 404 "Job not found"
   **And** lazy cleanup không ảnh hưởng đến job đang running hoặc job vừa hoàn thành < 5 phút

7. **Given** Binance API không khả dụng hoàn toàn (timeout, DNS fail)
   **When** trader dùng `GET /api/ohlcv` với cache đã có
   **Then** cache vẫn serve bình thường — Binance unavailability không ảnh hưởng read path
   **And** chỉ `POST /api/fetch` mới fail (error SSE event sau retry) — không crash server (NFR20, NFR24)

## Tasks / Subtasks

- [x] Task 1: Upgrade `backend/services/binance.py` — full pagination (AC: #1, #2, #3, #4)
  - [x] Thêm helper `_timeframe_to_ms(timeframe: str) -> int` — map timeframe sang milliseconds (ví dụ: "1h" → 3_600_000)
  - [x] Thêm helper `_expected_rows(start_ms, end_ms, interval_ms) -> int` — tính số bars expected cho page
  - [x] Refactor `fetch_ohlcv` thành vòng lặp pagination: `cursor = start_ms; while cursor < end_ms:`
  - [x] Mỗi iteration: fetch 1000 candles từ `cursor` → `cursor + 1000 * interval_ms`; cập nhật `cursor` sau mỗi page
  - [x] Gap-8: sau mỗi page, so sánh `len(rows) vs expected`; retry page tối đa 3 lần nếu thiếu
  - [x] Rate-limit: nếu response status 429, đọc `Retry-After` header, `await asyncio.sleep(wait_time)`, retry (không count vào general retry budget)
  - [x] General retry: catch httpx errors + 5xx, retry với backoff `[1, 2, 4]` giây, max 3 lần; sau 3 lần raise
  - [x] Progress callback: `on_progress(percent, f"Fetching page {page}/{total_pages}")` sau mỗi page thành công
  - [x] Rate-limit progress: `on_progress(current_percent, f"Rate limited — waiting {wait_time}s")`
  - [x] Kết quả: `pd.concat(all_dfs)` → dedup → sort ascending → trả về final DataFrame

- [x] Task 2: Thêm `refresh_ohlcv_fetch` vào `backend/services/binance.py` (AC: #5)
  - [x] Hàm `async def get_cached_max_timestamp(symbol, timeframe, cache_dir) -> int | None`
    - Đọc cache qua `read_ohlcv()` → trả về `int(df["timestamp"].max())` hoặc `None` nếu không có cache
  - [x] Trong `_run_fetch_job` (route hoặc service), check `mode`:
    - `mode=full`: gọi `fetch_ohlcv(symbol, timeframe, date_start, date_end, on_progress)`
    - `mode=refresh`: lấy `max_ts = get_cached_max_timestamp()`; nếu None → fallback sang full; ngược lại: fetch từ `max_ts + interval_ms` đến `date_end or today`; load existing df; concat+dedup+sort; atomic write

- [x] Task 3: Cập nhật `backend/models.py` — thêm `mode` field (AC: #5)
  - [x] Thêm vào `FetchRequest`: `mode: Literal["full", "refresh"] = "full"`
  - [x] Validate: nếu `mode` không phải "full" hoặc "refresh", FastAPI tự validate qua Pydantic Literal

- [x] Task 4: Upgrade `backend/services/job_manager.py` — lazy cleanup (AC: #6)
  - [x] Thêm `_job_completed_at: dict[str, float]` — lưu `time.time()` khi job complete/fail
  - [x] Trong `complete_job()` và `fail_job()`: ghi `_job_completed_at[job_id] = time.time()`
  - [x] Thêm `_cleanup_expired_jobs(ttl_seconds=300)`:
    - Loop qua `_job_completed_at`, xóa entries có age > TTL khỏi cả `_job_progress` và `_job_completed_at`
  - [x] Gọi `_cleanup_expired_jobs()` ở đầu `get_progress()` và `start_job()` (lazy, không background task)

- [x] Task 5: Viết `tests/test_fetch_pagination.py` (AC: #1–#7)
  - [x] Test pagination happy path: mock Binance trả về 3 pages → verify concat 2500 rows, progress calls đúng
  - [x] Test Gap-8 partial page: mock page trả về 999 rows thay vì 1000 → verify retry logic được gọi
  - [x] Test rate-limit (429): mock Binance trả về 429 rồi success → verify sleep được gọi với đúng wait time
  - [x] Test general retry: mock Binance raise `httpx.ConnectError` 2 lần rồi success → verify data đúng
  - [x] Test retry exhausted (3 lần fail): verify hàm raise exception sau 3 lần
  - [x] Test mode=refresh: cache có max_ts → verify chỉ fetch từ max_ts+interval trở đi
  - [x] Test mode=refresh fallback: cache rỗng → verify fallback sang full fetch
  - [x] Test job cleanup: complete job → mock time.time() +301s → verify `get_progress(job_id)` returns None

## Dev Notes

### Context brownfield quan trọng

**`backend/services/binance.py` hiện tại (Story 1.2):**
```python
async def fetch_ohlcv(symbol, timeframe, date_start, date_end, on_progress):
    # SINGLE REQUEST — Story 1.4 upgrade sang full pagination
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(BINANCE_KLINES_URL, params={
            "symbol": symbol, "interval": interval,
            "startTime": start_ms, "endTime": end_ms,
            "limit": 1000,  # chỉ 1 request, tối đa 1000 nến
        })
        resp.raise_for_status()
        raw = resp.json()
    on_progress(100, f"Fetched {len(raw)} candles")
    # ... convert to DataFrame
```
→ **Task 1 refactor hàm này** thành vòng lặp pagination.

**`backend/services/job_manager.py` hiện tại:**
```python
_active_tasks: dict[tuple[str, str], asyncio.Task] = {}
_job_progress: dict[str, dict] = {}
_job_key_map: dict[str, tuple[str, str]] = {}
```
→ **Task 4 thêm** `_job_completed_at` và lazy cleanup.

**`backend/models.py`** đã có `FetchRequest` với `symbol, timeframe, date_start, date_end`.
→ **Task 3 thêm** `mode: Literal["full", "refresh"] = "full"` vào `FetchRequest`.

### Pagination pattern

```python
# backend/services/binance.py

_INTERVAL_MS: dict[str, int] = {
    "5m": 5 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1D": 24 * 60 * 60 * 1000,
}

async def fetch_ohlcv(
    symbol: str,
    timeframe: str,
    date_start: str,
    date_end: str,
    on_progress: Callable[[int, str], None],
) -> pd.DataFrame:
    interval = TIMEFRAME_MAP[timeframe]
    interval_ms = _INTERVAL_MS[timeframe]
    start_ms = _date_to_ms(date_start)
    end_ms = _date_to_ms(date_end)

    total_expected = max(1, (end_ms - start_ms) // interval_ms)
    total_pages = max(1, (total_expected + 999) // 1000)

    all_frames: list[pd.DataFrame] = []
    cursor = start_ms
    page = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        while cursor < end_ms:
            page += 1
            page_end = min(cursor + 1000 * interval_ms, end_ms)
            raw = await _fetch_page_with_retry(
                client, symbol, interval, cursor, page_end
            )
            df_page = _raw_to_df(raw)
            all_frames.append(df_page)
            cursor = int(df_page["timestamp"].max()) + interval_ms

            percent = min(99, int(page / total_pages * 100))
            on_progress(percent, f"Fetching page {page}/{total_pages}")

    if not all_frames:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    result = pd.concat(all_frames, ignore_index=True)
    result = result.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    on_progress(100, f"Done — {len(result)} candles")
    return result
```

### Rate-limit + retry pattern

```python
async def _fetch_page_with_retry(
    client: httpx.AsyncClient,
    symbol: str,
    interval: str,
    start_ms: int,
    end_ms: int,
    max_retries: int = 3,
) -> list:
    backoff = [1, 2, 4]
    for attempt in range(max_retries + 1):
        try:
            resp = await client.get(
                BINANCE_KLINES_URL,
                params={"symbol": symbol, "interval": interval,
                        "startTime": start_ms, "endTime": end_ms, "limit": 1000},
            )
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                await asyncio.sleep(wait)
                continue  # retry không count vào general budget
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as exc:
            if attempt >= max_retries:
                raise
            await asyncio.sleep(backoff[min(attempt, len(backoff) - 1)])
    return []
```

### Refresh mode pattern

```python
# Trong _run_fetch_job (backend/routes/fetch.py hoặc service layer)

if request.mode == "refresh":
    cached_df = read_ohlcv(symbol, timeframe, settings.cache_dir)
    if cached_df is not None and len(cached_df) > 0:
        max_ts = int(cached_df["timestamp"].max())
        interval_ms = _INTERVAL_MS[timeframe]
        new_start_ms = max_ts + interval_ms
        # Convert back to date string cho fetch_ohlcv
        from datetime import datetime, timezone
        date_start_refresh = datetime.fromtimestamp(new_start_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        date_end_refresh = request.date_end or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        new_df = await fetch_ohlcv(symbol, timeframe, date_start_refresh, date_end_refresh, on_progress)
        merged = pd.concat([cached_df, new_df], ignore_index=True)
        merged = merged.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
        write_ohlcv(merged, symbol, timeframe, settings.cache_dir)
    else:
        # Fallback to full fetch
        df = await fetch_ohlcv(symbol, timeframe, request.date_start, request.date_end, on_progress)
        write_ohlcv(df, symbol, timeframe, settings.cache_dir)
else:  # mode == "full"
    df = await fetch_ohlcv(symbol, timeframe, request.date_start, request.date_end, on_progress)
    write_ohlcv(df, symbol, timeframe, settings.cache_dir)
```

### Job cleanup pattern

```python
# backend/services/job_manager.py
import time

_job_completed_at: dict[str, float] = {}
_JOB_TTL = 300  # 5 phút

def _cleanup_expired_jobs() -> None:
    now = time.time()
    expired = [jid for jid, ts in _job_completed_at.items() if now - ts > _JOB_TTL]
    for jid in expired:
        _job_progress.pop(jid, None)
        _job_completed_at.pop(jid, None)

def complete_job(job_id: str, rows: int) -> None:
    _cleanup_expired_jobs()  # lazy cleanup
    if job_id in _job_progress:
        _job_progress[job_id].update({"status": "done", "percent": 100, "rows": rows})
    key = _job_key_map.pop(job_id, None)
    if key:
        _active_tasks.pop(key, None)
    _job_completed_at[job_id] = time.time()

# Tương tự cho fail_job() — thêm _job_completed_at[job_id] = time.time()
# Gọi _cleanup_expired_jobs() ở đầu get_progress() và start_job()
```

### Scope boundary — Story 1.4 vs kế tiếp

| Feature | Story 1.4 (này) | Story kế tiếp |
|---------|----------------|--------------|
| Full pagination (nhiều pages) | ✓ | |
| Rate-limit handling (429) | ✓ | |
| Exponential backoff retry | ✓ | |
| Gap-8 partial page validation | ✓ | |
| `mode=refresh` incremental fetch | ✓ | |
| Lazy job cleanup (TTL 5 min) | ✓ | |
| **Data gap detection** (clip notification) | | Story 1.5 |
| **MA/EMA slice-first** backend | | Story 1.5 hoặc 2.5 |
| **`GET /api/fetch/jobs`** list endpoint | scope tùy dev | |

### Files cần modify

| File | Thay đổi |
|------|---------|
| `backend/services/binance.py` | Refactor `fetch_ohlcv` sang pagination loop, thêm `_fetch_page_with_retry`, thêm `_INTERVAL_MS` |
| `backend/services/job_manager.py` | Thêm `_job_completed_at`, lazy cleanup, cập nhật `complete_job`/`fail_job` |
| `backend/models.py` | Thêm `mode: Literal["full", "refresh"] = "full"` vào `FetchRequest` |
| `backend/routes/fetch.py` | Cập nhật `_run_fetch_job` để handle `mode=refresh` |

### Files cần tạo mới

| File | Nội dung |
|------|---------|
| `tests/test_fetch_pagination.py` | Unit tests cho pagination, retry, rate-limit, refresh mode, cleanup |

### Files KHÔNG được touch

- `backend/services/cache.py` — Story 1.3 scope
- `backend/routes/ohlcv.py` — Story 1.1 scope
- `backend/settings.py` — không cần setting mới
- Bất kỳ Phase 2 file nào

### References

- Architecture Gap-5 (async SSE fetch): `_bmad-output/planning-artifacts/architecture.md#Gap-5`
- Architecture Gap-8 (batch validation): `_bmad-output/planning-artifacts/architecture.md#Gap-8`
- NFR19 (rate-limit), NFR20 (fallback), NFR21 (pagination transparent): epics-phase1.md
- Epic story definition: `_bmad-output/planning-artifacts/epics-phase1.md#Story-1.4`
- Previous story P1-1.3: `_bmad-output/implementation-artifacts/p1-1-3-atomic-parquet-write-va-cache-management.md`
- Previous story P1-1.2: `_bmad-output/implementation-artifacts/p1-1-2-post-api-fetch-async-binance-fetch-voi-sse-progress.md`

## Review Findings (2026-05-03)

| # | Severity | File | Description | Status |
|---|----------|------|-------------|--------|
| F1 | HIGH | binance.py:75-80 | 429 consecutive retries → silent empty return → data loss | **Fixed** |
| F2 | MED | binance.py:100-109 | Gap-8 inner retry `max_retries=0` → network error kills entire fetch | **Fixed** |
| F3 | MED | binance.py:107 | `raw = raw_retry` overwrites even when retry returns fewer rows | **Fixed** |
| F4 | LOW | job_manager.py:13-18 | `_cleanup_expired_jobs` doesn't clean `_job_key_map` | Deferred |
| F5 | LOW | test:187-188 | `test_partial_page_retry` weak assertions | Deferred |
| F6 | LOW | test:4-11 | AC7 claimed but not tested | Deferred |
| F7 | LOW | test:327-330 | `empty_cache` test identical to `no_cache` | Deferred |
| F8 | LOW | binance.py:76 | `Retry-After` value not validated | Deferred |

**Fixes applied:**
- F1: Added `_MAX_429_RETRIES = 5` limit; after loop exhaustion with rate-limit hits, raises `RuntimeError` instead of silent empty return
- F2: Changed `max_retries=0` → `max_retries=1` in inner retry; wrapped in try/except so network errors don't propagate
- F3: Changed `raw = raw_retry` → `if len(raw_retry) > len(raw): raw = raw_retry`

**Tests:** 17/17 pass (2 new: `test_rate_limit_429_exhaustion_raises`, `test_partial_page_retry_keeps_best_result`)

## Dev Agent Record

### Agent Model Used

Claude (mimo-v2.5-pro)

### Debug Log References

- Pagination test date range issue: 3-day range produced only 72 bars (1 page), fixed by using larger date range with exact ms boundaries
- Partial page retry triggering on last page: expected_rows based on time range vs actual data count mismatch, fixed by using exact ms boundary dates
- httpx.AsyncClient mocking: initial mock approach didn't work with async context manager, fixed by creating MockAsyncClient class

### Completion Notes List

- Refactored `fetch_ohlcv` from single-request to pagination loop with cursor-based iteration
- Added `_INTERVAL_MS` mapping for all supported timeframes
- Added `_raw_to_df` helper to extract DataFrame conversion logic
- Added `_fetch_page_with_retry` with rate-limit (429) handling and exponential backoff
- Added Gap-8 partial page validation with retry (up to 3 attempts per page)
- Added `get_cached_max_timestamp` for refresh mode support
- Updated `FetchRequest` model with `mode: Literal["full", "refresh"]` field
- Updated `_run_fetch_job` route to handle mode=refresh with merge logic
- Added lazy job cleanup with 5-minute TTL to `job_manager.py`
- Updated existing test fixture to clear `_job_completed_at`
- Created 15 comprehensive tests covering all ACs

### File List

- `backend/services/binance.py` — Refactored to pagination loop, added `_INTERVAL_MS`, `_raw_to_df`, `_fetch_page_with_retry`, `get_cached_max_timestamp`
- `backend/services/job_manager.py` — Added `_job_completed_at`, `_cleanup_expired_jobs`, updated `complete_job`/`fail_job`/`get_progress`/`start_job`
- `backend/models.py` — Added `mode: Literal["full", "refresh"] = "full"` to `FetchRequest`, date_end optional for refresh mode
- `backend/routes/fetch.py` — Updated `_run_fetch_job` to handle `mode=refresh`, pass `mode` param
- `tests/test_fetch_pagination.py` — New: 15 tests for pagination, retry, rate-limit, refresh, cleanup
- `tests/test_fetch_route.py` — Updated `reset_job_manager` fixture to clear `_job_completed_at`
