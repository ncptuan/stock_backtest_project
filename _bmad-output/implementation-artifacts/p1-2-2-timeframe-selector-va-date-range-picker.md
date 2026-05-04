# Story P1-2.2: Timeframe Selector + Date Range Picker

Status: done

## Story

As a trader,
I want to select timeframe and date range from the toolbar,
So that I can analyze different periods and granularities without re-fetching data.

## Acceptance Criteria

1. **Given** app đã load và chart đang hiển thị
   **When** trader chọn timeframe mới từ `<select id="toolbar-timeframe">` (5m / 30m / 1h / 4h / 1D)
   **Then** `ChartController.loadData()` được gọi với timeframe mới và date range hiện tại
   **And** chart reload với data của timeframe mới từ API
   **And** LRU-1 cache được evict trước khi fetch (timeframe khác = cache miss)

2. **Given** trader chọn timeframe mới nhưng cache không có data cho timeframe đó
   **When** API trả về 404 với `code: "no_cache"`
   **Then** chart hiển thị empty state với message "Chưa có data cho [timeframe] — fetch trước"
   **And** `chartController.hasData()` trả về `false`
   **And** nút Play (nếu đã tồn tại) bị disabled

3. **Given** trader có drawings (Entry/TP/SL đã vẽ) và đang switch timeframe
   **When** trader thay đổi `<select>` timeframe
   **Then** hiển thị toast warning: "Chuyển timeframe sẽ xóa tất cả drawings"
   **And** toast có nút "Hoàn tác" với countdown 5 giây
   **And** nếu trader nhấn Hoàn tác trong 5 giây: timeframe selector quay về giá trị cũ, drawings giữ nguyên
   **And** nếu không undo: sau 5 giây tự động proceed — `DrawingManager.clear()` (khi DrawingManager tồn tại), chart reload với timeframe mới
   **And** nếu DrawingManager chưa tồn tại (Story 3.x chưa dev): skip check, reload trực tiếp

4. **Given** trader thay đổi date_start hoặc date_end trong toolbar inputs
   **When** trader nhấn nút Load hoặc nhấn Enter
   **Then** `ChartController.loadData()` được gọi với date range mới
   **And** chart slice về đúng date range đó

5. **Given** date range vượt quá data có sẵn trong cache (clip scenario)
   **When** API trả về `{ clipped: true, actual_date_start: "...", actual_date_end: "..." }`
   **Then** hiển thị toast info: "Date range đã được clip về [actual_date_start] — [actual_date_end]"
   **And** chart vẫn render với data đã clip (không phải error)
   **And** toast tự đóng sau 5 giây (không cần dismiss action)

6. **Given** settings được thay đổi (timeframe hoặc date range)
   **When** load thành công
   **Then** `SettingsManager.save({ timeframe, dateStart, dateEnd })` được gọi để persist vào localStorage
   **And** key localStorage: `btcReplay_lastSettings`

7. **Given** app load lại lần tiếp theo (page refresh)
   **When** `SettingsManager.load()` được gọi trong `main.ts` init
   **Then** toolbar timeframe selector được set về giá trị đã lưu
   **And** toolbar date inputs được set về dateStart/dateEnd đã lưu
   **And** `ChartController.loadData()` được gọi tự động với restored settings
   **And** nếu localStorage corrupt hoặc empty: fallback gracefully về defaults (timeframe=4h, range=6 tháng gần nhất)

8. **Given** date_start > date_end trong toolbar
   **When** trader nhấn Load
   **Then** hiển thị toast error: "Date start phải trước date end"
   **And** không gọi API, không reload chart

## Tasks / Subtasks

