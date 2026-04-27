import { eventBus } from './EventBus';
import type { SessionItem, SessionsApiResponse } from './types';
import { ExportHistory } from './ExportHistory';

// Unused import lint suppression — eventBus wired in Story 2.x for state sync
void eventBus;

function isSupabaseEnabled(): boolean {
    return typeof window !== 'undefined' && (window as unknown as Record<string, unknown>)['__SUPABASE_ENABLED__'] === true;
}

function escapeHtml(s: string): string {
    return s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;');
}

export class SessionListPanel {
    private overlay: HTMLElement | null = null;
    private currentFilename: string | null = null;
    private fetchAbortController: AbortController | null = null;
    // Two-click re-export guard — reset on each open() call (AC #3, #4)
    private _pendingReExport: Record<string, boolean> = {};

    constructor() {
        // Story 2.4: disable/enable Export buttons based on replay state
        document.addEventListener('exportpanel:canExport', (e: Event) => {
            const { canExport } = (e as CustomEvent<{ canExport: boolean }>).detail;
            if (!this.overlay) return;  // Panel chưa open → no-op
            const exportBtns = this.overlay.querySelectorAll<HTMLButtonElement>(
                '.session-export-btn, .session-reexport-btn'
            );
            exportBtns.forEach((btn) => {
                btn.disabled = !canExport;
                if (!canExport) {
                    btn.setAttribute('aria-disabled', 'true');
                    btn.title = 'Replay đang chạy — nhấn Stop trước khi export';
                } else {
                    btn.removeAttribute('aria-disabled');
                    btn.title = '';
                }
            });
        });
    }

    open(currentSessionFilename?: string): void {
        this.currentFilename = currentSessionFilename ?? null;
        this._pendingReExport = {};  // Reset two-click guard on each open
        this.render();
        this.fetchAndPopulate();
        // P3: remove before add to prevent listener accumulation across re-opens
        document.removeEventListener('keydown', this.handleKeyDown);
        document.addEventListener('keydown', this.handleKeyDown);
    }

    close(): void {
        // P4: cancel in-flight fetch to prevent stale write-back
        this.fetchAbortController?.abort();
        this.fetchAbortController = null;
        this.overlay?.remove();
        this.overlay = null;
        this.currentFilename = null;
        document.removeEventListener('keydown', this.handleKeyDown);
    }

