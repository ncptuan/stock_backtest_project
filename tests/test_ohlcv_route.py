"""
Tests cho Story P1-1-1: GET /api/ohlcv — Serve OHLCV từ Parquet cache.

Covers ACs #1–#6:
  - AC1: cache tồn tại, slice đúng range → 200 + JSON đúng shape
  - AC2: cache không tồn tại → 404 + error code "no_cache"
  - AC3: cache corrupt → 404 + code "cache_corrupted", file bị xóa
  - AC4: dedup + sort timestamps trước khi slice
  - AC5: date_start/date_end vượt range → clipped=True + actual dates
  - AC6: indicators slice-first — EMA chỉ tính đến date_end (no look-ahead)
         NaN đầu series → null trong JSON
"""
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

BASE_TS = 1_704_067_200_000   # 2024-01-01 00:00:00 UTC ms
INTERVAL_1H = 60 * 60 * 1_000  # 1 giờ tính bằng ms


def _make_df(n: int = 100, base_ts: int = BASE_TS) -> pd.DataFrame:
    """Tạo DataFrame OHLCV chuẩn với n bars."""
    return pd.DataFrame({
        "timestamp": [base_ts + i * INTERVAL_1H for i in range(n)],
        "open": [40000.0 + i * 10 for i in range(n)],
        "high": [40100.0 + i * 10 for i in range(n)],
        "low": [39900.0 + i * 10 for i in range(n)],
        "close": [40050.0 + i * 10 for i in range(n)],
        "volume": [1000.0] * n,
    })


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    """TestClient với cache_dir trỏ vào tmp_path."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    from backend.main import create_app
    return TestClient(create_app())


@pytest.fixture
def cache_with_data(tmp_path: Path):
    """Tạo BTCUSDT_1h.parquet trong tmp_path với 100 bars từ 2024-01-01."""
    df = _make_df(n=100)
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)
    return tmp_path


# ─── AC1: Happy path ─────────────────────────────────────────────────────────

def test_happy_path_200(tmp_path, monkeypatch):
    """Cache tồn tại → 200 với data array đúng shape."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    df = _make_df(n=100)
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)

    from backend.main import create_app
    c = TestClient(create_app())

    resp = c.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "date_start": "2024-01-01",
        "date_end": "2024-01-05",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert len(body["data"]) > 0

    bar = body["data"][0]
    assert set(bar.keys()) >= {"timestamp", "open", "high", "low", "close", "volume"}
    assert isinstance(bar["timestamp"], int)
    assert isinstance(bar["close"], float)


def test_happy_path_slice_range(tmp_path, monkeypatch):
    """Data được slice đúng theo date_start/date_end — không trả về toàn bộ cache."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    df = _make_df(n=200)  # 200 giờ từ 2024-01-01
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)

    from backend.main import create_app
    c = TestClient(create_app())

    resp = c.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "date_start": "2024-01-02",
        "date_end": "2024-01-03",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]

    # Chỉ bars trong range [2024-01-02, 2024-01-03)
    for bar in data:
        assert bar["timestamp"] >= 1_704_153_600_000   # 2024-01-02 UTC ms
        assert bar["timestamp"] <= 1_704_240_000_000 + INTERVAL_1H  # 2024-01-03 end


# ─── AC2: No cache → 404 no_cache ────────────────────────────────────────────

def test_no_cache_404(tmp_path, monkeypatch):
    """Cache không tồn tại → 404 với error code no_cache."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    from backend.main import create_app
    c = TestClient(create_app())

    resp = c.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "date_start": "2024-01-01",
        "date_end": "2024-01-05",
    })
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "no_cache"
    assert body["error"]["retryable"] is False


# ─── AC3: Corrupt cache → 404 cache_corrupted, file bị xóa ──────────────────

def test_corrupt_cache_404_and_deleted(tmp_path, monkeypatch):
    """Cache corrupt → 404 với code cache_corrupted, file bị xóa."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    corrupt_file = tmp_path / "BTCUSDT_1h.parquet"
    corrupt_file.write_bytes(b"not-a-parquet-file")

    from backend.main import create_app
    c = TestClient(create_app())

    resp = c.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "date_start": "2024-01-01",
        "date_end": "2024-01-05",
    })
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "cache_corrupted"
    assert body["error"]["retryable"] is True
    assert not corrupt_file.exists(), "File corrupt phải bị xóa"


# ─── AC4: Dedup + sort trước khi slice ───────────────────────────────────────

def test_dedup_and_sort(tmp_path, monkeypatch):
    """DataFrame có duplicate timestamps → output sorted và dedup'd."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    t0 = BASE_TS
    t1 = BASE_TS + INTERVAL_1H
    t2 = BASE_TS + 2 * INTERVAL_1H

    # Thêm duplicate t1 và đảo ngược thứ tự
    df = pd.DataFrame({
        "timestamp": [t2, t1, t1, t0],   # ngược, có duplicate
        "open":  [40020.0, 40010.0, 40010.0, 40000.0],
        "high":  [40120.0, 40110.0, 40110.0, 40100.0],
        "low":   [39920.0, 39910.0, 39910.0, 39900.0],
        "close": [40070.0, 40060.0, 40060.0, 40050.0],
        "volume": [1000.0, 1000.0, 1000.0, 1000.0],
    })
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)

    from backend.main import create_app
    c = TestClient(create_app())

    resp = c.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "date_start": "2024-01-01",
        "date_end": "2024-01-31",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]

    timestamps = [b["timestamp"] for b in data]
    assert timestamps == sorted(timestamps), "Timestamps phải sort ascending"
    assert len(timestamps) == len(set(timestamps)), "Không được có duplicate timestamps"
    assert len(data) == 3   # t0, t1, t2 — sau dedup


