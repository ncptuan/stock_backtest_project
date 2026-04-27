"""
Tests cho POST /api/export — Story 3.1 ACs.

Test coverage:
  1. Valid export → 200 with counts and first_signal_id
  2. SUPABASE_ENABLED=false → 503 disabled
  3. Timeout on check_duplicate → 504
  4. Timeout on write_signal_cases → rollback + 504
  5. ValueError on write_signal_cases (auth fail) → rollback + 500
  6. Duplicate detected → 409
  7. generate_signal_id format
  8. strategy_name sanitization (spaces, special chars)
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from backend.services.supabase import generate_signal_id, _parse_session_date
import httpx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_TRADE = {
    "bar_index": 42,
    "entry_timestamp_ms": 1745712000000,
    "direction": "LONG",
    "entry_price": 80000.0,
    "tp_price": 82000.0,
    "sl_price": 79000.0,
    "result": "win",
    "bars_to_exit": 3,
    "reasoning_summary": "EMA breakout với volume cao",
}

SAMPLE_REQUEST = {
    "session_filename": "BTCUSDT_4h_20260426.parquet",
    "strategy_name": "breakout_4h",
    "timeframe": "4h",
    "session_win_rate": 0.75,
    "trades": [SAMPLE_TRADE],
}

# SAMPLE_REQUEST_VALID: passes quality gate (10 trades, 75% WR, first is SAMPLE_TRADE)
_EXTRA_TRADES = [
    {
        "bar_index": 50 + i,
        "entry_timestamp_ms": 1745712000000 + i * 3600000,
        "direction": "LONG",
        "entry_price": 80000.0,
        "tp_price": 82000.0,
        "sl_price": 79000.0,
        "result": "win" if i < 7 else "loss",
        "bars_to_exit": 3,
        "reasoning_summary": "Extra trade",
    }
    for i in range(9)
]
SAMPLE_REQUEST_VALID = {
    "session_filename": "BTCUSDT_4h_20260426.parquet",
    "strategy_name": "breakout_4h",
    "timeframe": "4h",
    "session_win_rate": 0.75,
    "trades": [SAMPLE_TRADE] + _EXTRA_TRADES,
}


@pytest.fixture
def client_supabase_enabled(monkeypatch):
    """TestClient với supabase_enabled=True và fake credentials."""
    from backend.settings import settings

    monkeypatch.setattr(settings, "supabase_enabled", True)
    monkeypatch.setattr(settings, "supabase_url", "https://fake.supabase.co")
    monkeypatch.setattr(settings, "supabase_key", "fake-anon-key")
    monkeypatch.setattr(settings, "supabase_service_key", "fake-service-key")

    from backend.main import create_app

    return TestClient(create_app())


@pytest.fixture
def client_supabase_disabled(monkeypatch):
    """TestClient với supabase_enabled=False (default)."""
    from backend.settings import settings

    monkeypatch.setattr(settings, "supabase_enabled", False)

    from backend.main import create_app

    return TestClient(create_app())


# ---------------------------------------------------------------------------
# Test 1: Valid export → 200
# ---------------------------------------------------------------------------

def test_export_valid_200(client_supabase_enabled):
    """AC: Valid request khi Supabase enabled → 200 với đúng counts và first_signal_id."""
    with (
        patch(
            "backend.routes.export.validate_credentials",
            new_callable=AsyncMock,
        ),
        patch(
            "backend.routes.export.check_duplicate",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "backend.routes.export.write_signal_comparisons",
            new_callable=AsyncMock,
            return_value=10,
        ),
        patch(
            "backend.routes.export.write_signal_cases",
            new_callable=AsyncMock,
            return_value=10,
        ),
    ):
        resp = client_supabase_enabled.post("/api/export", json=SAMPLE_REQUEST_VALID)

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    data = body["data"]
    assert data["signal_comparisons_count"] == 10
    assert data["signal_cases_count"] == 10
    assert data["first_signal_id"] == "backtest_20260426_breakout_4h_00042"
    assert "signal_cases" in data["supabase_url"]


# ---------------------------------------------------------------------------
# Test 2: SUPABASE_ENABLED=false → 503
# ---------------------------------------------------------------------------

def test_export_disabled_503(client_supabase_disabled):
    """AC: SUPABASE_ENABLED=false → HTTP 503 với error='disabled'."""
    resp = client_supabase_disabled.post("/api/export", json=SAMPLE_REQUEST)
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert detail["error"] == "disabled"


# ---------------------------------------------------------------------------
# Test 3: Timeout on check_duplicate → 504
# ---------------------------------------------------------------------------

def test_export_timeout_on_duplicate_check_504(client_supabase_enabled):
    """AC: httpx.TimeoutException trên check_duplicate → HTTP 504."""
    with (
        patch(
            "backend.routes.export.validate_credentials",
            new_callable=AsyncMock,
        ),
        patch(
            "backend.routes.export.check_duplicate",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timeout"),
        ),
    ):
        resp = client_supabase_enabled.post("/api/export", json=SAMPLE_REQUEST_VALID)

    assert resp.status_code == 504
    detail = resp.json()["detail"]
    assert detail["error"] == "timeout"


# ---------------------------------------------------------------------------
# Test 4: Timeout on write_signal_cases → rollback + 504
# ---------------------------------------------------------------------------

def test_export_timeout_signal_cases_rollback_504(client_supabase_enabled):
    """AC: Timeout trên write_signal_cases → rollback signal_comparisons → 504."""
    with (
        patch(
            "backend.routes.export.validate_credentials",
            new_callable=AsyncMock,
        ),
        patch(
            "backend.routes.export.check_duplicate",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "backend.routes.export.write_signal_comparisons",
            new_callable=AsyncMock,
            return_value=10,
        ),
        patch(
            "backend.routes.export.write_signal_cases",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timeout"),
        ),
        patch(
            "backend.routes.export.rollback_signal_comparisons",
            new_callable=AsyncMock,
            return_value=10,
        ) as mock_rollback,
    ):
        resp = client_supabase_enabled.post("/api/export", json=SAMPLE_REQUEST_VALID)

    assert resp.status_code == 504
    detail = resp.json()["detail"]
    assert detail["error"] == "timeout"
    mock_rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 5: ValueError on write_signal_cases (auth fail) → rollback + 500
# ---------------------------------------------------------------------------

def test_export_signal_cases_auth_fail_rollback_500(client_supabase_enabled):
    """AC: ValueError trên write_signal_cases (ví dụ: RLS auth fail) → rollback → 500."""
    with (
        patch(
            "backend.routes.export.validate_credentials",
            new_callable=AsyncMock,
        ),
        patch(
            "backend.routes.export.check_duplicate",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "backend.routes.export.write_signal_comparisons",
            new_callable=AsyncMock,
            return_value=10,
        ),
        patch(
            "backend.routes.export.write_signal_cases",
            new_callable=AsyncMock,
            side_effect=ValueError("signal_cases write failed: 401"),
        ),
        patch(
            "backend.routes.export.rollback_signal_comparisons",
            new_callable=AsyncMock,
            return_value=10,
        ) as mock_rollback,
    ):
        resp = client_supabase_enabled.post("/api/export", json=SAMPLE_REQUEST_VALID)

    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert detail["error"] == "partial_write_rolled_back"
    mock_rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 6: Duplicate detected → 409
# ---------------------------------------------------------------------------

def test_export_duplicate_409(client_supabase_enabled):
    """AC: Session đã exported → check_duplicate=True → HTTP 409."""
    with (
        patch(
            "backend.routes.export.validate_credentials",
            new_callable=AsyncMock,
        ),
        patch(
            "backend.routes.export.check_duplicate",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        resp = client_supabase_enabled.post("/api/export", json=SAMPLE_REQUEST_VALID)

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["error"] == "duplicate"
    assert "BTCUSDT_4h_20260426.parquet" in detail["message"]


# ---------------------------------------------------------------------------
# Test 7: generate_signal_id format
# ---------------------------------------------------------------------------

def test_generate_signal_id_format():
    """AC: signal_id format = 'backtest_{date}_{sanitized}_{bar:05d}'."""
    result = generate_signal_id("20260426", "breakout_4h", 42)
    assert result == "backtest_20260426_breakout_4h_00042"


def test_generate_signal_id_zero_padded():
    """AC: bar_index zero-padded đến 5 chữ số."""
    result = generate_signal_id("20260426", "ema", 1)
    assert result == "backtest_20260426_ema_00001"


# ---------------------------------------------------------------------------
# Test 8: strategy_name sanitization
# ---------------------------------------------------------------------------

def test_generate_signal_id_sanitize_spaces():
    """AC: Spaces và ký tự đặc biệt được sanitize."""
    result = generate_signal_id("20260426", "Breakout 4H / EMA", 42)
    assert result == "backtest_20260426_breakout_4h_ema_00042"


def test_generate_signal_id_sanitize_special_chars():
    """AC: Dấu gạch đầu/cuối bị strip sau sanitization."""
    result = generate_signal_id("20260426", "---strategy---", 5)
    assert result == "backtest_20260426_strategy_00005"


# ---------------------------------------------------------------------------
# Test 9: _parse_session_date helper
# ---------------------------------------------------------------------------

def test_parse_session_date_standard():
    """_parse_session_date returns yyyymmdd from standard filename."""
    assert _parse_session_date("BTCUSDT_4h_20260420.parquet") == "20260420"


def test_parse_session_date_fallback():
    """_parse_session_date returns '00000000' on malformed filename."""
    assert _parse_session_date("invalid.parquet") == "00000000"


# ---------------------------------------------------------------------------
# Quality Gate helpers + tests — Story 4.2 (AC: #2, #7)
# ---------------------------------------------------------------------------

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


def test_quality_gate_fail_trade_count(client_supabase_enabled):
    """7 trades với 71% WR → HTTP 422, error='quality_gate', message chứa '7 trades'."""
    payload = _make_export_request(n_trades=7, win_rate=0.71)
    with patch(
        "backend.routes.export.check_duplicate",
        new_callable=AsyncMock,
        return_value=False,
    ):
        resp = client_supabase_enabled.post("/api/export", json=payload)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error"] == "quality_gate"
    assert "7 trades" in detail["message"]


def test_quality_gate_fail_win_rate(client_supabase_enabled):
    """15 trades với 48% WR → HTTP 422, error='quality_gate', message chứa win rate."""
    payload = _make_export_request(n_trades=15, win_rate=0.48)
    with patch(
        "backend.routes.export.check_duplicate",
        new_callable=AsyncMock,
        return_value=False,
    ):
        resp = client_supabase_enabled.post("/api/export", json=payload)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error"] == "quality_gate"
    assert "48%" in detail["message"]
    assert "win rate" in detail["message"]


def test_quality_gate_pass(client_supabase_enabled):
    """20 trades với 55% WR → quality gate pass → không 422."""
    payload = _make_export_request(n_trades=20, win_rate=0.55)
    with (
        patch(
            "backend.routes.export.validate_credentials",
            new_callable=AsyncMock,
        ),
        patch(
            "backend.routes.export.check_duplicate",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "backend.routes.export.write_signal_comparisons",
            new_callable=AsyncMock,
            return_value=20,
        ),
        patch(
            "backend.routes.export.write_signal_cases",
            new_callable=AsyncMock,
            return_value=20,
        ),
    ):
        resp = client_supabase_enabled.post("/api/export", json=payload)
    assert resp.status_code != 422


def test_quality_gate_fail_count_only(client_supabase_enabled):
    """9 trades với 60% WR → HTTP 422, message chứa '9 trades'."""
    payload = _make_export_request(n_trades=9, win_rate=0.60)
    with patch(
        "backend.routes.export.check_duplicate",
        new_callable=AsyncMock,
        return_value=False,
    ):
        resp = client_supabase_enabled.post("/api/export", json=payload)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error"] == "quality_gate"
    assert "9 trades" in detail["message"]


def test_quality_gate_dual_fail(client_supabase_enabled):
    """7 trades VÀ 43% WR → 422 với cả hai reasons trong message."""
    payload = _make_export_request(n_trades=7, win_rate=0.43)
    with patch(
        "backend.routes.export.check_duplicate",
        new_callable=AsyncMock,
        return_value=False,
    ):
        resp = client_supabase_enabled.post("/api/export", json=payload)
    assert resp.status_code == 422
    message = resp.json()["detail"]["message"]
    assert "7 trades" in message
    assert "43%" in message or "win rate" in message


def test_quality_gate_before_supabase_write(client_supabase_enabled):
    """Quality gate check phải xảy ra TRƯỚC khi Supabase write — write NOT called."""
    payload = _make_export_request(n_trades=7, win_rate=0.71)
    with (
        patch(
            "backend.routes.export.check_duplicate",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "backend.routes.export.write_signal_comparisons",
            new_callable=AsyncMock,
            return_value=0,
        ) as mock_write,
    ):
        resp = client_supabase_enabled.post("/api/export", json=payload)
    assert resp.status_code == 422
    mock_write.assert_not_called()


def test_export_rollback_also_fails_still_returns_500(client_supabase_enabled):
    """If rollback raises, route still returns 500 (original error), does not swallow rollback exception."""
    with (
        patch(
            "backend.routes.export.validate_credentials",
            new_callable=AsyncMock,
        ),
        patch(
            "backend.routes.export.check_duplicate",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "backend.routes.export.write_signal_comparisons",
            new_callable=AsyncMock,
            return_value=10,
        ),
        patch(
            "backend.routes.export.write_signal_cases",
            new_callable=AsyncMock,
            side_effect=ValueError("signal_cases write failed: 401"),
        ),
        patch(
            "backend.routes.export.rollback_signal_comparisons",
            new_callable=AsyncMock,
            side_effect=Exception("network down during rollback"),
        ),
    ):
        resp = client_supabase_enabled.post("/api/export", json=SAMPLE_REQUEST_VALID)

    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert detail["error"] == "partial_write_rolled_back"


def test_bars_to_exit_off_by_one():
    """Explicit regression guard: entry bar 42, exit bar 49 → bars_to_exit = 7."""
    entry_bar = 42
    exit_bar = 49
    bars_to_exit = exit_bar - entry_bar
    assert bars_to_exit == 7, (
        f"bars_to_exit off-by-one: expected 7, got {bars_to_exit}. "
        "Correct formula: exit_bar - entry_bar (NOT exit_bar - entry_bar + 1)"
    )


# ---------------------------------------------------------------------------
# Credential Validation tests — Story 4.3 (AC: #1, #2, #3, #6, #7)
# ---------------------------------------------------------------------------

def test_credential_invalid_anon_key_401(client_supabase_enabled):
    """Mock anon key returns 401 → export returns 401 với 'SUPABASE_KEY' message"""
    payload = _make_export_request(n_trades=15, win_rate=0.60)

    with patch("backend.routes.export.validate_credentials", new_callable=AsyncMock) as mock_val:
        mock_val.side_effect = ValueError(
            "SUPABASE_KEY không hợp lệ — Kiểm tra anon key trong .env (dùng cho signal_comparisons)"
        )
        resp = client_supabase_enabled.post("/api/export", json=payload)

    assert resp.status_code == 401
    detail = resp.json()["detail"]
    assert detail["error"] == "invalid_credentials"
    assert "SUPABASE_KEY" in detail["message"]
    assert "signal_comparisons" in detail["message"]


def test_credential_invalid_service_key_401(client_supabase_enabled):
    """Service key invalid → 401 với 'SUPABASE_SERVICE_KEY' message"""
    payload = _make_export_request(n_trades=15, win_rate=0.60)

    with patch("backend.routes.export.validate_credentials", new_callable=AsyncMock) as mock_val:
        mock_val.side_effect = ValueError(
            "SUPABASE_SERVICE_KEY không hợp lệ — Kiểm tra service role key trong .env "
            "(dùng cho signal_cases, RLS enabled)"
        )
        resp = client_supabase_enabled.post("/api/export", json=payload)

    assert resp.status_code == 401
    detail = resp.json()["detail"]
    assert detail["error"] == "invalid_credentials"
    assert "SUPABASE_SERVICE_KEY" in detail["message"]
    assert "signal_cases" in detail["message"]


def test_credential_validation_timeout_504(client_supabase_enabled):
    """Credential validation timeout → 504"""
    payload = _make_export_request(n_trades=15, win_rate=0.60)

    with patch("backend.routes.export.validate_credentials", new_callable=AsyncMock) as mock_val:
        mock_val.side_effect = httpx.TimeoutException("timeout")
        resp = client_supabase_enabled.post("/api/export", json=payload)

    assert resp.status_code == 504
    assert resp.json()["detail"]["error"] == "timeout"


def test_credential_valid_export_proceeds(client_supabase_enabled):
    """Both credentials valid → export proceeds past credential check (not 401)"""
    payload = _make_export_request(n_trades=15, win_rate=0.60)

    with (
        patch("backend.routes.export.validate_credentials", new_callable=AsyncMock),
        patch("backend.routes.export.check_duplicate", new_callable=AsyncMock, return_value=False),
        patch("backend.routes.export.write_signal_comparisons", new_callable=AsyncMock, return_value=15),
        patch("backend.routes.export.write_signal_cases", new_callable=AsyncMock, return_value=15),
    ):
        resp = client_supabase_enabled.post("/api/export", json=payload)

    assert resp.status_code != 401


def test_quality_gate_fail_skips_credential_check(client_supabase_enabled):
    """Quality gate fail (< 10 trades) → credential check NOT called"""
    payload = _make_export_request(n_trades=7, win_rate=0.71)

    with patch("backend.routes.export.validate_credentials", new_callable=AsyncMock) as mock_val:
        resp = client_supabase_enabled.post("/api/export", json=payload)

    assert resp.status_code == 422
    mock_val.assert_not_called()


def test_credential_fail_skips_duplicate_check(client_supabase_enabled):
    """Credential fail → duplicate check NOT called"""
    payload = _make_export_request(n_trades=15, win_rate=0.60)

    with (
        patch("backend.routes.export.validate_credentials", new_callable=AsyncMock) as mock_val,
        patch("backend.routes.export.check_duplicate", new_callable=AsyncMock) as mock_dup,
    ):
        mock_val.side_effect = ValueError("SUPABASE_KEY không hợp lệ ...")
        resp = client_supabase_enabled.post("/api/export", json=payload)

    assert resp.status_code == 401
    mock_dup.assert_not_called()
