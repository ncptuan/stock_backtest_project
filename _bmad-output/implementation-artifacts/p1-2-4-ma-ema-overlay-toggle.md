# Story P1-2.4: MA/EMA Overlay Toggle

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (4)

1. **NaN/Infinity not filtered in `buildLineData`** — HIGH (Blind + Edge Case)
   - Added `Number.isFinite(b[field])` to filter chain to prevent NaN/Infinity values from reaching LW Charts `setData()`
   - File: `IndicatorOverlay.ts`

2. **Indicators not cleared on `loadData()` failure** — HIGH (Edge Case)
   - Added `indicatorOverlay.update([])` before early return when `loadData()` returns null
   - Prevents stale MA/EMA lines persisting on empty chart after error
   - File: `main.ts`

3. **`init()` double-call leaks orphaned series** — MED (Blind + Edge Case)
   - Added `if (this.maSeries) return;` idempotency guard at top of `init()`
   - File: `IndicatorOverlay.ts`

4. **`IndicatorToggleState` exported but never used** — LOW (Blind)
   - Removed dead code from `types.ts`

### All 8 ACs: FULLY MET (Acceptance Auditor)

### Deferred

- `destroy()` gaps — single-user app, page unload cleans up
- `currentBars` shared reference — `_renderBars` already copies via `[...bars]`
- `init()` silently no-ops — ordering enforced by main.ts init sequence
- Hardcoded colors (#2f81f7, #d29922) — LW Charts JS API doesn't support CSS variables
- Toggle state not persisted — intentional per scope, no AC requires it
- `chart:dataLoaded` event bypass — direct call in doLoad() works correctly
- `for` attribute on label — redundant but harmless
- `setData([])` on hide — series invisible with empty data, cosmetic
- Timestamp rounding mismatch — Binance timestamps are whole-second ms multiples

## Story

As a trader,
I want to optionally show MA20 and EMA20 overlays on the chart,
So that I can analyze trend context without cluttering the chart by default.

## Acceptance Criteria

1. **Given** chart đã render với data
   **When** app load lần đầu
   **Then** MA20 và EMA20 đều OFF — không có overlay line nào trên chart
   **And** toolbar checkboxes (hoặc toggles) `#toggle-ma20` và `#toggle-ema20` ở trạng thái unchecked

2. **Given** app đang hiển thị chart với data
   **When** trader bật `#toggle-ma20`
   **Then** MA20 line xuất hiện trên chart với màu `#2f81f7` (blue, `--prim-blue-500`)
   **And** các bars đầu (warm-up period, index 0–18) hiển thị với giá trị null — không vẽ line về điểm 0

3. **Given** app đang hiển thị chart với data
   **When** trader bật `#toggle-ema20`
   **Then** EMA20 line xuất hiện trên chart với màu `#d29922` (yellow, `--prim-yellow-500`)
   **And** các bars đầu (warm-up period, index 0–18) hiển thị với giá trị null — không vẽ line về điểm 0

4. **Given** MA20 hoặc EMA20 đang ON
   **When** trader tắt toggle
   **Then** overlay line biến mất khỏi chart ngay lập tức

5. **Given** MA20 đang bật và chart reload (timeframe đổi, date range đổi)
   **When** `ChartController.loadData()` hoàn thành
   **Then** MA20 overlay tự động re-render với data mới
   **And** toggle state giữ nguyên (ON/OFF state không bị reset)

6. **Given** EMA20 đang bật và chart reload
   **When** `ChartController.loadData()` hoàn thành
   **Then** EMA20 overlay tự động re-render với data mới
   **And** toggle state giữ nguyên

7. **Given** date range quá ngắn (< 20 bars)
   **When** MA20 hoặc EMA20 được bật
   **Then** hiển thị toast warning: "Date range quá ngắn cho MA/EMA period (cần ≥ 20 bars)"
   **And** series vẫn được tạo nhưng sẽ chỉ có null values

8. **Given** chart chưa có data (empty state)
   **When** trader bật MA20 hoặc EMA20
   **Then** không crash — toggle state được lưu, overlay sẽ render khi data được load
   **And** không hiển thị warning "date range quá ngắn" khi chưa có data

## Tasks / Subtasks

- [x] Task 1: Cập nhật `frontend/types.ts` — Thêm `ma_20`/`ema_20` vào `OHLCVBar` (AC: #2, #3)
  - [x] Add `ma_20: number | null` và `ema_20: number | null` vào interface `OHLCVBar`
  - [x] Add `IndicatorToggleState` interface: `{ ma20: boolean; ema20: boolean }`

- [x] Task 2: Tạo `frontend/IndicatorOverlay.ts` — Manages MA/EMA series (AC: #1–#8)
  - [x] Class `IndicatorOverlay` nhận `(chartController: ChartController)`
  - [x] `init()`: tạo 2 LineSeries (MA + EMA) với LW Charts v5 API
  - [x] `setMa20Visible(visible: boolean)`: show/hide + render MA20
  - [x] `setEma20Visible(visible: boolean)`: show/hide + render EMA20
  - [x] `update(bars: OHLCVBar[])`: re-render visible indicators với data mới
  - [x] `destroy()`: remove series từ chart

- [x] Task 3: Cập nhật `frontend/ChartController.ts` — Expose series creation + data propagation (AC: #5, #6)
  - [x] Add `getChart(): IChartApi | undefined` method để `IndicatorOverlay` có thể add series
  - [x] Sau `_renderBars()`: fire `'chart:dataLoaded'` event với `{ barCount, bars }` để `IndicatorOverlay` có data
  - [x] Update `EventMap['chart:dataLoaded']` để include `bars: OHLCVBar[]`

- [x] Task 4: Cập nhật `frontend/main.ts` — Wire toolbar toggles + IndicatorOverlay (AC: #1–#8)
  - [x] Khởi tạo `IndicatorOverlay` sau `ChartController.init()`
  - [x] Subscribe `chart:dataLoaded` → `indicatorOverlay.update(bars)`
  - [x] `#toggle-ma20` change → `indicatorOverlay.setMa20Visible(checked)` + warning check
  - [x] `#toggle-ema20` change → `indicatorOverlay.setEma20Visible(checked)` + warning check
  - [x] Warning: nếu `chartController.hasData()` && bars.length < 20 → show toast warning

- [x] Task 5: Cập nhật `static/style.css` — Toolbar toggle styles (AC: #1)
  - [x] Style cho `<label class="indicator-toggle">` wrapper
  - [x] Indicator màu sắc swatch nhỏ bên cạnh label text

- [x] Task 6: Cập nhật `static/index.html` — Thêm toggle elements vào toolbar (AC: #1)
  - [x] `<label><input type="checkbox" id="toggle-ma20"> MA20</label>` trong toolbar
  - [x] `<label><input type="checkbox" id="toggle-ema20"> EMA20</label>` trong toolbar

## Dev Notes

### LW Charts v5 — LineSeries API

```typescript
// Import cần thêm vào IndicatorOverlay.ts
import {
  LineSeries,        // v5: series type constant (không phải addLineSeries())
  IChartApi,
  ISeriesApi,
  UTCTimestamp,
} from 'lightweight-charts';

// CRITICAL — v5 breaking change: dùng addSeries(LineSeries, opts) KHÔNG phải addLineSeries()
const maSeries = chart.addSeries(LineSeries, {
  color: '#2f81f7',   // --prim-blue-500 (MA20)
  lineWidth: 1,
  priceLineVisible: false,   // không hiện horizontal line tại last value
  lastValueVisible: false,   // không hiện value label ở right axis
  crosshairMarkerVisible: false,
});

const emaSeries = chart.addSeries(LineSeries, {
  color: '#d29922',   // --prim-yellow-500 (EMA20)
  lineWidth: 1,
  priceLineVisible: false,
  lastValueVisible: false,
  crosshairMarkerVisible: false,
});
```

### Handling null values (warm-up period)

LW Charts v5 `LineSeries.setData()` nhận `LineData[]`:
```typescript
interface LineData {
  time: UTCTimestamp;
  value: number;
}
```

**Null handling:** LW Charts v5 KHÔNG có null value type trong `LineData`. Phải **filter out** các bars có `ma_20 === null` trước khi setData. Line sẽ bắt đầu từ bar đầu tiên có giá trị không null.

```typescript
// Cách đúng — filter null trước khi setData:
function buildLineData(bars: OHLCVBar[], field: 'ma_20' | 'ema_20') {
  return bars
    .filter(b => b[field] !== null && b[field] !== undefined)
    .map(b => ({
      time: (b.timestamp / 1000) as UTCTimestamp,
      value: b[field] as number,
    }));
}

// Cách SAI — gây crash hoặc line về 0:
// bars.map(b => ({ time: ..., value: b.ma_20 ?? 0 }))  ← ❌ line về 0
// bars.map(b => ({ time: ..., value: b.ma_20 }))        ← ❌ TypeScript error
```

### IndicatorOverlay implementation

```typescript
// frontend/IndicatorOverlay.ts
import { LineSeries, ISeriesApi, UTCTimestamp } from 'lightweight-charts';
import type { ChartController } from './ChartController';
import type { OHLCVBar } from './types';

function buildLineData(bars: OHLCVBar[], field: 'ma_20' | 'ema_20') {
  return bars
    .filter(b => b[field] !== null && b[field] !== undefined)
    .map(b => ({
      time: (b.timestamp / 1000) as UTCTimestamp,
      value: b[field] as number,
    }));
}

export class IndicatorOverlay {
  private controller: ChartController;
  private maSeries: ISeriesApi<'Line'> | null = null;
  private emaSeries: ISeriesApi<'Line'> | null = null;
  private maVisible = false;
  private emaVisible = false;
  private currentBars: OHLCVBar[] = [];

  constructor(controller: ChartController) {
    this.controller = controller;
  }

  init(): void {
    const chart = this.controller.getChart();
    if (!chart) return;

    this.maSeries = chart.addSeries(LineSeries, {
      color: '#2f81f7',         // --prim-blue-500
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    this.emaSeries = chart.addSeries(LineSeries, {
      color: '#d29922',         // --prim-yellow-500
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    // Initially hidden: set empty data
    this.maSeries.setData([]);
    this.emaSeries.setData([]);
  }

  update(bars: OHLCVBar[]): void {
    this.currentBars = bars;
    if (this.maVisible)  this._renderMa(bars);
    if (this.emaVisible) this._renderEma(bars);
  }

  setMa20Visible(visible: boolean): void {
    this.maVisible = visible;
    if (visible) {
      this._renderMa(this.currentBars);
    } else {
      this.maSeries?.setData([]);
    }
  }

  setEma20Visible(visible: boolean): void {
    this.emaVisible = visible;
    if (visible) {
      this._renderEma(this.currentBars);
    } else {
      this.emaSeries?.setData([]);
    }
  }

  private _renderMa(bars: OHLCVBar[]): void {
    if (!this.maSeries) return;
    this.maSeries.setData(buildLineData(bars, 'ma_20'));
  }

  private _renderEma(bars: OHLCVBar[]): void {
    if (!this.emaSeries) return;
    this.emaSeries.setData(buildLineData(bars, 'ema_20'));
  }

  destroy(): void {
    const chart = this.controller.getChart();
    if (chart && this.maSeries)  chart.removeSeries(this.maSeries);
    if (chart && this.emaSeries) chart.removeSeries(this.emaSeries);
    this.maSeries  = null;
    this.emaSeries = null;
  }
}
```

### ChartController additions (diff từ Story 2.3)

```typescript
// Thêm method vào ChartController:
getChart(): IChartApi | undefined {
  return this.chart;
}
```

`IndicatorOverlay` cần `chart` instance để gọi `chart.addSeries()` và `chart.removeSeries()`. ChartController expose `getChart()` (không phải public field) để giữ encapsulation.

### Cập nhật EventMap['chart:dataLoaded']

```typescript
// Trong frontend/types.ts — cập nhật EventMap:
'chart:dataLoaded': { barCount: number; bars: OHLCVBar[] };
```

**Backward compat:** Story 2.2 (`main.ts`) lắng nghe `chart:dataLoaded` để update status bar bằng `barCount`. Với thay đổi này, payload giờ có thêm `bars` field. Vì TypeScript, phải cập nhật tất cả listeners để nhận cả `bars`.

Trong `main.ts`: subscriber cũ `({ barCount }) => ...` phải đổi thành `({ barCount, bars }) => ...`.

### ChartController emit update (eventBus)

```typescript
// Trong ChartController._renderBars() hoặc sau successful loadData():
// Thay vì:
eventBus.emit('chart:dataLoaded', { barCount: bars.length });
// Thành:
eventBus.emit('chart:dataLoaded', { barCount: bars.length, bars });
```

**Lưu ý:** `bars` ở đây là `OHLCVBar[]` từ cache, bao gồm `ma_20`/`ema_20` fields từ API response.

### Cập nhật OHLCVBar trong types.ts

```typescript
// Trước (Story 2.1):
export interface OHLCVBar {
  timestamp: number;  // Unix ms int64 (ADR-03)
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// Sau (Story 2.4):
export interface OHLCVBar {
  timestamp: number;  // Unix ms int64 (ADR-03)
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma_20: number | null;    // ← THÊM MỚI — null cho warm-up bars (index 0–18)
  ema_20: number | null;   // ← THÊM MỚI — null cho warm-up bars (index 0–18)
}
```

**Tại sao null thay vì undefined:** API response JSON dùng `null` cho missing values, TypeScript JSON.parse không phân biệt undefined/null. Dùng `null` để match API contract.

### main.ts wiring pattern

```typescript
// Thêm import
import { IndicatorOverlay } from './IndicatorOverlay';

// Trong init():
let indicatorOverlay: IndicatorOverlay;

// Sau chartController.init() và hoverTooltip.init():
indicatorOverlay = new IndicatorOverlay(chartController);
indicatorOverlay.init();  // Phải sau chartController.init() vì cần getChart()

// Subscribe chart:dataLoaded → update indicators
eventBus.on('chart:dataLoaded', ({ barCount, bars }) => {
  const statusInfo = document.getElementById('status-data-info');
  if (statusInfo) statusInfo.textContent = `${barCount.toLocaleString()} bars`;
  indicatorOverlay.update(bars);
});

// Toolbar toggles
const toggleMa20 = document.getElementById('toggle-ma20') as HTMLInputElement | null;
const toggleEma20 = document.getElementById('toggle-ema20') as HTMLInputElement | null;

function handleIndicatorToggle(field: 'ma20' | 'ema20', checked: boolean): void {
  if (field === 'ma20') indicatorOverlay.setMa20Visible(checked);
  else                  indicatorOverlay.setEma20Visible(checked);

  // AC #7: warn if too few bars
  if (checked && chartController.hasData()) {
    const bars = chartController.getCachedBars();  // cần thêm method này
    if (bars && bars.length < 20) {
      toastManager.show('Date range quá ngắn cho MA/EMA period (cần ≥ 20 bars)', 'warning');
    }
  }
}

toggleMa20?.addEventListener('change', (e) => {
  handleIndicatorToggle('ma20', (e.target as HTMLInputElement).checked);
});
toggleEma20?.addEventListener('change', (e) => {
  handleIndicatorToggle('ema20', (e.target as HTMLInputElement).checked);
});
```

### ChartController — thêm `getCachedBars()`

```typescript
// Thêm method vào ChartController:
getCachedBars(): OHLCVBar[] | null {
  return this.cache?.data ?? null;
}
```

Cần để `main.ts` kiểm tra số bars cho warning AC #7 mà không cần duplicate state.

### HTML — toolbar toggles

```html
<!-- Trong toolbar div của index.html, sau date inputs -->
<label class="indicator-toggle" for="toggle-ma20">
  <input type="checkbox" id="toggle-ma20">
  <span class="indicator-toggle-swatch indicator-toggle-swatch--ma"></span>
  MA20
</label>
<label class="indicator-toggle" for="toggle-ema20">
  <input type="checkbox" id="toggle-ema20">
  <span class="indicator-toggle-swatch indicator-toggle-swatch--ema"></span>
  EMA20
</label>
```

### CSS — indicator toggles

```css
/* Trong @layer components */
.indicator-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-family: var(--font-ui);
  font-size: 13px;            /* --type-ui-md */
  color: var(--sem-text-secondary);
  user-select: none;
}

.indicator-toggle:has(input:checked) {
  color: var(--sem-text-primary);
}

.indicator-toggle-swatch {
  display: inline-block;
  width: 12px;
  height: 3px;
  border-radius: 2px;
  flex-shrink: 0;
}

.indicator-toggle-swatch--ma  { background: var(--prim-blue-500); }
.indicator-toggle-swatch--ema { background: var(--prim-yellow-500); }
```

### API Response — ma_20/ema_20 fields

Backend đã tính toán MA/EMA trong `backend/services/indicators.py` và trả về cùng với bars:
```json
{
  "timestamp": 1710489600000,
  "open": 68000.0,
  "high": 68500.0,
  "low": 67800.0,
  "close": 68200.0,
  "volume": 1234.5,
  "ma_20": 67800.5,   ← null nếu index < 19
  "ema_20": 67950.3   ← null nếu index < 19
}
```

Story này chỉ là **frontend** — không cần thay đổi backend. Backend đã có `ma_20`/`ema_20` từ `indicators.py` (ADR-07).

**Nếu backend chưa có:** Kiểm tra `backend/routes/ohlcv.py` — nếu `ma_20`/`ema_20` không có trong response, story này sẽ hoạt động với null values (overlay không render). Không cần unblock vì series chỉ là `[]`.

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/types.ts` | Thêm `ma_20`/`ema_20` vào `OHLCVBar`, thêm `bars` vào `EventMap['chart:dataLoaded']`, thêm `IndicatorToggleState` |
| `frontend/ChartController.ts` | Thêm `getChart()`, `getCachedBars()`, update `eventBus.emit('chart:dataLoaded')` để include `bars` |
| `frontend/main.ts` | Import + init `IndicatorOverlay`, wire toggles, update `chart:dataLoaded` handler |
| `static/index.html` | Thêm MA20/EMA20 toggle elements vào toolbar |
| `static/style.css` | Thêm `.indicator-toggle` và `.indicator-toggle-swatch` CSS |

### Files cần tạo mới

| File | Nội dung |
|------|----------|
| `frontend/IndicatorOverlay.ts` | Manages LineSeries cho MA/EMA, null-filter, show/hide |

### Files KHÔNG được touch

- `backend/` — story này chỉ là frontend (backend đã có indicators)
- `frontend/EventBus.ts` — không thay đổi
- `frontend/HoverTooltip.ts` — không liên quan
- `frontend/SettingsManager.ts`, `frontend/ToastManager.ts` — ToastManager được dùng (via import) nhưng không modify

### Dependency order trong story

1. **types.ts** — update `OHLCVBar` + `EventMap['chart:dataLoaded']`
2. **ChartController.ts** — thêm `getChart()`, `getCachedBars()`, update emit
3. **IndicatorOverlay.ts** — tạo mới, import ChartController + types
4. **main.ts** — import IndicatorOverlay, wire events + toggles
5. **index.html** — thêm toggle HTML
6. **style.css** — thêm toggle CSS

### Lưu ý về LW Charts v5 removeSeries

```typescript
// v5: chart.removeSeries(series) — cần lưu reference để remove sau
// KHÔNG thể remove bằng type string như v4
// Do đó IndicatorOverlay giữ this.maSeries và this.emaSeries references

// Khi destroy():
chart.removeSeries(this.maSeries);   // OK
chart.removeSeries(this.emaSeries);  // OK
```

### Edge case — toggle ON trước khi data load

Nếu trader bật MA20 trước khi data được load (empty state):
- `this.currentBars = []` → `buildLineData([], 'ma_20')` → `[]` → `setData([])` → empty series (safe)
- Không crash, không warning (AC #8)
- Khi data load xong: `indicatorOverlay.update(bars)` được gọi qua `chart:dataLoaded` event → MA20 render đúng

### References

- FR (MA/EMA toggle): epics-phase1.md → Story 2.5, lines 642–656
- ADR-07: pandas built-in EMA, slice-first — architecture.md line 232
- ADR-13: LRU-1 cache — architecture.md line 393 (`data: OHLCVBar[]` includes `ma_20`/`ema_20`)
- Architecture API response: architecture.md lines 1334–1357 (ma_20/ema_20 fields)
- UX: Indicators OFF by default — ux-design-specification.md line 66
- Color tokens: `--prim-blue-500: #2f81f7`, `--prim-yellow-500: #d29922` — ux-design-specification.md line 443–446
- Previous story: `_bmad-output/implementation-artifacts/p1-2-3-ohlcv-hover-tooltip.md`

## Dev Agent Record

### Agent Model Used

mimo-v2.5-pro

### Debug Log References

- Build: 290.2kb, esbuild 43ms
- Typecheck: passed (tsc --noEmit)

### Completion Notes List

- All 6 tasks completed
- `IndicatorOverlay` class created with null-filtering for warm-up bars
- `ChartController.eventBus.emit` updated to include `bars` in payload (cache hit + fetch success paths)
- `main.ts` wires IndicatorOverlay init, toggle handlers with < 20 bars warning
- Toggle CSS uses `@layer components` with color swatches (#2f81f7 MA, #d29922 EMA)
- HTML toggles added to toolbar after Load button
- `getCachedBars()` added to ChartController for warning check without duplicate state

### File List

- `frontend/types.ts` — updated OHLCVBar (ma_20/ema_20), EventMap, added IndicatorToggleState, PersistedSettings, LoadDataResult
- `frontend/ChartController.ts` — added getChart(), getCachedBars(), updated eventBus.emit calls to include bars
- `frontend/IndicatorOverlay.ts` — new file, manages LineSeries for MA/EMA
- `frontend/main.ts` — imported IndicatorOverlay, init + toggle wiring + data propagation
- `static/style.css` — added .indicator-toggle CSS in @layer components
- `static/index.html` — added MA20/EMA20 toggle labels in toolbar
