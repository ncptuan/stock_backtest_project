# Story P1-1.5: Data gap detection + clip notification

Status: done

## Story

As a trader,
I want to know when my cached OHLCV data has missing candles or doesn't cover my requested date range,
So that I can fetch more complete data before running a replay session and avoid drawing conclusions from incomplete data.

## Acceptance Criteria

1. **Given** cache có đủ data trong requested date range nhưng có khoảng hở giữa các candles
   **When** frontend gọi `GET /api/ohlcv` với date range đó
   **Then** response bao gồm `has_gaps: true` và `gaps: [{start_ts, end_ts, missing_bars}]` — list các khoảng hở được detect
   **And** mỗi gap là một dict với: `start_ts` (int64 ms, timestamp của bar TRƯỚC gap), `end_ts` (int64 ms, timestamp của bar SAU gap), `missing_bars` (int, số bars còn thiếu trong khoảng đó)
   **And** gap được detect khi `next_timestamp - current_timestamp > expected_interval_ms * 1.5` (threshold 1.5x để tránh false positive do timezone offsets nhỏ)
   **And** bars OHLCV vẫn được trả về đầy đủ — gap detection không filter hay modify data

2. **Given** cache có data liên tục trong requested date range (không có gap)
   **When** frontend gọi `GET /api/ohlcv`
   **Then** response có `has_gaps: false` và `gaps: []` (empty list, không phải null)

3. **Given** requested date range extend NGOÀI phạm vi data có trong cache
   **When** frontend gọi `GET /api/ohlcv` với `date_start` sớm hơn earliest bar hoặc `date_end` muộn hơn latest bar
   **Then** response bao gồm `clipped: true`, `actual_date_start` (nếu start bị clip), `actual_date_end` (nếu end bị clip)
   **And** hành vi này **đã được implement trong Story 1.1** — story này thêm test coverage, không viết lại logic
   **And** response có thể có cả `clipped: true` VÀ `has_gaps: true` đồng thời (cả hai điều kiện độc lập)

4. **Given** cache rỗng hoặc không tồn tại cho (symbol, timeframe) đó
   **When** frontend gọi `GET /api/ohlcv`
   **Then** response trả về 404 với `{code: "no_cache"}` — không crash, không `has_gaps`
   **And** hành vi 404 này **đã có từ Story 1.1** — không cần thay đổi

5. **Given** timeframe là "1h" (interval = 3,600,000 ms)
   **When** detect gaps với threshold 1.5x
   **Then** gap thực sự (thiếu 1+ bars): `next_ts - curr_ts > 5,400,000 ms` → detected
   **And** daylight saving time offset (chênh ±1h): `next_ts - curr_ts = 3,600,000 ms` → NOT a gap (bình thường)
   **And** weekend gap cho "1D" timeframe (Sat→Mon = 3 ngày): `next_ts - curr_ts = 172,800,000 ms` → detected (expected cho crypto 24/7 — mọi day gap là gap thực)

6. **Given** sliced DataFrame (sau khi filter by date range) có gaps
   **When** gap detection chạy
   **Then** gap detection chạy TRÊN sliced data (không phải full cache) — chỉ report gaps trong khoảng user đang dùng
   **And** performance: gap detection O(n) — một pass qua timestamps là đủ, không nested loop

## Tasks / Subtasks

