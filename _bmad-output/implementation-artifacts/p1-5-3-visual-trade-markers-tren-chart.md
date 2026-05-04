# Story P1-5.3: Visual trade markers trên chart

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (5)

1. **Entry marker never emitted** — HIGH (all 3 agents)
   - `openTrade()` never fired `replay:tradeHit` with `type: 'entry'`
   - AC#1 (green ▲ Entry marker) was NOT MET
   - Added `eventBus.emit('replay:tradeHit', { type: 'entry', price: fillPrice, barIndex })` to `openTrade()`
   - File: `ReplayEngine.ts`

2. **stepBack() clears markers but never rebuilds** — HIGH (Blind + Edge)
   - `session:reset` clears all markers, valid trades not re-emitted
   - Extended `tradeLog` to store entryBarIndex, entryPrice, exitPrice
   - After session:reset in stepBack(), re-emit replay:tradeHit for each remaining trade
   - File: `ReplayEngine.ts`

3. **Fragile price read in _showPulseAnimation** — MED (Blind)
   - Read price from array tail instead of using the price param already available
   - Changed signature to accept `price` directly from `addTradeMarker()`
   - File: `ChartController.ts`

4. **No pulse fallback cleanup + destroy() leaks** — MED (Blind + Edge)
   - Pulse cleanup relied solely on `animationend` — leaked if animation interrupted
   - Added `setTimeout` fallback (700ms) for pulse removal
   - Fixed `destroy()` to null markersPlugin, clear tradeMarkers, remove pulse DOM elements
   - File: `ChartController.ts`

5. **TP/SL text missing ✓/✗ icons** — LOW (Acceptance Auditor)
   - AC specifies "✓ TP" and "✗ SL" but implementation used plain "TP"/"SL"
   - Updated marker text to include icon characters
   - File: `ChartController.ts`

### AC Results (Acceptance Auditor)

- AC#1: NOT MET → **FULLY MET** (patch 1)
- AC#2: FULLY MET
- AC#3: FULLY MET
- AC#4: FULLY MET

### Deferred

- reset() forced-close misclassifies exit marker — semantic issue, not a bug, defer
- Pulse animation stays at fixed pixel during zoom/pan — 0.6s window, cosmetic, defer
- No pulse feedback for off-screen markers — markers still render, just no DOM pulse, defer
- 1-frame marker flicker on trade hit — addTradeMarker between revealBar calls, defer
- `TradeMarker.price` stored but never used in rendering — dead data, cosmetic, defer
- Duplicate type definition TradeMarkerType vs EventMap inline union — low drift risk, defer

## Story

As a trader,
I want to see entry and exit markers on the chart,
So that I can visually understand where each trade occurred in the context of price action.

## Acceptance Criteria

1. **Given** lệnh vừa được mở tại bar N+1
   **When** replay reveal bar N+1
   **Then** marker "▲ Entry" xuất hiện tại đáy nến entry — màu xanh
   **And** marker có brief pulse animation 1 lần khi xuất hiện (không loop)

2. **Given** lệnh đóng tại bar M (TP hoặc SL hit)
   **When** replay reveal bar M
   **Then** marker "✓ TP" hoặc "✗ SL" xuất hiện tại bar exit với màu tương ứng (teal / đỏ)
   **And** markers cho tất cả trades trong session tích lũy trên chart — không bị xóa khi replay tiếp tục

3. **Given** trader nhấn Reset
   **When** reset hoàn tất
   **Then** tất cả trade markers bị xóa khỏi chart

4. **Given** markers đang hiển thị
   **When** trader zoom/pan chart
   **Then** markers stay at correct price positions (coordinate translation)

## Tasks / Subtasks

