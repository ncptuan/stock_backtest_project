import { eventBus } from './EventBus';
import type { OHLCVBar, LineSnapshot, TradeCompletedPayload } from './types';

export class ReplayEngine {
    private data: OHLCVBar[] = [];
    private currentIndex = 0;
    private isRunning = false;

    // Phase 2 trade tracking
    private openPosition: {
        direction: 'LONG' | 'SHORT';
        entryPrice: number;
        tpPrice: number;
        slPrice: number;
        entryBarIndex: number;
        entryTimestampMs: number;
    } | null = null;

    start(lineSnapshot: LineSnapshot, data: OHLCVBar[]): void {
        if (this.isRunning) return;
        this.data = data;
        this.currentIndex = 0;
        this.openPosition = null;
        this.isRunning = true;

        // Phase 2: notify ExportPanel replay started
        eventBus.emit('replayStateChanged', { state: 'playing' });

        // TODO (Phase 1 story): implement delta-time bar advancement loop (Gap 3)
        // For now: stub — bar loop implemented in later story
        void lineSnapshot; // suppress noImplicitAny: used by future bar loop
    }

    stop(): void {
        if (!this.isRunning) return;
        this.isRunning = false;

        // Phase 2: notify ExportPanel replay stopped
        eventBus.emit('replayStateChanged', { state: 'stopped' });
    }

    reset(): void {
        // Emit tradeCompleted for any open trade before clearing — AC2 compliance
        if (this.openPosition) {
            this.handleTradeClose(this.currentIndex, 'loss');
        }

        this.isRunning = false;
        this.currentIndex = 0;
        this.openPosition = null;

        // Phase 2: notify ExportPanel (Reset = stopped state)
        // Also triggers trades array reset in ExportPanel (Story 2.4)
        eventBus.emit('replayStateChanged', { state: 'stopped' });

        // Phase 1: notify other components
        eventBus.emit('session:reset', {});
    }

    // Called by bar advancement loop when TP or SL is detected
    // NOT called directly from outside — internal to ReplayEngine
    private handleTradeClose(
        exitBarIndex: number,
        result: 'win' | 'loss'
    ): void {
        if (!this.openPosition) return; // guard: no open position

        const payload: TradeCompletedPayload = {
            bar_index: exitBarIndex,
            entry_timestamp_ms: this.openPosition.entryTimestampMs,
            direction: this.openPosition.direction,
            entry_price: this.openPosition.entryPrice,
            tp_price: this.openPosition.tpPrice,
            sl_price: this.openPosition.slPrice,
            result,
            bars_to_exit: Math.max(0, exitBarIndex - this.openPosition.entryBarIndex),
        };

        // Phase 2: notify ExportPanel trade completed
        eventBus.emit('tradeCompleted', payload);

        // Phase 1: notify ResultsPanel (legacy event)
        eventBus.emit('replay:tradeHit', {
            type: result === 'win' ? 'tp' : 'sl',
            price: result === 'win' ? this.openPosition.tpPrice : this.openPosition.slPrice,
            barIndex: exitBarIndex,
        });

        // Clear position — prevents duplicate emit
        this.openPosition = null;
    }

    // Called by bar advancement loop when entry bar reached
    openTrade(
        barIndex: number,
        lineSnapshot: LineSnapshot,
        direction: 'LONG' | 'SHORT'
    ): void {
        if (this.openPosition) return; // guard: already in trade
        const bar = this.data[barIndex];
        if (!bar) return; // guard: out-of-bounds barIndex
        this.openPosition = {
            direction,
            entryPrice: lineSnapshot.entry,
            tpPrice: lineSnapshot.tp,
            slPrice: lineSnapshot.sl,
            entryBarIndex: barIndex,
            entryTimestampMs: bar.timestamp,
        };
    }

    // Expose for bar loop access (Phase 1 story will use this)
    getCurrentIndex(): number {
        return this.currentIndex;
    }

    // TODO (Phase 1 story): getTradeLog(), getSummary() — implements pull pattern from ADR-14
}