- [x] Task 1: Tạo `frontend/SettingsManager.ts` — Typed LocalStorage wrapper (AC: #6, #7)
  - [x] Class `SettingsManager` với `load(): PersistedSettings` và `save(settings: PersistedSettings): void`
  - [x] `PersistedSettings` interface: `{ timeframe: string; dateStart: string; dateEnd: string }`
  - [x] `STORAGE_KEY = 'btcReplay_lastSettings'`
  - [x] `load()`: `try { JSON.parse(localStorage.getItem(key)) } catch { return defaults }` — fail-safe
  - [x] `save()`: `localStorage.setItem(key, JSON.stringify(settings))` — try/catch, log warning on fail
  - [x] `getDefaults()`: returns `{ timeframe: '4h', dateStart: <6 months ago>, dateEnd: <today> }`

- [x] Task 2: Tạo `frontend/ToastManager.ts` — Toast notification singleton (AC: #3, #5, #8)
  - [x] Class `ToastManager` (singleton) với `show(message: string, type: 'info' | 'warning' | 'error', opts?): void`
  - [x] Optional `opts.undoDuration: number` (ms) + `opts.onUndo: () => void` — cho timed undo
  - [x] Toast tự dismiss sau `opts.duration ?? 4000` ms nếu không có undo
  - [x] Undo toast: hiển thị countdown visible (5s, 4s, ...) + nút "Hoàn tác"
  - [x] Mount vào `#toast-root` container (đã có trong index.html từ Story 2.1)
  - [x] Tối đa 3 toasts chồng nhau — oldest dismissed khi vượt quá

- [x] Task 3: Cập nhật `frontend/main.ts` — Wire toolbar events (AC: #1–#8)
  - [x] `SettingsManager.load()` → populate toolbar inputs + init ChartController.loadData với restored settings
  - [x] Timeframe `change` event handler:
    - [x] Check `drawingManager?.hasDrawings()` (guard: DrawingManager chưa tồn tại trong story này → skip)
    - [x] Nếu có drawings: show undo toast → nếu không undo sau 5s, proceed với reload
    - [x] Nếu không drawings: reload ngay
    - [x] Save settings sau reload thành công
  - [x] Date input `change` event + Load button `click` → validate date range → `loadData()` → save settings
  - [x] Sau `chart:dataLoaded`: update `status-data-info` span với "Loaded [N] bars"
  - [x] Guard pattern cho DrawingManager: module-level `let drawingManager` + `setDrawingManager()` export

- [x] Task 4: Cập nhật `frontend/ChartController.ts` — Handle clip response + propagate to caller (AC: #5)
  - [x] `loadData()` đọc `body.clipped`, `body.actual_date_start`, `body.actual_date_end` từ response
  - [x] Return value để `main.ts` có thể show clip toast
  - [x] `loadData()` returns `Promise<LoadDataResult | null>` — main.ts xử lý toast
  - [x] **Option A** (separation of concerns — ChartController không biết về ToastManager)

- [x] Task 5: Cập nhật `frontend/types.ts` — Thêm types mới (AC: #6)
  - [x] Add `PersistedSettings` interface: `{ timeframe: string; dateStart: string; dateEnd: string }`
  - [x] Add `LoadDataResult` interface: `{ barCount, clipped, actualDateStart, actualDateEnd }`
  - [x] `OHLCVApiResponse` đã có `clipped` fields từ Story 2.1

## Dev Notes

### SettingsManager implementation

```typescript
// frontend/SettingsManager.ts
import type { PersistedSettings } from './types';

const STORAGE_KEY = 'btcReplay_lastSettings';

function getDefaultDateRange(): { dateStart: string; dateEnd: string } {
  const end = new Date();
  const start = new Date();
  start.setMonth(start.getMonth() - 6);
  const fmt = (d: Date): string => d.toISOString().slice(0, 10);
  return { dateStart: fmt(start), dateEnd: fmt(end) };
}

export class SettingsManager {
  load(): PersistedSettings {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return this.getDefaults();
      const parsed = JSON.parse(raw) as Partial<PersistedSettings>;
      // Validate shape — nếu thiếu bất kỳ field nào → fallback defaults
      if (!parsed.timeframe || !parsed.dateStart || !parsed.dateEnd) {
        return this.getDefaults();
      }
      return {
        timeframe: parsed.timeframe,
        dateStart: parsed.dateStart,
        dateEnd: parsed.dateEnd,
      };
    } catch {
      // JSON.parse failed hoặc localStorage không available
      return this.getDefaults();
    }
  }

  save(settings: PersistedSettings): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch (e: unknown) {
      // localStorage full hoặc private browsing mode
      const msg = e instanceof Error ? e.message : String(e);
      console.warn(`[SettingsManager] save failed: ${msg}`);
    }
  }

  getDefaults(): PersistedSettings {
    const { dateStart, dateEnd } = getDefaultDateRange();
    return { timeframe: '4h', dateStart, dateEnd };
  }
}

// Singleton export
export const settingsManager = new SettingsManager();
```

### ToastManager implementation

```typescript
// frontend/ToastManager.ts
export type ToastType = 'info' | 'warning' | 'error';

export interface ToastOptions {
  duration?: number;           // ms — default 4000; ignored if undoDuration set
  undoDuration?: number;       // ms — enables undo button + countdown
  onUndo?: () => void;         // called if user clicks Hoàn tác
}

class ToastManagerImpl {
  private container: HTMLElement | null = null;
  private count = 0;

  private getContainer(): HTMLElement {
    if (!this.container) {
      this.container = document.getElementById('toast-root');
      if (!this.container) {
        // Fallback: create container if not found (shouldn't happen after Story 2.1)
        this.container = document.createElement('div');
        this.container.id = 'toast-root';
        document.body.appendChild(this.container);
      }
    }
    return this.container;
  }

  show(message: string, type: ToastType = 'info', opts: ToastOptions = {}): void {
    const container = this.getContainer();

    // Max 3 toasts — remove oldest
    if (this.count >= 3) {
      const oldest = container.querySelector('.toast');
      if (oldest) oldest.remove();
      this.count--;
    }

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    this.count++;

    const dismiss = (): void => {
      toast.classList.add('toast--hiding');
      setTimeout(() => {
        if (toast.parentNode) {
          toast.remove();
          this.count = Math.max(0, this.count - 1);
        }
      }, 200);
    };

    if (opts.undoDuration && opts.onUndo) {
      // Undo toast with countdown
      let remaining = Math.ceil(opts.undoDuration / 1000);
      let undoTriggered = false;

      const countdownSpan = document.createElement('span');
      countdownSpan.className = 'toast-countdown';
      countdownSpan.textContent = `(${remaining}s)`;

      const undoBtn = document.createElement('button');
      undoBtn.className = 'toast-undo-btn';
      undoBtn.textContent = 'Hoàn tác';
      undoBtn.addEventListener('click', () => {
        undoTriggered = true;
        opts.onUndo!();
        clearInterval(timer);
        dismiss();
      });

      toast.innerHTML = `<span class="toast-msg">${message}</span>`;
      toast.appendChild(countdownSpan);
      toast.appendChild(undoBtn);

      const timer = setInterval(() => {
        remaining--;
        countdownSpan.textContent = `(${remaining}s)`;
        if (remaining <= 0) {
          clearInterval(timer);
          if (!undoTriggered) dismiss();
        }
      }, 1000);

      setTimeout(() => {
        if (!undoTriggered) dismiss();
      }, opts.undoDuration);
    } else {
      // Simple toast
      toast.innerHTML = `<span class="toast-msg">${message}</span>`;
      const duration = opts.duration ?? 4000;
      setTimeout(dismiss, duration);
    }

    container.appendChild(toast);
  }
}

export const toastManager = new ToastManagerImpl();
```

### Toast CSS — thêm vào `static/style.css`

```css
/* Trong @layer components */

/* Toast container */
#toast-root {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9000;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
  max-width: 360px;
}

.toast {
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 0.875rem;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--sem-text-primary);
  background: var(--sem-bg-surface);
  border: 1px solid var(--sem-border);
  pointer-events: all;
  animation: toast-in var(--sem-anim-normal) ease;
}

.toast--info    { border-left: 3px solid var(--sem-tp); }
.toast--warning { border-left: 3px solid var(--sem-warning); }
.toast--error   { border-left: 3px solid var(--sem-candle-bear); }

.toast--hiding {
  opacity: 0;
  transform: translateX(8px);
  transition: opacity 0.2s, transform 0.2s;
}

.toast-countdown {
  color: var(--sem-text-muted);
  font-size: 0.8rem;
  min-width: 28px;
}

.toast-undo-btn {
  background: none;
  border: 1px solid var(--sem-border);
  color: var(--sem-text-primary);
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  flex-shrink: 0;
}

.toast-undo-btn:hover { background: var(--sem-bg-app); }

@keyframes toast-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

### Cập nhật ChartController.loadData() return type

Story 2.1 tạo `ChartController` với `loadData()` trả về `Promise<void>`. Story này cần clip info được propagate lên `main.ts`. Cập nhật return type:

```typescript
// Trong ChartController.ts — thay đổi loadData signature
interface LoadDataResult {
  barCount: number;
  clipped: boolean;
  actualDateStart: string | null;
  actualDateEnd: string | null;
}

async loadData(
  symbol: string,
  timeframe: string,
  dateRange: DateRange
): Promise<LoadDataResult | null> {
  // ... existing code ...
  
  // Khi success:
  return {
    barCount: bars.length,
    clipped: body.clipped ?? false,
    actualDateStart: body.actual_date_start ?? null,
    actualDateEnd: body.actual_date_end ?? null,
  };
  
  // Khi error (return null để caller biết là failed):
  return null;
}
```

### main.ts — updated wiring

```typescript
// frontend/main.ts (cập nhật từ Story 2.1)
import { ChartController } from './ChartController';
import { settingsManager } from './SettingsManager';
import { toastManager } from './ToastManager';
import type { PersistedSettings } from './types';

const SYMBOL = 'BTC/USDT';

let chartController: ChartController;
let currentSettings: PersistedSettings;

// Guard: DrawingManager sẽ được set từ Story 3.x
// Dùng module-level let thay vì window hack
let drawingManager: { hasDrawings(): boolean; clear(): void } | null = null;
export function setDrawingManager(dm: typeof drawingManager): void {
  drawingManager = dm;
}

async function doLoad(settings: PersistedSettings): Promise<void> {
  const result = await chartController.loadData(SYMBOL, settings.timeframe, {
    dateStart: settings.dateStart,
    dateEnd: settings.dateEnd,
  });

  if (result === null) {
    // Error đã được logged trong ChartController
    return;
  }

  // Show clip toast nếu cần
  if (result.clipped) {
    const parts = [
      result.actualDateStart ?? '?',
      result.actualDateEnd ?? '?',
    ];
    toastManager.show(
      `Date range đã được clip về ${parts[0]} — ${parts[1]}`,
      'info',
      { duration: 5000 }
    );
  }

  // Persist settings
  settingsManager.save(settings);
  currentSettings = settings;

  // Update status bar
  const statusInfo = document.getElementById('status-data-info');
  if (statusInfo) {
    statusInfo.textContent = `${result.barCount.toLocaleString()} bars`;
  }
}

function handleTimeframeChange(newTimeframe: string): void {
  const prevTimeframe = currentSettings.timeframe;
  if (newTimeframe === prevTimeframe) return;

  const hasDrawings = drawingManager?.hasDrawings() ?? false;

  if (hasDrawings) {
    // Show undo toast
    const tfSelect = document.getElementById('toolbar-timeframe') as HTMLSelectElement | null;
    // Revert select immediately — proceed only if no undo
    if (tfSelect) tfSelect.value = prevTimeframe;  // visual revert

    toastManager.show(
      'Chuyển timeframe sẽ xóa tất cả drawings',
      'warning',
      {
        undoDuration: 5000,
        onUndo: () => {
          // Undo: already reverted visually above, no action needed
        },
      }
    );

    // Proceed after 5s if no undo
    setTimeout(() => {
      // Re-check: if user didn't undo, tfSelect still shows prevTimeframe
      // We need to apply the new timeframe now
      if (tfSelect) tfSelect.value = newTimeframe;
      drawingManager?.clear();
      const newSettings = { ...currentSettings, timeframe: newTimeframe };
      doLoad(newSettings);
    }, 5000);
  } else {
    const newSettings = { ...currentSettings, timeframe: newTimeframe };
    doLoad(newSettings);
  }
}

function init(): void {
  const container = document.getElementById('chart-container');
  if (!container) {
    console.error('[main] #chart-container not found');
    return;
  }

  chartController = new ChartController();
  chartController.init(container);

  // Load settings
  const settings = settingsManager.load();
  currentSettings = settings;

  // Populate toolbar
  const tfSelect = document.getElementById('toolbar-timeframe') as HTMLSelectElement | null;
  const startInput = document.getElementById('toolbar-date-start') as HTMLInputElement | null;
  const endInput = document.getElementById('toolbar-date-end') as HTMLInputElement | null;

  if (tfSelect) tfSelect.value = settings.timeframe;
  if (startInput) startInput.value = settings.dateStart;
  if (endInput) endInput.value = settings.dateEnd;

  // Auto-load with restored settings
  doLoad(settings);

  // Timeframe change handler
  tfSelect?.addEventListener('change', (e) => {
    const newTf = (e.target as HTMLSelectElement).value;
    handleTimeframeChange(newTf);
  });

  // Load button + date validation
  const btnLoad = document.getElementById('btn-load');
  btnLoad?.addEventListener('click', () => {
    const tf = tfSelect?.value ?? currentSettings.timeframe;
    const ds = startInput?.value ?? currentSettings.dateStart;
    const de = endInput?.value ?? currentSettings.dateEnd;

    // AC #8: date validation
    if (ds > de) {
      toastManager.show('Date start phải trước date end', 'error');
      return;
    }

    const newSettings: PersistedSettings = { timeframe: tf, dateStart: ds, dateEnd: de };
    doLoad(newSettings);
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
```

### Timeframe switch undo pattern — quan trọng

Vấn đề phức tạp nhất trong story này là **timeframe switch với undo**. Pattern được dùng:

1. User thay đổi `<select>` → `change` event fire
2. Nếu có drawings: **revert select về giá trị cũ ngay lập tức** (visual revert)
3. Hiện toast warning với `undoDuration: 5000`
4. Sau 5 giây (nếu không undo): **restore select về new value**, clear drawings, reload
5. Nếu user click Hoàn tác: không cần làm gì vì select đã reverted về giá trị cũ

**Tại sao revert ngay:** Nếu để select ở giá trị mới trong khi undo đang chờ, user thấy timeframe đã đổi nhưng chart chưa reload — confusing. Reverted → consistent UI state trong suốt undo window.

**Nhược điểm:** Nếu user click Hoàn tác, select đang ở prevTimeframe → correct.  
Nếu user không undo và 5s hết: phải set select về newTimeframe thủ công trước khi reload.

### types.ts — Additions

```typescript
// Thêm vào frontend/types.ts

export interface PersistedSettings {
  timeframe: string;  // e.g., "4h"
  dateStart: string;  // "YYYY-MM-DD"
  dateEnd: string;    // "YYYY-MM-DD"
}

// LoadDataResult — returned by ChartController.loadData()
export interface LoadDataResult {
  barCount: number;
  clipped: boolean;
  actualDateStart: string | null;
  actualDateEnd: string | null;
}
```

### Files cần modify

| File | Thay đổi |
|------|---------|
| `frontend/types.ts` | Thêm `PersistedSettings`, `LoadDataResult` |
| `frontend/main.ts` | Wire toolbar events, SettingsManager, ToastManager, doLoad() |
| `frontend/ChartController.ts` | `loadData()` → `Promise<LoadDataResult \| null>` (trả về clip info) |
| `static/style.css` | Thêm toast CSS vào `@layer components` |

### Files cần tạo mới

| File | Nội dung |
|------|---------|
| `frontend/SettingsManager.ts` | Typed LocalStorage wrapper, load/save, defaults |
| `frontend/ToastManager.ts` | Toast UI singleton, undo countdown support |

### Files KHÔNG được touch

- `backend/` — story này chỉ là frontend
- `frontend/EventBus.ts` — không thay đổi
- `frontend/ReplayEngine.ts` — Epic P1-4 scope
- Phase 2 components (SessionListPanel, ExportPreview, etc.)

### Dependency order trong story

1. **SettingsManager.ts** — không phụ thuộc gì mới
2. **ToastManager.ts** — không phụ thuộc gì mới
3. **types.ts** — thêm PersistedSettings, LoadDataResult
4. **ChartController.ts** — update return type của loadData
5. **main.ts** — import và wire tất cả lại

### Edge case quan trọng

**DrawingManager guard:** Story 3.x chưa dev khi story này được implement. `drawingManager` sẽ là `null`. Code phải defensive:
```typescript
const hasDrawings = drawingManager?.hasDrawings() ?? false;
```
→ Luôn `false` cho đến khi DrawingManager được inject. Không crash.

**localStorage unavailable:** Một số browsers (private mode, Safari strict) có thể throw khi access localStorage. `SettingsManager.load()` và `.save()` phải đều có try/catch.

**Timeframe switch timer leak:** Nếu user switch timeframe 3 lần nhanh liên tiếp (mỗi lần có drawings), sẽ có 3 setTimeout chồng lên nhau. Trong MVP, chấp nhận behavior này — đây là corner case hiếm. Phase 2 có thể cancel timer cũ.

**Date input browser compatibility:** `<input type="date">` supported tốt trên Chrome/Safari 2026. Không cần polyfill.

### References

- FR8: Timeframe selector — `epics-phase1.md` line 148
- FR9: Date range selector — `epics-phase1.md` line 149
- FR19c: Switch timeframe xóa drawings — `epics-phase1.md` line 44
- UX-DR3: Toast + 5s undo khi switch timeframe — `epics-phase1.md` line 118
- UX-DR8: Last-used settings persistence — `epics-phase1.md` line 121
- ADR-20: LocalStorage key `btcReplay_lastSettings` — `architecture.md` line 507
- Previous story P1-2.1: `_bmad-output/implementation-artifacts/p1-2-1-candlestick-chart-render-voi-lightweight-charts.md`

## Dev Agent Record

### Agent Model Used

mimo-v2.5-pro

### Debug Log References

- Build: `npm run build` — 281.4kb output, 30ms, no errors
- Typecheck: `npm run typecheck` — no errors

### Completion Notes List

- All 5 tasks completed
- SettingsManager: typed localStorage wrapper with fail-safe load/save, defaults to 4h timeframe + 6-month range
- ToastManager: singleton with max 3 toasts, undo countdown support, mounts to #toast-root
- ChartController.loadData() now returns `LoadDataResult | null` instead of `void` — propagates clip info
- main.ts: full toolbar wiring — timeframe change with undo toast (when DrawingManager exists), date validation, settings persistence
- DrawingManager guard: module-level `let` with `setDrawingManager()` export — null until Epic P1-3 injects it
- Toast CSS added to `@layer components` in style.css

### File List

- `frontend/SettingsManager.ts` — created (typed localStorage wrapper)
- `frontend/ToastManager.ts` — created (toast notification singleton with undo support)
- `frontend/types.ts` — modified (added PersistedSettings, LoadDataResult interfaces)
- `frontend/ChartController.ts` — modified (loadData returns LoadDataResult | null, reads clip fields)
- `frontend/main.ts` — rewritten (toolbar wiring, SettingsManager, ToastManager, doLoad, handleTimeframeChange)
- `static/style.css` — modified (toast CSS added to @layer components)

## Review Findings (2026-05-03)

### Patch (applied)
- [x] [Review][Patch] Undo timeout never cancelled — undo is cosmetic only [main.ts:77-93] — fixed: store timeout ID, cancel on undo + new change
- [x] [Review][Patch] Rapid timeframe switches stack multiple timeouts [main.ts:88-93] — fixed: cancel previous timeout on new change
- [x] [Review][Patch] Empty state message missing timeframe string [ChartController.ts:114,121,144] — fixed: interpolate timeframe
- [x] [Review][Patch] Missing Enter key handler on date inputs [main.ts:179-192] — fixed: keydown listener on startInput/endInput
- [x] [Review][Patch] Toast double-dismiss decrements count twice [ToastManager.ts:39-47] — fixed: dismissed flag makes dismiss() idempotent
- [x] [Review][Patch] Toast count desync with DOM reality [ToastManager.ts:29-32] — deferred, Math.max guard sufficient for MVP
- [x] [Review][Patch] No date format validation [main.ts:185] — fixed: Date.parse + empty string checks

### Defer
- [x] [Review][Defer] IndicatorToggleState dead code [types.ts:80-83] — cosmetic, not a bug
- [x] [Review][Defer] Month boundary overflow in getDefaultDateRange [SettingsManager.ts:7-8] — 1-day edge case
- [x] [Review][Defer] No destroy/cleanup in main.ts (HMR leak) [main.ts] — development concern only
- [x] [Review][Defer] PersistedSettings.timeframe accepts arbitrary strings [SettingsManager.ts:19-26] — server validates
- [x] [Review][Defer] Settings save no user feedback on failure [SettingsManager.ts:32-38] — acceptable UX
- [x] [Review][Defer] load() swallows parse failures silently [SettingsManager.ts:28] — minor debuggability
- [x] [Review][Defer] No input sanitization on date inputs [main.ts:185] — browser constrains format
- [x] [Review][Defer] sessionListPanel/ExportPanel opaque side effects [main.ts:10-11] — Phase 2 scope
- [x] [Review][Defer] Date string comparison fragility [main.ts:185] — safe with input type="date"
- [x] [Review][Defer] IndicatorOverlay.init() silently no-ops [IndicatorOverlay.ts:27-28] — latent bug, not current
