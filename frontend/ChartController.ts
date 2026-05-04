import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  IChartApi,
  ISeriesApi,
  ISeriesMarkersPluginApi,
  Time,
  UTCTimestamp,
  MouseEventParams,
} from 'lightweight-charts';
import { eventBus } from './EventBus';
import type { OHLCVBar, OHLCVApiResponse, DateRange, LoadDataResult } from './types';

export type TradeMarkerType = 'entry' | 'tp' | 'sl';

export interface TradeMarker {
  barIndex: number;
  type: TradeMarkerType;
  price: number;
}

interface LRU1Cache {
  symbol: string;
  timeframe: string;
  dateStart: string;
  dateEnd: string;
  data: OHLCVBar[];
}

export class ChartController {
  private chart: IChartApi | undefined;
  private series: ISeriesApi<'Candlestick'> | undefined;
  private cache: LRU1Cache | null = null;
  private abortController: AbortController | null = null;
  private resizeObserver: ResizeObserver | undefined;
  private container: HTMLElement | undefined;
  private tradeMarkers: TradeMarker[] = [];
  private markersPlugin: ISeriesMarkersPluginApi<Time> | null = null;

  init(container: HTMLElement): void {
    this.container = container;
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

    // Trade markers plugin
    this.markersPlugin = createSeriesMarkers(this.series, []);

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

  async loadData(symbol: string, timeframe: string, dateRange: DateRange): Promise<LoadDataResult | null> {
    // LRU-1 cache check
    if (
      this.cache &&
      this.cache.symbol === symbol &&
      this.cache.timeframe === timeframe &&
      this.cache.dateStart === dateRange.dateStart &&
      this.cache.dateEnd === dateRange.dateEnd
    ) {
      this._renderBars(this.cache.data);
      eventBus.emit('chart:dataLoaded', { barCount: this.cache.data.length, bars: this.cache.data });
      return {
        barCount: this.cache.data.length,
        clipped: false,
        actualDateStart: null,
        actualDateEnd: null,
      };
    }

    // LRU-1 evict before fetch
    this.cache = null;

    // Abort any in-flight request
    this.abortController?.abort();
    this.abortController = new AbortController();

    const params = new URLSearchParams({
      symbol,
      timeframe,
      date_start: dateRange.dateStart,
      date_end: dateRange.dateEnd,
    });

    try {
      const res = await fetch(`/api/ohlcv?${params}`, {
        signal: this.abortController.signal,
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const message = errData?.error?.message ?? `HTTP ${res.status}`;
        console.error(`[ChartController] loadData error: ${message}`);
        this._showEmptyState(`Chưa có data cho ${timeframe} — fetch trước`);
        return null;
      }

      const body: OHLCVApiResponse = await res.json();
      if (!body.data) {
        console.error('[ChartController] loadData: response data is null');
        this._showEmptyState(`Chưa có data cho ${timeframe} — fetch trước`);
        return null;
      }

      const bars = body.data;
      this.cache = { symbol, timeframe, dateStart: dateRange.dateStart, dateEnd: dateRange.dateEnd, data: bars };
      this._renderBars(bars);
      this._hideEmptyState();
      eventBus.emit('chart:dataLoaded', { barCount: bars.length, bars });

      return {
        barCount: bars.length,
        clipped: body.clipped ?? false,
        actualDateStart: body.actual_date_start ?? null,
        actualDateEnd: body.actual_date_end ?? null,
      };

    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === 'AbortError') {
        return null; // silently ignore aborted requests
      }
      const message = e instanceof Error ? e.message : String(e);
      console.error(`[ChartController] loadData exception: ${message}`);
      this._showEmptyState(`Chưa có data cho ${timeframe} — fetch trước`);
      return null;
    }
  }

  hasData(): boolean {
    return this.cache !== null && this.cache.data.length > 0;
  }

  getChart(): IChartApi | undefined {
    return this.chart;
  }

  getCachedBars(): OHLCVBar[] | null {
    return this.cache?.data ?? null;
  }

  getCandlestickSeries(): ISeriesApi<'Candlestick'> | undefined {
    return this.series;
  }

  subscribeHover(cb: (param: MouseEventParams) => void): void {
    this.chart?.subscribeCrosshairMove(cb);
  }

  unsubscribeHover(cb: (param: MouseEventParams) => void): void {
    this.chart?.unsubscribeCrosshairMove(cb);
  }

  getBarByTime(timeSeconds: number): OHLCVBar | undefined {
    if (!this.cache) return undefined;
    return this.cache.data.find(b => Math.round(b.timestamp / 1000) === timeSeconds);
  }

  getContainer(): HTMLElement | undefined {
    return this.container;
  }

  /** Called by ReplayEngine (Epic P1-4) to reveal bars up to index */
  revealBar(upToIndex: number): void {
    if (!this.cache || !this.series) return;

    const savedRange = this.chart?.timeScale().getVisibleLogicalRange();

    if (upToIndex === 0) {
      // Reset: render full data so timeScale knows the full date range,
      // then restore zoom width and scroll to start
      this._renderBars(this.cache.data);
      if (savedRange && savedRange.to > savedRange.from) {
        const width = savedRange.to - savedRange.from;
        this.chart?.timeScale().setVisibleLogicalRange({ from: 0, to: width });
      }
    } else {
      // Normal replay: render slice, preserve zoom
      const slice = this.cache.data.slice(0, upToIndex + 1);
      this._renderBars(slice);
      if (savedRange) {
        this.chart?.timeScale().setVisibleLogicalRange(savedRange);
      }
    }

    // Re-render trade markers after data update (setData clears markers)
    if (this.tradeMarkers.length > 0) {
      this._renderTradeMarkers();
    }
  }

  private _renderBars(bars: OHLCVBar[]): void {
    if (!this.series) return;

    // Sort by timestamp and deduplicate
    const seen = new Set<number>();
    const sorted = [...bars]
      .filter(b => {
        const t = Math.round(b.timestamp / 1000);
        if (seen.has(t)) return false;
        seen.add(t);
        return true;
      })
      .sort((a, b) => a.timestamp - b.timestamp);

    this.series.setData(
      sorted.map(b => ({
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

    // Show visible overlay in chart container
    if (this.container) {
      let overlay = this.container.querySelector('.chart-empty-overlay') as HTMLElement | null;
      if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'chart-empty-overlay';
        overlay.style.cssText = 'position:absolute;inset:0;z-index:15;display:flex;align-items:center;justify-content:center;color:var(--sem-text-muted);font-size:0.9rem;pointer-events:none;';
        this.container.appendChild(overlay);
      }
      overlay.textContent = message;
      overlay.style.display = 'flex';
    }

    eventBus.emit('chart:loadError', { message });
  }

  private _hideEmptyState(): void {
    if (!this.container) return;
    const overlay = this.container.querySelector('.chart-empty-overlay') as HTMLElement | null;
    if (overlay) overlay.style.display = 'none';
  }

  addTradeMarker(barIndex: number, type: TradeMarkerType, price: number): void {
    this.tradeMarkers.push({ barIndex, type, price });
    this._renderTradeMarkers();
    this._showPulseAnimation(type, barIndex, price);
  }

  clearTradeMarkers(): void {
    this.tradeMarkers = [];
    this._renderTradeMarkers();
  }

  private _getBarTime(barIndex: number): UTCTimestamp | undefined {
    if (!this.cache) return undefined;
    const bar = this.cache.data[barIndex];
    if (!bar) return undefined;
    return (bar.timestamp / 1000) as UTCTimestamp;
  }

  private _renderTradeMarkers(): void {
    if (!this.series) return;

    const markerShapes: Record<TradeMarkerType, { color: string; shape: 'arrowUp' | 'circle'; position: 'belowBar' | 'aboveBar'; text: string }> = {
      entry: { color: '#3fb950', shape: 'arrowUp', position: 'belowBar', text: 'Entry' },
      tp:    { color: '#4ea8de', shape: 'circle', position: 'aboveBar', text: '✓ TP' },
      sl:    { color: '#f85149', shape: 'circle', position: 'aboveBar', text: '✗ SL' },
    };

    const chartMarkers = this.tradeMarkers
      .map(m => {
        const time = this._getBarTime(m.barIndex);
        if (!time) return null;
        const shape = markerShapes[m.type];
        return { time, position: shape.position, color: shape.color, shape: shape.shape, text: shape.text };
      })
      .filter((m): m is NonNullable<typeof m> => m !== null)
      .sort((a, b) => (a.time as number) - (b.time as number));

    this.markersPlugin?.setMarkers(chartMarkers);
  }

  private _showPulseAnimation(type: TradeMarkerType, barIndex: number, price: number): void {
    if (!this.container || !this.chart || !this.series || !this.cache) return;

    const bar = this.cache.data[barIndex];
    if (!bar) return;

    const time = bar.timestamp / 1000;

    const seriesApi = this.chart.timeScale();
    const x = seriesApi.timeToCoordinate(time as UTCTimestamp);
    const y = this.series.priceToCoordinate(price);
    if (x === null || y === null) return;

    const pulse = document.createElement('div');
    pulse.className = `trade-marker-pulse trade-marker-pulse--${type}`;
    pulse.style.left = `${x}px`;
    pulse.style.top = `${y}px`;
    this.container.appendChild(pulse);

    const fallback = setTimeout(() => pulse.remove(), 700);
    pulse.addEventListener('animationend', () => { clearTimeout(fallback); pulse.remove(); });
  }

  destroy(): void {
    this.abortController?.abort();
    this.abortController = null;
    this.resizeObserver?.disconnect();
    this.markersPlugin = null;
    this.tradeMarkers = [];
    this.container?.querySelectorAll('.trade-marker-pulse').forEach(el => el.remove());
    this.chart?.remove();
    this.chart = undefined;
    this.series = undefined;
    this.cache = null;
  }
}