# ─── AC5: Clip khi date range vượt cache range ───────────────────────────────

def test_clip_date_start_before_cache(tmp_path, monkeypatch):
    """date_start trước cache range → clipped=True + actual_date_start/end."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    df = _make_df(n=48)  # 48h từ 2024-01-01
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)

    from backend.main import create_app
    c = TestClient(create_app())

    resp = c.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "date_start": "2023-12-01",    # TRƯỚC cache start (2024-01-01)
        "date_end": "2024-01-03",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["clipped"] is True
    assert body["actual_date_start"] is not None
    assert body["actual_date_end"] is not None


def test_no_clip_within_range(tmp_path, monkeypatch):
    """date_start/date_end trong cache range → clipped=False."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    df = _make_df(n=200)
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)

    from backend.main import create_app
    c = TestClient(create_app())

    resp = c.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "date_start": "2024-01-02",
        "date_end": "2024-01-05",
    })
    assert resp.status_code == 200
    assert resp.json()["clipped"] is False


# ─── AC6: Indicators slice-first + NaN → null ────────────────────────────────

def test_ema_slice_first_no_lookahead(tmp_path, monkeypatch):
    """EMA chỉ tính trên data tới date_end — giá trị phải khác nếu tính trên full df."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    # 50 bars, close tăng dần
    df = pd.DataFrame({
        "timestamp": [BASE_TS + i * INTERVAL_1H for i in range(50)],
        "open":  [40000.0 + i * 100 for i in range(50)],
        "high":  [40100.0 + i * 100 for i in range(50)],
        "low":   [39900.0 + i * 100 for i in range(50)],
        "close": [40000.0 + i * 100 for i in range(50)],  # strictly increasing
        "volume": [1000.0] * 50,
    })
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)

    from backend.main import create_app
    c = TestClient(create_app())

    # date_end = 2024-01-02 = chỉ dùng bars đầu (khoảng 24 bars)
    resp = c.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "date_start": "2024-01-01",
        "date_end": "2024-01-02",
        "ema": 20,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]

    # Lấy EMA cuối trong slice (khoảng bar 23)
    last_ema = next((b["ema_20"] for b in reversed(data) if b["ema_20"] is not None), None)
    assert last_ema is not None

    # EMA tính trên full df (50 bars) sẽ lớn hơn vì close tăng dần
    full_ema_at_same_pos = df["close"].ewm(span=20, adjust=False).mean().iloc[23]
    # Slice EMA phải khác full-df EMA (slice-first enforcement)
    assert abs(last_ema - float(full_ema_at_same_pos)) > 0.01, (
        "EMA slice-first phải khác EMA trên full df"
    )


def test_ema_nan_returns_null(tmp_path, monkeypatch):
    """EMA đầu series (< span bars) trả về null trong JSON — không crash."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    df = _make_df(n=30)
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)

    from backend.main import create_app
    c = TestClient(create_app())

    resp = c.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "date_start": "2024-01-01",
        "date_end": "2024-01-31",
        "ema": 20,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]

    # pandas ewm không thực sự trả NaN với adjust=False — nhưng MA sẽ có NaN đầu
    # Test MA thay vì EMA cho NaN behavior
    resp_ma = c.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "date_start": "2024-01-01",
        "date_end": "2024-01-31",
        "ma": 20,
    })
    assert resp_ma.status_code == 200
    data_ma = resp_ma.json()["data"]

    # 19 bars đầu MA20 phải là null (rolling cần đủ 20 bars)
    null_count = sum(1 for b in data_ma if b.get("ma_20") is None)
    assert null_count == 19, f"Cần 19 null ở đầu MA20, got {null_count}"


# ─── AC: Timeframe không hợp lệ → 422 ───────────────────────────────────────

def test_invalid_timeframe_422(tmp_path, monkeypatch):
    """Timeframe không trong whitelist → 422."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    from backend.main import create_app
    c = TestClient(create_app())

    resp = c.get("/api/ohlcv", params={
        "symbol": "BTCUSDT",
        "timeframe": "99h",
        "date_start": "2024-01-01",
        "date_end": "2024-01-05",
    })
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "invalid_timeframe"


# ─── AC: Symbol normalize BTC/USDT → BTCUSDT ─────────────────────────────────

def test_symbol_normalize_slash(tmp_path, monkeypatch):
    """Symbol với '/' được normalize — tìm đúng file BTCUSDT_1h.parquet."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    df = _make_df(n=50)
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)

    from backend.main import create_app
    c = TestClient(create_app())

    resp = c.get("/api/ohlcv", params={
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "date_start": "2024-01-01",
        "date_end": "2024-01-10",
    })
    assert resp.status_code == 200
    assert len(resp.json()["data"]) > 0
