/**
 * ExportPanel — Story 2.2 full implementation + Story 2.4 EventBus wiring.
 *
 * Orchestrates export flow:
 * 1. Listens for 'sessionlist:exportSelected' CustomEvent
 * 2. POSTs /api/sessions/{filename}/preview with accumulated trades
 * 3. Routes → QualityGateBlock (fail) or ExportPreview (pass)
 *
 * Story 2.4:
 * - EventBus subscriptions to populate this.trades[] from 'tradeCompleted'
 * - Clears trades + draft on replayStateChanged:stopped and exportpreview:confirmed
 * - Fires 'exportpanel:canExport' CustomEvent for ResultsPanel + SessionListPanel
 */
import type { ApiResponse, PreviewResponse } from './types';
import type { TradeCompletedPayload } from './types';
import { eventBus } from './EventBus';
import { exportPreview } from './ExportPreview';
import { qualityGateBlock } from './QualityGateBlock';
import { exportProgressOverlay as _exportProgressOverlay } from './ExportProgressOverlay';
import { ExportHistory } from './ExportHistory';

export class ExportPanel {
    // Trades array — accumulated from EventBus 'tradeCompleted' events (Story 2.4)
    private _trades: TradeCompletedPayload[] = [];

    get trades(): readonly TradeCompletedPayload[] {
        return this._trades;
    }

    private _isLoading = false;
    private _isPlaying = false;                         // Story 2.4
    private _currentFilename: string | null = null;     // Story 2.4

    constructor() {
        // Listen for session selected event
        document.addEventListener('sessionlist:exportSelected', (e: Event) => {
            const { filename } = (e as CustomEvent<{ filename: string }>).detail;
            this._currentFilename = filename;  // Story 2.4: track for draft cleanup
            void this.openForSession(filename);
        });

        // Story 2.4: EventBus subscriptions
        eventBus.on('tradeCompleted', this._onTradeCompleted);
        eventBus.on('replayStateChanged', this._onReplayStateChanged);

        // Story 2.4: Listen for export confirmed (clean up after success)
        document.addEventListener('exportpreview:confirmed', this._onExportConfirmed);

        // Story 3.3: Track exported sessions in localStorage
        document.addEventListener('exportprogress:exportSuccess', (e: Event) => {
            const { filename, date } = (e as CustomEvent<{ filename: string; date: string }>).detail;
            ExportHistory.recordExport(filename, date);
        });
    }

    async openForSession(filename: string): Promise<void> {
        // Story 2.4: Reject if replay is active
        if (this._isPlaying) {
            this._showToastError('Export không khả dụng khi replay đang chạy — nhấn Stop trước');
            return;
        }
        if (this._isLoading) return;  // debounce double-click
        this._isLoading = true;

        try {
            const response = await this._callPreviewApi(filename);

            if (!response.data || response.error) {
                const msg = response.error?.message ?? 'Không thể tải preview session';
                this._showToastError(msg);
                return;
            }

            const preview = response.data;

            if (preview.quality_gate === 'fail') {
                qualityGateBlock.open(preview.quality_gate_reason ?? 'Session không đủ điều kiện');
            } else {
                exportPreview.open(preview, filename);
            }
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : String(err);
            this._showToastError(`Lỗi khi tải preview: ${message}`);
        } finally {
            this._isLoading = false;
        }
    }

    private async _callPreviewApi(filename: string): Promise<ApiResponse<PreviewResponse>> {
        const response = await fetch(
            `/api/sessions/${encodeURIComponent(filename)}/preview`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ trades: this._trades }),
            }
        );
        if (!response.ok) {
            return { data: null, error: { message: `HTTP ${response.status}`, code: 'HTTP_ERROR', retryable: response.status >= 500 } };
        }
        return response.json() as Promise<ApiResponse<PreviewResponse>>;
    }

    private _showToastError(message: string): void {
        // Fallback to console if toastManager not yet available (Phase 1 not wired)
        const win = window as unknown as Record<string, unknown>;
        if (typeof win['toastManager'] !== 'undefined' && win['toastManager'] !== null) {
            (win['toastManager'] as { show: (msg: string, type: string) => void }).show(message, 'error');
        } else {
            console.error('[ExportPanel]', message);
        }
    }

    // =========================================================================
    // Story 2.4: EventBus handlers
    // =========================================================================

    private _onTradeCompleted = (payload: TradeCompletedPayload): void => {
        this._trades.push({ ...payload });
    };

    private _onReplayStateChanged = (payload: { state: 'playing' | 'paused' | 'stopped' }): void => {
        const { state } = payload;

        if (state === 'playing') {
            this._isPlaying = true;
            // P8: clear trades on (re)start so a new replay session begins with a clean slate
            this._trades = [];
            this._fireCanExportEvent(false);
        } else if (state === 'stopped') {
            this._isPlaying = false;
            this._trades = [];
            // F3: force-close ExportPreview first so its pending _saveTimer is cancelled
            // before we delete the draft key — prevents re-creation of the just-deleted entry
            exportPreview.close(true);
            if (this._currentFilename) {
                try {
                    sessionStorage.removeItem(`export_draft_${this._currentFilename}`);
                } catch {
                    // private mode / storage blocked — fail silently
                }
                this._currentFilename = null;
            }
            this._fireCanExportEvent(true);
        } else if (state === 'paused') {
            // _isPlaying stays true; fire canExport(false) to comply with AC6 "bất kỳ state nào"
            this._fireCanExportEvent(false);
        }
    };

    private _onExportConfirmed = (e: Event): void => {
        const { filename } = (e as CustomEvent<{ filename: string }>).detail;
        this._trades = [];
        try {
            sessionStorage.removeItem(`export_draft_${filename}`);
        } catch {
            // fail silently
        }
        // G10: only null _currentFilename if it still matches the confirmed session
        // — prevents clearing state for a subsequent session selected between confirm and handler
        if (this._currentFilename === filename) this._currentFilename = null;
    };

    private _fireCanExportEvent(canExport: boolean): void {
        document.dispatchEvent(
            new CustomEvent('exportpanel:canExport', { detail: { canExport } })
        );
    }
}

export const exportPanel = new ExportPanel();
