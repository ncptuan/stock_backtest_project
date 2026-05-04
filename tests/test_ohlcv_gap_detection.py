"""
Tests cho Story P1-1.5: Data gap detection + clip notification.

Covers ACs #1–#6:
  - AC1: Cache có gaps → response có has_gaps=true, gaps list đúng
  - AC2: Cache liên tục → response có has_gaps=false, gaps=[]
  - AC3: Clip + gap đồng thời → cả hai field đều đúng
  - AC4: Cache rỗng → 404 no_cache (đã có từ Story 1.1)
  - AC5: Threshold 1.5x boundary
  - AC6: Gap detection trên sliced data, O(n)
"""
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.services.cache import detect_gaps

BASE_TS = 1_704_067_200_000  # 2024-01-01 00:00:00 UTC ms
HOUR_MS = 3_600_000


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _continuous_df(n: int = 10, base_ts: int = BASE_TS, interval_ms: int = HOUR_MS) -> pd.DataFrame:
    """n bars liên tục."""
    return pd.DataFrame({
        "timestamp": [base_ts + i * interval_ms for i in range(n)],
        "open": [100.0] * n,
        "high": [101.0] * n,
        "low": [99.0] * n,
        "close": [100.5] * n,
        "volume": [10.0] * n,
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
        "open": [100.0] * n,
        "high": [101.0] * n,
        "low": [99.0] * n,
        "close": [100.5] * n,
        "volume": [10.0] * n,
    })


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    """TestClient với cache_dir trỏ vào tmp_path."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    from backend.main import create_app
    return TestClient(create_app())


# ─── Unit tests: detect_gaps ─────────────────────────────────────────────────

def test_no_gap_returns_empty():
    """Data liên tục 1h → trả về []"""
    df = _continuous_df(10)
    result = detect_gaps(df, "1h")
    assert result == []


def test_single_gap_detected():
    """1 gap ở giữa (thiếu 2 bars 1h) → 1 gap entry đúng."""
    df = _df_with_gap(gap_after_bar=4, skip_bars=2)
    gaps = detect_gaps(df, "1h")
    assert len(gaps) == 1
    assert gaps[0]["missing_bars"] == 2
    assert gaps[0]["start_ts"] == BASE_TS + 4 * HOUR_MS
    assert gaps[0]["end_ts"] == BASE_TS + 7 * HOUR_MS  # 4 + 2 skip + 1 next


def test_multiple_gaps_detected():
    """Nhiều gaps → list đủ entries."""
    df = _df_with_gap(gap_after_bar=2, skip_bars=3, n=15)
    # Add second gap after bar 8
    ts = list(df["timestamp"])
    ts[8:] = [t + 2 * HOUR_MS for t in ts[8:]]
    df["timestamp"] = ts
    gaps = detect_gaps(df, "1h")
    assert len(gaps) == 2


def test_df_less_than_2_rows():
    """df < 2 rows → trả về []"""
    df = _continuous_df(1)
    assert detect_gaps(df, "1h") == []
    df_empty = _continuous_df(0)
    assert detect_gaps(df_empty, "1h") == []


def test_threshold_boundary_1_4x_not_gap():
    """Diff = 1.4x interval → NOT a gap."""
    df = pd.DataFrame({
        "timestamp": [BASE_TS, BASE_TS + int(HOUR_MS * 1.4)],
        "open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0],
        "close": [1.0, 1.0], "volume": [1.0, 1.0],
    })
    assert detect_gaps(df, "1h") == []


def test_threshold_boundary_1_6x_is_gap():
    """Diff = 1.6x interval → IS a gap."""
    df = pd.DataFrame({
        "timestamp": [BASE_TS, BASE_TS + int(HOUR_MS * 1.6)],
        "open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0],
        "close": [1.0, 1.0], "volume": [1.0, 1.0],
    })
    gaps = detect_gaps(df, "1h")
    assert len(gaps) == 1
    assert gaps[0]["missing_bars"] == 0  # 1.6x / 1.0 - 1 = 0.6 → int = 0


def test_threshold_exact_1_5x_not_gap():
    """Diff = exactly 1.5x → NOT a gap (strict >)."""
    df = pd.DataFrame({
        "timestamp": [BASE_TS, BASE_TS + int(HOUR_MS * 1.5)],
        "open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0],
        "close": [1.0, 1.0], "volume": [1.0, 1.0],
    })
    assert detect_gaps(df, "1h") == []


def test_unknown_timeframe_returns_empty():
    """Timeframe không xác định → trả về [] (fail safe)."""
    df = _continuous_df(10)
    assert detect_gaps(df, "unknown") == []


def test_4h_timeframe_gap():
    """Gap detection với timeframe 4h."""
    interval_4h = 4 * HOUR_MS
    df = _continuous_df(5, interval_ms=interval_4h)
    # Insert gap: skip 2 bars after bar 2
    ts = list(df["timestamp"])
    ts[3:] = [t + 2 * interval_4h for t in ts[3:]]
    df["timestamp"] = ts
    gaps = detect_gaps(df, "4h")
    assert len(gaps) == 1
    assert gaps[0]["missing_bars"] == 2


def test_1d_timeframe_gap():
    """Gap detection với timeframe 1D."""
    interval_1d = 24 * HOUR_MS
    df = _continuous_df(5, interval_ms=interval_1d)
    # Insert gap: skip 3 days after bar 1
    ts = list(df["timestamp"])
    ts[2:] = [t + 3 * interval_1d for t in ts[2:]]
    df["timestamp"] = ts
    gaps = detect_gaps(df, "1D")
    assert len(gaps) == 1
    assert gaps[0]["missing_bars"] == 3


# ─── Integration tests: GET /api/ohlcv ──────────────────────────────────────

def test_ohlcv_with_gaps(tmp_path, monkeypatch):
    """GET /api/ohlcv với cache có gap → response có has_gaps=true."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    # Create cache with a gap: bars 0-4, skip 2, bars 5-9
    df = _df_with_gap(gap_after_bar=4, skip_bars=2, n=10)
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)

    from backend.main import create_app
    client = TestClient(create_app())

    resp = client.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "date_start": "2024-01-01",
        "date_end": "2024-01-10",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_gaps"] is True
    assert len(body["gaps"]) == 1
    assert body["gaps"][0]["missing_bars"] == 2