- [x] Task 1: Thêm `detect_gaps(df, timeframe) -> list[dict]` vào `backend/services/cache.py` (AC: #1, #2, #5, #6)
  - [x] Thêm `_INTERVAL_MS: dict[str, int]` (5m→300000, 30m→1800000, 1h→3600000, 4h→14400000, 1D→86400000) — nếu chưa có
  - [x] Hàm nhận: `df: pd.DataFrame` (đã sorted ascending), `timeframe: str`
  - [x] Tính `interval_ms = _INTERVAL_MS[timeframe]` và `threshold = interval_ms * 1.5`
  - [x] Loop qua `df["timestamp"].values` với `zip(timestamps[:-1], timestamps[1:])`:
    - Nếu `next_ts - curr_ts > threshold`: thêm `{"start_ts": int(curr_ts), "end_ts": int(next_ts), "missing_bars": int((next_ts - curr_ts) // interval_ms) - 1}` vào gaps list
  - [x] Trả về `list[dict]` (empty list nếu không có gap)
  - [x] `df` phải có ít nhất 2 rows để check gaps — nếu `len(df) < 2`: trả về `[]`

- [x] Task 2: Cập nhật `OHLCVResponse` trong `backend/models.py` — thêm gap fields (AC: #1, #2)
  - [x] Thêm `has_gaps: bool = False`
  - [x] Thêm `gaps: list[dict] = []` — mỗi item là `{"start_ts": int, "end_ts": int, "missing_bars": int}`
  - [x] Giữ nguyên `clipped`, `actual_date_start`, `actual_date_end` — không xóa, không rename

- [x] Task 3: Gọi `detect_gaps` trong `backend/routes/ohlcv.py` và include kết quả vào response (AC: #1, #2, #3, #6)
  - [x] Import `detect_gaps` từ `backend.services.cache`
  - [x] Sau khi có `sliced` DataFrame và trước khi build `bars` list: `gaps = detect_gaps(sliced, timeframe)`
  - [x] Cập nhật `OHLCVResponse(...)` để set `has_gaps=len(gaps) > 0` và `gaps=gaps`
  - [x] Đảm bảo `gaps` luôn là list (không phải None)

- [x] Task 4: Viết `tests/test_ohlcv_gap_detection.py` (AC: #1–#6)
  - [x] Test `detect_gaps` với data liên tục 1h → trả về `[]`
  - [x] Test `detect_gaps` với 1 gap ở giữa (thiếu 2 bars 1h) → trả về 1 gap entry đúng
  - [x] Test `detect_gaps` với nhiều gaps → trả về list đủ entries
  - [x] Test `detect_gaps` với df < 2 rows → trả về `[]`
  - [x] Test `detect_gaps` threshold boundary: diff = interval * 1.4 → NOT gap; diff = interval * 1.6 → gap
  - [x] Test `GET /api/ohlcv` integration — mock cache với gap → response có `has_gaps=true`, `gaps` list đúng
  - [x] Test `GET /api/ohlcv` integration — mock cache liên tục → response có `has_gaps=false`, `gaps=[]`
  - [x] Test `GET /api/ohlcv` clip + gap đồng thời: cache có clip VÀ gap → cả hai field đều đúng
  - [x] Test FR6 regression: clip detection vẫn đúng sau khi thêm gap logic

## Dev Notes

### Context brownfield quan trọng

**`backend/models.py` — `OHLCVResponse` HIỆN TẠI:**
```python
class OHLCVResponse(BaseModel):
    data: list[OHLCVBar]
    clipped: bool = False
    actual_date_start: str | None = None
    actual_date_end: str | None = None
```
→ **Task 2 thêm** `has_gaps` và `gaps` vào class này. Các field clip giữ nguyên.

**`backend/routes/ohlcv.py` — phần cuối của hàm `get_ohlcv` HIỆN TẠI:**
```python
response = OHLCVResponse(
    data=bars,
    clipped=clipped,
    actual_date_start=_ms_to_date(actual_start_ms) if start_clipped else None,
    actual_date_end=_ms_to_date(actual_end_ms) if end_clipped else None,
)
return response
```
→ **Task 3 cập nhật** đoạn này: gọi `detect_gaps(sliced, timeframe)` trước, rồi thêm `has_gaps` và `gaps` vào `OHLCVResponse(...)`.

**`backend/services/cache.py` — HIỆN TẠI:**
- `CacheCorruptError`, `CacheSchemaError` classes ✓
- `_SYMBOL_RE` regex ✓
- `_cache_path()` ✓
- `read_ohlcv()` — validate schema, dedup, sort ✓
- `write_ohlcv()` — plain write hiện tại (Story 1.3 sẽ upgrade)
- **KHÔNG CÓ** `detect_gaps()` → **Task 1 thêm vào**
- **KHÔNG CÓ** `_INTERVAL_MS` dict → **Task 1 thêm vào** (nếu binance.py chưa export)

**Note về `_INTERVAL_MS`:** Story 1.4 sẽ thêm `_INTERVAL_MS` vào `binance.py`. Trong story này, `detect_gaps` trong `cache.py` cần interval map riêng. Không import từ `binance.py` — ADR-09 (separation of concerns): cache.py không phụ thuộc binance.py. Define riêng trong `cache.py`.

### Gap detection algorithm

```python
# backend/services/cache.py

_INTERVAL_MS: dict[str, int] = {
    "5m": 5 * 60 * 1000,       # 300_000
    "30m": 30 * 60 * 1000,     # 1_800_000
    "1h": 60 * 60 * 1000,      # 3_600_000
    "4h": 4 * 60 * 60 * 1000,  # 14_400_000
    "1D": 24 * 60 * 60 * 1000, # 86_400_000
}

def detect_gaps(df: pd.DataFrame, timeframe: str) -> list[dict]:
    """
    Detect timestamp gaps trong OHLCV DataFrame.
    
    Args:
        df: DataFrame đã sorted ascending theo timestamp
        timeframe: timeframe string (e.g., "1h", "4h")
    
    Returns:
        List of gap dicts: [{"start_ts": int, "end_ts": int, "missing_bars": int}]
        Empty list nếu không có gap hoặc df < 2 rows.
    """
    if len(df) < 2:
        return []
    
    interval_ms = _INTERVAL_MS.get(timeframe)
    if interval_ms is None:
        return []  # unknown timeframe — fail safe, no gaps reported
    
    threshold = interval_ms * 1.5
    timestamps = df["timestamp"].values  # numpy array, efficient
    gaps: list[dict] = []
    
    for curr_ts, next_ts in zip(timestamps[:-1], timestamps[1:]):
        diff = int(next_ts) - int(curr_ts)
        if diff > threshold:
            missing = int(diff // interval_ms) - 1
            gaps.append({
                "start_ts": int(curr_ts),
                "end_ts": int(next_ts),
                "missing_bars": missing,
            })
    
    return gaps
```

**Tại sao threshold 1.5x:**
- 1x threshold: false positive nếu timestamps có rounding errors nhỏ
- 1.5x threshold: an toàn cho clock jitter, nhưng bắt được gap 1 bar thực sự
- Ví dụ "1h": interval=3600000, threshold=5400000 → `next_ts - curr_ts = 7200000` (2h diff) → 1 bar missing được detect

**Weekend gap cho "1D":**
- BTCUSDT trên Binance là 24/7 — không có weekend gap
- Nếu có gap: thực sự là data missing (holiday, API downtime)
- Threshold 1.5x = 129600000ms (1.5 ngày) → bắt được gap > 1.5 ngày

### Cập nhật GET /api/ohlcv

```python
# backend/routes/ohlcv.py — đoạn cuối hàm get_ohlcv

# ... (code hiện tại: build bars list)
bars: list[OHLCVBar] = [...]

# Task 3: Detect gaps sau khi slice
from backend.services.cache import detect_gaps  # thêm vào import ở đầu file
gaps = detect_gaps(sliced, timeframe)

response = OHLCVResponse(
    data=bars,
    clipped=clipped,
    actual_date_start=_ms_to_date(actual_start_ms) if start_clipped else None,
    actual_date_end=_ms_to_date(actual_end_ms) if end_clipped else None,
    has_gaps=len(gaps) > 0,
    gaps=gaps,
)
return response
```

**Import thêm:** Add `detect_gaps` vào import line hiện tại:
```python
# Từ:
from backend.services.cache import CacheCorruptError, CacheSchemaError, read_ohlcv
# Thành:
from backend.services.cache import CacheCorruptError, CacheSchemaError, detect_gaps, read_ohlcv
```

### Test patterns

```python
# tests/test_ohlcv_gap_detection.py
import pandas as pd
import pytest

from backend.services.cache import detect_gaps

BASE_TS = 1_704_067_200_000  # 2024-01-01 00:00:00 UTC ms
HOUR_MS = 3_600_000


def _continuous_df(n: int = 10) -> pd.DataFrame:
    """n bars liên tục 1h."""
    return pd.DataFrame({
        "timestamp": [BASE_TS + i * HOUR_MS for i in range(n)],
        "open": [100.0] * n, "high": [101.0] * n,
        "low": [99.0] * n, "close": [100.5] * n, "volume": [10.0] * n,
    })


def _df_with_gap(gap_after_bar: int, skip_bars: int = 2, n: int = 10) -> pd.DataFrame:
    """n bars, gap ở sau bar index gap_after_bar (skip_bars bars bị thiếu)."""
    timestamps = []
    for i in range(n):
        if i <= gap_after_bar:
            timestamps.append(BASE_TS + i * HOUR_MS)
        else:
            timestamps.append(BASE_TS + (i + skip_bars) * HOUR_MS)
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": [100.0] * n, "high": [101.0] * n,
        "low": [99.0] * n, "close": [100.5] * n, "volume": [10.0] * n,
    })


def test_no_gap_returns_empty(tmp_path):
    df = _continuous_df(10)
    result = detect_gaps(df, "1h")
    assert result == []


def test_single_gap_detected():
    df = _df_with_gap(gap_after_bar=4, skip_bars=2)
    gaps = detect_gaps(df, "1h")
    assert len(gaps) == 1
    assert gaps[0]["missing_bars"] == 2
    assert gaps[0]["start_ts"] == BASE_TS + 4 * HOUR_MS
    assert gaps[0]["end_ts"] == BASE_TS + 7 * HOUR_MS  # 4 + 2 skip + 1 next


def test_multiple_gaps_detected():
    df = _df_with_gap(gap_after_bar=2, skip_bars=3, n=15)
    # Add second gap
    ts = list(df["timestamp"])
    ts[8:] = [t + 2 * HOUR_MS for t in ts[8:]]
    df["timestamp"] = ts
    gaps = detect_gaps(df, "1h")
    assert len(gaps) == 2


def test_df_less_than_2_rows():
    df = _continuous_df(1)
    assert detect_gaps(df, "1h") == []
    df_empty = _continuous_df(0)
    assert detect_gaps(df_empty, "1h") == []


def test_threshold_boundary():
    """Diff = 1.4x → NOT gap; diff = 1.6x → gap."""
    interval = HOUR_MS
    # 1.4x: should NOT be a gap
    df_no_gap = pd.DataFrame({
        "timestamp": [BASE_TS, BASE_TS + int(interval * 1.4)],
        "open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0],
        "close": [1.0, 1.0], "volume": [1.0, 1.0],
    })
    assert detect_gaps(df_no_gap, "1h") == []

    # 1.6x: should be a gap
    df_gap = pd.DataFrame({
        "timestamp": [BASE_TS, BASE_TS + int(interval * 1.6)],
        "open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0],
        "close": [1.0, 1.0], "volume": [1.0, 1.0],
    })
    assert len(detect_gaps(df_gap, "1h")) == 1
```

### Files cần modify

| File | Thay đổi |
|------|---------|
| `backend/services/cache.py` | Thêm `_INTERVAL_MS` dict và `detect_gaps()` function |
| `backend/models.py` | Thêm `has_gaps: bool = False` và `gaps: list[dict] = []` vào `OHLCVResponse` |
| `backend/routes/ohlcv.py` | Import `detect_gaps`, gọi sau slice, thêm vào `OHLCVResponse(...)` |

### Files cần tạo mới

| File | Nội dung |
|------|---------|
| `tests/test_ohlcv_gap_detection.py` | Unit tests cho `detect_gaps` + integration tests cho `GET /api/ohlcv` |

### Files KHÔNG được touch

- `backend/routes/fetch.py` — Story 1.2 / 1.4 scope
- `backend/services/binance.py` — Story 1.4 scope
- `backend/services/job_manager.py` — Story 1.4 scope
- `backend/settings.py` — không cần setting mới
- `tests/test_cache.py` — Story 1.3 scope
- Bất kỳ Phase 2 file nào

### Scope boundary — Story 1.5 vs kế tiếp

| Feature | Story 1.5 (này) | Kế tiếp |
|---------|----------------|---------|
| Detect gaps trong sliced data | ✓ | |
| `has_gaps` + `gaps` trong response | ✓ | |
| Clip detection (date range vượt cache) | đã có từ Story 1.1 | |
| Test coverage cho clip detection | ✓ (regression) | |
| **Frontend gap warning UI** | | Epic P1-2 (Story 2.3) |
| **MA/EMA slice-first** | | Epic P1-2 (Story 2.5) |

### Current state verification

Trước khi implement, dev cần verify 2 điều:
1. `OHLCVResponse.clipped` logic trong `ohlcv.py` vẫn đúng (không bị thay đổi bởi Story 1.3/1.4)
2. `read_ohlcv` trong `cache.py` vẫn sort ascending trước khi trả về (yêu cầu cho `detect_gaps`)

Cả hai đều đã verified từ Story 1.1. `detect_gaps` assume `df` đã sorted — đây là post-condition của `read_ohlcv`.

### References

- FR4: data gap detection — `_bmad-output/planning-artifacts/epics-phase1.md` line 26
- FR6: clip date range — `_bmad-output/planning-artifacts/epics-phase1.md` line 28
- Architecture: `DataGapError` class trong exception hierarchy — `architecture.md`
- Architecture: `sample_bars_with_gap` fixture hint — `architecture.md` line 1092
- Previous story P1-1.4: `_bmad-output/implementation-artifacts/p1-1-4-post-api-fetch-refresh-data-va-job-management.md`

## Review Findings (2026-05-03)

| # | Severity | File | Description | Status |
|---|----------|------|-------------|--------|
| F1 | LOW | cache.py:63-69 | `_INTERVAL_MS` duplicated with `binance.py` | Deferred |
| F2 | LOW | models.py:26 | `gaps: list[dict]` untyped | Deferred |
| F3 | LOW | cache.py:72 | `detect_gaps` doesn't validate sorted input | Deferred |

No MEDIUM/HIGH findings. Clean implementation.

## Dev Agent Record

### Agent Model Used

Claude (mimo-v2.5-pro)

### Debug Log References

- None — implementation was straightforward, no debugging needed

### Completion Notes List

- Added `_INTERVAL_MS` dict and `detect_gaps()` function to `cache.py` with O(n) single-pass algorithm
- Gap detection uses 1.5x threshold to avoid false positives from timezone/rounding jitter
- Updated `OHLCVResponse` model with `has_gaps` and `gaps` fields (backward compatible defaults)
- Updated `ohlcv.py` route to call `detect_gaps` on sliced data and include in response
- Created 15 tests: 10 unit tests for `detect_gaps` + 5 integration tests for `GET /api/ohlcv`
- All 164 tests pass (2 pre-existing settings failures unrelated to this story)

### File List

- `backend/services/cache.py` — Added `_INTERVAL_MS` dict and `detect_gaps()` function
- `backend/models.py` — Added `has_gaps: bool = False` and `gaps: list[dict] = []` to `OHLCVResponse`
- `backend/routes/ohlcv.py` — Added `detect_gaps` import, call on sliced data, include in response
- `tests/test_ohlcv_gap_detection.py` — New: 15 tests for gap detection (unit + integration)
