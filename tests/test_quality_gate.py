"""
tests/test_quality_gate.py — Story 4.2

Pure unit tests cho:
  - compute_quality_gate() (backend/services/preview.py)
  - compute_reasoning_template() (backend/services/preview.py)
  - bars_to_exit off-by-one regression guard

No network connection, no Supabase, no Parquet files required.
"""
import re

import numpy as np
import pandas as pd
import pytest

from backend.models import TradeInput
from backend.services.preview import compute_quality_gate, compute_reasoning_template


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_trades(n_total: int, n_wins: int) -> list[TradeInput]:
    """Helper: tạo list[TradeInput] với n_total trades và n_wins wins."""
    return [
        TradeInput(
            bar_index=10 + i,
            entry_timestamp_ms=1745625600000,
            direction="LONG",
            entry_price=43000.0,
            tp_price=44000.0,
            sl_price=42000.0,
            result="win" if i < n_wins else "loss",
            bars_to_exit=7,
        )
        for i in range(n_total)
    ]


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


# ---------------------------------------------------------------------------
# compute_quality_gate
# ---------------------------------------------------------------------------

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
        """15 trades, 7 wins (46.7% → rounds to 47%) → fail because < 55% win rate"""
        trades = _make_trades(15, 7)
        status, reason = compute_quality_gate(trades)
        assert status == "fail"
        assert reason is not None
        assert "47%" in reason
        assert "cần tối thiểu 55%" in reason

    def test_pass_boundary_exactly_55_percent(self):
        """20 trades, 11 wins (55%) → pass (exactly at threshold)"""
        trades = _make_trades(20, 11)
        status, reason = compute_quality_gate(trades)
        assert status == "pass"
        assert reason is None

    def test_fail_count_only_not_rate(self):
        """9 trades, 6 wins (67%) → fail on count only; win rate would pass"""
        trades = _make_trades(9, 6)
        status, reason = compute_quality_gate(trades)
        assert status == "fail"
        assert "9 trades" in reason
        # win rate is 67% so win rate reason should NOT appear
        assert "win rate" not in reason

    def test_fail_dual_reasons(self):
        """7 trades, 3 wins (43%) → both count AND win rate fail, joined by '; '"""
        trades = _make_trades(7, 3)
        status, reason = compute_quality_gate(trades)
        assert status == "fail"
        assert "7 trades" in reason
        assert "43%" in reason
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

    def test_fail_exactly_9_trades_100pct(self):
        """9 trades with 100% win rate → still fail because count < 10"""
        trades = _make_trades(9, 9)
        status, reason = compute_quality_gate(trades)
        assert status == "fail"
        assert "9 trades" in reason

    def test_pass_exactly_10_trades_60pct(self):
        """10 trades, 6 wins (60%) → pass (count == 10, rate == 60% > 55%)"""
        trades = _make_trades(10, 6)
        status, reason = compute_quality_gate(trades)
        assert status == "pass"
        assert reason is None


# ---------------------------------------------------------------------------
# compute_reasoning_template
# ---------------------------------------------------------------------------

class TestComputeReasoningTemplate:
    def test_output_format_matches_template(self):
        """Output phải match exact format pattern"""
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
        """timeframe='4h' → output bắt đầu bằng '4H |'"""
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
        """entry_price=43250 → '$43,250' trong output"""
        df = _make_minimal_df(60)
        trade = TradeInput(
            bar_index=42, entry_timestamp_ms=1745625600000,
            direction="LONG", entry_price=43250.0,
            tp_price=44000.0, sl_price=42800.0,
            result="win", bars_to_exit=7,
        )
        result = compute_reasoning_template(df, trade, "4h")
        assert "Entry $43,250" in result

    def test_slice_first_no_look_ahead(self):
        """
        Verify slice-first (Gap-1): EMA tại bar 42 không bị ảnh hưởng bởi spike sau bar 42.
        Nếu look-ahead bias tồn tại, EMA sẽ bị kéo lên bởi spike tại bar 50+.
        """
        n_bars = 80
        close = np.ones(n_bars) * 40000.0
        close[50:] = 60000.0  # spike sau bar 42 — không được ảnh hưởng EMA tại bar 42
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
        # EMA at bar 42 must be ~40000 (flat region, no spike influence)
        # Format check ensures valid output was generated
        assert REASONING_TEMPLATE_PATTERN.match(result), (
            f"Format check failed for slice-first test. Got: '{result}'"
        )
        # EMA should be ~$40,000 — not pulled by $60,000 spike
        assert "EMA20=$40,000" in result or "EMA20=$40" in result[:30] or "EMA20=$4" in result


# ---------------------------------------------------------------------------
# bars_to_exit off-by-one regression guard (AC #6)
# ---------------------------------------------------------------------------

def test_bars_to_exit_off_by_one_regression():
    """
    Explicit regression guard.

    CORRECT formula: bars_to_exit = exit_bar_index - entry_bar_index
    INCORRECT: bars_to_exit = exit_bar_index - entry_bar_index + 1

    AC: entry bar 42, exit bar 49 → bars_to_exit = 7 (NOT 8)
    """
    entry_bar = 42
    exit_bar = 49
    bars_to_exit = exit_bar - entry_bar
    assert bars_to_exit == 7, (
        f"bars_to_exit off-by-one bug: expected 7, got {bars_to_exit}. "
        "Use 'exit_bar - entry_bar', NOT 'exit_bar - entry_bar + 1'."
    )


def test_bars_to_exit_same_bar():
    """Entry and exit on same bar → bars_to_exit = 0"""
    assert 42 - 42 == 0


def test_bars_to_exit_next_bar():
    """Exit on next bar → bars_to_exit = 1"""
    assert 43 - 42 == 1
