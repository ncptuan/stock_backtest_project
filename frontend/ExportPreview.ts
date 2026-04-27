import type { PreviewResponse, TradePreviewItem } from './types';

export class ExportPreview {
    private overlay: HTMLElement | null = null;
    private data: PreviewResponse | null = null;
    private filename: string | null = null;
    private _hasEdited = false;
    private _confirmEnabled = false;
    private _scrollObserver: IntersectionObserver | null = null;
    private _reviewedCount = 0;
    // Story 2.3: draft auto-save
    private _saveTimer: ReturnType<typeof setTimeout> | null = null;
    private _draftKey: string | null = null;

    open(data: PreviewResponse, filename: string): void {
        // P7: tear down any previous session before opening a new one
        this._scrollObserver?.disconnect();
        this._scrollObserver = null;
        document.removeEventListener('keydown', this.handleKeyDown);
        // F2: cancel any stale save timer before overwriting _draftKey
        if (this._saveTimer !== null) {
            clearTimeout(this._saveTimer);
            this._saveTimer = null;
        }
        // F6: clear previous session's draft before adopting new key
        this._clearDraft();

        this.data = data;
        this.filename = filename;
        this._hasEdited = false;
        this._confirmEnabled = false;
        this._reviewedCount = 0;
        this._draftKey = `export_draft_${filename}`;
        this.render();
        this.setupIntersectionObserver();
        document.addEventListener('keydown', this.handleKeyDown);
        // Story 2.3: restore saved draft after DOM is ready
        this._tryRestoreDraft();
    }

    close(force = false): void {
        if (!force && this._hasEdited) {
            this.showCloseConfirmDialog();
            return;
        }
        this.cleanup();
    }

    private render(): void {
        this.overlay?.remove();
        const data = this.data!;
        // P9: use trades.length as canonical count for rendering (not server-reported trade_count)
        const totalTrades = data.trades.length;
        const winRatePct = Math.round(data.win_rate * 100);
        // P2: escape defaultStrategy before use in attribute
        const defaultStrategy = this.escapeAttr(`${data.symbol}_${data.timeframe}`);
        // P1: escape all server-supplied strings used in innerHTML
        const safeSymbol = this.escapeHtml(data.symbol);
        const safeTf = this.escapeHtml(data.timeframe.toUpperCase());
        const safeDate = this.escapeHtml(data.date);
        const safeQualityGate = data.quality_gate === 'pass' ? '✅ PASS' : '❌ FAIL';

        this.overlay = document.createElement('div');
        this.overlay.className = 'export-preview-overlay';
        this.overlay.setAttribute('role', 'dialog');
        this.overlay.setAttribute('aria-modal', 'true');
        this.overlay.setAttribute('aria-label', 'Export Preview');

        this.overlay.innerHTML = `
      <div class="export-preview-panel">
        <div class="export-preview-header">
          <span class="export-preview-title">
            Export Preview — ${safeSymbol} ${safeTf} | ${safeDate}
          </span>
          <button class="export-preview-close" aria-label="Đóng">✕</button>
        </div>

        <div class="export-preview-summary" role="region" aria-label="Tóm tắt session">
          <span class="summary-stat">${totalTrades} trades</span>
          <span class="summary-stat win-rate">${winRatePct}% win rate</span>
          <span class="summary-stat quality-gate-badge quality-${data.quality_gate}">${safeQualityGate}</span>
          <div class="summary-strategy">
            <label for="strategy-name-input">Strategy:</label>
            <input
              id="strategy-name-input"
              class="strategy-name-input"
              type="text"
              value="${defaultStrategy}"
              maxlength="80"
              aria-label="Tên strategy"
            />
          </div>
        </div>

        <div class="export-preview-trade-list" id="trade-list-scroll">
          ${data.trades.map((trade, index) => this.renderTradeRow(trade, index, totalTrades)).join('')}
        </div>

        <div class="export-preview-footer">
          <span class="scroll-progress" id="scroll-progress" aria-live="polite">
            Đã xem 0/${totalTrades} trades
          </span>
          <button
            class="btn-primary confirm-export-btn"
            id="confirm-export-btn"
            aria-disabled="true"
            aria-describedby="scroll-progress"
          >
            Confirm Export
          </button>
        </div>
      </div>
    `;

        // Wire close button
        this.overlay.querySelector('.export-preview-close')!
            .addEventListener('click', () => this.close());

        // Wire Confirm button — only fires when not aria-disabled
        const confirmBtn = this.overlay.querySelector('#confirm-export-btn') as HTMLButtonElement;
        confirmBtn.addEventListener('click', () => {
            if (this._confirmEnabled) this.handleConfirm();
        });

        // Wire strategy name dirty flag
        const strategyInput = this.overlay.querySelector('#strategy-name-input') as HTMLInputElement;
        strategyInput.addEventListener('input', () => { this._hasEdited = true; });

        // Wire textarea events: dirty tracking + auto-save + expand + char counter (Story 2.3)
        this.overlay.querySelectorAll('.trade-reasoning-textarea').forEach((ta) => {
            const textarea = ta as HTMLTextAreaElement;
            textarea.addEventListener('input', () => {
                this._hasEdited = true;
                this._scheduleSave();
                this._updateCharCounter(textarea);
            });
            textarea.addEventListener('focus', () => {
                textarea.rows = 5;
                this._showCharCounter(textarea);
            });
            textarea.addEventListener('blur', () => {
                textarea.rows = 2;
                this._hideCharCounter(textarea);
                this._checkBlankTextarea(textarea);
            });
        });

        document.body.appendChild(this.overlay);

        // Focus close button (first focusable)
        (this.overlay.querySelector('.export-preview-close') as HTMLElement)?.focus();
    }

