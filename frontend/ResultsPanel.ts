/**
 * ResultsPanel — Phase 1 component
 * Manages CompletionOverlay and StatusBar display after replay.
 * Story 1.4: Phase 2 integration points added (Supabase button + Export link).
 * Story P1-5.4: Per-trade results table with real-time update.
 */
import { sessionListPanel, isSupabaseEnabled } from './SessionListPanel';
import { eventBus } from './EventBus';
import type { ReplayEngine } from './ReplayEngine';
import type { TradeCompletedPayload } from './types';
import type { OHLCVBar } from './types';

export class ResultsPanel {
    private completionOverlay: HTMLElement | null = null;
    private statusBarEl: HTMLElement | null = null;
    private currentSessionFilename: string | null = null;
    private tradeRows: HTMLElement[] = [];
    private tableBody: HTMLElement | null = null;
    private emptyMsg: HTMLElement | null = null;
    private summaryEl: HTMLElement | null = null;
    private cachedBars: OHLCVBar[] = [];
    private replayEngine: ReplayEngine | null = null;

    constructor() {
        // Story 2.4: disable/enable Export buttons based on replay state
        document.addEventListener('exportpanel:canExport', (e: Event) => {
            const { canExport } = (e as CustomEvent<{ canExport: boolean }>).detail;
            const exportBtn = this.completionOverlay
                ?.querySelector<HTMLButtonElement>('.completion-export-btn');
            if (exportBtn) {
                exportBtn.disabled = !canExport;
                if (!canExport) {
                    exportBtn.setAttribute('aria-disabled', 'true');
                } else {
                    exportBtn.removeAttribute('aria-disabled');
                }
            }
            const exportLink = this.statusBarEl
                ?.querySelector<HTMLElement>('.statusbar-export-link');
            if (exportLink) {
                exportLink.style.pointerEvents = canExport ? 'auto' : 'none';
                exportLink.style.opacity = canExport ? '1' : '0.4';
                if (!canExport) {
                    exportLink.setAttribute('aria-disabled', 'true');
                    exportLink.setAttribute('tabindex', '-1');
                } else {
                    exportLink.removeAttribute('aria-disabled');
                    exportLink.setAttribute('tabindex', '0');
                }
            }
        });

        // P1-4.3: Clear results on session reset
        eventBus.on('session:reset', () => {
            this.dismissCompletionOverlay();
            this.clearTradeList();
        });

        // P1-5.4: Real-time trade row append
        eventBus.on('tradeCompleted', (payload) => {
            this.addTradeRow(payload);
        });

        // P1-5.4: Zero trades message on replay stop
        // P1-5.5: Session summary on replay stop
        eventBus.on('replayStateChanged', ({ state }) => {
            if (state === 'stopped') {
                this.showSummary();
            }
        });

        // P1-5.4: Cache bars for audit trail
        eventBus.on('chart:dataLoaded', ({ bars }) => {
            this.cachedBars = bars;
        });

        // P1-5.5: Rebuild summary after stepBack
        eventBus.on('session:rebuilt', () => {
            this.showSummary();
        });
    }

    init(statusBarEl: HTMLElement): void {
        this.statusBarEl = statusBarEl;
        this.tableBody = document.getElementById('results-table-body');
        this.emptyMsg = document.getElementById('results-empty-msg');
        this.summaryEl = document.getElementById('results-summary');
    }

    setReplayEngine(engine: ReplayEngine): void {
        this.replayEngine = engine;
    }

