# Story P1-2.3: OHLCV Hover Tooltip

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (3)

1. **MEMORY LEAK: `destroy()` didn't unsubscribe crosshairMove handler** — HIGH (all 3 agents)
   - `ChartController.unsubscribeHover()` added (wraps `chart.unsubscribeCrosshairMove()`)
   - `HoverTooltip.destroy()` now calls `this.controller.unsubscribeHover(this.boundHandler)` before removing DOM element
   - Files: `ChartController.ts`, `HoverTooltip.ts`

2. **Duplicate `formatPrice`/`formatVolume` functions** — MED (all 3 agents)
   - Replaced with single `formatNumber()` function (identical bodies: `toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})`)
   - File: `HoverTooltip.ts`

### Deferred

- `innerHTML` on every crosshair move — `formatPrice` returns numeric strings via `toLocaleString`, safe today, defer perf optimization
- `getBarByTime` O(n) linear scan on every hover — defer to perf optimization sprint (Map index)
- `param.time as number` BusinessDay type guard — chart uses UTCTimestamp (numeric), BusinessDay impossible with candlestick data
- `offsetWidth` fallback (160px) one-frame position jump on first show after hide — cosmetic, defer
- `formatTimestampUTC7` NaN handling for invalid timestamps — upstream data validated by backend, defer
- Small container positioning overflow — `min-width: 1024px` in CSS prevents containers < 160px, defer

## Story

As a trader,
I want to see OHLCV details when hovering over a candle,
So that I can audit exact price values and timestamps (critical for detecting look-ahead bias).

## Acceptance Criteria

1. **Given** chart đã render với data (candlestick bars đang hiển thị)
   **When** trader di chuột lên một nến
   **Then** tooltip xuất hiện ngay lập tức (không có delay) hiển thị đầy đủ 6 fields:
   - Timestamp dạng "DD/MM/YYYY HH:mm UTC+7"
   - Open, High, Low, Close (mỗi field 2 chữ số thập phân)
   - Volume (format: 2 chữ số thập phân, separator phần nghìn)

2. **Given** tooltip đang hiển thị
   **When** trader di chuột sang nến khác
   **Then** tooltip update ngay lập tức với data của nến mới (không flicker, không hide/show)

3. **Given** chuột đang ở bên phải chart (x > 50% width)
   **When** tooltip hiển thị
   **Then** tooltip xuất hiện bên TRÁI cursor để không che khuất nến

4. **Given** chuột đang ở bên trái chart (x ≤ 50% width)
   **When** tooltip hiển thị
   **Then** tooltip xuất hiện bên PHẢI cursor

5. **Given** chuột di chuyển ra ngoài chart area
   **When** crosshairMove event không có `param.time`
   **Then** tooltip ẩn đi (display: none)

6. **Given** chart chưa có data (empty state)
   **When** chuột di chuyển trên chart area
   **Then** tooltip không hiển thị (không có bar để show)

7. **Given** chart đang hiển thị
   **When** app load lần đầu (trước khi có data)
   **Then** tooltip element tồn tại trong DOM nhưng ẩn (display: none)

## Tasks / Subtasks

