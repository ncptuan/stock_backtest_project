"""
Preview service — Story 2.1.

Business logic cho POST /api/sessions/{filename}/preview:
  - compute_quality_gate: kiểm tra trade count >= 10 và win_rate >= 55%
  - compute_reasoning_template: EMA20/EMA50/volume với slice-first (Gap-1 no look-ahead)
  - build_preview: orchestrate cả hai, đọc Parquet, trả về PreviewResponse
"""
import asyncio
import re
from pathlib import Path

import pandas as pd

from backend.models import (
    PreviewResponse,
    TradeInput,
    TradePreviewItem,
)

_SESSION_FILENAME_PATTERN = re.compile(
    r"^([A-Z0-9]+)_([A-Za-z0-9]+)_(\d{8})\.parquet$"
)


def compute_quality_gate(trades: list[TradeInput]) -> tuple[str, str | None]:
    """
    Kiểm tra quality gate:
      - trade_count >= 10
      - win_rate >= 55%

    Trả về ("pass", None) hoặc ("fail", reason_string).
    Khi cả hai fail: reason = "{trade_reason}; {winrate_reason}".
    """
    trade_count = len(trades)
    win_count = sum(1 for t in trades if t.result == "win")
    win_rate = win_count / trade_count if trade_count > 0 else 0.0

    if trade_count == 0:
        return "fail", "0 trades — cần tối thiểu 10"

    reasons: list[str] = []
    if trade_count < 10:
        reasons.append(f"{trade_count} trades — cần tối thiểu 10")
    if win_rate < 0.55:
        pct = int(round(win_rate * 100))
        reasons.append(f"{pct}% win rate — cần tối thiểu 55%")

    if reasons:
        return "fail", "; ".join(reasons)
    return "pass", None


def compute_reasoning_template(
    df: pd.DataFrame,
    trade: TradeInput,
    timeframe: str,
) -> str:
    """
    Compute reasoning template cho một trade.

    CRITICAL — Gap-1 (slice-first, no look-ahead):
      df.iloc[:bar_index] — slice TRƯỚC khi compute EMA/volume.
      EMA tại bar_index-1 (candle TRƯỚC entry) = không nhìn vào tương lai.

    Ví dụ: bar_index=42 → sliced_df = df.iloc[:42] (rows 0–41)
    """
    bar_index = trade.bar_index
    # Guard: clamp to valid range
    bar_index = max(1, min(bar_index, len(df)))

    sliced_df = df.iloc[:bar_index]  # slice-first, Gap-1 compliance

    close_series = sliced_df["close"]
    volume_series = sliced_df["volume"]

    # ADR-07: pandas built-in ewm() — zero extra dependencies
    ema20_val = close_series.ewm(span=20, adjust=False).mean().iloc[-1]
    ema50_val = close_series.ewm(span=50, adjust=False).mean().iloc[-1]

    vol_curr = volume_series.iloc[-1]
    vol_avg = volume_series.rolling(window=20, min_periods=1).mean().iloc[-1]

    def fmt_price(val: float) -> str:
        if pd.isna(val):
            return "N/A"
        return f"${val:,.0f}"

    def fmt_vol_ratio(curr: float, avg: float) -> str:
        if pd.isna(curr) or pd.isna(avg):
            return "N/Ax"
        ratio = curr / avg if avg > 0 else 1.0
        return f"{ratio:.1f}x"

    outcome = "WIN" if trade.result == "win" else "LOSS"
    tf_upper = timeframe.upper()
    entry_fmt = f"${trade.entry_price:,.0f}"

    return (
        f"{tf_upper} | Entry {entry_fmt} | "
        f"EMA20={fmt_price(ema20_val)} | EMA50={fmt_price(ema50_val)} | "
        f"Vol={fmt_vol_ratio(vol_curr, vol_avg)} | Outcome: {outcome}"
    )


async def build_preview(
    parquet_path: Path,
    filename: str,
    trades: list[TradeInput],
) -> PreviewResponse:
    """
    Đọc Parquet, compute quality gate + reasoning templates, trả về PreviewResponse.
    Route delegate hoàn toàn cho function này — không có business logic trong route.
    """
    match = _SESSION_FILENAME_PATTERN.match(filename)
    if not match:
        raise ValueError(f"Invalid session filename format: {filename}")

    symbol, timeframe, date_raw = match.groups()
    date_formatted = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}"

    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(None, pd.read_parquet, parquet_path)

    # P5: validate required columns
    _REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = _REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Parquet file missing required columns: {missing}")

    # P6: reject empty files before any .iloc[-1] access
    if len(df) == 0:
        raise ValueError("Parquet file contains no data rows")

    # Data integrity check (architecture.md rule)
    if not df["timestamp"].is_monotonic_increasing:
        raise ValueError("Session Parquet timestamps not sorted ascending")

    trade_count = len(trades)
    win_count = sum(1 for t in trades if t.result == "win")
    win_rate = win_count / trade_count if trade_count > 0 else 0.0

    quality_gate, quality_gate_reason = compute_quality_gate(trades)

    preview_trades: list[TradePreviewItem] = []
    for trade in trades:
        reasoning = compute_reasoning_template(df, trade, timeframe)
        preview_trades.append(
            TradePreviewItem(
                bar_index=trade.bar_index,
                entry_timestamp_ms=trade.entry_timestamp_ms,
                direction=trade.direction,
                entry_price=trade.entry_price,
                tp_price=trade.tp_price,
                sl_price=trade.sl_price,
                result=trade.result,
                bars_to_exit=trade.bars_to_exit,
                reasoning_template=reasoning,
            )
        )

    return PreviewResponse(
        symbol=symbol,
        timeframe=timeframe,
        date=date_formatted,
        trade_count=trade_count,
        win_rate=round(win_rate, 4),
        quality_gate=quality_gate,
        quality_gate_reason=quality_gate_reason,
        trades=preview_trades,
    )