    private renderTradeRow(trade: TradePreviewItem, index: number, total: number): string {
        const isLast = index === total - 1;
        const outcomeClass = trade.result === 'win' ? 'outcome-win' : 'outcome-loss';
        // P1: derive display strings from trusted literals, not server data, where possible
        const outcomeText = trade.result === 'win' ? 'WIN' : 'LOSS';
        const directionClass = trade.direction === 'LONG' ? 'long' : 'short';
        const directionText = trade.direction === 'LONG' ? 'LONG' : 'SHORT';
        const entryDate = this.escapeHtml(new Date(trade.entry_timestamp_ms).toISOString().slice(0, 10));

        return `
      <div
        class="trade-row"
        data-index="${index}"
        data-last="${isLast}"
        id="trade-row-${index}"
      >
        <div class="trade-row-header">
          <span class="trade-num">#${index + 1}</span>
          <span class="trade-date">${entryDate}</span>
          <span class="trade-direction direction-${directionClass}">${directionText}</span>
          <span class="trade-outcome ${outcomeClass}">${outcomeText}</span>
        </div>
        <div class="trade-row-prices">
          <span>Entry: <strong>$${trade.entry_price.toLocaleString()}</strong></span>
          <span>TP: $${trade.tp_price.toLocaleString()}</span>
          <span>SL: $${trade.sl_price.toLocaleString()}</span>
          <span class="trade-bars">+${trade.bars_to_exit} bars</span>
        </div>
        <textarea
          class="trade-reasoning-textarea"
          data-trade-index="${index}"
          data-original="${this.escapeAttr(trade.reasoning_template)}"
          rows="2"
          data-min-rows="2"
          data-max-rows="5"
          maxlength="500"
          placeholder="Nhập reasoning cho trade này..."
          aria-label="Reasoning cho trade #${index + 1}"
        >${this.escapeHtml(trade.reasoning_template)}</textarea>
        <span class="textarea-blank-hint"></span>
        <span class="char-counter"></span>
      </div>
    `;
    }

