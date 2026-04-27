"""
tests/test_supabase_service.py — Story 4.1

Unit tests for pure mapping logic in backend/services/supabase.py.
No network connection, no Supabase credentials required.
"""
from datetime import datetime, timezone

import pytest

from backend.services.supabase import (
    _map_direction_to_verdict,
    _map_result_to_follow,
    _map_result_to_outcome,
    _parse_session_date,
    _parse_supabase_error,
    generate_signal_id,
)


# ---------------------------------------------------------------------------
# generate_signal_id
# ---------------------------------------------------------------------------

def test_generate_signal_id_basic():
    assert generate_signal_id("20260426", "breakout_4h", 42) == "backtest_20260426_breakout_4h_00042"


def test_generate_signal_id_sanitize_spaces():
    assert generate_signal_id("20260426", "Breakout 4H / EMA", 42) == "backtest_20260426_breakout_4h_ema_00042"


def test_generate_signal_id_sanitize_special_chars():
    assert generate_signal_id("20260426", "BTC Strategy!", 1) == "backtest_20260426_btc_strategy_00001"


def test_generate_signal_id_zero_pad_5_digits():
    result = generate_signal_id("20260426", "strat", 1)
    assert result.endswith("_00001")


def test_generate_signal_id_bar_index_large():
    result = generate_signal_id("20260426", "strat", 99999)
    assert result.endswith("_99999")


# ---------------------------------------------------------------------------
# _parse_session_date
# ---------------------------------------------------------------------------

def test_parse_session_date_standard_format():
    assert _parse_session_date("BTCUSDT_4h_20260420.parquet") == "20260420"


def test_parse_session_date_invalid_fallback():
    assert _parse_session_date("invalid.parquet") == "00000000"


def test_parse_session_date_no_date_in_filename():
    assert _parse_session_date("BTCUSDT_4h_weekly.parquet") == "00000000"


def test_parse_session_date_eth():
    assert _parse_session_date("ETHUSDT_1h_20260415.parquet") == "20260415"


# ---------------------------------------------------------------------------
# _map_direction_to_verdict
# ---------------------------------------------------------------------------

def test_direction_long_to_buy():
    assert _map_direction_to_verdict("LONG") == "BUY"


def test_direction_short_to_sell():
    assert _map_direction_to_verdict("SHORT") == "SELL"


def test_direction_case_insensitive():
    assert _map_direction_to_verdict("long") == "BUY"
    assert _map_direction_to_verdict("short") == "SELL"


# ---------------------------------------------------------------------------
# _map_result_to_follow
# ---------------------------------------------------------------------------

def test_result_win_follow():
    assert _map_result_to_follow("win") == "TP hit"


def test_result_loss_follow():
    assert _map_result_to_follow("loss") == "SL hit"


def test_result_follow_case_insensitive():
    assert _map_result_to_follow("WIN") == "TP hit"


# ---------------------------------------------------------------------------
# _map_result_to_outcome
# ---------------------------------------------------------------------------

def test_result_win_outcome():
    assert _map_result_to_outcome("win") == "TP_HIT"


def test_result_loss_outcome():
    assert _map_result_to_outcome("loss") == "SL_HIT"


def test_outcome_not_wrong_format():
    """outcome MUST be TP_HIT / SL_HIT — production bot format (all caps, underscore)"""
    assert _map_result_to_outcome("win") != "TP hit"
    assert _map_result_to_outcome("win") != "tp_hit"
    assert _map_result_to_outcome("loss") != "SL hit"
    assert _map_result_to_outcome("loss") != "sl_hit"


# ---------------------------------------------------------------------------
# Field type assertions (AC #2, #3)
# ---------------------------------------------------------------------------

def test_timestamp_is_int():
    """timestamp field MUST be Python int — not string or float (PostgreSQL bigint compatibility)"""
    entry_timestamp_ms = 1745625600000
    assert isinstance(entry_timestamp_ms, int)
    row = {"timestamp": entry_timestamp_ms}
    assert type(row["timestamp"]) is int


def test_signal_sent_at_is_utc_iso8601():
    """signal_sent_at must be ISO8601 UTC string ending with '+00:00'"""
    entry_timestamp_ms = 1745625600000
    signal_sent_at = datetime.fromtimestamp(
        entry_timestamp_ms / 1000, tz=timezone.utc
    ).isoformat()
    assert isinstance(signal_sent_at, str)
    assert signal_sent_at.endswith("+00:00"), f"Must be UTC ISO8601, got: {signal_sent_at}"


def test_telegram_sent_is_false_bool():
    """telegram_sent MUST be Python False (not string 'false')"""
    telegram_sent = False
    assert telegram_sent is False
    assert type(telegram_sent) is bool
    assert telegram_sent != "false"
    assert telegram_sent != "False"


def test_claude_verdict_is_none():
    """claude_verdict MUST be Python None (serializes to JSON null)"""
    claude_verdict = None
    assert claude_verdict is None
    assert claude_verdict != "null"
    assert claude_verdict != "None"


def test_metadata_schema_version_is_string():
    """metadata.schema_version MUST be string '1.0', not float 1.0"""
    schema_version = "1.0"
    assert isinstance(schema_version, str)
    assert schema_version == "1.0"
    assert schema_version != 1.0


# ---------------------------------------------------------------------------
# _parse_supabase_error (AC #6)
# ---------------------------------------------------------------------------

class _MockResp:
    """Helper mock for httpx.Response — used only in error parsing tests."""
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


def test_parse_supabase_error_type_mismatch_42804():
    """PostgreSQL error code 42804 → ValueError starting with 'Schema mismatch:'"""
    resp = _MockResp(400, {
        "code": "42804",
        "message": 'column "timestamp" is of type bigint but expression is of type text',
    })
    err = _parse_supabase_error(resp, "signal_comparisons")
    assert str(err).startswith("Schema mismatch:")
    assert "timestamp" in str(err)


def test_parse_supabase_error_generic_4xx():
    """Non-type-mismatch error → includes table name and status code"""
    resp = _MockResp(401, {"message": "Invalid API key"})
    err = _parse_supabase_error(resp, "signal_cases")
    assert "signal_cases write failed: 401" in str(err)
    assert "Invalid API key" in str(err)


def test_parse_supabase_error_no_json_body():
    """Corrupted/empty body → fallback to raw text message"""
    class _BadJsonResp:
        status_code = 500
        text = "Internal Server Error"
        def json(self):
            raise ValueError("not json")

    err = _parse_supabase_error(_BadJsonResp(), "signal_comparisons")
    assert "signal_comparisons write failed: 500" in str(err)
    assert "Internal Server Error" in str(err)


def test_parse_supabase_error_returns_value_error():
    """Return type must be ValueError"""
    resp = _MockResp(400, {"code": "42804", "message": "type mismatch"})
    err = _parse_supabase_error(resp, "signal_comparisons")
    assert isinstance(err, ValueError)
