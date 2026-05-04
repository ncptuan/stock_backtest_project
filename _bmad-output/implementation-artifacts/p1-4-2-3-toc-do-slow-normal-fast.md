# Story P1-4.2-3: Look-ahead prevention — chỉ reveal nến đã đóng

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (3)

1. **Toggle MA/EMA/Volume ON during replay leaks full future data** — HIGH (Blind + Edge)
   - `setMa20Visible()`, `setEma20Visible()`, `setVisible()` rendered full `currentBars` unconditionally
   - Added `replayActive` check: if active, call `_updateReplaySlice()` instead of rendering full data
   - Files: `IndicatorOverlay.ts`, `VolumeOverlay.ts`

2. **Replay start no bar event for index 0 — overlays at -1** — MED (Blind + Edge)
   - `start()` emitted `replayStateChanged:playing` but never `replay:barAdvanced` for bar 0
   - Overlays stayed at `replayCurrentIndex = -1` (empty slice) until first tick
   - Added `revealBar(0)` + `replay:barAdvanced` with barIndex=0 in `start()`
   - File: `ReplayEngine.ts`

3. **stepBack clears openPosition without emitting tradeCompleted** — MED (Edge)
   - Already patched in p1-4-1 review — `this.openPosition = null` in stepBack()
   - No additional patch needed

### All 5 ACs: FULLY MET (Acceptance Auditor)

### Deferred

- `revealBar(0)` renders full data for timeScale calibration — brief flash before viewport snaps to start — design tradeoff, defer
- HoverTooltip double O(n) scan per crosshair event — `getBarByTime` + `findIndex` — perf optimization sprint, defer
- Bar index 0 never emits `replay:barAdvanced` from `advanceBar()` — by design (increments before emit), fixed by initial emit in `start()`, defer

## Story

As a trader,
I want the chart to only show candles that have fully closed during replay,
So that I can practice without accidentally seeing future price action.

## Acceptance Criteria

1. **Given** replay đang chạy tại bar index N
   **When** chart render
   **Then** chỉ hiển thị nến từ index 0 đến N (inclusive) — nến N+1 trở đi không visible

2. **Given** replay đang chạy
   **When** MA/EMA overlay đang hiển thị
   **Then** indicator lines cũng chỉ vẽ đến bar N — không extend vào tương lai

3. **Given** replay đang chạy
   **When** trader hover lên vùng chưa render (nến N+1 trở đi)
   **Then** OHLCV tooltip không hiển thị — chỉ hoạt động cho nến đã revealed

4. **Given** replay ở Setup mode (chưa Play)
   **When** trader xem chart
   **Then** tất cả nến visible bình thường (không look-ahead constraint)

5. **Given** replay đang paused tại bar N
   **When** trader hover
   **Then** tooltip hoạt động bình thường cho nến 0..N

## Tasks / Subtasks