    private setupIntersectionObserver(): void {
        const tradeList = this.overlay?.querySelector('#trade-list-scroll');
        if (!tradeList) return;

        const allRows = this.overlay!.querySelectorAll('.trade-row');
        const lastRow = this.overlay!.querySelector('.trade-row[data-last="true"]');

        if (!lastRow) {
            // 0 trades: enable immediately
            this.enableConfirm();
            return;
        }

        this._scrollObserver = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    const rowEl = entry.target as HTMLElement;
                    if (entry.isIntersecting) {
                        rowEl.classList.add('trade-row--in-viewport');
                        if (!rowEl.classList.contains('trade-row--reviewed')) {
                            rowEl.classList.add('trade-row--reviewed');
                            this._reviewedCount++;
                            // P6: updateScrollProgress called only from enableConfirm to avoid
                            // double aria-live announcements; update incrementally here for non-last rows
                            if (rowEl.dataset['last'] !== 'true') {
                                this.updateScrollProgress(allRows.length);
                            }
                        }
                        // Enable confirm when last row is visible (P5: threshold:0 ensures this fires)
                        if (rowEl.dataset['last'] === 'true' && !this._confirmEnabled) {
                            this.enableConfirm();
                        }
                    } else {
                        rowEl.classList.remove('trade-row--in-viewport');
                    }
                });
            },
            {
                // P5: threshold:0 fires as soon as any pixel of a row enters the viewport,
                // preventing tall rows from never reaching the old 0.3 threshold
                root: tradeList as HTMLElement,
                threshold: 0,
            }
        );

        allRows.forEach((row) => this._scrollObserver!.observe(row));
    }

    private enableConfirm(): void {
        this._confirmEnabled = true;
        const btn = this.overlay?.querySelector('#confirm-export-btn') as HTMLElement | null;
        if (!btn) return;
        btn.removeAttribute('aria-disabled');
        btn.classList.add('confirm-export-btn--enabled', 'confirm-glow');
        // Remove glow class after animation (800ms)
        setTimeout(() => btn.classList.remove('confirm-glow'), 800);

        // Update progress to show all reviewed if last row was reached
        const allRows = this.overlay?.querySelectorAll('.trade-row');
        if (allRows) {
            this.updateScrollProgress(allRows.length);
        }
    }

    private updateScrollProgress(total: number): void {
        const progressEl = this.overlay?.querySelector('#scroll-progress');
        if (progressEl) {
            const reviewed = this._confirmEnabled ? total : this._reviewedCount;
            progressEl.textContent = `Đã xem ${reviewed}/${total} trades`;
        }
    }

    private showCloseConfirmDialog(): void {
        // P12: exact AC5 text — no trailing period
        const confirmed = window.confirm(
            'Đóng preview? Draft đã lưu — có thể tiếp tục sau'
        );
        if (confirmed) this.cleanup();
    }

    private handleConfirm(): void {
        const strategyInput = this.overlay?.querySelector('#strategy-name-input') as HTMLInputElement;
        const strategyName = strategyInput?.value.trim()
            || `${this.data!.symbol}_${this.data!.timeframe}`;

        // Collect current textarea values (Story 3.x will POST to /api/export)
        // P10: use data-trade-index foreign key, not positional zip
        const textareas = (this.overlay?.querySelectorAll('.trade-reasoning-textarea') ?? []) as NodeListOf<HTMLTextAreaElement>;
        const editedTrades = Array.from(textareas).map((ta) => {
            const i = Number(ta.dataset['tradeIndex']);
            return {
                ...this.data!.trades[i],
                reasoning_summary: ta.value,
            };
        });

        // Fire export-ready event — Story 3.x ExportProgressOverlay will listen
        document.dispatchEvent(new CustomEvent('exportpreview:confirmed', {
            detail: {
                filename: this.filename,
                strategy_name: strategyName,
                trades: editedTrades,
                session_win_rate: this.data!.win_rate,
                timeframe: this.data!.timeframe,
            },
        }));

        this.cleanup(true);  // export success → clear draft
    }

    private cleanup(clearDraft = false): void {
        // Story 2.3: cancel pending auto-save timer
        if (this._saveTimer !== null) {
            clearTimeout(this._saveTimer);
            this._saveTimer = null;
        }
        // Clear draft only on successful export, not on close-without-export
        if (clearDraft) this._clearDraft();
        this._draftKey = null;
        this._scrollObserver?.disconnect();
        this._scrollObserver = null;
        this.overlay?.remove();
        this.overlay = null;
        this.data = null;
        this.filename = null;
        this._hasEdited = false;
        this._confirmEnabled = false;
        this._reviewedCount = 0;
        document.removeEventListener('keydown', this.handleKeyDown);
    }

    private handleKeyDown = (e: KeyboardEvent): void => {
        if (e.key === 'Escape') {
            e.preventDefault();
            this.close();
        }
        // Ctrl+Enter (or Cmd+Enter on Mac) to confirm
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && this._confirmEnabled) {
            e.preventDefault();
            this.handleConfirm();
        }
    };

    // =========================================================================
    // Story 2.3: Auto-save draft
    // =========================================================================

    private _scheduleSave(): void {
        if (this._saveTimer !== null) clearTimeout(this._saveTimer);
        this._saveTimer = setTimeout(() => {
            this._saveDraft();
            this._saveTimer = null;
        }, 3000);
    }

    private _saveDraft(): void {
        if (!this._draftKey || !this.overlay) return;
        const textareas = this.overlay.querySelectorAll('.trade-reasoning-textarea');
        const draft: Record<string, string> = {};
        // F1: use data-trade-index attribute (consistent with _tryRestoreDraft) instead of positional i
        textareas.forEach((ta) => {
            const textarea = ta as HTMLTextAreaElement;
            const idx = textarea.dataset['tradeIndex'];
            if (idx !== undefined) draft[idx] = textarea.value;
        });
        try {
            sessionStorage.setItem(this._draftKey, JSON.stringify(draft));
        } catch {
            // QuotaExceededError — fail silently
        }
    }

    private _clearDraft(): void {
        if (this._draftKey) sessionStorage.removeItem(this._draftKey);
    }

    // =========================================================================
    // Story 2.3: Draft restore
    // =========================================================================

    private _tryRestoreDraft(): void {
        if (!this._draftKey || !this.overlay) return;
        let raw: string | null = null;
        try {
            raw = sessionStorage.getItem(this._draftKey);
        } catch {
            return;  // private mode / storage blocked
        }
        if (!raw) return;

        let draft: Record<string, string>;
        try {
            draft = JSON.parse(raw) as Record<string, string>;
        } catch {
            return;  // corrupt data — ignore
        }

        let restored = 0;
        let actuallyEdited = false;
        Object.entries(draft).forEach(([idx, value]) => {
            const ta = this.overlay!.querySelector(
                `.trade-reasoning-textarea[data-trade-index="${idx}"]`
            ) as HTMLTextAreaElement | null;
            if (ta) {
                ta.value = value;
                restored++;
                // F12: only mark edited if restored value differs from original template
                const original = ta.dataset['original'] ?? '';
                if (value !== original) actuallyEdited = true;
                // Trigger blank check on restored-empty textareas
                if (value.trim() === '') {
                    ta.classList.add('textarea--blank');
                    this._showBlankHint(ta);
                }
            }
        });

        // F5+F12: set _hasEdited and show toast only when user genuinely modified content
        if (restored > 0 && actuallyEdited) {
            this._hasEdited = true;
            this._showRestoreToast();
        }
    }

    private _showRestoreToast(): void {
        const win = window as unknown as Record<string, unknown>;
        if (typeof win['toastManager'] !== 'undefined' && win['toastManager'] !== null) {
            (win['toastManager'] as { show: (msg: string, type: string) => void })
                .show('Đã khôi phục draft trước đó', 'info');
            return;
        }
        // Fallback: inline toast within overlay
        const toast = document.createElement('div');
        toast.className = 'export-preview-toast';
        toast.textContent = 'Đã khôi phục draft trước đó';
        const tradeList = this.overlay!.querySelector('.export-preview-trade-list');
        tradeList?.insertAdjacentElement('beforebegin', toast);
        setTimeout(() => toast.remove(), 3000);
    }

    // =========================================================================
    // Story 2.3: Textarea expand, char counter, blank check
    // =========================================================================

    private _showCharCounter(textarea: HTMLTextAreaElement): void {
        const counter = this._getCharCounter(textarea);
        if (counter) {
            counter.textContent = `${textarea.value.length}/500`;
            counter.classList.add('char-counter--visible');
        }
    }

    private _hideCharCounter(textarea: HTMLTextAreaElement): void {
        this._getCharCounter(textarea)?.classList.remove('char-counter--visible');
    }

    private _updateCharCounter(textarea: HTMLTextAreaElement): void {
        const counter = this._getCharCounter(textarea);
        if (counter?.classList.contains('char-counter--visible')) {
            counter.textContent = `${textarea.value.length}/500`;
        }
    }

    private _getCharCounter(textarea: HTMLTextAreaElement): HTMLElement | null {
        // DOM order after textarea: blank-hint, then char-counter
        const next1 = textarea.nextElementSibling;   // blank-hint
        const next2 = next1?.nextElementSibling;     // char-counter
        return (next2?.classList.contains('char-counter') ? next2 : null) as HTMLElement | null;
    }

    private _checkBlankTextarea(textarea: HTMLTextAreaElement): void {
        const hint = (textarea.nextElementSibling?.classList.contains('textarea-blank-hint')
            ? textarea.nextElementSibling
            : null) as HTMLElement | null;

        if (textarea.value.trim() === '') {
            textarea.classList.add('textarea--blank');
            if (hint) {
                hint.textContent = 'Trống — pre-fill template đã bị xóa';
                hint.classList.add('textarea-blank-hint--visible');
            }
        } else {
            textarea.classList.remove('textarea--blank');
            if (hint) hint.classList.remove('textarea-blank-hint--visible');
        }
    }

    private _showBlankHint(textarea: HTMLTextAreaElement): void {
        const hint = textarea.nextElementSibling as HTMLElement | null;
        if (hint?.classList.contains('textarea-blank-hint')) {
            hint.textContent = 'Trống — pre-fill template đã bị xóa';
            hint.classList.add('textarea-blank-hint--visible');
        }
    }

    private escapeHtml(str: string): string {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    private escapeAttr(str: string): string {
        return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
}

export const exportPreview = new ExportPreview();
