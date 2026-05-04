# Story P1-3.1: Entry/TP/SL Line Drawing với Price Snap (CoordinateTranslator + DrawingManager Scaffold)

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (5)

1. **`destroy()` leaks ResizeObserver + chart subscriptions** — HIGH (Blind + Edge Case)
   - Stored `resizeObserver`, `unsubRangeChange`, `unsubClick` as class fields
   - `destroy()` now disconnects observer and unsubscribes all chart callbacks
   - File: `DrawingManager.ts`

2. **`_startDrag` allows concurrent drags — orphaned listeners + race on lines Map** — HIGH (Blind + Edge Case)
   - Added `private dragging: LineType | null = null` guard
   - `_startDrag` returns early if `this.dragging` is set; cleared in `onUp`
   - File: `DrawingManager.ts`

3. **`init()` not idempotent — double canvas/observer/click handler** — MED (Edge Case)
   - Added `if (this.canvas) return;` guard at top of `init()`
   - File: `DrawingManager.ts`

4. **`ctx.scale(dpr, dpr)` relies on implicit canvas.width reset** — MED (Blind + Edge Case)
   - Changed to `ctx.setTransform(dpr, 0, 0, dpr, 0, 0)` — explicit, no implicit coupling
   - File: `DrawingManager.ts`

5. **`clearLine()` doesn't emit event (inconsistent with `setLine`/`clearAll`)** — MED
   - Added `eventBus.emit('drawing:cleared', {})` to `clearLine()`
   - File: `DrawingManager.ts`

### All 10 ACs: FULLY MET (Acceptance Auditor)

### Deferred

- RR calculation assumes LONG direction — negative rr badge never triggers for SHORT — UX polish, defer
- Handle mousedown listeners not cleaned up in destroy() — GC minor, defer
- `isUpdating` is public mutable field — encapsulation concern, defer
- freeze/unfreeze only on 'playing'/'stopped' — 'paused' state gap — Epic P1-4 scope, defer

## Story

As a trader,
I want to place Entry, TP, and SL lines on the chart with a single click and price snap,
So that I can define my strategy visually at precise price levels.

## Acceptance Criteria

1. **Given** chart đã render với data và `chart:dataLoaded` đã fire
   **When** `CoordinateTranslator.init(series)` được gọi
   **Then** `series.priceToCoordinate(price)` và `series.coordinateToPrice(y)` hoạt động chính xác
   **And** CoordinateTranslator không khởi tạo trước khi chart có data (lazy init guard)

2. **Given** chart đang hiển thị với data
   **When** chart zoom hoặc pan (visible range thay đổi)
   **Then** DrawingManager nhận sự kiện và redraw tất cả existing lines trên overlay canvas
   **And** `CoordinateTranslator.isUpdating` flag ngăn re-entrant event loop

3. **Given** trader click toolbar button "Entry"
   **When** button được click
   **Then** button hiển thị trạng thái active (highlighted)
   **And** chart container đổi cursor thành `crosshair`
   **And** ESC key cancel drawing mode — cursor trở về mặc định, button deactivated

4. **Given** trader đang ở drawing mode (active tool selected)
   **When** trader click lên chart area
   **Then** đường ngang xuất hiện trên overlay canvas tại mức giá đã snap
   **And** price snap: `Math.round(price * 100) / 100` (BTC/USDT min tick = $0.01)
   **And** drawing mode tự động exit sau khi đặt đường (single-click, not toggle)

5. **Given** trader đặt đường Entry
   **When** đường render trên canvas
   **Then** Entry line: màu `#2f81f7` (blue), solid, lineWidth 2px

6. **Given** trader đặt đường TP
   **When** đường render trên canvas
   **Then** TP line: màu `#3fb950` (green), dashed (`[6, 4]`), lineWidth 1.5px

7. **Given** trader đặt đường SL
   **When** đường render trên canvas
   **Then** SL line: màu `#f85149` (red), dotted (`[2, 4]`), lineWidth 1.5px

