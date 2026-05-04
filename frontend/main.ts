import { ChartController } from './ChartController';
import { HoverTooltip } from './HoverTooltip';
import { IndicatorOverlay } from './IndicatorOverlay';
import { VolumeOverlay } from './VolumeOverlay';
import { CoordinateTranslator } from './CoordinateTranslator';
import { DrawingManager } from './DrawingManager';
import { ReplayEngine, SPEED_SLOW, SPEED_NORMAL, SPEED_FAST } from './ReplayEngine';
import { eventBus } from './EventBus';
import { settingsManager } from './SettingsManager';
import { toastManager } from './ToastManager';
import type { PersistedSettings, LineType } from './types';

// Phase 2 imports — ensure these modules are bundled
import { sessionListPanel } from './SessionListPanel';
import { ExportPanel } from './export_panel';
import { resultsPanel } from './ResultsPanel';

const SYMBOL = 'BTC/USDT';

let chartController: ChartController;
let indicatorOverlay: IndicatorOverlay;
let volumeOverlay: VolumeOverlay;
let coordinateTranslator: CoordinateTranslator;
let drawingManager: DrawingManager;
let replayEngine: ReplayEngine;
let currentSettings: PersistedSettings;

// Session fingerprint — frozen at Play time
let frozenFingerprint = '';