    private render(): void {
        // P4: abort previous fetch before replacing overlay
        this.fetchAbortController?.abort();
        this.fetchAbortController = null;

        this.overlay?.remove();

        this.overlay = document.createElement('div');
        this.overlay.className = 'session-list-overlay';
        this.overlay.setAttribute('role', 'dialog');
        this.overlay.setAttribute('aria-label', 'Danh sách sessions');
        this.overlay.setAttribute('aria-modal', 'true');

        this.overlay.innerHTML = `
      <div class="session-list-panel" tabindex="-1">
        <div class="session-list-header">
          <h2>Chọn session để export</h2>
          <button class="session-list-close" aria-label="Đóng">&times;</button>
        </div>
        <div class="session-list-body" id="session-list-body">
          ${this.renderSkeleton()}
        </div>
        <div class="session-list-footer">
          <button class="btn-secondary session-list-close-btn">Đóng</button>
        </div>
      </div>
    `;

        // Backdrop click to close
        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) this.close();
        });

        this.overlay.querySelector('.session-list-close')!
            .addEventListener('click', () => this.close());
        this.overlay.querySelector('.session-list-close-btn')!
            .addEventListener('click', () => this.close());

        document.body.appendChild(this.overlay);

        // Focus trap setup + initial focus
        const panel = this.overlay.querySelector('.session-list-panel') as HTMLElement;
        this.trapFocus(panel);
        panel.focus();
    }

    private renderSkeleton(): string {
        return Array.from({ length: 3 }, () => `
      <div class="session-row skeleton">
        <div class="skeleton-line wide"></div>
        <div class="skeleton-line narrow"></div>
      </div>
    `).join('');
    }

    private async fetchAndPopulate(): Promise<void> {
        // P4: create AbortController for this fetch
        const controller = new AbortController();
        this.fetchAbortController = controller;

        try {
            const response = await fetch('/api/sessions', { signal: controller.signal });
            const json: SessionsApiResponse = await response.json();

            if (!response.ok || json.error) {
                this.renderError(json.error?.message ?? 'Không thể tải danh sách sessions');
                return;
            }

            this.renderSessions(json.data ?? []);
        } catch (err) {
            // P4: ignore AbortError — fetch was cancelled intentionally
            if (err instanceof Error && err.name === 'AbortError') return;
            this.renderError('Lỗi kết nối — thử lại sau');
        }
    }

    private renderSessions(sessions: SessionItem[]): void {
        const body = this.overlay?.querySelector('#session-list-body');
        if (!body) return;

        if (sessions.length === 0) {
            body.innerHTML = `
        <div class="session-list-empty">
          <p>Không có session nào trong cache.</p>
          <p class="text-muted">Chạy replay một session trước để tạo Parquet file.</p>
        </div>
      `;
            return;
        }

        const exportHistory = ExportHistory.getAllHistory();

        body.innerHTML = sessions.map((session) => {
            const isCurrentSession = session.filename === this.currentFilename;
            const exportRecord = exportHistory[session.filename];
            const isExported = !!exportRecord;

            // P2: escape all user-controlled values before innerHTML interpolation
            const safeFilename = escapeHtml(session.filename);
            const safeSymbol = escapeHtml(session.symbol);
            const safeTimeframe = escapeHtml(session.timeframe);
            const safeDate = escapeHtml(session.date);
            // Format stored "YYYY-MM-DD" → display "DD/MM" for badge (AC #2, #7)
            const safeExportDate = exportRecord
                ? escapeHtml(ExportHistory.formatDisplayDate(exportRecord.date))
                : '';

            return `
        <div class="session-row${isCurrentSession ? ' session-row--current' : ''}"
             data-filename="${safeFilename}">
          <div class="session-row-info">
            <span class="session-symbol">${safeSymbol}</span>
            <span class="session-timeframe">${safeTimeframe}</span>
            <span class="session-date">${safeDate}</span>
            ${isCurrentSession ? '<span class="session-badge current">Session hiện tại</span>' : ''}
          </div>
          <div class="session-row-actions">
            ${isExported
                    ? `<span class="session-exported-badge">Đã export ${safeExportDate}</span>
                 <button class="btn-ghost session-reexport-btn"
                         data-filename="${safeFilename}">Re-export</button>`
                    : `<button class="btn-primary session-export-btn"
                         data-filename="${safeFilename}">Export</button>`
                }
          </div>
        </div>
      `;
        }).join('');

        // Bind export button events
        body.querySelectorAll<HTMLElement>('.session-export-btn, .session-reexport-btn')
            .forEach((btn) => {
                btn.addEventListener('click', (e) => {
                    const filename = (e.currentTarget as HTMLElement).dataset['filename']!;
                    const isReexport = btn.classList.contains('session-reexport-btn');
                    this.onExportClick(filename, isReexport);
                });
            });
    }

    private onExportClick(filename: string, isReexport: boolean): void {
        if (isReexport) {
            if (!this._pendingReExport[filename]) {
                // First click: show warning toast, set pending flag (AC #3)
                this._pendingReExport[filename] = true;
                const exportedDate = ExportHistory.getExportDate(filename);
                // F6: use formatDisplayDate fallback ('??/??') instead of bare '?'
                const displayDate = exportedDate
                    ? ExportHistory.formatDisplayDate(exportedDate)
                    : '??/??';
                // F7: escape displayDate before interpolation — toastManager may use innerHTML
                this._showToastWarning(
                    `Session đã export ngày ${escapeHtml(displayDate)}. Backend sẽ từ chối nếu rows chưa được xóa trên Supabase`
                );
                return;
            }
            // Second click: proceed with export, clear pending flag (AC #4)
            this._pendingReExport[filename] = false;
        }
        this.close();
        // Delegate to ExportPanel via CustomEvent — Story 2.2 listens to this
        document.dispatchEvent(new CustomEvent('sessionlist:exportSelected', {
            detail: { filename }
        }));
    }

    private _showToastWarning(message: string): void {
        const win = window as unknown as Record<string, unknown>;
        if (typeof win['toastManager'] !== 'undefined' && win['toastManager'] !== null) {
            (win['toastManager'] as { show: (msg: string, type: string) => void }).show(message, 'warning');
        } else {
            console.warn('[SessionListPanel]', message);
        }
    }

    private renderError(message: string): void {
        const body = this.overlay?.querySelector('#session-list-body');
        if (!body) return;
        // P2: escape error message before innerHTML interpolation
        body.innerHTML = `
      <div class="session-list-error">
        <span class="error-icon">⚠️</span>
        <p>${escapeHtml(message)}</p>
      </div>
    `;
    }

    private trapFocus(container: HTMLElement): void {
        // G7: query focusable elements dynamically at event time so Tab-wrap reflects
        // the actual rendered list (skeleton → real rows after fetchAndPopulate)
        container.addEventListener('keydown', (e) => {
            if (e.key !== 'Tab') return;
            const focusable = container.querySelectorAll<HTMLElement>(
                'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            );
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (!first || !last) return;
            if (e.shiftKey) {
                if (document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                }
            } else {
                if (document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        });
    }

    private handleKeyDown = (e: KeyboardEvent): void => {
        if (e.key === 'Escape') {
            e.preventDefault();
            this.close();
        }
    };
}

// Singleton export
export const sessionListPanel = new SessionListPanel();

// Re-export helper for components that need feature flag
export { isSupabaseEnabled };
