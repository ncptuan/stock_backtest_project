import { LineSeries, ISeriesApi, UTCTimestamp } from 'lightweight-charts';
import type { ChartController } from './ChartController';
import type { OHLCVBar } from './types';
import { eventBus } from './EventBus';

function buildLineData(bars: OHLCVBar[], field: 'ma_20' | 'ema_20') {
  return bars
    .filter(b => b[field] !== null && b[field] !== undefined && Number.isFinite(b[field]))
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
  private replayActive = false;
  private replayCurrentIndex = -1;

  constructor(controller: ChartController) {
    this.controller = controller;
  }

  init(): void {
    if (this.maSeries) return; // idempotent — prevent double-init series leak
    const chart = this.controller.getChart();
    if (!chart) return;

    this.maSeries = chart.addSeries(LineSeries, {
      color: '#2f81f7',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    this.emaSeries = chart.addSeries(LineSeries, {
      color: '#d29922',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    this.maSeries.setData([]);
    this.emaSeries.setData([]);

    eventBus.on('replay:barAdvanced', ({ barIndex }) => {
      this.replayActive = true;
      this.replayCurrentIndex = barIndex;
      this._updateReplaySlice();
    });

    eventBus.on('replayStateChanged', ({ state }) => {
      if (state === 'stopped') {
        this.replayActive = false;
        this.replayCurrentIndex = -1;
        if (this.currentBars.length > 0) this.update(this.currentBars);
      }
    });
  }

  update(bars: OHLCVBar[]): void {
    this.currentBars = bars;
    if (this.replayActive) {
      this._updateReplaySlice();
    } else {
      if (this.maVisible)  this._renderMa(bars);
      if (this.emaVisible) this._renderEma(bars);
    }
  }

  private _updateReplaySlice(): void {
    if (!this.replayActive || this.currentBars.length === 0) return;
    const slice = this.currentBars.slice(0, this.replayCurrentIndex + 1);
    if (this.maVisible)  this._renderMa(slice);
    if (this.emaVisible) this._renderEma(slice);
  }

  setMa20Visible(visible: boolean): void {
    this.maVisible = visible;
    if (visible) {
      if (this.replayActive) {
        this._updateReplaySlice();
      } else {
        this._renderMa(this.currentBars);
      }
    } else {
      this.maSeries?.setData([]);
    }
  }

  setEma20Visible(visible: boolean): void {
    this.emaVisible = visible;
    if (visible) {
      if (this.replayActive) {
        this._updateReplaySlice();
      } else {
        this._renderEma(this.currentBars);
      }
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
