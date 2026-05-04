"""
Unit tests cho backend/services/cache.py — Story P1-1-3.

Covers ACs #1–#5:
  - AC1: atomic write — .parquet tồn tại, .tmp KHÔNG tồn tại sau write
  - AC1: write failure → .tmp bị xóa, .parquet không được tạo
  - AC3: corrupt detection → CacheCorruptError + file bị xóa
  - AC3: missing columns → CacheCorruptError
  - AC4: dedup + sort timestamps
  - AC5: write rồi read → data regression OK
"""
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from backend.services.cache import CacheCorruptError, read_ohlcv, write_ohlcv

BASE_TS = 1_704_067_200_000   # 2024-01-01 00:00:00 UTC ms
INTERVAL_1H = 3_600_000


def _make_df(n: int = 10) -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": [BASE_TS + i * INTERVAL_1H for i in range(n)],
        "open": [42000.0] * n,
        "high": [42100.0] * n,
        "low": [41900.0] * n,
        "close": [42050.0] * n,
        "volume": [100.0] * n,
    })


# ─── AC1: Atomic write ───────────────────────────────────────────────────────

def test_atomic_write_happy_path(tmp_path):
    """Sau write: .parquet tồn tại, .tmp KHÔNG tồn tại."""
    df = _make_df()
    write_ohlcv(df, "BTCUSDT", "1h", tmp_path)
    assert (tmp_path / "BTCUSDT_1h.parquet").exists()
    assert not (tmp_path / "BTCUSDT_1h.parquet.tmp").exists()


def test_atomic_write_failure_cleanup(tmp_path):
    """`to_parquet` raise OSError → .tmp bị xóa, .parquet không được tạo."""
    df = _make_df()
    with patch("pandas.DataFrame.to_parquet", side_effect=OSError("disk full")):
        with pytest.raises(OSError, match="disk full"):
            write_ohlcv(df, "BTCUSDT", "1h", tmp_path)

    assert not (tmp_path / "BTCUSDT_1h.parquet.tmp").exists()
    assert not (tmp_path / "BTCUSDT_1h.parquet").exists()


def test_atomic_write_no_partial_file(tmp_path):
    """Intermediate .tmp không tồn tại sau rename thành công."""
    df = _make_df()
    write_ohlcv(df, "ETHUSDT", "4h", tmp_path)
    assert (tmp_path / "ETHUSDT_4h.parquet").exists()
    assert not (tmp_path / "ETHUSDT_4h.parquet.tmp").exists()


# ─── AC5: Regression — write rồi read → data khớp ────────────────────────────

def test_read_write_roundtrip(tmp_path):
    """write_ohlcv rồi read_ohlcv → data match."""
    df = _make_df(n=5)
    write_ohlcv(df, "BTCUSDT", "1h", tmp_path)
    result = read_ohlcv("BTCUSDT", "1h", tmp_path)
    assert result is not None
    assert list(result["timestamp"]) == list(df["timestamp"])
    assert list(result["close"]) == list(df["close"])


# ─── AC3: Corrupt detection ──────────────────────────────────────────────────

def test_corrupt_detection_raises_and_deletes(tmp_path):
    """File rác → CacheCorruptError + file bị xóa."""
    path = tmp_path / "BTCUSDT_1h.parquet"
    path.write_bytes(b"this is not a valid parquet file")
    with pytest.raises(CacheCorruptError):
        read_ohlcv("BTCUSDT", "1h", tmp_path)
    assert not path.exists(), "File corrupt phải bị xóa"


def test_missing_columns_raises_corrupt(tmp_path):
    """DataFrame thiếu column 'volume' → CacheCorruptError."""
    df = _make_df().drop(columns=["volume"])
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)
    with pytest.raises(CacheCorruptError):
        read_ohlcv("BTCUSDT", "1h", tmp_path)


# ─── AC4: Dedup + sort ───────────────────────────────────────────────────────

def test_dedup_and_sort(tmp_path):
    """Duplicate timestamps bị dedup, output sort ascending."""
    df = pd.DataFrame({
        "timestamp": [BASE_TS + 2 * INTERVAL_1H, BASE_TS, BASE_TS + INTERVAL_1H, BASE_TS],
        "open":   [1.0, 2.0, 3.0, 4.0],
        "high":   [1.0, 2.0, 3.0, 4.0],
        "low":    [1.0, 2.0, 3.0, 4.0],
        "close":  [1.0, 2.0, 3.0, 4.0],
        "volume": [1.0, 2.0, 3.0, 4.0],
    })
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)
    result = read_ohlcv("BTCUSDT", "1h", tmp_path)
    assert result is not None
    assert len(result) == 3, "1 duplicate phải bị xóa"
    assert list(result["timestamp"]) == sorted(result["timestamp"].tolist())


# ─── No cache ────────────────────────────────────────────────────────────────

def test_no_cache_returns_none(tmp_path):
    """File không tồn tại → None."""
    result = read_ohlcv("BTCUSDT", "1h", tmp_path)
    assert result is None


# ─── Symbol normalize ────────────────────────────────────────────────────────

def test_symbol_slash_normalize(tmp_path):
    """Symbol 'BTC/USDT' được normalize → tìm đúng file BTCUSDT_1h.parquet."""
    df = _make_df(n=5)
    write_ohlcv(df, "BTCUSDT", "1h", tmp_path)

    result = read_ohlcv("BTC/USDT", "1h", tmp_path)
    assert result is not None
    assert len(result) == 5


# ─── AC2: .tmp cleanup at startup (integration) ──────────────────────────────

def test_lifespan_cleans_stale_tmp(tmp_path, monkeypatch):
    """Lifespan startup xóa file .tmp còn sót."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    stale_tmp = tmp_path / "BTCUSDT_1h.parquet.tmp"
    stale_tmp.write_bytes(b"stale")
    assert stale_tmp.exists()

    from backend.main import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app()):
        assert not stale_tmp.exists(), "Stale .tmp phải bị xóa khi server startup"
