# Story 3.2: ExportProgressOverlay — Feedback Realtime và Kết Quả

Status: done

## Story

As a trader,
I want thấy progress step-by-step khi đang ghi Supabase và kết quả rõ ràng khi xong,
So that tôi không bao giờ thấy app im lặng và không biết chuyện gì đang xảy ra.

## Acceptance Criteria

1. **Given** Narron click "Confirm Export" trong ExportPreview (sau khi scroll đến cuối) — **When** `exportpreview:confirmed` CustomEvent fire — **Then** ExportPreview đóng → `ExportProgressOverlay` mở ngay lập tức với State "In Progress": spinner + title "Đang ghi vào Supabase..." + progress steps bắt đầu với "✅ Kết nối thành công" + "⏳ Đang ghi signal_comparisons (0/N)..." + "— signal_cases (chờ)".

2. **Given** `ExportProgressOverlay` đang ở State "In Progress" — **When** backend `POST /api/export` trả về HTTP 200 success — **Then** overlay chuyển sang State "Success": icon ✅ (48px, green-500) + title "Export thành công!" + summary "N rows → signal_comparisons | N rows → signal_cases" + link "Xem trên Supabase →" (mở tab mới) + footer với "Đóng" (secondary) và "Reset Replay" (primary).

3. **Given** `ExportProgressOverlay` đang ở State "In Progress" — **When** backend trả về error (HTTP 500/503/504/409) — **Then** overlay chuyển sang State "Error": icon ❌ (48px, red-500) + title "Export thất bại" + actionable error message từ backend + collapsible "Xem chi tiết kỹ thuật" (raw error text, truncated 200 chars) + footer với "Thử lại" (primary) và "Đóng" (secondary).

4. **Given** `signal_comparisons` ghi thành công nhưng `signal_cases` fail (backend trả về 500 với `"error": "partial_write_rolled_back"`) — **When** overlay nhận error response — **Then** progress text hiển thị rollback info: "Đã rollback signal_comparisons (0/N được giữ lại)" — Error state normal nhưng user biết state sạch, có thể retry an toàn.

5. **Given** Narron click "Thử lại" trong Error state — **When** retry action — **Then** overlay reset về State "In Progress" → gửi lại `POST /api/export` với cùng payload — không cần đóng overlay hay navigate lại ExportPreview.

6. **Given** request đang chạy > 10 giây — **When** timeout chưa xảy ra nhưng đã > 10s — **Then** progress text thêm dòng "Kết nối chậm — đang thử tiếp..." dưới step text — không error, chỉ inform — tiếp tục đợi response.

7. **Given** Narron click "Reset Replay" trong Success state — **When** action — **Then** overlay đóng + `document.dispatchEvent(new CustomEvent('exportprogress:resetReplay'))` fire → Phase 1 ReplayController reset về Setup mode.

8. **Given** Narron click "Đóng" trong Success state hoặc Error state — **When** action — **Then** overlay đóng + Phase 1 giữ nguyên current state — không reset.

9. **Given** `ExportProgressOverlay` đang ở State "In Progress" — **When** Narron nhấn Escape — **Then** không đóng — atomic write đang diễn ra, không interrupt.

10. **Given** `ExportProgressOverlay` đang ở State "Success" hoặc "Error" — **When** Narron nhấn Escape — **Then** "Đóng" action được trigger (giống click "Đóng" button) — overlay đóng.

11. **Given** `ExportProgressOverlay` đang ở State "Error" — **When** Narron nhấn phím `R` — **Then** "Thử lại" action được trigger (giống click "Thử lại" button).

12. **Given** backend trả về HTTP 409 (duplicate) — **When** overlay ở State "In Progress" nhận response — **Then** chuyển sang State "Error" với message: "Session đã export — xóa rows trên Supabase trước nếu muốn re-export" (không phải actionable error hướng dẫn như auth fail — chỉ informational).

## Tasks / Subtasks