- [x] Task 1: Tạo `frontend/HoverTooltip.ts` — DOM tooltip class (AC: #1–#6)
  - [x] Class `HoverTooltip` nhận `(container: HTMLElement, chartController: ChartController)`
  - [x] `init()`: tạo tooltip DOM element + append vào container + subscribe `chart.subscribeCrosshairMove()`
  - [x] Crosshair move handler: get bar data, format, position, show/hide
  - [x] `destroy()`: remove DOM element

- [x] Task 2: Cập nhật `frontend/ChartController.ts` — Expose crosshair subscription + data lookup (AC: #1)
  - [x] Add `subscribeHover(cb: (param: MouseEventParams) => void): void` method
  - [x] Add `getBarByTime(timeSeconds: number): OHLCVBar | undefined` method
  - [x] Add `getContainer(): HTMLElement | undefined` method
  - [x] Store `private container: HTMLElement` trong `init()`
  - [x] **Import `MouseEventParams` từ `lightweight-charts`**

- [x] Task 3: Cập nhật `frontend/main.ts` — Khởi tạo HoverTooltip sau chart init (AC: #7)
  - [x] Import `HoverTooltip`
  - [x] Sau `chartController.init(container)`: `hoverTooltip = new HoverTooltip(container, chartController); hoverTooltip.init()`
  - [x] Order: HoverTooltip.init() gọi SAU ChartController.init()

- [x] Task 4: Cập nhật `static/style.css` — Tooltip styles trong `@layer components` (AC: #1–#5)
  - [x] `#ohlcv-tooltip` positioning + appearance
  - [x] Labels (O/H/L/C/Vol) vs values typography tokens
  - [x] Tooltip hide/show via display:none/block

- [x] Task 5: index.html KHÔNG cần thay đổi — HoverTooltip.init() tự tạo DOM element

## Dev Notes

### LW Charts v5 — CrosshairMove API

```typescript
// Import cần thêm vào ChartController.ts
import {
  createChart,
  CandlestickSeries,
  IChartApi,
  ISeriesApi,
  UTCTimestamp,
  MouseEventParams,   // ← THÊM MỚI
} from 'lightweight-charts';

// MouseEventParams shape (LW Charts v5):
interface MouseEventParams {
  time?: Time;                          // UTCTimestamp (seconds) | undefined
  logical?: Logical;
  point?: { x: number; y: number };    // pixel coords trong chart canvas
  seriesData: Map<ISeriesApiBase, SeriesDataItem>;
  hoveredSeries?: ISeriesApiBase;
  sourceEvent?: TouchMouseEventData;
}

// Usage trong ChartController:
subscribeHover(cb: (param: MouseEventParams) => void): void {
  this.chart?.subscribeCrosshairMove(cb);
}

getBarByTime(timeSeconds: number): OHLCVBar | undefined {
  if (!this.cache) return undefined;
  return this.cache.data.find(b => b.timestamp / 1000 === timeSeconds);
}

getContainer(): HTMLElement | undefined {
  return this.container;
}
```

**Lưu ý LW Charts v5:** `param.seriesData` là `Map<ISeriesApiBase, SeriesDataItem>`. Để lấy candlestick data từ đây:
```typescript
const candle = param.seriesData.get(this.series);
// candle = { time: UTCTimestamp, open, high, low, close }
// KHÔNG có volume — phải lookup từ this.cache.data bằng getBarByTime()
```
**Critical:** Volume KHÔNG có trong `seriesData` vì chỉ CandlestickData được setData. Phải dùng `getBarByTime(param.time)` để lấy đầy đủ bar kể cả volume.

### HoverTooltip implementation

```typescript
// frontend/HoverTooltip.ts
import type { IChartApi, MouseEventParams, UTCTimestamp } from 'lightweight-charts';
import type { ChartController } from './ChartController';

function formatPrice(v: number): string {
  return v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatVolume(v: number): string {
  return v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatTimestampUTC7(timestampMs: number): string {
  // Add 7 hours UTC offset (display only — data stored as UTC)
  const utc7Ms = timestampMs + 7 * 3600 * 1000;
  const d = new Date(utc7Ms);
  const dd   = String(d.getUTCDate()).padStart(2, '0');
  const mm   = String(d.getUTCMonth() + 1).padStart(2, '0');
  const yyyy = d.getUTCFullYear();
  const hh   = String(d.getUTCHours()).padStart(2, '0');
  const min  = String(d.getUTCMinutes()).padStart(2, '0');
  return `${dd}/${mm}/${yyyy} ${hh}:${min} UTC+7`;
}

export class HoverTooltip {
  private el: HTMLElement;
  private container: HTMLElement;
  private controller: ChartController;
  private boundHandler: (param: MouseEventParams) => void;

  constructor(container: HTMLElement, controller: ChartController) {
    this.container = container;
    this.controller = controller;
    this.el = document.createElement('div');
    this.el.id = 'ohlcv-tooltip';
    this.el.setAttribute('role', 'status');
    this.el.setAttribute('aria-live', 'polite');
    this.boundHandler = this.handleCrosshairMove.bind(this);
  }

  init(): void {
    this.container.appendChild(this.el);
    this.controller.subscribeHover(this.boundHandler);
  }

  private handleCrosshairMove(param: MouseEventParams): void {
    if (!param.time || !param.point) {
      this.el.style.display = 'none';
      return;
    }

    const bar = this.controller.getBarByTime(param.time as number);
    if (!bar) {
      this.el.style.display = 'none';
      return;
    }

    // Format content
    const timeStr = formatTimestampUTC7(bar.timestamp);
    this.el.innerHTML = `
      <div class="tooltip-time">${timeStr}</div>
      <div class="tooltip-grid">
        <span class="tooltip-label">O</span><span class="tooltip-value">${formatPrice(bar.open)}</span>
        <span class="tooltip-label">H</span><span class="tooltip-value tooltip-value--high">${formatPrice(bar.high)}</span>
        <span class="tooltip-label">L</span><span class="tooltip-value tooltip-value--low">${formatPrice(bar.low)}</span>
        <span class="tooltip-label">C</span><span class="tooltip-value">${formatPrice(bar.close)}</span>
        <span class="tooltip-label">Vol</span><span class="tooltip-value">${formatVolume(bar.volume)}</span>
      </div>
    `;

    // Position: boundary-aware
    const containerWidth  = this.container.clientWidth;
    const containerHeight = this.container.clientHeight;
    const tooltipWidth    = this.el.offsetWidth || 160;   // fallback nếu display:none
    const tooltipHeight   = this.el.offsetHeight || 110;
    const OFFSET          = 12;  // px gap between cursor and tooltip

    let left: number;
    let top: number;

    if (param.point.x > containerWidth / 2) {
      // Right half → show LEFT of cursor
      left = param.point.x - tooltipWidth - OFFSET;
    } else {
      // Left half → show RIGHT of cursor
      left = param.point.x + OFFSET;
    }

    // Vertical: align near cursor, clamp to container
    top = param.point.y - tooltipHeight / 2;
    top = Math.max(8, Math.min(top, containerHeight - tooltipHeight - 8));
    // Clamp left too
    left = Math.max(8, Math.min(left, containerWidth - tooltipWidth - 8));

    this.el.style.left    = `${left}px`;
    this.el.style.top     = `${top}px`;
    this.el.style.display = 'block';
  }

  destroy(): void {
    // LW Charts v5: unsubscribeCrosshairMove
    // Lưu ý: LW Charts v5 không expose unsubscribeCrosshairMove trực tiếp trên chart instance
    // Workaround: không cần unsubscribe nếu chart bị destroy (chartController.destroy() calls chart.remove())
    if (this.el.parentNode) {
      this.el.remove();
    }
  }
}
```

### ChartController additions (diff từ Story 2.1)

```typescript
// Trong class ChartController — thêm property + methods:

private container: HTMLElement | undefined;  // ← thêm field

// Trong init():
init(container: HTMLElement): void {
  this.container = container;  // ← thêm dòng này ở đầu
  // ... existing code ...
}

// Thêm 3 methods public:
subscribeHover(cb: (param: MouseEventParams) => void): void {
  this.chart?.subscribeCrosshairMove(cb);
}

getBarByTime(timeSeconds: number): OHLCVBar | undefined {
  if (!this.cache) return undefined;
  // timestamp trong cache = Unix ms, timeSeconds từ LW Charts = Unix seconds
  return this.cache.data.find(b => Math.round(b.timestamp / 1000) === timeSeconds);
}

getContainer(): HTMLElement | undefined {
  return this.container;
}
```

**Important:** Dùng `Math.round(b.timestamp / 1000)` thay vì exact division để tránh floating-point rounding issues với ms timestamps.

### main.ts — thêm HoverTooltip initialization

```typescript
// Thêm import
import { HoverTooltip } from './HoverTooltip';

// Trong init():
let hoverTooltip: HoverTooltip;

// Sau chartController.init(container):
hoverTooltip = new HoverTooltip(container, chartController);
hoverTooltip.init();
// HoverTooltip.init() phải gọi SAU ChartController.init()
// vì subscribeHover cần this.chart đã tồn tại
```

### Tooltip CSS — thêm vào `static/style.css`

```css
/* Trong @layer components */

/* OHLCV Hover Tooltip */
#ohlcv-tooltip {
  display: none;
  position: absolute;
  z-index: 100;
  pointer-events: none;      /* không interfere với chart mouse events */
  background: var(--sem-bg-surface);
  border: 1px solid var(--sem-border);
  border-radius: 6px;
  padding: 8px 10px;
  min-width: 148px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

.tooltip-time {
  font-family: var(--font-data);
  font-size: 11px;           /* --type-price-sm */
  color: var(--sem-text-muted);
  margin-bottom: 6px;
  white-space: nowrap;
}

.tooltip-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: 8px;
  row-gap: 2px;
  align-items: baseline;
}

.tooltip-label {
  font-family: var(--font-ui);
  font-size: 11px;             /* --type-ui-sm */
  color: var(--sem-text-muted);
  font-weight: 400;
}

.tooltip-value {
  font-family: var(--font-data);
  font-size: 14px;             /* --type-price-lg */
  font-weight: 500;
  color: var(--sem-text-primary);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.tooltip-value--high { color: var(--sem-candle-bull); }
.tooltip-value--low  { color: var(--sem-candle-bear); }
```

### index.html — KHÔNG cần thêm `<div id="ohlcv-tooltip">`

`HoverTooltip.init()` tự tạo và append element vào container. Không cần hardcode trong HTML.

### Positioning: tại sao không dùng floating-ui

UX spec mention `floating-ui` (5KB) nhưng:
1. **Không có trong `package.json`** — thêm dependency mới cần justify
2. **Scope không cần thiết:** Tooltip chỉ cần boundary-aware positioning trong chart container — không cần full flip/shift middleware của floating-ui
3. **param.point from LW Charts** đã cho pixel coordinates → simple math đủ dùng

Quyết định: implement WITHOUT floating-ui. Nếu Phase 2 cần trade marker tooltips phức tạp hơn, lúc đó add floating-ui.

### Timestamp conversion pattern

Cùng pattern đã dùng trong `ChartController.localization.timeFormatter`:
```typescript
// UTC timestamp (ms) → UTC+7 display
const utc7Ms = bar.timestamp + 7 * 3600 * 1000;
const d = new Date(utc7Ms);
// Read via d.getUTCXxx() — safe vì đã shift offset thủ công
```

### Volume number format

BTC/USDT volume là số lượng BTC traded. Thường trong range 1,000–10,000 BTC cho 4h candle. Format: 2 decimal places với thousand separator → `toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})`.

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/ChartController.ts` | Thêm `private container`, `subscribeHover()`, `getBarByTime()`, `getContainer()` + import `MouseEventParams` |
| `frontend/main.ts` | Import + init `HoverTooltip` sau `chartController.init()` |
| `static/style.css` | Thêm `#ohlcv-tooltip` CSS vào `@layer components` |

### Files cần tạo mới

| File | Nội dung |
|------|----------|
| `frontend/HoverTooltip.ts` | DOM tooltip class, crosshair subscriber, boundary-aware positioning |

### Files KHÔNG được touch

- `backend/` — story này chỉ là frontend
- `frontend/types.ts` — không cần thêm type mới (OHLCVBar đã đủ, MouseEventParams từ LW Charts)
- `frontend/EventBus.ts` — không cần event mới cho tooltip
- `frontend/SettingsManager.ts`, `frontend/ToastManager.ts` — Story 2.2 scope

### Dependency order trong story

1. **ChartController.ts** — thêm 3 methods (không phụ thuộc gì mới)
2. **HoverTooltip.ts** — import ChartController (type only)
3. **main.ts** — import HoverTooltip + init
4. **style.css** — thêm tooltip CSS

### Lưu ý từ Story 2.1 — ChartController init order

Story 2.1 đã thiết lập: `chart:ready` event được emit từ cuối `ChartController.init()`. Nhưng với `HoverTooltip`, quan trọng hơn là gọi `HoverTooltip.init()` SAU `chartController.init()` — không phải sau `chart:ready` event. Lý do: `init()` là synchronous và `chart` instance tồn tại ngay sau `createChart()` call.

Thứ tự init trong `main.ts`:
```typescript
chartController.init(container);         // 1. chart created, series added
hoverTooltip.init();                      // 2. subscribe crosshairMove, append DOM
await doLoad(settings);                   // 3. fetch data → render bars
```

### References

- FR (hover tooltip): epics-phase1.md → Story 2.4, lines 628–641
- UX-DR (tooltip design): ux-design-specification.md, line 544 (components table)
- ADR-13: UTC+7 localization — architecture.md
- Previous story: `_bmad-output/implementation-artifacts/p1-2-2-timeframe-selector-va-date-range-picker.md`
- LW Charts v5 crosshair API: `subscribeCrosshairMove` — architecture.md line 116

## Dev Agent Record

### Agent Model Used

mimo-v2.5-pro

### Debug Log References

- Build: `npm run build` — 284.9kb output, 35ms, no errors
- Typecheck: `npm run typecheck` — no errors

### Completion Notes List

- All 5 tasks completed
- ChartController: added `subscribeHover()`, `getBarByTime()`, `getContainer()`, stored `container` field, imported `MouseEventParams`
- HoverTooltip: DOM tooltip created dynamically in `init()`, boundary-aware positioning (left/right of cursor based on x > 50%), vertical clamping
- Timestamp format: DD/MM/YYYY HH:mm UTC+7 using manual offset addition
- Volume formatted with thousand separator + 2 decimal places
- Tooltip hides when `param.time` is undefined (mouse outside data area)
- index.html NOT modified — HoverTooltip creates its own DOM element
- Note: ChartController.ts was externally modified (LRU1Cache now includes dateStart/dateEnd, abortController added) — compatible with tooltip changes

### File List

- `frontend/ChartController.ts` — modified (added subscribeHover, getBarByTime, getContainer, container field, MouseEventParams import)
- `frontend/HoverTooltip.ts` — created (DOM tooltip class, crosshair subscriber, boundary-aware positioning)
- `frontend/main.ts` — modified (import HoverTooltip, init after chartController.init())
- `static/style.css` — modified (#ohlcv-tooltip CSS added to @layer components)
