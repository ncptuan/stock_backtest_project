import { eventBus } from './EventBus';
import type { ChartController } from './ChartController';
import type { OHLCVBar, LineSnapshot, TradeCompletedPayload } from './types';

export const SPEED_SLOW = 500;
export const SPEED_NORMAL = 150;
export const SPEED_FAST = 30;

export class ReplayEngine {
    private static readonly COMMISSION_RATE = 0.001; // 0.1% per side

    private data: OHLCVBar[] = [];
    private currentIndex = 0;
    private isRunning = false;
    private isPausedState = false;

    // Delta-time loop
    private lastTimestamp = 0;
    private elapsed = 0;
    private targetInterval = SPEED_NORMAL;
    private rafId = 0;
    private chartController: ChartController | null = null;
    private lineSnapshot: LineSnapshot | null = null;

    // Trade log — accumulated across session (stores full payload for rebuild)
    private tradeLog: TradeCompletedPayload[] = [];

    // Phase 2 trade tracking
    private openPosition: {
        direction: 'LONG' | 'SHORT';
        entryPrice: number;
        tpPrice: number;
        slPrice: number;
        entryBarIndex: number;
        entryTimestampMs: number;
    } | null = null;

    start(lineSnapshot: LineSnapshot, chartController: ChartController, data: OHLCVBar[]): void {
        if (this.isRunning) return;
        if (data.length === 0) return;

        this.data = data;
        this.currentIndex = 0;
        this.openPosition = null;
        this.tradeLog = [];
        this.lineSnapshot = lineSnapshot;
        this.chartController = chartController;
        this.isRunning = true;
        this.isPausedState = false;
        this.lastTimestamp = 0;
        this.elapsed = 0;

        eventBus.emit('replayStateChanged', { state: 'playing' });

        // Sync overlays to bar 0 immediately (before first tick)
        this.chartController?.revealBar(0);
        eventBus.emit('replay:barAdvanced', { barIndex: 0, timestamp: data[0]?.timestamp ?? 0 });

        this.rafId = requestAnimationFrame((ts) => this.tick(ts));
    }

