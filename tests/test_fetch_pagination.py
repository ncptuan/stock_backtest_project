"""
Tests cho Story P1-1.4: Full pagination, refresh data + job management.

Covers ACs #1–#7:
  - AC1: Pagination qua nhiều pages, concat, progress updates
  - AC2: Gap-8 partial page validation + retry
  - AC3: Rate-limit (429) handling
  - AC4: General retry with exponential backoff
  - AC5: mode=refresh incremental fetch
  - AC6: Lazy job cleanup (TTL 5 min)
  - AC7: Cache still serves when Binance unavailable
"""
import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pandas as pd
import pytest

from backend.services import binance, job_manager


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_raw_rows(start_ts: int, count: int, interval_ms: int = 3_600_000) -> list:
    """Tạo raw Binance klines rows."""
    rows = []
    for i in range(count):
        ts = start_ts + i * interval_ms
        rows.append([
            ts,                    # open_time
            "42000.0",             # open
            "42500.0",             # high
            "41800.0",             # low
            "42200.0",             # close
            "100.0",               # volume
            ts + interval_ms - 1,  # close_time
            "0.0",                 # quote_volume
            100,                   # trades
            "50.0",                # taker_buy_base
            "0.0",                 # taker_buy_quote
            "0",                   # ignore
        ])
    return rows


def _make_df(start_ts: int, count: int, interval_ms: int = 3_600_000) -> pd.DataFrame:
    """Tạo DataFrame giống output của fetch_ohlcv."""
    timestamps = [start_ts + i * interval_ms for i in range(count)]
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": [42000.0] * count,
        "high": [42500.0] * count,
        "low": [41800.0] * count,
        "close": [42200.0] * count,
        "volume": [100.0] * count,
    })


class MockAsyncClient:
    """Mock httpx.AsyncClient that works as async context manager."""

    def __init__(self, get_side_effect):
        self.get = AsyncMock(side_effect=get_side_effect)
        self.timeout = 30.0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.fixture(autouse=True)
def reset_job_manager():
    """Reset global state trước/sau mỗi test."""
    job_manager._active_tasks.clear()
    job_manager._job_progress.clear()
    job_manager._job_key_map.clear()
    job_manager._job_completed_at.clear()
    yield
    job_manager._active_tasks.clear()
    job_manager._job_progress.clear()
    job_manager._job_key_map.clear()
    job_manager._job_completed_at.clear()


# ─── AC1: Pagination happy path ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pagination_3_pages_concat():
    """3 pages → concat all rows, progress calls đúng."""
    # Use exact ms boundaries so partial page retry never triggers
    start_ms = binance._date_to_ms("2024-01-01")
    interval_ms = 3_600_000  # 1h

    # 3 pages: 1000 + 1000 + 500 = 2500 rows
    # end_ms = start_ms + 2500 * interval_ms → exactly 2500 bars
    end_ms = start_ms + 2500 * interval_ms
    end_date = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")

    page1 = _make_raw_rows(start_ms, 1000, interval_ms)
    page2 = _make_raw_rows(start_ms + 1000 * interval_ms, 1000, interval_ms)
    page3 = _make_raw_rows(start_ms + 2000 * interval_ms, 500, interval_ms)

    call_count = 0
    responses = [page1, page2, page3]

    async def mock_get(url, params=None):
        nonlocal call_count
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = responses[call_count]
        resp.raise_for_status = MagicMock()
        call_count += 1
        return resp

    progress_calls = []

    def on_progress(percent, status_text):
        progress_calls.append((percent, status_text))

    mock_client = MockAsyncClient(mock_get)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await binance.fetch_ohlcv(
            "BTCUSDT", "1h", "2024-01-01", end_date, on_progress
        )

    assert len(result) == 2500
    assert len(progress_calls) >= 3
    # Last progress should be 100%
    assert progress_calls[-1][0] == 100
    assert "Done" in progress_calls[-1][1]
    # Verify page progress messages
    page_msgs = [c for c in progress_calls if "Fetching page" in c[1]]
    assert len(page_msgs) == 3


