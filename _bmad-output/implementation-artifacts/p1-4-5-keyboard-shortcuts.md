# Story P1-4.5: Keyboard shortcuts — step forward/back + cheat sheet

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (3)

1. **stepBack corrupts trade log via duplicate re-entry** — HIGH (Blind + Edge)
   - `stepBack()` cleared `openPosition` but never pruned `tradeLog`
   - Stepping forward again re-triggered same trades, compounding duplicates
   - Added `exitBarIndex` to tradeLog entries, prune on stepBack
   - File: `ReplayEngine.ts`

2. **stepBack doesn't clear trade markers** — HIGH (Blind)
   - Trade markers remained on chart after stepping back past exit bar
   - Added `session:reset` emission in stepBack to clear markers
   - File: `ReplayEngine.ts`

3. **Missing click-outside-to-close for cheat sheet** — MED (Edge + Acceptance)
   - AC#4 requires click-outside dismiss
   - Added click handler on overlay that closes when target === overlay
   - File: `main.ts`

### AC Results (Acceptance Auditor)

- AC#1-3, #5: FULLY MET
- AC#4: PARTIALLY MET → FULLY MET (after patch)

### Deferred

- `e.preventDefault()` on arrow keys runs even when not replaying — blocks native scroll/page-nav in setup mode, defer
- Focus guard misses `[contenteditable]` — no contenteditable exists today, defer
- Missing `e.preventDefault()` on letter-key shortcuts — no contenteditable today, defer
- `?` key layout dependency on non-US keyboards — single-user app, defer

## Story

As a trader,
I want keyboard shortcuts to step through bars and a cheat sheet overlay,
So that I can control replay precisely without reaching for the mouse.

## Acceptance Criteria

1. **Given** replay đang paused tại bar N
   **When** trader nhấn Arrow Right
   **Then** advance 1 bar: currentIndex++, chart reveal bar N+1
   **And** emit `replay:barAdvanced` như bình thường

2. **Given** replay đang paused tại bar N > 0
   **When** trader nhấn Arrow Left
   **Then** go back 1 bar: currentIndex--, chart reveal bar N-1
   **And** emit `replay:barAdvanced` với index mới

3. **Given** trader nhấn `?` (Shift + /)
   **When** không có input nào đang focus
   **Then** cheat sheet overlay hiển thị tất cả keyboard shortcuts

4. **Given** cheat sheet đang hiển thị
   **When** trader nhấn Escape hoặc click outside
   **Then** cheat sheet đóng

5. **Given** replay đang chạy (playing)
   **When** trader nhấn Arrow Right/Left
   **Then** nothing xảy ra — arrows chỉ hoạt động khi paused

## Tasks / Subtasks

