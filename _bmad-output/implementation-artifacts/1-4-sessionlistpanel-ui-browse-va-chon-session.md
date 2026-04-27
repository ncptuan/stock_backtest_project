# Story 1.4: SessionListPanel — UI Browse và Chọn Session

Status: done

## Story

As a trader,
I want xem danh sách sessions trong một panel và chọn session để bắt đầu export flow,
so that tôi có thể tìm đúng session muốn export mà không cần nhớ tên file.

## Acceptance Criteria

1. **Given** Narron vừa hoàn thành replay (CompletionOverlay hiển thị) và `SUPABASE_ENABLED=true` — **When** CompletionOverlay render — **Then** button "📤 Lưu vào Supabase" xuất hiện cạnh nút Reset.

2. **Given** `SUPABASE_ENABLED=false` — **When** CompletionOverlay render — **Then** button "📤 Lưu vào Supabase" không hiển thị — Phase 1 UI giữ nguyên.

3. **Given** Narron click "📤 Lưu vào Supabase" trong CompletionOverlay — **When** click event — **Then** CompletionOverlay dismiss ngay lập tức → SessionListPanel mở với danh sách sessions từ `GET /api/sessions`.

4. **Given** SessionListPanel mở — **When** sessions đang load từ API — **Then** skeleton loader hiển thị — không blank screen.

5. **Given** SessionListPanel có sessions — **When** Narron nhìn vào mỗi session row — **Then** thấy: symbol, timeframe, date, và "Export" button (hoặc trạng thái "Đã export {date}" nếu đã export).

6. **Given** Narron nhấn Escape hoặc click nút Đóng trong SessionListPanel — **When** close action — **Then** SessionListPanel đóng lại — không có side effect, không trigger export.

7. **Given** StatusBar ở Complete mode và `SUPABASE_ENABLED=true` — **When** CompletionOverlay đã dismiss — **Then** StatusBar hiển thị secondary "Export" link text bên phải — click mở lại SessionListPanel.

8. **Given** SessionListPanel — **When** mở lần đầu sau khi Narron vừa replay xong session X — **Then** session X được highlight là session hiện tại.

## Tasks / Subtasks