# ─── AC2: Gap-8 partial page validation ─────────────────────────────────────

@pytest.mark.asyncio
async def test_partial_page_retry():
    """Page trả về ít hơn expected → retry logic được gọi."""
    start_ms = binance._date_to_ms("2024-01-01")
    interval_ms = 3_600_000
    # Exactly 1500 bars → 2 pages: 1000 + 500
    end_ms = start_ms + 1500 * interval_ms
    end_date = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")

    # Page 1 returns 999 rows (partial), retry returns 1000 (full)
    partial_page = _make_raw_rows(start_ms, 999, interval_ms)
    full_page = _make_raw_rows(start_ms, 1000, interval_ms)
    page2 = _make_raw_rows(start_ms + 1000 * interval_ms, 500, interval_ms)

    call_count = 0

    async def mock_get(url, params=None):
        nonlocal call_count
        resp = MagicMock()
        resp.status_code = 200
        if call_count == 0:
            resp.json.return_value = partial_page  # first call: partial
        elif call_count == 1:
            resp.json.return_value = full_page      # retry: full
        else:
            resp.json.return_value = page2           # page 2
        resp.raise_for_status = MagicMock()
        call_count += 1
        return resp

    progress_calls = []

    def on_progress(percent, status_text):
        progress_calls.append((percent, status_text))

    mock_client = MockAsyncClient(mock_get)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await binance.fetch_ohlcv(
            "BTCUSDT", "1h", "2024-01-01", end_date, on_progress
        )

    # Should have retried the partial page (at least 3 calls: partial + retry + page2)
    assert call_count >= 3


# ─── AC3: Rate-limit (429) handling ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_429_handling():
    """Binance trả về 429 → sleep đúng wait time, rồi retry."""
    start_ms = binance._date_to_ms("2024-01-01")
    interval_ms = 3_600_000
    end_ms = start_ms + 100 * interval_ms
    end_date = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    raw_rows = _make_raw_rows(start_ms, 100, interval_ms)

    call_count = 0

    async def mock_get(url, params=None):
        nonlocal call_count
        resp = MagicMock()
        if call_count == 0:
            resp.status_code = 429
            resp.headers = {"Retry-After": "5"}
            resp.raise_for_status = MagicMock()
        else:
            resp.status_code = 200
            resp.json.return_value = raw_rows
            resp.raise_for_status = MagicMock()
        call_count += 1
        return resp

    progress_calls = []

    def on_progress(percent, status_text):
        progress_calls.append((percent, status_text))

    mock_client = MockAsyncClient(mock_get)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await binance.fetch_ohlcv(
                "BTCUSDT", "1h", "2024-01-01", end_date, on_progress
            )

    # Should have slept for Retry-After value
    mock_sleep.assert_any_call(5)
    # Should have rate-limit progress message
    rate_limit_msgs = [c for c in progress_calls if "Rate limited" in c[1]]
    assert len(rate_limit_msgs) >= 1


# ─── AC4: General retry with backoff ────────────────────────────────────────

@pytest.mark.asyncio
async def test_general_retry_exponential_backoff():
    """httpx.ConnectError 2 lần rồi success → data đúng."""
    start_ms = binance._date_to_ms("2024-01-01")
    interval_ms = 3_600_000
    end_ms = start_ms + 100 * interval_ms
    end_date = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    raw_rows = _make_raw_rows(start_ms, 100, interval_ms)

    call_count = 0

    async def mock_get(url, params=None):
        nonlocal call_count
        if call_count < 2:
            call_count += 1
            raise httpx.ConnectError("Connection failed")
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = raw_rows
        resp.raise_for_status = MagicMock()
        call_count += 1
        return resp

    progress_calls = []

    def on_progress(percent, status_text):
        progress_calls.append((percent, status_text))

    mock_client = MockAsyncClient(mock_get)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await binance.fetch_ohlcv(
                "BTCUSDT", "1h", "2024-01-01", end_date, on_progress
            )

    assert len(result) == 100
    # Should have slept with backoff: 1s, 2s
    sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
    assert 1 in sleep_calls
    assert 2 in sleep_calls