    pause(): void {
        if (!this.isRunning || this.isPausedState) return;
        this.isPausedState = true;
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
            this.rafId = 0;
        }
        eventBus.emit('replayStateChanged', { state: 'paused' });
    }

    resume(): void {
        if (!this.isRunning || !this.isPausedState) return;
        this.isPausedState = false;
        this.lastTimestamp = 0; // reset to avoid gap accumulation
        eventBus.emit('replayStateChanged', { state: 'playing' });
        this.rafId = requestAnimationFrame((ts) => this.tick(ts));
    }

    stop(): void {
        if (!this.isRunning) return;
        this.isRunning = false;
        this.isPausedState = false;
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
            this.rafId = 0;
        }
        eventBus.emit('replayStateChanged', { state: 'stopped' });
    }

    reset(): void {
        // Emit tradeCompleted for any open trade before clearing
        if (this.openPosition) {
            const bar = this.data[this.currentIndex];
            const closePrice = bar ? this.normalize(bar.close) : this.openPosition.slPrice;
            const result = closePrice >= this.openPosition.entryPrice ? 'win' : 'loss';
            this.handleTradeClose(this.currentIndex, result, closePrice, 'auto');
        }

        this.isRunning = false;
        this.isPausedState = false;
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
            this.rafId = 0;
        }
        this.currentIndex = 0;
        this.openPosition = null;
        this.tradeLog = [];
        this.elapsed = 0;
        this.lastTimestamp = 0;

        eventBus.emit('replayStateChanged', { state: 'stopped' });
        eventBus.emit('session:reset', {});
    }

    getSummary(): { total: number; wins: number; losses: number; winRate: number; totalPnl: number } {
        const wins = this.tradeLog.filter(t => t.result === 'win').length;
        const losses = this.tradeLog.length - wins;
        return {
            total: this.tradeLog.length,
            wins,
            losses,
            winRate: this.tradeLog.length > 0 ? (wins / this.tradeLog.length) * 100 : 0,
            totalPnl: Math.round(this.tradeLog.reduce((sum, t) => sum + t.pnl_percent, 0) * 100) / 100,
        };
    }

    setSpeed(ms: number): void {
        // Clamp to valid range — prevent 0/negative causing frame-rate advancement
        this.targetInterval = Math.max(ms, SPEED_FAST);
        // Reset elapsed to prevent burst advancement when switching to slower speed
        this.elapsed = 0;
    }

    getSpeed(): number {
        return this.targetInterval;
    }

    isPlaying(): boolean {
        return this.isRunning && !this.isPausedState;
    }

    isPaused(): boolean {
        return this.isRunning && this.isPausedState;
    }

    private tick(now: number): void {
        if (!this.isRunning || this.isPausedState) return;

        if (this.lastTimestamp === 0) {
            this.lastTimestamp = now;
            this.rafId = requestAnimationFrame((ts) => this.tick(ts));
            return;
        }

        const delta = now - this.lastTimestamp;
        this.lastTimestamp = now;

        // Clamp: if tab was throttled, only advance 1 bar
        const clampedDelta = delta > this.targetInterval * 3
            ? this.targetInterval
            : delta;

        this.elapsed += clampedDelta;

        // Advance max 1 bar per tick for consistent feel
        if (this.elapsed >= this.targetInterval) {
            this.elapsed -= this.targetInterval;
            this.advanceBar();
        }

        // Auto-stop when out of data
        if (this.currentIndex >= this.data.length) {
            this.isRunning = false;
            this.rafId = 0;
            eventBus.emit('replayStateChanged', { state: 'stopped' });
            return;
        }

        this.rafId = requestAnimationFrame((ts) => this.tick(ts));
    }

    private advanceBar(): void {
        this.currentIndex++;

        const bar = this.data[this.currentIndex];
        if (bar) {
            eventBus.emit('replay:barAdvanced', {
                barIndex: this.currentIndex,
                timestamp: bar.timestamp,
            });
        }

        // Reveal bars up to current index on chart
        this.chartController?.revealBar(this.currentIndex);

        // Hit detection after bar reveal
        if (bar && this.lineSnapshot) {
            this.checkHits(bar);
        }

        // Auto-close at last bar if position still open
        if (this.currentIndex >= this.data.length - 1 && this.openPosition) {
            const closePrice = this.normalize(bar.close);
            const result = closePrice >= this.openPosition.entryPrice ? 'win' : 'loss';
            this.handleTradeClose(this.currentIndex, result, closePrice, 'auto');
        }
    }

    private normalize(price: number): number {
        return Math.round(price * 100) / 100;
    }

    private checkHits(bar: OHLCVBar): void {
        if (!this.lineSnapshot) return;

        const high = this.normalize(bar.high);
        const low = this.normalize(bar.low);
        const open = this.normalize(bar.open);
        const close = this.normalize(bar.close);

        const entry = this.normalize(this.lineSnapshot.entry);
        const tp = this.normalize(this.lineSnapshot.tp);
        const sl = this.normalize(this.lineSnapshot.sl);

        // Entry check — only when no position
        if (!this.openPosition) {
            if (high >= entry) {
                // Enter at next bar's open (AC#1: no intra-candle)
                const nextBar = this.data[this.currentIndex + 1];
                if (nextBar) {
                    const fillPrice = this.normalize(nextBar.open);
                    this.openTrade(this.currentIndex + 1, fillPrice, this.lineSnapshot.tp, this.lineSnapshot.sl, 'LONG');
                }
                // If last bar, no entry — no next bar to enter on
            }
            return;
        }

        // TP/SL checks — only after entry bar
        if (this.currentIndex <= this.openPosition.entryBarIndex) return;

        const tpHit = high >= tp;
        const slHit = low <= sl;

        // Gap-down: open below SL → slippage at open (AC#4) — priority over TP
        if (slHit && open < sl) {
            this.handleTradeClose(this.currentIndex, 'loss', open);
        } else if (tpHit && slHit) {
            // Same bar: priority by candle direction (AC#2)
            const isBullish = close > open;
            if (isBullish) {
                this.handleTradeClose(this.currentIndex, 'win');  // TP first
            } else {
                this.handleTradeClose(this.currentIndex, 'loss'); // SL first
            }
        } else if (tpHit) {
            this.handleTradeClose(this.currentIndex, 'win');
        } else if (slHit) {
            this.handleTradeClose(this.currentIndex, 'loss');
        }
    }

    private calcPnL(entryPrice: number, exitPrice: number): number {
        const rawPnl = ((exitPrice - entryPrice) / entryPrice) * 100;
        const commission = ReplayEngine.COMMISSION_RATE * 2 * 100; // 0.2% total
        return Math.round((rawPnl - commission) * 100) / 100;
    }

    // Called by bar advancement loop when TP or SL is detected
    private handleTradeClose(
        exitBarIndex: number,
        result: 'win' | 'loss',
        exitPrice?: number,
        closeReason?: 'tp' | 'sl' | 'auto'
    ): void {
        if (!this.openPosition) return;

        // Use provided exit price or TP/SL from snapshot
        const actualExitPrice = exitPrice ?? (result === 'win'
            ? this.openPosition.tpPrice
            : this.openPosition.slPrice);

        const pnl = this.calcPnL(this.openPosition.entryPrice, actualExitPrice);
        const reason = closeReason ?? (result === 'win' ? 'tp' : 'sl');

        const payload: TradeCompletedPayload = {
            bar_index: exitBarIndex,
            entry_bar_index: this.openPosition.entryBarIndex,
            entry_timestamp_ms: this.openPosition.entryTimestampMs,
            direction: this.openPosition.direction,
            entry_price: this.openPosition.entryPrice,
            tp_price: this.openPosition.tpPrice,
            sl_price: this.openPosition.slPrice,
            actual_exit_price: actualExitPrice,
            result,
            close_reason: reason,
            bars_to_exit: Math.max(0, exitBarIndex - this.openPosition.entryBarIndex),
            pnl_percent: pnl,
        };

        // Accumulate in trade log for getSummary() + marker rebuild
        this.tradeLog.push(payload);

        eventBus.emit('tradeCompleted', payload);
        eventBus.emit('replay:tradeHit', {
            type: reason === 'auto' ? (result === 'win' ? 'tp' : 'sl') : reason,
            price: actualExitPrice,
            barIndex: exitBarIndex,
        });

        this.openPosition = null;
    }

    openTrade(
        barIndex: number,
        fillPrice: number,
        tpPrice: number,
        slPrice: number,
        direction: 'LONG' | 'SHORT'
    ): void {
        if (this.openPosition) return;
        const bar = this.data[barIndex];
        if (!bar) return;
        this.openPosition = {
            direction,
            entryPrice: fillPrice,
            tpPrice,
            slPrice,
            entryBarIndex: barIndex,
            entryTimestampMs: bar.timestamp,
        };

        eventBus.emit('replay:tradeHit', {
            type: 'entry',
            price: fillPrice,
            barIndex,
        });
    }

    getCurrentIndex(): number {
        return this.currentIndex;
    }

    canStep(): boolean {
        return this.isRunning && this.isPausedState;
    }

    stepForward(): void {
        if (!this.canStep()) return;
        if (this.currentIndex >= this.data.length - 1) return;
        this.currentIndex++;
        this._emitBarAdvanced();
        this.chartController?.revealBar(this.currentIndex);

        // Hit detection on step
        const bar = this.data[this.currentIndex];
        if (bar && this.lineSnapshot) {
            this.checkHits(bar);
        }

        // Auto-close at last bar
        if (this.currentIndex >= this.data.length - 1 && this.openPosition) {
            const closePrice = this.normalize(bar.close);
            const result = closePrice >= this.openPosition.entryPrice ? 'win' : 'loss';
            this.handleTradeClose(this.currentIndex, result, closePrice, 'auto');
        }
    }

    stepBack(): void {
        if (!this.canStep()) return;
        if (this.currentIndex <= 0) return;
        this.currentIndex--;
        // Clear open position — stepping back invalidates trades at later bars
        this.openPosition = null;
        // Prune trade log entries that closed beyond current index
        this.tradeLog = this.tradeLog.filter(t => t.bar_index <= this.currentIndex);
        // Clear and rebuild trade markers + rows for remaining valid trades
        eventBus.emit('session:reset', {});
        for (const trade of this.tradeLog) {
            eventBus.emit('replay:tradeHit', { type: 'entry', price: trade.entry_price, barIndex: trade.entry_bar_index });
            eventBus.emit('replay:tradeHit', {
                type: trade.close_reason === 'auto' ? (trade.result === 'win' ? 'tp' : 'sl') : trade.close_reason,
                price: trade.actual_exit_price,
                barIndex: trade.bar_index,
            });
            eventBus.emit('tradeCompleted', trade);
        }
        eventBus.emit('session:rebuilt', {});
        this._emitBarAdvanced();
        this.chartController?.revealBar(this.currentIndex);
    }

    private _emitBarAdvanced(): void {
        const bar = this.data[this.currentIndex];
        if (bar) {
            eventBus.emit('replay:barAdvanced', {
                barIndex: this.currentIndex,
                timestamp: bar.timestamp,
            });
        }
    }
}
