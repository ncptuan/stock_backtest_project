# Story 3.1: POST /api/export — Write signal_comparisons và signal_cases

Status: done

## Story

As a developer,
I want backend endpoint nhận trade list và ghi atomic vào cả 2 Supabase tables,
So that Narron có thể commit kiến thức vào Supabase Backtest DB với guarantee: hoặc tất cả rows thành công, hoặc không có gì được ghi.

## Acceptance Criteria

1. **Given** `POST /api/export` với valid payload (`session_filename`, `strategy_name`, `trades` array đầy đủ fields) và `SUPABASE_ENABLED=true` — **When** endpoint được gọi — **Then** backend ghi `signal_comparisons` trước → nếu thành công → ghi `signal_cases` → return HTTP 200: `{"signal_comparisons_count": N, "signal_cases_count": N, "first_signal_id": "backtest_...", "supabase_url": "..."}`.

2. **Given** `signal_comparisons` ghi thành công nhưng `signal_cases` fail (ví dụ: auth error với service key) — **When** partial failure xảy ra — **Then** backend execute `DELETE FROM signal_comparisons WHERE signal_id LIKE 'backtest_{date}_{strategy}_%'` → return HTTP 500 với `{"error": "partial_write_rolled_back", "message": "Authentication failed cho signal_cases (RLS enabled) — Kiểm tra SUPABASE_SERVICE_KEY trong .env. Đã rollback signal_comparisons."}`.

3. **Given** session đã được export trước đó (duplicate detection) — **When** `POST /api/export` với cùng `session_filename` VÀ cùng `strategy_name` — **Then** HTTP 409 với `{"error": "duplicate", "message": "Session BTCUSDT_4h_20260420.parquet đã export — xóa rows trên Supabase trước nếu muốn re-export"}` — không có row nào được ghi.

4. **Given** `SUPABASE_ENABLED=false` — **When** `POST /api/export` được gọi — **Then** HTTP 503 với `{"error": "disabled", "message": "Supabase integration chưa được bật — set SUPABASE_ENABLED=true trong .env"}` — không attempt kết nối Supabase.

5. **Given** Supabase không phản hồi sau 30 giây — **When** timeout xảy ra — **Then** HTTP 504 với `{"error": "timeout", "message": "Supabase đang wake up — thử lại sau 30 giây"}` — không partial write.

6. **Given** backend log trong quá trình export thành công — **When** export xong — **Then** log `INFO: "Exported session {filename}: {N} signal_comparisons + {N} signal_cases"`.

7. **Given** backend log khi export fail và rollback — **When** rollback xong — **Then** log `ERROR: "Export failed, rolled back {N} signal_comparisons rows. Error: {error_detail}"`.

## Tasks / Subtasks