- [x] Task 1: Cập nhật `frontend/ChartController.ts` — Trade marker rendering (AC: #1, #2, #4)
  - [x] `addTradeMarker(barIndex, type, price)`: thêm marker lên chart
  - [x] Dùng Lightweight Charts `series.setMarkers()` for persistent markers + DOM overlay for pulse
  - [x] Pulse animation CSS khi marker xuất hiện

- [x] Task 2: Cập nhật `frontend/main.ts` — Subscribe trade events (AC: #1, #2)
  - [x] Listen `replay:tradeHit` event → `chartController.addTradeMarker()`
  - [x] Track markers array để clear on reset

- [x] Task 3: Clear markers on reset (AC: #3)
  - [x] Listen `session:reset` → clear all markers
  - [x] `chartController.clearTradeMarkers()`

- [x] Task 4: Cập nhật `static/style.css` — Marker styles (AC: #1)
  - [x] `.trade-marker-pulse` base styles
  - [x] `.trade-marker-pulse--entry` (green)
  - [x] `.trade-marker-pulse--tp` (teal)
  - [x] `.trade-marker-pulse--sl` (red)
  - [x] `@keyframes marker-pulse` animation

## Dev Notes

### Marker Rendering Strategy

Option A: **Lightweight Charts Markers API** (preferred)
```typescript
// Using built-in markers
const markers = series.markers();
series.setMarkers([
  ...markers,
  { time: barTimestamp, position: 'belowBar', color: '#3fb950', shape: 'arrowUp', text: 'Entry' }
]);
```

Option B: **Canvas overlay** (fallback nếu LW markers API không đủ flexible)
- Canvas overlay đã có từ DrawingManager — reuse pattern

### Marker Types

| Type | Icon | Color | Position |
|------|------|-------|----------|
| Entry | ▲ | green (#3fb950) | below bar |
| TP | ✓ | teal (#4ea8de) | above bar |
| SL | ✗ | red (#f85149) | above bar |

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/ChartController.ts` | `addTradeMarker()`, `clearTradeMarkers()` |
| `frontend/main.ts` | Subscribe `replay:tradeHit`, wire reset |
| `static/style.css` | Marker styles + pulse animation |

### Scope Boundary

| Feature | P1-5.3 | Khác |
|---------|--------|------|
| Entry markers (green ▲) | ✓ | |
| TP markers (teal ✓) | ✓ | |
| SL markers (red ✗) | ✓ | |
| Pulse animation | ✓ | |
| Clear on reset | ✓ | |
| Markers persist during replay | ✓ | |
| Hit detection | ✗ | P1-5.1 |
| P&L calculation | ✗ | P1-5.2 |
| Results panel | ✗ | P1-5.4 |

## Dev Agent Record

### Agent Model Used


### Debug Log References

### Completion Notes List

- **Task 1**: Added `addTradeMarker()` and `clearTradeMarkers()` to `ChartController`. Uses Lightweight Charts `series.setMarkers()` for persistent markers that stay at correct price positions during zoom/pan (AC#4). Markers re-render after each `revealBar()` call since `setData()` clears them. Pulse animation uses DOM overlay positioned via `timeToCoordinate()`/`priceToCoordinate()`.
- **Task 2**: Subscribed `replay:tradeHit` event in `main.ts` → calls `chartController.addTradeMarker(barIndex, type, price)`. Markers accumulate on chart during replay (AC#2).
- **Task 3**: Subscribed `session:reset` event → calls `chartController.clearTradeMarkers()`. All markers removed on reset (AC#3).
- **Task 4**: Added CSS pulse animation (`.trade-marker-pulse`) with color-coded variants for entry (green), TP (teal), SL (red). Animation plays once on marker appearance (AC#1).

### File List

| File | Action | Description |
|------|--------|-------------|
| `frontend/ChartController.ts` | Modified | Added `TradeMarker` type, `tradeMarkers` array, `addTradeMarker()`, `clearTradeMarkers()`, `_renderTradeMarkers()`, `_showPulseAnimation()`, updated `revealBar()` to re-render markers |
| `frontend/main.ts` | Modified | Subscribed `replay:tradeHit` → `addTradeMarker()`, `session:reset` → `clearTradeMarkers()` |
| `static/style.css` | Modified | Added `.trade-marker-pulse` styles + `@keyframes marker-pulse` animation |

## Change Log

- 2026-05-03: Code review — applied 5 patches. Key fix: entry marker event emission was missing (AC#1 NOT MET), stepBack marker rebuild, pulse fallback cleanup, destroy() leak fix, TP/SL icon text. All ACs now fully met.
