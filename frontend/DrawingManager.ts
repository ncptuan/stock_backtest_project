import { MouseEventParams } from 'lightweight-charts';
import type { ChartController } from './ChartController';
import type { CoordinateTranslator } from './CoordinateTranslator';
import type { LineType, DrawingLine, DrawingSnapshot } from './types';
import { eventBus } from './EventBus';

const LINE_CONFIG: Record<LineType, { color: string; dash: number[]; width: number }> = {
  entry: { color: '#2f81f7', dash: [],        width: 2   },
  tp:    { color: '#3fb950', dash: [6, 4],    width: 1.5 },
  sl:    { color: '#f85149', dash: [2, 4],    width: 1.5 },
};

const LINE_LABEL: Record<LineType, string> = {
  entry: 'Entry',
  tp:    'TP',
  sl:    'SL',
};

const LINE_LABEL_BG: Record<LineType, string> = {
  entry: 'rgba(47, 129, 247, 0.85)',
  tp:    'rgba(63, 185, 80, 0.85)',
  sl:    'rgba(248, 81, 73, 0.85)',
};

const LABEL_FONT = '11px monospace';
const LABEL_PADDING_H = 6;
const LABEL_HEIGHT = 18;
const LABEL_RIGHT_MARGIN = 8;
const MIN_LABEL_GAP = 15;

export class DrawingManager {
  private controller: ChartController;
  private translator: CoordinateTranslator;
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;
  private dpr = 1;
  private cssWidth = 0;
  private cssHeight = 0;
  private container: HTMLElement | null = null;
  private lines = new Map<LineType, DrawingLine | null>([
    ['entry', null], ['tp', null], ['sl', null],
  ]);
  private handles = new Map<LineType, HTMLDivElement | null>([
    ['entry', null], ['tp', null], ['sl', null],
  ]);
  private activeType: LineType | null = null;
  private selectedType: LineType | null = null;
  private replayLocked = false;
  private dragging: LineType | null = null; // Patch #2: concurrent drag guard
  private onActiveTypeChange: ((type: LineType | null) => void) | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private unsubRangeChange: (() => void) | null = null;
  private unsubClick: (() => void) | null = null;

  constructor(controller: ChartController, translator: CoordinateTranslator) {
    this.controller = controller;
    this.translator = translator;
  }

  setActiveTypeChangeCallback(cb: (type: LineType | null) => void): void {
    this.onActiveTypeChange = cb;
  }

  init(container: HTMLElement): void {
    if (this.canvas) return; // idempotent — prevent double-init leak

    this.container = container;

    const canvas = document.createElement('canvas');
    canvas.style.cssText = [
      'position:absolute', 'top:0', 'left:0',
      'width:100%', 'height:100%',
      'pointer-events:none',
      'z-index:10',
    ].join(';');
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');

    if (getComputedStyle(container).position === 'static') {
      container.style.position = 'relative';
    }
    container.appendChild(canvas);

    this._resizeCanvas(container);
    this.resizeObserver = new ResizeObserver(() => {
      this._resizeCanvas(container);
      this.redrawAll();
    });
    this.resizeObserver.observe(container);

    const chart = this.controller.getChart();
    if (!chart) return;

    const rangeChangeHandler = () => {
      if (this.translator.isUpdating) return;
      this.translator.isUpdating = true;
      this.redrawAll();
      this.translator.isUpdating = false;
    };
    chart.timeScale().subscribeVisibleLogicalRangeChange(rangeChangeHandler);
    this.unsubRangeChange = () => {
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(rangeChangeHandler);
    };

    const clickHandler = (param: MouseEventParams) => {
      this._handleChartClick(param);
    };
    chart.subscribeClick(clickHandler);
    this.unsubClick = () => chart.unsubscribeClick(clickHandler);
  }

  private _resizeCanvas(container: HTMLElement): void {
    if (!this.canvas) return;
    this.dpr = window.devicePixelRatio || 1;
    this.cssWidth = container.clientWidth;
    this.cssHeight = container.clientHeight;
    this.canvas.width = this.cssWidth * this.dpr;
    this.canvas.height = this.cssHeight * this.dpr;
    this.canvas.style.width = `${this.cssWidth}px`;
    this.canvas.style.height = `${this.cssHeight}px`;
    // setTransform is explicit — doesn't depend on canvas.width resetting state
    this.ctx?.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
  }

  private _handleChartClick(param: MouseEventParams): void {
    this.selectedType = null;

    if (!this.activeType) return;
    if (!param.point) return;
    if (!this.translator.isInitialized()) return;

    const rawPrice = this.translator.yToPrice(param.point.y);
    if (rawPrice === null) return;

    const snapped = Math.round(rawPrice * 100) / 100;
    this.setLine(this.activeType, snapped);
    this.setActiveType(null);
  }

  setLine(type: LineType, price: number): void {
    this.lines.set(type, { type, price });
    this.redrawAll();
    eventBus.emit('drawing:lineChanged', { type, price });
  }

