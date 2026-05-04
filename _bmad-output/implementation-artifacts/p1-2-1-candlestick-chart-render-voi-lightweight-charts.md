# Story P1-2.1: CSS Design Token System + App Layout + Candlestick Chart Render

Status: done

## Story

As a trader,
I want to see a professional dark-theme candlestick chart loaded from the backend,
So that I can visually analyze OHLCV price data and the app has a solid visual foundation for all future features.

## Acceptance Criteria

1. **Given** app load sau khi data đã được fetch (Parquet cache tồn tại)
   **When** frontend init
   **Then** `ChartController` khởi tạo Lightweight Charts v5 trên `<div id="chart-container">`
   **And** gọi `GET /api/ohlcv?symbol=BTC/USDT&timeframe=4h&date_start=...&date_end=...`
   **And** chart render candlestick series với đúng OHLCV values
   **And** render hoàn tất trong < 2 giây

2. **Given** chart đã render
   **When** user nhìn vào time axis
   **Then** timestamp UTC được hiển thị theo UTC+7 (timezone offset +07:00)
   **And** nến bullish (close >= open) hiển thị màu xanh `#3fb950`
   **And** nến bearish (close < open) hiển thị màu đỏ `#f85149`
   **And** chart auto-resize khi window resize — `width: 100%` container

3. **Given** `GET /api/ohlcv` trả về 404 hoặc error
   **When** `ChartController.loadData()` nhận lỗi
   **Then** chart không crash — hiển thị empty state placeholder (text "Chưa có data — fetch trước")
   **And** `console.error(message)` để dev có thể debug
   **And** `has_data` còn là `false` → nút Play vẫn disabled

4. **Given** data đã được load thành công
   **When** `ChartController.loadData()` hoàn thành
   **Then** emit event `'chart:dataLoaded'` với payload `{ barCount: number }`
   **And** `chartController.hasData()` trả về `true`
   **And** LRU-1 cache lưu `{symbol, timeframe, data}` — call tiếp theo với cùng params không re-fetch API

5. **Given** `loadData()` được gọi với cùng (symbol, timeframe) — LRU-1 hit
   **When** ChartController check cache
   **Then** không gọi API (không có fetch network request)
   **And** chart re-render từ cache data ngay lập tức

6. **Given** `loadData()` được gọi với (symbol, timeframe) khác — LRU-1 miss
   **When** ChartController evict cache
   **Then** cache cũ bị xóa TRƯỚC khi fetch mới để tránh memory bloat
   **And** fetch API mới, update LRU-1, re-render chart

7. **Given** app load với Phase 1 layout
   **When** browser render `index.html`
   **Then** layout có chart area chiếm ≥ 70% viewport width
   **And** results panel placeholder ở bên phải, max-width 400px
   **And** toolbar ở trên cùng với các field: symbol, timeframe selector (5m/30m/1h/4h/1D), date range
   **And** `min-width: 1024px` cho `body`
   **And** nền dark — `--sem-bg-app: #0d1117`

8. **Given** `style.css`
   **When** parse CSS
   **Then** có `@layer reset, tokens, components, utilities;` declaration
   **And** CSS custom properties được định nghĩa trong `@layer tokens`
   **And** tokens: `--prim-gray-*` (màu primitive), `--sem-bg-*`, `--sem-text-*`, `--sem-anim-*`, `--sem-candle-bull`, `--sem-candle-bear`
   **And** không có literal hex/px ngoài `:root` trong `@layer tokens` (dùng CSS variables ở mọi nơi khác)

## Tasks / Subtasks

