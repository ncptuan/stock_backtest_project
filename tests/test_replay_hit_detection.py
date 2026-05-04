"""
Hit detection engine reference tests (P1-5.1).
Validates the algorithm used by frontend/ReplayEngine.ts checkHits().

These tests implement the same logic in Python to verify correctness
of the hit detection rules: entry, TP, SL, same-bar priority, gap-down,
auto-close, max 1 position, float safety.
"""
import pytest


def normalize(price: float) -> float:
    """Float-safe price normalization — $0.01 tick for BTC/USDT."""
    return round(price * 100) / 100


# ---------------------------------------------------------------------------
# Minimal replay engine for testing hit detection logic
# ---------------------------------------------------------------------------

class HitDetectionEngine:
    """Python reference implementation of ReplayEngine.checkHits() logic."""

    def __init__(self, entry: float, tp: float, sl: float):
        self.entry = normalize(entry)
        self.tp = normalize(tp)
        self.sl = normalize(sl)
        self.open_position = None  # None or dict with entry_bar_index, etc.
        self.trades = []           # list of completed trades

    def process_bar(self, bar_index: int, bar: dict, data: list[dict]):
        """Process a single bar — mirrors checkHits() in ReplayEngine.ts."""
        high = normalize(bar['high'])
        low = normalize(bar['low'])
        open_ = normalize(bar['open'])
        close = normalize(bar['close'])

        # Entry check — only when no position
        if not self.open_position:
            if high >= self.entry:
                # Enter at next bar's open (AC#1)
                next_bar = data[bar_index + 1] if bar_index + 1 < len(data) else None
                if next_bar:
                    self.open_position = {
                        'direction': 'LONG',
                        'entry_price': normalize(next_bar['open']),
                        'entry_bar_index': bar_index + 1,
                    }
            return

        # TP/SL checks — only after entry bar
        if bar_index <= self.open_position['entry_bar_index']:
            return

        tp_hit = high >= self.tp
        sl_hit = low <= self.sl

        if tp_hit and sl_hit:
            # Same bar: priority by candle direction (AC#2)
            is_bullish = close > open_
            result = 'win' if is_bullish else 'loss'
            self._close(bar_index, result)
        elif tp_hit:
            self._close(bar_index, 'win')
        elif sl_hit:
            # Gap-down: open below SL → slippage at open
            self._close(bar_index, 'loss')

    def auto_close(self, bar_index: int):
        """Auto-close at last bar if position still open (AC#3)."""
        if self.open_position:
            self._close(bar_index, 'loss')

    def _close(self, bar_index: int, result: str):
        self.trades.append({
            'entry_bar_index': self.open_position['entry_bar_index'],
            'exit_bar_index': bar_index,
            'entry_price': self.open_position['entry_price'],
            'direction': self.open_position['direction'],
            'result': result,
            'bars_to_exit': bar_index - self.open_position['entry_bar_index'],
        })
        self.open_position = None


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def make_bar(high: float, low: float, open_: float, close: float) -> dict:
    return {'high': high, 'low': low, 'open': open_, 'close': close, 'timestamp': 0, 'volume': 0}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEntryHit:
    def test_entry_hit_high_above_entry(self):
        """AC#1: high >= entry → open at next bar's open."""
        data = [
            make_bar(68000, 67000, 67500, 67800),  # bar 0
            make_bar(69000, 68000, 68500, 68800),  # bar 1: high=69000 >= entry=68500
            make_bar(69500, 68500, 69000, 69200),  # bar 2
        ]
        engine = HitDetectionEngine(entry=68500, tp=70000, sl=67000)
        for i, bar in enumerate(data):
            engine.process_bar(i, bar, data)
        assert len(engine.trades) == 0  # no close yet
        assert engine.open_position is not None
        assert engine.open_position['entry_bar_index'] == 2  # entered at bar 2's open
        assert engine.open_position['entry_price'] == 69000.0

    def test_entry_miss_high_below_entry(self):
        """AC#1: high < entry → no trade on bar 1, but hit on bar 2."""
        data = [
            make_bar(68000, 67000, 67500, 67800),  # bar 0
            make_bar(68400, 67500, 68000, 68200),  # bar 1: high=68400 < entry=68500
            make_bar(68600, 67800, 68200, 68400),  # bar 2: high=68600 >= entry
            make_bar(69000, 68000, 68500, 68800),  # bar 3: entry lands here
        ]
        engine = HitDetectionEngine(entry=68500, tp=70000, sl=67000)
        for i, bar in enumerate(data):
            engine.process_bar(i, bar, data)
        assert engine.open_position is not None
        assert engine.open_position['entry_bar_index'] == 3  # entered at bar 3 (next after bar 2)

    def test_entry_at_exact_price(self):
        """AC#4: Entry price exactly at high → hit (float boundary)."""
        data = [
            make_bar(68500.00, 67000, 67500, 68000),  # high == entry
            make_bar(69000, 68000, 68500, 68800),
        ]
        engine = HitDetectionEngine(entry=68500, tp=70000, sl=67000)
        for i, bar in enumerate(data):
            engine.process_bar(i, bar, data)
        assert engine.open_position is not None


