# Story P1-4.3: Reset giữ drawings + zoom level

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (2)

1. **Completion overlay "Reset" button dead-end** — HIGH (Edge)
   - `showCompletionOverlay()` dispatches `results:resetRequested` but no listener existed
   - Added listener in `main.ts` to call `replayEngine.reset()` + `chartController.revealBar(0)`
   - File: `main.ts`

2. **Redundant `clearSummary()` in session:reset handler** — LOW (Blind + Edge)
   - `clearTradeList()` already calls `clearSummary()` internally
   - Removed redundant call from session:reset handler
   - File: `ResultsPanel.ts`

### All 4 ACs: FULLY MET (Acceptance Auditor)

### Deferred

- Summary flash on reset — `replayStateChanged:stopped` fires before `session:reset`, `showSummary()` briefly renders empty-state message, immediately cleared — event ordering design tradeoff, defer
- Zoom preservation drops range when zero-width `savedRange` — `{from:5, to:5}` fails `to > from` guard, chart auto-fits — edge case on uninitialized chart, defer
- `revealBar(0)` full dataset perf spike — renders entire cache then narrows viewport — only matters for 100k+ bars, defer
- Visual flash between overlay restore and chart restore on reset — single-frame inconsistency on slow renders, defer

## Story

As a trader,
I want to reset replay to the beginning without losing my drawn lines,
So that I can quickly iterate on the same strategy setup.

## Acceptance Criteria

1. **Given** trader đang replay (playing hoặc paused) với 3 đường Entry/TP/SL đã vẽ
   **When** trader nhấn Reset
   **Then** currentIndex reset về 0, chart scroll về đầu date range
   **And** zoom level giữ nguyên — không reset zoom
   **And** drawings (Entry/TP/SL) giữ nguyên — KHÔNG bị xóa
   **And** UI trở về Setup mode — trader có thể Play lại ngay

2. **Given** trade markers (entry/exit dots) đang hiển thị trên chart từ session trước
   **When** trader nhấn Reset
   **Then** tất cả trade markers bị xóa khỏi chart
   **And** results panel clear — không còn trade list

3. **Given** trader đang ở Setup mode (chưa Play)
   **When** trader nhấn Reset
   **Then** nothing xảy ra — Reset button disabled hoặc no-op

4. **Given** trader đã vẽ lại đường mới sau khi Reset
   **When** trader nhấn Play
   **Then** replay bắt đầu lại từ đầu với drawings mới

## Tasks / Subtasks

- [x] Task 1: Verify `frontend/ReplayEngine.ts` — Reset logic (AC: #1, #2)
  - [x] `reset()`: đã có từ P1-4.1 — verify reset currentIndex, emit events
  - [x] Verify `DrawingManager.unfreeze()` được gọi khi reset
  - [x] Verify trade markers được clear

- [x] Task 2: Cập nhật `frontend/ChartController.ts` — Preserve zoom khi reset (AC: #1)
  - [x] `revealBar(0)`: render full data, restore zoom width, scroll to start
  - [x] `revealBar(N>0)`: render slice, restore zoom range

- [x] Task 3: Cập nhật `frontend/main.ts` — Reset button wiring (AC: #1, #3)
  - [x] Reset button: gọi `replayEngine.reset()` + `chartController.revealBar(0)`
  - [x] Disable Reset khi replay chưa start (isRunning = false)
  - [x] Enable Reset khi replay playing/paused

- [x] Task 4: Cập nhật `frontend/ResultsPanel.ts` — Clear results on reset (AC: #2)
  - [x] Subscribe `session:reset` event
  - [x] Dismiss completion overlay nếu đang hiển thị

## Dev Notes

### Overlap với P1-4.1

P1-4.1 đã implement phần lớn Reset functionality:
- `reset()` method trong ReplayEngine
- `session:reset` event emission
- Reset button trong toolbar

Story này focus vào:
- **Zoom preservation** — chart zoom level không reset khi clear data
- **Trade markers cleanup** — xóa entry/exit dots
- **Results panel clear** — xóa trade list

### Zoom Preservation Strategy

```typescript
// frontend/ChartController.ts

revealBar(upToIndex: number): void {
  if (!this.cache || !this.series) return;

  // Save current zoom range TRƯỚC khi update data
  const savedRange = this.chart?.timeScale().getVisibleLogicalRange();

  const slice = this.cache.data.slice(0, upToIndex + 1);
  this._renderBars(slice);

  // Restore zoom range SAU khi update data (nếu có)
  if (savedRange && upToIndex > 0) {
    this.chart?.timeScale().setVisibleLogicalRange(savedRange);
  }
}
```

**Lưu ý**: Khi `upToIndex === 0` (reset về đầu), không restore zoom — để chart tự fit về đầu date range.

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/ReplayEngine.ts` | Verify reset logic đã có từ P1-4.1 |
| `frontend/ChartController.ts` | Zoom preservation trong `revealBar()` |
| `frontend/main.ts` | Reset button enable/disable logic |
| `frontend/ResultsPanel.ts` | Subscribe `session:reset`, clear UI |

### Files KHÔNG được touch

- `frontend/DrawingManager.ts` — `unfreeze()` đã có, không cần sửa
- `frontend/EventBus.ts` — generic
- Backend — frontend only

### Scope Boundary

| Feature | P1-4.3 | Khác |
|---------|--------|------|
| Reset về đầu date range | ✓ | |
| Giữ nguyên drawings | ✓ | |
| Giữ nguyên zoom level | ✓ | |
| Clear trade markers | ✓ | |
| Clear results panel | ✓ | |
| Play/Pause/Speed | ✗ | P1-4.1 |
| Look-ahead prevention | ✗ | P1-4.2-3 |
| Pre-flight checklist | ✗ | P1-4.4 |

### Edge Cases

1. **Reset khi chưa có data**: `revealBar(0)` với cache rỗng → no-op
2. **Reset khi đang drag line**: DrawingManager freeze đang active → unfreeze → drag bị cancel
3. **Rapid Reset nhiều lần**: no-op vì `isRunning = false` sau lần đầu
4. **Reset + Play ngay**: drawings vẫn còn → có thể Play lại ngay

## Dev Agent Record

### Agent Model Used

mimo-v2.5-pro

### Debug Log References

- Build: 324.2kb, esbuild 29ms
- Typecheck: passed (tsc --noEmit)

### Completion Notes List

- ReplayEngine.reset() already works from P1-4.1 — emits session:reset and replayStateChanged:stopped
- ChartController.revealBar(0): renders full data to establish time range, then restores zoom width and scrolls to start
- ChartController.revealBar(N>0): normal slice with zoom preservation
- ResultsPanel: subscribes to session:reset, calls dismissCompletionOverlay()
- Reset button: disabled initially, enabled on replayStateChanged:playing/paused, disabled on stopped
- Added disabled + disabled:hover CSS for replay buttons

### File List

- `frontend/ChartController.ts` — revealBar() zoom preservation: save/restore visibleLogicalRange, full render on reset
- `frontend/ResultsPanel.ts` — added eventBus import, session:reset subscription
- `frontend/main.ts` — Reset button enable/disable on replayStateChanged
- `static/index.html` — added disabled attribute to Reset button
- `static/style.css` — added .replay-btn:disabled and :disabled:hover styles