function updatePreflightChecklist(): void {
  const snap = drawingManager.getSnapshot();
  const entry = snap.lines.get('entry')?.price ?? null;
  const tp = snap.lines.get('tp')?.price ?? null;
  const sl = snap.lines.get('sl')?.price ?? null;

  const items = [
    { label: 'Entry', price: entry },
    { label: 'TP', price: tp },
    { label: 'SL', price: sl },
    { label: 'Date', price: currentSettings?.dateStart ? 1 : null },
  ];

  const allSet = items.every(i => i.price !== null);

  // Update Play button disabled state
  const btnPlay = document.getElementById('btn-replay-play') as HTMLButtonElement | null;
  if (btnPlay) btnPlay.disabled = !allSet;

  // Update checklist display
  const checklistEl = document.getElementById('preflight-checklist');
  if (checklistEl) {
    checklistEl.innerHTML = items.map(item => {
      const ok = item.price !== null;
      const priceStr = ok
        ? ` ${item.price!.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
        : ' ——';
      return `<span class="checklist-item checklist-item--${ok ? 'ok' : 'missing'}">${ok ? '✓' : '✗'} ${item.label}${priceStr}</span>`;
    }).join(' ');
  }
}

function toggleCheatSheet(): void {
  const el = document.getElementById('cheat-sheet-overlay');
  if (!el) return;
  el.style.display = el.style.display === 'none' ? 'flex' : 'none';
}

function showSessionFingerprint(): void {
  const snap = drawingManager.getSnapshot();
  const entry = snap.lines.get('entry')?.price;
  const tp = snap.lines.get('tp')?.price;
  const sl = snap.lines.get('sl')?.price;
  if (entry === undefined || tp === undefined || sl === undefined) return;

  const fmt = (v: number) => v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  frozenFingerprint = [
    SYMBOL,
    currentSettings.timeframe,
    `${currentSettings.dateStart} → ${currentSettings.dateEnd}`,
    `Entry ${fmt(entry)}`,
    `TP ${fmt(tp)}`,
    `SL ${fmt(sl)}`,
  ].join(' · ');

  const fpEl = document.getElementById('session-fingerprint');
  if (fpEl) {
    fpEl.textContent = frozenFingerprint;
    fpEl.style.display = 'block';
  }
}

async function doLoad(settings: PersistedSettings): Promise<void> {
  const result = await chartController.loadData(SYMBOL, settings.timeframe, {
    dateStart: settings.dateStart,
    dateEnd: settings.dateEnd,
  });

  if (result === null) {
    indicatorOverlay.update([]);
    volumeOverlay.update([]);
    return;
  }

  // Show clip toast if needed
  if (result.clipped) {
    const parts = [
      result.actualDateStart ?? '?',
      result.actualDateEnd ?? '?',
    ];
    toastManager.show(
      `Date range đã được clip về ${parts[0]} — ${parts[1]}`,
      'info',
      { duration: 5000 }
    );
  }

  // Persist settings
  settingsManager.save(settings);
  currentSettings = settings;

  // Update indicator overlay with new bars
  const bars = chartController.getCachedBars();
  if (bars) {
    // Lazy init CoordinateTranslator on first data load
    if (!coordinateTranslator.isInitialized()) {
      const series = chartController.getCandlestickSeries();
      if (series) coordinateTranslator.init(series);
    }
    indicatorOverlay.update(bars);
    volumeOverlay.update(bars);
  }

  // Update status bar
  const statusInfo = document.getElementById('status-data-info');
  if (statusInfo) {
    statusInfo.textContent = `${result.barCount.toLocaleString()} bars`;
  }
}

function handleTimeframeChange(newTimeframe: string): void {
  const prevTimeframe = currentSettings.timeframe;
  if (newTimeframe === prevTimeframe) return;

  // Pause replay if running
  if (replayEngine?.isPlaying()) {
    replayEngine.pause();
  }

  toastManager.dismiss();

  const hasDrawings = drawingManager?.hasDrawings() ?? false;

  if (hasDrawings) {
    // Save snapshot BEFORE clearing (AC#1)
    const savedSnapshot = drawingManager.exportDrawings();
    const savedTimeframe = prevTimeframe;
    const tfSelect = document.getElementById('toolbar-timeframe') as HTMLSelectElement | null;

    // Clear drawings and switch immediately (AC#1)
    drawingManager.clearAll();
    // Freeze settings before async doLoad to prevent stale closure on undo
    const frozenSettings = { ...currentSettings };
    const newSettings = { ...frozenSettings, timeframe: newTimeframe };
    doLoad(newSettings);

    // Show undo toast (AC#1, #2, #3)
    toastManager.show(
      'Drawings đã bị xóa',
      'warning',
      {
        undoDuration: 5000,
        onUndo: () => {
          // Restore drawings + revert timeframe (AC#2)
          drawingManager.importDrawings(savedSnapshot);
          if (tfSelect) tfSelect.value = savedTimeframe;
          const restoreSettings = { ...frozenSettings, timeframe: savedTimeframe };
          doLoad(restoreSettings);
        },
      }
    );
  } else {
    // No drawings — switch normally (AC#5)
    const newSettings = { ...currentSettings, timeframe: newTimeframe };
    doLoad(newSettings);
  }
}

function init(): void {
  const container = document.getElementById('chart-container');
  if (!container) {
    console.error('[main] #chart-container not found');
    return;
  }

  // Init ExportPanel (Phase 2)
  new ExportPanel();

  // Init ResultsPanel (P1-5.4)
  const statusBarEl = document.getElementById('status-bar');
  if (statusBarEl) resultsPanel.init(statusBarEl);

  chartController = new ChartController();
  chartController.init(container);

  // HoverTooltip — must init after chart (subscribeCrosshairMove needs chart instance)
  const hoverTooltip = new HoverTooltip(container, chartController);
  hoverTooltip.init();

  // IndicatorOverlay — MA/EMA line series
  indicatorOverlay = new IndicatorOverlay(chartController);
  indicatorOverlay.init();

  // VolumeOverlay — volume histogram
  volumeOverlay = new VolumeOverlay(chartController);
  volumeOverlay.init();

  // DrawingManager — canvas overlay for Entry/TP/SL lines
  coordinateTranslator = new CoordinateTranslator();
  drawingManager = new DrawingManager(chartController, coordinateTranslator);
  drawingManager.init(container);

  // Drawing toolbar buttons
  function activateDrawTool(type: LineType): void {
    const current = drawingManager.getActiveType();
    drawingManager.setActiveType(current === type ? null : type);
  }

  document.getElementById('btn-draw-entry')?.addEventListener('click', () => activateDrawTool('entry'));
  document.getElementById('btn-draw-tp')?.addEventListener('click', () => activateDrawTool('tp'));
  document.getElementById('btn-draw-sl')?.addEventListener('click', () => activateDrawTool('sl'));

  drawingManager.setActiveTypeChangeCallback((activeType) => {
    ['entry', 'tp', 'sl'].forEach(t => {
      const btn = document.getElementById(`btn-draw-${t}`);
      btn?.classList.toggle('active', activeType === t);
    });
    if (activeType) {
      container.classList.add('chart-drawing-mode');
    } else {
      container.classList.remove('chart-drawing-mode');
    }
  });

  // ReplayEngine
  replayEngine = new ReplayEngine();
  resultsPanel.setReplayEngine(replayEngine);

  // Replay lock — freeze drawings when replay running
  eventBus.on('replayStateChanged', ({ state }) => {
    const resetBtn = document.getElementById('btn-replay-reset') as HTMLButtonElement | null;
    const fpEl = document.getElementById('session-fingerprint');
    if (state === 'playing') {
      drawingManager.freeze();
      showSessionFingerprint();
      document.getElementById('btn-replay-play')?.classList.add('playing');
      document.getElementById('btn-replay-play')!.textContent = '⏸';
      document.getElementById('status-mode')!.textContent = 'PLAYING';
      if (resetBtn) resetBtn.disabled = false;
    } else if (state === 'paused') {
      document.getElementById('btn-replay-play')?.classList.remove('playing');
      document.getElementById('btn-replay-play')!.textContent = '▶';
      document.getElementById('status-mode')!.textContent = 'PAUSED';
      if (resetBtn) resetBtn.disabled = false;
    } else if (state === 'stopped') {
      drawingManager.unfreeze();
      if (fpEl) fpEl.style.display = 'none';
      frozenFingerprint = '';
      document.getElementById('btn-replay-play')?.classList.remove('playing');
      document.getElementById('btn-replay-play')!.textContent = '▶';
      document.getElementById('status-mode')!.textContent = 'SETUP MODE';
      if (resetBtn) resetBtn.disabled = true;
      updatePreflightChecklist();
    }
  });

  // Replay Play/Pause button
  document.getElementById('btn-replay-play')?.addEventListener('click', () => {
    if (!replayEngine.isPlaying() && !replayEngine.isPaused()) {
      // Start new replay — need all 3 lines
      const snap = drawingManager.getSnapshot();
      const entry = snap.lines.get('entry');
      const tp = snap.lines.get('tp');
      const sl = snap.lines.get('sl');
      if (!entry || !tp || !sl) {
        toastManager.show('Cần vẽ đủ Entry + TP + SL trước khi Play', 'warning');
        return;
      }
      const bars = chartController.getCachedBars();
      if (!bars || bars.length === 0) {
        toastManager.show('Không có data để replay', 'error');
        return;
      }
      replayEngine.start({ entry: entry.price, tp: tp.price, sl: sl.price }, chartController, bars);
    } else if (replayEngine.isPaused()) {
      replayEngine.resume();
    } else {
      replayEngine.pause();
    }
  });

  // Replay Reset button
  document.getElementById('btn-replay-reset')?.addEventListener('click', () => {
    replayEngine.reset();
    chartController.revealBar(0);
  });

  // Completion overlay Reset button (dispatched by ResultsPanel)
  document.addEventListener('results:resetRequested', () => {
    replayEngine.reset();
    chartController.revealBar(0);
  });

  // Speed buttons
  document.querySelectorAll('.speed-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const speed = Number((btn as HTMLElement).dataset.speed);
      replayEngine.setSpeed(speed);
      document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('speed-btn--active'));
      btn.classList.add('speed-btn--active');
    });
  });

  // ESC to cancel drawing mode, Delete/Backspace to delete selected line, Space/1/2/3 for replay
  document.addEventListener('keydown', (e) => {
    // Skip shortcuts when typing in input/textarea
    const tag = (e.target as HTMLElement).tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

    if (e.key === 'Escape') {
      // Close cheat sheet if open, otherwise cancel drawing
      const cheatSheet = document.getElementById('cheat-sheet-overlay');
      if (cheatSheet && cheatSheet.style.display !== 'none') {
        cheatSheet.style.display = 'none';
        return;
      }
      drawingManager.setActiveType(null);
    }
    if (e.key === 'Delete' || e.key === 'Backspace') {
      if (drawingManager.deleteSelected()) {
        e.preventDefault();
      }
    }
    // Ctrl+Z / Cmd+Z to trigger undo toast action
    if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
      const undoBtn = document.querySelector('.toast-undo-btn') as HTMLButtonElement | null;
      if (undoBtn) {
        e.preventDefault();
        undoBtn.click();
      }
    }
    // Space: toggle play/pause
    if (e.key === ' ' && !e.repeat) {
      e.preventDefault();
      document.getElementById('btn-replay-play')?.click();
    }
    // 1/2/3: speed control
    if (e.key === '1') {
      replayEngine.setSpeed(SPEED_SLOW);
      document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('speed-btn--active'));
      document.getElementById('btn-speed-slow')?.classList.add('speed-btn--active');
    }
    if (e.key === '2') {
      replayEngine.setSpeed(SPEED_NORMAL);
      document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('speed-btn--active'));
      document.getElementById('btn-speed-normal')?.classList.add('speed-btn--active');
    }
    if (e.key === '3') {
      replayEngine.setSpeed(SPEED_FAST);
      document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('speed-btn--active'));
      document.getElementById('btn-speed-fast')?.classList.add('speed-btn--active');
    }
    // Arrow Left/Right: step back/forward when paused
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      replayEngine.stepForward();
    }
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      replayEngine.stepBack();
    }
    // R: Reset replay
    if (e.key === 'r' || e.key === 'R') {
      document.getElementById('btn-replay-reset')?.click();
    }
    // E/T/S: Draw Entry/TP/SL
    if (e.key === 'e' || e.key === 'E') {
      drawingManager.setActiveType(drawingManager.getActiveType() === 'entry' ? null : 'entry');
    }
    if (e.key === 't' || e.key === 'T') {
      drawingManager.setActiveType(drawingManager.getActiveType() === 'tp' ? null : 'tp');
    }
    if (e.key === 's' || e.key === 'S') {
      drawingManager.setActiveType(drawingManager.getActiveType() === 'sl' ? null : 'sl');
    }
    // ?: Toggle cheat sheet
    if (e.key === '?') {
      toggleCheatSheet();
    }
  });

  // Cheat sheet: click outside to close
  document.getElementById('cheat-sheet-overlay')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) toggleCheatSheet();
  });

  // Dismiss undo toast when user draws a new line (committed to new timeframe)
  eventBus.on('drawing:lineChanged', () => {
    toastManager.dismiss();
    updatePreflightChecklist();
    // Auto-save drawings to localStorage
    const snap = drawingManager.getSnapshot();
    settingsManager.save({
      ...currentSettings,
      drawings: {
        entry: snap.lines.get('entry')?.price ?? null,
        tp: snap.lines.get('tp')?.price ?? null,
        sl: snap.lines.get('sl')?.price ?? null,
      },
    });
  });

  eventBus.on('drawing:cleared', () => {
    updatePreflightChecklist();
    // Auto-save cleared drawings
    settingsManager.save({
      ...currentSettings,
      drawings: { entry: null, tp: null, sl: null },
    });
  });

  // Trade markers (P1-5.3)
  eventBus.on('replay:tradeHit', ({ type, price, barIndex }) => {
    chartController.addTradeMarker(barIndex, type, price);
  });

  eventBus.on('session:reset', () => {
    chartController.clearTradeMarkers();
  });

  // Toggle handlers
  const toggleMa20 = document.getElementById('toggle-ma20') as HTMLInputElement | null;
  const toggleEma20 = document.getElementById('toggle-ema20') as HTMLInputElement | null;

  function handleIndicatorToggle(field: 'ma20' | 'ema20', checked: boolean): void {
    if (field === 'ma20') indicatorOverlay.setMa20Visible(checked);
    else                  indicatorOverlay.setEma20Visible(checked);

    // AC #7: warn if too few bars
    if (checked && chartController.hasData()) {
      const bars = chartController.getCachedBars();
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

  // Volume toggle
  const toggleVolume = document.getElementById('toggle-volume') as HTMLInputElement | null;
  toggleVolume?.addEventListener('change', (e) => {
    volumeOverlay.setVisible((e.target as HTMLInputElement).checked);
  });

  // Load persisted settings
  const settings = settingsManager.load();
  currentSettings = settings;

  // Populate toolbar with restored settings
  const tfSelect = document.getElementById('toolbar-timeframe') as HTMLSelectElement | null;
  const startInput = document.getElementById('toolbar-date-start') as HTMLInputElement | null;
  const endInput = document.getElementById('toolbar-date-end') as HTMLInputElement | null;

  if (tfSelect) tfSelect.value = settings.timeframe;
  if (startInput) startInput.value = settings.dateStart;
  if (endInput) endInput.value = settings.dateEnd;

  // Auto-load with restored settings
  doLoad(settings);

  // Initialize pre-flight checklist (Play disabled until 3 lines drawn)
  updatePreflightChecklist();

  // Restore drawings from persisted settings
  if (settings.drawings) {
    const { entry, tp, sl } = settings.drawings;
    if (entry != null) drawingManager.setLine('entry', entry);
    if (tp != null) drawingManager.setLine('tp', tp);
    if (sl != null) drawingManager.setLine('sl', sl);
  }

  // P1-6.1: Empty state + getting started guide
  let ghostOverlay: HTMLElement | null = null;

  function showEmptyState(): void {
    if (ghostOverlay) return;
    ghostOverlay = document.createElement('div');
    ghostOverlay.className = 'empty-state-overlay';
    ghostOverlay.innerHTML = `
      <div class="ghost-drawings">
        <div class="ghost-line ghost-line--entry"></div>
        <div class="ghost-line ghost-line--tp"></div>
        <div class="ghost-line ghost-line--sl"></div>
      </div>
      <div class="getting-started-guide">
        <h3>Getting Started</h3>
        <ol>
          <li><strong>Fetch data</strong> — Chọn symbol + timeframe &rarr; Click Load</li>
          <li><strong>V&#7869; strategy</strong> — Click &#273;&#7875; &#273;&#7863;t Entry, TP, SL l&#234;n chart</li>
          <li><strong>Replay</strong> — Nh&#481;n Play &#273;&#7875; xem k&#7871;t qu&#7843; t&#7915; l&#7879;nh</li>
        </ol>
      </div>
    `;
    container.appendChild(ghostOverlay);
  }

  function hideEmptyState(): void {
    ghostOverlay?.remove();
    ghostOverlay = null;
  }

  // Show empty state if no cached data
  if (!chartController.hasData()) {
    showEmptyState();
  }

  // Hide empty state when data loads
  eventBus.on('chart:dataLoaded', () => {
    // Restore visibility before removal (in case hidden by chart:loadError)
    if (ghostOverlay) ghostOverlay.style.display = '';
    hideEmptyState();
  });

  // Hide ghost drawings when user draws first line
  eventBus.on('drawing:lineChanged', () => {
    if (ghostOverlay) {
      const ghosts = ghostOverlay.querySelector('.ghost-drawings');
      if (ghosts) (ghosts as HTMLElement).style.display = 'none';
    }
  });

  // Restore ghost drawings when all lines cleared (P1-6.1 patch)
  eventBus.on('drawing:cleared', () => {
    if (ghostOverlay) {
      const ghosts = ghostOverlay.querySelector('.ghost-drawings');
      if (ghosts) (ghosts as HTMLElement).style.display = '';
    }
  });

  // Hide ghost overlay when ChartController error overlay appears (P1-6.1 patch)
  eventBus.on('chart:loadError', () => {
    if (ghostOverlay) {
      ghostOverlay.style.display = 'none';
    }
  });

  // Timeframe change handler
  tfSelect?.addEventListener('change', (e) => {
    const newTf = (e.target as HTMLSelectElement).value;
    handleTimeframeChange(newTf);
  });

  // Load button + date validation
  function handleLoad(): void {
    const tf = tfSelect?.value ?? currentSettings.timeframe;
    const ds = startInput?.value ?? currentSettings.dateStart;
    const de = endInput?.value ?? currentSettings.dateEnd;

    // Validate non-empty
    if (!ds || !de) {
      toastManager.show('Vui lòng chọn ngày bắt đầu và kết thúc', 'error');
      return;
    }

    // Validate date format
    if (isNaN(Date.parse(ds)) || isNaN(Date.parse(de))) {
      toastManager.show('Định dạng ngày không hợp lệ', 'error');
      return;
    }

    // AC #8: date validation
    if (ds > de) {
      toastManager.show('Date start phải trước date end', 'error');
      return;
    }

    const newSettings: PersistedSettings = { timeframe: tf, dateStart: ds, dateEnd: de, drawings: currentSettings.drawings };
    doLoad(newSettings);
  }

  const btnLoad = document.getElementById('btn-load');
  btnLoad?.addEventListener('click', handleLoad);

  // AC #4: Enter key on date inputs triggers load
  startInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleLoad();
  });
  endInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleLoad();
  });

}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', safeInit);
} else {
  safeInit();
}

function safeInit(): void {
  try {
    init();
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : String(e);
    console.error(`[main] Fatal init error: ${message}`);
    const container = document.getElementById('chart-container');
    if (container) {
      container.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--sem-text-muted);">Lỗi khởi tạo — vui lòng reload trang</div>`;
    }
  }
}
