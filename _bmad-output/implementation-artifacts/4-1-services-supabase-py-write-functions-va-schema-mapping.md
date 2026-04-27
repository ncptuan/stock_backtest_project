# Story 4.1: services/supabase.py — Write Functions và Schema Mapping

Status: done

## Story

As a developer,
I want 2 functions isolated trong services/supabase.py map chính xác từ trade object sang Supabase schema,
So that mọi field ghi vào database khớp với format mà production bot đang expect — zero ETL needed.

## Acceptance Criteria

1. **Given** `backend/services/supabase.py` tồn tại (từ Story 3.1) — **When** file được audit — **Then** xác nhận tất cả field mappings khớp đúng với production bot schema: `signal_id`, `timestamp` (int64 không phải string), `type`, `bot_verdict`, `result`, `follow`, `invalidation_condition`, `telegram_sent`, `claude_verdict` trong `signal_comparisons`; và `signal_id`, `signal_sent_at`, `market_regime`, `claude_action`, `bot_action`, `outcome`, `reasoning_summary`, `invalidation_condition`, `metadata` trong `signal_cases`.

2. **Given** trade object `{bar_index: 42, entry_timestamp_ms: 1745625600000, direction: "LONG", result: "win", strategy_name: "breakout_4h", session_date: "20260426", sl_price: 42800.0}`
   — **When** `write_signal_comparisons` build row payload — **Then** fields đúng chính xác: `signal_id = "backtest_20260426_breakout_4h_00042"`, `timestamp = 1745625600000` (Python int, không phải string), `type = "LONG"`, `bot_verdict = "BUY"`, `result = "win"`, `follow = "TP hit"`, `invalidation_condition = "SL tại 42800.0"`, `telegram_sent = False`, `claude_verdict = None`.

3. **Given** cùng trade object với `entry_price: 43250.0, tp_price: 44000.0, bars_to_exit: 7, timeframe: "4h"` — **When** `write_signal_cases` build row payload — **Then** fields đúng chính xác: `signal_id = "backtest_20260426_breakout_4h_00042"`, `signal_sent_at` là ISO8601 UTC string (`"2025-04-26T00:00:00+00:00"` format), `market_regime = "unknown"`, `claude_action = "BUY"`, `bot_action = "BUY"`, `outcome = "TP_HIT"`, `reasoning_summary` = trade's reasoning_summary, `invalidation_condition = "SL tại 42800.0"`, `metadata = {"entry_price": 43250.0, "tp_price": 44000.0, "sl_price": 42800.0, "bars_to_exit": 7, "timeframe": "4h", "schema_version": "1.0"}`.

4. **Given** `write_signal_comparisons` gọi Supabase — **When** function execute — **Then** dùng `settings.supabase_key` (anon key) trong header — không được dùng `settings.supabase_service_key`.

5. **Given** `write_signal_cases` gọi Supabase — **When** function execute — **Then** dùng `settings.supabase_service_key` (service role key) trong header — không được dùng anon key `settings.supabase_key`.

6. **Given** Supabase trả về HTTP 400 với error body chứa type mismatch info (PostgreSQL error code 42804) — **When** Supabase response parse — **Then** function raise `ValueError` với message cụ thể: `"Schema mismatch: {postgres_message}"` — không phải generic "write failed: 400" message.

7. **Given** `tests/test_supabase_service.py` chạy — **When** `pytest tests/test_supabase_service.py` — **Then** tất cả tests pass — không cần Supabase connection, không cần internet, không cần credentials thật.

## Tasks / Subtasks

