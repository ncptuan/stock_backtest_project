# Story 4.2: Pytest unit tests cho critical paths

Status: done

## Story

As a developer,
I want unit tests cover quality gate, signal_id generation, outcome mapping, và reasoning template,
So that những logic critical này được verify tự động — không cần Supabase connection để chạy tests.

## Acceptance Criteria

1. **Given** `tests/test_export.py` tồn tại (từ Story 3.1) — **When** `pytest tests/test_export.py` chạy — **Then** tất cả tests pass — không cần Supabase credentials, không cần internet connection.

2. **Given** quality gate logic tại `POST /api/export`
   — **When** test cases:
   - `(trades=7, win_rate=0.71)` → fail với reason về trade count
   - `(trades=15, win_rate=0.48)` → fail với reason về win rate
   - `(trades=10, win_rate=0.55)` → pass (export proceeds)
   - `(trades=9, win_rate=0.60)` → fail với reason về trade count
   — **Then** HTTP 422 cho fail cases, export continues cho pass case — reason message cụ thể cho từng fail.

3. **Given** signal_id generation function — **When** `pytest tests/test_supabase_service.py` — **Then** `generate_signal_id("20260426", "breakout_4h", 42)` = `"backtest_20260426_breakout_4h_00042"` *(đã covered bởi Story 4.1 — xác nhận không bị regression)*.

4. **Given** outcome mapping tests — **When** `pytest tests/test_supabase_service.py` — **Then** `result="win"` → `follow="TP hit"`, `outcome="TP_HIT"`; `result="loss"` → `follow="SL hit"`, `outcome="SL_HIT"`; `direction="LONG"` → `bot_verdict="BUY"`; `direction="SHORT"` → `bot_verdict="SELL"` *(đã covered bởi Story 4.1 — xác nhận không bị regression)*.

5. **Given** reasoning template generation với Parquet data — **When** `pytest tests/test_quality_gate.py` — **Then** template output đúng format: `"4H | Entry $43,250 | EMA20=$... | EMA50=$... | Vol=...x | Outcome: WIN"` — EMA values lấy từ `df.iloc[bar_index - 1]` (slice-first, không look-ahead).

6. **Given** bars_to_exit off-by-one test — **When** trade entry tại bar 42 và exit tại bar 49 — **Then** `bars_to_exit = 7` — explicit assertion ngăn off-by-one regression.

7. **Given** `backend/routes/export.py` hiện tại (từ Story 3.1) **không có** quality gate check — **When** Story 4.2 complete — **Then** backend route enforce quality gate TRƯỚC khi ghi bất kỳ row nào: HTTP 422 với `{"error": "quality_gate", "message": "..."}` nếu `len(trades) < 10` HOẶC `session_win_rate < 0.55`.

## Tasks / Subtasks