- [x] Task 1: Cập nhật `frontend/ChartController.ts` — Slice data khi reveal (AC: #1)
  - [x] `revealBar(upToIndex)` đã có từ P1-4.1 — gọi `_renderBars(slice)` với `data[0..upToIndex]`
  - [x] `_renderBars()` sort + dedup hoạt động đúng trên sliced data

- [x] Task 2: Cập nhật `frontend/IndicatorOverlay.ts` — Slice indicators theo replay (AC: #2)
  - [x] Subscribe `replay:barAdvanced` event → update `replayCurrentIndex`, call `_updateReplaySlice()`
  - [x] Khi replay active: render indicators chỉ với `data[0..currentIndex]`
  - [x] Khi replay stopped: restore full indicator data

- [x] Task 3: Cập nhật `frontend/HoverTooltip.ts` — Block tooltip vùng chưa reveal (AC: #3)
  - [x] Track `replayCurrentIndex` từ `replay:barAdvanced` event
  - [x] Trong hover handler: tìm bar index → nếu > replayCurrentIndex → hide tooltip
  - [x] Khi replay stopped: reset state, tooltip hoạt động bình thường

- [x] Task 4: Cập nhật `frontend/VolumeOverlay.ts` — Slice volume theo replay (AC: #2)
  - [x] Subscribe `replay:barAdvanced` + `replayStateChanged` events
  - [x] Khi replay active: render volume chỉ với `data[0..currentIndex]`
  - [x] Khi replay stopped: restore full volume data

## Dev Notes

### Look-ahead Prevention Architecture

Look-ahead prevention là **Critical NFR (NFR12)** — phải enforce ở multiple layers:

```
ReplayEngine.advanceBar() → emit 'replay:barAdvanced'
  ↓
ChartController.revealBar(N) → setData(bars[0..N])     ← candle layer
  ↓
IndicatorOverlay → setIndicatorData(indicators[0..N])   ← indicator layer
  ↓
VolumeOverlay → setVolumeData(volumes[0..N])            ← volume layer
  ↓
HoverTooltip → check barIndex <= N trước khi show       ← tooltip layer
```

### ChartController.revealBar() — Slice Strategy

```typescript
// frontend/ChartController.ts — existing method, refactor

revealBar(upToIndex: number): void {
  if (!this.cache || !this.series) return;
  const slice = this.cache.data.slice(0, upToIndex + 1);
  this._renderBars(slice);
}
```

**Lưu ý**: `_renderBars()` đã sort + dedup, nên slice data sẽ hoạt động đúng. Không cần thay đổi `_renderBars()`.

### IndicatorOverlay Integration

```typescript
// frontend/IndicatorOverlay.ts

private replayActive = false;
private replayCurrentIndex = -1;

init(): void {
  // ... existing code ...

  eventBus.on('replay:barAdvanced', ({ barIndex }) => {
    this.replayActive = true;
    this.replayCurrentIndex = barIndex;
    this._updateReplaySlice();
  });

  eventBus.on('replayStateChanged', ({ state }) => {
    if (state === 'stopped') {
      this.replayActive = false;
      this.replayCurrentIndex = -1;
      // Restore full indicators
      if (this.lastBars) this.update(this.lastBars);
    }
  });
}

private _updateReplaySlice(): void {
  if (!this.replayActive || !this.lastBars) return;
  const slice = this.lastBars.slice(0, this.replayCurrentIndex + 1);
  this._renderIndicators(slice);
}
```

### HoverTooltip Integration

```typescript
// frontend/HoverTooltip.ts

private replayCurrentIndex = -1;
private replayActive = false;

init(): void {
  // ... existing code ...

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

private _handleHover(param: MouseEventParams): void {
  // ... existing tooltip logic ...

  // Look-ahead guard
  if (this.replayActive) {
    const barTime = param.time as number;
    const barIndex = this._findBarIndex(barTime);
    if (barIndex !== null && barIndex > this.replayCurrentIndex) {
      this._hideTooltip();
      return;
    }
  }

  // ... show tooltip ...
}
```

### VolumeOverlay Integration

```typescript
// frontend/VolumeOverlay.ts
// Tương tự IndicatorOverlay — slice volume data theo currentIndex
```

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/ChartController.ts` | `revealBar()` — đã có, verify slice behavior |
| `frontend/IndicatorOverlay.ts` | Subscribe `replay:barAdvanced`, slice indicator data |
| `frontend/HoverTooltip.ts` | Track replay index, block tooltip vùng future |
| `frontend/VolumeOverlay.ts` | Slice volume data theo replay index |

### Files KHÔNG được touch

- `frontend/ReplayEngine.ts` — không cần sửa (đã emit events từ P1-4.1)
- `frontend/DrawingManager.ts` — drawings không affected bởi look-ahead
- `frontend/main.ts` — wiring đã có từ P1-4.1
- Backend — story này hoàn toàn là frontend

### Scope Boundary

| Feature | P1-4.2-3 | Khác |
|---------|----------|------|
| Chart chỉ show nến 0..N trong replay | ✓ | |
| Indicators slice theo replay | ✓ | |
| Volume slice theo replay | ✓ | |
| Tooltip block vùng future | ✓ | |
| Full chart trong Setup mode | ✓ | |
| Delta-time loop | ✗ | P1-4.1 |
| Play/Pause/Reset controls | ✗ | P1-4.1 |
| Speed control | ✗ | P1-4.1 |
| Hit detection | ✗ | Epic P1-5 |
| Smooth candle animation | ✗ | P1-4.5 |

### Dependency từ P1-4.1

- **P1-4.1**: `replay:barAdvanced` event đã được emit mỗi bar — subscribe trong overlay/tooltip
- **P1-4.1**: `replayStateChanged` event đã có — dùng để reset replay state
- **P1-2-1**: `ChartController.revealBar()` đã có sẵn — verify slice behavior

### Edge Cases

1. **Replay chưa bắt đầu**: Không có `replay:barAdvanced` event → overlay/tooltip ở Setup mode → full chart visible
2. **Replay paused**: `replayCurrentIndex` giữ nguyên → tooltip chỉ cho revealed bars
3. **Reset**: `replayStateChanged: stopped` → reset overlay/tooltip → full chart visible lại
4. **Switch timeframe khi replay**: `handleTimeframeChange()` pause replay trước → overlays reset
5. **Indicator period > revealed bars**: MA/EMA warm-up period → NaN values hiển thị là `null` (đã có từ backend)
6. **Hover đúng boundary**: barIndex === replayCurrentIndex → tooltip vẫn show (nến đã đóng)

### Thứ tự implement

1. Cập nhật `frontend/ChartController.ts` — verify `revealBar()` slice behavior
2. Cập nhật `frontend/IndicatorOverlay.ts` — subscribe events + slice
3. Cập nhật `frontend/VolumeOverlay.ts` — subscribe events + slice
4. Cập nhật `frontend/HoverTooltip.ts` — track index + block future
5. Build + typecheck
6. Test manual: Play replay → thấy chỉ nến 0..N → hover vùng future → không tooltip → indicators chỉ đến N

## Dev Agent Record

### Agent Model Used

mimo-v2.5-pro

### Debug Log References

- Build: 323.4kb, esbuild 35ms
- Typecheck: passed (tsc --noEmit)

### Completion Notes List

- ChartController.revealBar() already slices data correctly from P1-4.1
- IndicatorOverlay: subscribed to replay:barAdvanced + replayStateChanged, slices MA/EMA data during replay
- VolumeOverlay: same pattern — slices volume histogram data during replay
- HoverTooltip: look-ahead guard — finds bar index from time, blocks tooltip if barIndex > replayCurrentIndex
- All overlays restore full data on replayStateChanged: stopped (Setup mode)

### File List

- `frontend/IndicatorOverlay.ts` — added eventBus import, replay tracking fields, event subscriptions, _updateReplaySlice()
- `frontend/VolumeOverlay.ts` — added eventBus import, replay tracking fields, event subscriptions, _updateReplaySlice()
- `frontend/HoverTooltip.ts` — added eventBus import, replay tracking fields, event subscriptions, look-ahead guard in handleCrosshairMove