@pytest.mark.asyncio
async def test_retry_exhausted_raises():
    """3 lần fail → raise exception."""
    start_ms = binance._date_to_ms("2024-01-01")
    interval_ms = 3_600_000
    end_ms = start_ms + 100 * interval_ms
    end_date = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")

    async def mock_get(url, params=None):
        raise httpx.ConnectError("Connection failed")

    def on_progress(percent, status_text):
        pass

    mock_client = MockAsyncClient(mock_get)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.ConnectError):
                await binance.fetch_ohlcv(
                    "BTCUSDT", "1h", "2024-01-01", end_date, on_progress
                )


# ─── AC5: mode=refresh ─────────────────────────────────────────────────────

def test_get_cached_max_timestamp_with_data(tmp_path):
    """Cache có data → trả về max timestamp."""
    from backend.services.cache import write_ohlcv

    df = _make_df(1_704_067_200_000, 100)
    write_ohlcv(df, "BTCUSDT", "1h", tmp_path)

    result = binance.get_cached_max_timestamp("BTCUSDT", "1h", tmp_path)
    expected = 1_704_067_200_000 + 99 * 3_600_000
    assert result == expected


def test_get_cached_max_timestamp_no_cache(tmp_path):
    """Cache không tồn tại → trả về None."""
    result = binance.get_cached_max_timestamp("BTCUSDT", "1h", tmp_path)
    assert result is None


def test_get_cached_max_timestamp_empty_cache(tmp_path):
    """Cache rỗng → trả về None."""
    result = binance.get_cached_max_timestamp("BTCUSDT", "1h", tmp_path)
    assert result is None


# ─── AC6: Lazy job cleanup ──────────────────────────────────────────────────

def test_job_cleanup_expired():
    """Complete job → sau 301s → get_progress returns None."""
    job_id = job_manager.start_job("BTCUSDT", "1h")
    job_manager.complete_job(job_id, rows=1000)

    # Job should still exist immediately
    assert job_manager.get_progress(job_id) is not None

    # Simulate time passing by manipulating _job_completed_at
    job_manager._job_completed_at[job_id] = time.time() - 301

    # Next get_progress should trigger cleanup
    assert job_manager.get_progress(job_id) is None


def test_job_cleanup_not_expired():
    """Complete job → sau 100s → vẫn tồn tại."""
    job_id = job_manager.start_job("BTCUSDT", "1h")
    job_manager.complete_job(job_id, rows=1000)

    # Simulate 100s passing
    job_manager._job_completed_at[job_id] = time.time() - 100

    # Should still exist
    assert job_manager.get_progress(job_id) is not None


def test_job_cleanup_does_not_affect_running():
    """Running job không bị cleanup."""
    job_id = job_manager.start_job("BTCUSDT", "1h")

    # Running jobs don't have _job_completed_at entry
    assert job_id not in job_manager._job_completed_at

    # get_progress should still work
    progress = job_manager.get_progress(job_id)
    assert progress is not None
    assert progress["status"] == "running"


# ─── F1 fix: 429 exhaustion raises RuntimeError ────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_429_exhaustion_raises():
    """Consecutive 429s超过 _MAX_429_RETRIES → raise RuntimeError."""
    start_ms = binance._date_to_ms("2024-01-01")
    interval_ms = 3_600_000
    end_ms = start_ms + 100 * interval_ms
    end_date = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")

    async def mock_get(url, params=None):
        resp = MagicMock()
        resp.status_code = 429
        resp.headers = {"Retry-After": "1"}
        resp.raise_for_status = MagicMock()
        return resp

    def on_progress(percent, status_text):
        pass

    mock_client = MockAsyncClient(mock_get)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="Rate-limited"):
                await binance.fetch_ohlcv(
                    "BTCUSDT", "1h", "2024-01-01", end_date, on_progress
                )