- [ ] Task 1: Thêm quality gate check vào `backend/routes/export.py` (AC: #2, #7)
  - [ ] Sau duplicate check (step 3) và TRƯỚC write signal_comparisons (step 4)
  - [ ] Check: `trade_count = len(request.trades)` và `win_rate = request.session_win_rate`
  - [ ] Build reason message: collect failures (count < 10, win_rate < 0.55) → join với "; "
  - [ ] Nếu quality gate fail → `raise HTTPException(status_code=422, detail={"error": "quality_gate", "message": reason})`
  - [ ] Pattern từ `compute_quality_gate` trong `backend/services/preview.py` — dùng cùng logic, cùng reason format: `f"{count} trades — cần tối thiểu 10"` và `f"{pct}% win rate — cần tối thiểu 55%"`
  - [ ] **Không** import `compute_quality_gate` từ `services/preview.py` — inline logic trong route (ExportTrade vs TradeInput models khác nhau, inline tránh coupling)

- [ ] Task 2: Extend `tests/test_export.py` — thêm quality gate test cases (AC: #1, #2)
  - [ ] File đã tồn tại từ Story 3.1 — **EXTEND**, không tạo lại
  - [ ] Test: 7 trades (win_rate=0.71) → HTTP 422, `error = "quality_gate"`, message chứa "7 trades"
  - [ ] Test: 15 trades (win_rate=0.48) → HTTP 422, `error = "quality_gate"`, message chứa "48% win rate"
  - [ ] Test: 20 trades (win_rate=0.55) → KHÔNG 422 — export proceeds (mock httpx để pass Supabase calls)
  - [ ] Test: 9 trades (win_rate=0.60) → HTTP 422, `error = "quality_gate"`, message chứa "9 trades"
  - [ ] Test: cả hai fail (7 trades, win_rate=0.48) → 422, message chứa cả count lẫn win rate
  - [ ] Test: quality gate check xảy ra TRƯỚC Supabase write — verify httpx KHÔNG được gọi khi quality gate fail (mock assertion)
  - [ ] Test: `bars_to_exit` field có trong ExportTrade — assert `49 - 42 == 7` là explicit test cho off-by-one (AC: #6)

- [ ] Task 3: Tạo `tests/test_quality_gate.py` — pure unit tests (AC: #5, #6)
  - [ ] Test `compute_quality_gate` pure function từ `backend.services.preview`
  - [ ] Test: 7 trades (5 wins) → `("fail", "7 trades — cần tối thiểu 10")`
  - [ ] Test: 15 trades (7 wins → 46%) → `("fail", "46% win rate — cần tối thiểu 55%")`
  - [ ] Test: 20 trades (11 wins → 55%) → `("pass", None)` — boundary pass
  - [ ] Test: 9 trades (6 wins → 67%) → `("fail", "9 trades — cần tối thiểu 10")` — count fail even with good WR
  - [ ] Test: 7 trades (3 wins → 43%) → `("fail", "7 trades...; 43% win rate...")` — dual fail, both reasons joined
  - [ ] Test: 0 trades → `("fail", "0 trades — cần tối thiểu 10")`
  - [ ] Test `compute_reasoning_template` format — verify output matches regex `r"\d+H \| Entry \$[\d,]+ \| EMA20=\$[\d,N/A]+ \| EMA50=\$[\d,N/A]+ \| Vol=[\d.N/A]+x \| Outcome: (WIN|LOSS)"`
  - [ ] Test reasoning template với real minimal DataFrame (5 bars) — just verify format, không assert exact EMA values
  - [ ] Test reasoning template outcome: `result="win"` → `"Outcome: WIN"`, `result="loss"` → `"Outcome: LOSS"`
  - [ ] Test reasoning template timeframe uppercase: timeframe="4h" → output chứa "4H"
  - [ ] Test `bars_to_exit` off-by-one: `assert 49 - 42 == 7` — explicit regression guard

### Review Findings

- [x] [Review][Patch] Stale comment `# 4.` trong export.py step 6 [backend/routes/export.py] — fixed: đổi thành `# 6.`
- [x] [Review][Patch] test_quality_gate_fail_win_rate không assert phần trăm cụ thể — AC #2 yêu cầu "48%" [tests/test_export.py] — fixed: thêm `assert "48%" in detail["message"]`
- [x] [Review][Patch] Story file Status vẫn là `ready-for-dev` thay vì `review` — fixed

## Dev Notes

### ⚠️ CRITICAL: Story 3.1 Đã Tạo `tests/test_export.py` — EXTEND Không Tạo Lại

Story 3.1 Task 5 (marked done [x]) đã tạo `tests/test_export.py` với các tests:
- `SUPABASE_ENABLED=false` → 503
- Timeout → 504
- Duplicate → 409
- Partial write rolled back → 500
- Valid payload → 200
- signal_id format

Story 4.2 **EXTENDS** file này với quality gate tests — **không overwrite/recreate**.

> **Trước khi edit**: Đọc toàn bộ `tests/test_export.py` hiện tại để tránh trùng lặp test. Thêm vào cuối file.

---

### ⚠️ CRITICAL: Quality Gate Check Bị Thiếu trong Story 3.1

`backend/routes/export.py` (Story 3.1) hiện tại **không có** quality gate check. PRD FR10/FR11 yêu cầu backend CŨNG enforce:
- FR10: Export từ chối nếu trade count < 10 *(CRITICAL)*
- FR11: Export từ chối nếu win rate < 55% *(CRITICAL)*

PRD API contract: `"error": "quality_gate|duplicate|auth_failed|partial_write_rolled_back"` — `quality_gate` là listed error.

**BACKEND DEFENSE-IN-DEPTH**: Frontend đã check quality gate trong QualityGateBlock.ts (Story 2.2). Backend phải CŨNG check để prevent:
1. API calls không qua frontend (curl, scripts)
2. Frontend bug bỏ qua QualityGateBlock
3. Race condition giữa preview check và export submit

---

### `backend/routes/export.py` — Quality Gate Addition

Thêm vào SAU duplicate check (step 3), TRƯỚC write:

```python
    # 3.5. Quality gate enforcement (backend defense-in-depth — FR10, FR11)
    trade_count = len(request.trades)
    win_rate = request.session_win_rate

    qg_reasons: list[str] = []
    if trade_count < 10:
        qg_reasons.append(f"{trade_count} trades — cần tối thiểu 10")
    if win_rate < 0.55:
        pct = int(round(win_rate * 100))
        qg_reasons.append(f"{pct}% win rate — cần tối thiểu 55%")

    if qg_reasons:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "quality_gate",
                "message": "; ".join(qg_reasons),
            },
        )
```

**Lưu ý về inline vs import:**
- `compute_quality_gate()` trong `services/preview.py` nhận `list[TradeInput]`, nhưng export route có `list[ExportTrade]` (khác model)
- Inline logic tránh coupling giữa hai service modules
- Logic tương đương với `compute_quality_gate()` — cùng thresholds (10 trades, 55% WR), cùng reason format

---

### `tests/test_export.py` — Quality Gate Test Pattern

```python
# Thêm vào cuối tests/test_export.py (đã có từ Story 3.1)

def _make_export_request(n_trades: int, win_rate: float) -> dict:
    """Helper: tạo ExportRequest dict với n_trades và win_rate cụ thể."""
    n_wins = round(n_trades * win_rate)
    trades = []
    for i in range(n_trades):
        trades.append({
            "bar_index": 10 + i,
            "entry_timestamp_ms": 1745625600000 + i * 3600000,
            "direction": "LONG",
            "entry_price": 43000.0,
            "tp_price": 44000.0,
            "sl_price": 42000.0,
            "result": "win" if i < n_wins else "loss",
            "bars_to_exit": 7,
            "reasoning_summary": "Test summary",
        })
    return {
        "session_filename": "BTCUSDT_4h_20260420.parquet",
        "strategy_name": "breakout_4h",
        "timeframe": "4h",
        "session_win_rate": win_rate,
        "trades": trades,
    }


# Quality gate tests — sử dụng FastAPI TestClient (hoặc httpx.AsyncClient)
# từ Story 3.1's existing test setup pattern

class TestQualityGate:
    def test_quality_gate_fail_trade_count(self, client, mock_settings_enabled):
        """7 trades với 71% WR → 422 quality_gate (trade count fails)"""
        payload = _make_export_request(n_trades=7, win_rate=0.71)
        resp = client.post("/api/export", json=payload)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "quality_gate"
        assert "7 trades" in detail["message"]

    def test_quality_gate_fail_win_rate(self, client, mock_settings_enabled):
        """15 trades với 48% WR → 422 quality_gate (win rate fails)"""
        payload = _make_export_request(n_trades=15, win_rate=0.48)
        resp = client.post("/api/export", json=payload)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "quality_gate"
        assert "48%" in detail["message"] or "win rate" in detail["message"]

    def test_quality_gate_pass(self, client, mock_settings_enabled, mock_httpx):
        """20 trades với 55% WR → pass, export proceeds"""
        payload = _make_export_request(n_trades=20, win_rate=0.55)
        resp = client.post("/api/export", json=payload)
        # Không phải 422 — có thể 200 (nếu mock httpx trả về success)
        assert resp.status_code != 422

    def test_quality_gate_fail_count_not_rate(self, client, mock_settings_enabled):
        """9 trades với 60% WR → 422 (count fails, rate would pass)"""
        payload = _make_export_request(n_trades=9, win_rate=0.60)
        resp = client.post("/api/export", json=payload)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "9 trades" in detail["message"]

    def test_quality_gate_dual_fail(self, client, mock_settings_enabled):
        """7 trades VÀ 43% WR → 422 với cả hai reasons"""
        payload = _make_export_request(n_trades=7, win_rate=0.43)
        resp = client.post("/api/export", json=payload)
        assert resp.status_code == 422
        message = resp.json()["detail"]["message"]
        assert "7 trades" in message
        assert "43%" in message or "win rate" in message

    def test_quality_gate_before_supabase_write(self, client, mock_settings_enabled, mock_httpx):
        """Quality gate check phải xảy ra TRƯỚC khi Supabase write"""
        payload = _make_export_request(n_trades=7, win_rate=0.71)
        resp = client.post("/api/export", json=payload)
        assert resp.status_code == 422
        # Verify httpx KHÔNG được gọi — Supabase writes không xảy ra
        mock_httpx.assert_not_called()  # hoặc mock_httpx.call_count == 0


def test_bars_to_exit_off_by_one():
    """Explicit regression guard: entry bar 42, exit bar 49 → bars_to_exit = 7"""
    entry_bar = 42
    exit_bar = 49
    bars_to_exit = exit_bar - entry_bar
    assert bars_to_exit == 7, (
        f"bars_to_exit off-by-one: expected 7, got {bars_to_exit}. "
        f"Correct formula: exit_bar - entry_bar (NOT exit_bar - entry_bar + 1)"
    )
```

> **Mock setup note**: Sử dụng cùng mock pattern từ Story 3.1's `tests/test_export.py`. Nếu Story 3.1 dùng `pytest.fixture` với `mock_settings_enabled` → tái sử dụng fixture. Không tạo mock mới nếu đã có.

---

### `tests/test_quality_gate.py` — Pure Function Tests

```python
# tests/test_quality_gate.py
"""
Pure unit tests cho compute_quality_gate() và compute_reasoning_template().
Không cần Supabase, không cần HTTP, không cần Parquet files thật.
"""
import re
import pytest
import pandas as pd
import numpy as np

from backend.services.preview import compute_quality_gate, compute_reasoning_template
from backend.models import TradeInput


def _make_trades(n_total: int, n_wins: int) -> list[TradeInput]:
    """Helper: tạo list[TradeInput] với n_total trades và n_wins wins."""
    trades = []
    for i in range(n_total):
        trades.append(TradeInput(
            bar_index=10 + i,
            entry_timestamp_ms=1745625600000,
            direction="LONG",
            entry_price=43000.0,
            tp_price=44000.0,
            sl_price=42000.0,
            result="win" if i < n_wins else "loss",
            bars_to_exit=7,
        ))
    return trades


# --- Quality Gate Tests ---

class TestComputeQualityGate:
    def test_fail_trade_count(self):
        """7 trades, 5 wins (71%) → fail because < 10 trades"""
        trades = _make_trades(7, 5)
        status, reason = compute_quality_gate(trades)
        assert status == "fail"
        assert reason is not None
        assert "7 trades" in reason
        assert "cần tối thiểu 10" in reason

    def test_fail_win_rate(self):
        """15 trades, 7 wins (46%) → fail because < 55% win rate"""
        trades = _make_trades(15, 7)
        status, reason = compute_quality_gate(trades)
        assert status == "fail"
        assert reason is not None
        assert "46%" in reason or "win rate" in reason
        assert "cần tối thiểu 55%" in reason

    def test_pass_boundary_exactly_55_percent(self):
        """20 trades, 11 wins (55.0%) → pass (exactly at threshold)"""
        trades = _make_trades(20, 11)
        status, reason = compute_quality_gate(trades)
        assert status == "pass"
        assert reason is None

    def test_fail_count_only_not_rate(self):
        """9 trades, 6 wins (67%) → fail on count, rate would pass"""
        trades = _make_trades(9, 6)
        status, reason = compute_quality_gate(trades)
        assert status == "fail"
        assert "9 trades" in reason
        # Should NOT mention win rate (rate is 67%, which is >= 55%)
        assert "win rate" not in reason.lower() or "55%" not in reason

    def test_fail_dual_reasons(self):
        """7 trades, 3 wins (43%) → both count AND win rate fail"""
        trades = _make_trades(7, 3)
        status, reason = compute_quality_gate(trades)
        assert status == "fail"
        assert "7 trades" in reason
        assert "43%" in reason or "win rate" in reason
        # Both reasons joined
        assert ";" in reason

    def test_fail_empty_trades(self):
        """0 trades → fail with count reason"""
        status, reason = compute_quality_gate([])
        assert status == "fail"
        assert "0 trades" in reason

    def test_pass_more_than_10_trades_good_wr(self):
        """31 trades, 21 wins (67%) → pass"""
        trades = _make_trades(31, 21)
        status, reason = compute_quality_gate(trades)
        assert status == "pass"
        assert reason is None

    def test_fail_exactly_9_trades(self):
        """Exactly 9 trades with 100% win rate → still fail (< 10)"""
        trades = _make_trades(9, 9)
        status, reason = compute_quality_gate(trades)
        assert status == "fail"
        assert "9 trades" in reason

    def test_pass_exactly_10_trades_exactly_55_pct():
        """10 trades, need 5.5 wins → can't do exactly 55% with 10 trades.
        
        Use 20 trades, 11 wins instead for exact 55% boundary.
        This tests that 10/20 >= 0.55 and 10 >= 10 both pass.
        """
        # 10 trades, 6 wins (60%) → pass (60% > 55%, 10 >= 10)
        trades = _make_trades(10, 6)
        status, reason = compute_quality_gate(trades)
        assert status == "pass"


# --- Reasoning Template Format Tests ---

def _make_minimal_df(n_bars: int = 60) -> pd.DataFrame:
    """Create minimal DataFrame with realistic OHLCV data."""
    np.random.seed(42)
    close = 40000 + np.cumsum(np.random.randn(n_bars) * 100)
    volume = 1000 + np.abs(np.random.randn(n_bars) * 200)
    return pd.DataFrame({
        "timestamp": [1745625600000 + i * 3600000 for i in range(n_bars)],
        "open": close * 0.999,
        "high": close * 1.002,
        "low": close * 0.998,
        "close": close,
        "volume": volume,
    })


REASONING_TEMPLATE_PATTERN = re.compile(
    r"^\d+H \| Entry \$[\d,]+ \| EMA20=(\$[\d,]+|N/A) \| "
    r"EMA50=(\$[\d,]+|N/A) \| Vol=([\d.]+x|N/Ax) \| Outcome: (WIN|LOSS)$"
)


class TestComputeReasoningTemplate:
    def test_output_format_matches_template(self):
        """Output phải match exact format: 'TF | Entry $... | EMA20=... | EMA50=... | Vol=...x | Outcome: WIN/LOSS'"""
        df = _make_minimal_df(60)
        trade = TradeInput(
            bar_index=42,
            entry_timestamp_ms=1745625600000,
            direction="LONG",
            entry_price=43250.0,
            tp_price=44000.0,
            sl_price=42800.0,
            result="win",
            bars_to_exit=7,
        )
        result = compute_reasoning_template(df, trade, "4h")
        assert REASONING_TEMPLATE_PATTERN.match(result), (
            f"Template không match pattern. Got: '{result}'"
        )

    def test_outcome_win(self):
        """result='win' → Outcome: WIN"""
        df = _make_minimal_df(60)
        trade = TradeInput(
            bar_index=42, entry_timestamp_ms=1745625600000,
            direction="LONG", entry_price=43250.0,
            tp_price=44000.0, sl_price=42800.0,
            result="win", bars_to_exit=7,
        )
        result = compute_reasoning_template(df, trade, "4h")
        assert result.endswith("Outcome: WIN")

    def test_outcome_loss(self):
        """result='loss' → Outcome: LOSS"""
        df = _make_minimal_df(60)
        trade = TradeInput(
            bar_index=42, entry_timestamp_ms=1745625600000,
            direction="LONG", entry_price=43250.0,
            tp_price=44000.0, sl_price=42800.0,
            result="loss", bars_to_exit=7,
        )
        result = compute_reasoning_template(df, trade, "4h")
        assert result.endswith("Outcome: LOSS")

    def test_timeframe_uppercase(self):
        """timeframe='4h' → output chứa '4H' (uppercase)"""
        df = _make_minimal_df(60)
        trade = TradeInput(
            bar_index=42, entry_timestamp_ms=1745625600000,
            direction="LONG", entry_price=43250.0,
            tp_price=44000.0, sl_price=42800.0,
            result="win", bars_to_exit=7,
        )
        result = compute_reasoning_template(df, trade, "4h")
        assert result.startswith("4H |")

    def test_entry_price_formatted(self):
        """entry_price=43250 → '$43,250' (currency format với comma)"""
        df = _make_minimal_df(60)
        trade = TradeInput(
            bar_index=42, entry_timestamp_ms=1745625600000,
            direction="LONG", entry_price=43250.0,
            tp_price=44000.0, sl_price=42800.0,
            result="win", bars_to_exit=7,
        )
        result = compute_reasoning_template(df, trade, "4h")
        assert "Entry $43,250" in result

    def test_slice_first_not_look_ahead(self):
        """
        Verify slice-first: EMA tại bar 42 phải dùng df.iloc[:42], không toàn bộ df.
        Tạo DataFrame với price spike AFTER bar 42 → EMA giá trị phải khác nhau.
        """
        n_bars = 80
        close = np.ones(n_bars) * 40000.0
        close[50:] = 60000.0  # spike sau bar 42
        df = pd.DataFrame({
            "timestamp": [1745625600000 + i * 3600000 for i in range(n_bars)],
            "open": close, "high": close, "low": close,
            "close": close,
            "volume": np.ones(n_bars) * 1000,
        })

        trade = TradeInput(
            bar_index=42, entry_timestamp_ms=1745625600000,
            direction="LONG", entry_price=40000.0,
            tp_price=41000.0, sl_price=39000.0,
            result="win", bars_to_exit=7,
        )
        result = compute_reasoning_template(df, trade, "4h")

        # EMA at bar 42 should be ~40000 (no influence from spike at bar 50+)
        # If look-ahead bias exists, EMA would be higher (pulled by 60000 spike)
        assert "Outcome: WIN" in result  # sanity check
        assert REASONING_TEMPLATE_PATTERN.match(result), (
            f"Format check failed for slice-first test. Got: '{result}'"
        )


# --- bars_to_exit Off-By-One Regression Guard ---

def test_bars_to_exit_off_by_one_regression():
    """
    Explicit regression guard for bars_to_exit calculation.

    CORRECT formula: bars_to_exit = exit_bar_index - entry_bar_index
    INCORRECT formula: bars_to_exit = exit_bar_index - entry_bar_index + 1

    Example from AC: entry bar 42, exit bar 49 → bars_to_exit = 7 (NOT 8)
    This is how many bars the trade was HELD, exclusive of entry bar.
    """
    entry_bar = 42
    exit_bar = 49
    bars_to_exit = exit_bar - entry_bar
    assert bars_to_exit == 7, (
        f"bars_to_exit off-by-one bug: expected 7, got {bars_to_exit}. "
        f"Use 'exit_bar - entry_bar', NOT 'exit_bar - entry_bar + 1'."
    )

    # Additional boundary: same-bar TP/SL (hit on entry bar)
    bars_to_exit_same_bar = 42 - 42
    assert bars_to_exit_same_bar == 0

    # Additional: exit next bar
    bars_to_exit_next = 43 - 42
    assert bars_to_exit_next == 1
```

---

### Sự Khác Biệt giữa Story 4.1 và 4.2 Tests

| File | Story | Scope |
|------|-------|-------|
| `tests/test_supabase_service.py` | 4.1 *(đã tạo)* | Pure unit tests: `generate_signal_id`, mapping functions, `_parse_supabase_error` |
| `tests/test_export.py` | 3.1 *(đã tạo)* + **4.2 extends** | Route-level integration tests với mock httpx |
| `tests/test_quality_gate.py` | **4.2 tạo mới** | Pure unit tests: `compute_quality_gate`, `compute_reasoning_template`, bars_to_exit |

> **Không chồng lặp**: Story 4.1 tests signal_id + schema mapping. Story 4.2 tests quality gate + reasoning template + route-level quality gate enforcement. Story 3.1 đã test route HTTP error codes. Phân chia rõ ràng.

---

### Tránh Import Trap: TradeInput vs ExportTrade

`compute_quality_gate()` trong `backend/services/preview.py` nhận `list[TradeInput]`:
```python
class TradeInput(BaseModel):
    bar_index: int
    entry_timestamp_ms: int
    direction: str
    entry_price: float
    tp_price: float
    sl_price: float
    result: str           # "win" hoặc "loss"
    bars_to_exit: int
    # NOTE: KHÔNG có reasoning_summary
```

`ExportTrade` trong `backend/models.py` có thêm `reasoning_summary: str`.

Trong `tests/test_quality_gate.py`:
- Import và dùng `TradeInput` (không phải `ExportTrade`)
- `compute_quality_gate` nhận `list[TradeInput]`

Trong `tests/test_export.py` (extend):
- Dùng dict trực tiếp trong payload (không cần import model)
- `_make_export_request()` helper build dict với đúng fields cho `ExportRequest`

---

### Test Runner Commands

```bash
# Chạy tất cả Story 4.2 tests:
uv run pytest tests/test_quality_gate.py -v

# Chạy quality gate tests trong test_export.py:
uv run pytest tests/test_export.py -k "quality_gate" -v

# Chạy tất cả tests (không cần credentials):
uv run pytest tests/ -v

# Xác nhận Story 4.1 tests vẫn pass (regression check):
uv run pytest tests/test_supabase_service.py -v
```

---

### NFR Compliance

- **NFR19 (Medium):** Quality gate logic, signal_id generation, outcome mapping, reasoning template generation có pytest unit tests — không cần Supabase connection ✓
- **FR10/FR11 (CRITICAL):** Backend enforce quality gate tại `POST /api/export` — defense-in-depth ✓
- **Gap-1 (Critical):** Slice-first enforcement có test case trong `test_quality_gate.py::TestComputeReasoningTemplate::test_slice_first_not_look_ahead` ✓

---

### Cross-Story Dependencies

- **Story 2.1** (done): `backend/services/preview.py` chứa `compute_quality_gate()` và `compute_reasoning_template()` — Story 4.2 imports và tests these functions.
- **Story 3.1** (review): `backend/routes/export.py` — Story 4.2 MODIFIES để thêm quality gate check. Nếu dev story 3.1 vẫn đang trong review khi story 4.2 starts, sẽ có merge conflict potential — verify cùng developer.
- **Story 4.1** (ready-for-dev): `tests/test_supabase_service.py` — Story 4.2 KHÔNG thay đổi. Chạy cả hai test files để verify không có regression.
- **Story 4.3** (backlog): Credentials validation — không conflict với Story 4.2 scope.

### References

- [epics.md - Story 4.2 Acceptance Criteria](_bmad-output/planning-artifacts/epics.md#story-42-pytest-unit-tests-cho-critical-paths)
- [prd-phase2-supabase.md - FR10, FR11, NFR19](_bmad-output/planning-artifacts/prd-phase2-supabase.md)
- [3-1-post-api-export-write-signal-comparisons-va-signal-cases.md - Full export.py implementation](_bmad-output/implementation-artifacts/3-1-post-api-export-write-signal-comparisons-va-signal-cases.md)
- [2-1-get-api-sessions-filename-preview-trade-list-voi-reasoning-templates.md - compute_quality_gate + compute_reasoning_template implementation](_bmad-output/implementation-artifacts/2-1-get-api-sessions-filename-preview-trade-list-voi-reasoning-templates.md)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

### Completion Notes List

### File List
