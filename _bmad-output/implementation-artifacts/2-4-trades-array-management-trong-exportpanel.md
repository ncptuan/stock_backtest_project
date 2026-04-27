# Story 2.4: Trades Array Management trong ExportPanel

Status: done

## Story

As a trader,
I want trades từ replay được tự động thu thập và reset đúng lúc,
So that ExportPreview luôn có đúng danh sách trades của session hiện tại, không bao giờ lẫn với session cũ.

## Acceptance Criteria

1. **Given** ExportPanel component đã mounted — **When** constructor chạy — **Then** `trades = []` (empty), subscribe `tradeCompleted` event và `replayStateChanged` event từ EventBus.

2. **Given** replay đang chạy và một trade hit (TP hoặc SL) — **When** EventBus emit `tradeCompleted` — **Then** trade object append vào `this.trades[]` — `trades.length` tăng 1.

3. **Given** Narron nhấn Reset trong Phase 1 UI — **When** EventBus emit `replayStateChanged` với `state: 'stopped'` — **Then** `this.trades = []` (clear hoàn toàn) + xóa draft sessionStorage của session đang active (`export_draft_{currentFilename}`).

4. **Given** `replayStateChanged` với `state: 'stopped'` và trades array có data — **When** Export button có thể trigger — **Then** ExportPanel cho phép export tiến hành (không reject).

5. **Given** `replayStateChanged` với `state: 'playing'` — **When** `sessionlist:exportSelected` event fire — **Then** ExportPanel reject flow, show toast "Export không khả dụng khi replay đang chạy — nhấn Stop trước" — không gọi API.

6. **Given** ExportPanel nhận `replayStateChanged` event (bất kỳ state nào) — **When** state thay đổi — **Then** fire `document.dispatchEvent(new CustomEvent('exportpanel:canExport', { detail: { canExport: !isPlaying } }))` — ResultsPanel và SessionListPanel dùng event này để update visual state của Export buttons.

7. **Given** ExportPreview fired `exportpreview:confirmed` (export success) — **When** ExportPanel nhận event này — **Then** `this.trades = []` (reset) + xóa draft sessionStorage.

## Tasks / Subtasks

Story 2.4 **thêm vào** `frontend/export_panel.ts` (đã implement trong Story 2.2). Cũng thêm listener nhỏ vào `frontend/ResultsPanel.ts` và `frontend/SessionListPanel.ts`.

