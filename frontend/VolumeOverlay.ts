import { HistogramSeries, ISeriesApi, UTCTimestamp } from 'lightweight-charts';
import type { ChartController } from './ChartController';
import type { OHLCVBar } from './types';
import { eventBus } from './EventBus';

interface HistogramData {
  time: UTCTimestamp;
  value: number;
  color: string;
}

function buildVolumeData(bars: OHLCVBar[]): HistogramData[] {
  const seen = new Set<number>();
  return bars
    .filter(b => {
      const t = Math.round(b.timestamp / 1000);
      if (!Number.isFinite(b.volume) || seen.has(t)) return false;
      seen.add(t);
      return true;
    })
    .map(b => ({
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
  private replayActive = false;
  private replayCurrentIndex = -1;

  constructor(controller: ChartController) {
    this.controller = controller;
  }

  init(): void {
    if (this.series) return; // idempotent — prevent double-init series leak
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

    eventBus.on('replay:barAdvanced', ({ barIndex }) => {
      this.replayActive = true;
      this.replayCurrentIndex = barIndex;
      this._updateReplaySlice();
    });

    eventBus.on('replayStateChanged', ({ state }) => {
      if (state === 'stopped') {
        this.replayActive = false;
        this.replayCurrentIndex = -1;
        if (this.currentBars.length > 0 && this.visible) this._render(this.currentBars);
      }
    });
  }

  update(bars: OHLCVBar[]): void {
    this.currentBars = bars;
    if (this.replayActive) {
      this._updateReplaySlice();
    } else if (this.visible) {
      this._render(bars);
    }
  }

  private _updateReplaySlice(): void {
    if (!this.replayActive || this.currentBars.length === 0 || !this.visible) return;
    const slice = this.currentBars.slice(0, this.replayCurrentIndex + 1);
    this._render(slice);
  }

  setVisible(visible: boolean): void {
    this.visible = visible;
    if (visible) {
      if (this.replayActive) {
        this._updateReplaySlice();
      } else {
        this._render(this.currentBars);
      }
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
