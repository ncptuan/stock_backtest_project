# Story 3.3: Session Exported Indicator và Duplicate Prevention

Status: done

## Story

As a trader,
I want sessions đã export có visual indicator rõ ràng và không thể export lại vô tình,
So that tôi không bao giờ ghi duplicate data vào Supabase Backtest DB.

## Acceptance Criteria

1. **Given** export thành công cho session `BTCUSDT_4h_20260420.parquet` (Story 3.2 dispatch `exportprogress:exportSuccess`) — **When** event received — **Then** `localStorage` key `export_history` được cập nhật: `{ "BTCUSDT_4h_20260420.parquet": { "date": "2026-04-27" } }` — persist qua browser refresh.

2. **Given** `localStorage.export_history` có entry cho session `BTCUSDT_4h_20260420.parquet` — **When** SessionListPanel render session row đó — **Then** session row hiển thị badge gray "Đã export 27/04" thay vì "Export" button.

3. **Given** session row ở trạng thái `already-exported` trong SessionListPanel — **When** Narron muốn re-export — **Then** "Re-export" button xuất hiện thay vì "Export" — click → toast warning: `"Session đã export ngày 27/04. Backend sẽ từ chối nếu rows chưa được xóa trên Supabase"` — không mở ExportPreview ngay lập tức, toast dừng lại ở đây.

4. **Given** Narron click "Re-export" và đọc toast warning — **When** Narron click "Re-export" lần thứ hai (sau toast đã hiển thị) — **Then** ExportPreview mở bình thường cho session đó — cho phép Narron tiếp tục nếu biết mình muốn override (backend sẽ trả về 409 nếu rows vẫn còn trên Supabase).

5. **Given** `POST /api/export` trả về HTTP 409 (duplicate từ backend) — **When** `ExportProgressOverlay` nhận 409 — **Then** Error state hiển thị message: `"Session đã export — xóa rows trên Supabase trước nếu muốn re-export"` — không crash, không silent fail — cũng update localStorage nếu chưa có entry (backend là source of truth).

6. **Given** localStorage bị clear (hoặc first run trên browser mới) — **When** SessionListPanel load — **Then** tất cả sessions hiển thị "Export" button — không có indicator — backend là source of truth cho duplicate detection; localStorage chỉ là UI cache.

7. **Given** export thành công — **When** user mở SessionListPanel lần tiếp theo (kể cả sau refresh) — **Then** session vừa export hiển thị badge "Đã export {DD/MM}" — data persist qua browser session.

8. **Given** Narron dùng cùng app trên browser mới (localStorage empty) — **When** Narron thử export lại session đã export trước đó — **Then** SessionListPanel không có indicator (localStorage empty) → ExportPreview mở → confirm → backend trả về 409 → `ExportProgressOverlay` Error state hiển thị message 409 → localStorage được update với entry mới → SessionListPanel lần sau sẽ có indicator.

## Tasks / Subtasks

