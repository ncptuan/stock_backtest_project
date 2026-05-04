# Story P1-4.1: ReplayEngine — delta-time bar advancement loop

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (2)

1. **`stepBack()` doesn't clear openPosition — state divergence** — MED (Blind + Edge)
   - Added `this.openPosition = null` in `stepBack()` to prevent position referencing bars ahead of current index
   - File: `ReplayEngine.ts`

2. **Elapsed burst on speed change + setSpeed(0) causes frame-rate advancement** — MED (Blind + Edge)
   - Added `Math.max(ms, SPEED_FAST)` clamp to prevent 0/negative values
   - Added `this.elapsed = 0` reset to prevent burst advancement when switching to slower speed
   - File: `ReplayEngine.ts`

### All 8 ACs: FULLY MET (Acceptance Auditor)

### Deferred

- SHORT direction dead code — checkHits hardcodes LONG, no SHORT entry path — Epic P1-5 scope (hit detection refinement)
- Entry price uses lineSnapshot.entry instead of next-bar open — Epic P1-5 scope (fill price logic)
- Entry at last bar silently dropped — no feedback to user, Epic P1-5 edge case
- TP=Entry degenerate trades — no validation prevents equal TP/SL/Entry, Epic P1-5 validation
- Background tab RAF still advances bars at ~1/sec — UX enhancement, could auto-pause on visibilitychange
- reset() handleTradeClose with stale currentIndex — acceptable semantics (fires loss event before clearing)

## Story

As a trader,
I want bar replay to advance smoothly at consistent speed,
So that I experience the market flow accurately even when the browser tab is throttled.

## Acceptance Criteria

1. **Given** trader nhấn Play
   **When** replay loop chạy qua `requestAnimationFrame`
   **Then** engine dùng delta-time accumulation: track `lastTimestamp`, accumulate `elapsed`, advance bar chỉ khi `elapsed >= targetInterval`
   **And** Slow = 500ms/bar, Normal = 150ms/bar, Fast = 30ms/bar — tất cả 3 speeds reveal từng nến một (Fast không skip nến)

2. **Given** tab bị throttle (background tab)
   **When** replay loop tick
   **Then** replay không advance nhiều bar cùng lúc — chỉ advance 1 bar mỗi tick (clamp delta)

3. **Given** replay đang chạy
   **When** trader nhấn Pause
   **Then** replay dừng tại bar hiện tại — chart giữ nguyên vị trí

4. **Given** replay đang paused
   **When** trader nhấn Play (resume)
   **Then** replay tiếp tục từ bar hiện tại — không reset về đầu

5. **Given** replay đang chạy hoặc đã pause
   **When** trader nhấn Reset
   **Then** currentIndex reset về 0, chart scroll về đầu, UI trở về Setup mode
   **And** drawings giữ nguyên (DrawingManager.unfreeze())

6. **Given** trader thay đổi speed (1/2/3 hoặc UI)
   **When** replay đang chạy
   **Then** speed thay đổi ngay lập tức — không cần restart replay

7. **Given** replay đạt bar cuối cùng trong data
   **When** currentIndex >= data.length
   **Then** replay tự động dừng, emit `replayStateChanged` với state `'stopped'`

8. **Given** replay đang chạy
   **When** mỗi bar được advance
   **Then** emit `replay:barAdvanced` với `{ barIndex, timestamp }`
   **And** gọi `chartController.revealBar(currentIndex)` để update chart

## Tasks / Subtasks

