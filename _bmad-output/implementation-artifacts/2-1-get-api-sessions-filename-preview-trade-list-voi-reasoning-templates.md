# Story 2.1: GET /api/sessions/{filename}/preview — Trade List với Reasoning Templates

Status: done

## Story

As a trader,
I want backend trả về danh sách trades của session với reasoning template được pre-fill từ EMA/volume data,
So that ExportPreview có thể hiển thị context indicator cho từng trade mà không cần tôi nhập thủ công.

## Acceptance Criteria

1. **Given** file `BTCUSDT_4h_20260420.parquet` tồn tại trong `cache/` — **When** `GET /api/sessions/BTCUSDT_4h_20260420.parquet/preview` được gọi với trade list trong request body — **Then** trả về `trade_count`, `win_rate`, `quality_gate` ("pass"/"fail") và array `trades` với `reasoning_template` per trade.

2. **Given** trade tại `bar_index=42` (entry candle) — **When** backend compute reasoning template — **Then** EMA20, EMA50, volume được lấy tại `df.iloc[41]` (= slice `df.iloc[:42]`, lấy `.iloc[-1]` — slice-first, không look-ahead), format: `"4H | Entry $43,250 | EMA20=$42,100 | EMA50=$41,800 | Vol=1.8x | Outcome: WIN"`.

3. **Given** file Parquet chỉ định không tồn tại trong `cache/` — **When** `GET /api/sessions/{filename}/preview` được gọi — **Then** HTTP 404 với `APIResponse` error: `"Session file không tồn tại — có thể đã bị xóa"`.

4. **Given** session có 7 trades với win rate 71% — **When** preview response — **Then** `quality_gate: "fail"`, `quality_gate_reason: "7 trades — cần tối thiểu 10"`.

5. **Given** session có 15 trades với win rate 48% — **When** preview response — **Then** `quality_gate: "fail"`, `quality_gate_reason: "48% win rate — cần tối thiểu 55%"`.

6. **Given** session có 31 trades với win rate 67% — **When** preview response — **Then** `quality_gate: "pass"`, không có `quality_gate_reason` trong response.

7. **Given** request body có `trades: []` (empty array) — **When** preview được gọi — **Then** `trade_count: 0`, `win_rate: 0.0`, `quality_gate: "fail"`, `quality_gate_reason: "0 trades — cần tối thiểu 10"`.

## Tasks / Subtasks

