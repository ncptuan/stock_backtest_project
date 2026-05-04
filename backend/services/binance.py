import asyncio
from datetime import datetime, timezone
from typing import Callable

import httpx
import pandas as pd

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

TIMEFRAME_MAP = {
    "5m": "5m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1D": "1d",   # Binance dùng lowercase "1d"
}

_INTERVAL_MS: dict[str, int] = {
    "5m": 5 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1D": 24 * 60 * 60 * 1000,
}

# Columns returned by Binance klines API
_KLINE_COLUMNS = [
    "timestamp", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_buy_base",
    "taker_buy_quote", "ignore",
]
_OUTPUT_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def _date_to_ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _raw_to_df(raw: list) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)
    df = pd.DataFrame(raw, columns=_KLINE_COLUMNS)
    df = df[_OUTPUT_COLUMNS].copy()
    df["timestamp"] = df["timestamp"].astype("int64")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype("float64")
    return df


_MAX_429_RETRIES = 5


async def _fetch_page_with_retry(
    client: httpx.AsyncClient,
    symbol: str,
    interval: str,
    start_ms: int,
    end_ms: int,
    on_progress: Callable[[int, str], None] | None,
    current_percent: int,
    max_retries: int = 3,
) -> list:
    """Fetch one page from Binance with rate-limit + retry logic."""
    backoff = [1, 2, 4]
    rate_limit_count = 0
    for attempt in range(max_retries + 1):
        try:
            resp = await client.get(
                BINANCE_KLINES_URL,
                params={
                    "symbol": symbol,
                    "interval": interval,
                    "startTime": start_ms,
                    "endTime": end_ms,
                    "limit": 1000,
                },
            )
            if resp.status_code == 429:
                rate_limit_count += 1
                if rate_limit_count > _MAX_429_RETRIES:
                    raise RuntimeError(
                        f"Rate-limited {_MAX_429_RETRIES} times consecutively — aborting"
                    )
                wait = int(resp.headers.get("Retry-After", 60))
                if on_progress:
                    on_progress(current_percent, f"Rate limited — waiting {wait}s")
                await asyncio.sleep(wait)
                continue  # retry không count vào general budget
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as exc:
            if attempt >= max_retries:
                raise
            await asyncio.sleep(backoff[min(attempt, len(backoff) - 1)])
    # All retries exhausted — if rate-limiting was the cause, raise explicitly
    if rate_limit_count > 0:
        raise RuntimeError(
            f"Rate-limited {rate_limit_count} times — exhausted all retries"
        )
    return []


async def fetch_ohlcv(
    symbol: str,
    timeframe: str,
    date_start: str,
    date_end: str,
    on_progress: Callable[[int, str], None],
) -> pd.DataFrame:
    interval = TIMEFRAME_MAP[timeframe]
    interval_ms = _INTERVAL_MS[timeframe]
    start_ms = _date_to_ms(date_start)
    end_ms = _date_to_ms(date_end)

    total_expected = max(1, (end_ms - start_ms) // interval_ms)
    total_pages = max(1, (total_expected + 999) // 1000)

    all_frames: list[pd.DataFrame] = []
    cursor = start_ms
    page = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        while cursor < end_ms:
            page += 1
            page_end = min(cursor + 1000 * interval_ms, end_ms)
            raw = await _fetch_page_with_retry(
                client, symbol, interval, cursor, page_end, on_progress,
                current_percent=min(99, int((page - 1) / total_pages * 100)),
            )

            # Gap-8: validate partial page
            expected_rows = min(1000, max(1, (page_end - cursor) // interval_ms))
            if len(raw) < expected_rows:
                # Retry partial page up to 3 times, keep best result
                for retry in range(3):
                    try:
                        raw_retry = await _fetch_page_with_retry(
                            client, symbol, interval, cursor, page_end, on_progress,
                            current_percent=min(99, int((page - 1) / total_pages * 100)),
                            max_retries=1,
                        )
                    except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException, RuntimeError):
                        break  # network/rate-limit error during retry — use best effort
                    if len(raw_retry) > len(raw):
                        raw = raw_retry
                    if len(raw) >= expected_rows:
                        break

            df_page = _raw_to_df(raw)
            all_frames.append(df_page)

            if len(df_page) > 0:
                cursor = int(df_page["timestamp"].max()) + interval_ms
            else:
                cursor = page_end

            percent = min(99, int(page / total_pages * 100))
            on_progress(percent, f"Fetching page {page}/{total_pages}")

    if not all_frames:
        on_progress(100, "Fetched 0 candles")
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)

    result = pd.concat(all_frames, ignore_index=True)
    result = result.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    on_progress(100, f"Done — {len(result)} candles")
    return result


def get_cached_max_timestamp(symbol: str, timeframe: str, cache_dir) -> int | None:
    """Đọc cache và trả về max timestamp hoặc None nếu cache rỗng/không tồn tại."""
    from backend.services.cache import read_ohlcv

    df = read_ohlcv(symbol, timeframe, cache_dir)
    if df is None or len(df) == 0:
        return None
    return int(df["timestamp"].max())
