import type { MouseEventParams } from 'lightweight-charts';
import type { ChartController } from './ChartController';
import { eventBus } from './EventBus';

function formatNumber(v: number): string {
  return v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatTimestampUTC7(timestampMs: number): string {
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
  private replayActive = false;
  private replayCurrentIndex = -1;

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

    eventBus.on('replay:barAdvanced', ({ barIndex }) => {
      this.replayActive = true;
      this.replayCurrentIndex = barIndex;
    });

    eventBus.on('replayStateChanged', ({ state }) => {
      if (state === 'stopped') {
        this.replayActive = false;
        this.replayCurrentIndex = -1;
      }
    });
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

    // Look-ahead guard: block tooltip for unrevealed bars during replay
    if (this.replayActive) {
      const bars = this.controller.getCachedBars();
      if (bars) {
        const barIndex = bars.findIndex(b => Math.round(b.timestamp / 1000) === (param.time as number));
        if (barIndex !== -1 && barIndex > this.replayCurrentIndex) {
          this.el.style.display = 'none';
          return;
        }
      }
    }

    // Format content
    const timeStr = formatTimestampUTC7(bar.timestamp);
    this.el.innerHTML = `
      <div class="tooltip-time">${timeStr}</div>
      <div class="tooltip-grid">
        <span class="tooltip-label">O</span><span class="tooltip-value">${formatNumber(bar.open)}</span>
        <span class="tooltip-label">H</span><span class="tooltip-value tooltip-value--high">${formatNumber(bar.high)}</span>
        <span class="tooltip-label">L</span><span class="tooltip-value tooltip-value--low">${formatNumber(bar.low)}</span>
        <span class="tooltip-label">C</span><span class="tooltip-value">${formatNumber(bar.close)}</span>
        <span class="tooltip-label">Vol</span><span class="tooltip-value">${formatNumber(bar.volume)}</span>
      </div>
    `;

    // Position: boundary-aware
    const containerWidth  = this.container.clientWidth;
    const containerHeight = this.container.clientHeight;
    const tooltipWidth    = this.el.offsetWidth || 160;
    const tooltipHeight   = this.el.offsetHeight || 110;
    const OFFSET          = 12;

    let left: number;
    let top: number;

    if (param.point.x > containerWidth / 2) {
      left = param.point.x - tooltipWidth - OFFSET;
    } else {
      left = param.point.x + OFFSET;
    }

    top = param.point.y - tooltipHeight / 2;
    top = Math.max(8, Math.min(top, containerHeight - tooltipHeight - 8));
    left = Math.max(8, Math.min(left, containerWidth - tooltipWidth - 8));

    this.el.style.left    = `${left}px`;
    this.el.style.top     = `${top}px`;
    this.el.style.display = 'block';
  }

  destroy(): void {
    this.controller.unsubscribeHover(this.boundHandler);
    if (this.el.parentNode) {
      this.el.remove();
    }
  }
}
