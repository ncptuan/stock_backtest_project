# Story 2.2: ExportPreview Component — Per-Trade List với Scroll Gate

Status: done

## Story

As a trader,
I want xem toàn bộ danh sách trades trong ExportPreview và phải scroll đến cuối trước khi có thể confirm,
So that tôi không vô tình commit data mình chưa review.

## Acceptance Criteria

1. **Given** Narron click "Export" button trên một session row trong SessionListPanel — **When** ExportPreview mở — **Then** full-screen overlay hiển thị với: summary bar sticky top (trade count, win rate, quality gate status) + scrollable trade list + strategy name input (default: `{symbol}_{timeframe}`) + scroll progress "Đã xem 0/N trades".

2. **Given** ExportPreview vừa mở với 31 trades — **When** Narron chưa scroll — **Then** "Confirm Export" button có `aria-disabled="true"` và không clickable — không thể bypass.

3. **Given** Narron scroll đến trade cuối cùng (IntersectionObserver detect row cuối visible) — **When** trade cuối visible trong viewport — **Then** "Confirm Export" button enable với brief glow animation 1 lần + scroll progress update thành "Đã xem 31/31 trades".

4. **Given** session bị quality gate fail (trade count < 10 hoặc win rate < 55%) — **When** Narron click "Export" trên session row đó — **Then** QualityGateBlock modal mở (không phải ExportPreview) — hiển thị lý do cụ thể, không có override button.

5. **Given** ExportPreview đang hiển thị — **When** Narron nhấn ✕ hoặc Escape — **Then** nếu chưa edit bất kỳ textarea nào → đóng ngay, không confirm dialog; nếu đã edit → confirm dialog "Đóng preview? Draft đã lưu — có thể tiếp tục sau".

6. **Given** ExportPreview mở cho session có `quality_gate: "pass"` — **When** Narron Ctrl+Enter — **Then** nếu Confirm button đã enabled → trigger confirm action.

7. **Given** ExportPanel nhận `sessionlist:exportSelected` CustomEvent với `{ filename }` — **When** event fire — **Then** ExportPanel gọi `POST /api/sessions/{filename}/preview`, route đến QualityGateBlock (fail) hoặc ExportPreview (pass) dựa trên response.

## Tasks / Subtasks