- [x] Task 1: Tạo `frontend/ExportProgressOverlay.ts` — toàn bộ component (AC: #1–#12)
  - [x] Implement `class ExportProgressOverlay` với method `open(payload: ExportConfirmedPayload): void` và `close(): void`
  - [x] Constructor: inject `document.body`, render DOM, `document.addEventListener('exportpreview:confirmed', handler)`
  - [x] Render modal 400px wide, centered full-screen backdrop (semi-transparent), z-index cao hơn ExportPreview (z-index: 1300)
  - [x] State machine: `_state: 'idle' | 'in-progress' | 'success' | 'error'`
  - [x] Implement `_showInProgress()` — render spinner + progress lines list
  - [x] Implement `_showSuccess(data: ExportSuccessData)` — render ✅ icon + summary + Supabase link + buttons
  - [x] Implement `_showError(message: string, rawError?: string)` — render ❌ icon + message + collapsible + buttons
  - [x] Implement `_doExport(payload: ExportConfirmedPayload): Promise<void>` — POST fetch + state transitions
  - [x] Save payload to `this._lastPayload` để retry có thể reuse
  - [x] Optimistic progress: sau khi POST bắt đầu, dùng `setTimeout(1500)` advance step 1 → step 2 text (signal_comparisons progress)
  - [x] Slow connection: `setTimeout(10000)` sau khi POST start → nếu response chưa về → thêm "Kết nối chậm — đang thử tiếp..." line
  - [x] Rollback detection: check `response.error === 'partial_write_rolled_back'` → add rollback info vào progress text trước khi show error state
  - [x] Retry logic: `_retryButton` click → `_showInProgress()` → clear timers → `_doExport(this._lastPayload)`
  - [x] Reset Replay: `_resetReplayButton` click → `this.close()` → dispatch `exportprogress:resetReplay` CustomEvent
  - [x] "Xem trên Supabase →" link: href từ `data.supabase_url`, `target="_blank"`, `rel="noopener noreferrer"`
  - [x] Keyboard: `keydown` listener → `Escape` trong non-in-progress state → `close()`; `R` key trong error state → retry
  - [x] Accessibility: `role="alertdialog"`, `aria-modal="true"`, `aria-live="assertive"` trên progress-lines container, focus trap trong modal, focus vào primary button khi state change

- [x] Task 2: Thêm `ExportConfirmedPayload` type vào `frontend/types.ts` (AC: #1)
  - [x] Thêm interface `ExportConfirmedPayload`: `{ filename: string; strategy_name: string; trades: Array<TradePreviewItem & { reasoning_summary: string }>; session_win_rate: number; timeframe: string }`
  - [x] Thêm interface `ExportSuccessData`: `{ signal_comparisons_count: number; signal_cases_count: number; first_signal_id: string; supabase_url: string }`
  - [x] Không thay đổi existing types (`TradeCompletedPayload`, `PreviewResponse`, `TradePreviewItem`)

- [x] Task 3: CSS trong `static/style.css` cho ExportProgressOverlay (AC: #1, #2, #3)
  - [x] `.export-progress-overlay-backdrop`: `position: fixed; inset: 0; background: rgba(0,0,0,0.75); z-index: 1300; display: flex; align-items: center; justify-content: center`
  - [x] `.export-progress-overlay-modal`: `width: 400px; max-width: 90vw; background: var(--sem-bg-panel); border-radius: 8px; border: 1px solid var(--sem-border); padding: 24px`
  - [x] Spinner: `@keyframes epo-spin` + `.epo-spinner`
  - [x] `.epo-progress-lines`, `.epo-success-icon`, `.epo-error-icon`, `.epo-summary`, `.epo-supabase-link`, `.epo-technical-details`, `.epo-footer`, `.epo-details-toggle`

- [x] Task 4: Update `frontend/export_panel.ts` (hoặc entry point) để init `ExportProgressOverlay` (AC: #1)
  - [x] Khởi tạo singleton `exportProgressOverlay` bằng import trong `export_panel.ts`
  - [x] `ExportProgressOverlay` tự listen `exportpreview:confirmed` trong constructor — không cần wiring thêm từ ExportPanel
  - [x] Ghi chú: `ExportPreview.ts` (Story 2.2) dispatch `exportpreview:confirmed` khi Confirm button click — verified đúng pattern

## Dev Notes

### ⚠️ CRITICAL: Phụ Thuộc Prerequisites

Story 3.2 phụ thuộc:
- **Story 2.2**: `ExportPreview.ts` dispatch `exportpreview:confirmed` CustomEvent với detail `{ filename, strategy_name, trades, session_win_rate, timeframe }` — phải đã complete
- **Story 3.1**: `POST /api/export` endpoint hoạt động với error shapes chuẩn (`{ error: string, message: string }`)
- **Story 1.2**: `frontend/types.ts` với `TradeCompletedPayload` interface — phải đã tồn tại

> **Kiểm tra trước khi code:**
> 1. `ExportPreview.ts` dispatch `document.dispatchEvent(new CustomEvent('exportpreview:confirmed', { detail: {...} }))` khi Confirm click
> 2. `POST /api/export` endpoint available và trả về `APIResponse[ExportResponse]` format
> 3. `frontend/types.ts` có `TradeCompletedPayload` với fields: `bar_index`, `entry_timestamp_ms`, `direction`, `entry_price`, `tp_price`, `sl_price`, `result`, `bars_to_exit`

---

### New Files trong Story 3.2

| File | Action |
|------|--------|
| `frontend/ExportProgressOverlay.ts` | **CREATE NEW** |

**Files Modified:**
| File | Change |
|------|--------|
| `frontend/types.ts` | Thêm `ExportConfirmedPayload`, `ExportSuccessData` |
| `frontend/export_panel.ts` (hoặc main entry) | Thêm `new ExportProgressOverlay()` init |
| `static/style.css` | Thêm CSS cho overlay |

---

### `ExportConfirmedPayload` vs `ExportRequest`

Frontend dispatch `exportpreview:confirmed` với shape:
```typescript
// frontend/types.ts — ExportConfirmedPayload (dispatched by ExportPreview.ts)
interface ExportConfirmedPayload {
  filename: string;           // "BTCUSDT_4h_20260420.parquet"
  strategy_name: string;      // User-edited string, default "{symbol}_{timeframe}"
  trades: TradeCompletedPayload[];  // Accumulated từ Story 2.4 ExportPanel
  session_win_rate: number;   // Float: 0.67
  timeframe: string;          // "4h"
}
```

`ExportProgressOverlay._doExport()` map sang `POST /api/export` request body (`ExportRequest` schema trên backend):
```typescript
// Mapping trong _doExport():
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
    reasoning_summary: t.reasoning_summary ?? '',   // Story 2.3 thêm field này vào TradeCompletedPayload
  })),
};
```

> **Note về `reasoning_summary`:** `TradeCompletedPayload` trong Story 1.2 chưa có `reasoning_summary`. Tại Story 2.3 (auto-save), field này được collect từ textareas và merge vào trades data trước khi `exportpreview:confirmed` fires. Dev cần check `ExportPreview.ts` _buildConfirmedPayload() method (Story 2.2/2.3) để xác nhận field đã có.

---

### `ExportProgressOverlay` — Full Implementation

```typescript
import type { ExportConfirmedPayload, ExportSuccessData } from './types';

interface ApiErrorBody {
  error: string;
  message: string;
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
    this._doExport(payload);
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

    // Keyboard handler
    this._keyHandler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && this._state !== 'in-progress') {
        this.close();
      }
      if (e.key === 'r' || e.key === 'R') {
        if (this._state === 'error') this._retry();
      }
    };
    document.addEventListener('keydown', this._keyHandler);
  }

  private _getModal(): HTMLDivElement {
    return this._backdrop!.querySelector('.export-progress-overlay-modal') as HTMLDivElement;
  }

  private _showInProgress(): void {
    this._state = 'in-progress';
    const modal = this._getModal();
    modal.innerHTML = `
      <div style="display:flex;flex-direction:column;align-items:center;gap:12px">
        <div class="epo-spinner"></div>
        <h3 style="margin:0;font-size:16px">Đang ghi vào Supabase...</h3>
      </div>
      <div class="epo-progress-lines" aria-live="assertive">
        <div>✅ Kết nối thành công</div>
        <div id="epo-step-sc">⏳ Đang ghi signal_comparisons...</div>
        <div id="epo-step-cases">— signal_cases (chờ)</div>
      </div>
    `;
    this._progressLines = modal.querySelector('.epo-progress-lines');

    // Optimistic progress: advance after 1.5s
    this._progressTimer = setTimeout(() => {
      const scEl = modal.querySelector('#epo-step-sc');
      if (scEl && this._state === 'in-progress') {
        const n = this._lastPayload?.trades.length ?? 0;
        scEl.textContent = `✅ signal_comparisons (${n}/${n})`;
        const casesEl = modal.querySelector('#epo-step-cases');
        if (casesEl) casesEl.textContent = '⏳ Đang ghi signal_cases...';
      }
    }, 1500);

    // Slow connection warning after 10s
    this._slowTimer = setTimeout(() => {
      if (this._state === 'in-progress' && this._progressLines) {
        const slowEl = document.createElement('div');
        slowEl.textContent = 'Kết nối chậm — đang thử tiếp...';
        slowEl.style.color = 'var(--c-warn, #d97706)';
        this._progressLines.appendChild(slowEl);
      }
    }, 10000);
  }

  private _showSuccess(data: ExportSuccessData): void {
    this._state = 'success';
    this._clearTimers();
    const modal = this._getModal();
    modal.innerHTML = `
      <div class="epo-success-icon">✅</div>
      <h3 style="text-align:center;margin:0 0 8px">Export thành công!</h3>
      <p class="epo-summary">${data.signal_comparisons_count} rows → signal_comparisons | ${data.signal_cases_count} rows → signal_cases</p>
      <a class="epo-supabase-link" href="${data.supabase_url}" target="_blank" rel="noopener noreferrer">Xem trên Supabase →</a>
      <div class="epo-footer">
        <button class="btn-secondary" id="epo-close-btn">Đóng</button>
        <button class="btn-primary" id="epo-reset-btn">Reset Replay</button>
      </div>
    `;
    modal.querySelector('#epo-close-btn')!.addEventListener('click', () => this.close());
    modal.querySelector('#epo-reset-btn')!.addEventListener('click', () => this._resetReplay());
    (modal.querySelector('#epo-reset-btn') as HTMLElement).focus();
  }

  private _showError(message: string, rawError?: string): void {
    this._state = 'error';
    this._clearTimers();
    const modal = this._getModal();
    const rawTruncated = rawError ? rawError.slice(0, 200) : '';
    modal.innerHTML = `
      <div class="epo-error-icon">❌</div>
      <h3 style="text-align:center;margin:0 0 8px">Export thất bại</h3>
      <p class="epo-error-message">${message}</p>
      ${rawTruncated ? `
        <button class="epo-details-toggle" id="epo-toggle-btn">Xem chi tiết kỹ thuật ▶</button>
        <div class="epo-technical-details" id="epo-raw-details" hidden>${rawTruncated}</div>
      ` : ''}
      <div class="epo-footer">
        <button class="btn-secondary" id="epo-close-btn">Đóng</button>
        <button class="btn-primary" id="epo-retry-btn">Thử lại</button>
      </div>
    `;
    modal.querySelector('#epo-close-btn')!.addEventListener('click', () => this.close());
    modal.querySelector('#epo-retry-btn')!.addEventListener('click', () => this._retry());
    if (rawTruncated) {
      modal.querySelector('#epo-toggle-btn')!.addEventListener('click', (e) => {
        const el = modal.querySelector('#epo-raw-details') as HTMLElement;
        el.hidden = !el.hidden;
        (e.target as HTMLElement).textContent = el.hidden
          ? 'Xem chi tiết kỹ thuật ▶'
          : 'Ẩn chi tiết kỹ thuật ▼';
      });
    }
    (modal.querySelector('#epo-retry-btn') as HTMLElement).focus();
  }

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
        reasoning_summary: (t as any).reasoning_summary ?? '',
      })),
    };

    try {
      const resp = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const json = await resp.json();

      if (resp.ok && json.data) {
        this._showSuccess(json.data as ExportSuccessData);
      } else {
        // Handle partial_write_rolled_back — add note to progress before error
        const errBody = (json.detail ?? json) as ApiErrorBody;
        if (errBody.error === 'partial_write_rolled_back' && this._progressLines) {
          const n = payload.trades.length;
          const rollbackNote = document.createElement('div');
          rollbackNote.style.color = 'var(--c-warn, #d97706)';
          rollbackNote.textContent = `Đã rollback signal_comparisons (0/${n} được giữ lại)`;
          this._progressLines.appendChild(rollbackNote);
          // Brief pause so user can read rollback note
          await new Promise(r => setTimeout(r, 800));
        }
        this._showError(errBody.message ?? 'Lỗi không xác định', JSON.stringify(errBody));
      }
    } catch (err) {
      this._showError('Không thể kết nối đến backend — kiểm tra server đang chạy', String(err));
    }
  }

  private _retry(): void {
    if (this._lastPayload) {
      this._showInProgress();
      this._doExport(this._lastPayload);
    }
  }

  private _resetReplay(): void {
    this.close();
    document.dispatchEvent(new CustomEvent('exportprogress:resetReplay'));
  }

  private _clearTimers(): void {
    if (this._slowTimer) { clearTimeout(this._slowTimer); this._slowTimer = null; }
    if (this._progressTimer) { clearTimeout(this._progressTimer); this._progressTimer = null; }
  }
}
```

---

### Tại Sao Optimistic Progress (Không Phải SSE/Polling)

UX spec đề cập "update realtime bằng EventSource hoặc polling mỗi 500ms" nhưng PRD và architecture đã quyết định:
- Backend `POST /api/export` là **synchronous** — không có status endpoint
- Free tier Supabase write cho ~30 rows hoàn thành trong 2–5 giây
- **Quyết định trong Story 3.2:** Dùng `setTimeout` optimistic (1.5s delay) advance step text từ "⏳ Đang ghi signal_comparisons..." → "✅ signal_comparisons (N/N)" trước khi response về
- Sau khi response về: transition sang Success hoặc Error state với actual counts từ response
- **Không fake progress bar từ 0–100%** — chỉ update text labels, không có percentage counter

**Rationale:** Đơn giản hơn nhiều so với SSE/polling. 1 timer, 1 HTTP call, đủ UX feedback cho Narron.

---

### Error Message Mapping

| HTTP Status | `error` field | User-facing message trong `_showError()` |
|-------------|---------------|------------------------------------------|
| 503 | `disabled` | "Supabase integration chưa được bật — set SUPABASE_ENABLED=true trong .env" |
| 409 | `duplicate` | "Session đã export — xóa rows trên Supabase trước nếu muốn re-export" |
| 504 | `timeout` | "Supabase đang wake up — thử lại sau 30 giây" |
| 500 | `partial_write_rolled_back` | "Authentication failed cho signal_cases (RLS enabled) — Kiểm tra SUPABASE_SERVICE_KEY trong .env. Đã rollback signal_comparisons." |
| 500 | `write_failed` | raw message từ backend |
| fetch error | — | "Không thể kết nối đến backend — kiểm tra server đang chạy" |

Backend trả về `APIResponse[T]` format — error body nằm trong `json.detail` (FastAPI HTTPException format) hoặc `json.error`/`json.message`.

> **Note về 409 và Story 3.3:** Story 3.3 sẽ thêm localStorage `export_history` tracking để prevent duplicate UI (show "Đã export" badge thay vì "Export" button trên SessionListPanel). Story 3.2 chỉ handle 409 ở error display — không write localStorage. Story 3.3 sẽ listen `exportprogress:exportSuccess` CustomEvent để write localStorage — dev nên thêm dispatch `document.dispatchEvent(new CustomEvent('exportprogress:exportSuccess', { detail: { filename: payload.filename } }))` trong `_showSuccess()` để Story 3.3 có thể listen.

---

### `exportprogress:resetReplay` — Phase 1 Integration

Khi Narron click "Reset Replay" trong Success state:
```typescript
document.dispatchEvent(new CustomEvent('exportprogress:resetReplay'));
```

**Phase 1 (ReplayController hoặc entry point) cần thêm listener:**
```typescript
document.addEventListener('exportprogress:resetReplay', () => {
  // ReplayController reset về Setup mode
  replayController.dispatch('reset');  // hoặc tương đương
});
```

> **Action cho dev:** Verify Phase 1 `ReplayController` có method/dispatch để reset về setup state. Nếu chưa có listener cho `exportprogress:resetReplay` → thêm vào Phase 1 entry point (không thuộc scope Story 3.2 nhưng phải coordinate).

---

### `ExportProgressOverlay` Init Pattern

```typescript
// Trong frontend/export_panel.ts constructor (hoặc main entry point):
import { ExportProgressOverlay } from './ExportProgressOverlay';

// Singleton — init một lần khi app load
const _exportProgressOverlay = new ExportProgressOverlay();
```

Component tự listen `exportpreview:confirmed` — không cần wiring thêm. Pattern giống `ExportPreview`, `QualityGateBlock`.

---

### Z-Index Hierarchy

| Component | z-index | Note |
|-----------|---------|------|
| SessionListPanel | 1000 | Phase 2 panel |
| ExportPreview | 1100 | Full-screen overlay |
| QualityGateBlock | 1100 | Modal (same level, shows alone) |
| ExportProgressOverlay | 1200 | Highest — shows on top of ExportPreview backdrop |

`ExportProgressOverlay` phải có z-index cao nhất vì nó opens khi ExportPreview đóng (transition). Trong quá trình transition, có thể overlap.

---

### Accessibility Checklist

- `role="alertdialog"` trên backdrop — interrupt screen reader
- `aria-modal="true"` — focus trap
- `aria-live="assertive"` trên `.epo-progress-lines` — screen reader đọc progress updates ngay
- Focus management: khi open → focus vào modal container; khi state change → focus vào primary button
- Không có Escape trong In Progress state — atomic operation constraint
- `R` key cho retry — phím tắt documented (Story 3.3/keyboard shortcut table)

---

### NFR Compliance

- **NFR3 (Medium):** UI feedback < 100ms cho action — overlay open ngay khi `exportpreview:confirmed` fires, trước khi fetch bắt đầu ✓
- **NFR4 (Medium):** Supabase write chạy async — overlay hiển thị feedback trong khi fetch đang chờ ✓
- **NFR14 (High):** Export fail không corrupt Parquet cache — overlay chỉ read payload, không write local files ✓
- **NFR17 (Medium):** Backend log operations — overlay display messages từ backend log (mirror via error response) ✓

---

### Cross-Story Notes

- **Story 2.2** (ExportPreview): Phải confirm `exportpreview:confirmed` được dispatch với full payload khi Confirm button click. Story 3.2 phụ thuộc event này.
- **Story 2.3** (Auto-save): `reasoning_summary` per trade được thêm vào payload trước khi `exportpreview:confirmed` fires — Story 3.2 dùng `(t as any).reasoning_summary` để safe-access field này, tránh TypeScript error nếu Story 2.3 chưa complete.
- **Story 3.3** (Session indicator): Thêm listener `exportprogress:exportSuccess` để track localStorage. Story 3.2 dispatch event này trong `_showSuccess()` (dev cần thêm dispatch — see note trong implementation).
- **Story 4.2** (pytest tests): Tests cho `POST /api/export` response shapes — Story 3.2 frontend expects đúng `APIResponse[ExportResponse]` format.

### References

- [epics.md - Story 3.2 Acceptance Criteria](_bmad-output/planning-artifacts/epics.md#story-32-exportprogressoverlay--feedback-realtime-và-kết-quả)
- [ux-design-specification.md - ExportProgressOverlay 3 states](_bmad-output/planning-artifacts/ux-design-specification.md#L1876-L1920)
- [ux-design-specification.md - Progress text update pattern](_bmad-output/planning-artifacts/ux-design-specification.md#L1963)
- [prd-phase2-supabase.md - FR19, FR20, FR21](_bmad-output/planning-artifacts/prd-phase2-supabase.md)
- [3-1-post-api-export-write-signal-comparisons-va-signal-cases.md - POST /api/export response shapes](_bmad-output/implementation-artifacts/3-1-post-api-export-write-signal-comparisons-va-signal-cases.md)
- [2-2-exportpreview-component-per-trade-list-voi-scroll-gate.md - exportpreview:confirmed CustomEvent](_bmad-output/implementation-artifacts/2-2-exportpreview-component-per-trade-list-voi-scroll-gate.md)
- Story 3.3 — Session exported indicator sẽ listen `exportprogress:exportSuccess` event

## Review Findings (2026-04-27)

### Applied Patches

- **F1+F2**: `_showSuccess` và `_showError` giờ gọi `_getModal()` trả về `null | HTMLDivElement` và early-return nếu `_backdrop` đã bị close — fix crash khi user close trong khi fetch in-flight hoặc trong 800ms rollback pause.
- **F3+F4**: Thêm `escapeHtml()` helper, áp dụng cho `message` và `rawTruncated` trước khi interpolate vào `innerHTML`.
- **F5**: Validate `supabase_url.startsWith('https://')` trước khi dùng trong `href`, fallback về `#` nếu không hợp lệ.
- **F6**: `_showInProgress()` gọi `_clearTimers()` ở đầu — fix timer leak khi retry.
- **F7**: `_render()` remove existing backdrop và keyHandler trước khi tạo mới — fix double backdrop + keyboard listener leak khi `open()` gọi 2 lần.
- **F8 (AC1)**: Render initial step text với `(0/${n})` count ngay từ đầu thay vì chờ optimistic timer.
- **F9 (AC3)**: Swap button order trong Error footer — "Thử lại" (primary) trước "Đóng" (secondary).
- **F10 (AC12)**: Override `errBody.message` client-side cho 409 duplicate — không phụ thuộc backend message string.
- **F11**: Wrap `resp.json()` trong try/catch riêng — non-JSON response (502 HTML) giờ hiển thị `"Lỗi server (HTTP 502)"` thay vì generic "không thể kết nối".

### Deferred

- D1–D4: xem deferred-work.md

### TypeScript

`npx tsc --noEmit` → 0 errors.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

N/A

### Completion Notes List

- `ExportConfirmedPayload.trades` typed as `Array<TradePreviewItem & { reasoning_summary: string }>` (không phải `TradeCompletedPayload[]`) vì `ExportPreview.ts` dispatch `editedTrades` là `TradePreviewItem` + `reasoning_summary` — type chính xác thay vì dùng `(t as any)`.
- z-index đặt 1300 (story spec nói 1200 nhưng QualityGateBlock đang dùng z-index 1200 — tăng lên 1300 để ExportProgressOverlay luôn trên cùng).
- Singleton `exportProgressOverlay` exported — import trong `export_panel.ts` để init tại app startup.
- `exportprogress:exportSuccess` event dispatch trong `_showSuccess()` — Story 3.3 sẽ listen để track localStorage.
- `@keyframes epo-spin` (namespaced) tránh xung đột với bất kỳ `spin` animation nào khác.
- TypeScript: `npx tsc --noEmit` → 0 errors. Python: 41 tests pass.

### File List

- `frontend/ExportProgressOverlay.ts` — **CREATED**: full component với 3 states, keyboard, optimistic progress, rollback detection, retry, resetReplay
- `frontend/types.ts` — Added `ExportConfirmedPayload`, `ExportSuccessData`
- `frontend/export_panel.ts` — Import `exportProgressOverlay` để init singleton
- `static/style.css` — Added ExportProgressOverlay CSS (backdrop, modal, spinner, icons, footer, collapsible)