    addTradeRow(payload: TradeCompletedPayload): void {
        if (!this.tableBody) return;

        // Hide empty message if showing
        if (this.emptyMsg) this.emptyMsg.style.display = 'none';

        const num = this.tradeRows.length + 1;
        const isWin = payload.result === 'win';
        const pnlStr = (payload.pnl_percent >= 0 ? '+' : '') + payload.pnl_percent.toFixed(2) + '%';
        const exitType = payload.close_reason === 'auto' ? 'Auto' : (payload.close_reason === 'tp' ? 'TP' : 'SL');

        // Format entry timestamp (UTC+7)
        const entryDate = new Date(payload.entry_timestamp_ms + 7 * 3600 * 1000);
        const dd = String(entryDate.getUTCDate()).padStart(2, '0');
        const mm = String(entryDate.getUTCMonth() + 1).padStart(2, '0');
        const hh = String(entryDate.getUTCHours()).padStart(2, '0');
        const min = String(entryDate.getUTCMinutes()).padStart(2, '0');
        const timeStr = `${dd}/${mm} ${hh}:${min}`;

        const exitPrice = payload.actual_exit_price;
        const fmt = (v: number) => v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

        const row = document.createElement('div');
        row.className = `results-row results-row--${isWin ? 'win' : 'loss'}`;
        row.innerHTML = `
            <span class="results-num">#${num}</span>
            <span class="results-direction direction-${payload.direction.toLowerCase()}">${payload.direction}</span>
            <span class="results-entry">${fmt(payload.entry_price)}</span>
            <span class="results-exit">${fmt(exitPrice)}</span>
            <span class="results-type">${exitType}</span>
            <span class="results-pnl">${pnlStr}</span>
            <span class="results-time">${timeStr}</span>
        `;

        // Audit trail (expandable on hover)
        const bar = this.cachedBars[payload.bar_index];
        if (bar) {
            const auditDate = new Date(bar.timestamp + 7 * 3600 * 1000);
            const ad = String(auditDate.getUTCDate()).padStart(2, '0');
            const am = String(auditDate.getUTCMonth() + 1).padStart(2, '0');
            const ay = auditDate.getUTCFullYear();
            const ah = String(auditDate.getUTCHours()).padStart(2, '0');
            const amn = String(auditDate.getUTCMinutes()).padStart(2, '0');

            const audit = document.createElement('div');
            audit.className = 'results-audit';
            audit.innerHTML = `
                <div>Trigger: ${ad}/${am}/${ay} ${ah}:${amn} UTC+7</div>
                <div>O: ${fmt(bar.open)} H: ${fmt(bar.high)} L: ${fmt(bar.low)} C: ${fmt(bar.close)}</div>
            `;
            row.appendChild(audit);

            row.addEventListener('mouseenter', () => { audit.style.display = 'block'; });
            row.addEventListener('mouseleave', () => { audit.style.display = 'none'; });
        }

        this.tableBody.appendChild(row);
        this.tradeRows.push(row);
        row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    clearTradeList(): void {
        for (const row of this.tradeRows) row.remove();
        this.tradeRows = [];
        if (this.emptyMsg) this.emptyMsg.style.display = 'none';
        this.clearSummary();
    }

    private clearSummary(): void {
        if (this.summaryEl) this.summaryEl.innerHTML = '';
    }

    showSummary(): void {
        if (!this.summaryEl) return;

        const summary = this.replayEngine?.getSummary();
        if (!summary) return;

        if (summary.total === 0) {
            this.showEmptyMessage();
            return;
        }

        const winRateStr = summary.winRate.toFixed(1);
        const totalPnlStr = (summary.totalPnl >= 0 ? '+' : '') + summary.totalPnl.toFixed(2) + '%';

        let warningHtml = '';
        if (summary.total < 10) {
            warningHtml = `<div class="summary-warning summary-warning--strong">⛔ Sample size &lt; 10 — kết quả không có ý nghĩa thống kê</div>`;
        } else if (summary.total < 30) {
            warningHtml = `<div class="summary-warning summary-warning--light">⚠ Sample size &lt; 30 — kết quả chưa đủ tin cậy</div>`;
        }

        this.summaryEl.innerHTML = `
            <div class="summary-stats">
                <span class="summary-stat">Lệnh: ${summary.total}</span>
                <span class="summary-stat summary-stat--win">Thắng: ${summary.wins} (${winRateStr}%)</span>
                <span class="summary-stat summary-stat--loss">Thua: ${summary.losses}</span>
                <span class="summary-stat">P&L: ${totalPnlStr}</span>
            </div>
            ${warningHtml}
        `;
    }

    private showEmptyMessage(): void {
        if (this.emptyMsg) {
            this.emptyMsg.style.display = 'block';
            this.emptyMsg.textContent = 'Entry price chưa được chạm — thử mở rộng date range hoặc điều chỉnh Entry';
        }
    }

    // Called by ReplayEngine or main.ts when replay completes
    showCompletionOverlay(sessionFilename?: string): void {
        this.currentSessionFilename = sessionFilename ?? null;
        this.dismissCompletionOverlay();

        this.completionOverlay = document.createElement('div');
        this.completionOverlay.className = 'completion-overlay';
        this.completionOverlay.setAttribute('role', 'alertdialog');
        this.completionOverlay.setAttribute('aria-label', 'Replay hoàn thành');

        // Phase 2: conditionally show Supabase export button
        const supabaseButton = isSupabaseEnabled()
            ? `<button class="btn-primary completion-export-btn">📤 Lưu vào Supabase</button>`
            : '';

        this.completionOverlay.innerHTML = `
      <div class="completion-overlay-panel">
        <h3>✅ Replay hoàn thành</h3>
        <div class="completion-actions">
          <button class="btn-secondary completion-reset-btn">Reset</button>
          ${supabaseButton}
        </div>
      </div>
    `;

        // Phase 1: Reset button
        this.completionOverlay.querySelector('.completion-reset-btn')
            ?.addEventListener('click', () => {
                this.dismissCompletionOverlay();
                // Phase 1: notify reset (handled by main.ts / ReplayEngine)
                document.dispatchEvent(new CustomEvent('results:resetRequested'));
            });

        // Phase 2: Supabase export button (only rendered when supabase enabled)
        this.completionOverlay.querySelector('.completion-export-btn')
            ?.addEventListener('click', () => {
                this.dismissCompletionOverlay();
                sessionListPanel.open(this.currentSessionFilename ?? undefined);
            });

        document.body.appendChild(this.completionOverlay);

        // Update StatusBar to Complete mode
        this.renderStatusBarComplete();
    }

    dismissCompletionOverlay(): void {
        this.completionOverlay?.remove();
        this.completionOverlay = null;
    }

    // Phase 1 StatusBar update — shows replay state
    renderStatusBar(state: 'idle' | 'playing' | 'paused' | 'complete'): void {
        if (!this.statusBarEl) return;

        if (state === 'complete') {
            this.renderStatusBarComplete();
        } else {
            this.statusBarEl.innerHTML = `<span class="statusbar-state">${state}</span>`;
        }
    }

    private renderStatusBarComplete(): void {
        if (!this.statusBarEl) return;

        // Phase 2: export link only when Supabase enabled
        const exportLink = isSupabaseEnabled()
            ? `<span class="statusbar-export-link" role="button" tabindex="0">📤 Export</span>`
            : '';

        this.statusBarEl.innerHTML = `
      <span class="statusbar-state complete">✅ Hoàn thành</span>
      ${exportLink}
    `;

        // Phase 2: bind export link click
        this.statusBarEl.querySelector('.statusbar-export-link')
            ?.addEventListener('click', () => {
                sessionListPanel.open(this.currentSessionFilename ?? undefined);
            });
    }
}

export const resultsPanel = new ResultsPanel();