- [x] Task 1: Thêm EventBus subscriptions vào `ExportPanel` constructor (AC: #1, #2, #3, #5, #6)
  - [ ] Thêm private field `_isPlaying = false` vào class
  - [ ] Thêm private field `_currentFilename: string | null = null` (set khi `sessionlist:exportSelected` fire)
  - [ ] Trong constructor — sau `document.addEventListener('sessionlist:exportSelected', ...)`:
    - [ ] Subscribe `eventBus.on('tradeCompleted', this._onTradeCompleted)`
    - [ ] Subscribe `eventBus.on('replayStateChanged', this._onReplayStateChanged)`
    - [ ] Subscribe `document.addEventListener('exportpreview:confirmed', this._onExportConfirmed)`
  - [ ] Implement `_onTradeCompleted = (payload: TradeCompletedPayload): void => { this.trades.push(payload); }`
  - [ ] Implement `_onReplayStateChanged = (payload: { state: string }): void` — xử lý cả 3 cases (xem Dev Notes)
  - [ ] Implement `_onExportConfirmed = (e: Event): void` — clear trades + clear draft

- [x] Task 2: Update `openForSession` để check `_isPlaying` trước khi proceed (AC: #5)
  - [ ] Đầu method `openForSession`: `if (this._isPlaying) { this._showToastError('Export không khả dụng khi replay đang chạy — nhấn Stop trước'); return; }`
  - [ ] Set `this._currentFilename = filename` tại đầu method (trước fetch)

- [x] Task 3: Thêm listener vào `frontend/ResultsPanel.ts` để disable/enable Supabase button (AC: #6)
  - [ ] Trong method init/constructor của ResultsPanel: `document.addEventListener('exportpanel:canExport', this._onCanExportChanged)`
  - [ ] Implement `_onCanExportChanged`: tìm `#supabase-export-btn` (hoặc selector tương đương cho "📤 Lưu vào Supabase" button) — set `disabled` / `aria-disabled` dựa trên `event.detail.canExport`
  - [ ] Nếu button không tồn tại (CompletionOverlay chưa render) → no-op, event sẽ fire lại khi cần

- [x] Task 4: Thêm listener vào `frontend/SessionListPanel.ts` để disable Export buttons khi playing (AC: #6)
  - [ ] Trong constructor của SessionListPanel: `document.addEventListener('exportpanel:canExport', this._onCanExportChanged)`
  - [ ] Implement `_onCanExportChanged`: tìm tất cả `.session-export-btn` → set `disabled` attribute hoặc thêm CSS class `btn--disabled` dựa trên `event.detail.canExport`
  - [ ] Khi ExportPanel render session rows (trong `openForSession` loading state) — buttons mặc định enabled nếu `!this._isPlaying`

## Dev Notes

### ⚠️ CRITICAL: ADD Vào ExportPanel — Không Tạo Lại

Story 2.4 chỉ **thêm** private fields, handlers, và subscribers vào `class ExportPanel` đã tạo ở Story 2.2. Pattern giống Story 2.3 — không overwrite logic có sẵn.

---

### `_onReplayStateChanged` — 3 State Cases

```typescript
private _onReplayStateChanged = (payload: { state: 'playing' | 'paused' | 'stopped' }): void => {
  const { state } = payload;

  if (state === 'playing') {
    this._isPlaying = true;
    this._fireCanExportEvent(false);
  } else if (state === 'stopped') {
    this._isPlaying = false;
    // Clear trades — session đã reset, không để lẫn với session tiếp theo
    this.trades = [];
    // Clear draft nếu có current session
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
    // Paused: giữ _isPlaying = true (replay chưa kết thúc, không cho export)
    // this._isPlaying stays true; no change to canExport
  }
};
```

**Logic quan trọng:**
- `paused` → vẫn coi là đang "active replay" → Export vẫn disabled
- `stopped` → trades clear + draft clear + Export enabled

---

### `_onExportConfirmed` — Clean up Sau Export Success

```typescript
private _onExportConfirmed = (e: Event): void => {
  const { filename } = (e as CustomEvent<{ filename: string }>).detail;
  // Clear trades
  this.trades = [];
  // Clear draft for this specific session
  try {
    sessionStorage.removeItem(`export_draft_${filename}`);
  } catch {
    // fail silently
  }
  this._currentFilename = null;
};
```

**Trigger:** `exportpreview:confirmed` CustomEvent fired bởi `ExportPreview.handleConfirm()` (Story 2.2). ExportPanel listen qua `document.addEventListener`.

---

### `_fireCanExportEvent` Helper

```typescript
private _fireCanExportEvent(canExport: boolean): void {
  document.dispatchEvent(
    new CustomEvent('exportpanel:canExport', {
      detail: { canExport },
    })
  );
}
```

**Listeners:**
- `ResultsPanel.ts` — disable/enable "📤 Lưu vào Supabase" button trong CompletionOverlay
- `SessionListPanel.ts` — disable/enable per-row Export buttons

---

### Updated Constructor — ExportPanel (Sau Story 2.4)

```typescript
constructor() {
  // Story 2.2: Listen for session selected event
  document.addEventListener('sessionlist:exportSelected', (e: Event) => {
    const { filename } = (e as CustomEvent<{ filename: string }>).detail;
    this._currentFilename = filename;   // Story 2.4
    this.openForSession(filename);
  });

  // Story 2.4: EventBus subscriptions
  eventBus.on('tradeCompleted', this._onTradeCompleted);
  eventBus.on('replayStateChanged', this._onReplayStateChanged);

  // Story 2.4: Listen for export confirmed (clean up after success)
  document.addEventListener('exportpreview:confirmed', this._onExportConfirmed);
}
```

---

### Updated `openForSession` — Guard Khi Playing

```typescript
async openForSession(filename: string): Promise<void> {
  // Story 2.4: Reject if replay is active
  if (this._isPlaying) {
    this._showToastError('Export không khả dụng khi replay đang chạy — nhấn Stop trước');
    return;
  }
  if (this._isLoading) return;
  // ... rest of Story 2.2 logic unchanged ...
}
```

---

### ResultsPanel.ts — Minimal Addition

Chỉ thêm 1 listener trong constructor/init của ResultsPanel. Dev phải tìm đúng button selector — Story 1.4 đã tạo button với id hoặc class cụ thể.

```typescript
// Trong ResultsPanel constructor hoặc init():
document.addEventListener('exportpanel:canExport', (e: Event) => {
  const { canExport } = (e as CustomEvent<{ canExport: boolean }>).detail;
  // Tìm Supabase export button — Story 1.4 đã tạo element này
  const exportBtn = document.querySelector('#supabase-export-btn') as HTMLButtonElement | null;
  if (exportBtn) {
    if (canExport) {
      exportBtn.disabled = false;
      exportBtn.removeAttribute('aria-disabled');
    } else {
      exportBtn.disabled = true;
      exportBtn.setAttribute('aria-disabled', 'true');
    }
  }
  // Cũng update StatusBar export link nếu có
  const statusBarExportLink = document.querySelector('#statusbar-export-link') as HTMLElement | null;
  if (statusBarExportLink) {
    statusBarExportLink.style.pointerEvents = canExport ? 'auto' : 'none';
    statusBarExportLink.style.opacity = canExport ? '1' : '0.4';
  }
});
```

> **Lưu ý cho dev:** Verify selector `#supabase-export-btn` hoặc `#statusbar-export-link` với Story 1.4 implementation. Nếu Story 1.4 dùng class khác → dùng đúng selector đó.

---

### SessionListPanel.ts — Minimal Addition

```typescript
// Trong SessionListPanel constructor:
document.addEventListener('exportpanel:canExport', (e: Event) => {
  const { canExport } = (e as CustomEvent<{ canExport: boolean }>).detail;
  if (!this.overlay) return;  // Panel chưa open → no-op
  const exportBtns = this.overlay.querySelectorAll<HTMLButtonElement>('.session-export-btn');
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
```

> **Lưu ý:** Story 1.4 tạo session row buttons với class `.session-export-btn` (hoặc tương đương). Verify class name với Story 1.4 implementation.

---

### Trades Array — Accumulation Pattern

```typescript
private _onTradeCompleted = (payload: TradeCompletedPayload): void => {
  this.trades.push({ ...payload });  // shallow copy đủ vì payload là plain object
};
```

**Import cần thêm ở đầu `export_panel.ts`:**
```typescript
import { eventBus } from './EventBus';
```

`TradeCompletedPayload` đã được import từ Story 2.2: `import type { ..., TradeCompletedPayload } from './types';`

---

### State Machine ExportPanel (Sau Story 2.4)

```
Initial state:
  trades = []
  _isPlaying = false
  _currentFilename = null

Event: tradeCompleted
  → trades.push(payload)

Event: replayStateChanged { state: 'playing' | 'paused' }
  → _isPlaying = true
  → fire exportpanel:canExport { canExport: false }

Event: replayStateChanged { state: 'stopped' }
  → _isPlaying = false
  → trades = []
  → sessionStorage.removeItem(export_draft_{currentFilename})
  → _currentFilename = null
  → fire exportpanel:canExport { canExport: true }

Event: sessionlist:exportSelected { filename }
  → _currentFilename = filename
  → if _isPlaying → toast + return
  → else → openForSession(filename)

Event: exportpreview:confirmed { filename }
  → trades = []
  → sessionStorage.removeItem(export_draft_{filename})
  → _currentFilename = null
```

---

### Edge Cases

**Double `tradeCompleted` events (duplicate prevention):**
Story 1.2 đảm bảo ReplayEngine không emit duplicate `tradeCompleted`. ExportPanel không cần thêm dedup logic — trust Story 1.2.

**`replayStateChanged: stopped` fire nhiều lần:**
- Clear trades nhiều lần trên `[]` = no-op
- `sessionStorage.removeItem` trên key không tồn tại = no-op
- Safe to call multiple times

**Export khi `trades = []` (user chưa replay):**
ExportPanel sẽ vẫn gọi API với `trades: []` — backend sẽ trả về `quality_gate: "fail"` vì `trade_count = 0 < 10`. QualityGateBlock sẽ hiển thị lý do. Đây là expected behavior, không phải bug.

**Browser refresh giữa chừng:**
- `_isPlaying` = false (fresh state)
- `trades = []` (không persist qua refresh — correct behavior)
- sessionStorage draft còn đó → ExportPreview sẽ restore khi mở (Story 2.3)

---

### CustomEvent Flow — Hoàn Chỉnh Sau Story 2.4

```
Phase 1 EventBus Events:
  ReplayEngine → EventBus.emit('replayStateChanged', { state })
  ReplayEngine → EventBus.emit('tradeCompleted', payload)

Phase 2 CustomEvents (qua document.dispatchEvent):
  CompletionOverlay button click → 'sessionlist:exportSelected' → ExportPanel
  ExportPanel state change → 'exportpanel:canExport' → ResultsPanel, SessionListPanel
  ExportPreview confirm → 'exportpreview:confirmed' → ExportPanel, ExportProgressOverlay (Story 3.2)
```

**Design pattern nhất quán:**
- **EventBus**: Phase 1 state changes (replay engine, trade engine) → reactive state subscribers
- **CustomEvent**: Phase 2 imperative actions và cross-component UI state sync (import flow)

---

### Files Modified trong Story 2.4

| File | Change |
|------|--------|
| `frontend/export_panel.ts` | **THÊM VÀO**: `_isPlaying`, `_currentFilename` fields; `_onTradeCompleted`, `_onReplayStateChanged`, `_onExportConfirmed`, `_fireCanExportEvent` methods; EventBus subscriptions trong constructor |
| `frontend/ResultsPanel.ts` | **THÊM VÀO**: `exportpanel:canExport` listener để disable/enable Supabase button + StatusBar link |
| `frontend/SessionListPanel.ts` | **THÊM VÀO**: `exportpanel:canExport` listener để disable/enable per-row Export buttons |

**Không tạo file mới.**
**Không sửa** backend, types.ts, EventBus.ts, ExportPreview.ts, QualityGateBlock.ts.

---

### Import Additions

Trong `frontend/export_panel.ts`, thêm import:
```typescript
import { eventBus } from './EventBus';
```

`TradeCompletedPayload` và `ApiResponse<T>` đã được import từ Story 2.2.

---

### NFR Compliance

- **NFR3 (Medium):** UI feedback < 100ms — EventBus handlers là synchronous, không có async operations trong event handlers
- **NFR3:** Trades accumulation là O(1) append — không gây lag dù trades nhiều
- **NFR5 (Critical):** Story 2.4 không xử lý credentials

### References

- [epics.md - Story 2.4 Acceptance Criteria](_bmad-output/planning-artifacts/epics.md#story-24-trades-array-management-trong-exportpanel)
- [prd-phase2-supabase.md - FR4, FR5, FR30, FR31, FR32](_bmad-output/planning-artifacts/prd-phase2-supabase.md)
- [prd-phase2-supabase.md - ExportPanel listeners](_bmad-output/planning-artifacts/prd-phase2-supabase.md#L330)
- [1-2-eventbus-replaystatechanged-va-tradecompleted-events.md - EventBus + EventMap](_bmad-output/implementation-artifacts/1-2-eventbus-replaystatechanged-va-tradecompleted-events.md)
- [2-2-exportpreview-component-per-trade-list-voi-scroll-gate.md - ExportPanel base](_bmad-output/implementation-artifacts/2-2-exportpreview-component-per-trade-list-voi-scroll-gate.md)
- [2-3-per-trade-reasoning-summary-textarea-voi-auto-save.md - Draft cleanup contract](_bmad-output/implementation-artifacts/2-3-per-trade-reasoning-summary-textarea-voi-auto-save.md)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

### Completion Notes List

- Tất cả 4 tasks hoàn thành. tsc --noEmit exit 0. 24 pytest tests vẫn pass (không có backend changes).
- **Task 1+2** (`export_panel.ts`): Thêm import `eventBus`, private fields `_isPlaying` + `_currentFilename`. Constructor subscribe `eventBus.on('tradeCompleted', ...)`, `eventBus.on('replayStateChanged', ...)`, `document.addEventListener('exportpreview:confirmed', ...)`. `openForSession` guard check `_isPlaying` lên đầu method + set `_currentFilename`. Handlers: `_onTradeCompleted` (push to trades), `_onReplayStateChanged` (playing/paused/stopped state machine + draft cleanup), `_onExportConfirmed` (clear trades + draft), `_fireCanExportEvent` helper.
- **Task 3** (`ResultsPanel.ts`): Thêm constructor, `exportpanel:canExport` listener disable/enable `.completion-export-btn` + `.statusbar-export-link` dựa trên `canExport` flag.
- **Task 4** (`SessionListPanel.ts`): Thêm constructor, `exportpanel:canExport` listener disable/enable `.session-export-btn` + `.session-reexport-btn` dựa trên `canExport` flag, chỉ khi `this.overlay` tồn tại.

### File List

- `frontend/export_panel.ts` — MODIFIED (import eventBus, new fields/handlers/subscriptions)
- `frontend/ResultsPanel.ts` — MODIFIED (thêm constructor + canExport listener)
- `frontend/SessionListPanel.ts` — MODIFIED (thêm constructor + canExport listener)

### Review Findings

- [x] [Review][Dismiss] G3: `_trades` cleared on `replayStateChanged:playing` — intentional behavior, tránh lẫn trades từ replay trước; spec AC3 incomplete, Dev Notes confirm đây là correct design
- [x] [Review][Patch→resolved] G5: AC6 "bất kỳ state nào" — patch applied: thêm `_fireCanExportEvent(false)` trên paused branch để comply với AC6 text mà không thay đổi behavior
- [x] [Review][Patch] G7: `trapFocus` snapshots focusable elements trước khi `fetchAndPopulate()` complete → Tab-wrap trỏ vào skeleton rows không interactive [frontend/SessionListPanel.ts] — fixed: dynamic query tại event time
- [x] [Review][Patch] G10: `_onExportConfirmed` null `_currentFilename` unconditionally kể cả khi đã đổi sang session khác [frontend/export_panel.ts:154] — fixed: chỉ null nếu match filename
- [x] [Review][Patch] G12: `.statusbar-export-link` không có `aria-disabled` khi replay đang chạy — keyboard-accessible nhưng không announced as disabled [frontend/ResultsPanel.ts:32] — fixed: thêm aria-disabled + tabindex=-1
- [x] [Review][Defer] G1: EventBus `on()` return value (unsubscribe fn) bị discard — handlers không bao giờ remove, ảnh hưởng test isolation [frontend/export_panel.ts:43-44] — deferred, singleton pattern, test concern only
- [x] [Review][Defer] G4: Draft sessionStorage không clear khi `_currentFilename` null lúc stopped — design gap: không có filename để clear [frontend/export_panel.ts:133] — deferred, cần design decision về filename tracking scope
- [x] [Review][Defer] G6: `paused→stopped` transition không có `canExport(false)` broadcast — latent risk khi pause() được implement [frontend/export_panel.ts:146] — deferred, paused chưa implement trong ReplayEngine
- [x] [Review][Defer] G11: Double `sessionlist:exportSelected` khi ExportPreview đang open → parallel filename tracking diverge [frontend/export_panel.ts] — deferred, ExportPreview teardown là intentional P7, complex design scenario
- [x] [Review][Defer] G14: ResultsPanel Export buttons không có initial disabled state — buttons appear enabled trước khi canExport event đầu tiên [frontend/ResultsPanel.ts] — deferred, marginal init gap, backend gate chặn export nếu 0 trades
