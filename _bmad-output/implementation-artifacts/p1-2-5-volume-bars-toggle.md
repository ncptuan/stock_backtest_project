# Story P1-2.5: Volume Bars Toggle

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (4)

1. **`init()` no idempotency guard — leaks orphaned HistogramSeries** — HIGH (Blind + Edge Case)
   - Added `if (this.series) return;` guard at top of `init()`
   - File: `VolumeOverlay.ts`

2. **`buildVolumeData` no NaN/Infinity guard on volume** — HIGH (Blind + Edge Case)
   - Added `Number.isFinite(b.volume)` to filter chain to prevent NaN/Infinity from crashing LW Charts
   - File: `VolumeOverlay.ts`

3. **`buildVolumeData` no timestamp dedup — LW Charts crashes on duplicates** — HIGH (Edge Case)
   - Added `Set<number>` dedup with `Math.round(b.timestamp / 1000)`, matching ChartController pattern
   - File: `VolumeOverlay.ts`

4. **Volume not cleared on `loadData()` failure** — MED (all 3 agents)
   - Added `volumeOverlay.update([])` alongside `indicatorOverlay.update([])` in failure path
   - File: `main.ts`

### All 6 ACs: FULLY MET (Acceptance Auditor)

### Deferred

- Scale margins always allocated (bottom 20%) — LW Charts hides empty scales automatically, defer
- `currentBars` shared reference — `_renderBars` copies via `[...bars]`, defer
- `destroy()` gaps — single-user app, page unload cleans up, defer
- Hardcoded rgba colors — LW Charts JS API doesn't support CSS variables, defer
- Toggle state not persisted — intentional per scope, defer
- Timestamp rounding mismatch — Binance timestamps are whole-second ms multiples, defer

## Story

As a trader,
I want to optionally show volume bars at the bottom of the chart,
So that I can see volume context without the visual noise when I don't need it.

## Acceptance Criteria

1. **Given** app load lần đầu
   **When** chart render
   **Then** volume bars OFF — không có histogram nào trên chart
   **And** toolbar checkbox `#toggle-volume` ở trạng thái unchecked

2. **Given** chart đang hiển thị với data
   **When** trader bật `#toggle-volume`
   **Then** volume histogram xuất hiện ở phần dưới chart, chiếm ~20% chiều cao chart area
   **And** bullish bars (close ≥ open) màu xanh `rgba(63, 185, 80, 0.5)` (semi-transparent `--prim-green-500`)
   **And** bearish bars (close < open) màu đỏ `rgba(248, 81, 73, 0.5)` (semi-transparent `--prim-red-500`)

3. **Given** volume bars đang ON
   **When** trader tắt toggle
   **Then** volume histogram biến mất khỏi chart ngay lập tức

4. **Given** volume bars đang ON và chart reload (timeframe đổi, date range đổi)
   **When** `ChartController.loadData()` hoàn thành
   **Then** volume histogram tự động re-render với data mới
   **And** toggle state giữ nguyên (không bị reset về OFF)

5. **Given** chart chưa có data (empty state)
   **When** trader bật volume toggle
   **Then** không crash — toggle state được lưu, volume sẽ render khi data được load

6. **Given** volume bars đang ON
   **When** trader hover lên chart
   **Then** volume bars không interfere với OHLCV tooltip (HoverTooltip vẫn hoạt động bình thường)

## Tasks / Subtasks

