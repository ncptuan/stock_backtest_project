// EventMap — typed contract giữa tất cả emitters và listeners
// Phase 1 events (namespace:camelCase per ADR Gap 13)
// Phase 2 events (flat names per Epic 1 Story 1.2 spec — không namespace)
export interface EventMap {
    // Phase 1 events
    'replay:barAdvanced': { barIndex: number; timestamp: number };
    'replay:tradeHit': { type: 'entry' | 'tp' | 'sl'; price: number; barIndex: number };
    'drawing:lineChanged': { type: 'entry' | 'tp' | 'sl'; price: number };
    'session:reset': Record<string, never>;

    // Phase 2 events — ExportPanel listens to these
    replayStateChanged: { state: 'playing' | 'paused' | 'stopped' };
    tradeCompleted: TradeCompletedPayload;
}

// Phase 2 trade payload — 8 fields required by Epic 1 AC
export interface TradeCompletedPayload {
    bar_index: number;           // bar index khi trade CLOSE (exit bar)
    entry_timestamp_ms: number;  // Unix ms UTC của entry candle (ADR-03)
    direction: 'LONG' | 'SHORT';
    entry_price: number;
    tp_price: number;
    sl_price: number;
    result: 'win' | 'loss';
    bars_to_exit: number;        // exit_bar_index - entry_bar_index
}

// Shared types (used by EventMap payloads and components)
export interface OHLCVBar {
    timestamp: number;  // Unix ms int64 (ADR-03)
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

export interface LineSnapshot {
    entry: number;  // price frozen tại Play time
    tp: number;
    sl: number;
}

export interface IndicatorValues {
    ema20: number | null;
    ema50: number | null;
}

export interface Trade {
    barIndex: number;
    direction: 'LONG' | 'SHORT';
    entryPrice: number;
    tpPrice: number;
    slPrice: number;
    result: 'win' | 'loss';
    pnl: number;
    commission: number;
}

// --- Phase 2: API response types ---

export interface SessionItem {
    filename: string;    // "BTCUSDT_4h_20260420.parquet"
    symbol: string;      // "BTCUSDT"
    timeframe: string;   // "4h"
    date: string;        // "2026-04-20"
    exported: boolean;   // hardcoded false from backend (Story 3.3 implements tracking)
}

export interface ApiError {
    message: string;
    code: string;
    retryable: boolean;
}

// Generic API response shape (matches backend APIResponse[T])
export interface ApiResponse<T> {
    data: T | null;
    error: ApiError | null;
}

export type SessionsApiResponse = ApiResponse<SessionItem[]>;

// --- Phase 2: Preview response types ---

export interface TradePreviewItem {
    bar_index: number;
    entry_timestamp_ms: number;       // Unix ms int64 (ADR-03)
    direction: 'LONG' | 'SHORT';
    entry_price: number;
    tp_price: number;
    sl_price: number;
    result: 'win' | 'loss';
    bars_to_exit: number;
    reasoning_template: string;       // Pre-filled từ backend — editable by user
}

export interface PreviewResponse {
    symbol: string;                   // "BTCUSDT"
    timeframe: string;                // "4h"
    date: string;                     // "2026-04-20"
    trade_count: number;
    win_rate: number;                 // 0.67 (not percentage)
    quality_gate: 'pass' | 'fail';
    quality_gate_reason: string | null; // null khi pass
    trades: TradePreviewItem[];
}

export type PreviewApiResponse = ApiResponse<PreviewResponse>;

// --- Epic 3: Export overlay types ---

// Shape of `exportpreview:confirmed` CustomEvent detail (dispatched by ExportPreview.ts)
export interface ExportConfirmedPayload {
    filename: string;           // "BTCUSDT_4h_20260420.parquet"
    strategy_name: string;      // User-edited, default "{symbol}_{timeframe}"
    trades: Array<TradePreviewItem & { reasoning_summary: string }>;
    session_win_rate: number;   // Float: 0.67
    timeframe: string;          // "4h"
}

// Shape of APIResponse<ExportResponse>.data from POST /api/export
export interface ExportSuccessData {
    signal_comparisons_count: number;
    signal_cases_count: number;
    first_signal_id: string;    // "backtest_20260426_breakout_4h_00042"
    supabase_url: string;       // Link to verify in Supabase dashboard
}