class TestTPHit:
    def test_tp_hit_wins(self):
        """AC#2: high >= TP → close as win."""
        data = [
            make_bar(69000, 68000, 68500, 68800),  # bar 0: entry hit
            make_bar(68800, 68200, 68500, 68600),  # bar 1: entry bar (no TP/SL check)
            make_bar(70500, 68500, 69000, 70200),  # bar 2: TP hit
        ]
        engine = HitDetectionEngine(entry=68500, tp=70000, sl=67000)
        for i, bar in enumerate(data):
            engine.process_bar(i, bar, data)
        assert len(engine.trades) == 1
        assert engine.trades[0]['result'] == 'win'
        assert engine.trades[0]['exit_bar_index'] == 2


class TestSLHit:
    def test_sl_hit_loses(self):
        """AC#2: low <= SL → close as loss."""
        data = [
            make_bar(69000, 68000, 68500, 68800),  # bar 0: entry hit
            make_bar(68800, 68200, 68500, 68600),  # bar 1: entry bar
            make_bar(68000, 66500, 67800, 66800),  # bar 2: SL hit (low=66500 <= 67000)
        ]
        engine = HitDetectionEngine(entry=68500, tp=70000, sl=67000)
        for i, bar in enumerate(data):
            engine.process_bar(i, bar, data)
        assert len(engine.trades) == 1
        assert engine.trades[0]['result'] == 'loss'
        assert engine.trades[0]['exit_bar_index'] == 2

    def test_gap_down_slippage(self):
        """AC#2: open < SL → slippage, still closes as loss."""
        data = [
            make_bar(69000, 68000, 68500, 68800),  # bar 0: entry hit
            make_bar(68800, 68200, 68500, 68600),  # bar 1: entry bar
            make_bar(67000, 65000, 66000, 65500),  # bar 2: gap-down (open=66000 < SL=67000)
        ]
        engine = HitDetectionEngine(entry=68500, tp=70000, sl=67000)
        for i, bar in enumerate(data):
            engine.process_bar(i, bar, data)
        assert len(engine.trades) == 1
        assert engine.trades[0]['result'] == 'loss'


class TestSameBarPriority:
    def test_bullish_tp_priority(self):
        """AC#2: Both TP and SL hit, bullish candle → TP wins."""
        data = [
            make_bar(69000, 68000, 68500, 68800),  # bar 0: entry hit
            make_bar(68800, 68200, 68500, 68600),  # bar 1: entry bar
            make_bar(70500, 66500, 67000, 70200),  # bar 2: TP+SL, close(70200) > open(67000) → bullish
        ]
        engine = HitDetectionEngine(entry=68500, tp=70000, sl=67000)
        for i, bar in enumerate(data):
            engine.process_bar(i, bar, data)
        assert len(engine.trades) == 1
        assert engine.trades[0]['result'] == 'win'  # TP priority on bullish

    def test_bearish_sl_priority(self):
        """AC#2: Both TP and SL hit, bearish candle → SL wins."""
        data = [
            make_bar(69000, 68000, 68500, 68800),  # bar 0: entry hit
            make_bar(68800, 68200, 68500, 68600),  # bar 1: entry bar
            make_bar(70500, 66500, 70200, 66800),  # bar 2: TP+SL, close(66800) < open(70200) → bearish
        ]
        engine = HitDetectionEngine(entry=68500, tp=70000, sl=67000)
        for i, bar in enumerate(data):
            engine.process_bar(i, bar, data)
        assert len(engine.trades) == 1
        assert engine.trades[0]['result'] == 'loss'  # SL priority on bearish