- [x] Task 1: Tạo `frontend/ExportHistory.ts` — localStorage helper module (AC: #1, #2, #6, #7)
  - [x] Implement `class ExportHistory` (singleton hoặc module với static methods)
  - [x] Implement `recordExport(filename: string, date: string): void` — ghi vào localStorage key `export_history`
  - [x] Implement `getExportDate(filename: string): string | null` — trả về date string hoặc null nếu chưa export
  - [x] Implement `isExported(filename: filename: string): boolean` — shorthand check
  - [x] Implement `getAllHistory(): Record<string, { date: string }>` — read full history object
  - [x] localStorage key: `"export_history"` (string literal — không dùng constant từ file khác)
  - [x] Date format: `"YYYY-MM-DD"` internal, display format `"DD/MM"` trong badge (derived từ stored string)
  - [x] JSON.parse với try/catch — nếu corrupted localStorage → return empty object (degrade gracefully)
  - [x] Không ghi gì nếu `filename` blank/null

- [x] Task 2: Tạo listener `exportprogress:exportSuccess` trong entry point (AC: #1)
  - [x] Trong `frontend/export_panel.ts` constructor (hoặc main entry point): thêm `document.addEventListener('exportprogress:exportSuccess', handler)`
  - [x] Handler gọi `ExportHistory.recordExport(detail.filename, detail.date)` với current date
  - [x] Verify Story 3.2 (`ExportProgressOverlay._showSuccess()`) dispatch `exportprogress:exportSuccess` với detail: `{ filename: string, date: string }` — nếu chưa có → add dispatch vào `ExportProgressOverlay._showSuccess()` (cross-story action)

- [x] Task 3: Update `frontend/SessionListPanel.ts` — render `already-exported` state (AC: #2, #3, #4, #8)
  - [x] Trong method render session row: check `ExportHistory.isExported(session.filename)`
  - [x] Nếu exported: render badge `<span class="session-exported-badge">Đã export {DD/MM}</span>` + button `<button class="btn-re-export">Re-export</button>` (thay vì "Export" button thông thường)
  - [x] Nếu chưa exported: render "Export" button thông thường (existing behavior — không thay đổi)
  - [x] `Re-export` button first click: dispatch toast warning → set flag `_pendingReExport[filename] = true` (in-memory, không persist)
  - [x] `Re-export` button second click (sau khi `_pendingReExport[filename] === true`): proceed với `openForSession(filename)` bình thường → clear pending flag sau khi proceed
  - [x] Toast text: `"Session đã export ngày {DD/MM}. Backend sẽ từ chối nếu rows chưa được xóa trên Supabase"`
  - [x] Khi SessionListPanel mở lại (mới render): `_pendingReExport` reset về empty — mỗi lần open panel là fresh state
  - [x] Import `ExportHistory` từ `./ExportHistory`

- [x] Task 4: Handle HTTP 409 trong `ExportProgressOverlay.ts` — update localStorage (AC: #5, #8)
  - [x] Trong `_doExport()`: nếu response status 409 (và error `"duplicate"`) → gọi `ExportHistory.recordExport(payload.filename, today)` để update localStorage (backend là source of truth)
  - [x] Error message cho 409: `"Session đã export — xóa rows trên Supabase trước nếu muốn re-export"` (đã có trong Story 3.2 mapping table — confirm message khớp)
  - [x] Sau khi recordExport() trong 409 case: `_showError(message)` như bình thường (không close overlay)
  - [x] Import `ExportHistory` từ `./ExportHistory`

- [x] Task 5: CSS cho `already-exported` state và badge (AC: #2, #3)
  - [x] `.session-exported-badge`: `color: var(--sem-text-muted, #6b7280); font-size: 12px; font-style: italic`
  - [x] `.btn-re-export`: style giống secondary button nhưng với `color: var(--sem-text-muted)` — visual cue rằng đây là cautionary action
  - [x] Session row `already-exported` state: background hơi dim so với normal rows — `opacity: 0.85` hoặc `background: color-mix(in srgb, var(--sem-bg-surface) 90%, transparent)`
  - [x] Thêm vào `static/style.css`

## Dev Notes

### ⚠️ CRITICAL: Phụ Thuộc Prerequisites

Story 3.3 phụ thuộc:
- **Story 1.4**: `frontend/SessionListPanel.ts` đã tồn tại với session row rendering — story này **ADD** `already-exported` state
- **Story 3.2**: `ExportProgressOverlay.ts` phải dispatch `exportprogress:exportSuccess` trong `_showSuccess()` — **nếu chưa có → phải thêm vào Story 3.2's file trước khi implement 3.3**
- **Story 1.2**: `frontend/types.ts` tồn tại

> **Kiểm tra trước khi code:**
> 1. `frontend/SessionListPanel.ts` tồn tại với method `open()` và session row rendering
> 2. `ExportProgressOverlay._showSuccess()` dispatch `exportprogress:exportSuccess` với `{ filename, date }` detail
> 3. `static/style.css` tồn tại (thêm styles vào cuối file)

---

### New Files trong Story 3.3

| File | Action |
|------|--------|
| `frontend/ExportHistory.ts` | **CREATE NEW** |

**Files Modified:**
| File | Change |
|------|--------|
| `frontend/SessionListPanel.ts` | Thêm `already-exported` row state + Re-export button logic |
| `frontend/ExportProgressOverlay.ts` | Thêm `ExportHistory.recordExport()` trong 409 path + dispatch `exportprogress:exportSuccess` trong success path (nếu Story 3.2 chưa thêm) |
| `frontend/export_panel.ts` (hoặc main entry) | Thêm listener `exportprogress:exportSuccess` |
| `static/style.css` | Thêm CSS cho exported badge + re-export button |

---

### `ExportHistory` — Full Implementation

```typescript
// frontend/ExportHistory.ts

const STORAGE_KEY = 'export_history';

interface ExportRecord {
  date: string;  // "YYYY-MM-DD"
}

type ExportHistoryMap = Record<string, ExportRecord>;

function _load(): ExportHistoryMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (typeof parsed === 'object' && parsed !== null) return parsed as ExportHistoryMap;
  } catch {
    // Corrupted localStorage — degrade gracefully
  }
  return {};
}

function _save(history: ExportHistoryMap): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
  } catch {
    // Storage quota exceeded — silently fail (non-critical feature)
  }
}

export const ExportHistory = {
  recordExport(filename: string, date: string): void {
    if (!filename) return;
    const history = _load();
    history[filename] = { date };
    _save(history);
  },

  getExportDate(filename: string): string | null {
    if (!filename) return null;
    const history = _load();
    return history[filename]?.date ?? null;
  },

  isExported(filename: string): boolean {
    return ExportHistory.getExportDate(filename) !== null;
  },

  getAllHistory(): ExportHistoryMap {
    return _load();
  },

  /** Format stored "YYYY-MM-DD" → display "DD/MM" */
  formatDisplayDate(isoDate: string): string {
    const [year, month, day] = isoDate.split('-');
    return `${day}/${month}`;
  },
};
```

---

### `SessionListPanel.ts` — Updated Row Rendering Pattern

```typescript
// Trong SessionListPanel.ts — method _renderSessionRow(session: SessionItem)
import { ExportHistory } from './ExportHistory';

private _renderSessionRow(session: SessionItem, isCurrentSession: boolean): HTMLElement {
  const row = document.createElement('div');
  row.className = 'session-row' + (isCurrentSession ? ' session-row--current' : '');

  const exportedDate = ExportHistory.getExportDate(session.filename);
  
  if (exportedDate) {
    // Already exported state
    const displayDate = ExportHistory.formatDisplayDate(exportedDate);
    row.innerHTML = `
      <span class="session-info">${session.symbol} ${session.timeframe} ${session.date}</span>
      <span class="session-exported-badge">Đã export ${displayDate}</span>
      <button class="btn-re-export" data-filename="${session.filename}" data-export-date="${displayDate}">Re-export</button>
    `;
    const reExportBtn = row.querySelector('.btn-re-export') as HTMLButtonElement;
    reExportBtn.addEventListener('click', () => this._handleReExport(session.filename, displayDate));
  } else {
    // Normal export state
    row.innerHTML = `
      <span class="session-info">${session.symbol} ${session.timeframe} ${session.date}</span>
      <button class="btn-export" data-filename="${session.filename}">Export</button>
    `;
    row.querySelector('.btn-export')!.addEventListener('click', () => {
      document.dispatchEvent(new CustomEvent('sessionlist:exportSelected', { detail: { filename: session.filename } }));
      this.close();
    });
  }
  
  return row;
}

// In-memory pending re-export flags (reset on each panel open)
private _pendingReExport: Record<string, boolean> = {};

private _handleReExport(filename: string, displayDate: string): void {
  if (!this._pendingReExport[filename]) {
    // First click: show toast warning, set pending flag
    this._pendingReExport[filename] = true;
    // Dispatch toast — follow existing Toast pattern in project
    document.dispatchEvent(new CustomEvent('toast:show', {
      detail: {
        message: `Session đã export ngày ${displayDate}. Backend sẽ từ chối nếu rows chưa được xóa trên Supabase`,
        type: 'warning',
        duration: 5000,
      },
    }));
  } else {
    // Second click: proceed with export
    this._pendingReExport[filename] = false;
    document.dispatchEvent(new CustomEvent('sessionlist:exportSelected', { detail: { filename } }));
    this.close();
  }
}
```

> **Note về Toast pattern:** Check hiện tại project dispatch toast như thế nào. Story 1.4 dùng `Toast` singleton — check `frontend/Toast.ts` hoặc match Event pattern hiện có. Nếu dùng singleton: `toastSingleton.show(message, 'warning', 5000)`. Nếu dùng CustomEvent: `document.dispatchEvent(new CustomEvent('toast:show', { detail: { ... } }))`.

---

### `ExportProgressOverlay.ts` — 409 Path Addition

```typescript
// Trong ExportProgressOverlay._doExport() — trong block `if (!resp.ok)`:

const errBody = (json.detail ?? json) as ApiErrorBody;

// Handle 409 duplicate — update localStorage so SessionListPanel will show indicator
if (resp.status === 409 && errBody.error === 'duplicate') {
  const today = new Date().toISOString().slice(0, 10);  // "YYYY-MM-DD"
  ExportHistory.recordExport(this._lastPayload!.filename, today);
}

// Existing rollback check for partial_write_rolled_back...
if (errBody.error === 'partial_write_rolled_back' && this._progressLines) {
  // ... existing rollback note code
}

this._showError(errBody.message ?? 'Lỗi không xác định', JSON.stringify(errBody));
```

---

### `ExportProgressOverlay._showSuccess()` — exportSuccess Dispatch (Cross-Story Coordination)

Story 3.2 should have added this dispatch in `_showSuccess()`. **Verify it exists.** If not, add it:

```typescript
private _showSuccess(data: ExportSuccessData): void {
  this._state = 'success';
  this._clearTimers();

  // Story 3.3 requires: dispatch exportprogress:exportSuccess for localStorage tracking
  const today = new Date().toISOString().slice(0, 10);  // "YYYY-MM-DD"
  document.dispatchEvent(new CustomEvent('exportprogress:exportSuccess', {
    detail: { filename: this._lastPayload!.filename, date: today },
  }));

  // ... rest of existing _showSuccess DOM rendering
}
```

---

### localStorage `export_history` — Data Format

```
localStorage['export_history'] = JSON.stringify({
  "BTCUSDT_4h_20260420.parquet": { "date": "2026-04-27" },
  "ETHUSDT_1h_20260415.parquet": { "date": "2026-04-25" },
  ...
})
```

**Key:** `session.filename` — phải khớp chính xác với filename từ `GET /api/sessions` response (case-sensitive).

**Rationale tại sao dùng `filename` làm key (không phải `signal_id` prefix hay URL):**
- `filename` là immutable identifier cho session — không thay đổi kể cả khi strategy_name thay đổi
- Đủ unique trong scope của một developer's local machine
- Consistent với `sessionlist:exportSelected` CustomEvent payload đã dùng `filename`

---

### Two-Click Re-Export Pattern — Design Intent

**Tại sao cần 2 click để re-export:**
1. Ngăn accidental re-export khi Narron vô tình click "Re-export"
2. Toast warning giải thích context (cần xóa rows trên Supabase trước)
3. Narron đọc warning → nếu vẫn muốn proceed → click lần 2

**Tại sao KHÔNG block hoàn toàn:**
- Backend sẽ trả về 409 nếu rows vẫn còn — đó là safety net cuối cùng
- Narron có thể đã xóa rows thủ công trên Supabase trước khi re-export
- localStorage chỉ là UI cache — không phải source of truth

**UX flow chi tiết:**
```
[Session row: "BTCUSDT 4H — Đã export 27/04"] [Re-export button]
       ↓ 1st click
[Toast: "Session đã export ngày 27/04. Backend sẽ từ chối..."] (5s)
[Re-export button — vẫn hiển thị]
       ↓ 2nd click (trong session panel open)
[SessionListPanel close] → [ExportPreview open bình thường]
       ↓ Confirm → POST /api/export
       ↓ Nếu rows vẫn còn Supabase: 409 → ExportProgressOverlay Error: "Xóa rows trước"
       ↓ Nếu rows đã được xóa: success → localStorage update date mới
```

---

### AC #4 Clarification — Toast Disappears Between Clicks

Sau khi toast appear (5s) và disappear, `_pendingReExport[filename]` vẫn là `true` cho đến khi:
- Panel bị đóng và mở lại (reset trong `open()`)
- Narron click Re-export lần 2 và proceed

Điều này có nghĩa: ngay cả khi toast đã disappear, click thứ 2 trong same panel session vẫn proceed. Narron không cần đọc toast trong thời gian toast còn hiển thị — intent là "một lần warning, sau đó proceed nếu confirm".

---

### FR33 Reference

> **FR33:** Session list hiển thị visual indicator cho sessions đã export *(CRITICAL — prevent duplicate)*

Story 3.3 là implementation của FR33. `localStorage` approach là intentional decision — được xác nhận trong PRD:
> "localStorage chỉ là UI cache — backend là source of truth cho duplicate detection"

---

### NFR Compliance

- **NFR14 (High):** Export fail không corrupt Parquet cache — story này chỉ đụng đến localStorage, không parquet ✓
- **FR17 (Critical):** Duplicate export bị từ chối dựa trên session filename — Backend 409 là primary guard, localStorage là UI convenience layer ✓

---

### Cross-Story Notes

- **Story 1.4** (`SessionListPanel.ts`): Story 3.3 extends existing session row rendering. Không replace existing code — ADD `ExportHistory.isExported()` check và conditional render.
- **Story 3.2** (`ExportProgressOverlay.ts`): Must dispatch `exportprogress:exportSuccess` in `_showSuccess()`. If missing → add as part of Story 3.3 implementation (coordinate with dev who implemented 3.2).
- **Story 4.2** (pytest tests): 409 duplicate detection is backend-side — Story 3.3's localStorage is frontend-only, no backend tests needed.

### References

- [epics.md - Story 3.3 Acceptance Criteria](_bmad-output/planning-artifacts/epics.md#story-33-session-exported-indicator-và-duplicate-prevention)
- [ux-design-specification.md - SessionListPanel already-exported state](_bmad-output/planning-artifacts/ux-design-specification.md#L1766)
- [ux-design-specification.md - Re-export toast behavior](_bmad-output/planning-artifacts/ux-design-specification.md#L1773)
- [prd-phase2-supabase.md - FR33, FR17](_bmad-output/planning-artifacts/prd-phase2-supabase.md)
- [1-4-sessionlistpanel-ui-browse-va-chon-session.md - SessionListPanel.ts already-exported read from localStorage](_bmad-output/implementation-artifacts/1-4-sessionlistpanel-ui-browse-va-chon-session.md)
- [3-2-exportprogressoverlay-feedback-realtime-va-ket-qua.md - exportprogress:exportSuccess dispatch + 409 handling](_bmad-output/implementation-artifacts/3-2-exportprogressoverlay-feedback-realtime-va-ket-qua.md)

## Review Findings (2026-04-27)

### Applied Patches

- **F1**: `_load()` thêm `!Array.isArray(parsed)` guard — JSON array không còn pass qua làm ExportHistoryMap.
- **F2**: `recordExport()` thêm `!date` guard — blank date không được ghi vào localStorage.
- **F3**: `formatDisplayDate()` guard empty string và malformed parts → trả về `'??/??'` thay vì blank/garbage.
- **F4**: 409 path trong `ExportProgressOverlay._doExport()` mở rộng từ `errBody.error === 'duplicate'` thành bất kỳ `resp.status === 409` — localStorage write và message override áp dụng cho mọi 409 response.
- **F5**: Thêm `!ExportHistory.isExported(filename)` guard trước `recordExport` trong 409 path — chỉ ghi nếu chưa có entry (spec: "if no entry yet").
- **F6**: `displayDate` fallback từ `'?'` → `'??/??'` (consistent với formatDisplayDate fallback).
- **F7**: `escapeHtml(displayDate)` trước khi interpolate vào toast message — phòng XSS nếu toastManager dùng innerHTML.

### Deferred

- F8: `exportpanel:canExport` listener trong constructor không remove — singleton pattern, defer (same as stories 2.4, 3.3)
- Array-stored-in-localStorage silent degradation — acceptable per spec design

### TypeScript

`npx tsc --noEmit` → 0 errors.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

### Completion Notes List

- ✅ Task 1: Tạo `frontend/ExportHistory.ts` — module với static methods, localStorage key `export_history`, JSON.parse graceful degradation, `formatDisplayDate()` YYYY-MM-DD → DD/MM.
- ✅ Task 2: Thêm import `ExportHistory` + listener `exportprogress:exportSuccess` trong `export_panel.ts` constructor. Thêm `date` field vào dispatch trong `ExportProgressOverlay._doExport()` (Story 3.2 dispatch thiếu date).
- ✅ Task 3: Update `SessionListPanel.ts` — import `ExportHistory`, thêm `_pendingReExport: Record<string, boolean> = {}`, reset trong `open()`, dùng `ExportHistory.getAllHistory()` thay inline method, format DD/MM với `formatDisplayDate()`, 2-click re-export với toast warning, xóa `getExportHistory()` inline method.
- ✅ Task 4: Update `ExportProgressOverlay.ts` — import `ExportHistory`, 409 path gọi `ExportHistory.recordExport(payload.filename, today)` trước khi `_showError()`.
- ✅ Task 5: CSS thêm vào `static/style.css` — `.session-exported-badge`, `.session-reexport-btn`, `.session-row.already-exported`.
- ✅ Validation: `npx tsc --noEmit` sạch. `python3 -m pytest tests/ -q` → 41 passed.

### File List

- `frontend/ExportHistory.ts` — **TẠO MỚI** (localStorage helper)
- `frontend/ExportProgressOverlay.ts` — thêm import ExportHistory, date field vào exportSuccess dispatch, 409 → recordExport
- `frontend/SessionListPanel.ts` — thêm import ExportHistory, `_pendingReExport`, 2-click re-export, DD/MM format, toast
- `frontend/export_panel.ts` — thêm import ExportHistory, listener `exportprogress:exportSuccess`
- `static/style.css` — thêm CSS Story 3.3

## Change Log

- 2026-04-27: Story 3.3 implemented — Session exported indicator + duplicate prevention. ExportHistory localStorage module, 2-click re-export guard, 409 localStorage sync.