8. **Given** trader đã vẽ 1 Entry line và click Entry button lại, rồi đặt đường mới
   **When** đường mới được placed
   **Then** đường Entry cũ bị thay thế — chỉ tồn tại 1 Entry + 1 TP + 1 SL tại mọi thời điểm (FR19b)

9. **Given** trader đã vẽ ít nhất 1 đường
   **When** code gọi `drawingManager.hasDrawings()`
   **Then** trả về `true`
   **And** khi không có đường nào, trả về `false`

10. **Given** trader đang ở Setup mode (chưa Play)
    **When** chart resize (window resize)
    **Then** overlay canvas resize khớp với chart container — đường không bị shift position
    **And** drawings re-render chính xác sau resize

## Tasks / Subtasks

- [x] Task 1: Cập nhật `frontend/types.ts` — Thêm Drawing types (AC: #1–#9)
  - [x] `type LineType = 'entry' | 'tp' | 'sl'`
  - [x] `interface DrawingLine { type: LineType; price: number }`
  - [x] `interface DrawingSnapshot { lines: Map<LineType, DrawingLine | null> }`
  - [x] `EventMap`: đã có `'drawing:lineChanged': { type: LineType; price: number }`
  - [x] `EventMap`: đã có `'chart:ready': Record<string, never>`

- [x] Task 2: Tạo `frontend/CoordinateTranslator.ts` — Y-axis price/coordinate bridge (AC: #1, #2)
  - [x] Class `CoordinateTranslator`
  - [x] `private series: ISeriesApi<'Candlestick'> | null = null`
  - [x] `isUpdating = false` (public flag — DrawingManager đọc để tránh event loop)
  - [x] `init(series: ISeriesApi<'Candlestick'>): void` — lưu series reference
  - [x] `isInitialized(): boolean`
  - [x] `priceToY(price: number): number | null` — gọi `series.priceToCoordinate(price)`
  - [x] `yToPrice(y: number): number | null` — gọi `series.coordinateToPrice(y)`
  - [x] Guard: return null nếu series chưa init

- [x] Task 3: Tạo `frontend/DrawingManager.ts` — Overlay canvas + line management (AC: #2–#10)
  - [x] Class `DrawingManager` nhận `(chartController: ChartController, translator: CoordinateTranslator)`
  - [x] `private canvas: HTMLCanvasElement`
  - [x] `private lines: Map<LineType, DrawingLine | null>` — init với `{entry: null, tp: null, sl: null}`
  - [x] `init(container: HTMLElement): void`
    - [x] Tạo và append overlay canvas (absolute position, pointer-events: none)
    - [x] Subscribe `chart.timeScale().subscribeVisibleLogicalRangeChange(() => this.redrawAll())`
    - [x] `ResizeObserver` on container → resize canvas + redrawAll
    - [x] Subscribe `chart.subscribeClick((param) => this._handleChartClick(param))`
  - [x] `private _handleChartClick(param: MouseEventParams): void`
    - [x] Guard: nếu `activeType === null` return
    - [x] Guard: nếu `!param.point` return (clicked outside chart)
    - [x] `const raw = translator.yToPrice(param.point.y)` → nếu null return
    - [x] `const snapped = Math.round(raw * 100) / 100`
    - [x] `this.setLine(activeType, snapped)` + `this.activeType = null`
    - [x] Reset cursor + deactivate toolbar button
  - [x] `setLine(type: LineType, price: number): void`
  - [x] `clearLine(type: LineType): void`
  - [x] `clearAll(): void`
  - [x] `hasDrawings(): boolean` — trả về true nếu bất kỳ line nào non-null
  - [x] `getSnapshot(): DrawingSnapshot` — deep copy current lines map
  - [x] `restore(snapshot: DrawingSnapshot): void` + redrawAll
  - [x] `setActiveType(type: LineType | null): void` — toolbar wiring
  - [x] `getActiveType(): LineType | null`
  - [x] `private redrawAll(): void` — clear canvas + redraw tất cả non-null lines
  - [x] `private _drawLine(line: DrawingLine): void` — canvas 2D rendering với đúng color/dash

- [x] Task 4: Cập nhật `frontend/ChartController.ts` — Expose candlestick series (AC: #1)
  - [x] Add `getCandlestickSeries(): ISeriesApi<'Candlestick'> | undefined`

- [x] Task 5: Cập nhật `frontend/main.ts` — Init sequence + toolbar wiring (AC: #3, #4)
  - [x] Import `CoordinateTranslator`, `DrawingManager`
  - [x] Khởi tạo instances sau `chartController.init()`
  - [x] Lazy init CoordinateTranslator trong `doLoad` (lần đầu tiên data load)
  - [x] `drawingManager.init(container)` sau `chartController.init()`
  - [x] Wire toolbar buttons: `#btn-draw-entry`, `#btn-draw-tp`, `#btn-draw-sl`
  - [x] ESC key listener → `drawingManager.setActiveType(null)` + clear cursor

- [x] Task 6: Cập nhật `static/index.html` — Drawing toolbar buttons (AC: #3)
  - [x] Thêm `<button id="btn-draw-entry" class="draw-btn" data-type="entry">Entry</button>`
  - [x] Thêm `<button id="btn-draw-tp" class="draw-btn" data-type="tp">TP</button>`
  - [x] Thêm `<button id="btn-draw-sl" class="draw-btn" data-type="sl">SL</button>`
  - [x] Đặt trong toolbar section, sau indicator toggles

- [x] Task 7: Cập nhật `static/style.css` — Drawing toolbar styles (AC: #3, #5–#7)
  - [x] `.draw-btn` base style (trong `@layer components`)
  - [x] `.draw-btn[data-type="entry"].active` — blue highlight
  - [x] `.draw-btn[data-type="tp"].active` — green highlight
  - [x] `.draw-btn[data-type="sl"].active` — red highlight
  - [x] `.chart-drawing-mode` class cho container → `cursor: crosshair !important`

## Dev Notes

### Epic P1-3 là epic đầu tiên — Frontend chưa có nhiều file

`frontend/` directory hiện có: `EventBus.ts`, `ReplayEngine.ts`, `types.ts`, và Phase 2 files.
**Các files từ Epic P1-2 stories (p1-2-1 → p1-2-5) phải được implement trước:**
- `frontend/ChartController.ts` (từ p1-2-1) — required: `getChart()`, `getCandlestickSeries()`
- `frontend/IndicatorOverlay.ts` (từ p1-2-4) — không ảnh hưởng story này
- `frontend/VolumeOverlay.ts` (từ p1-2-5) — không ảnh hưởng story này

**Dependencies block:** Story này không thể implement nếu `ChartController.ts` chưa tồn tại.

### Architecture: Canvas Overlay approach (không dùng LW Charts native price lines)

Tại sao **canvas overlay** thay vì `series.createPriceLine()`:
1. `createPriceLine()` không hỗ trợ drag natively — p1-3-2 cần drag, canvas cho phép
2. Canvas cho full control: custom dash pattern, tương lai thêm price label (p1-3-3), handle zone
3. Architecture đã thiết kế CoordinateTranslator + canvas pattern — follow it

```
chartContainer (position: relative)
  ├── LW Charts main canvas (auto-created by library)
  └── overlay canvas (position: absolute; top:0; left:0; pointer-events:none)
                      ↑ pointer-events: none = mouse events pass through to LW Charts
                        click detection dùng chart.subscribeClick() thay vì canvas events
```

### CoordinateTranslator — Lazy Init Pattern

```typescript
// frontend/CoordinateTranslator.ts
import type { ISeriesApi } from 'lightweight-charts';

export class CoordinateTranslator {
  private series: ISeriesApi<'Candlestick'> | null = null;
  isUpdating = false;   // public — DrawingManager reads to prevent event loops

  init(series: ISeriesApi<'Candlestick'>): void {
    this.series = series;
  }

  isInitialized(): boolean {
    return this.series !== null;
  }

  priceToY(price: number): number | null {
    if (!this.series) return null;
    const coord = this.series.priceToCoordinate(price);
    return coord ?? null;
  }

  yToPrice(y: number): number | null {
    if (!this.series) return null;
    const price = this.series.coordinateToPrice(y);
    return price ?? null;
  }
}
```

**Init trigger trong main.ts:** Gọi `coordinateTranslator.init()` khi `chart:dataLoaded` fire lần đầu — lúc này chart đã render và series đã có data, `priceToCoordinate` sẽ trả về valid values.

```typescript
let translatorInitialized = false;
eventBus.on('chart:dataLoaded', ({ barCount, bars }) => {
  if (!translatorInitialized) {
    const series = chartController.getCandlestickSeries();
    if (series) {
      coordinateTranslator.init(series);
      translatorInitialized = true;
    }
  }
  // ... rest of handler
});
```

### DrawingManager — Canvas Overlay + Line Management

```typescript
// frontend/DrawingManager.ts
import { MouseEventParams } from 'lightweight-charts';
import type { ChartController } from './ChartController';
import type { CoordinateTranslator } from './CoordinateTranslator';
import type { LineType, DrawingLine, DrawingSnapshot } from './types';

// Line rendering config
const LINE_CONFIG: Record<LineType, { color: string; dash: number[]; width: number }> = {
  entry: { color: '#2f81f7', dash: [],        width: 2   },  // solid
  tp:    { color: '#3fb950', dash: [6, 4],    width: 1.5 },  // dashed
  sl:    { color: '#f85149', dash: [2, 4],    width: 1.5 },  // dotted
};

export class DrawingManager {
  private controller: ChartController;
  private translator: CoordinateTranslator;
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;
  private lines = new Map<LineType, DrawingLine | null>([
    ['entry', null], ['tp', null], ['sl', null],
  ]);
  private activeType: LineType | null = null;
  private onActiveTypeChange: ((type: LineType | null) => void) | null = null;

  constructor(controller: ChartController, translator: CoordinateTranslator) {
    this.controller = controller;
    this.translator = translator;
  }

  // Callback for toolbar button update — main.ts passes this
  setActiveTypeChangeCallback(cb: (type: LineType | null) => void): void {
    this.onActiveTypeChange = cb;
  }

  init(container: HTMLElement): void {
    // 1. Create overlay canvas
    const canvas = document.createElement('canvas');
    canvas.style.cssText = [
      'position:absolute', 'top:0', 'left:0',
      'width:100%', 'height:100%',
      'pointer-events:none',   // clicks pass through to LW Charts
      'z-index:10',
    ].join(';');
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');

    // Ensure container is positioned
    if (getComputedStyle(container).position === 'static') {
      container.style.position = 'relative';
    }
    container.appendChild(canvas);

    // 2. Size canvas to match container
    this._resizeCanvas(container);
    const ro = new ResizeObserver(() => {
      this._resizeCanvas(container);
      this.redrawAll();
    });
    ro.observe(container);

    // 3. Subscribe to chart zoom/pan events for re-render
    const chart = this.controller.getChart();
    if (!chart) return;

    chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
      if (this.translator.isUpdating) return;
      this.translator.isUpdating = true;
      this.redrawAll();
      this.translator.isUpdating = false;
    });

    chart.priceScale('right').subscribePriceScaleOptionsChanged(() => {
      if (this.translator.isUpdating) return;
      this.translator.isUpdating = true;
      this.redrawAll();
      this.translator.isUpdating = false;
    });

    // 4. Click detection via LW Charts API (not canvas events)
    chart.subscribeClick((param: MouseEventParams) => {
      this._handleChartClick(param);
    });
  }

  private _resizeCanvas(container: HTMLElement): void {
    if (!this.canvas) return;
    this.canvas.width = container.clientWidth;
    this.canvas.height = container.clientHeight;
  }

  private _handleChartClick(param: MouseEventParams): void {
    if (!this.activeType) return;
    if (!param.point) return;
    if (!this.translator.isInitialized()) return;

    const rawPrice = this.translator.yToPrice(param.point.y);
    if (rawPrice === null) return;

    const snapped = Math.round(rawPrice * 100) / 100;  // $0.01 BTC tick
    this.setLine(this.activeType, snapped);

    // Exit drawing mode after single click
    this.setActiveType(null);
  }

  setLine(type: LineType, price: number): void {
    this.lines.set(type, { type, price });
    this.redrawAll();
  }

  clearLine(type: LineType): void {
    this.lines.set(type, null);
    this.redrawAll();
  }

  clearAll(): void {
    this.lines.set('entry', null);
    this.lines.set('tp', null);
    this.lines.set('sl', null);
    this.redrawAll();
  }

  hasDrawings(): boolean {
    return Array.from(this.lines.values()).some(line => line !== null);
  }

  getSnapshot(): DrawingSnapshot {
    return { lines: new Map(this.lines) };
  }

  restore(snapshot: DrawingSnapshot): void {
    this.lines = new Map(snapshot.lines);
    this.redrawAll();
  }

  setActiveType(type: LineType | null): void {
    this.activeType = type;
    this.onActiveTypeChange?.(type);
  }

  getActiveType(): LineType | null {
    return this.activeType;
  }

  redrawAll(): void {
    if (!this.ctx || !this.canvas) return;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    for (const line of this.lines.values()) {
      if (line) this._drawLine(line);
    }
  }

  private _drawLine(line: DrawingLine): void {
    if (!this.ctx || !this.canvas) return;
    if (!this.translator.isInitialized()) return;

    const y = this.translator.priceToY(line.price);
    if (y === null) return;

    const cfg = LINE_CONFIG[line.type];
    const ctx = this.ctx;
    const w = this.canvas.width;

    ctx.save();
    ctx.beginPath();
    ctx.strokeStyle = cfg.color;
    ctx.lineWidth = cfg.width;
    ctx.setLineDash(cfg.dash);
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
    ctx.restore();
  }

  destroy(): void {
    this.canvas?.remove();
    this.canvas = null;
    this.ctx = null;
  }
}
```

### types.ts — Drawing Types mới

```typescript
// Thêm vào frontend/types.ts

export type LineType = 'entry' | 'tp' | 'sl';

export interface DrawingLine {
  type: LineType;
  price: number;
}

export interface DrawingSnapshot {
  lines: Map<LineType, DrawingLine | null>;
}
```

**`EventMap` đã có `'drawing:lineChanged'`** — verify event payload type khớp với `LineType`.

### ChartController.ts — Thêm getCandlestickSeries()

```typescript
// Thêm private field và method vào ChartController
private candlestickSeries: ISeriesApi<'Candlestick'> | undefined;

// Trong init(), ngay sau addSeries():
this.candlestickSeries = this.chart.addSeries(CandlestickSeries, { ... });

// Thêm method:
getCandlestickSeries(): ISeriesApi<'Candlestick'> | undefined {
  return this.candlestickSeries;
}
```

### main.ts — Init Sequence và Toolbar Wiring

```typescript
import { CoordinateTranslator } from './CoordinateTranslator';
import { DrawingManager } from './DrawingManager';

// Sau chartController.init():
const coordinateTranslator = new CoordinateTranslator();
const drawingManager = new DrawingManager(chartController, coordinateTranslator);

// Init DrawingManager (cần container)
const chartContainer = document.getElementById('chart-container')!;
drawingManager.init(chartContainer);

// Lazy init CoordinateTranslator khi data load lần đầu
let translatorReady = false;
eventBus.on('chart:dataLoaded', ({ barCount, bars }) => {
  if (!translatorReady) {
    const series = chartController.getCandlestickSeries();
    if (series) {
      coordinateTranslator.init(series);
      translatorReady = true;
    }
  }
  indicatorOverlay.update(bars);
  volumeOverlay.update(bars);
  // ... existing handlers
});

// Toolbar buttons
function activateDrawTool(type: LineType): void {
  const current = drawingManager.getActiveType();
  // Toggle: click same button again → deactivate
  drawingManager.setActiveType(current === type ? null : type);
}

document.getElementById('btn-draw-entry')?.addEventListener('click', () => activateDrawTool('entry'));
document.getElementById('btn-draw-tp')?.addEventListener('click', () => activateDrawTool('tp'));
document.getElementById('btn-draw-sl')?.addEventListener('click', () => activateDrawTool('sl'));

// DrawingManager callback → update toolbar UI + cursor
drawingManager.setActiveTypeChangeCallback((activeType) => {
  // Update button active states
  ['entry', 'tp', 'sl'].forEach(t => {
    const btn = document.getElementById(`btn-draw-${t}`);
    btn?.classList.toggle('active', activeType === t);
  });
  // Update cursor
  if (activeType) {
    chartContainer.classList.add('chart-drawing-mode');
  } else {
    chartContainer.classList.remove('chart-drawing-mode');
  }
});

// ESC to cancel drawing mode
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    drawingManager.setActiveType(null);
  }
});
```

### Integration với p1-2-2 (Timeframe Switch Toast + Undo)

Story p1-2-2 đã implement timeframe switch với undo pattern, sử dụng guard:
```typescript
drawingManager?.hasDrawings() ?? false  // null khi DrawingManager chưa tồn tại
```

Khi p1-3-1 implement DrawingManager và pass instance vào main.ts, logic trong p1-2-2 tự động activate:
- Timeframe switch khi `hasDrawings() === true` → hiển thị toast "Drawings đã bị xóa — [Undo] (5s)"
- `clearAll()` xóa drawings trước khi reload  
- Undo: `restore(snapshot)` phục hồi drawings

**Không cần sửa lại p1-2-2 code** — chỉ cần DrawingManager instance được khai báo trong scope mà p1-2-2 handler có thể access (đều trong main.ts).

### LW Charts v5 — chart.subscribeClick() API

```typescript
// LW Charts v5 MouseEventParams
interface MouseEventParams {
  point?: { x: number; y: number };  // pixel coords relative to chart container
  time?: UTCTimestamp;               // hovered time (bar's timestamp)
  seriesData: Map<ISeriesApi, any>;  // data for each series at hover point
  hoveredSeries?: ISeriesApi;
  hoveredObjectId?: unknown;
}

// subscribeClick fires only when clicking WITHIN the chart area (not on axes)
chart.subscribeClick((param: MouseEventParams) => {
  if (!param.point) return;  // null when clicking on axes
  const price = series.coordinateToPrice(param.point.y);
  // ...
});
```

**IMPORTANT:** `param.point.y` là pixel Y relative to chart container, không phải window. `coordinateToPrice(y)` nhận pixel Y và trả về price — valid sau khi chart đã render.

### Price Snap: BTC/USDT

```typescript
// $0.01 minimum tick cho BTC/USDT
const snapped = Math.round(rawPrice * 100) / 100;

// Ví dụ:
// rawPrice = 68499.73412  → snapped = 68499.73
// rawPrice = 68500.006    → snapped = 68500.01
```

**Không dùng** OHLC snap (snap to nearest OHLC level) — quá phức tạp cho MVP. Simple `$0.01` tick đủ cho BTC strategy practice.

### Canvas Resize — Pixel Ratio

```typescript
// Để canvas không bị blurry trên Retina/HiDPI displays:
private _resizeCanvas(container: HTMLElement): void {
  if (!this.canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const w = container.clientWidth;
  const h = container.clientHeight;
  
  this.canvas.width = w * dpr;
  this.canvas.height = h * dpr;
  this.canvas.style.width = `${w}px`;
  this.canvas.style.height = `${h}px`;
  
  // Scale context for DPR
  this.ctx?.scale(dpr, dpr);
}
```

**CRITICAL:** Sau mỗi resize, `ctx.scale(dpr, dpr)` phải gọi lại vì `canvas.width` assignment reset context state. Pattern: resize → scale → redrawAll.

### index.html — Drawing Toolbar Buttons

```html
<!-- Trong toolbar section, sau indicator toggles (MA20, EMA20, Vol) -->
<div class="toolbar-separator"></div>

<button id="btn-draw-entry" class="draw-btn" data-type="entry"
        title="Đặt Entry line (click để activate, click lại để cancel)">
  Entry
</button>
<button id="btn-draw-tp" class="draw-btn" data-type="tp"
        title="Đặt Take Profit line">
  TP
</button>
<button id="btn-draw-sl" class="draw-btn" data-type="sl"
        title="Đặt Stop Loss line">
  SL
</button>
```

### CSS — Drawing Toolbar Styles

```css
/* @layer components */

.draw-btn {
  padding: var(--space-1) var(--space-2);
  background: var(--sem-bg-secondary);
  border: 1px solid var(--sem-border);
  border-radius: 4px;
  color: var(--sem-text-secondary);
  cursor: pointer;
  font-size: 0.8125rem;
  font-weight: 500;
  transition: all 120ms ease;
}

.draw-btn:hover {
  background: var(--sem-bg-hover);
  color: var(--sem-text-primary);
}

/* Active states — dùng semantic tokens từ UX spec */
.draw-btn[data-type="entry"].active {
  background: rgba(47, 129, 247, 0.15);   /* --prim-blue-500 @ 15% */
  border-color: var(--sem-entry);         /* #2f81f7 */
  color: var(--sem-entry);
}

.draw-btn[data-type="tp"].active {
  background: rgba(63, 185, 80, 0.15);
  border-color: var(--sem-tp);            /* #3fb950 */
  color: var(--sem-tp);
}

.draw-btn[data-type="sl"].active {
  background: rgba(248, 81, 73, 0.15);
  border-color: var(--sem-sl);            /* #f85149 */
  color: var(--sem-sl);
}

/* Chart container trong drawing mode */
.chart-drawing-mode {
  cursor: crosshair !important;
}

/* Separator giữa indicator toggles và drawing tools */
.toolbar-separator {
  width: 1px;
  height: 20px;
  background: var(--sem-border);
  margin: 0 var(--space-1);
  align-self: center;
}
```

### Scope của Story này vs Stories tiếp theo

| Feature | Story này (p1-3-1) | Story |
|---------|-------------------|-------|
| CoordinateTranslator scaffold | ✓ | |
| DrawingManager canvas overlay | ✓ | |
| Click-to-place Entry/TP/SL | ✓ | |
| Price snap ($0.01 tick) | ✓ | |
| Line type limit (max 1 each) | ✓ | |
| Line colors + dash styles | ✓ | |
| Price label text on line | ✗ | p1-3-3 |
| Drag to move | ✗ | p1-3-2 |
| Delete line (keyboard) | ✗ | p1-3-2 |
| R:R ratio display | ✗ | p1-3-4 |
| Toast undo on timeframe switch | Already in p1-2-2 | p1-3-5 (edge cases) |

**p1-3-2 extension point:** Khi p1-3-2 thêm drag support, sẽ:
- Thêm `pointer-events: auto` on canvas khi hover near a line
- Thêm `mousedown` / `mousemove` / `mouseup` handlers on canvas
- DrawingManager đã có infrastructure (lines Map, redrawAll) — chỉ thêm drag handlers

### Architecture Gaps được giải quyết

- **Gap 4 (High):** DrawingManager subscribes zoom/pan events ✓
- **Gap 14 (High):** CoordinateTranslator lazy init sau chart:dataLoaded ✓
- **Gap 15 (Medium):** Y-axis only (price) — không build 2D system ✓
- **ADR-06:** Price snap, coordinateToPrice, priceToCoordinate, lazy init ✓

### Files cần tạo mới

| File | Nội dung |
|------|----------|
| `frontend/CoordinateTranslator.ts` | Y-axis price/coordinate bridge, lazy init, isUpdating guard |
| `frontend/DrawingManager.ts` | Canvas overlay, line management, click handler, zoom/pan subscribe |

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/types.ts` | Add `LineType`, `DrawingLine`, `DrawingSnapshot` |
| `frontend/ChartController.ts` | Add `private candlestickSeries`, `getCandlestickSeries()` |
| `frontend/main.ts` | Import + init CoordinateTranslator + DrawingManager, toolbar wiring, ESC key |
| `static/index.html` | Add `#btn-draw-entry`, `#btn-draw-tp`, `#btn-draw-sl` buttons |
| `static/style.css` | Add `.draw-btn`, `.draw-btn.active`, `.chart-drawing-mode`, `.toolbar-separator` |

### Files KHÔNG được touch

- `frontend/ReplayEngine.ts` — chưa liên quan (Epic 4)
- `frontend/IndicatorOverlay.ts` — scope p1-2-4
- `frontend/VolumeOverlay.ts` — scope p1-2-5
- `frontend/HoverTooltip.ts` — scope p1-2-3
- `backend/` — story này chỉ là frontend

### Thứ tự implement

1. **types.ts** — thêm LineType, DrawingLine, DrawingSnapshot
2. **CoordinateTranslator.ts** — tạo mới (đơn giản, không dependencies mới)
3. **ChartController.ts** — thêm `getCandlestickSeries()`
4. **DrawingManager.ts** — tạo mới (depends on CoordinateTranslator + ChartController types)
5. **index.html** — thêm 3 buttons trong toolbar
6. **style.css** — thêm CSS classes
7. **main.ts** — wire everything together, lazy init pattern

### Verify Init Sequence

```
1. DOM ready → ChartController.init(container)    [chart created, no data yet]
2. DrawingManager.init(container)                 [canvas appended, subscriptions set]
3. User triggers data load (or auto-load)
4. chart:dataLoaded event fires
   → CoordinateTranslator.init(series)            [lazy init, now valid]
   → indicatorOverlay.update(bars)
   → volumeOverlay.update(bars)
5. User clicks [Entry] button → activateDrawTool('entry')
6. User clicks on chart → _handleChartClick()
   → coordinateToPrice(y) → snap → setLine('entry', price)
   → redrawAll() → Entry line appears on canvas
7. User clicks [TP] → [SL] to complete strategy
```

## Dev Agent Record

### Agent Model Used

mimo-v2.5-pro

### Debug Log References

- Build: 302.4kb, esbuild 34ms
- Typecheck: passed (tsc --noEmit)
- Fix: removed `subscribePriceScaleOptionsChanged` — not available in this LW Charts version

### Completion Notes List

- All 7 tasks completed
- `CoordinateTranslator` created with lazy init pattern (init on first data load)
- `DrawingManager` created with canvas overlay, DPR-aware resize, click-to-place lines
- Price snap: `Math.round(price * 100) / 100` ($0.01 tick for BTC/USDT)
- Line configs: Entry (blue, solid, 2px), TP (green, dashed [6,4], 1.5px), SL (red, dotted [2,4], 1.5px)
- Single-click placement mode (not toggle) — exits drawing mode after placing line
- `getCandlestickSeries()` added to ChartController
- Toolbar buttons with active state highlighting and crosshair cursor
- ESC key cancels drawing mode
- Removed `subscribePriceScaleOptionsChanged` due to LW Charts API incompatibility

### File List

- `frontend/types.ts` — added LineType, DrawingLine, DrawingSnapshot
- `frontend/CoordinateTranslator.ts` — new file, Y-axis price/coordinate bridge
- `frontend/DrawingManager.ts` — new file, canvas overlay + line management
- `frontend/ChartController.ts` — added getCandlestickSeries()
- `frontend/main.ts` — imported CoordinateTranslator + DrawingManager, init + toolbar wiring + ESC key + lazy init
- `static/index.html` — added Entry/TP/SL drawing buttons in toolbar
- `static/style.css` — added .draw-btn, .toolbar-separator, .chart-drawing-mode styles