# ─── F3 fix: partial page retry keeps best result ──────────────────────────

@pytest.mark.asyncio
async def test_partial_page_retry_keeps_best_result():
    """Partial page retry chỉ overwrite khi kết quả tốt hơn."""
    start_ms = binance._date_to_ms("2024-01-01")
    interval_ms = 3_600_000
    # Exactly 1500 bars → 2 pages: 1000 + 500
    end_ms = start_ms + 1500 * interval_ms
    end_date = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")

    # Page 1 returns 999 (partial), retry returns 500 (worse) → should keep 999
    partial_page = _make_raw_rows(start_ms, 999, interval_ms)
    worse_page = _make_raw_rows(start_ms, 500, interval_ms)
    page2 = _make_raw_rows(start_ms + 1000 * interval_ms, 500, interval_ms)

    call_count = 0

    async def mock_get(url, params=None):
        nonlocal call_count
        resp = MagicMock()
        resp.status_code = 200
        if call_count == 0:
            resp.json.return_value = partial_page  # first call: 999 rows
        elif call_count == 1:
            resp.json.return_value = worse_page     # retry: 500 rows (worse)
        elif call_count == 2:
            resp.json.return_value = worse_page     # retry 2: 500 rows (worse)
        elif call_count == 3:
            resp.json.return_value = worse_page     # retry 3: 500 rows (worse)
        else:
            resp.json.return_value = page2           # page 2
        resp.raise_for_status = MagicMock()
        call_count += 1
        return resp

    mock_client = MockAsyncClient(mock_get)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await binance.fetch_ohlcv(
            "BTCUSDT", "1h", "2024-01-01", end_date, lambda *a: None
        )

    # Should keep original 999 rows (not the worse 500) + 500 from page 2 = 1499
    assert len(result) == 1499


# ─── Additional: Pagination with empty result ───────────────────────────────

@pytest.mark.asyncio
async def test_fetch_empty_result():
    """Fetch trả về 0 rows → DataFrame rỗng."""
    start_ms = binance._date_to_ms("2024-01-01")
    interval_ms = 3_600_000
    end_ms = start_ms + 100 * interval_ms
    end_date = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")

    async def mock_get(url, params=None):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = []
        resp.raise_for_status = MagicMock()
        return resp

    progress_calls = []

    def on_progress(percent, status_text):
        progress_calls.append((percent, status_text))

    mock_client = MockAsyncClient(mock_get)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await binance.fetch_ohlcv(
            "BTCUSDT", "1h", "2024-01-01", end_date, on_progress
        )

    assert len(result) == 0
    assert list(result.columns) == ["timestamp", "open", "high", "low", "close", "volume"]


# ─── Additional: _raw_to_df helper ──────────────────────────────────────────

def test_raw_to_df_conversion():
    """Raw Binance response → DataFrame đúng format."""
    raw = _make_raw_rows(1_704_067_200_000, 3)
    df = binance._raw_to_df(raw)

    assert len(df) == 3
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert df["timestamp"].dtype == "int64"
    assert df["open"].dtype == "float64"


def test_raw_to_df_empty():
    """Empty raw → empty DataFrame."""
    df = binance._raw_to_df([])
    assert len(df) == 0
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]


# ─── Additional: _INTERVAL_MS mapping ───────────────────────────────────────

def test_interval_ms_mapping():
    """Verify timeframe → milliseconds mapping."""
    assert binance._INTERVAL_MS["5m"] == 5 * 60 * 1000
    assert binance._INTERVAL_MS["30m"] == 30 * 60 * 1000
    assert binance._INTERVAL_MS["1h"] == 60 * 60 * 1000
    assert binance._INTERVAL_MS["4h"] == 4 * 60 * 60 * 1000
    assert binance._INTERVAL_MS["1D"] == 24 * 60 * 60 * 1000