- [x] Task 1: Tạo `frontend/ExportPreview.ts` — component chính (AC: #1, #2, #3, #5, #6)
  - [ ] Implement `class ExportPreview` với `open(data: PreviewResponse, filename: string): void` và `close(force?: boolean): void`
  - [ ] Render full-screen overlay với header + summary bar sticky top + trade list + footer sticky bottom
  - [ ] Summary bar: trade count, win rate (%), quality gate badge, strategy name input (default: `{symbol}_{timeframe}`)
  - [ ] Render mỗi trade row: trade #N, timestamp, LONG/SHORT, Entry/TP/SL prices, WIN/LOSS outcome, reasoning_summary textarea (pre-filled từ `reasoning_template`)
  - [ ] Footer: scroll progress "Đã xem 0/N trades" + Confirm Export button (disabled bằng `aria-disabled="true"` + CSS pointer-events)
  - [ ] Implement IntersectionObserver trên trade row cuối — khi visible: enable Confirm button + glow animation + update scroll progress về N/N
  - [ ] Scroll progress update: theo dõi số rows đã intersect — update "Đã xem X/N trades"
  - [ ] Close: `✕` + Escape → check `_hasEdited` flag → đóng ngay hoặc confirm dialog
  - [ ] Ctrl+Enter shortcut: trigger confirm nếu button enabled
  - [ ] Accessibility: `role="dialog"`, `aria-modal="true"`, focus trap, `aria-disabled` trên Confirm button

- [x] Task 2: Tạo `frontend/QualityGateBlock.ts` — quality gate blocked modal (AC: #4)
  - [ ] Implement `class QualityGateBlock` với `open(reason: string): void` và `close(): void`
  - [ ] Render modal 480px, icon ⚠️, title, reason block (1 hoặc 2 ❌ reasons), explanation text, Đóng button
  - [ ] Reason text format: "8 trades — cần tối thiểu 10" và/hoặc "43% win rate — cần tối thiểu 55%"
  - [ ] Không có override button
  - [ ] Accessibility: `role="alertdialog"`, `aria-describedby` trỏ explanation, focus vào Đóng button khi mở
  - [ ] Escape/Đóng → close modal

- [x] Task 3: Mở rộng `frontend/export_panel.ts` từ stub thành partial implementation (AC: #7)
  - [ ] Thêm `trades: TradeCompletedPayload[] = []` field (sẽ được populate bởi Story 2.4 EventBus wiring)
  - [ ] Implement `openForSession(filename: string): Promise<void>` — gọi POST API, route đến đúng component
  - [ ] Implement `_callPreviewApi(filename: string): Promise<ApiResponse<PreviewResponse>>` — fetch helper
  - [ ] Listen `document.addEventListener('sessionlist:exportSelected', handler)` trong constructor
  - [ ] Route: `quality_gate === "fail"` → `qualityGateBlock.open(reason)`, `quality_gate === "pass"` → `exportPreview.open(data, filename)`
  - [ ] Loading state: khi fetch đang chạy → show inline loading indicator (hoặc disable Export button trong SessionListPanel — acceptable)
  - [ ] Error fallback: nếu fetch fail → toast error message

- [x] Task 4: Thêm types vào `frontend/types.ts` (AC: #1, #7)
  - [ ] Thêm `PreviewResponse` interface matching backend `PreviewResponse` schema
  - [ ] Thêm `TradePreviewItem` interface (TradeInput fields + `reasoning_template: string`)
  - [ ] Verify `TradeCompletedPayload` (từ Story 1.2) đã tồn tại trong EventMap — không duplicate

- [x] Task 5: CSS cho ExportPreview + QualityGateBlock trong `static/style.css` (AC: #1, #2, #3, #4)
  - [ ] ExportPreview: `position: fixed; inset: 0; z-index: 1100; background: var(--sem-bg-app)` (full-screen, higher z-index than SessionListPanel)
  - [ ] Summary bar: `position: sticky; top: 0; background: var(--sem-bg-panel); border-bottom: 1px solid var(--sem-border)`
  - [ ] Trade list: `overflow-y: auto; flex: 1` (scrollable, fills remaining height)
  - [ ] Footer: `position: sticky; bottom: 0; background: var(--sem-bg-panel); border-top: 1px solid var(--sem-border)`
  - [ ] Confirm button disabled state: `opacity: 0.4; pointer-events: none` → enabled: `opacity: 1; pointer-events: auto`
  - [ ] Glow animation: `@keyframes confirmGlow { 0% { box-shadow: 0 0 0 0 ... } 100% { box-shadow: none } }` — 1 lần, 800ms
  - [ ] Trade row states: default, in-viewport (yellow left border), reviewed (green left border)
  - [ ] QualityGateBlock modal: `width: 480px; max-width: 90vw`

## Dev Notes

### ⚠️ CRITICAL: Phụ Thuộc Prerequisites

Story 2.2 phụ thuộc:
- **Story 1.2**: `frontend/EventBus.ts`, `frontend/types.ts` với `TradeCompletedPayload` — EventBus singleton phải tồn tại
- **Story 1.4**: `frontend/export_panel.ts` stub (sẽ được expand trong story này), `sessionlist:exportSelected` CustomEvent pattern
- **Story 2.1**: `POST /api/sessions/{filename}/preview` endpoint phải hoạt động

> **Kiểm tra trước khi code:**
> 1. `frontend/EventBus.ts` tồn tại với `eventBus` singleton
> 2. `frontend/export_panel.ts` tồn tại (stub từ Story 1.4)
> 3. `backend/routes/sessions.py` có `POST /sessions/{filename}/preview` endpoint

---

### ⚠️ Story 2.2 vs Story 2.3 — Phân Chia Trách Nhiệm

Story 2.2 và Story 2.3 implement hai phần của cùng `ExportPreview` component:

| Story | Phần | Trách nhiệm |
|-------|------|-------------|
| **2.2** (này) | ExportPreview shell + scroll gate | Full-screen overlay, summary bar, trade rows (with textarea), IntersectionObserver, QualityGateBlock |
| **2.3** | Auto-save + restore + validation | `sessionStorage` draft save/restore, blank warning, character counter expand |

> **Story 2.2** tạo `ExportPreview` với textareas được **render** và **pre-filled**, nhưng chưa có:
> - Auto-save draft logic (Story 2.3)
> - sessionStorage restore (Story 2.3)
> - Character counter expand-on-focus (Story 2.3)
> - Blank textarea warning (Story 2.3)
>
> Khi Story 2.3 arrive, dev sẽ **thêm vào** `ExportPreview.ts` không phải tạo lại từ đầu.

---

### `frontend/ExportPreview.ts` — Implementation Đầy Đủ

```typescript
import type { PreviewResponse, TradePreviewItem } from './types';

export class ExportPreview {
  private overlay: HTMLElement | null = null;
  private data: PreviewResponse | null = null;
  private filename: string | null = null;
  private _hasEdited = false;
  private _confirmEnabled = false;
  private _scrollObserver: IntersectionObserver | null = null;
  private _reviewedCount = 0;

  open(data: PreviewResponse, filename: string): void {
    this.data = data;
    this.filename = filename;
    this._hasEdited = false;
    this._confirmEnabled = false;
    this._reviewedCount = 0;
    this.render();
    this.setupIntersectionObserver();
    document.addEventListener('keydown', this.handleKeyDown);
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
    const totalTrades = data.trade_count;
    const winRatePct = Math.round(data.win_rate * 100);
    const defaultStrategy = `${data.symbol}_${data.timeframe}`;

    this.overlay = document.createElement('div');
    this.overlay.className = 'export-preview-overlay';
    this.overlay.setAttribute('role', 'dialog');
    this.overlay.setAttribute('aria-modal', 'true');
    this.overlay.setAttribute('aria-label', 'Export Preview');

    this.overlay.innerHTML = `
      <div class="export-preview-panel">
        <div class="export-preview-header">
          <span class="export-preview-title">
            Export Preview — ${data.symbol} ${data.timeframe.toUpperCase()} | ${data.date}
          </span>
          <button class="export-preview-close" aria-label="Đóng">✕</button>
        </div>

        <div class="export-preview-summary" role="region" aria-label="Tóm tắt session">
          <span class="summary-stat">${totalTrades} trades</span>
          <span class="summary-stat quality-pass">${winRatePct}% win rate ✅</span>
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

    // Wire close buttons
    this.overlay.querySelector('.export-preview-close')!
      .addEventListener('click', () => this.close());

    // Wire Confirm button (only fires when not aria-disabled)
    const confirmBtn = this.overlay.querySelector('#confirm-export-btn') as HTMLButtonElement;
    confirmBtn.addEventListener('click', () => {
      if (this._confirmEnabled) this.handleConfirm();
    });

    // Wire strategy name
    const strategyInput = this.overlay.querySelector('#strategy-name-input') as HTMLInputElement;
    strategyInput.addEventListener('input', () => { this._hasEdited = true; });

    // Wire textarea dirty tracking (Story 2.3 will add auto-save on top)
    this.overlay.querySelectorAll('.trade-reasoning-textarea').forEach((ta) => {
      ta.addEventListener('input', () => { this._hasEdited = true; });
    });

    document.body.appendChild(this.overlay);

    // Focus first focusable
    (this.overlay.querySelector('.export-preview-close') as HTMLElement)?.focus();
  }

  private renderTradeRow(trade: TradePreviewItem, index: number, total: number): string {
    const isLast = index === total - 1;
    const outcomeClass = trade.result === 'win' ? 'outcome-win' : 'outcome-loss';
    const outcomeText = trade.result === 'win' ? 'WIN' : 'LOSS';
    const entryDate = new Date(trade.entry_timestamp_ms).toISOString().slice(0, 10);

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
          <span class="trade-direction direction-${trade.direction.toLowerCase()}">${trade.direction}</span>
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
          maxlength="500"
          placeholder="Nhập reasoning cho trade này..."
          aria-label="Reasoning cho trade #${index + 1}"
        >${this.escapeHtml(trade.reasoning_template)}</textarea>
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

    // Track reviewed count via intersection
    this._scrollObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const rowEl = entry.target as HTMLElement;
          if (entry.isIntersecting) {
            rowEl.classList.add('trade-row--in-viewport');
            if (!rowEl.classList.contains('trade-row--reviewed')) {
              rowEl.classList.add('trade-row--reviewed');
              this._reviewedCount++;
              this.updateScrollProgress(allRows.length);
            }
            // Enable confirm when last row visible
            if (rowEl.dataset.last === 'true' && !this._confirmEnabled) {
              this.enableConfirm();
            }
          } else {
            rowEl.classList.remove('trade-row--in-viewport');
          }
        });
      },
      {
        root: tradeList as HTMLElement,
        threshold: 0.3,  // 30% visible counts as "reviewed"
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
  }

  private updateScrollProgress(total: number): void {
    const progressEl = this.overlay?.querySelector('#scroll-progress');
    if (progressEl) {
      progressEl.textContent = `Đã xem ${this._reviewedCount}/${total} trades`;
    }
  }

  private showCloseConfirmDialog(): void {
    const confirmed = window.confirm(
      'Đóng preview? Draft đã lưu — có thể tiếp tục sau.'
    );
    if (confirmed) this.cleanup();
  }

  private handleConfirm(): void {
    const strategyInput = this.overlay?.querySelector('#strategy-name-input') as HTMLInputElement;
    const strategyName = strategyInput?.value.trim() || `${this.data!.symbol}_${this.data!.timeframe}`;

    // Collect current textarea values (Story 3.x will POST to /api/export)
    const textareas = this.overlay?.querySelectorAll('.trade-reasoning-textarea') ?? [];
    const editedTrades = Array.from(textareas).map((ta, i) => ({
      ...this.data!.trades[i],
      reasoning_summary: (ta as HTMLTextAreaElement).value,
    }));

    // Fire export-ready event — Story 3.x ExportProgressOverlay will listen
    const event = new CustomEvent('exportpreview:confirmed', {
      detail: {
        filename: this.filename,
        strategy_name: strategyName,
        trades: editedTrades,
        session_win_rate: this.data!.win_rate,
        timeframe: this.data!.timeframe,
      },
    });
    document.dispatchEvent(event);

    this.cleanup(true);  // force close, no dirty check
  }

  private cleanup(force = false): void {
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
    // Ctrl+Enter to confirm
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && this._confirmEnabled) {
      e.preventDefault();
      this.handleConfirm();
    }
  };

  private escapeHtml(str: string): string {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  private escapeAttr(str: string): string {
    return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
}

export const exportPreview = new ExportPreview();
```

---

### `frontend/QualityGateBlock.ts` — Implementation

```typescript
export class QualityGateBlock {
  private overlay: HTMLElement | null = null;

  open(reason: string): void {
    this.render(reason);
    document.addEventListener('keydown', this.handleKeyDown);
  }

  close(): void {
    this.overlay?.remove();
    this.overlay = null;
    document.removeEventListener('keydown', this.handleKeyDown);
  }

  private render(reason: string): void {
    this.overlay?.remove();

    // reason may contain semicolon-separated items: "7 trades — cần tối thiểu 10; 48% win rate — cần tối thiểu 55%"
    const reasons = reason.split(';').map((r) => r.trim()).filter(Boolean);

    this.overlay = document.createElement('div');
    this.overlay.className = 'quality-gate-overlay';

    this.overlay.innerHTML = `
      <div class="quality-gate-modal" role="alertdialog" aria-modal="true"
           aria-describedby="quality-gate-explanation">
        <div class="quality-gate-icon">⚠️</div>
        <h2 class="quality-gate-title">Session chưa đủ điều kiện export</h2>
        <div class="quality-gate-reasons">
          ${reasons.map((r) => `<div class="quality-gate-reason">❌ ${r}</div>`).join('')}
        </div>
        <p class="quality-gate-explanation" id="quality-gate-explanation">
          Sample nhỏ có thể cho kết quả ngẫu nhiên. Bot học tốt hơn từ sessions có đủ data.
        </p>
        <div class="quality-gate-footer">
          <button class="btn-primary quality-gate-close-btn" autofocus>Đóng</button>
        </div>
      </div>
    `;

    // Backdrop click closes
    this.overlay.addEventListener('click', (e) => {
      if (e.target === this.overlay) this.close();
    });

    this.overlay.querySelector('.quality-gate-close-btn')!
      .addEventListener('click', () => this.close());

    document.body.appendChild(this.overlay);

    // Focus Đóng button (accessibility: alertdialog must focus first)
    (this.overlay.querySelector('.quality-gate-close-btn') as HTMLElement)?.focus();
  }

  private handleKeyDown = (e: KeyboardEvent): void => {
    if (e.key === 'Escape') {
      e.preventDefault();
      this.close();
    }
  };
}

export const qualityGateBlock = new QualityGateBlock();
```

---

### `frontend/export_panel.ts` — Expand From Stub

**File đã được tạo là stub trong Story 1.4.** Story 2.2 thay thế hoàn toàn nội dung stub:

```typescript
import type { PreviewResponse, ApiResponse } from './types';
import type { TradeCompletedPayload } from './types';  // từ EventMap
import { exportPreview } from './ExportPreview';
import { qualityGateBlock } from './QualityGateBlock';

/**
 * ExportPanel — Orchestrates export flow:
 * 1. Listen for 'sessionlist:exportSelected' CustomEvent
 * 2. POST /api/sessions/{filename}/preview với accumulated trades
 * 3. Route → QualityGateBlock (fail) hoặc ExportPreview (pass)
 *
 * STORY 2.4 sẽ add:
 * - EventBus subscription để populate this.trades[]
 * - Export button enable/disable logic
 */
export class ExportPanel {
  // Trades array — populated by Story 2.4 via EventBus 'tradeCompleted'
  // Story 2.2: empty array (ExportPreview tests with mock data directly)
  trades: TradeCompletedPayload[] = [];

  private _isLoading = false;

  constructor() {
    // Listen for export selected event from SessionListPanel
    document.addEventListener('sessionlist:exportSelected', (e: Event) => {
      const { filename } = (e as CustomEvent<{ filename: string }>).detail;
      this.openForSession(filename);
    });
  }

  async openForSession(filename: string): Promise<void> {
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
    const response = await fetch(`/api/sessions/${encodeURIComponent(filename)}/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trades: this.trades }),
    });
    return response.json() as Promise<ApiResponse<PreviewResponse>>;
  }

  private _showToastError(message: string): void {
    // Assumes toastManager singleton from Phase 1 (Story 1.x)
    // Fallback: console.error if not available
    if (typeof (window as any).toastManager !== 'undefined') {
      (window as any).toastManager.show(message, 'error');
    } else {
      console.error('[ExportPanel]', message);
    }
  }
}

export const exportPanel = new ExportPanel();
```

> **IMPORTANT:** `this.trades` sẽ là `[]` cho đến khi Story 2.4 wires EventBus. Preview API nhận empty trades → sẽ trả về `quality_gate: "fail"` với reason "0 trades". Đây là expected behavior khi stories chưa complete. Dev không cần fix điều này trong Story 2.2 — Story 2.4 sẽ fix.

---

### `frontend/types.ts` — Additions

Thêm vào `types.ts` (sau `SessionItem`, `ApiResponse<T>` đã thêm trong Story 1.4):

```typescript
// --- Phase 2: Preview response types ---

export interface TradePreviewItem {
  bar_index: number;
  entry_timestamp_ms: number;           // Unix ms int64 (ADR-03)
  direction: 'LONG' | 'SHORT';
  entry_price: number;
  tp_price: number;
  sl_price: number;
  result: 'win' | 'loss';
  bars_to_exit: number;
  reasoning_template: string;           // Pre-filled từ backend — editable bởi Narron
}

export interface PreviewResponse {
  symbol: string;                        // "BTCUSDT"
  timeframe: string;                     // "4h"
  date: string;                          // "2026-04-20"
  trade_count: number;
  win_rate: number;                      // 0.67 (not percentage)
  quality_gate: 'pass' | 'fail';
  quality_gate_reason: string | null;    // null khi pass
  trades: TradePreviewItem[];
}

export type PreviewApiResponse = ApiResponse<PreviewResponse>;
```

> **Verify:** `ApiResponse<T>` đã có từ Story 1.4. `TradeCompletedPayload` đã có từ Story 1.2 EventMap. Không duplicate.

---

### CustomEvent Architecture — Story 1.4 → Story 2.2 → Story 3.x

```
SessionListPanel (Story 1.4)
  → fires: document.dispatchEvent(new CustomEvent('sessionlist:exportSelected', { detail: { filename } }))

ExportPanel (Story 2.2)
  → listens: 'sessionlist:exportSelected'
  → POST /api/sessions/{filename}/preview
  → routes to QualityGateBlock OR ExportPreview

ExportPreview (Story 2.2)
  → fires: document.dispatchEvent(new CustomEvent('exportpreview:confirmed', { detail: { filename, strategy_name, trades, session_win_rate, timeframe } }))

ExportProgressOverlay (Story 3.2)
  → listens: 'exportpreview:confirmed'
  → POST /api/export
  → shows progress + result
```

**Lý do dùng CustomEvent thay vì EventBus:**
- Export flow là imperative action sequence (không phải reactive state change)
- Components không biết nhau trực tiếp — CustomEvent bridge qua document
- PRD Technical Architecture: "Direct fetch call đến backend — không qua EventBus (export là imperative action)"

---

### CSS — Key Declarations

Thêm vào `static/style.css`:

```css
/* ExportPreview — Full-screen overlay */
.export-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 1100;  /* > SessionListPanel z-index 1000 */
  background: var(--sem-bg-app, #0d1117);
  display: flex;
  flex-direction: column;
}

.export-preview-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}

.export-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--sem-border);
  flex-shrink: 0;
}

.export-preview-summary {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 16px;
  background: var(--sem-bg-panel);
  border-bottom: 1px solid var(--sem-border);
  position: sticky;
  top: 0;
  z-index: 10;
  flex-shrink: 0;
}

.export-preview-trade-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 16px;
}

.export-preview-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--sem-bg-panel);
  border-top: 1px solid var(--sem-border);
  position: sticky;
  bottom: 0;
  flex-shrink: 0;
}

/* Confirm button states */
.confirm-export-btn[aria-disabled="true"] {
  opacity: 0.4;
  pointer-events: none;
  cursor: not-allowed;
}

.confirm-export-btn.confirm-export-btn--enabled {
  opacity: 1;
  pointer-events: auto;
}

/* Glow animation — plays once when button enables */
@keyframes confirmGlow {
  0%   { box-shadow: 0 0 0 0 rgba(56, 139, 253, 0.7); }
  50%  { box-shadow: 0 0 12px 6px rgba(56, 139, 253, 0.4); }
  100% { box-shadow: 0 0 0 0 rgba(56, 139, 253, 0); }
}

.confirm-glow {
  animation: confirmGlow 0.8s ease-out forwards;
}

/* Trade row states */
.trade-row {
  padding: 12px;
  border-radius: 4px;
  margin-bottom: 8px;
  border-left: 2px solid transparent;
  transition: border-color 0.2s;
}

.trade-row--in-viewport {
  border-left-color: var(--prim-yellow-300, #d29922);
}

.trade-row--reviewed {
  border-left-color: var(--sem-entry, #3fb950);
  opacity: 0.85;
}

/* QualityGateBlock */
.quality-gate-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
}

.quality-gate-modal {
  background: var(--sem-bg-panel);
  border-radius: 8px;
  width: 480px;
  max-width: 90vw;
  padding: 24px;
  text-align: center;
}

.quality-gate-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.quality-gate-reasons {
  text-align: left;
  margin: 16px 0;
}

.quality-gate-reason {
  padding: 6px 0;
  color: var(--sem-loss, #f85149);
}

/* Strategy name input */
.strategy-name-input {
  background: var(--sem-bg-surface);
  border: 1px solid var(--sem-border);
  border-radius: 4px;
  padding: 4px 8px;
  color: var(--sem-text-primary);
  font-size: 13px;
  width: 200px;
}

/* Trade reasoning textarea */
.trade-reasoning-textarea {
  width: 100%;
  background: var(--sem-bg-surface);
  border: 1px solid var(--sem-border);
  border-radius: 4px;
  color: var(--sem-text-primary);
  font-size: 12px;
  font-family: inherit;
  padding: 6px 8px;
  resize: none;
  box-sizing: border-box;
  margin-top: 6px;
}
```

---

### New Files Created in Story 2.2

| File | Action |
|------|--------|
| `frontend/ExportPreview.ts` | **CREATE NEW** |
| `frontend/QualityGateBlock.ts` | **CREATE NEW** |

### Files Modified in Story 2.2

| File | Change |
|------|--------|
| `frontend/export_panel.ts` | **REPLACE stub** với full ExportPanel implementation |
| `frontend/types.ts` | Thêm `TradePreviewItem`, `PreviewResponse`, `PreviewApiResponse` |
| `static/style.css` | Thêm ExportPreview + QualityGateBlock CSS declarations |

**Không sửa:**
- `backend/` — Story 2.1 đã provide API endpoint
- `frontend/EventBus.ts` — không touch
- `frontend/SessionListPanel.ts` — không touch
- `backend/main.py` — không touch

---

### IntersectionObserver — Scroll Gate Kỹ Thuật

Pattern IntersectionObserver được sử dụng thay vì `scroll` event vì:
- Không gây performance issue (no per-scroll callback)
- Chính xác về "element đã visible" — không phải "user đã scroll đến đây"
- Tương thích với keyboard navigation (Tab → focus scroll)

**Root element:** `#trade-list-scroll` div (không phải `window`) để limit observation đến scrollable container

**Threshold `0.3`:** 30% của trade row visible = đủ để count là "reviewed" — balance giữa strict (100%) và loose (1%)

**Edge case — 0 trades:** Nếu `data.trade_count === 0`, skip IntersectionObserver và enable Confirm button ngay lập tức. Empty session → no trades to review → allow confirm.

**Edge case — session được scroll nhanh:** User scroll rất nhanh, IntersectionObserver có thể miss một vài rows. Trade-off này được chấp nhận — Narron cần scroll qua *trade cuối cùng*, không cần dừng tại mỗi trade.

---

### Accessibility — ExportPreview

```
role="dialog"
aria-modal="true"
aria-label="Export Preview"

Confirm button:
  - Disabled: aria-disabled="true" (không dùng disabled attribute — giữ focusable cho keyboard)
  - aria-describedby="scroll-progress" (reader thông báo: "Confirm Export — Đã xem 12/31 trades")

QualityGateBlock:
  - role="alertdialog" (blocking intent)
  - aria-describedby="quality-gate-explanation"
  - autofocus trên Đóng button khi mở

Focus trap: Tab không thoát ra ngoài modal (pattern giống SessionListPanel từ Story 1.4)
```

> **Tại sao `aria-disabled` thay vì `disabled` attribute?**
> HTML `disabled` attribute khiến button không focusable và bị skip bởi Tab navigation + screen reader. `aria-disabled="true"` giữ element focusable (reader có thể announce nó) nhưng CSS `pointer-events: none` chặn click. Đây là accessibility best practice cho "conditionally enabled" buttons.

---

### `exportpreview:confirmed` Event — Contract với Story 3.x

Khi Narron confirm export, ExportPreview fire event:

```typescript
new CustomEvent('exportpreview:confirmed', {
  detail: {
    filename: string,           // "BTCUSDT_4h_20260420.parquet"
    strategy_name: string,      // Narron's input, default "{symbol}_{timeframe}"
    trades: TradeExportItem[],  // trades với reasoning_summary edited by Narron
    session_win_rate: number,   // 0.67
    timeframe: string,          // "4h"
  }
})
```

Story 3.2 `ExportProgressOverlay` sẽ listen event này và POST `/api/export`.

---

### NFR Compliance

- **NFR3 (Medium):** UI feedback < 100ms — ExportPreview render là synchronous DOM operation; POST API call runs async; không block UI
- **NFR2 (Medium):** Export preview render < 500ms — render là synchronous DOM write; API response time handled by Story 2.1
- **NFR5 (Critical):** Không hardcode credentials — ExportPanel không handle credentials, Story 4.3 validates env

### References

- [epics.md - Story 2.2 Acceptance Criteria](_bmad-output/planning-artifacts/epics.md#story-22-exportpreview-component--per-trade-list-với-scroll-gate)
- [ux-design-specification.md - ExportPreview Anatomy + Behaviors](_bmad-output/planning-artifacts/ux-design-specification.md#2-exportpreview)
- [ux-design-specification.md - QualityGateBlock Anatomy](_bmad-output/planning-artifacts/ux-design-specification.md#3-qualitygateblock)
- [ux-design-specification.md - Phase 2 Keyboard Shortcuts](_bmad-output/planning-artifacts/ux-design-specification.md#phase-2-keyboard-shortcuts)
- [prd-phase2-supabase.md - FR6, FR7, FR8, FR9, FR10, FR11, FR12, FR36](_bmad-output/planning-artifacts/prd-phase2-supabase.md)
- [prd-phase2-supabase.md - UX-DR5, UX-DR7, UX-DR8, UX-DR12, UX-DR13](_bmad-output/planning-artifacts/prd-phase2-supabase.md)
- [2-1-get-api-sessions-filename-preview-trade-list-voi-reasoning-templates.md - POST /api/sessions/{filename}/preview contract](_bmad-output/implementation-artifacts/2-1-get-api-sessions-filename-preview-trade-list-voi-reasoning-templates.md)
- [1-4-sessionlistpanel-ui-browse-va-chon-session.md - sessionlist:exportSelected CustomEvent](_bmad-output/implementation-artifacts/1-4-sessionlistpanel-ui-browse-va-chon-session.md)
- NFR2: Preview < 500ms; NFR3: UI feedback < 100ms

## Review Findings (2026-04-27)

### Patches Applied
- [x] P1 — Escape `symbol`, `timeframe`, `date`, `direction`, `entryDate` before innerHTML interpolation
- [x] P2 — Escape `defaultStrategy` with `escapeAttr()` in `value="..."` attribute
- [x] P3 — `escapeHtml()`: add `"` → `&quot;` escaping
- [x] P4 — `QualityGateBlock`: add `escapeHtml()` helper; escape each reason before innerHTML
- [x] P5 — IntersectionObserver `threshold: 0.3` → `threshold: 0` (1px pixel fires, prevents tall-row deadlock)
- [x] P6 — Remove redundant `updateScrollProgress` call from observer loop for non-last rows; single canonical call from `enableConfirm`
- [x] P7 — Teardown at top of `open()`: disconnect `_scrollObserver`, `removeEventListener` (prevents orphaned observer + double-open issues)
- [x] P8 — Clear `_trades = []` on `'playing'` state (prevents trades bleeding across replay restarts)
- [x] P9 — Use `data.trades.length` (not `data.trade_count`) as `totalTrades` for rendering
- [x] P10 — `handleConfirm`: use `data-trade-index` attribute to align textareas to trades (not positional zip)
- [x] P11 — Add quality gate status badge (`✅ PASS` / `❌ FAIL`) to summary bar (AC#1)
- [x] P12 — Remove trailing period from `window.confirm()` text (exact AC#5 text)
- [x] P13 — `QualityGateBlock.open()`: defensive `removeEventListener` before `addEventListener`

### Deferred
- B11/D-B11: `window.confirm()` suppressed in sandboxed iframes — defer custom DOM dialog (MVP runs standalone)
- E3: `close(force)` vs `cleanup(clearDraft)` parameter naming — cosmetic, no functional impact
- E2: null-guard on `data.trades` — backend schema guarantees array

### Result: TypeScript 0 errors, 41 pytest passed

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

### Completion Notes List

- All 5 tasks completed. tsc --noEmit exit 0. 24 pytest tests still pass (no new backend tests for pure-frontend story).
- IntersectionObserver root set to `#trade-list-scroll` container, threshold 0.3 per spec.
- Confirm button disabled via `aria-disabled="true"` + CSS `pointer-events: none`; enabled via `removeAttribute('aria-disabled')` + 800ms `confirmGlow` animation.
- QualityGateBlock splits reason by `;` to render per-reason `❌` lines.
- ExportPanel stub replaced; constructor listens `sessionlist:exportSelected`; routes to qualityGateBlock (fail) or exportPreview (pass).
- `static/style.css` created (new file); linked from `<head>` of `static/index.html`.

### File List

- `frontend/ExportPreview.ts` — CREATED
- `frontend/QualityGateBlock.ts` — CREATED
- `frontend/export_panel.ts` — MODIFIED (stub replaced)
- `frontend/types.ts` — MODIFIED (TradePreviewItem, PreviewResponse, PreviewApiResponse added)
- `static/style.css` — CREATED
- `static/index.html` — MODIFIED (link rel stylesheet style.css added)
