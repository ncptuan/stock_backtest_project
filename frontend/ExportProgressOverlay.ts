/**
 * ExportProgressOverlay — Story 3.2
 *
 * 3-state overlay that shows during and after POST /api/export:
 *   - in-progress: spinner + optimistic step text
 *   - success: ✅ icon + counts + Supabase link + Reset Replay / Đóng
 *   - error: ❌ icon + message + collapsible raw detail + Thử lại / Đóng
 *
 * AC coverage: #1–#12
 * Listens: `exportpreview:confirmed` CustomEvent (dispatched by ExportPreview.ts)
 * Dispatches: `exportprogress:resetReplay`, `exportprogress:exportSuccess`
 */
import type { ExportConfirmedPayload, ExportSuccessData } from './types';
import { ExportHistory } from './ExportHistory';

interface ApiErrorBody {
    error: string;
    message: string;
}

function escapeHtml(s: string): string {
    return s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;');
}

export class ExportProgressOverlay {
    private _backdrop: HTMLDivElement | null = null;
    private _progressLines: HTMLDivElement | null = null;
    private _state: 'idle' | 'in-progress' | 'success' | 'error' = 'idle';
    private _lastPayload: ExportConfirmedPayload | null = null;
    private _slowTimer: ReturnType<typeof setTimeout> | null = null;
    private _progressTimer: ReturnType<typeof setTimeout> | null = null;
    private _keyHandler: ((e: KeyboardEvent) => void) | null = null;

    constructor() {
        document.addEventListener('exportpreview:confirmed', (e: Event) => {
            const payload = (e as CustomEvent<ExportConfirmedPayload>).detail;
            this.open(payload);
        });
    }

    open(payload: ExportConfirmedPayload): void {
        this._lastPayload = payload;
        this._render();
        this._showInProgress();
        void this._doExport(payload);
    }

    close(): void {
        this._clearTimers();
        if (this._backdrop) {
            this._backdrop.remove();
            this._backdrop = null;
        }
        if (this._keyHandler) {
            document.removeEventListener('keydown', this._keyHandler);
            this._keyHandler = null;
        }
        this._state = 'idle';
    }

    private _render(): void {
        // F7: idempotency — remove existing backdrop + old keyHandler before creating new one
        if (this._keyHandler) {
            document.removeEventListener('keydown', this._keyHandler);
            this._keyHandler = null;
        }
        if (this._backdrop) {
            this._backdrop.remove();
            this._backdrop = null;
        }

        const backdrop = document.createElement('div');
        backdrop.className = 'export-progress-overlay-backdrop';
        backdrop.setAttribute('role', 'alertdialog');
        backdrop.setAttribute('aria-modal', 'true');
        backdrop.setAttribute('aria-label', 'Export Progress');

        const modal = document.createElement('div');
        modal.className = 'export-progress-overlay-modal';
        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);
        this._backdrop = backdrop;

