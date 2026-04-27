"""
backend/services/supabase.py
Story 3.1: Write functions for signal_comparisons and signal_cases via PostgREST.

Key rules (NFR5, NFR6, NFR12):
- signal_comparisons: uses ANON key (supabase_key), RLS disabled
- signal_cases: uses SERVICE ROLE key (supabase_service_key), RLS enabled
- No credentials hardcoded — all from Settings
- Atomic: write signal_comparisons first, then signal_cases; rollback on partial failure
"""
import logging
import re
from datetime import datetime, timezone

import httpx

from backend.models import ExportTrade, ExportRequest
from backend.settings import Settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate_signal_id(session_date: str, strategy_name: str, bar_index: int) -> str:
    """
    Generate a sortable, unique signal ID.

    session_date: "20260426"  (yyyymmdd)
    strategy_name: user input — sanitized to lowercase, non-alphanumeric → "_"
    bar_index: zero-padded to 5 digits

    Examples:
        generate_signal_id("20260426", "breakout_4h", 42)
            → "backtest_20260426_breakout_4h_00042"
        generate_signal_id("20260426", "Breakout 4H / EMA", 42)
            → "backtest_20260426_breakout_4h_ema_00042"
    """
    sanitized = re.sub(r'[^a-z0-9]+', '_', strategy_name.lower()).strip('_')
    return f"backtest_{session_date}_{sanitized}_{bar_index:05d}"


def _map_direction_to_verdict(direction: str) -> str:
    """LONG → BUY, SHORT → SELL"""
    return "BUY" if direction.upper() == "LONG" else "SELL"


def _map_result_to_follow(result: str) -> str:
    """win → TP hit, loss → SL hit"""
    return "TP hit" if result.lower() == "win" else "SL hit"


def _map_result_to_outcome(result: str) -> str:
    """win → TP_HIT, loss → SL_HIT"""
    return "TP_HIT" if result.lower() == "win" else "SL_HIT"


def _parse_session_date(session_filename: str) -> str:
    """
    Extract yyyymmdd from filename.

    "BTCUSDT_4h_20260420.parquet" → "20260420"
    Falls back to "00000000" if parse fails.
    """
    try:
        stem = session_filename.rsplit('.', 1)[0]   # "BTCUSDT_4h_20260420"
        parts = stem.split('_')
        candidate = parts[-1]
        if len(candidate) == 8 and candidate.isdigit():
            return candidate
    except Exception:
        pass
    logger.warning("_parse_session_date: could not extract date from %r — using '00000000'", session_filename)
    return "00000000"


def _parse_supabase_error(resp: httpx.Response, table_name: str) -> ValueError:
    """
    Parse Supabase/PostgREST error response and return a descriptive ValueError.

    PostgreSQL type mismatch error code: 42804
    Example body: {"code": "42804", "message": "column \"timestamp\" is of type bigint..."}
    """
    try:
        body = resp.json()
        pg_code = str(body.get("code", ""))
        pg_message = body.get("message", "")

        if pg_code == "42804":
            return ValueError(f"Schema mismatch: {pg_message}")

        # Generic structured error with a message
        if pg_message:
            return ValueError(f"{table_name} write failed: {resp.status_code} — {pg_message}")
    except Exception:
        pass

    # Fallback to raw text (truncated to avoid giant error messages)
    return ValueError(f"{table_name} write failed: {resp.status_code} — {resp.text[:200]}")


# ---------------------------------------------------------------------------
# Supabase PostgREST operations
# ---------------------------------------------------------------------------

async def validate_credentials(settings: Settings) -> None:
    """
    Validate Supabase credentials before any write operation.
    Makes lightweight GET requests to test API key validity.

    Raises ValueError with actionable message if 401 (invalid credentials).
    Non-401 errors (404, 500, network) are NOT raised here — they will be
    caught during the actual write operations.
    """
    base_url = f"{settings.supabase_url}/rest/v1"

    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Validate anon key (signal_comparisons access)
        resp_anon = await client.get(
            f"{base_url}/signal_comparisons",
            headers={
                "apikey": settings.supabase_key,
                "Authorization": f"Bearer {settings.supabase_key}",
            },
            params={"limit": "1"},
        )
        if resp_anon.status_code == 401:
            raise ValueError(
                "SUPABASE_KEY không hợp lệ — Kiểm tra anon key trong .env "
                "(dùng cho signal_comparisons)"
            )

        # 2. Validate service role key (signal_cases access)
        resp_service = await client.get(
            f"{base_url}/signal_cases",
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
            },
            params={"limit": "1"},
        )
        if resp_service.status_code == 401:
            raise ValueError(
                "SUPABASE_SERVICE_KEY không hợp lệ — Kiểm tra service role key trong .env "
                "(dùng cho signal_cases, RLS enabled)"
            )