- [x] Task 1: Refactor `frontend/ReplayEngine.ts` — Thêm delta-time loop (AC: #1, #2)
  - [x] Thêm private fields: `lastTimestamp`, `elapsed`, `speed`, `isPaused`, `lineSnapshot`
  - [x] Implement `tick()` method với delta-time accumulation pattern
  - [x] Clamp delta khi tab throttle: `if (delta > targetInterval * 3) delta = targetInterval`
  - [x] Advance 1 bar mỗi tick tối đa (không skip bars ở Fast speed)
  - [x] Gọi `requestAnimationFrame` trong loop

- [x] Task 2: Implement Play/Pause/Reset controls (AC: #3, #4, #5)
  - [x] `pause()`: set `isPausedState = true`, cancel RAF, emit `replayStateChanged: paused`
  - [x] `resume()`: set `isPausedState = false`, reset `lastTimestamp`, emit `replayStateChanged: playing`
  - [x] `start()`: refactor — nhận `lineSnapshot` + `chartController` reference, init loop
  - [x] `reset()`: stop loop, reset `currentIndex = 0`, emit `replayStateChanged: stopped` + `session:reset`
  - [x] Expose `isPlaying()`, `isPaused()` getters

- [x] Task 3: Implement speed control (AC: #6)
  - [x] `setSpeed(ms: number)`: update `targetInterval` ngay trong loop
  - [x] Constants: `SPEED_SLOW = 500`, `SPEED_NORMAL = 150`, `SPEED_FAST = 30`
  - [x] `getSpeed()`: return current speed

- [x] Task 4: Auto-stop khi hết data (AC: #7)
  - [x] Trong `tick()`: check `currentIndex >= data.length` → stop + emit

- [x] Task 5: Emit events mỗi bar (AC: #8)
  - [x] Trong `advanceBar()`: emit `replay:barAdvanced` + gọi `chartController.revealBar()`
  - [x] `handleTradeClose()` đã có sẵn — wire vào khi implement hit detection (Epic P1-5)

- [x] Task 6: Cập nhật `frontend/types.ts` — Không cần thêm events mới
  - [x] `replayStateChanged`, `replay:barAdvanced`, `session:reset` đã có trong EventMap

- [x] Task 7: Cập nhật `frontend/main.ts` — Wire Play/Pause/Reset buttons + keyboard
  - [x] Play button: toggle play/pause/resume
  - [x] Reset button: `replayEngine.reset()` + `revealBar(0)`
  - [x] Space key: toggle play/pause
  - [x] 1/2/3 keys: set speed (Slow/Normal/Fast)
  - [x] Validate đủ 3 đường Entry+TP+SL trước khi Play
  - [x] Update status bar: SETUP MODE → PLAYING → PAUSED
  - [x] Auto-pause replay khi switch timeframe

- [x] Task 8: Cập nhật `static/index.html` — Thêm Play/Pause/Reset + speed buttons vào toolbar
  - [x] Play/Pause button (toggle icon ▶/⏸)
  - [x] Reset button (⏮)
  - [x] Speed selector: 3 buttons (1/2/3) với active state

- [x] Task 9: Cập nhật `static/style.css` — Replay control styles
  - [x] `.replay-btn` styles + `.playing` state
  - [x] `.speed-btn` styles
  - [x] `.speed-btn--active` highlight

## Dev Notes

### Existing ReplayEngine.ts Stub (KHÔNG xóa — refactor)

File `frontend/ReplayEngine.ts` đã có sẵn stub với:
- `start(lineSnapshot, data)` — emit `replayStateChanged: playing`, TODO comment cho bar loop
- `stop()` — emit `replayStateChanged: stopped`
- `reset()` — emit `replayStateChanged: stopped` + `session:reset`, auto-close open position
- `handleTradeClose(exitBarIndex, result)` — emit `tradeCompleted` + `replay:tradeHit`
- `openTrade(barIndex, lineSnapshot, direction)` — guard: 1 position at a time
- `getCurrentIndex()` — expose for external access

**Strategy**: Refactor existing code, KHÔNG tạo file mới. Giữ nguyên Phase 2 integration points (`tradeCompleted`, `replayStateChanged` events).

### Delta-time Accumulation Pattern (Gap 3)

```typescript
// frontend/ReplayEngine.ts

private lastTimestamp = 0;
private elapsed = 0;
private targetInterval = 150; // default Normal speed
private rafId = 0;

private tick(now: number): void {
  if (!this.isRunning || this.isPaused) return;

  if (this.lastTimestamp === 0) {
    this.lastTimestamp = now;
    this.rafId = requestAnimationFrame(this.tick.bind(this));
    return;
  }

  const delta = now - this.lastTimestamp;
  this.lastTimestamp = now;

  // Clamp: nếu tab bị throttle, chỉ advance 1 bar
  const clampedDelta = delta > this.targetInterval * 3
    ? this.targetInterval
    : delta;

  this.elapsed += clampedDelta;

  while (this.elapsed >= this.targetInterval && this.currentIndex < this.data.length) {
    this.advanceBar();
    this.elapsed -= this.targetInterval;
  }

  // Auto-stop khi hết data
  if (this.currentIndex >= this.data.length) {
    this.stop();
    return;
  }

  this.rafId = requestAnimationFrame(this.tick.bind(this));
}
```

### advanceBar() Method

```typescript
private advanceBar(): void {
  this.currentIndex++;

  // Emit Phase 1 event
  eventBus.emit('replay:barAdvanced', {
    barIndex: this.currentIndex,
    timestamp: this.data[this.currentIndex]?.timestamp ?? 0,
  });

  // Update chart — reveal bar
  this.chartController?.revealBar(this.currentIndex);

  // TODO (Story 5.1): hit detection — checkHits() sẽ được thêm trong Epic P1-5
  // Hiện tại handleTradeClose() đã có sẵn, chỉ cần wire vào khi implement hit detection
}
```

### Speed Constants

```typescript
export const SPEED_SLOW = 500;    // ~500ms/bar
export const SPEED_NORMAL = 150;  // ~150ms/bar
export const SPEED_FAST = 30;     // ~30ms/bar
```

### Refactored start() Method

```typescript
start(lineSnapshot: LineSnapshot, chartController: ChartController, data: OHLCVBar[]): void {
  if (this.isRunning) return;

  this.data = data;
  this.currentIndex = 0;
  this.openPosition = null;
  this.lineSnapshot = lineSnapshot;
  this.chartController = chartController;
  this.isRunning = true;
  this.isPaused = false;
  this.lastTimestamp = 0;
  this.elapsed = 0;

  // Phase 2: notify ExportPanel
  eventBus.emit('replayStateChanged', { state: 'playing' });

  // Start delta-time loop
  this.rafId = requestAnimationFrame(this.tick.bind(this));
}
```

### Pause / Resume

```typescript
pause(): void {
  if (!this.isRunning || this.isPaused) return;
  this.isPaused = true;
  eventBus.emit('replayStateChanged', { state: 'paused' });
}

resume(): void {
  if (!this.isRunning || !this.isPaused) return;
  this.isPaused = false;
  this.lastTimestamp = 0; // reset timestamp để không accumulate gap
  eventBus.emit('replayStateChanged', { state: 'playing' });
  this.rafId = requestAnimationFrame(this.tick.bind(this));
}
```

### main.ts Integration Points

```typescript
// Wire replay controls trong main.ts
const btnPlay = document.getElementById('btn-replay-play');
const btnReset = document.getElementById('btn-replay-reset');

btnPlay?.addEventListener('click', () => {
  if (!replayEngine.isRunning()) {
    // Start mới — cần đủ 3 đường
    if (!drawingManager.getEntryPrice() || !drawingManager.getTpPrice() || !drawingManager.getSlPrice()) {
      toastManager.show('Cần vẽ đủ Entry + TP + SL trước khi Play', 'warning');
      return;
    }
    const snapshot: LineSnapshot = {
      entry: drawingManager.getEntryPrice()!,
      tp: drawingManager.getTpPrice()!,
      sl: drawingManager.getSlPrice()!,
    };
    drawingManager.freeze();
    replayEngine.start(snapshot, chartController, chartController.getCachedBars()!);
  } else if (replayEngine.isPaused()) {
    replayEngine.resume();
  } else {
    replayEngine.pause();
  }
});

btnReset?.addEventListener('click', () => {
  replayEngine.reset();
  // Chart scroll về đầu
  chartController.revealBar(0);
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.key === ' ' && !e.repeat) {
    e.preventDefault();
    btnPlay?.click();
  }
  if (e.key === '1') replayEngine.setSpeed(500);
  if (e.key === '2') replayEngine.setSpeed(150);
  if (e.key === '3') replayEngine.setSpeed(30);
});
```

### EventMap Additions (types.ts)

```typescript
// Thêm vào EventMap:
'replay:started': { barIndex: number };
'replay:paused': { barIndex: number };
'replay:reset': {};
```

### Project Structure Notes

- File chính cần modify: `frontend/ReplayEngine.ts` (refactor stub)
- KHÔNG tạo file mới — tất cả logic nằm trong existing ReplayEngine.ts
- `frontend/main.ts` — wire controls + keyboard
- `frontend/types.ts` — thêm events + Speed type
- `static/index.html` — thêm replay buttons vào toolbar
- `static/style.css` — replay button styles

### Files KHÔNG được touch

- `frontend/ChartController.ts` — `revealBar()` đã có sẵn
- `frontend/DrawingManager.ts` — `freeze()`/`unfreeze()` đã có sẵn
- `frontend/EventBus.ts` — generic, không cần sửa
- Backend — story này hoàn toàn là frontend

### Scope Boundary

| Feature | P1-4.1 | Khác |
|---------|--------|------|
| Delta-time bar advancement loop | ✓ | |
| 3 speeds (Slow/Normal/Fast) | ✓ | |
| Play/Pause/Resume | ✓ | |
| Reset (keep drawings) | ✓ | |
| Keyboard shortcuts (Space/1/2/3) | ✓ | |
| Auto-stop khi hết data | ✓ | |
| Tab throttle protection | ✓ | |
| Smooth candle animation | ✗ | P1-4.5 |
| Pre-flight checklist | ✗ | P1-4.4 |
| Look-ahead prevention | ✗ | P1-4.3 |
| Hit detection | ✗ | Epic P1-5 |

### Dependency từ Stories trước

- **p1-2-1**: `ChartController` đã có `revealBar(upToIndex)` — reuse
- **p1-3-1**: `DrawingManager` đã có `freeze()`/`unfreeze()` — reuse
- **p1-3-5**: `handleTimeframeChange()` đã auto-pause replay khi switch — wire vào `replayEngine.pause()`
- **Phase 2 stub**: `ReplayEngine` đã có `handleTradeClose()`, `openTrade()` — giữ nguyên

### Edge Cases

1. **Click Play khi data rỗng**: `start()` check `data.length === 0` → return early, không crash
2. **Click Play 2 lần liên tiếp**: `isRunning` guard prevent double start
3. **Switch timeframe khi đang replay**: `handleTimeframeChange()` trong main.ts gọi `replayEngine.pause()` trước → safe
4. **Tab background 5 phút**: clamp delta prevent mass bar advancement
5. **Reset khi đang pause**: reset về đầu, UI về Setup mode
6. **Speed change khi paused**: speed update, resume sẽ dùng speed mới
7. **Resize window khi replay**: ChartController auto-resize đã có, không ảnh hưởng

### Thứ tự implement

1. Thêm types vào `frontend/types.ts` (Speed type, new events)
2. Refactor `frontend/ReplayEngine.ts` — delta-time loop + play/pause/reset + speed
3. Thêm replay buttons vào `static/index.html`
4. Thêm replay styles vào `static/style.css`
5. Wire controls + keyboard vào `frontend/main.ts`
6. Build + typecheck: `npx esbuild frontend/main.ts --bundle --outfile=static/app.js && npx tsc --noEmit`
7. Test manual: Load data → vẽ 3 đường → Play → thấy nến reveal → Pause → Resume → Reset

## Dev Agent Record

### Agent Model Used

mimo-v2.5-pro

### Debug Log References

- Build: 320.7kb, esbuild 30ms
- Typecheck: passed (tsc --noEmit)

### Completion Notes List

- Refactored ReplayEngine.ts: delta-time accumulation with requestAnimationFrame loop
- 3 speeds: Slow (500ms), Normal (150ms), Fast (30ms) — exported as constants
- Tab throttle protection: clamp delta > 3x interval to single interval
- Play/Pause/Resume/Reset with proper state management and EventBus emissions
- Auto-stop when currentIndex >= data.length
- advanceBar() emits `replay:barAdvanced` + calls `chartController.revealBar()`
- Keyboard: Space (play/pause), 1/2/3 (speed control)
- Status bar updates: SETUP MODE → PLAYING → PAUSED
- Auto-pause replay on timeframe switch
- Play button validates all 3 lines (Entry+TP+SL) before starting
- HTML: replay buttons + speed selector added to toolbar
- CSS: `.replay-btn`, `.speed-btn`, `.speed-btn--active` styles

### File List

- `frontend/ReplayEngine.ts` — full refactor: delta-time loop, pause/resume, speed control, chartController integration
- `frontend/main.ts` — added ReplayEngine import, replay control wiring, keyboard shortcuts, status bar updates, auto-pause on timeframe switch
- `static/index.html` — added replay buttons (Play/Pause, Reset) and speed selector (1/2/3) to toolbar
- `static/style.css` — added `.replay-btn`, `.speed-btn`, `.speed-btn--active` styles
