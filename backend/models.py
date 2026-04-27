from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class OHLCVBar(BaseModel):
    timestamp: int   # Unix ms
    open: float
    high: float
    low: float
    close: float
    volume: float


class ErrorResponse(BaseModel):
    message: str
    code: str        # "FETCH_FAILED", "CACHE_CORRUPT", etc.
    retryable: bool


class APIResponse(BaseModel, Generic[T]):
    data: T | None = None
    error: ErrorResponse | None = None


class SessionItem(BaseModel):
    """Một Parquet session file trong cache/ — metadata từ filename only."""
    filename: str           # "BTCUSDT_4h_20260420.parquet"
    symbol: str             # "BTCUSDT"
    timeframe: str          # "4h"
    date: str               # "2026-04-20" (YYYY-MM-DD format)
    exported: bool          # hardcode False — Story 3.3 sẽ implement tracking


# ─── Phase 2: Preview endpoint models ───────────────────────────────────────

class TradeInput(BaseModel):
    """
    Trade data được gửi từ frontend.
    Matches tradeCompleted EventBus payload trong types.ts.
    """
    bar_index: Annotated[int, Field(ge=1)]
    entry_timestamp_ms: int
    direction: Literal["LONG", "SHORT"]
    entry_price: Annotated[float, Field(gt=0)]
    tp_price: Annotated[float, Field(gt=0)]
    sl_price: Annotated[float, Field(gt=0)]
    result: Literal["win", "loss"]
    bars_to_exit: Annotated[int, Field(ge=0)]


class TradePreviewItem(TradeInput):
    """TradeInput + computed reasoning template từ backend."""
    reasoning_template: str


class PreviewRequest(BaseModel):
    """Request body cho POST /api/sessions/{filename}/preview."""
    trades: list[TradeInput]


class PreviewResponse(BaseModel):
    """
    Response body cho preview endpoint.
    Wrapped trong APIResponse[PreviewResponse].
    """
    symbol: str
    timeframe: str
    date: str
    trade_count: int
    win_rate: float
    quality_gate: Literal["pass", "fail"]
    quality_gate_reason: str | None = None
    trades: list[TradePreviewItem]


# ─── Epic 3: Export endpoint models ────────────────────────────────────────

class ExportTrade(BaseModel):
    bar_index: int
    entry_timestamp_ms: int           # Unix ms int64 (ADR-03)
    direction: str                    # "LONG" or "SHORT"
    entry_price: float
    tp_price: float
    sl_price: float
    result: str                       # "win" or "loss"
    bars_to_exit: int
    reasoning_summary: str            # Edited by user in ExportPreview


class ExportRequest(BaseModel):
    session_filename: str             # "BTCUSDT_4h_20260420.parquet"
    strategy_name: str                # User input, default "{symbol}_{timeframe}"
    timeframe: str                    # "4h"
    session_win_rate: float           # 0.67
    trades: list[ExportTrade]


class ExportResponse(BaseModel):
    signal_comparisons_count: int
    signal_cases_count: int
    first_signal_id: str              # "backtest_20260426_breakout_4h_00042"
    supabase_url: str                 # Link to verify in Supabase dashboard