- [x] Task 1: Cập nhật `frontend/ReplayEngine.ts` — Step forward/back (AC: #1, #2)
  - [x] `stepForward()`: advance 1 bar, emit events, update chart
  - [x] `stepBack()`: go back 1 bar (min 0), emit events, update chart
  - [x] `canStep()`: guard chỉ hoạt động khi paused

- [x] Task 2: Cập nhật `frontend/main.ts` — Arrow key handlers (AC: #1, #2, #5)
  - [x] Arrow Right → `replayEngine.stepForward()`
  - [x] Arrow Left → `replayEngine.stepBack()`
  - [x] Skip shortcuts when input/textarea/select focused

- [x] Task 3: Tạo cheat sheet overlay (AC: #3, #4)
  - [x] `?` key → toggle cheat sheet overlay
  - [x] Escape → close cheat sheet
  - [x] Full shortcut list displayed

- [x] Task 4: Cập nhật `static/index.html` — Cheat sheet container (AC: #3)
  - [x] `#cheat-sheet-overlay` div with grid layout

- [x] Task 5: Cập nhật `static/style.css` — Cheat sheet styles (AC: #3)
  - [x] `.cheat-sheet-overlay` — centered modal with backdrop
  - [x] `.cheat-sheet-grid` — 2-column grid layout
  - [x] `.cheat-sheet-key` — styled key badges

## Dev Notes

### Overlap với P1-4.1

P1-4.1 đã implement:
- Space: play/pause toggle
- 1/2/3: speed control

Story này thêm:
- **Arrow Left/Right**: step single bar (chỉ khi paused)
- **`?` key**: cheat sheet overlay
- **R key**: reset shortcut (nếu chưa có)

### stepForward / stepBack Implementation

```typescript
// frontend/ReplayEngine.ts

stepForward(): void {
  if (this.currentIndex >= this.data.length - 1) return;
  this.currentIndex++;
  this._emitBarAdvanced();
  this.chartController?.revealBar(this.currentIndex);
}

stepBack(): void {
  if (this.currentIndex <= 0) return;
  this.currentIndex--;
  this._emitBarAdvanced();
  this.chartController?.revealBar(this.currentIndex);
}

private _emitBarAdvanced(): void {
  eventBus.emit('replay:barAdvanced', {
    barIndex: this.currentIndex,
    timestamp: this.data[this.currentIndex]?.timestamp ?? 0,
  });
}
```

### Cheat Sheet Content

```
Keyboard Shortcuts
─────────────────────
Space        Play / Pause
1  2  3      Slow · Normal · Fast
←  →         Step back / forward (paused)
R            Reset
E  T  S      Draw Entry / TP / SL
Del          Delete selected line
Esc          Cancel drawing mode
?            This cheat sheet
```

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/ReplayEngine.ts` | `stepForward()`, `stepBack()` methods |
| `frontend/main.ts` | Arrow key + `?` + `R` handlers |
| `static/index.html` | Cheat sheet overlay container |
| `static/style.css` | Cheat sheet styles |

### Files KHÔNG được touch

- `frontend/ChartController.ts` — `revealBar()` đã có
- `frontend/DrawingManager.ts` — không cần sửa
- Backend — frontend only

### Scope Boundary

| Feature | P1-4.5 | Khác |
|---------|--------|------|
| Arrow Left/Right step | ✓ | |
| Cheat sheet overlay | ✓ | |
| `?` key toggle | ✓ | |
| Space/1/2/3/R shortcuts | ✗ | P1-4.1 |
| Look-ahead prevention | ✗ | P1-4.2-3 |
| Pre-flight checklist | ✗ | P1-4.4 |

### Edge Cases

1. **Arrow Right khi ở bar cuối**: no-op, không crash
2. **Arrow Left khi ở bar 0**: no-op, không crash
3. **Arrow khi replay đang chạy**: no-op (chỉ hoạt động paused/stopped)
4. **`?` khi đang ghi text input**: ignore nếu `document.activeElement` là input/textarea
5. **Step forward/back trigger hit detection**: chỉ emit event, hit detection sẽ được wire trong Epic P1-5

## Dev Agent Record

### Agent Model Used

mimo-v2.5-pro

### Debug Log References

- Build: 328.5kb, esbuild 36ms
- Typecheck: passed (tsc --noEmit)

### Completion Notes List

- ReplayEngine: added stepForward(), stepBack(), canStep(), _emitBarAdvanced()
- Step methods guard with canStep() — only works when paused
- Arrow keys, R, E/T/S, ? all skip when input/textarea/select focused
- Cheat sheet overlay: fixed position, backdrop, 2-column grid with styled key badges
- Escape closes cheat sheet first, then cancels drawing mode

### File List

- `frontend/ReplayEngine.ts` — added stepForward(), stepBack(), canStep(), _emitBarAdvanced()
- `frontend/main.ts` — added Arrow/R/E/T/S/? key handlers, toggleCheatSheet(), input focus guard
- `static/index.html` — added #cheat-sheet-overlay with shortcut grid
- `static/style.css` — added .cheat-sheet-overlay, .cheat-sheet-panel, .cheat-sheet-grid, .cheat-sheet-key styles