  clearLine(type: LineType): void {
    this.lines.set(type, null);
    this.redrawAll();
    eventBus.emit('drawing:cleared', {});
  }

  clearAll(): void {
    this.lines.set('entry', null);
    this.lines.set('tp', null);
    this.lines.set('sl', null);
    this.redrawAll();
    eventBus.emit('drawing:cleared', {});
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
    for (const [type, line] of this.lines) {
      if (line) eventBus.emit('drawing:lineChanged', { type, price: line.price });
    }
  }

  exportDrawings(): DrawingSnapshot {
    return this.getSnapshot();
  }

  importDrawings(snapshot: DrawingSnapshot): void {
    this.restore(snapshot);
  }

  setActiveType(type: LineType | null): void {
    this.activeType = type;
    this.onActiveTypeChange?.(type);
  }

  getActiveType(): LineType | null {
    return this.activeType;
  }

  setSelectedType(type: LineType | null): void {
    this.selectedType = type;
  }

  getSelectedType(): LineType | null {
    return this.selectedType;
  }

  deleteSelected(): boolean {
    if (!this.selectedType) return false;
    this.clearLine(this.selectedType);
    this.selectedType = null;
    return true;
  }

  freeze(): void {
    this.replayLocked = true;
    this.selectedType = null;
    for (const [type, handle] of this.handles) {
      if (handle) {
        handle.remove();
        this.handles.set(type, null);
      }
    }
  }

  unfreeze(): void {
    this.replayLocked = false;
    this.redrawAll();
  }

  redrawAll(): void {
    if (!this.ctx || !this.canvas) return;
    this.ctx.clearRect(0, 0, this.cssWidth, this.cssHeight);

    // Collect lines with their Y positions
    const drawItems: Array<{ line: DrawingLine; y: number }> = [];
    for (const line of this.lines.values()) {
      if (!line) continue;
      const y = this.translator.priceToY(line.price);
      if (y === null) continue;
      drawItems.push({ line, y });
    }

    // Sort by Y ascending
    drawItems.sort((a, b) => a.y - b.y);

    // Adjust label Y positions to prevent overlap
    const labelYs: number[] = [];
    for (let i = 0; i < drawItems.length; i++) {
      let labelY = drawItems[i].y;
      if (i > 0 && labelY - labelYs[i - 1] < MIN_LABEL_GAP) {
        labelY = labelYs[i - 1] + MIN_LABEL_GAP;
      }
      // Clamp to prevent labels from going off-canvas bottom
      labelY = Math.min(labelY, this.cssHeight - LABEL_HEIGHT / 2);
      labelYs.push(labelY);
    }

    // Draw lines at real Y, labels at adjusted Y
    for (let i = 0; i < drawItems.length; i++) {
      const { line } = drawItems[i];
      const realY = drawItems[i].y;
      const labelY = labelYs[i];
      const isSelected = line.type === this.selectedType;

      this._drawLineStroke(line, realY, isSelected);
      this._drawLabel(line, labelY, isSelected);
    }

    this._updateHandles();

    const rr = this._calcRR();
    if (rr !== null) {
      this._drawRRBadge(rr);
    }
  }

  private _drawLineStroke(line: DrawingLine, y: number, isSelected: boolean): void {
    if (!this.ctx) return;
    const cfg = LINE_CONFIG[line.type];
    const ctx = this.ctx;

    ctx.save();
    ctx.beginPath();
    ctx.strokeStyle = cfg.color;
    ctx.lineWidth = isSelected ? cfg.width + 0.5 : cfg.width;
    ctx.setLineDash(cfg.dash);
    ctx.moveTo(0, y);
    ctx.lineTo(this.cssWidth, y);
    ctx.stroke();
    ctx.restore();
  }

  private _formatPrice(price: number): string {
    return price.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  private _drawLabel(line: DrawingLine, canvasY: number, isSelected: boolean): void {
    if (!this.ctx) return;
    const ctx = this.ctx;

    ctx.save();

    const text = `${LINE_LABEL[line.type]} ${this._formatPrice(line.price)}`;
    ctx.font = LABEL_FONT;
    const textW = ctx.measureText(text).width;
    const rectW = textW + LABEL_PADDING_H * 2;
    const rectH = LABEL_HEIGHT;
    const rectX = this.cssWidth - rectW - LABEL_RIGHT_MARGIN;
    const rectY = canvasY - rectH / 2;

    // Background rect
    ctx.beginPath();
    ctx.fillStyle = LINE_LABEL_BG[line.type];
    if (ctx.roundRect) {
      ctx.roundRect(rectX, rectY, rectW, rectH, 3);
    } else {
      ctx.rect(rectX, rectY, rectW, rectH);
    }
    ctx.fill();

    // Selected border
    if (isSelected) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
      ctx.lineWidth = 1;
      ctx.setLineDash([]);
      ctx.stroke();
    }

    // Label text
    ctx.fillStyle = '#ffffff';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, rectX + LABEL_PADDING_H, canvasY);