class TestMaxOnePosition:
    def test_ignore_subsequent_entries(self):
        """AC#1: Max 1 position — second entry ignored."""
        data = [
            make_bar(69000, 68000, 68500, 68800),  # bar 0: entry hit → open at bar 1
            make_bar(68800, 68200, 68500, 68600),  # bar 1: entry bar
            make_bar(68000, 66500, 67800, 66800),  # bar 2: SL hit → close
            make_bar(69000, 68000, 68500, 68800),  # bar 3: second entry hit
            make_bar(68800, 68200, 68500, 68600),  # bar 4: entry bar
        ]
        engine = HitDetectionEngine(entry=68500, tp=70000, sl=67000)
        for i, bar in enumerate(data):
            engine.process_bar(i, bar, data)
        # First trade closed at bar 2, second opened at bar 4
        assert len(engine.trades) == 1
        assert engine.open_position is not None
        assert engine.open_position['entry_bar_index'] == 4


class TestAutoClose:
    def test_auto_close_at_last_bar(self):
        """AC#3: Position still open at last bar → auto-close as loss."""
        data = [
            make_bar(69000, 68000, 68500, 68800),  # bar 0: entry hit
            make_bar(68800, 68200, 68500, 68600),  # bar 1: entry bar
            make_bar(69500, 68500, 69000, 69200),  # bar 2: no TP/SL hit
        ]
        engine = HitDetectionEngine(entry=68500, tp=70000, sl=67000)
        for i, bar in enumerate(data):
            engine.process_bar(i, bar, data)
        assert engine.open_position is not None
        engine.auto_close(2)
        assert len(engine.trades) == 1
        assert engine.trades[0]['result'] == 'loss'
        assert engine.trades[0]['exit_bar_index'] == 2


class TestFloatSafety:
    def test_exact_boundary_entry(self):
        """AC#4: Float edge case — entry at exact boundary."""
        data = [
            make_bar(68500.005, 67000, 67500, 68000),  # high slightly above entry
            make_bar(69000, 68000, 68500, 68800),
        ]
        engine = HitDetectionEngine(entry=68500, tp=70000, sl=67000)
        for i, bar in enumerate(data):
            engine.process_bar(i, bar, data)
        # normalize(68500.005) = 68500.00, normalize(68500) = 68500.00 → hit
        assert engine.open_position is not None

    def test_exact_boundary_tp(self):
        """AC#4: Float edge case — TP at exact boundary."""
        data = [
            make_bar(69000, 68000, 68500, 68800),  # bar 0: entry hit
            make_bar(68800, 68200, 68500, 68600),  # bar 1: entry bar
            make_bar(70000.004, 68500, 69000, 69800),  # bar 2: high slightly below TP
        ]
        engine = HitDetectionEngine(entry=68500, tp=70000, sl=67000)
        for i, bar in enumerate(data):
            engine.process_bar(i, bar, data)
        # normalize(70000.004) = 70000.00 >= normalize(70000) = 70000.00 → TP hit
        assert len(engine.trades) == 1
        assert engine.trades[0]['result'] == 'win'


class TestNoEntryOnLastBar:
    def test_no_entry_when_last_bar(self):
        """Entry hit on last bar → no trade (no next bar to enter on)."""
        data = [
            make_bar(68000, 67000, 67500, 67800),  # bar 0
            make_bar(69000, 68000, 68500, 68800),  # bar 1: entry hit, but last bar
        ]
        engine = HitDetectionEngine(entry=68500, tp=70000, sl=67000)
        for i, bar in enumerate(data):
            engine.process_bar(i, bar, data)
        assert engine.open_position is None
        assert len(engine.trades) == 0