async def check_duplicate(
    session_date: str,
    strategy_name: str,
    settings: Settings,
) -> bool:
    """
    Query signal_comparisons for any row matching the (date, strategy) prefix.
    Returns True if duplicate detected.
    On query error, returns False (do NOT block export on connectivity issues).
    """
    sanitized = re.sub(r'[^a-z0-9]+', '_', strategy_name.lower()).strip('_')
    pattern = f"backtest_{session_date}_{sanitized}_"

    url = f"{settings.supabase_url}/rest/v1/signal_comparisons"
    headers = {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
    }
    params = {
        "signal_id": f"like.{pattern}%",
        "select": "signal_id",
        "limit": "1",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            return len(resp.json()) > 0
        # On query error, do not block export
        return False


async def write_signal_comparisons(
    trades: list[ExportTrade],
    request: ExportRequest,
    settings: Settings,
) -> int:
    """
    Bulk-insert all trades into signal_comparisons using ANON key.
    Returns count of rows written.
    Raises ValueError on non-2xx response.
    Raises httpx.TimeoutException on timeout.
    """
    session_date = _parse_session_date(request.session_filename)
    rows = []
    for trade in trades:
        signal_id = generate_signal_id(session_date, request.strategy_name, trade.bar_index)
        rows.append({
            "signal_id": signal_id,
            "timestamp": trade.entry_timestamp_ms,
            "type": trade.direction.upper(),
            "bot_verdict": _map_direction_to_verdict(trade.direction),
            "result": trade.result.lower(),
            "follow": _map_result_to_follow(trade.result),
            "invalidation_condition": f"SL tại {trade.sl_price}",
            "telegram_sent": False,
            "claude_verdict": None,
        })

    url = f"{settings.supabase_url}/rest/v1/signal_comparisons"
    headers = {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=rows)
        if resp.status_code not in (200, 201, 204):
            raise _parse_supabase_error(resp, "signal_comparisons")

    return len(rows)


async def write_signal_cases(
    trades: list[ExportTrade],
    request: ExportRequest,
    settings: Settings,
) -> int:
    """
    Bulk-insert all trades into signal_cases using SERVICE ROLE key (bypasses RLS).
    Returns count of rows written.
    Raises ValueError on non-2xx response (incl. auth errors).
    Raises httpx.TimeoutException on timeout.
    """
    session_date = _parse_session_date(request.session_filename)
    rows = []
    for trade in trades:
        signal_id = generate_signal_id(session_date, request.strategy_name, trade.bar_index)
        signal_sent_at = datetime.fromtimestamp(
            trade.entry_timestamp_ms / 1000, tz=timezone.utc
        ).isoformat()
        action = _map_direction_to_verdict(trade.direction)
        rows.append({
            "signal_id": signal_id,
            "signal_sent_at": signal_sent_at,
            "market_regime": "unknown",
            "claude_action": action,
            "bot_action": action,
            "outcome": _map_result_to_outcome(trade.result),
            "reasoning_summary": trade.reasoning_summary,
            "invalidation_condition": f"SL tại {trade.sl_price}",
            "metadata": {
                "entry_price": trade.entry_price,
                "tp_price": trade.tp_price,
                "sl_price": trade.sl_price,
                "bars_to_exit": trade.bars_to_exit,
                "timeframe": request.timeframe,
                "schema_version": "1.0",
            },
        })

    url = f"{settings.supabase_url}/rest/v1/signal_cases"
    headers = {
        "apikey": settings.supabase_service_key,
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=rows)
        if resp.status_code not in (200, 201, 204):
            raise _parse_supabase_error(resp, "signal_cases")

    return len(rows)


async def rollback_signal_comparisons(
    session_date: str,
    strategy_name: str,
    settings: Settings,
) -> int:
    """
    DELETE FROM signal_comparisons WHERE signal_id LIKE 'backtest_{date}_{strategy}_%'.
    Returns count of deleted rows from Content-Range header (0 if unavailable).
    Uses ANON key.
    """
    sanitized = re.sub(r'[^a-z0-9]+', '_', strategy_name.lower()).strip('_')
    pattern = f"backtest_{session_date}_{sanitized}_"

    url = f"{settings.supabase_url}/rest/v1/signal_comparisons"
    headers = {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
        "Prefer": "return=minimal,count=exact",
    }
    params = {"signal_id": f"like.{pattern}%"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(url, headers=headers, params=params)
        if resp.status_code not in (200, 204):
            raise _parse_supabase_error(resp, "signal_comparisons rollback")
        # PostgREST returns count in Content-Range: "0-N/N"
        count_header = resp.headers.get("content-range", "")
        try:
            deleted = int(count_header.split("/")[-1]) if "/" in count_header else 0
        except (ValueError, IndexError):
            deleted = 0
        return deleted