    ctx.restore();
  }

  private _calcRR(): number | null {
    const entry = this.lines.get('entry');
    const tp    = this.lines.get('tp');
    const sl    = this.lines.get('sl');

    if (!entry || !tp || !sl) return null;

    const reward = tp.price - entry.price;
    const risk   = entry.price - sl.price;

    if (risk === 0) return null;

    return reward / risk;
  }

  private _drawRRBadge(rr: number): void {
    if (!this.ctx) return;
    const ctx = this.ctx;
    const w = this.cssWidth;
    const h = this.cssHeight;
    if (h === 0) return;

    const rrAbs = Math.abs(rr).toFixed(2);
    const text = rr < 0 ? `⚠ R:R = 1:${rrAbs}` : `R:R = 1:${rrAbs}`;
    ctx.font = 'bold 12px monospace';
    const textW = ctx.measureText(text).width;

    const PAD_H = 8;
    const rectW = textW + PAD_H * 2;
    const rectH = 24;
    const MARGIN = 12;

    const rectX = w - rectW - MARGIN;
    const rectY = h - rectH - MARGIN;

    ctx.save();
    ctx.fillStyle = rr >= 1
      ? 'rgba(63, 185, 80, 0.85)'
      : rr >= 0
      ? 'rgba(210, 153, 34, 0.85)'
      : 'rgba(248, 81, 73, 0.85)';

    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(rectX, rectY, rectW, rectH, 4);
    } else {
      ctx.rect(rectX, rectY, rectW, rectH);
    }
    ctx.fill();

    ctx.fillStyle = '#ffffff';
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';
    ctx.fillText(text, rectX + PAD_H, rectY + rectH / 2);
    ctx.restore();
  }

  private _updateHandles(): void {
    if (!this.container || !this.translator.isInitialized()) return;

    for (const [type, line] of this.lines) {
      const existingHandle = this.handles.get(type) ?? null;

      if (!line || this.replayLocked) {
        if (existingHandle) {
          existingHandle.remove();
          this.handles.set(type, null);
        }
        continue;
      }

      const y = this.translator.priceToY(line.price);
      if (y === null || y < 0 || y > this.container.clientHeight) {
        if (existingHandle) existingHandle.style.display = 'none';
        continue;
      }

      if (!existingHandle) {
        const div = document.createElement('div');
        div.style.cssText = [
          'position:absolute',
          'left:0',
          'right:0',
          'height:10px',
          'cursor:ns-resize',
          'z-index:15',
          'transform:translateY(-50%)',
          'background:transparent',
          'user-select:none',
        ].join(';');
        div.addEventListener('mousedown', (e) => this._startDrag(type, e));
        this.container.appendChild(div);
        this.handles.set(type, div);
      }

      const handle = this.handles.get(type)!;
      handle.style.display = 'block';
      handle.style.top = `${y}px`;
    }
  }

  private _startDrag(type: LineType, e: MouseEvent): void {
    e.preventDefault();
    e.stopPropagation();

    if (this.replayLocked) return;
    if (this.dragging) return; // guard: one drag at a time

    this.dragging = type;
    const startY = e.clientY;
    let maxMoved = 0;

    document.body.style.cursor = 'ns-resize';

    const cleanup = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      this.dragging = null;
    };

    const onMove = (mv: MouseEvent) => {
      if (!this.container || this.replayLocked) { cleanup(); return; }

      const moved = Math.abs(mv.clientY - startY);
      if (moved > maxMoved) maxMoved = moved;

      const rect = this.container.getBoundingClientRect();
      const cssY = mv.clientY - rect.top;

      const rawPrice = this.translator.yToPrice(cssY);
      if (rawPrice !== null && this.lines.get(type)) {
        const snapped = Math.round(rawPrice * 100) / 100;
        this.lines.set(type, { type, price: snapped });
        this.redrawAll();
      }
    };

    const onUp = (up: MouseEvent) => {
      cleanup();

      if (!this.container || this.replayLocked) return;

      if (maxMoved < 3) {
        this.setActiveType(null);
        this.selectedType = type;
        this.onActiveTypeChange?.(null);
      } else {
        const rect = this.container.getBoundingClientRect();
        const cssY = up.clientY - rect.top;
        const rawPrice = this.translator.yToPrice(cssY);
        if (rawPrice !== null) {
          const finalPrice = Math.round(rawPrice * 100) / 100;
          this.lines.set(type, { type, price: finalPrice });
          this.redrawAll();
          eventBus.emit('drawing:lineChanged', { type, price: finalPrice });
        }
      }
    };

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  destroy(): void {
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    this.unsubRangeChange?.();
    this.unsubRangeChange = null;
    this.unsubClick?.();
    this.unsubClick = null;

    for (const handle of this.handles.values()) {
      handle?.remove();
    }
    this.handles.clear();
    this.canvas?.remove();
    this.canvas = null;
    this.ctx = null;
  }
}