- [ ] Task 1: Tạo `frontend/SessionListPanel.ts` — component chính (AC: #3, #4, #5, #6, #8)
  - [ ] Implement `class SessionListPanel` với `open(currentSessionFilename?: string): void` và `close(): void`
  - [ ] Gọi `GET /api/sessions` khi open — hiển thị skeleton loader trong khi load
  - [ ] Render modal 680px × 80vh với session list scrollable
  - [ ] Render mỗi session row: symbol + timeframe + date + "Export" button
  - [ ] Highlight row của `currentSessionFilename` khi được cung cấp
  - [ ] `already-exported` rows: đọc từ `localStorage` key `export_history`, render "Đã export {date}" thay vì "Export"
  - [ ] Close: Escape key + nút Đóng → gọi `close()`
  - [ ] Accessibility: `role="dialog"`, `aria-label="Danh sách sessions"`, focus trap, Escape dismiss

- [ ] Task 2: Tạo `frontend/types.ts` — thêm `SessionItem` type (AC: #5)
  - [ ] Thêm interface `SessionItem` matching backend response: `filename`, `symbol`, `timeframe`, `date`, `exported`
  - [ ] Thêm interface `SessionsApiResponse` matching `APIResponse[SessionItem[]]` shape: `{ data: SessionItem[] | null, error: { message: string, code: string, retryable: boolean } | null }`

- [ ] Task 3: Sửa `frontend/ResultsPanel.ts` — thêm Phase 2 entry points trong CompletionOverlay (AC: #1, #2, #3, #7)
  - [ ] Trong method render CompletionOverlay: thêm button "📤 Lưu vào Supabase" chỉ khi `window.__SUPABASE_ENABLED__ === true`
  - [ ] Button click handler: dismiss CompletionOverlay → gọi `sessionListPanel.open(currentSessionFilename)`
  - [ ] StatusBar Complete mode: thêm `[📤 Export]` link text bên phải — chỉ khi `SUPABASE_ENABLED=true`
  - [ ] StatusBar Export link click: gọi `sessionListPanel.open()`

- [ ] Task 4: Tạo `frontend/export_panel.ts` — stub ExportPanel (AC: #5, #6)
  - [ ] Implement `class ExportPanel` với `openForSession(sessionFilename: string): void`
  - [ ] STUB ONLY trong story này — chỉ cần method tồn tại để SessionListPanel có thể delegate
  - [ ] Log `console.log('[ExportPanel] openForSession:', sessionFilename)` — full implement trong Story 2.x

- [ ] Task 5: Inject SUPABASE_ENABLED flag vào frontend (AC: #1, #2)
  - [ ] Trong `static/index.html`: thêm `<script>window.__SUPABASE_ENABLED__ = {{ supabase_enabled }};</script>` trước app.js load
  - [ ] Trong `backend/routes/static.py` (hoặc `main.py`): inject `settings.supabase_enabled` vào HTML template khi serve `index.html`
  - [ ] Frontend code đọc từ `window.__SUPABASE_ENABLED__` — không gọi backend endpoint riêng

- [ ] Task 6: CSS cho SessionListPanel (AC: #4, #5, #8)
  - [ ] Modal overlay: `position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 1000`
  - [ ] Panel: `width: 680px; max-height: 80vh; background: var(--sem-bg-panel); border-radius: 8px; overflow: hidden; display: flex; flex-direction: column`
  - [ ] Session row highlight current: `background: color-mix(in srgb, var(--sem-entry) 15%, transparent); border-left: 2px solid var(--sem-entry)`
  - [ ] Skeleton loader: 3 placeholder rows với `background: var(--sem-bg-surface); animate shimmer`
  - [ ] Already-exported badge: `color: var(--sem-text-muted); font-size: 12px`

## Dev Notes

### ⚠️ CRITICAL: Đây là Story Frontend đầu tiên — phụ thuộc vào Stories 1.2 và 1.3

Story 1.4 phụ thuộc:
- **Story 1.2**: `EventBus.ts`, `types.ts`, `ReplayEngine.ts` — phải tồn tại trước
- **Story 1.3**: `GET /api/sessions` endpoint — phải hoạt động
- **Story 1.1**: `backend/settings.py` với `supabase_enabled` field

> **Kiểm tra prerequisite:** `frontend/EventBus.ts` và `frontend/types.ts` phải tồn tại. Nếu không → dừng lại, chạy story 1.2 trước.

### Architecture Warning: snake_case vs PascalCase Filenames

Architecture doc (Naming Patterns section) nói files TypeScript dùng `snake_case.ts`. Nhưng Story 1.2 đã tạo `EventBus.ts`, `ReplayEngine.ts` (PascalCase). Story này **phải follow pattern đã establish trong Story 1.2**:

| File | Convention áp dụng |
|------|-------------------|
| `frontend/SessionListPanel.ts` | PascalCase — nhất quán với EventBus.ts, ReplayEngine.ts |
| `frontend/export_panel.ts` | snake_case — HOẶC `ExportPanel.ts` — phải nhất quán với story 1.2 pattern |

> **Quyết định cho dev:** Kiểm tra `frontend/` hiện có các file nào, follow exact casing đã dùng trong Story 1.2.

### SUPABASE_ENABLED Injection Pattern

Backend `settings.supabase_enabled` phải được biết bởi frontend. Pattern đúng là **server-side injection vào HTML**, không phải:
- ❌ API endpoint `/api/config` — round-trip không cần thiết
- ❌ Hardcode trong TypeScript
- ❌ Env var trong esbuild (không an toàn)

**Cách implement:**

```python
# backend/routes/static.py (hoặc trong main.py)
from fastapi.responses import HTMLResponse
from pathlib import Path
from backend.settings import settings

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    html = Path("static/index.html").read_text()
    # Inject settings vào HTML trước khi serve
    html = html.replace(
        "{{ supabase_enabled }}",
        "true" if settings.supabase_enabled else "false"
    )
    return HTMLResponse(content=html)
```

```html
<!-- static/index.html — trong <head> TRƯỚC script app.js -->
<script>
  window.__SUPABASE_ENABLED__ = {{ supabase_enabled }};
</script>
<script src="/static/app.js" defer></script>
```

**TypeScript sử dụng:**
```typescript
// Bất kỳ component nào cần check
declare const __SUPABASE_ENABLED__: boolean; // global từ window

function isSupabaseEnabled(): boolean {
  return typeof window !== 'undefined' && (window as any).__SUPABASE_ENABLED__ === true;
}
```

### `frontend/SessionListPanel.ts` — Implementation Đầy Đủ

```typescript
import { eventBus } from './EventBus';
import type { SessionItem, SessionsApiResponse } from './types';

export class SessionListPanel {
  private overlay: HTMLElement | null = null;
  private currentFilename: string | null = null;

  open(currentSessionFilename?: string): void {
    this.currentFilename = currentSessionFilename ?? null;
    this.render();
    this.fetchAndPopulate();
    document.addEventListener('keydown', this.handleKeyDown);
  }

  close(): void {
    this.overlay?.remove();
    this.overlay = null;
    this.currentFilename = null;
    document.removeEventListener('keydown', this.handleKeyDown);
  }

  private render(): void {
    // Remove existing if any
    this.overlay?.remove();

    this.overlay = document.createElement('div');
    this.overlay.className = 'session-list-overlay';
    this.overlay.setAttribute('role', 'dialog');
    this.overlay.setAttribute('aria-label', 'Danh sách sessions');
    this.overlay.setAttribute('aria-modal', 'true');

    this.overlay.innerHTML = `
      <div class="session-list-panel">
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

    // Focus trap — focus vào panel
    (this.overlay.querySelector('.session-list-panel') as HTMLElement)?.focus();
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
    try {
      const response = await fetch('/api/sessions');
      const json: SessionsApiResponse = await response.json();

      if (!response.ok || json.error) {
        this.renderError(json.error?.message ?? 'Không thể tải danh sách sessions');
        return;
      }

      this.renderSessions(json.data ?? []);
    } catch (err) {
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

    const exportHistory = this.getExportHistory();

    body.innerHTML = sessions.map((session) => {
      const isCurrentSession = session.filename === this.currentFilename;
      const exportRecord = exportHistory[session.filename];
      const isExported = !!exportRecord;

      return `
        <div class="session-row${isCurrentSession ? ' session-row--current' : ''}"
             data-filename="${session.filename}">
          <div class="session-row-info">
            <span class="session-symbol">${session.symbol}</span>
            <span class="session-timeframe">${session.timeframe}</span>
            <span class="session-date">${session.date}</span>
            ${isCurrentSession ? '<span class="session-badge current">Session hiện tại</span>' : ''}
          </div>
          <div class="session-row-actions">
            ${isExported
              ? `<span class="session-exported-badge">Đã export ${exportRecord.date}</span>
                 <button class="btn-ghost session-reexport-btn"
                         data-filename="${session.filename}">Re-export</button>`
              : `<button class="btn-primary session-export-btn"
                         data-filename="${session.filename}">Export</button>`
            }
          </div>
        </div>
      `;
    }).join('');

    // Bind export button events
    body.querySelectorAll('.session-export-btn, .session-reexport-btn')
      .forEach((btn) => {
        btn.addEventListener('click', (e) => {
          const filename = (e.currentTarget as HTMLElement).dataset.filename!;
          this.onExportClick(filename, !!(btn as HTMLElement).classList.contains('session-reexport-btn'));
        });
      });
  }

  private onExportClick(filename: string, isReexport: boolean): void {
    if (isReexport) {
      const history = this.getExportHistory();
      const date = history[filename]?.date ?? '?';
      // Show toast warn — Story 2.x will implement ExportPreview
      console.warn(`[SessionListPanel] Re-export: ${filename} (previously exported ${date})`);
    }
    this.close();
    // Delegate to ExportPanel — Story 2.2 implements full ExportPreview
    // ExportPanel singleton will be wired in main.ts
    const event = new CustomEvent('sessionlist:exportSelected', {
      detail: { filename }
    });
    document.dispatchEvent(event);
  }

  private renderError(message: string): void {
    const body = this.overlay?.querySelector('#session-list-body');
    if (!body) return;
    body.innerHTML = `
      <div class="session-list-error">
        <span class="error-icon">⚠️</span>
        <p>${message}</p>
      </div>
    `;
  }

  private getExportHistory(): Record<string, { date: string }> {
    try {
      return JSON.parse(localStorage.getItem('export_history') ?? '{}');
    } catch {
      return {};
    }
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
```

### `frontend/types.ts` — Additions

Thêm vào `types.ts` đã tạo trong Story 1.2:

```typescript
// --- Phase 2: API response types ---

export interface SessionItem {
  filename: string;    // "BTCUSDT_4h_20260420.parquet"
  symbol: string;      // "BTCUSDT"
  timeframe: string;   // "4h"
  date: string;        // "2026-04-20"
  exported: boolean;   // hardcoded false from backend (Story 3.3 implements tracking)
}

export interface ApiError {
  message: string;
  code: string;
  retryable: boolean;
}

// Generic API response shape (matches backend APIResponse[T])
export interface ApiResponse<T> {
  data: T | null;
  error: ApiError | null;
}

export type SessionsApiResponse = ApiResponse<SessionItem[]>;
```

### `frontend/ResultsPanel.ts` — Diff (Chỉ thêm, không xóa)

Trong Phase 1 `ResultsPanel.ts`, phần render `CompletionOverlay`:

```typescript
// THÊM import ở đầu file
import { sessionListPanel } from './SessionListPanel';

// THÊM trong method renderCompletionOverlay() (hoặc tương đương)
// SAU button Reset, TRƯỚC khi close overlay:
function renderCompletionOverlay(currentFilename: string) {
  const supabaseEnabled = (window as any).__SUPABASE_ENABLED__ === true;

  const supabaseButton = supabaseEnabled
    ? `<button class="btn-primary completion-export-btn">
         📤 Lưu vào Supabase
       </button>`
    : '';

  // ... existing overlay HTML với supabaseButton thêm vào
  overlayEl.querySelector('.completion-export-btn')
    ?.addEventListener('click', () => {
      dismissCompletionOverlay();  // dismiss ngay lập tức
      sessionListPanel.open(currentFilename);
    });
}

// THÊM vào StatusBar Complete mode render:
function renderStatusBarComplete() {
  const supabaseEnabled = (window as any).__SUPABASE_ENABLED__ === true;
  const exportLink = supabaseEnabled
    ? `<span class="statusbar-export-link" role="button" tabindex="0">📤 Export</span>`
    : '';

  // ... existing status bar với exportLink thêm vào bên phải

  statusBarEl.querySelector('.statusbar-export-link')
    ?.addEventListener('click', () => sessionListPanel.open());
}
```

> **IMPORTANT:** Dev phải đọc existing `ResultsPanel.ts` code trước khi sửa. Chỉ ADD — không xóa bất kỳ Phase 1 logic nào.

### `frontend/export_panel.ts` — Stub

```typescript
/**
 * ExportPanel — Phase 2 component
 * Story 1.4: STUB ONLY — full implementation trong Stories 2.2, 2.3
 */
export class ExportPanel {
  openForSession(sessionFilename: string): void {
    // TODO (Story 2.2): Fetch /api/sessions/{filename}/preview
    // TODO (Story 2.2): Render ExportPreview full-screen overlay
    // TODO (Story 2.2): Implement IntersectionObserver scroll gate
    // TODO (Story 2.3): Implement per-trade reasoning_summary textareas
    console.log('[ExportPanel] openForSession:', sessionFilename);
  }
}

export const exportPanel = new ExportPanel();
```

### Backend: `index.html` Serving với Flag Injection

`static/index.html` chứa placeholder `{{ supabase_enabled }}` — được replace khi FastAPI serve:

```python
# backend/main.py (hoặc backend/routes/static.py)
from fastapi.responses import HTMLResponse
from pathlib import Path

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index() -> HTMLResponse:
    html_path = Path("static/index.html")
    html = html_path.read_text(encoding="utf-8")
    # Server-side injection — secure: không expose secrets, chỉ boolean
    html = html.replace(
        "{{ supabase_enabled }}",
        "true" if settings.supabase_enabled else "false"
    )
    return HTMLResponse(content=html)
```

```html
<!-- static/index.html — <head> section -->
<script>
  // Injected by server — DO NOT edit this line manually
  window.__SUPABASE_ENABLED__ = {{ supabase_enabled }};
</script>
```

### `export_history` localStorage Schema

`already-exported` state được track bởi `localStorage` (không phải backend) — decision từ UX spec UX-DR11:

```typescript
// Key: 'export_history'
// Value:
interface ExportHistory {
  [filename: string]: {
    date: string;  // "2026-04-24" — ngày export
  };
}

// Ghi khi export thành công (Story 3.x sẽ implement):
const history = JSON.parse(localStorage.getItem('export_history') ?? '{}');
history[filename] = { date: new Date().toISOString().slice(0, 10) };
localStorage.setItem('export_history', JSON.stringify(history));
```

> **Story 1.4 chỉ READ** từ `export_history`. Story 3.3 sẽ WRITE khi export thành công. Nếu localStorage trống → tất cả sessions hiện `exported: false` — đây là expected behavior.

### New Files Created in Story 1.4

| File | Action |
|------|--------|
| `frontend/SessionListPanel.ts` | **CREATE NEW** |
| `frontend/export_panel.ts` | **CREATE NEW** (stub) |

### Files Modified in Story 1.4

| File | Change |
|------|--------|
| `frontend/types.ts` | Thêm `SessionItem`, `ApiResponse<T>`, `SessionsApiResponse` |
| `frontend/ResultsPanel.ts` | Thêm Phase 2 entry points — CompletionOverlay button + StatusBar link |
| `static/index.html` | Thêm `<script>window.__SUPABASE_ENABLED__ = {{ supabase_enabled }};</script>` |
| `backend/main.py` | Thêm route `/` serve index.html với supabase_enabled injection |

> **DO NOT** modify `frontend/EventBus.ts` hay `frontend/ReplayEngine.ts` — chỉ đọc.

### Backward-Compatibility Checklist

- [ ] `SUPABASE_ENABLED=false` → button không hiển thị (AC #2)
- [ ] Phase 1 CompletionOverlay buttons (Reset, etc.) vẫn hoạt động
- [ ] Phase 1 StatusBar hiển thị bình thường khi `SUPABASE_ENABLED=false`
- [ ] `EventBus` không emit bất kỳ event mới nào trong story này
- [ ] `ReplayEngine`, `ChartController`, `DrawingManager` không bị sửa

### Accessibility Requirements (UX-DR12)

Tất cả Phase 2 modals phải tuân:
- `role="dialog"` hoặc `role="alertdialog"`
- `aria-modal="true"`
- Focus trap — Tab key không thoát ra ngoài modal
- `Escape` dismiss

Focus trap implementation (minimal):
```typescript
private trapFocus(container: HTMLElement): void {
  const focusable = container.querySelectorAll<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  container.addEventListener('keydown', (e) => {
    if (e.key !== 'Tab') return;
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

  first?.focus();
}
```

### Custom Event Bridge (Story 1.4 → Story 2.x)

Story 1.4 uses `document.dispatchEvent(new CustomEvent('sessionlist:exportSelected', { detail: { filename } }))` để delegate export action. Story 2.2 sẽ listen event này trong `ExportPanel`:

```typescript
// Story 2.2 sẽ implement:
document.addEventListener('sessionlist:exportSelected', (e: Event) => {
  const { filename } = (e as CustomEvent<{ filename: string }>).detail;
  exportPanel.openForSession(filename);
});
```

> **Lý do dùng CustomEvent thay vì EventBus:** Export là imperative action (không phải reactive state change). PRD Technical Architecture: "Direct fetch call đến backend — không qua EventBus (export là imperative action)."

### NFR: UI Feedback < 100ms (NFR3)

SessionListPanel `open()` phải:
1. Render overlay và skeleton ngay lập tức (< 1ms)
2. Fetch `/api/sessions` async (không block render)
3. Update skeleton → real data khi fetch complete

Pattern này đảm bảo NFR3: user thấy response < 100ms.

### References

- [epics.md - Story 1.4 Acceptance Criteria](_bmad-output/planning-artifacts/epics.md#story-14-sessionlistpanel--ui-browse-và-chọn-session)
- [ux-design-specification.md - SessionListPanel Anatomy & Behaviors](_bmad-output/planning-artifacts/ux-design-specification.md#1-sessionlistpanel)
- [ux-design-specification.md - Phase 2 Integration Points](_bmad-output/planning-artifacts/ux-design-specification.md#integration-points-với-phase-1-ui)
- [ux-design-specification.md - Accessibility UX-DR12](_bmad-output/planning-artifacts/ux-design-specification.md#accessibility)
- [architecture.md - Frontend Architecture (ADR-12, ADR-14)](_bmad-output/planning-artifacts/architecture.md#frontend-architecture)
- [prd-phase2-supabase.md - FR1, FR2, FR3, FR4, FR5, FR27, FR28, FR33](_bmad-output/planning-artifacts/prd-phase2-supabase.md)
- [prd-phase2-supabase.md - UX-DR1, UX-DR2, UX-DR3, UX-DR4, UX-DR11](_bmad-output/planning-artifacts/prd-phase2-supabase.md)
- [1-2-eventbus-replaystatechanged-va-tradecompleted-events.md - EventBus singleton pattern](_bmad-output/implementation-artifacts/1-2-eventbus-replaystatechanged-va-tradecompleted-events.md)
- [1-3-get-api-sessions-danh-sach-parquet-sessions.md - SessionItem model + API contract](_bmad-output/implementation-artifacts/1-3-get-api-sessions-danh-sach-parquet-sessions.md)
- NFR3: UI feedback < 100ms

### Review Findings

- [x] [Review][Patch] `trapFocus` crash khi không có focusable elements — fixed: `if (!first || !last) return` [`frontend/SessionListPanel.ts:trapFocus()`]
- [x] [Review][Patch] XSS: session fields và error message không escape — fixed: `escapeHtml()` helper [`frontend/SessionListPanel.ts:renderSessions()/renderError()`]
- [x] [Review][Patch] `handleKeyDown` accumulate — fixed: `removeEventListener` trước `addEventListener` trong `open()` [`frontend/SessionListPanel.ts:open()`]
- [x] [Review][Patch] `fetchAndPopulate` stale write-back — fixed: AbortController cancel khi `close()`/`render()` [`frontend/SessionListPanel.ts`]
- [x] [Review][Patch] `trades` public field — fixed: `private _trades` + readonly getter [`frontend/export_panel.ts`]
- [x] [Review][Patch] `_callPreviewApi` không check `response.ok` — fixed: check trước `.json()` [`frontend/export_panel.ts`]
- [x] [Review][Dismiss] `_onReplayStateChanged` `state` — false positive, `const { state } = payload` đã có ở line 108
- [x] [Review][Defer] `_onReplayStateChanged` xóa `trades` khi 'stopped' mid-export race [`frontend/export_panel.ts`] — deferred, pre-existing — cần design decision về UX

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Completion Notes List

- `frontend/ResultsPanel.ts` không tồn tại trong codebase (greenfield) — tạo mới với Phase 1 stub + Phase 2 entry points baked in theo story spec.
- `frontend/export_panel.ts` dùng snake_case đúng theo story spec (khác với PascalCase các file khác).
- CSS được thêm vào `static/index.html` dạng `<style>` block (không tạo file CSS riêng).
- `SessionListPanel.ts` dùng `void eventBus` để tránh unused import lint error — EventBus sẽ được wire trong Story 2.x.
- tsc --noEmit: exit 0 (no errors)
- pytest: 15/15 pass (no regression)

### File List

- `frontend/SessionListPanel.ts` — CREATED
- `frontend/ResultsPanel.ts` — CREATED  
- `frontend/export_panel.ts` — CREATED
- `frontend/types.ts` — MODIFIED (added SessionItem, ApiError, ApiResponse<T>, SessionsApiResponse)
- `static/index.html` — MODIFIED (added SUPABASE_ENABLED script tag + SessionListPanel CSS)
- `backend/main.py` — MODIFIED (added GET / route with supabase_enabled injection)