- [x] Task 1: Tạo `frontend/VolumeOverlay.ts` — Manages HistogramSeries (AC: #1–#6)
  - [x] Class `VolumeOverlay` nhận `(chartController: ChartController)`
  - [x] `init()`: tạo 1 `HistogramSeries` với LW Charts v5 API + `priceScaleId: 'volume'`, scale margins top 0.8
  - [x] `setVisible(visible: boolean)`: show/hide bằng cách setData([]) khi hide
  - [x] `update(bars: OHLCVBar[])`: re-render khi visible và data mới
  - [x] `destroy()`: `chart.removeSeries(series)`

- [x] Task 2: Cập nhật `frontend/main.ts` — Wire toolbar toggle + VolumeOverlay (AC: #1–#5)
  - [x] Import + init `VolumeOverlay` sau `ChartController.init()`
  - [x] Subscribe `chart:dataLoaded` → `volumeOverlay.update(bars)` (cùng event đã có từ Story 2.4)
  - [x] `#toggle-volume` change → `volumeOverlay.setVisible(checked)`

- [x] Task 3: Cập nhật `static/index.html` — Thêm volume toggle vào toolbar (AC: #1)
  - [x] `<label><input type="checkbox" id="toggle-volume"> Vol</label>` sau MA/EMA toggles

- [x] Task 4: Cập nhật `static/style.css` — Swatch màu cho volume toggle (AC: #2)
  - [x] `.indicator-toggle-swatch--volume` với gradient green+red (dùng class đã có từ Story 2.4)

## Dev Notes

### LW Charts v5 — HistogramSeries API

```typescript
// Import cần thêm vào VolumeOverlay.ts
import {
  HistogramSeries,      // v5 series type constant
  ISeriesApi,
  UTCTimestamp,
} from 'lightweight-charts';

// CRITICAL — v5: dùng addSeries(HistogramSeries, opts) KHÔNG phải addHistogramSeries()
const volumeSeries = chart.addSeries(HistogramSeries, {
  priceFormat: { type: 'volume' },
  priceScaleId: 'volume',      // separate price scale, không conflict với candlestick scale
  lastValueVisible: false,
  priceLineVisible: false,
});

// Scale margins: volume chiếm bottom 20% của chart area
volumeSeries.priceScale().applyOptions({
  scaleMargins: {
    top: 0.8,     // volume chỉ dùng bottom 20%
    bottom: 0,
  },
});
```

### HistogramData format (LW Charts v5)

```typescript
interface HistogramData {
  time: UTCTimestamp;
  value: number;
  color?: string;  // per-bar color override
}
```

Color-coding per bar (xác định bull/bear tại render time):
```typescript
function buildVolumeData(bars: OHLCVBar[]): HistogramData[] {
  return bars.map(b => ({
    time: (b.timestamp / 1000) as UTCTimestamp,
    value: b.volume,
    color: b.close >= b.open
      ? 'rgba(63, 185, 80, 0.5)'    // bull: green semi-transparent
      : 'rgba(248, 81, 73, 0.5)',   // bear: red semi-transparent
  }));
}
```

**Không có null handling:** Volume luôn có giá trị (không có warm-up period như MA/EMA). Mọi bar đều có `volume > 0`.

### VolumeOverlay implementation

```typescript
// frontend/VolumeOverlay.ts
import { HistogramSeries, ISeriesApi, UTCTimestamp } from 'lightweight-charts';
import type { ChartController } from './ChartController';
import type { OHLCVBar } from './types';

interface HistogramData {
  time: UTCTimestamp;
  value: number;
  color: string;
}

function buildVolumeData(bars: OHLCVBar[]): HistogramData[] {
  return bars.map(b => ({
    time: (b.timestamp / 1000) as UTCTimestamp,
    value: b.volume,
    color: b.close >= b.open
      ? 'rgba(63, 185, 80, 0.5)'    // --prim-green-500 semi-transparent
      : 'rgba(248, 81, 73, 0.5)',   // --prim-red-500 semi-transparent
  }));
}

export class VolumeOverlay {
  private controller: ChartController;
  private series: ISeriesApi<'Histogram'> | null = null;
  private visible = false;
  private currentBars: OHLCVBar[] = [];

  constructor(controller: ChartController) {
    this.controller = controller;
  }

  init(): void {
    const chart = this.controller.getChart();
    if (!chart) return;

    this.series = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
      lastValueVisible: false,
      priceLineVisible: false,
    });

    // Volume chiếm bottom 20% của chart pane
    this.series.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    // Initially hidden
    this.series.setData([]);
  }

  update(bars: OHLCVBar[]): void {
    this.currentBars = bars;
    if (this.visible) this._render(bars);
  }

  setVisible(visible: boolean): void {
    this.visible = visible;
    if (visible) {
      this._render(this.currentBars);
    } else {
      this.series?.setData([]);
    }
  }

  private _render(bars: OHLCVBar[]): void {
    if (!this.series) return;
    this.series.setData(buildVolumeData(bars));
  }

  destroy(): void {
    const chart = this.controller.getChart();
    if (chart && this.series) chart.removeSeries(this.series);
    this.series = null;
  }
}
```

### main.ts wiring

```typescript
// Thêm import
import { VolumeOverlay } from './VolumeOverlay';

// Trong init(), sau indicatorOverlay.init():
const volumeOverlay = new VolumeOverlay(chartController);
volumeOverlay.init();

// chart:dataLoaded subscriber đã có từ Story 2.4 — thêm volumeOverlay vào cùng handler:
eventBus.on('chart:dataLoaded', ({ barCount, bars }) => {
  const statusInfo = document.getElementById('status-data-info');
  if (statusInfo) statusInfo.textContent = `${barCount.toLocaleString()} bars`;
  indicatorOverlay.update(bars);
  volumeOverlay.update(bars);     // ← THÊM dòng này
});

// Volume toggle
const toggleVolume = document.getElementById('toggle-volume') as HTMLInputElement | null;
toggleVolume?.addEventListener('change', (e) => {
  volumeOverlay.setVisible((e.target as HTMLInputElement).checked);
});
```

### index.html — volume toggle HTML

```html
<!-- Trong toolbar div, sau #toggle-ema20 label -->
<label class="indicator-toggle" for="toggle-volume">
  <input type="checkbox" id="toggle-volume">
  <span class="indicator-toggle-swatch indicator-toggle-swatch--volume"></span>
  Vol
</label>
```

### CSS — volume swatch

```css
/* Trong @layer components — thêm sau class đã có từ Story 2.4 */
.indicator-toggle-swatch--volume {
  /* Gradient green→red để biểu thị bull/bear bars */
  background: linear-gradient(
    to right,
    rgba(63, 185, 80, 0.7) 50%,
    rgba(248, 81, 73, 0.7) 50%
  );
}
```

### Quan hệ với Story 2.4 (IndicatorOverlay)

Story này **không** sửa `IndicatorOverlay.ts`. Pattern giống nhau nhưng tách thành class riêng vì:
- Volume dùng `HistogramSeries`, không phải `LineSeries`
- Volume không có null warm-up values
- Volume có per-bar color (bull/bear) thay vì single line color
- Scale riêng (`priceScaleId: 'volume'`)

`getChart()` và `getCachedBars()` đã được thêm vào `ChartController` trong Story 2.4 — VolumeOverlay tận dụng ngay.

`EventMap['chart:dataLoaded']` đã được update để include `bars: OHLCVBar[]` trong Story 2.4 — VolumeOverlay nhận bars qua cùng event.

### Về priceScaleId: 'volume'

Khi dùng `priceScaleId: 'volume'`:
- LW Charts tạo separate price scale riêng cho volume (axis không hiển thị vì `lastValueVisible: false`)
- Scale không bị mixed với candlestick price scale — volume bars không làm distort price axis
- `scaleMargins: { top: 0.8 }` đảm bảo volume chỉ chiếm 20% bottom của cùng pane

**Không dùng `priceScaleId: ''`** (overlay scale): sẽ share scale với candlestick — volume values (1000+ BTC) sẽ override và distort price axis.

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/main.ts` | Import + init `VolumeOverlay`, thêm vào `chart:dataLoaded` handler, wire `#toggle-volume` |
| `static/index.html` | Thêm `#toggle-volume` label/checkbox trong toolbar |
| `static/style.css` | Thêm `.indicator-toggle-swatch--volume` CSS |

### Files cần tạo mới

| File | Nội dung |
|------|----------|
| `frontend/VolumeOverlay.ts` | `HistogramSeries` management, bull/bear color per bar, scale margins |

### Files KHÔNG được touch

- `frontend/types.ts` — không cần type mới (OHLCVBar đã có `volume`, `HistogramData` định nghĩa inline)
- `frontend/ChartController.ts` — đã có `getChart()` từ Story 2.4, không cần thêm
- `frontend/IndicatorOverlay.ts` — scope Story 2.4
- `backend/` — story này chỉ là frontend

### Dependency order trong story

1. **VolumeOverlay.ts** — tạo mới, cần `ChartController.getChart()` (đã có từ Story 2.4)
2. **main.ts** — import VolumeOverlay, thêm vào chart:dataLoaded handler
3. **index.html** — thêm toggle HTML
4. **style.css** — thêm swatch CSS

### Lưu ý — init order trong main.ts

```typescript
// Thứ tự PHẢI là:
chartController.init(container);     // 1. chart + series created
hoverTooltip.init();                  // 2. crosshair subscribe
indicatorOverlay.init();             // 3. LineSeries added
volumeOverlay.init();                // 4. HistogramSeries added — PHẢI sau chartController.init()
```

`VolumeOverlay.init()` gọi `chart.addSeries()` — cần `chart` đã tồn tại. Tất cả `.init()` đều synchronous.

### References

- UX-DR19: Volume bars OFF by default, 1-click toolbar toggle — epics-phase1.md line 137
- UX decision: Volume default OFF + 1-click toggle — ux-design-specification.md line 367
- Color tokens: `--prim-green-500: #3fb950`, `--prim-red-500: #f85149` — ux-design-specification.md lines 752–753
- Pattern từ Story 2.4: `_bmad-output/implementation-artifacts/p1-2-4-ma-ema-overlay-toggle.md`
- `getChart()` method đã có từ Story 2.4 trong `ChartController.ts`
- `EventMap['chart:dataLoaded']` với `bars: OHLCVBar[]` đã có từ Story 2.4

## Dev Agent Record

### Agent Model Used

mimo-v2.5-pro

### Debug Log References

- Build: 295.0kb, esbuild 42ms
- Typecheck: passed (tsc --noEmit)

### Completion Notes List

- All 4 tasks completed
- `VolumeOverlay` class created with HistogramSeries, bull/bear per-bar color, priceScaleId 'volume' with scaleMargins top 0.8
- main.ts wires VolumeOverlay init after IndicatorOverlay, toggle handler, update in doLoad
- Volume swatch uses green/red gradient to indicate bull/bear bars
- Pattern follows IndicatorOverlay from Story 2.4 exactly

### File List

- `frontend/VolumeOverlay.ts` — new file, HistogramSeries management with bull/bear color
- `frontend/main.ts` — imported VolumeOverlay, init + toggle wiring + data propagation
- `static/index.html` — added #toggle-volume label in toolbar
- `static/style.css` — added .indicator-toggle-swatch--volume gradient CSS