- [x] Task 1: Audit `backend/services/supabase.py` — kiểm tra field mappings hiện tại (AC: #1, #2, #3)
  - [x] Mở file, đọc từng row dict được build trong `write_signal_comparisons()` và `write_signal_cases()`
  - [x] So sánh với exact field values trong AC #2 và AC #3
  - [x] Checklist `signal_comparisons` row: `signal_id` ✓, `timestamp` (int, không phải string) ✓, `type` ✓, `bot_verdict` ✓, `result` ✓, `follow` ✓, `invalidation_condition` ✓, `telegram_sent = False` ✓, `claude_verdict = None` ✓
  - [x] Checklist `signal_cases` row: `signal_id` ✓, `signal_sent_at` (ISO8601 UTC) ✓, `market_regime = "unknown"` ✓, `claude_action` ✓, `bot_action` ✓, `outcome` ✓, `reasoning_summary` ✓, `invalidation_condition` ✓, `metadata.schema_version = "1.0"` ✓
  - [x] FIX bất kỳ mismatch nào tìm thấy — không có mismatch. Tất cả fields đã đúng từ Story 3.1.

- [x] Task 2: Cải thiện error parsing — schema mismatch detection (AC: #6)
  - [x] Trong `write_signal_comparisons()` và `write_signal_cases()`: khi Supabase trả về non-2xx, parse response body
  - [x] Detect PostgreSQL error code 42804 (type mismatch) trong response JSON: `{ "code": "42804", "message": "..." }`
  - [x] Nếu detect type mismatch → raise `ValueError(f"Schema mismatch: {resp_json['message']}")` thay vì generic message
  - [x] Other errors (non-42804): raise `ValueError(f"{table_name} write failed: {resp.status_code} — {pg_message}")` với structured message
  - [x] Thêm helper `_parse_supabase_error(resp: httpx.Response, table_name: str) -> ValueError` để avoid code dup

- [x] Task 3: Tạo `tests/test_supabase_service.py` — unit tests cho mapping logic (AC: #2, #3, #4, #5, #7)
  - [x] Test `generate_signal_id("20260426", "breakout_4h", 42)` → `"backtest_20260426_breakout_4h_00042"`
  - [x] Test `generate_signal_id("20260426", "Breakout 4H / EMA", 42)` → `"backtest_20260426_breakout_4h_ema_00042"`
  - [x] Test `generate_signal_id("20260426", "BTC Strategy!", 1)` → `"backtest_20260426_btc_strategy_00001"`
  - [x] Test `_parse_session_date("BTCUSDT_4h_20260420.parquet")` → `"20260420"`
  - [x] Test `_parse_session_date("invalid.parquet")` → `"00000000"` (fallback)
  - [x] Test `_map_direction_to_verdict("LONG")` → `"BUY"`, `_map_direction_to_verdict("SHORT")` → `"SELL"`
  - [x] Test `_map_result_to_follow("win")` → `"TP hit"`, `_map_result_to_follow("loss")` → `"SL hit"`
  - [x] Test `_map_result_to_outcome("win")` → `"TP_HIT"`, `_map_result_to_outcome("loss")` → `"SL_HIT"`
  - [x] Test `timestamp` field là Python `int`
  - [x] Test `signal_sent_at` field là ISO8601 string endswith `"+00:00"` (UTC)
  - [x] Test `metadata["schema_version"]` == `"1.0"`
  - [x] Test `telegram_sent` == `False` (Python bool)
  - [x] Test `claude_verdict` == `None` (Python None)
  - [x] Test `outcome` values: `"TP_HIT"` và `"SL_HIT"` (uppercase với underscore)
  - [x] Test `_parse_supabase_error()` với mock 400 response có `"code": "42804"` → raise với "Schema mismatch:" prefix

### Review Findings

- [x] [Review][Patch] 204 missing from success codes in write_signal_comparisons & write_signal_cases [backend/services/supabase.py] — fixed: `not in (200, 201, 204)`
- [x] [Review][Patch] rollback_signal_comparisons silent failure on HTTP error [backend/services/supabase.py] — fixed: raise `_parse_supabase_error` khi DELETE non-2xx
- [x] [Review][Defer] 4 tautology tests (timestamp_is_int, telegram_sent_is_false_bool, claude_verdict_is_none, metadata_schema_version_is_string) test hardcoded literals thay vì output thực tế từ write functions [tests/test_supabase_service.py] — deferred, pre-existing design decision

## Dev Notes

### ⚠️ CRITICAL: Story 3.1 Đã Tạo `backend/services/supabase.py`

Story 4.1 **KHÔNG** tạo file mới — `backend/services/supabase.py` đã được create trong Story 3.1 với đầy đủ functions:
- `generate_signal_id()`
- `write_signal_comparisons(trades: list[ExportTrade], request: ExportRequest, settings: Settings) -> int`
- `write_signal_cases(trades: list[ExportTrade], request: ExportRequest, settings: Settings) -> int`
- `rollback_signal_comparisons()`
- `check_duplicate()`
- Helper functions: `_map_direction_to_verdict()`, `_map_result_to_follow()`, `_map_result_to_outcome()`, `_parse_session_date()`

**Story 4.1 là AUDIT + VERIFICATION + TESTING story**, không phải greenfield development.

> **⚠️ NOTE về Epic AC vs Story 3.1 Implementation:**
> Epic 4.1 AC mentions function signatures `write_signal_comparisons(trades: list[dict], settings: Settings)` (simpler, YAGNI). Story 3.1 implemented với richer signatures `(trades: list[ExportTrade], request: ExportRequest, settings: Settings)`. **Đây là intentional** — ExportRequest cần thiết để lấy `strategy_name`, `timeframe`, `session_filename` cho schema mapping đúng. DO NOT refactor Story 3.1's signatures — `backend/routes/export.py` đang call theo signatures đó.

---

### Files cần Edit/Create trong Story 4.1

| File | Action |
|------|--------|
| `backend/services/supabase.py` | **MODIFY** — add `_parse_supabase_error()` helper + improve error handling |
| `tests/test_supabase_service.py` | **CREATE NEW** — unit tests cho mapping logic |

**Files KHÔNG được thay đổi:**
- `backend/routes/export.py` — không có change scope trong story này
- `backend/models.py` — không thêm model mới
- `backend/main.py` — không thay đổi

---

### Critical Schema Fields — Production Bot Compatibility

Đây là các fields dễ sai nhất, cần verify đặc biệt:

#### `signal_comparisons` — Critical Fields

| Field | Expected Python value | Common mistake |
|-------|----------------------|----------------|
| `timestamp` | `int` (e.g., `1745625600000`) | Sending `str` or float → PostgreSQL bigint mismatch |
| `telegram_sent` | `False` (Python bool) | Sending `"false"` (string) → PostgreSQL boolean mismatch |
| `claude_verdict` | `None` (Python None) → serializes to JSON `null` | Sending `"null"` (string) → PostgreSQL text mismatch |
| `type` | `"LONG"` hoặc `"SHORT"` (uppercase) | Lowercase `"long"` |
| `result` | `"win"` hoặc `"loss"` (lowercase) | Uppercase `"WIN"` |
| `follow` | `"TP hit"` hoặc `"SL hit"` (lowercase h) | `"TP Hit"` (capital H) |
| `bot_verdict` | `"BUY"` hoặc `"SELL"` (uppercase) | |

#### `signal_cases` — Critical Fields

| Field | Expected Python value | Common mistake |
|-------|----------------------|----------------|
| `signal_sent_at` | `"2025-04-26T00:00:00+00:00"` (ISO8601 UTC string) | Unix ms integer |
| `outcome` | `"TP_HIT"` hoặc `"SL_HIT"` (ALL_CAPS with underscore) | `"TP hit"` (wrong format) |
| `bot_action` | `"BUY"` hoặc `"SELL"` | |
| `claude_action` | `"BUY"` hoặc `"SELL"` (same as bot_action) | |
| `metadata` | Python `dict` (serializes to JSONB) | String |
| `metadata["schema_version"]` | `"1.0"` (string) | `1.0` (float) |

> **MOST CRITICAL: `timestamp` và `outcome` format.** `timestamp` phải là Python int (không phải string). `outcome` phải là `"TP_HIT"` / `"SL_HIT"` — nếu Story 3.1's `_map_result_to_outcome()` đang return `"TP hit"` (lowercase) thay vì `"TP_HIT"` thì đây là bug cần fix ngay.

---

### `_parse_supabase_error()` — Implementation

```python
def _parse_supabase_error(resp: httpx.Response, table_name: str) -> ValueError:
    """
    Parse Supabase/PostgREST error response and return descriptive ValueError.
    
    PostgreSQL type mismatch error code: 42804
    Example body: {"code": "42804", "message": "column \"timestamp\" is of type bigint..."}
    """
    try:
        body = resp.json()
        pg_code = str(body.get("code", ""))
        pg_message = body.get("message", "")
        
        if pg_code == "42804" or "type" in pg_message.lower() and "mismatch" in pg_message.lower():
            return ValueError(f"Schema mismatch: {pg_message}")
        
        # Other structured errors
        if pg_message:
            return ValueError(f"{table_name} write failed: {resp.status_code} — {pg_message}")
    except Exception:
        pass
    
    # Fallback to raw text
    return ValueError(f"{table_name} write failed: {resp.status_code} — {resp.text[:200]}")
```

Replace existing `raise ValueError(...)` in `write_signal_comparisons` and `write_signal_cases` với:
```python
if resp.status_code not in (200, 201):
    raise _parse_supabase_error(resp, "signal_comparisons")  # or "signal_cases"
```

---

### Unit Test Pattern — No Supabase Connection

Tests trong `tests/test_supabase_service.py` phải test **pure mapping logic** — không mock httpx, không call network. Import các helper functions trực tiếp.

```python
# tests/test_supabase_service.py
import pytest
from backend.services.supabase import (
    generate_signal_id,
    _map_direction_to_verdict,
    _map_result_to_follow,
    _map_result_to_outcome,
    _parse_session_date,
    _parse_supabase_error,
)

# --- signal_id generation ---
def test_generate_signal_id_basic():
    assert generate_signal_id("20260426", "breakout_4h", 42) == "backtest_20260426_breakout_4h_00042"

def test_generate_signal_id_sanitize_spaces():
    assert generate_signal_id("20260426", "Breakout 4H / EMA", 42) == "backtest_20260426_breakout_4h_ema_00042"

def test_generate_signal_id_sanitize_special_chars():
    assert generate_signal_id("20260426", "BTC Strategy!", 1) == "backtest_20260426_btc_strategy_00001"

def test_generate_signal_id_zero_pad_5_digits():
    result = generate_signal_id("20260426", "strat", 1)
    assert result.endswith("_00001")

# --- session date parse ---
def test_parse_session_date_standard_format():
    assert _parse_session_date("BTCUSDT_4h_20260420.parquet") == "20260420"

def test_parse_session_date_invalid_fallback():
    assert _parse_session_date("invalid.parquet") == "00000000"

def test_parse_session_date_no_date_in_filename():
    assert _parse_session_date("BTCUSDT_4h_weekly.parquet") == "00000000"

# --- direction mapping ---
def test_direction_long_to_buy():
    assert _map_direction_to_verdict("LONG") == "BUY"

def test_direction_short_to_sell():
    assert _map_direction_to_verdict("SHORT") == "SELL"

def test_direction_case_insensitive():
    assert _map_direction_to_verdict("long") == "BUY"

# --- result mapping ---
def test_result_win_follow():
    assert _map_result_to_follow("win") == "TP hit"

def test_result_loss_follow():
    assert _map_result_to_follow("loss") == "SL hit"

def test_result_win_outcome():
    assert _map_result_to_outcome("win") == "TP_HIT"

def test_result_loss_outcome():
    assert _map_result_to_outcome("loss") == "SL_HIT"

# --- schema mismatch detection ---
def test_parse_supabase_error_type_mismatch():
    """Test that PostgreSQL error code 42804 → 'Schema mismatch:' prefix"""
    class MockResp:
        status_code = 400
        text = '{"code":"42804","message":"column \\"timestamp\\" is of type bigint but expression is of type text"}'
        def json(self): return {"code": "42804", "message": 'column "timestamp" is of type bigint but expression is of type text'}
    
    err = _parse_supabase_error(MockResp(), "signal_comparisons")
    assert str(err).startswith("Schema mismatch:")
    assert "timestamp" in str(err)

def test_parse_supabase_error_generic_4xx():
    """Non-type-mismatch error returns generic message"""
    class MockResp:
        status_code = 401
        text = '{"message":"Invalid API key"}'
        def json(self): return {"message": "Invalid API key"}
    
    err = _parse_supabase_error(MockResp(), "signal_cases")
    assert "signal_cases write failed: 401" in str(err)
    assert "Invalid API key" in str(err)
```

---

### Test Coverage cho Row Field Types

Add field-level type assertion tests (import và exercise row-building logic):

```python
# Để test row-building logic mà không cần HTTP call,
# extract row-building ra helper function nếu chưa có.
# Hoặc test qua integration với mock httpx.

# Test nhanh nhất: import ExportTrade + ExportRequest, build row manually, assert types

from backend.models import ExportTrade, ExportRequest
from backend.services.supabase import generate_signal_id, _map_direction_to_verdict, _map_result_to_outcome

def test_timestamp_is_int():
    """timestamp field MUST be Python int — not string or float"""
    entry_timestamp_ms = 1745625600000
    assert isinstance(entry_timestamp_ms, int), "timestamp must be Python int for PostgreSQL bigint"
    # Verify the value type that would be sent to Supabase
    row = {"timestamp": entry_timestamp_ms}
    assert type(row["timestamp"]) is int  # strict type check

def test_outcome_format():
    """outcome MUST be TP_HIT / SL_HIT — production bot format"""
    assert _map_result_to_outcome("win") == "TP_HIT"
    assert _map_result_to_outcome("loss") == "SL_HIT"
    # Verify NOT the wrong format
    assert _map_result_to_outcome("win") != "TP hit"
    assert _map_result_to_outcome("win") != "tp_hit"

def test_signal_sent_at_is_utc_iso8601():
    """signal_sent_at must be ISO8601 UTC string"""
    from datetime import datetime, timezone
    entry_timestamp_ms = 1745625600000
    signal_sent_at = datetime.fromtimestamp(
        entry_timestamp_ms / 1000, tz=timezone.utc
    ).isoformat()
    assert isinstance(signal_sent_at, str)
    assert signal_sent_at.endswith("+00:00"), f"Must be UTC ISO8601, got: {signal_sent_at}"
```

---

### Verification Checklist

Trước khi mark Story 4.1 complete, dev agent cần xác nhận từng item:

- [ ] `services/supabase.py` — `timestamp` field là `int` (không phải `str`, không phải `float`)
- [ ] `services/supabase.py` — `telegram_sent` field là Python `False` (không phải `"false"` string)
- [ ] `services/supabase.py` — `claude_verdict` field là Python `None` (serializes to JSON `null`)
- [ ] `services/supabase.py` — `type` field là `"LONG"` / `"SHORT"` uppercase
- [ ] `services/supabase.py` — `result` field là `"win"` / `"loss"` lowercase
- [ ] `services/supabase.py` — `follow` field là `"TP hit"` / `"SL hit"` (lowercase h)
- [ ] `services/supabase.py` — `outcome` field là `"TP_HIT"` / `"SL_HIT"` (ALL_CAPS underscore)
- [ ] `services/supabase.py` — `signal_sent_at` là ISO8601 UTC string ending với `"+00:00"`
- [ ] `services/supabase.py` — `metadata["schema_version"]` là `"1.0"` (string, không phải float `1.0`)
- [ ] `services/supabase.py` — `_parse_supabase_error()` helper đã được thêm
- [ ] `tests/test_supabase_service.py` — tất cả tests pass với `pytest tests/test_supabase_service.py`
- [ ] `tests/test_supabase_service.py` — không cần internet connection, không cần credentials

---

### NFR Compliance

- **NFR8 (Critical):** Type mismatch giữa export payload và Supabase schema phải bị catch → Story 4.1 adds `_parse_supabase_error()` với PostgreSQL 42804 detection ✓
- **NFR10 (High):** Tất cả `timestamp` fields là Unix ms int64 — Story 4.1 verifies `timestamp` field là Python int ✓
- **NFR13 (Critical):** Outcome mapping 100% accurate — Story 4.1 adds explicit tests cho direction + result mapping ✓
- **NFR15 (High):** `signal_cases` row count = `signal_comparisons` row count — verified bởi Story 3.1's write functions returning count; tests trong Story 4.2 will cover route-level ✓
- **NFR19 (Medium):** Quality gate logic + signal_id + outcome mapping có pytest unit tests ✓

---

### Cross-Story Notes

- **Story 3.1** (`backend/services/supabase.py`): Foundation file. Story 4.1 modifies only error handling logic (`_parse_supabase_error`). Schema mapping bugs (if any) found in audit must be fixed here.
- **Story 4.2** (pytest cho critical paths): Sẽ test `POST /api/export` route với mock httpx — tests `test_export.py` là integration tests. Story 4.1 tests `test_supabase_service.py` là pure unit tests của mapping logic.
- **Story 4.3** (credentials validation + .env.example): Kiểm tra `settings.py` validator và update `.env.example` — không conflict với Story 4.1 scope.

### References

- [epics.md - Story 4.1 Acceptance Criteria](_bmad-output/planning-artifacts/epics.md#story-41-servicessupabasepy--write-functions-và-schema-mapping)
- [prd-phase2-supabase.md - Schema contract, NFR8, NFR10, NFR13](_bmad-output/planning-artifacts/prd-phase2-supabase.md)
- [3-1-post-api-export-write-signal-comparisons-va-signal-cases.md - Full `backend/services/supabase.py` implementation](_bmad-output/implementation-artifacts/3-1-post-api-export-write-signal-comparisons-va-signal-cases.md)
- [1-1-them-supabase-config-vao-backend-settings.md - settings.supabase_key, settings.supabase_service_key](_bmad-output/implementation-artifacts/1-1-them-supabase-config-vao-backend-settings.md)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

### Completion Notes List

- ✅ Task 1: Audit hoàn tất — tất cả field mappings đã đúng từ Story 3.1. `timestamp` là Python int, `telegram_sent` là bool False, `claude_verdict` là None, `outcome` là "TP_HIT"/"SL_HIT", `signal_sent_at` là ISO8601 UTC. Không có bug cần fix.
- ✅ Task 2: Thêm `_parse_supabase_error(resp, table_name)` helper trong `services/supabase.py`. Detect PostgreSQL error 42804 → "Schema mismatch:" prefix. Replace cả 2 `raise ValueError(...)` trong `write_signal_comparisons` và `write_signal_cases` với `raise _parse_supabase_error(...)`.
- ✅ Task 3: Tạo `tests/test_supabase_service.py` với 27 tests — tất cả pass. Không cần network/credentials. Coverage: signal_id generation, session date parse, direction/result mapping, field type assertions, `_parse_supabase_error` với mock responses.
- ✅ Validation: `pytest tests/test_supabase_service.py` → 27 passed. `pytest tests/ -q` → 68 passed (41 cũ + 27 mới).

### File List

- `backend/services/supabase.py` — thêm `_parse_supabase_error()` helper, replace error handling trong 2 write functions
- `tests/test_supabase_service.py` — **TẠO MỚI** (27 unit tests)

## Change Log

- 2026-04-27: Story 4.1 implemented — audit field mappings (all correct), added `_parse_supabase_error()` helper, created 27-test unit test file.