- [x] Task 1: Cập nhật `frontend/types.ts` — thêm Phase 1 types còn thiếu (AC: #3, #4)
  - [x] Add `ma_20: number | null` và `ema_20: number | null` vào `OHLCVBar` interface
  - [x] Add vào `EventMap`: `'chart:ready': {}` và `'chart:dataLoaded': { barCount: number }`
  - [x] Add `OHLCVApiResponse` interface (matches actual backend response shape — xem Dev Notes)
  - [x] Add `DateRange` interface: `{ dateStart: string; dateEnd: string }` (dùng bởi ChartController)

- [x] Task 2: Cập nhật `static/style.css` — CSS Design Token System (AC: #7, #8)
  - [x] Thêm `@layer reset, tokens, components, utilities;` ở đầu file (trước mọi CSS hiện tại)
  - [x] Wrap các CSS custom properties vào `@layer tokens { :root { ... } }`
  - [x] Bổ sung tokens còn thiếu theo spec (xem Dev Notes — full token list)
  - [x] Thêm Phase 1 app layout CSS vào `@layer components` (xem Dev Notes)
  - [x] Giữ nguyên Phase 2 styles (ExportPreview, SessionListPanel, v.v.) — chỉ additive

- [x] Task 3: Cập nhật `static/index.html` — Phase 1 layout structure (AC: #7)
  - [x] Xóa `<style>` inline blocks trong `<head>` — move vào `static/style.css` nếu chưa có
  - [x] Cập nhật `<body>` với Phase 1 layout HTML (xem Dev Notes — full HTML skeleton)
  - [x] Giữ Phase 2 overlay elements (SessionListPanel, ExportPreview) vẫn trong DOM — chúng mount qua JS
  - [x] **Xóa Jinja2 hack**: `{{ supabase_enabled }}` — thay bằng `false` hardcoded (Phase 2 sẽ re-add khi cần)

- [x] Task 4: Tạo `frontend/ChartController.ts` (AC: #1–#6)
  - [x] Class `ChartController` với LW Charts v5 API
  - [x] `init(container: HTMLElement): void` — tạo chart, add candlestick series, emit `'chart:ready'`
  - [x] `loadData(symbol: string, timeframe: string, dateRange: DateRange): Promise<void>` — fetch API, LRU-1 check
  - [x] `hasData(): boolean`
  - [x] `revealBar(upToIndex: number): void` — dùng bởi ReplayEngine (Epic P1-4), chuẩn bị stub
  - [x] Xem Dev Notes cho implementation details quan trọng (v5 API, timestamp handling, UTC+7)

- [x] Task 5: Tạo `frontend/main.ts` — Minimal entry point (AC: #1, #3)
  - [x] Init `ChartController` với `document.getElementById('chart-container')`
  - [x] Load settings từ `localStorage` (default: symbol=`BTC/USDT`, timeframe=`4h`, dateStart/End cho 6 tháng gần nhất)
  - [x] Gọi `chartController.loadData(symbol, timeframe, dateRange)` khi DOM ready
  - [x] Chưa wire DrawingManager, ReplayEngine (chưa tồn tại — Epic P1-3, P1-4 scope)

## Dev Notes

### LW Charts v5 — Breaking Changes (CRITICAL)

**⚠️ v5 API khác v4 hoàn toàn — KHÔNG copy từ tutorials v4 hoặc Stack Overflow cũ:**

```typescript
// ❌ v4 API — KHÔNG dùng
const series = chart.addCandlestickSeries({ ... });

// ✅ v5 API — ĐÚNG
import { createChart, CandlestickSeries } from 'lightweight-charts';
const series = chart.addSeries(CandlestickSeries, { ... });
```

**Timestamp handling — LW Charts expects SECONDS, backend sends MILLISECONDS:**
```typescript
// Backend trả về timestamp ms (ADR-03: int64 Unix ms)
// LW Charts v5 time field: UTCTimestamp (seconds) hoặc string date
// → Phải chia cho 1000 khi gán data

series.setData(bars.map(b => ({
  time: (b.timestamp / 1000) as UTCTimestamp,
  open: b.open,
  high: b.high,
  low: b.low,
  close: b.close,
})));
```

**UTC+7 display — dùng `localization.timeFormatter`:**
```typescript
const OFFSET_MS = 7 * 60 * 60 * 1000; // UTC+7

const chart = createChart(container, {
  layout: {
    background: { color: '#0d1117' },
    textColor: '#e6edf3',
  },
  localization: {
    timeFormatter: (timestamp: number): string => {
      // timestamp here is in seconds (LW Charts convention)
      const date = new Date((timestamp + 7 * 3600) * 1000);
      return date.toISOString().replace('T', ' ').slice(0, 16); // "2024-01-15 08:00"
    },
  },
  grid: {
    vertLines: { color: '#21262d' },
    horzLines: { color: '#21262d' },
  },
  timeScale: {
    timeVisible: true,
    secondsVisible: false,
  },
});
```

**Candlestick series colors:**
```typescript
const series = chart.addSeries(CandlestickSeries, {
  upColor: '#3fb950',        // var(--sem-candle-bull)
  downColor: '#f85149',      // var(--sem-candle-bear)
  borderUpColor: '#3fb950',
  borderDownColor: '#f85149',
  wickUpColor: '#3fb950',
  wickDownColor: '#f85149',
});
```

**Auto-resize:**
```typescript
const resizeObserver = new ResizeObserver(entries => {
  for (const entry of entries) {
    chart.applyOptions({
      width: entry.contentRect.width,
      height: entry.contentRect.height,
    });
  }
});
resizeObserver.observe(container);
```

### ChartController implementation

```typescript
// frontend/ChartController.ts
import {
  createChart,
  CandlestickSeries,
  IChartApi,
  ISeriesApi,
  UTCTimestamp,
} from 'lightweight-charts';
import { eventBus } from './EventBus';
import type { OHLCVBar, OHLCVApiResponse, DateRange } from './types';

interface LRU1Cache {
  symbol: string;
  timeframe: string;
  data: OHLCVBar[];
}

export class ChartController {
  private chart: IChartApi | undefined;
  private series: ISeriesApi<'Candlestick'> | undefined;
  private cache: LRU1Cache | null = null;  // LRU-1: null = empty, LRU-1 = 1 slot
  private resizeObserver: ResizeObserver | undefined;

  init(container: HTMLElement): void {
    this.chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: {
        background: { color: '#0d1117' },
        textColor: '#e6edf3',
      },
      grid: {
        vertLines: { color: '#21262d' },
        horzLines: { color: '#21262d' },
      },
      localization: {
        timeFormatter: (timestamp: number): string => {
          const date = new Date((timestamp + 7 * 3600) * 1000);
          return date.toISOString().replace('T', ' ').slice(0, 16);
        },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
    });

    this.series = this.chart.addSeries(CandlestickSeries, {
      upColor: '#3fb950',
      downColor: '#f85149',
      borderUpColor: '#3fb950',
      borderDownColor: '#f85149',
      wickUpColor: '#3fb950',
      wickDownColor: '#f85149',
    });

    // Auto-resize
    this.resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        this.chart?.applyOptions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    this.resizeObserver.observe(container);

    eventBus.emit('chart:ready', {});
  }

  async loadData(symbol: string, timeframe: string, dateRange: DateRange): Promise<void> {
    // LRU-1 cache check
    if (
      this.cache &&
      this.cache.symbol === symbol &&
      this.cache.timeframe === timeframe
    ) {
      // Cache hit — re-render từ cache, không fetch API
      this._renderBars(this.cache.data);
      eventBus.emit('chart:dataLoaded', { barCount: this.cache.data.length });
      return;
    }

    // LRU-1 evict TRƯỚC khi fetch (tránh memory bloat)
    this.cache = null;

    const params = new URLSearchParams({
      symbol,
      timeframe,
      date_start: dateRange.dateStart,
      date_end: dateRange.dateEnd,
    });

    try {
      const res = await fetch(`/api/ohlcv?${params}`);
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const message = errData?.error?.message ?? `HTTP ${res.status}`;
        console.error(`[ChartController] loadData error: ${message}`);
        this._showEmptyState('Chưa có data — fetch trước');
        return;
      }

      const body: OHLCVApiResponse = await res.json();
      if (!body.data) {
        console.error('[ChartController] loadData: response data is null');
        this._showEmptyState('Chưa có data — fetch trước');
        return;
      }

      const bars = body.data;
      // LRU-1 save
      this.cache = { symbol, timeframe, data: bars };
      this._renderBars(bars);
      eventBus.emit('chart:dataLoaded', { barCount: bars.length });

    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      console.error(`[ChartController] loadData exception: ${message}`);
      this._showEmptyState('Chưa có data — fetch trước');
    }
  }

  hasData(): boolean {
    return this.cache !== null && this.cache.data.length > 0;
  }

  /** Được gọi bởi ReplayEngine trong Epic P1-4 để reveal bars up to index */
  revealBar(upToIndex: number): void {
    if (!this.cache || !this.series) return;
    const slice = this.cache.data.slice(0, upToIndex + 1);
    this._renderBars(slice);
  }

  private _renderBars(bars: OHLCVBar[]): void {
    if (!this.series) return;
    this.series.setData(
      bars.map(b => ({
        time: (b.timestamp / 1000) as UTCTimestamp,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }))
    );
  }

  private _showEmptyState(message: string): void {
    if (!this.series) return;
    this.series.setData([]);
    // TODO Epic P1-6: render empty state overlay message via OnboardingManager
    // For now, just log
    console.info(`[ChartController] ${message}`);
  }

  destroy(): void {
    this.resizeObserver?.disconnect();
    this.chart?.remove();
    this.chart = undefined;
    this.series = undefined;
    this.cache = null;
  }
}
```

### API Response format (actual — từ backend code)

`GET /api/ohlcv` trả về `OHLCVResponse` TRỰC TIẾP (không wrapped trong `APIResponse`):
```json
{
  "data": [
    {
      "timestamp": 1710489600000,
      "open": 68000.0, "high": 68500.0, "low": 67800.0, "close": 68200.0,
      "volume": 1234.5, "ema_20": null, "ma_20": null
    }
  ],
  "clipped": false,
  "actual_date_start": null,
  "actual_date_end": null
}
```

**Khi có lỗi (404, 422)** backend trả về `{error: {...}}` không có `data` field:
```json
{ "error": { "message": "...", "code": "no_cache", "retryable": false } }
```

TypeScript interface phù hợp:
```typescript
// frontend/types.ts — thêm vào
export interface OHLCVApiResponse {
  data: OHLCVBar[] | null;        // null khi error
  clipped?: boolean;
  actual_date_start?: string | null;
  actual_date_end?: string | null;
  has_gaps?: boolean;              // Story 1.5 sẽ add
  gaps?: GapInfo[];                // Story 1.5 sẽ add
  error?: {                        // present khi API trả về lỗi
    message: string;
    code: string;
    retryable: boolean;
  } | null;
}

export interface GapInfo {
  start_ts: number;
  end_ts: number;
  missing_bars: number;
}

export interface DateRange {
  dateStart: string;  // "YYYY-MM-DD"
  dateEnd: string;    // "YYYY-MM-DD"
}
```

**Note quan trọng:** Backend trả về `{"data": [...bars]}` và khi lỗi thì `{"error": {...}}` — hai shapes khác nhau. Frontend cần check `body.error` trước khi access `body.data`.

### CSS Design Token System

**Thêm vào đầu `static/style.css` (trước tất cả CSS hiện tại):**
```css
@layer reset, tokens, components, utilities;

@layer tokens {
  :root {
    /* === Primitive: Gray scale === */
    --prim-gray-950: #0a0f14;
    --prim-gray-900: #0d1117;
    --prim-gray-800: #161b22;
    --prim-gray-700: #21262d;
    --prim-gray-600: #30363d;
    --prim-gray-500: #484f58;
    --prim-gray-400: #8b949e;
    --prim-gray-200: #c9d1d9;
    --prim-gray-100: #e6edf3;

    /* === Semantic: Background === */
    --sem-bg-app:     var(--prim-gray-900);
    --sem-bg-panel:   var(--prim-gray-800);
    --sem-bg-surface: var(--prim-gray-700);
    --sem-border:     var(--prim-gray-600);

    /* === Semantic: Text === */
    --sem-text-primary: var(--prim-gray-100);
    --sem-text-muted:   var(--prim-gray-400);
    --sem-text-dim:     var(--prim-gray-500);

    /* === Semantic: Chart colors === */
    --sem-candle-bull: #3fb950;
    --sem-candle-bear: #f85149;

    /* === Semantic: Trade line colors === */
    --sem-entry: #3fb950;  /* Entry line — green */
    --sem-tp:    #4ea8de;  /* Take Profit line — blue */
    --sem-sl:    #f85149;  /* Stop Loss line — red */
    --sem-loss:  #f85149;

    /* === Semantic: Status colors === */
    --sem-win:     #3fb950;
    --sem-warning: #d29922;

    /* === Semantic: Animation === */
    --sem-anim-fast:   120ms;
    --sem-anim-normal: 200ms;
    --sem-anim-slow:   350ms;
  }
}
```

**Phase 1 App Layout — thêm vào `@layer components`:**
```css
@layer components {
  /* === App layout === */
  *, *::before, *::after { box-sizing: border-box; }

  html, body {
    margin: 0;
    padding: 0;
    height: 100%;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 14px;
    background: var(--sem-bg-app);
    color: var(--sem-text-primary);
    min-width: 1024px;
  }

  #app {
    display: flex;
    flex-direction: column;
    height: 100vh;
  }

  /* Toolbar */
  #toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 16px;
    background: var(--sem-bg-panel);
    border-bottom: 1px solid var(--sem-border);
    flex-shrink: 0;
  }

  /* Main content area */
  #app-content {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  /* Chart area */
  #chart-container {
    flex: 1;           /* chiếm tất cả space còn lại */
    min-width: 0;
    background: var(--sem-bg-app);
    position: relative;
  }

  /* Results panel */
  #results-panel {
    width: 30%;
    max-width: 400px;
    min-width: 240px;
    background: var(--sem-bg-panel);
    border-left: 1px solid var(--sem-border);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }

  /* Status bar */
  #status-bar {
    padding: 4px 16px;
    background: var(--sem-bg-panel);
    border-top: 1px solid var(--sem-border);
    font-size: 0.8rem;
    color: var(--sem-text-muted);
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
  }
}
```

### Phase 1 HTML Layout

**`static/index.html` cần được rewrite (giữ `<link>` và `<script>` cũ, thay `<body>`)**:
```html
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>BTC Replay</title>
  <link rel="stylesheet" href="/static/style.css" />
</head>
<body>
  <div id="app">
    <!-- Toolbar -->
    <div id="toolbar">
      <span id="toolbar-symbol" class="toolbar-label">BTC/USDT</span>
      <select id="toolbar-timeframe" class="toolbar-select">
        <option value="5m">5m</option>
        <option value="30m">30m</option>
        <option value="1h">1h</option>
        <option value="4h" selected>4h</option>
        <option value="1D">1D</option>
      </select>
      <input type="date" id="toolbar-date-start" class="toolbar-input" />
      <span class="toolbar-sep">→</span>
      <input type="date" id="toolbar-date-end" class="toolbar-input" />
      <button id="btn-load" class="btn-primary">Load</button>
      <!-- Placeholder cho fetch button (Story 1.2) và Play button (Story 4.1) -->
    </div>

    <!-- Main content -->
    <div id="app-content">
      <!-- Chart -->
      <div id="chart-container"></div>

      <!-- Results panel placeholder (Stories 5.3+) -->
      <div id="results-panel">
        <div id="results-panel-placeholder" style="padding:16px;color:var(--sem-text-muted);font-size:0.85rem;">
          Kết quả replay hiển thị ở đây
        </div>
      </div>
    </div>

    <!-- Status bar -->
    <div id="status-bar">
      <span id="status-mode">SETUP MODE</span>
      <span id="status-data-info"></span>
    </div>
  </div>

  <!-- Phase 2 overlay containers (mount via JS) -->
  <div id="session-list-root"></div>
  <div id="export-preview-root"></div>
  <div id="toast-root"></div>

  <script src="/static/app.js"></script>
</body>
</html>
```

**Lý do xóa `{{ supabase_enabled }}` Jinja2 hack:**
- Phase 2 code dùng `window.__SUPABASE_ENABLED__` để kiểm tra feature flag
- Hiện tại backend không serve index.html qua Jinja2 cho Phase 1 (static file server)
- Phase 2 feature flags sẽ được handle via env check trong JS khi cần

### main.ts — Minimal entry point

```typescript
// frontend/main.ts
import { ChartController } from './ChartController';
import type { DateRange } from './types';

// Default settings (Story 6.2 sẽ implement localStorage persistence)
const SYMBOL = 'BTC/USDT';
const DEFAULT_TIMEFRAME = '4h';

function getDefaultDateRange(): DateRange {
  const end = new Date();
  const start = new Date();
  start.setMonth(start.getMonth() - 6);
  const fmt = (d: Date) => d.toISOString().slice(0, 10); // YYYY-MM-DD
  return { dateStart: fmt(start), dateEnd: fmt(end) };
}

let chartController: ChartController;

function init(): void {
  const container = document.getElementById('chart-container');
  if (!container) {
    console.error('[main] #chart-container not found');
    return;
  }

  chartController = new ChartController();
  chartController.init(container);

  // Populate toolbar date inputs with defaults
  const dateRange = getDefaultDateRange();
  const startInput = document.getElementById('toolbar-date-start') as HTMLInputElement | null;
  const endInput = document.getElementById('toolbar-date-end') as HTMLInputElement | null;
  const tfSelect = document.getElementById('toolbar-timeframe') as HTMLSelectElement | null;

  if (startInput) startInput.value = dateRange.dateStart;
  if (endInput) endInput.value = dateRange.dateEnd;

  // Auto-load on startup
  chartController.loadData(SYMBOL, DEFAULT_TIMEFRAME, dateRange);

  // Load button — manual reload (Story 2.3 will wire timeframe/date changes properly)
  const btnLoad = document.getElementById('btn-load');
  if (btnLoad) {
    btnLoad.addEventListener('click', () => {
      const tf = tfSelect?.value ?? DEFAULT_TIMEFRAME;
      const ds = startInput?.value ?? dateRange.dateStart;
      const de = endInput?.value ?? dateRange.dateEnd;
      chartController.loadData(SYMBOL, tf, { dateStart: ds, dateEnd: de });
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
```

### Brownfield context quan trọng

**Inline `<style>` trong index.html hiện tại:**
Hiện tại `index.html` có nhiều inline `<style>` block chứa Phase 2 styles (SessionListPanel, ExportPreview, CompletionOverlay, StatusBar, button classes). Khi rewrite index.html:
- Chuyển toàn bộ inline styles sang `static/style.css` — tất cả trong `@layer components`
- Giữ class names y chang (`.session-list-panel`, `.export-preview-overlay`, etc.) để không break Phase 2 code
- Phase 2 components vẫn hoạt động bình thường — chúng mount vào `#session-list-root`, `#export-preview-root`

**Jinja2 template variable:**
- File index.html hiện có: `<script>window.__SUPABASE_ENABLED__ = {{ supabase_enabled }};</script>`
- Phase 2 code (ExportPanel, v.v.) có thể check `window.__SUPABASE_ENABLED__`
- Kiểm tra Phase 2 code trước khi xóa: nếu có check này, thay bằng `window.__SUPABASE_ENABLED__ = false;` hardcoded
- Backend sẽ không serve index.html qua Jinja2 nữa sau Phase 1 rewrite

**EventBus file name:**
- Architecture spec nói `event_bus.ts` (snake_case) nhưng file thực tế là `EventBus.ts` (PascalCase)
- **Quyết định**: Dùng PascalCase nhất quán với codebase hiện tại
- `ChartController.ts` (PascalCase) — không phải `chart_controller.ts`
- Import: `import { eventBus } from './EventBus'`

**Existing EventBus và types.ts:**
- `EventBus.ts` đã tồn tại và hoạt động — KHÔNG rewrite, chỉ thêm events vào types.ts
- `types.ts` đã có `OHLCVBar` nhưng thiếu `ma_20`/`ema_20` — add vào
- `types.ts` đã có `EventMap` — thêm `'chart:ready'` và `'chart:dataLoaded'` vào

**Phase 2 components (SessionListPanel, ExportPreview, etc.):**
- Tất cả mount động qua JS vào root containers (`#session-list-root`, `#export-preview-root`)
- Không cần thay đổi Phase 2 TS files — chỉ đảm bảo HTML containers vẫn tồn tại
- Nếu Phase 2 component nào hardcode append vào `document.body`, kiểm tra để đảm bảo nó vẫn work

### Files cần modify

| File | Thay đổi |
|------|---------|
| `frontend/types.ts` | Thêm `ma_20/ema_20` vào OHLCVBar; thêm `chart:ready`, `chart:dataLoaded` vào EventMap; thêm `OHLCVApiResponse`, `GapInfo`, `DateRange` |
| `static/style.css` | Thêm `@layer` declaration + tokens + Phase 1 layout CSS. Migrate inline styles từ index.html vào đây |
| `static/index.html` | Rewrite `<body>` cho Phase 1 layout. Xóa inline `<style>`. Xóa Jinja2 hack |

### Files cần tạo mới

| File | Nội dung |
|------|---------|
| `frontend/ChartController.ts` | LW Charts v5, init, loadData, LRU-1, revealBar, hasData |
| `frontend/main.ts` | Entry point: init ChartController, auto-load, toolbar Load button |

### Files KHÔNG được touch

- `frontend/EventBus.ts` — không rewrite
- `frontend/ReplayEngine.ts` — Epic P1-4 scope
- `backend/` — story này chỉ là frontend
- `tests/` — manual browser testing; không cần pytest tests cho frontend MVP (ADR-10)

### No tests required

Per ADR-10: "Frontend MVP: manual testing + browser DevTools. Unit tests cho EventBus, CoordinateTranslator — optional."

Story này không yêu cầu viết test file mới. Dev verify bằng browser: mở `localhost:8000`, thấy chart render với candlestick data từ cache.

### Build command

```bash
# Frontend build (run trong root dir)
npm run build         # one-time build
npm run watch         # watch mode cho dev

# Full dev stack (nếu có overmind)
overmind start

# Backend
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Sau khi build, `static/app.js` được cập nhật. Reload browser (hard reload: Cmd+Shift+R) để thấy changes.

### References

- FR7: Candlestick chart render — `epics-phase1.md` line 575 (Epic 2, Story 2.2)
- UX-DR17: CSS design tokens — `epics-phase1.md` line 118
- UX-DR18: Layout spec — `epics-phase1.md` line 136
- LW Charts v5: `node_modules/lightweight-charts/` — ONLY dùng v5 docs
- Architecture ADR-13: LRU-1 cache — `architecture.md` line 393
- Chart init sequence: `architecture.md` line 518

## Review Findings (2026-05-03)

### Decision-needed (resolved)
- [x] [Review][Decision] LRU cache ignores dateRange — user chose: include dateRange in cache key
- [x] [Review][Decision] sessionListPanel.open() auto-opens on startup — user chose: remove (not in spec)

### Patch
- [x] [Review][Patch] Race condition: no AbortController on fetch [ChartController.ts:57]
- [x] [Review][Patch] Include dateRange in LRU cache key [ChartController.ts:66-71]
- [x] [Review][Patch] Remove sessionListPanel.open() from init() [main.ts:59]
- [x] [Review][Patch] Empty state only logs to console, no visible UI [ChartController.ts:155-159]
- [x] [Review][Patch] No bar sort/dedup before setData() [ChartController.ts:127-135]
- [x] [Review][Patch] getDefaultDateRange() month boundary overflow [main.ts:12-16] — deferred, 1-day edge case
- [x] [Review][Patch] Literal hex/px in @layer components — should use tokens [style.css:117,242,262,291,298,307,362]
- [x] [Review][Patch] __SUPABASE_ENABLED__ hardcoded breaks backend replace() [index.html:53, main.py:55]
- [x] [Review][Patch] No error boundary around init() — ExportPanel failure kills app [main.ts:39]
- [x] [Review][Patch] loadData ignores clipped/gaps metadata from response [ChartController.ts:95-107] — already handled by doLoad()

### Defer
- [x] [Review][Defer] Missing --prim-gray-300 token [style.css] — deferred, cosmetic
- [x] [Review][Defer] Inline style on results-panel-placeholder [index.html:34] — deferred, cosmetic
- [x] [Review][Defer] Missing --prim-yellow-300 in @layer tokens [style.css] — deferred, Phase 2 fallback works
- [x] [Review][Defer] LoadDataResult type defined but unused [types.ts:53-58] — deferred, future use
- [x] [Review][Defer] revealBar may slice against different date range [ChartController.ts:82-86] — deferred, Epic P1-4 scope
- [x] [Review][Defer] ExportPanel/sessionListPanel never destroyed [main.ts:25-26] — deferred, single-call usage
- [x] [Review][Defer] No date input validation before fetch [main.ts:36-38] — deferred, server validates
- [x] [Review][Defer] _renderBars recalculates on every render [ChartController.ts:88-91] — deferred, perf optimization
- [x] [Review][Defer] ema_20/ma_20 discarded by _renderBars [ChartController.ts:127-135] — deferred, P1-2-4 scope
- [x] [Review][Defer] CSS @layer browser compatibility [style.css:5] — deferred, target browsers support it
- [x] [Review][Defer] Phase 2 CSS unlayered fragility [style.css:370] — deferred, intentional design
- [x] [Review][Defer] lang="vi" screen reader consideration [index.html:2] — deferred, all UI is Vietnamese
- [x] [Review][Defer] loadData() signature deviation from spec [ChartController.ts:67] — deferred, enhancement
- [x] [Review][Defer] main.ts extra Phase 2 logic [main.ts:12-13,65] — deferred, bundling concern
- [x] [Review][Defer] ChartController hardcoded hex vs CSS tokens [ChartController.ts:28-50] — deferred, LW Charts JS API limitation

## Dev Agent Record

### Agent Model Used

mimo-v2.5-pro

### Debug Log References

- Build: `npm run build` — 275.3kb output, 26ms, no errors
- Typecheck: `npm run typecheck` — no errors

### Completion Notes List

- All 5 tasks completed
- CSS: `@layer reset, tokens, components, utilities` declaration added. Tokens in `@layer tokens`, Phase 1 layout + Phase 2 component styles in `@layer components`, Phase 2 overlay styles unlayered (higher specificity)
- Inline `<style>` from index.html moved into `style.css` `@layer components`
- Jinja2 `{{ supabase_enabled }}` replaced with `false` hardcoded (SessionListPanel checks `=== true`, so Supabase features disabled in Phase 1)
- ChartController uses LW Charts v5 `addSeries(CandlestickSeries, ...)` pattern (verified v5.2.0 installed)
- Timestamp division by 1000 for LW Charts (backend sends ms, LW Charts expects seconds)
- UTC+7 display via `localization.timeFormatter`
- LRU-1 cache: single slot, evict before fetch, cache hit skips API call
- main.ts imports Phase 2 modules (SessionListPanel, ExportPanel) to ensure bundling

### File List

- `frontend/types.ts` — modified (added EventMap events, OHLCVBar fields, OHLCVApiResponse, GapInfo, DateRange)
- `static/style.css` — rewritten (CSS Design Token System with @layer, Phase 1 layout, Phase 2 styles migrated from index.html)
- `static/index.html` — rewritten (Phase 1 layout, removed inline styles, Jinja2 hack replaced)
- `frontend/ChartController.ts` — created (LW Charts v5 integration, LRU-1 cache, loadData, revealBar)
- `frontend/main.ts` — created (entry point, ChartController init, toolbar wiring, Phase 2 imports)