- [x] Task 1: Thêm models vào `backend/models.py` (AC: #1, #2, #4, #5, #6)
  - [x] Thêm `TradeInput(BaseModel)` — trade data từ frontend EventBus `tradeCompleted` event
  - [x] Thêm `TradePreviewItem(BaseModel)` — `TradeInput` + `reasoning_template: str`
  - [x] Thêm `PreviewRequest(BaseModel)` — `trades: list[TradeInput]`
  - [x] Thêm `PreviewResponse(BaseModel)` — full response body (symbol, timeframe, date, trade_count, win_rate, quality_gate, quality_gate_reason?, trades)
  - [x] Verify không break existing models (`SessionItem`, `OHLCVBar`, `APIResponse[T]`)

- [x] Task 2: Tạo `backend/services/preview.py` — business logic (AC: #2, #4, #5, #6, #7)
  - [x] Implement `compute_quality_gate(trades: list[TradeInput]) -> tuple[str, str | None]` — trả về `("pass", None)` hoặc `("fail", reason_string)`
  - [x] Implement `compute_reasoning_template(df: pd.DataFrame, trade: TradeInput, timeframe: str) -> str` — slice-first EMA/volume compute
  - [x] Implement `build_preview(df: pd.DataFrame, filename: str, trades: list[TradeInput]) -> PreviewResponse` — gọi cả hai functions, parse filename, assemble response
  - [x] Handle NaN EMA values (bars quá ít cho EMA warm-up) — hiển thị `"N/A"` trong template thay vì crash
  - [x] Handle volume avg = 0 — vol_ratio = 1.0 (safe fallback)

- [x] Task 3: Thêm endpoint vào `backend/routes/sessions.py` (AC: #1, #3)
  - [x] Thêm `POST /sessions/{filename}/preview` vào router đã có từ Story 1.3
  - [x] QUAN TRỌNG: Dùng `POST` thay vì `GET` (xem Dev Notes — GET với request body không được hỗ trợ bởi nhiều HTTP clients + openapi tooling)
  - [x] Route: validate file exists, gọi `preview_service.build_preview()`, trả về `APIResponse[PreviewResponse]`
  - [x] 404 handler nếu file không tồn tại
  - [x] Không đọc Parquet trong route — delegate hoàn toàn cho service

- [x] Task 4: Viết tests `tests/test_preview.py` (AC: #1–#7)
  - [x] Fixture: tạo Parquet file 60+ bars với predictable OHLCV data trong `tmp_path`
  - [x] Test: file tồn tại, 31 valid trades → 200, `quality_gate: "pass"`, reasoning templates đúng format
  - [x] Test: file không tồn tại → 404 với error message
  - [x] Test: 7 trades, 71% WR → `quality_gate: "fail"`, reason về trade count
  - [x] Test: 15 trades, 48% WR → `quality_gate: "fail"`, reason về win rate
  - [x] Test: 7 trades VÀ 48% WR (cả hai fail) → `quality_gate: "fail"`, reason ghi đủ cả hai
  - [x] Test: slice-first enforcement — trade bar_index=42 phải dùng `df.iloc[:42]` (verify EMA ≠ full-df EMA khi price đang trend)
  - [x] Test: empty trades `[]` → 200 với `quality_gate: "fail"`, reason về 0 trades

## Dev Notes

### ⚠️ CRITICAL: Đây là Epic 2 — Phụ thuộc vào Stories 1.1, 1.2, 1.3

Story 2.1 phụ thuộc:
- **Story 1.1** (`backend/settings.py`): `settings.cache_dir` phải tồn tại — phải complete trước
- **Story 1.3** (`backend/routes/sessions.py`): router đã tồn tại — story này thêm endpoint mới vào cùng file
- **Story 1.2** (models): `APIResponse[T]`, `ErrorResponse` phải tồn tại trong `models.py`

> **Kiểm tra trước khi code:** `backend/routes/sessions.py` phải tồn tại và có `router = APIRouter(prefix="/api")`. Nếu không → dừng, chạy Story 1.3 trước.

---

### ⚠️ CRITICAL: Dùng POST, không phải GET cho endpoint này

PRD viết `GET /api/sessions/{filename}/preview` nhưng đây là **design error** trong spec. Lý do thực tế cần dùng POST:

1. **GET với request body không được hỗ trợ rộng** — nhiều HTTP proxies, CDN, và HTTP/1.1 clients (bao gồm cả một số versions của `fetch()` trong browsers) có thể strip body từ GET requests
2. **OpenAPI / FastAPI behavior** — FastAPI không suggest GET với body; Swagger UI sẽ không render body fields cho GET endpoints
3. **Semantics** — endpoint nhận trade data từ client để compute → đây là "processing action" phù hợp với POST semantics

**Quyết định:** Implement là `POST /api/sessions/{filename}/preview`.

Frontend (Story 2.2) sẽ gọi:
```typescript
const response = await fetch(`/api/sessions/${filename}/preview`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ trades: accumulatedTrades }),
});
```

> **Nếu bị yêu cầu dùng GET:** Dùng FastAPI `Body(...)` và chấp nhận giới hạn OpenAPI compatibility. Đừng tự ý switch mà không confirm.

---

### Architecture Rules (ADR-09, ADR-07, Gap-1)

**Route chỉ là HTTP layer — không có business logic:**
```python
# backend/routes/sessions.py — chỉ thêm vào file đã có từ Story 1.3
@router.post("/sessions/{filename}/preview", response_model=APIResponse[PreviewResponse])
async def preview_session(
    filename: str,
    request: PreviewRequest,
) -> APIResponse[PreviewResponse]:
    """
    Nhận trade list từ frontend, đọc Parquet, compute EMA templates, trả về preview.
    Business logic hoàn toàn trong services/preview.py.
    """
    cache_dir: Path = settings.cache_dir
    parquet_path = cache_dir / filename

    if not parquet_path.exists():
        return JSONResponse(
            status_code=404,
            content=APIResponse(
                error=ErrorResponse(
                    message="Session file không tồn tại — có thể đã bị xóa",
                    code="SESSION_NOT_FOUND",
                    retryable=False,
                )
            ).model_dump(),
        )

    try:
        result = await preview_service.build_preview(parquet_path, filename, request.trades)
        return APIResponse(data=result)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=APIResponse(
                error=ErrorResponse(
                    message=str(e),
                    code="PREVIEW_FAILED",
                    retryable=True,
                )
            ).model_dump(),
        )
```

**Service layer — ADR-07 + Gap-1 slice-first:**
```python
# backend/services/preview.py
import re
import pandas as pd
from pathlib import Path

from backend.models import (
    PreviewRequest, PreviewResponse, TradeInput, TradePreviewItem
)

# Reuse filename parser từ sessions.py (hoặc import từ đó nếu đã extracted)
_SESSION_FILENAME_PATTERN = re.compile(
    r"^([A-Z0-9]+)_([A-Za-z0-9]+)_(\d{8})\.parquet$"
)


def compute_quality_gate(trades: list[TradeInput]) -> tuple[str, str | None]:
    """
    Kiểm tra quality gate: trade_count >= 10 AND win_rate >= 55%.
    Trả về ("pass", None) hoặc ("fail", reason_string).
    """
    trade_count = len(trades)
    win_count = sum(1 for t in trades if t.result == "win")
    win_rate = win_count / trade_count if trade_count > 0 else 0.0

    reasons: list[str] = []
    if trade_count < 10:
        reasons.append(f"{trade_count} trades — cần tối thiểu 10")
    if win_rate < 0.55:
        pct = int(round(win_rate * 100))
        reasons.append(f"{pct}% win rate — cần tối thiểu 55%")

    if reasons:
        return "fail", "; ".join(reasons)
    return "pass", None


def compute_reasoning_template(
    df: pd.DataFrame,
    trade: TradeInput,
    timeframe: str,
) -> str:
    """
    Compute reasoning template cho một trade.

    CRITICAL — Gap-1 (slice-first, no look-ahead):
    - Slice TRƯỚC khi compute: df.iloc[:trade.bar_index]
    - EMA được tính trên sliced df → lấy .iloc[-1]
    - Giá trị tại bar_index - 1 (candle TRƯỚC entry) = không nhìn vào tương lai

    Ví dụ: trade.bar_index=42 → sliced_df = df.iloc[:42] (rows 0–41)
           EMA20 tại entry = sliced_df['close'].ewm(span=20, adjust=False).mean().iloc[-1]
    """
    bar_index = trade.bar_index
    if bar_index <= 0 or bar_index > len(df):
        # fallback nếu bar_index out of range
        bar_index = min(bar_index, len(df))

    sliced_df = df.iloc[:bar_index]  # slice TRƯỚC, Gap-1 compliance

    close_series = sliced_df["close"]
    volume_series = sliced_df["volume"]

    # ADR-07: pandas built-in ewm() — không dùng thư viện ngoài
    ema20_series = close_series.ewm(span=20, adjust=False).mean()
    ema50_series = close_series.ewm(span=50, adjust=False).mean()
    vol_avg_series = volume_series.rolling(window=20, min_periods=1).mean()

    ema20_val = ema20_series.iloc[-1] if len(ema20_series) > 0 else None
    ema50_val = ema50_series.iloc[-1] if len(ema50_series) > 0 else None
    vol_curr = volume_series.iloc[-1] if len(volume_series) > 0 else None
    vol_avg = vol_avg_series.iloc[-1] if len(vol_avg_series) > 0 else None

    # Format EMA values — "$42,100" pattern
    def fmt_price(val: float | None) -> str:
        if val is None or pd.isna(val):
            return "N/A"
        return f"${val:,.0f}"

    # Volume ratio — "1.8x" pattern
    def fmt_vol_ratio(curr: float | None, avg: float | None) -> str:
        if curr is None or avg is None or pd.isna(curr) or pd.isna(avg):
            return "N/Ax"
        ratio = curr / avg if avg > 0 else 1.0
        return f"{ratio:.1f}x"

    # Outcome: WIN/LOSS (uppercase)
    outcome = "WIN" if trade.result == "win" else "LOSS"

    # Timeframe uppercase: "4h" → "4H"
    tf_upper = timeframe.upper()

    # Entry price format: "$43,250"
    entry_fmt = f"${trade.entry_price:,.0f}"

    return (
        f"{tf_upper} | Entry {entry_fmt} | "
        f"EMA20={fmt_price(ema20_val)} | EMA50={fmt_price(ema50_val)} | "
        f"Vol={fmt_vol_ratio(vol_curr, vol_avg)} | Outcome: {outcome}"
    )


async def build_preview(
    parquet_path: Path,
    filename: str,
    trades: list[TradeInput],
) -> PreviewResponse:
    """
    Đọc Parquet, compute quality gate + reasoning templates, trả về PreviewResponse.
    Gọi từ route — route chỉ handle HTTP, service handle data.
    """
    # Parse filename để lấy symbol, timeframe, date
    match = _SESSION_FILENAME_PATTERN.match(filename)
    if not match:
        raise ValueError(f"Invalid session filename format: {filename}")

    symbol, timeframe, date_raw = match.groups()
    date_formatted = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}"

    # Đọc Parquet — dùng pandas trực tiếp (cache.py's read_parquet cũng OK nếu đã có)
    df = pd.read_parquet(parquet_path)

    # Validate monotonic timestamps (Data Integrity Rule từ architecture.md)
    if len(df) > 0:
        assert df["timestamp"].is_monotonic_increasing, (
            f"Session Parquet not sorted ascending: {parquet_path}"
        )

    # Quality gate check
    trade_count = len(trades)
    win_count = sum(1 for t in trades if t.result == "win")
    win_rate = win_count / trade_count if trade_count > 0 else 0.0
    quality_gate, quality_gate_reason = compute_quality_gate(trades)

    # Compute reasoning templates per trade
    preview_trades: list[TradePreviewItem] = []
    for trade in trades:
        reasoning = compute_reasoning_template(df, trade, timeframe)
        preview_trades.append(
            TradePreviewItem(
                bar_index=trade.bar_index,
                entry_timestamp_ms=trade.entry_timestamp_ms,
                direction=trade.direction,
                entry_price=trade.entry_price,
                tp_price=trade.tp_price,
                sl_price=trade.sl_price,
                result=trade.result,
                bars_to_exit=trade.bars_to_exit,
                reasoning_template=reasoning,
            )
        )

    return PreviewResponse(
        symbol=symbol,
        timeframe=timeframe,
        date=date_formatted,
        trade_count=trade_count,
        win_rate=round(win_rate, 4),  # 0.6710 precision
        quality_gate=quality_gate,
        quality_gate_reason=quality_gate_reason,
        trades=preview_trades,
    )
```

---

### `backend/models.py` — New Models

Thêm vào cuối `models.py` (KHÔNG sửa existing models):

```python
from typing import Literal

# ─── Phase 2: Preview endpoint models ───────────────────────────────────────

class TradeInput(BaseModel):
    """
    Trade data được gửi từ frontend.
    Matches tradeCompleted EventBus payload trong types.ts.
    """
    bar_index: int                          # 0-indexed bar position trong DataFrame
    entry_timestamp_ms: int                 # Unix ms int64 (ADR-03)
    direction: Literal["LONG", "SHORT"]
    entry_price: float
    tp_price: float
    sl_price: float
    result: Literal["win", "loss"]
    bars_to_exit: int


class TradePreviewItem(TradeInput):
    """TradeInput + computed reasoning template từ backend."""
    reasoning_template: str                 # "4H | Entry $43,250 | EMA20=... | Outcome: WIN"


class PreviewRequest(BaseModel):
    """Request body cho POST /api/sessions/{filename}/preview."""
    trades: list[TradeInput]


class PreviewResponse(BaseModel):
    """
    Response body cho preview endpoint.
    Sẽ được wrapped trong APIResponse[PreviewResponse].
    """
    symbol: str                             # "BTCUSDT"
    timeframe: str                          # "4h"
    date: str                               # "2026-04-20"
    trade_count: int
    win_rate: float                         # 0.67 (not percentage)
    quality_gate: Literal["pass", "fail"]
    quality_gate_reason: str | None = None  # None khi "pass"
    trades: list[TradePreviewItem]
```

---

### `backend/routes/sessions.py` — Chỉ Thêm Vào, Không Sửa Existing

**File này đã được tạo trong Story 1.3.** Story 2.1 chỉ ADD thêm imports và 1 endpoint:

```python
# THÊM imports (đặt cùng với existing imports)
from fastapi.responses import JSONResponse
from backend.models import APIResponse, ErrorResponse, PreviewRequest, PreviewResponse
from backend.services import preview as preview_service

# ... (existing code từ Story 1.3 — GET /sessions endpoint giữ nguyên) ...

# THÊM endpoint mới bên dưới existing endpoint
@router.post("/sessions/{filename}/preview", response_model=APIResponse[PreviewResponse])
async def preview_session(
    filename: str,
    request: PreviewRequest,
) -> APIResponse[PreviewResponse]:
    """
    POST thay vì GET vì request body required (trade list từ frontend).
    Đọc Parquet, compute EMA indicators (slice-first), trả về trade list + reasoning templates.
    """
    parquet_path = settings.cache_dir / filename

    if not parquet_path.exists():
        return JSONResponse(
            status_code=404,
            content=APIResponse(
                error=ErrorResponse(
                    message="Session file không tồn tại — có thể đã bị xóa",
                    code="SESSION_NOT_FOUND",
                    retryable=False,
                )
            ).model_dump(),
        )

    try:
        result = await preview_service.build_preview(parquet_path, filename, request.trades)
        return APIResponse(data=result)
    except ValueError as e:
        return JSONResponse(
            status_code=422,
            content=APIResponse(
                error=ErrorResponse(
                    message=str(e),
                    code="INVALID_FILENAME",
                    retryable=False,
                )
            ).model_dump(),
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=APIResponse(
                error=ErrorResponse(
                    message=f"Preview computation failed: {e}",
                    code="PREVIEW_FAILED",
                    retryable=True,
                )
            ).model_dump(),
        )
```

**Không cần đăng ký router mới trong `main.py`** — `sessions_router` đã được register trong Story 1.3. Story 2.1 chỉ thêm endpoint vào router có sẵn.

---

### `tests/test_preview.py` — Test Cases

```python
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

# Fixture: tạo Parquet file 60 bars với predictable data
@pytest.fixture
def session_parquet(tmp_path: Path) -> Path:
    """
    Tạo session Parquet file BTCUSDT_4h_20260420.parquet với 60 bars.
    Close price = 40000 + i * 100 (tăng dần để EMA < current price).
    Volume = 1000 (constant, vol_ratio = 1.0x khi avg cũng 1000).
    """
    n = 60
    base_ts = 1745625600000  # 2026-04-20 00:00:00 UTC in ms
    interval_ms = 4 * 60 * 60 * 1000  # 4h in ms

    data = {
        "timestamp": [base_ts + i * interval_ms for i in range(n)],
        "open":  [40000.0 + i * 100 for i in range(n)],
        "high":  [40100.0 + i * 100 for i in range(n)],
        "low":   [39900.0 + i * 100 for i in range(n)],
        "close": [40050.0 + i * 100 for i in range(n)],
        "volume": [1000.0] * n,
    }
    df = pd.DataFrame(data)
    path = tmp_path / "BTCUSDT_4h_20260420.parquet"
    df.to_parquet(path, index=False)
    return path


@pytest.fixture
def sample_trades() -> list[dict]:
    """31 trades: 21 wins, 10 losses → 67.7% win rate → quality_gate pass."""
    base_ts = 1745625600000
    interval_ms = 4 * 60 * 60 * 1000
    trades = []
    for i in range(31):
        result = "win" if i < 21 else "loss"
        bar_index = i + 5  # bắt đầu từ bar 5 để có đủ data
        trades.append({
            "bar_index": bar_index,
            "entry_timestamp_ms": base_ts + bar_index * interval_ms,
            "direction": "LONG",
            "entry_price": 40050.0 + bar_index * 100,
            "tp_price": 40500.0 + bar_index * 100,
            "sl_price": 39500.0 + bar_index * 100,
            "result": result,
            "bars_to_exit": 3,
        })
    return trades


def test_preview_pass_quality_gate(client, session_parquet, monkeypatch, sample_trades):
    """31 trades, 67% WR → quality_gate pass, templates computed."""
    # Setup: monkeypatch settings.cache_dir → tmp_path
    ...
    resp = client.post(
        f"/api/sessions/BTCUSDT_4h_20260420.parquet/preview",
        json={"trades": sample_trades},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    data = body["data"]
    assert data["quality_gate"] == "pass"
    assert data["quality_gate_reason"] is None
    assert data["trade_count"] == 31
    assert data["win_rate"] == pytest.approx(21/31, abs=0.001)
    # Kiểm tra template format
    first_template = data["trades"][0]["reasoning_template"]
    assert "4H | Entry $" in first_template
    assert "EMA20=$" in first_template
    assert "EMA50=$" in first_template
    assert "Vol=" in first_template
    assert "Outcome: WIN" in first_template


def test_preview_file_not_found(client, tmp_path, monkeypatch):
    """File không tồn tại → 404."""
    ...
    resp = client.post(
        "/api/sessions/NONEXISTENT_4h_20260420.parquet/preview",
        json={"trades": []},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["data"] is None
    assert "không tồn tại" in body["error"]["message"]
    assert body["error"]["code"] == "SESSION_NOT_FOUND"


def test_preview_quality_gate_fail_trade_count(client, session_parquet, monkeypatch):
    """7 trades, 71% WR → fail on trade count."""
    trades = [
        {
            "bar_index": 10 + i, "entry_timestamp_ms": 1745625600000,
            "direction": "LONG", "entry_price": 41000.0, "tp_price": 42000.0,
            "sl_price": 40000.0, "result": "win" if i < 5 else "loss", "bars_to_exit": 2,
        }
        for i in range(7)
    ]
    ...
    resp = client.post("/api/sessions/BTCUSDT_4h_20260420.parquet/preview", json={"trades": trades})
    data = resp.json()["data"]
    assert data["quality_gate"] == "fail"
    assert "7 trades" in data["quality_gate_reason"]
    assert "10" in data["quality_gate_reason"]


def test_preview_quality_gate_fail_win_rate(client, session_parquet, monkeypatch):
    """15 trades, 48% WR → fail on win rate."""
    trades = [
        {
            "bar_index": 10 + i, "entry_timestamp_ms": 1745625600000,
            "direction": "LONG", "entry_price": 41000.0, "tp_price": 42000.0,
            "sl_price": 40000.0,
            "result": "win" if i < 7 else "loss",  # 7/15 = 46.7% < 55%
            "bars_to_exit": 2,
        }
        for i in range(15)
    ]
    ...
    data = resp.json()["data"]
    assert data["quality_gate"] == "fail"
    assert "win rate" in data["quality_gate_reason"].lower() or "%" in data["quality_gate_reason"]


def test_preview_slice_first_enforcement(client, session_parquet, monkeypatch):
    """
    CRITICAL: EMA tại bar_index=42 phải dùng df.iloc[:42], KHÔNG phải full df.
    Verify bằng cách compare EMA value với manual computation.
    """
    # Manual compute để so sánh
    df = pd.read_parquet(session_parquet)
    sliced = df.iloc[:42]
    expected_ema20 = sliced["close"].ewm(span=20, adjust=False).mean().iloc[-1]

    trade = {
        "bar_index": 42, "entry_timestamp_ms": 1745625600000,
        "direction": "LONG", "entry_price": df.iloc[41]["close"],
        "tp_price": df.iloc[41]["close"] + 500,
        "sl_price": df.iloc[41]["close"] - 500,
        "result": "win", "bars_to_exit": 5,
    }
    ...
    data = resp.json()["data"]
    template = data["trades"][0]["reasoning_template"]
    # Template phải chứa EMA20 từ slice, không phải full df
    # (trong fixture này close tăng dần → slice EMA < full-df EMA)
    expected_str = f"${expected_ema20:,.0f}"
    assert expected_str in template, f"Expected EMA20 {expected_str} in template: {template}"


def test_preview_empty_trades(client, session_parquet, monkeypatch):
    """Empty trade list → quality_gate fail với reason."""
    ...
    resp = client.post("/api/sessions/BTCUSDT_4h_20260420.parquet/preview", json={"trades": []})
    data = resp.json()["data"]
    assert data["quality_gate"] == "fail"
    assert data["trade_count"] == 0
    assert "0 trades" in data["quality_gate_reason"]
```

> **Test isolation:** Dùng `monkeypatch` để set `settings.cache_dir = tmp_path` trước mỗi test. Pattern này giống test_sessions.py từ Story 1.3.

---

### EMA/Volume Computation — Chi Tiết Kỹ Thuật

**ADR-07 compliant implementation:**

```python
# ADR-07: Indicator Library Strategy
# MVP: pandas built-in ewm() — Zero external dependency
# def ema(series, length): return series.ewm(span=length, adjust=False).mean()

# EMA20 (20-period Exponential Moving Average)
ema20 = close_series.ewm(span=20, adjust=False).mean().iloc[-1]

# EMA50 (50-period Exponential Moving Average)
ema50 = close_series.ewm(span=50, adjust=False).mean().iloc[-1]

# Volume ratio — current vs 20-period average
vol_avg = volume_series.rolling(window=20, min_periods=1).mean().iloc[-1]
vol_ratio = vol_curr / vol_avg if vol_avg > 0 else 1.0
```

**NaN Handling:**
- `ewm()` với ít bars → các bars đầu NaN do warm-up period
- Với `iloc[-1]`, nếu series chỉ có 1 bar → EMA50 = close price của bar đó (không NaN vì ewm handles min_periods)
- `min_periods=1` trong `rolling()` → không bao giờ NaN cho volume avg

> **Lưu ý pandas EMA behavior:** `ewm(span=20, adjust=False)` với 1 bar → không NaN, trả về chính bar đó. Với `adjust=False`, mỗi new observation được weight theo `alpha = 2/(span+1)`. Đây là "recursive EMA" — đúng cho trading indicators.

**Format Template:**
```python
# Timeframe uppercase
tf_upper = timeframe.upper()  # "4h" → "4H", "1d" → "1D"

# Price với comma separator, 0 decimal
f"${entry_price:,.0f}"   # $43,250
f"${ema20:,.0f}"         # $42,100

# Volume ratio, 1 decimal
f"{vol_ratio:.1f}x"      # 1.8x

# Outcome uppercase
outcome = "WIN" if result == "win" else "LOSS"

# Final template
f"{tf_upper} | Entry {entry_fmt} | EMA20={ema20_fmt} | EMA50={ema50_fmt} | Vol={vol_fmt} | Outcome: {outcome}"
```

---

### Parquet File Structure — Phase 2 Sessions

Phase 2 session files (`BTCUSDT_4h_20260420.parquet`) là snapshot của **Phase 1 OHLCV Parquet data** cho một replay session cụ thể:

**Schema (same as Phase 1, ADR-03):**
| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | int64 | Unix ms UTC |
| `open` | float64 | Open price |
| `high` | float64 | High price |
| `low` | float64 | Low price |
| `close` | float64 | Close price |
| `volume` | float64 | Trade volume |

> **Không có `bar_index` column** — `bar_index` trong trade data là positional index vào DataFrame (0-indexed row position). `df.iloc[bar_index]` = candle tại entry. `df.iloc[:bar_index]` = slice không bao gồm entry candle.

**Phase 2 filename vs Phase 1 cache:**
| | Phase 1 cache | Phase 2 session |
|---|---|---|
| Pattern | `BTC_USDT_4h.parquet` | `BTCUSDT_4h_20260420.parquet` |
| Role | Full OHLCV cache | Session snapshot |
| Schema | Same ADR-03 | Same ADR-03 |

---

### Quality Gate Logic — Exact Thresholds

| Condition | Threshold | Error Message |
|-----------|-----------|---------------|
| Trade count | `trades < 10` | `"{n} trades — cần tối thiểu 10"` |
| Win rate | `win_rate < 0.55` | `"{n}% win rate — cần tối thiểu 55%"` |

Khi cả hai fail:
- `quality_gate_reason = "{trade_reason}; {winrate_reason}"`
- Ví dụ: `"7 trades — cần tối thiểu 10; 48% win rate — cần tối thiểu 55%"`

Win rate calculation:
```python
win_count = sum(1 for t in trades if t.result == "win")
win_rate = win_count / len(trades)  # float 0.0–1.0
```

---

### New Files Created in Story 2.1

| File | Action |
|------|--------|
| `backend/services/preview.py` | **CREATE NEW** |
| `tests/test_preview.py` | **CREATE NEW** |

### Files Modified in Story 2.1

| File | Change |
|------|--------|
| `backend/models.py` | Thêm `TradeInput`, `TradePreviewItem`, `PreviewRequest`, `PreviewResponse` |
| `backend/routes/sessions.py` | Thêm `POST /sessions/{filename}/preview` endpoint |

**Không cần sửa `backend/main.py`** — `sessions_router` đã registered trong Story 1.3.

### Backward-Compatibility Checklist

- [ ] `GET /api/sessions` (Story 1.3) vẫn hoạt động sau khi thêm endpoint mới
- [ ] `backend/models.py` existing models không bị thay đổi signature
- [ ] `backend/settings.py` không cần thay đổi
- [ ] Phase 1 endpoints (`GET /api/ohlcv`, `POST /api/fetch_jobs`) không bị ảnh hưởng

### NFR Compliance

- **NFR2 (Medium):** Export preview render < 500ms cho session ≤ 200 trades — EMA computation cho 200 trades × 200-bar slice phải < 500ms trên local machine. `pd.ewm()` là O(n) — acceptable với 200 × 200 = 40,000 operations.
- **NFR14 (High):** Export fail không corrupt Parquet local cache — Story 2.1 chỉ READ Parquet (`pd.read_parquet`), không write. 100% safe.
- **NFR19 (Medium):** Quality gate logic và reasoning template generation phải có pytest unit tests — covered bởi `tests/test_preview.py`.

### References

- [epics.md - Story 2.1 Acceptance Criteria](_bmad-output/planning-artifacts/epics.md#story-21-get-apisessionsfilenamepreview--trade-list-với-reasoning-templates)
- [prd-phase2-supabase.md - FR6, FR10, FR11, FR12, FR26, FR34](_bmad-output/planning-artifacts/prd-phase2-supabase.md)
- [architecture.md - ADR-07 (pandas ewm), Gap-1 (slice-first)](_bmad-output/planning-artifacts/architecture.md#adr-07-revised-indicator-implementation)
- [architecture.md - ADR-09 (module split), ADR-11 (settings)](_bmad-output/planning-artifacts/architecture.md#adr-09-backend-module-structure)
- [architecture.md - ADR-17 (APIResponse wrapper)](_bmad-output/planning-artifacts/architecture.md#implementation-patterns--consistency-rules)
- [1-3-get-api-sessions-danh-sach-parquet-sessions.md - Sessions router pattern](_bmad-output/implementation-artifacts/1-3-get-api-sessions-danh-sach-parquet-sessions.md)
- NFR2: Preview < 500ms; NFR14: Parquet unaffected; NFR19: Quality gate tests required

## Review Findings (2026-04-27)

### Patches Applied
- [x] P1 — `compute_quality_gate`: early return for `trade_count == 0`; win-rate branch guarded by `trade_count > 0`
- [x] P2 — Route `except ValueError`: sanitized to static message, no server path leaked; uses `logger.exception`
- [x] P3 — `test_preview_quality_gate_fail_win_rate`: fixed inverted assertion (`assert "trades" not in reason`)
- [x] P4 — `test_preview_slice_first_enforcement`: rebuilt with diverging price fixture + negative assertion against full-df EMA
- [x] P5 — `build_preview`: required columns check after `pd.read_parquet`
- [x] P6 — `build_preview`: 0-row guard before `.iloc[-1]` access
- [x] P7 — New test: `test_quality_gate_exact_boundary` (20 trades, 11/20 = 55% → "pass")
- [x] P8 — New tests: `test_preview_bar_index_minimum` + `test_preview_bar_index_zero_rejected`
- [x] P9 — New tests: `test_preview_path_traversal_blocked` + `test_preview_malformed_filename_returns_422`
- [x] D1 — `TradeInput.bar_index: Annotated[int, Field(ge=1)]` + `bars_to_exit ge=0` + price fields `gt=0`
- [x] D2 — `build_preview`: `pd.read_parquet` wrapped with `asyncio.run_in_executor` (non-blocking)
- [x] D3 — AC5 test fixture changed to 25 trades / 12 wins = 48.0% exactly; AC text updated in docstring

### Deferred
- E3: bar_index > len(df) silent clamp (low risk, no crash) — defer to Story 4.3
- E6: timestamp dtype validation — defer to Story 4.3
- E12: distinct error codes per ValueError cause — defer to Story 4.3

### Result: 41 passed (14 preview + 27 regression), TypeScript 0 errors

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Completion Notes List

- Endpoint implement là `POST /api/sessions/{filename}/preview` (không phải GET) theo Dev Notes — GET với request body không được hỗ trợ rộng rãi.
- `pyarrow==24.0.0` cần được cài thủ công bằng `pip3 install pyarrow==24.0.0` trong môi trường pyenv (chưa có sẵn — đây là first-time install).
- `backend/services/__init__.py` đã tồn tại (empty file từ trước) — `from backend.services import preview as preview_service` hoạt động đúng.
- EMA với `ewm(span=20, adjust=False)` và `min_periods` default → không bao giờ NaN kể cả với 1 bar (recursive EMA behavior).
- Slice-first enforcement (Gap-1): `df.iloc[:bar_index]` verified bởi test `test_preview_slice_first_enforcement` — EMA value từ slice khớp expected manual computation.
- 24/24 tests pass (9 mới + 15 regression): pytest exit 0.

### File List

- `backend/models.py` — MODIFIED (thêm TradeInput, TradePreviewItem, PreviewRequest, PreviewResponse)
- `backend/services/preview.py` — CREATED
- `backend/routes/sessions.py` — MODIFIED (thêm POST /sessions/{filename}/preview endpoint)
- `tests/test_preview.py` — CREATED (9 tests, 9 pass)