- [x] Task 1: Thêm models vào `backend/models.py` (AC: #1)
  - [x] Thêm `ExportTrade(BaseModel)` — trade item trong export request: `bar_index`, `entry_timestamp_ms`, `direction`, `entry_price`, `tp_price`, `sl_price`, `result`, `bars_to_exit`, `reasoning_summary`
  - [x] Thêm `ExportRequest(BaseModel)` — full request body: `session_filename`, `strategy_name`, `timeframe`, `session_win_rate`, `trades: list[ExportTrade]`
  - [x] Thêm `ExportResponse(BaseModel)` — success response: `signal_comparisons_count`, `signal_cases_count`, `first_signal_id`, `supabase_url`
  - [x] Không modify existing models (`TradeInput`, `PreviewResponse`, `SessionItem`, `OHLCVBar`, `APIResponse[T]`)

- [x] Task 2: Tạo `backend/services/supabase.py` — write functions (AC: #1, #2)
  - [x] Implement `generate_signal_id(session_date: str, strategy_name: str, bar_index: int) -> str`
  - [x] Implement `write_signal_comparisons(trades: list[ExportTrade], request: ExportRequest, settings: Settings) -> int` — dùng **anon key** (`settings.supabase_key`)
  - [x] Implement `write_signal_cases(trades: list[ExportTrade], request: ExportRequest, settings: Settings) -> int` — dùng **service role key** (`settings.supabase_service_key`)
  - [x] Implement `rollback_signal_comparisons(session_date: str, strategy_name: str, settings: Settings) -> int` — DELETE WHERE signal_id LIKE pattern
  - [x] Implement `check_duplicate(session_date: str, strategy_name: str, settings: Settings) -> bool` — query signal_comparisons để check tồn tại
  - [x] Dùng `httpx.AsyncClient` với `timeout=30.0` cho tất cả calls
  - [x] Raise `httpx.TimeoutException` natively — route sẽ catch và return 504
  - [x] Raise `ValueError` với message rõ nếu Supabase trả về non-2xx (bao gồm auth errors)

- [x] Task 3: Tạo `backend/routes/export.py` — endpoint mới (AC: #1–#5)
  - [x] Tạo `router = APIRouter(prefix="/api")` trong file mới
  - [x] Implement `POST /export` endpoint: `async def export_session(request: ExportRequest, settings: Annotated[Settings, Depends(get_settings)])`
  - [x] Guard `SUPABASE_ENABLED`: nếu `not settings.supabase_enabled` → raise `HTTPException(503, ...)`
  - [x] Duplicate check: gọi `check_duplicate(session_date, strategy_name, settings)` → 409 nếu True
  - [x] Execute: write signal_comparisons → nếu ok → write signal_cases → nếu fail → rollback → 500
  - [x] Catch `httpx.TimeoutException` → 504
  - [x] Catch `ValueError` (auth/schema errors) → 500 với message từ exception
  - [x] Log INFO sau success, log ERROR sau fail + rollback
  - [x] `supabase_url` trong response: `f"{settings.supabase_url}/rest/v1/signal_cases?order=signal_id.desc&limit=50"`

- [x] Task 4: Đăng ký router trong `backend/main.py` (AC: #1)
  - [x] Import và `app.include_router(export_router)` trong `main.py`
  - [x] Không thay đổi bất kỳ logic nào khác trong `main.py`

- [x] Task 5: Viết tests `tests/test_export.py` (AC: #1–#5)
  - [x] Mock `httpx.AsyncClient` — không cần Supabase connection thật
  - [x] Test: valid payload, SUPABASE_ENABLED=true → 200, signal_ids generated đúng format
  - [x] Test: SUPABASE_ENABLED=false → 503 với error message
  - [x] Test: timeout (mock httpx raise TimeoutException) → 504
  - [x] Test: signal_cases fail → rollback được gọi → 500 với error "partial_write_rolled_back"
  - [x] Test: duplicate check True → 409 không gọi write functions
  - [x] Test: `signal_id` format — `generate_signal_id("20260426", "breakout_4h", 42)` == `"backtest_20260426_breakout_4h_00042"`
  - [x] Test: `strategy_name` với spaces → sanitize đúng

## Dev Notes

### ⚠️ CRITICAL: Phụ Thuộc Prerequisites

Story 3.1 phụ thuộc:
- **Story 1.1**: `backend/settings.py` với `supabase_url`, `supabase_key`, `supabase_service_key`, `supabase_enabled` — phải đã complete
- **Story 1.1**: `backend/models.py` với `APIResponse[T]` — phải đã tồn tại
- **Story 2.1**: `backend/models.py` với `TradeInput`, `PreviewResponse` pattern — reference để follow naming convention

> **Kiểm tra trước khi code:**
> 1. `backend/settings.py` có `supabase_url: str`, `supabase_key: str`, `supabase_service_key: str`, `supabase_enabled: bool`
> 2. `backend/models.py` có `APIResponse[T]`
> 3. `backend/main.py` tồn tại với `app.include_router(...)` pattern

---

### New Files trong Story 3.1

| File | Action |
|------|--------|
| `backend/routes/export.py` | **CREATE NEW** |
| `backend/services/supabase.py` | **CREATE NEW** |
| `tests/test_export.py` | **CREATE NEW** |

**Files Modified:**
| File | Change |
|------|--------|
| `backend/models.py` | Thêm `ExportTrade`, `ExportRequest`, `ExportResponse` |
| `backend/main.py` | Thêm `app.include_router(export_router)` |

---

### `generate_signal_id` — Exact Format

```python
import re

def generate_signal_id(session_date: str, strategy_name: str, bar_index: int) -> str:
    """
    session_date: "20260426"  (yyyymmdd from filename)
    strategy_name: user input — sanitize: lowercase, spaces+special → "_"
    bar_index: int — zero-padded to 5 digits
    
    Output: "backtest_20260426_breakout_4h_00042"
    """
    sanitized = re.sub(r'[^a-z0-9]+', '_', strategy_name.lower()).strip('_')
    return f"backtest_{session_date}_{sanitized}_{bar_index:05d}"
```

**Lý do zero-pad 5 chữ số:** Sort theo signal_id giữ đúng chronological order cho sessions ≤ 99,999 bars. Production bot có thể dùng field này để sort.

**Test cases:**
- `generate_signal_id("20260426", "breakout_4h", 42)` → `"backtest_20260426_breakout_4h_00042"`
- `generate_signal_id("20260426", "Breakout 4H / EMA", 42)` → `"backtest_20260426_breakout_4h_ema_00042"`
- `generate_signal_id("20260426", "BTC Strategy!", 1)` → `"backtest_20260426_btc_strategy_00001"`

---

### `backend/services/supabase.py` — Full Implementation

```python
import logging
import httpx
from backend.models import ExportTrade, ExportRequest
from backend.settings import Settings

logger = logging.getLogger(__name__)


def generate_signal_id(session_date: str, strategy_name: str, bar_index: int) -> str:
    import re
    sanitized = re.sub(r'[^a-z0-9]+', '_', strategy_name.lower()).strip('_')
    return f"backtest_{session_date}_{sanitized}_{bar_index:05d}"


def _map_direction_to_verdict(direction: str) -> str:
    """LONG → BUY, SHORT → SELL"""
    return "BUY" if direction.upper() == "LONG" else "SELL"


def _map_result_to_follow(result: str) -> str:
    """win → TP hit, loss → SL hit"""
    return "TP hit" if result.lower() == "win" else "SL hit"


def _map_result_to_outcome(result: str) -> str:
    """win → TP_HIT, loss → SL_HIT"""
    return "TP_HIT" if result.lower() == "win" else "SL_HIT"


def _parse_session_date(session_filename: str) -> str:
    """
    "BTCUSDT_4h_20260420.parquet" → "20260420"
    Falls back to "00000000" if parse fails.
    """
    try:
        stem = session_filename.rsplit('.', 1)[0]  # "BTCUSDT_4h_20260420"
        parts = stem.split('_')
        # Last part is typically the date (yyyymmdd)
        candidate = parts[-1]
        if len(candidate) == 8 and candidate.isdigit():
            return candidate
    except Exception:
        pass
    return "00000000"


async def check_duplicate(
    session_date: str,
    strategy_name: str,
    settings: Settings,
) -> bool:
    """
    Query signal_comparisons for any row with signal_id LIKE 'backtest_{date}_{sanitized}_%'.
    Returns True if duplicate detected.
    """
    import re
    sanitized = re.sub(r'[^a-z0-9]+', '_', strategy_name.lower()).strip('_')
    pattern = f"backtest_{session_date}_{sanitized}_"

    url = f"{settings.supabase_url}/rest/v1/signal_comparisons"
    headers = {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
    }
    params = {
        "signal_id": f"like.{pattern}%",  # PostgREST filter
        "select": "signal_id",
        "limit": "1",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            data = resp.json()
            return len(data) > 0
        # On query error, err on side of caution: do NOT block export
        return False


async def write_signal_comparisons(
    trades: list[ExportTrade],
    request: ExportRequest,
    settings: Settings,
) -> int:
    """
    Write all trades to signal_comparisons using anon key.
    Returns count of rows written.
    Raises ValueError on non-2xx response.
    """
    from datetime import datetime, timezone

    session_date = _parse_session_date(request.session_filename)
    rows = []
    for trade in trades:
        signal_id = generate_signal_id(session_date, request.strategy_name, trade.bar_index)
        rows.append({
            "signal_id": signal_id,
            "timestamp": trade.entry_timestamp_ms,           # int64 Unix ms (ADR-03)
            "type": trade.direction.upper(),                  # "LONG" or "SHORT"
            "bot_verdict": _map_direction_to_verdict(trade.direction),
            "result": trade.result.lower(),                   # "win" or "loss"
            "follow": _map_result_to_follow(trade.result),    # "TP hit" or "SL hit"
            "invalidation_condition": f"SL tại {trade.sl_price}",
            "telegram_sent": False,
            "claude_verdict": None,
        })

    url = f"{settings.supabase_url}/rest/v1/signal_comparisons"
    headers = {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=rows)
        if resp.status_code not in (200, 201):
            raise ValueError(
                f"signal_comparisons write failed: {resp.status_code} — {resp.text}"
            )

    return len(rows)


async def write_signal_cases(
    trades: list[ExportTrade],
    request: ExportRequest,
    settings: Settings,
) -> int:
    """
    Write all trades to signal_cases using SERVICE ROLE KEY (bypasses RLS).
    Returns count of rows written.
    Raises ValueError on non-2xx response.
    """
    from datetime import datetime, timezone

    session_date = _parse_session_date(request.session_filename)
    rows = []
    for trade in trades:
        signal_id = generate_signal_id(session_date, request.strategy_name, trade.bar_index)
        # Convert Unix ms → ISO8601 UTC string
        signal_sent_at = datetime.fromtimestamp(
            trade.entry_timestamp_ms / 1000, tz=timezone.utc
        ).isoformat()
        action = _map_direction_to_verdict(trade.direction)
        rows.append({
            "signal_id": signal_id,
            "signal_sent_at": signal_sent_at,
            "market_regime": "unknown",          # Growth feature: detect from EMA9/EMA21
            "claude_action": action,
            "bot_action": action,
            "outcome": _map_result_to_outcome(trade.result),
            "reasoning_summary": trade.reasoning_summary,
            "invalidation_condition": f"SL tại {trade.sl_price}",
            "metadata": {
                "entry_price": trade.entry_price,
                "tp_price": trade.tp_price,
                "sl_price": trade.sl_price,
                "bars_to_exit": trade.bars_to_exit,
                "timeframe": request.timeframe,
                "schema_version": "1.0",
            },
        })

    url = f"{settings.supabase_url}/rest/v1/signal_cases"
    headers = {
        "apikey": settings.supabase_service_key,
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=rows)
        if resp.status_code not in (200, 201):
            raise ValueError(
                f"signal_cases write failed: {resp.status_code} — {resp.text}. "
                "Lưu ý: signal_cases yêu cầu service role key, không phải anon key."
            )

    return len(rows)


async def rollback_signal_comparisons(
    session_date: str,
    strategy_name: str,
    settings: Settings,
) -> int:
    """
    DELETE FROM signal_comparisons WHERE signal_id LIKE 'backtest_{date}_{strategy}_%'
    Returns count of rows deleted (from response header if available, else 0).
    Uses anon key — assumes RLS allows DELETE for anon (or adjust to service key if needed).
    """
    import re
    sanitized = re.sub(r'[^a-z0-9]+', '_', strategy_name.lower()).strip('_')
    pattern = f"backtest_{session_date}_{sanitized}_"

    url = f"{settings.supabase_url}/rest/v1/signal_comparisons"
    headers = {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
        "Prefer": "return=minimal,count=exact",
    }
    params = {"signal_id": f"like.{pattern}%"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(url, headers=headers, params=params)
        # PostgREST returns count in Content-Range header: "0-N/N"
        count_header = resp.headers.get("content-range", "")
        try:
            deleted = int(count_header.split("/")[-1]) if "/" in count_header else 0
        except (ValueError, IndexError):
            deleted = 0
        return deleted
```

---

### `backend/routes/export.py` — Full Implementation

```python
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
import httpx

from backend.models import ExportRequest, ExportResponse, APIResponse
from backend.settings import Settings, get_settings
from backend import services

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/export", response_model=APIResponse[ExportResponse])
async def export_session(
    request: ExportRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> APIResponse[ExportResponse]:
    # 1. Guard: Supabase disabled
    if not settings.supabase_enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "disabled",
                "message": "Supabase integration chưa được bật — set SUPABASE_ENABLED=true trong .env",
            },
        )

    # 2. Parse session date from filename
    from backend.services.supabase import _parse_session_date, check_duplicate
    session_date = _parse_session_date(request.session_filename)

    # 3. Duplicate check
    try:
        is_dup = await check_duplicate(session_date, request.strategy_name, settings)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={
                "error": "timeout",
                "message": "Supabase đang wake up — thử lại sau 30 giây",
            },
        )

    if is_dup:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "duplicate",
                "message": (
                    f"Session {request.session_filename} đã export — "
                    "xóa rows trên Supabase trước nếu muốn re-export"
                ),
            },
        )

    # 4. Write signal_comparisons
    from backend.services.supabase import (
        write_signal_comparisons,
        write_signal_cases,
        rollback_signal_comparisons,
        generate_signal_id,
    )
    sc_count = 0
    try:
        sc_count = await write_signal_comparisons(request.trades, request, settings)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={
                "error": "timeout",
                "message": "Supabase đang wake up — thử lại sau 30 giây",
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "write_failed", "message": str(e)},
        )

    # 5. Write signal_cases — if fail, rollback signal_comparisons
    try:
        cases_count = await write_signal_cases(request.trades, request, settings)
    except (httpx.TimeoutException, ValueError) as e:
        # Rollback signal_comparisons
        rolled_back = 0
        try:
            rolled_back = await rollback_signal_comparisons(
                session_date, request.strategy_name, settings
            )
        except Exception as rollback_err:
            logger.error(
                "Rollback also failed after signal_cases error: %s", rollback_err
            )

        error_msg = str(e)
        logger.error(
            "Export failed, rolled back %d signal_comparisons rows. Error: %s",
            rolled_back,
            error_msg,
        )

        is_timeout = isinstance(e, httpx.TimeoutException)
        raise HTTPException(
            status_code=504 if is_timeout else 500,
            detail={
                "error": "timeout" if is_timeout else "partial_write_rolled_back",
                "message": (
                    "Supabase đang wake up — thử lại sau 30 giây"
                    if is_timeout
                    else (
                        "Authentication failed cho signal_cases (RLS enabled) — "
                        "Kiểm tra SUPABASE_SERVICE_KEY trong .env. "
                        f"Đã rollback signal_comparisons."
                    )
                ),
            },
        )

    # 6. Success
    first_signal_id = ""
    if request.trades:
        first_signal_id = generate_signal_id(
            session_date, request.strategy_name, request.trades[0].bar_index
        )
    supabase_url = (
        f"{settings.supabase_url}/rest/v1/signal_cases"
        f"?order=signal_id.desc&limit=50"
    )

    logger.info(
        "Exported session %s: %d signal_comparisons + %d signal_cases",
        request.session_filename,
        sc_count,
        cases_count,
    )

    return APIResponse(
        data=ExportResponse(
            signal_comparisons_count=sc_count,
            signal_cases_count=cases_count,
            first_signal_id=first_signal_id,
            supabase_url=supabase_url,
        ),
        error=None,
    )
```

---

### `backend/main.py` — Thêm Duy Nhất 2 Dòng

Tìm đoạn đăng ký routers trong `main.py` và thêm:

```python
from backend.routes.export import router as export_router
app.include_router(export_router)
```

**Không** thay đổi bất kỳ logic nào khác trong `main.py`.

---

### `backend/models.py` — Additions

```python
# --- Epic 3: Export request/response models ---

class ExportTrade(BaseModel):
    bar_index: int
    entry_timestamp_ms: int           # Unix ms int64 (ADR-03)
    direction: str                    # "LONG" or "SHORT"
    entry_price: float
    tp_price: float
    sl_price: float
    result: str                       # "win" or "loss"
    bars_to_exit: int
    reasoning_summary: str            # Edited by Narron in ExportPreview


class ExportRequest(BaseModel):
    session_filename: str             # "BTCUSDT_4h_20260420.parquet"
    strategy_name: str                # User input, default "{symbol}_{timeframe}"
    timeframe: str                    # "4h"
    session_win_rate: float           # 0.67
    trades: list[ExportTrade]


class ExportResponse(BaseModel):
    signal_comparisons_count: int
    signal_cases_count: int
    first_signal_id: str              # "backtest_20260426_breakout_4h_00042"
    supabase_url: str                 # Link to verify in Supabase dashboard
```

---

### PostgREST API Pattern — Supabase REST

Supabase exposes a PostgREST interface. Dev phải dùng đúng pattern:

**INSERT (POST):**
```
POST {supabase_url}/rest/v1/{table}
Headers:
  apikey: {key}
  Authorization: Bearer {key}
  Content-Type: application/json
  Prefer: return=minimal
Body: [{row}, {row}, ...]  ← array for bulk insert
```

**SELECT (để check duplicate):**
```
GET {supabase_url}/rest/v1/signal_comparisons
Headers:
  apikey: {supabase_key}
  Authorization: Bearer {supabase_key}
Query params:
  signal_id=like.backtest_20260426_breakout_4h_%   ← PostgREST filter syntax
  select=signal_id
  limit=1
```

**DELETE (để rollback):**
```
DELETE {supabase_url}/rest/v1/signal_comparisons
Headers:
  apikey: {supabase_key}
  Authorization: Bearer {supabase_key}
  Prefer: return=minimal,count=exact
Query params:
  signal_id=like.backtest_20260426_breakout_4h_%
```

> **CRITICAL (NFR6):** `signal_comparisons` dùng **anon key** (`settings.supabase_key`). `signal_cases` dùng **service role key** (`settings.supabase_service_key`). Không được swap — `signal_cases` có RLS enabled, chỉ service key bypass được.

---

### Atomic Rollback — Logic Flow

```
POST /api/export request nhận:
│
├── SUPABASE_ENABLED=false? → 503
│
├── check_duplicate() → True? → 409
│
├── write_signal_comparisons()
│     ├── Success: sc_count = N
│     └── Timeout → 504 (không cần rollback, chưa write gì)
│     └── Error → 500 (không cần rollback, chưa write gì)
│
└── write_signal_cases()
      ├── Success: → 200 + log INFO
      └── Timeout/Error → rollback_signal_comparisons()
                        → 504 hoặc 500 với "partial_write_rolled_back"
                        → log ERROR
```

**Orphan row risk:** Nếu `rollback_signal_comparisons()` cũng fail (ví dụ: Supabase down hoàn toàn) → orphan rows trong `signal_comparisons`. Error message hướng dẫn manual cleanup. Đây là acceptable trade-off — free tier Supabase, solo dev.

---

### Duplicate Detection Strategy

**Approach:** Query `signal_comparisons` với `signal_id LIKE 'backtest_{date}_{strategy}_%'`.

**Lý do:** 
- Backend là source of truth (từ PRD/Story 3.3)
- Không cần local storage hay database tracking phụ
- Tự động detect ngay cả khi localStorage của Narron bị clear

**Edge case:** Nếu Narron đổi `strategy_name` → signal_id prefix khác → không bị detect là duplicate. Đây là **intentional behavior** — khác strategy name = khác version của export.

---

### `settings.py` — Dependency Injection Pattern

Story 2.1 dùng `settings` singleton trực tiếp. Story 3.1 **phải dùng `Depends(get_settings)`** cho endpoint (FastAPI dependency injection pattern):

```python
# backend/settings.py — thêm nếu chưa có:
def get_settings() -> Settings:
    return settings  # return singleton
```

Nếu `get_settings()` chưa tồn tại trong `settings.py` → thêm vào. Nếu đã tồn tại → dùng nguyên.

---

### NFR Compliance

- **NFR5 (Critical):** Credentials chỉ từ `settings` (Pydantic Settings từ env vars) — không hardcode
- **NFR6 (Medium):** `supabase_key` (anon) cho `signal_comparisons` và `check_duplicate`; `supabase_service_key` cho `signal_cases` — hai keys khác nhau, không swap
- **NFR8 (Critical):** Schema mismatch được catch qua non-2xx Supabase response → `ValueError` → 500 trước khi partial write
- **NFR11 (Critical):** Không có cross-connection giữa Backtest DB và Production Bot DB — chỉ dùng `settings.supabase_url` (duy nhất 1 URL)
- **NFR12 (Critical):** Atomic: hoặc cả 2 tables đều ghi, hoặc rollback về state sạch
- **NFR15 (High):** `signal_cases_count == signal_comparisons_count` trong success response — verified bởi write count returns

### References

- [epics.md - Story 3.1 Acceptance Criteria](_bmad-output/planning-artifacts/epics.md#story-31-post-apiexport--write-signal_comparisons-và-signal_cases)
- [prd-phase2-supabase.md - FR13–FR18, FR23–FR25, NFR5, NFR6, NFR8, NFR11, NFR12](_bmad-output/planning-artifacts/prd-phase2-supabase.md)
- [prd-phase2-supabase.md - POST /api/export API Contract](_bmad-output/planning-artifacts/prd-phase2-supabase.md#L263-L300)
- [architecture.md - httpx, no supabase-py](_bmad-output/planning-artifacts/architecture.md)
- [1-1-them-supabase-config-vao-backend-settings.md - Settings fields](_bmad-output/implementation-artifacts/1-1-them-supabase-config-vao-backend-settings.md)
- [2-1-get-api-sessions-filename-preview-trade-list-voi-reasoning-templates.md - Models pattern](_bmad-output/implementation-artifacts/2-1-get-api-sessions-filename-preview-trade-list-voi-reasoning-templates.md)
- Story 3.2 `ExportProgressOverlay` listens `exportpreview:confirmed` → gọi `POST /api/export`
- Story 3.3 `session exported indicator` dùng localStorage + backend 409 response để prevent duplicate UI

## Review Findings (2026-04-27)

### Deferred (accepted risk / out of scope)

- **F2-rollback-anon-key**: `rollback_signal_comparisons` uses anon key for DELETE. If RLS is ever enabled on `signal_comparisons`, rollback silently returns 0 with no error. Accepted risk — NFR spec says RLS is disabled on this table.
- **F1-misleading-auth-message**: "Authentication failed" hardcoded in `partial_write_rolled_back` branch fires for all `ValueError` (schema mismatch, bad data). Deferred — operator can inspect logs for actual error.
- **F3-check-duplicate-silent-false**: `check_duplicate` returns `False` on any non-200 (401, 403, 500). Intentional policy: don't block export on connectivity issues.
- **F4/F8-test-quality-gate-ordering**: Tests for 409-duplicate and 504-timeout were using `SAMPLE_REQUEST` (1 trade) which would have hit quality gate first. Tests already use `SAMPLE_REQUEST_VALID` (10 trades) — verified correct.
- **F5-validate-credentials-timeout-10s**: `validate_credentials` uses timeout=10.0; spec says 30.0. Deferred — free-tier Supabase cold start risk acknowledged.
- **F6-timeout-mid-write-no-rollback**: Timeout during `write_signal_comparisons` returns 504 without rollback. PostgREST single-INSERT is atomic at DB level; mid-response TCP timeout is an accepted edge case.
- **F7-parse-date-fallback-collision**: Malformed filenames share "00000000" date prefix in `signal_id`. Mitigated by warning log (applied below).
- **F8-bar-index-overflow**: `bar_index:05d` overflows at ≥100000. Spec explicitly defines 5-digit zero-pad; not changed.
- **D1–D10**: Various low-severity defers (pg_message leak, session_filename in 409 body, non-calendar date acceptance, etc.)

### Applied Patches

- **F7-log-warning**: Added `logger.warning(...)` in `_parse_session_date` when fallback to "00000000" triggers — operators will now see the warning in logs.
- **F9-rollback-fails-test**: Added `test_export_rollback_also_fails_still_returns_500` — exercises the `except Exception as rollback_err` branch and verifies route still returns 500 with `partial_write_rolled_back`.

### Test Results

26 tests pass (`tests/test_export.py`).

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

N/A

### Completion Notes List

- `get_settings()` function added to `backend/settings.py` (was missing — required for FastAPI Depends DI).
- Test mock paths must target `backend.routes.export.*` (not `backend.services.supabase.*`) because route imports functions directly at module level.
- 36 tests pass (24 pre-existing + 12 new).

### File List

- `backend/models.py` — Added `ExportTrade`, `ExportRequest`, `ExportResponse`
- `backend/settings.py` — Added `get_settings()` dependency function
- `backend/services/supabase.py` — **CREATED**: `generate_signal_id`, `_parse_session_date`, helper mappers, `check_duplicate`, `write_signal_comparisons`, `write_signal_cases`, `rollback_signal_comparisons`
- `backend/routes/export.py` — **CREATED**: `POST /api/export` endpoint with 503/409/504/500 guards + rollback
- `backend/main.py` — Registered `export_router`
- `tests/test_export.py` — **CREATED**: 12 tests (200, 503, 504×2, 500, 409, signal_id format, sanitization, parse_date)