        // Keyboard: Escape = close (non in-progress only); R = retry in error state
        this._keyHandler = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && this._state !== 'in-progress') {
                this.close();
            }
            if ((e.key === 'r' || e.key === 'R') && this._state === 'error') {
                this._retry();
            }
        };
        document.addEventListener('keydown', this._keyHandler);
    }

    private _getModal(): HTMLDivElement | null {
        if (!this._backdrop) return null;
        return this._backdrop.querySelector('.export-progress-overlay-modal') as HTMLDivElement;
    }

    // =========================================================================
    // State: In Progress (AC #1, #6, #9)
    // =========================================================================

    private _showInProgress(): void {
        // F6: clear old timers before setting new ones (called on retry too)
        this._clearTimers();
        this._state = 'in-progress';
        const modal = this._getModal();
        if (!modal) return;

        // F8 (AC1): show "(0/N)" count immediately in initial render
        const n = this._lastPayload?.trades.length ?? 0;
        modal.innerHTML = `
          <div style="display:flex;flex-direction:column;align-items:center;gap:12px;padding-bottom:8px">
            <div class="epo-spinner"></div>
            <h3 style="margin:0;font-size:16px;color:var(--sem-text-primary)">Đang ghi vào Supabase...</h3>
          </div>
          <div class="epo-progress-lines" aria-live="assertive">
            <div>✅ Kết nối thành công</div>
            <div id="epo-step-sc">⏳ Đang ghi signal_comparisons (0/${n})...</div>
            <div id="epo-step-cases">— signal_cases (chờ)</div>
          </div>
        `;
        this._progressLines = modal.querySelector<HTMLDivElement>('.epo-progress-lines');

        // Optimistic progress: advance step text after 1.5s (AC #1)
        this._progressTimer = setTimeout(() => {
            const scEl = modal.querySelector<HTMLElement>('#epo-step-sc');
            if (scEl && this._state === 'in-progress') {
                scEl.textContent = `✅ signal_comparisons (${n}/${n})`;
                const casesEl = modal.querySelector<HTMLElement>('#epo-step-cases');
                if (casesEl) casesEl.textContent = '⏳ Đang ghi signal_cases...';
            }
        }, 1500);

        // Slow connection warning after 10s (AC #6)
        this._slowTimer = setTimeout(() => {
            if (this._state === 'in-progress' && this._progressLines) {
                const slowEl = document.createElement('div');
                slowEl.textContent = 'Kết nối chậm — đang thử tiếp...';
                slowEl.style.color = 'var(--prim-yellow-300, #d97706)';
                this._progressLines.appendChild(slowEl);
            }
        }, 10000);
    }

    // =========================================================================
    // State: Success (AC #2, #7, #8)
    // =========================================================================

    private _showSuccess(data: ExportSuccessData): void {
        // F1: guard stale close — overlay may have been closed while fetch was in-flight
        const modal = this._getModal();
        if (!modal) return;

        this._state = 'success';
        this._clearTimers();

        // F5: validate supabase_url to prevent javascript: URI injection
        const safeUrl = data.supabase_url.startsWith('https://') ? data.supabase_url : '#';

        modal.innerHTML = `
          <div class="epo-success-icon">✅</div>
          <h3 style="text-align:center;margin:0 0 8px;color:var(--sem-text-primary)">Export thành công!</h3>
          <p class="epo-summary">${escapeHtml(String(data.signal_comparisons_count))} rows → signal_comparisons | ${escapeHtml(String(data.signal_cases_count))} rows → signal_cases</p>
          <a class="epo-supabase-link" href="${escapeHtml(safeUrl)}" target="_blank" rel="noopener noreferrer">Xem trên Supabase →</a>
          <div class="epo-footer">
            <button class="btn-secondary" id="epo-close-btn">Đóng</button>
            <button class="btn-primary" id="epo-reset-btn">Reset Replay</button>
          </div>
        `;
        const closeBtn = modal.querySelector<HTMLElement>('#epo-close-btn')!;
        const resetBtn = modal.querySelector<HTMLElement>('#epo-reset-btn')!;
        closeBtn.addEventListener('click', () => this.close());
        resetBtn.addEventListener('click', () => this._resetReplay());
        resetBtn.focus();
    }

    // =========================================================================
    // State: Error (AC #3, #4, #5, #8, #12)
    // =========================================================================

    private _showError(message: string, rawError?: string): void {
        // F2: guard stale close — overlay may have been closed during 800ms rollback pause
        const modal = this._getModal();
        if (!modal) return;

        this._state = 'error';
        this._clearTimers();

        // F3, F4: escape all server-controlled strings before innerHTML interpolation
        const safeMessage = escapeHtml(message);
        const rawTruncated = rawError ? escapeHtml(rawError.slice(0, 200)) : '';

        modal.innerHTML = `
          <div class="epo-error-icon">❌</div>
          <h3 style="text-align:center;margin:0 0 8px;color:var(--sem-text-primary)">Export thất bại</h3>
          <p class="epo-error-message">${safeMessage}</p>
          ${rawTruncated ? `
            <button class="epo-details-toggle" id="epo-toggle-btn">Xem chi tiết kỹ thuật ▶</button>
            <div class="epo-technical-details" id="epo-raw-details" hidden>${rawTruncated}</div>
          ` : ''}
          <div class="epo-footer">
            <button class="btn-primary" id="epo-retry-btn">Thử lại</button>
            <button class="btn-secondary" id="epo-close-btn">Đóng</button>
          </div>
        `;
        const closeBtn = modal.querySelector<HTMLElement>('#epo-close-btn')!;
        const retryBtn = modal.querySelector<HTMLElement>('#epo-retry-btn')!;
        closeBtn.addEventListener('click', () => this.close());
        retryBtn.addEventListener('click', () => this._retry());
        if (rawTruncated) {
            const toggleBtn = modal.querySelector<HTMLButtonElement>('#epo-toggle-btn')!;
            toggleBtn.addEventListener('click', () => {
                const detailEl = modal.querySelector<HTMLElement>('#epo-raw-details')!;
                detailEl.hidden = !detailEl.hidden;
                toggleBtn.textContent = detailEl.hidden
                    ? 'Xem chi tiết kỹ thuật ▶'
                    : 'Ẩn chi tiết kỹ thuật ▼';
            });
        }
        retryBtn.focus();
    }

    // =========================================================================
    // Core: API call + state transitions (AC #1–#5, #12)
    // =========================================================================

    private async _doExport(payload: ExportConfirmedPayload): Promise<void> {
        const body = {
            session_filename: payload.filename,
            strategy_name: payload.strategy_name,
            timeframe: payload.timeframe,
            session_win_rate: payload.session_win_rate,
            trades: payload.trades.map(t => ({
                bar_index: t.bar_index,
                entry_timestamp_ms: t.entry_timestamp_ms,
                direction: t.direction,
                entry_price: t.entry_price,
                tp_price: t.tp_price,
                sl_price: t.sl_price,
                result: t.result,
                bars_to_exit: t.bars_to_exit,
                reasoning_summary: t.reasoning_summary ?? '',
            })),
        };

        try {
            const resp = await fetch('/api/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });

            // F11: wrap resp.json() separately — non-JSON 502/504 bodies would throw
            // and surface as "không thể kết nối" which is misleading for HTTP errors
            let json: { data?: ExportSuccessData; detail?: ApiErrorBody; error?: string; message?: string };
            try {
                json = (await resp.json()) as typeof json;
            } catch {
                this._showError(
                    `Lỗi server (HTTP ${resp.status}) — phản hồi không hợp lệ`,
                    `HTTP ${resp.status} ${resp.statusText}`
                );
                return;
            }

            if (resp.ok && json.data) {
                // Dispatch exportSuccess for Story 3.3 to track localStorage
                const today = new Date().toISOString().slice(0, 10); // "YYYY-MM-DD"
                document.dispatchEvent(
                    new CustomEvent('exportprogress:exportSuccess', {
                        detail: { filename: payload.filename, date: today },
                    })
                );
                this._showSuccess(json.data);
            } else {
                // FastAPI HTTPException puts detail in json.detail
                const errBody: ApiErrorBody = (json.detail as ApiErrorBody) ?? {
                    error: json.error ?? 'unknown',
                    message: (json.message as string) ?? 'Lỗi không xác định',
                };

                // AC #4: partial_write_rolled_back — add rollback note to progress lines
                if (errBody.error === 'partial_write_rolled_back' && this._progressLines) {
                    const n = payload.trades.length;
                    const rollbackNote = document.createElement('div');
                    rollbackNote.style.color = 'var(--prim-yellow-300, #d97706)';
                    rollbackNote.textContent = `Đã rollback signal_comparisons (0/${n} được giữ lại)`;
                    this._progressLines.appendChild(rollbackNote);
                    // Brief pause so user can read rollback note before error state
                    await new Promise<void>(r => setTimeout(r, 800));
                }

                // AC #12: enforce client-side message for any 409 (not just error==='duplicate')
                // F4: broaden from errBody.error==='duplicate' to any HTTP 409
                // F5: only write localStorage if no entry yet (backend is source of truth, not override)
                if (resp.status === 409) {
                    const today = new Date().toISOString().slice(0, 10);
                    if (!ExportHistory.isExported(payload.filename)) {
                        ExportHistory.recordExport(payload.filename, today);
                    }
                    errBody.message = 'Session đã export — xóa rows trên Supabase trước nếu muốn re-export';
                }

                this._showError(errBody.message ?? 'Lỗi không xác định', JSON.stringify(errBody));
            }
        } catch (err: unknown) {
            const errMsg = err instanceof Error ? err.message : String(err);
            this._showError(
                'Không thể kết nối đến backend — kiểm tra server đang chạy',
                errMsg
            );
        }
    }

    // =========================================================================
    // Actions
    // =========================================================================

    private _retry(): void {
        if (this._lastPayload) {
            this._showInProgress();
            void this._doExport(this._lastPayload);
        }
    }

    private _resetReplay(): void {
        this.close();
        document.dispatchEvent(new CustomEvent('exportprogress:resetReplay'));
    }

    private _clearTimers(): void {
        if (this._slowTimer !== null) {
            clearTimeout(this._slowTimer);
            this._slowTimer = null;
        }
        if (this._progressTimer !== null) {
            clearTimeout(this._progressTimer);
            this._progressTimer = null;
        }
    }
}

export const exportProgressOverlay = new ExportProgressOverlay();
