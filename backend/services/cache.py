import os
import re
from pathlib import Path

import pandas as pd


class CacheCorruptError(Exception):
    pass


# Alias — ohlcv.py dùng CacheSchemaError cho missing columns/bad dtypes
CacheSchemaError = CacheCorruptError


_SYMBOL_RE = re.compile(r"^[A-Za-z0-9]{1,20}$")


def _cache_path(symbol: str, timeframe: str, cache_dir: Path) -> Path:
    symbol = symbol.replace("/", "")
    if not _SYMBOL_RE.match(symbol):
        raise ValueError(f"Invalid symbol: {symbol!r}")
    return cache_dir / f"{symbol}_{timeframe}.parquet"


def _tmp_path(symbol: str, timeframe: str, cache_dir: Path) -> Path:
    symbol = symbol.replace("/", "")
    if not _SYMBOL_RE.match(symbol):
        raise ValueError(f"Invalid symbol: {symbol!r}")
    return cache_dir / f"{symbol}_{timeframe}.parquet.tmp"


def read_ohlcv(symbol: str, timeframe: str, cache_dir: Path) -> pd.DataFrame | None:
    path = _cache_path(symbol, timeframe, cache_dir)
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        path.unlink(missing_ok=True)
        raise CacheCorruptError(f"Cache corrupt: {path.name}")

    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        path.unlink(missing_ok=True)
        raise CacheCorruptError(f"Missing columns in {path.name}")

    try:
        df["timestamp"] = df["timestamp"].astype("int64")
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = df[col].astype("float64")
    except (ValueError, TypeError):
        path.unlink(missing_ok=True)
        raise CacheCorruptError(f"Invalid column types in {path.name}")

    if len(df) == 0:
        return None

    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    return df


_INTERVAL_MS: dict[str, int] = {
    "5m": 5 * 60 * 1000,       # 300_000
    "30m": 30 * 60 * 1000,     # 1_800_000
    "1h": 60 * 60 * 1000,      # 3_600_000
    "4h": 4 * 60 * 60 * 1000,  # 14_400_000
    "1D": 24 * 60 * 60 * 1000, # 86_400_000
}


def detect_gaps(df: pd.DataFrame, timeframe: str) -> list[dict]:
    """Detect timestamp gaps trong OHLCV DataFrame.

    Returns list of gap dicts: [{"start_ts": int, "end_ts": int, "missing_bars": int}]
    Empty list nếu không có gap hoặc df < 2 rows.
    """
    if len(df) < 2:
        return []

    interval_ms = _INTERVAL_MS.get(timeframe)
    if interval_ms is None:
        return []  # unknown timeframe — fail safe

    threshold = interval_ms * 1.5
    timestamps = df["timestamp"].values
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


def write_ohlcv(df: pd.DataFrame, symbol: str, timeframe: str, cache_dir: Path) -> None:
    """Atomic write: write-to-temp then rename. Tránh partial write corruption (Gap 2)."""
    if len(df) == 0:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    final_path = _cache_path(symbol, timeframe, cache_dir)
    tmp = _tmp_path(symbol, timeframe, cache_dir)
    try:
        df.to_parquet(tmp, index=False)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp, final_path)