def test_ohlcv_continuous_no_gaps(tmp_path, monkeypatch):
    """GET /api/ohlcv với cache liên tục → response có has_gaps=false."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    df = _continuous_df(100)
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)

    from backend.main import create_app
    client = TestClient(create_app())

    resp = client.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "date_start": "2024-01-01",
        "date_end": "2024-01-05",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_gaps"] is False
    assert body["gaps"] == []


def test_ohlcv_clip_and_gap_simultaneously(tmp_path, monkeypatch):
    """Cache có clip VÀ gap → cả hai field đều đúng."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    # Cache starts at 2024-01-03 (so requesting from 2024-01-01 clips the start)
    # And has a gap in the middle
    base_ts = BASE_TS + 2 * 24 * HOUR_MS  # Start at Jan 3
    df = _df_with_gap(gap_after_bar=4, skip_bars=2, n=10)
    df["timestamp"] = [base_ts + (t - BASE_TS) for t in df["timestamp"]]
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)

    from backend.main import create_app
    client = TestClient(create_app())

    resp = client.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "date_start": "2024-01-01",  # Earlier than cache
        "date_end": "2024-01-15",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["clipped"] is True
    assert body["has_gaps"] is True
    assert len(body["gaps"]) >= 1


def test_ohlcv_no_cache_404(tmp_path, monkeypatch):
    """Cache rỗng → 404 no_cache (AC4, regression từ Story 1.1)."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    from backend.main import create_app
    client = TestClient(create_app())

    resp = client.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "date_start": "2024-01-01",
        "date_end": "2024-01-05",
    })
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "no_cache"


def test_ohlcv_clip_detection_regression(tmp_path, monkeypatch):
    """FR6 regression: clip detection vẫn đúng sau khi thêm gap logic."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    # Cache: bars from 2024-01-05 to 2024-01-10 (continuous, no gaps)
    base_ts = BASE_TS + 4 * 24 * HOUR_MS
    df = _continuous_df(100, base_ts=base_ts)
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)

    from backend.main import create_app
    client = TestClient(create_app())

    # Request range extends before cache
    resp = client.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "date_start": "2024-01-01",
        "date_end": "2024-01-08",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["clipped"] is True
    assert body["actual_date_start"] is not None
    assert body["has_gaps"] is False
    assert body["gaps"] == []
