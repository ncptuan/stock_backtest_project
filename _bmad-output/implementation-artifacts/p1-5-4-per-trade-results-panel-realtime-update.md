# Story P1-5.4: Per-trade results panel + real-time update

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (5)

1. **Exit price uses TP/SL instead of actual exit price** — HIGH (all 3 agents)
   - Gap-down slippage: P&L calculated on open price but exit column showed SL price
   - Added `actual_exit_price` and `close_reason` to `TradeCompletedPayload`
   - Updated `handleTradeClose()` to populate both fields
   - Updated `addTradeRow()` to use `actual_exit_price` for display
   - Files: `types.ts`, `ReplayEngine.ts`, `ResultsPanel.ts`

2. **No "auto" exit type** — MED (Acceptance Auditor)
   - AC specifies "TP/SL/auto" but implementation only had TP/SL
   - Added `close_reason: 'tp' | 'sl' | 'auto'` to payload
   - Auto-close (last bar, reset) passes `'auto'`; checkHits defaults to `'tp'`/`'sl'`
   - Exit type column now shows "Auto" for forced closes
   - Files: `ReplayEngine.ts`, `ResultsPanel.ts`

3. **stepBack clears trade rows but never rebuilds** — MED (Edge Case Hunter)
   - `session:reset` cleared all rows, valid trades not re-emitted
   - Extended `tradeLog` to store full `TradeCompletedPayload`
   - After `session:reset` in `stepBack()`, re-emit `tradeCompleted` for each remaining trade
   - File: `ReplayEngine.ts`

4. **showEmptyMessage() dead code + clearTradeList hides msg** — MED (Blind Hunter)
   - `showEmptyMessage()` defined but never called; `showSummary()` zero-trades had different wording
   - Updated `showSummary()` zero-trades branch to call `showEmptyMessage()` (exact AC text)
   - File: `ResultsPanel.ts`

5. **Duplicate "Exit" headers + missing auto-scroll** — MED (Blind + Edge)
   - HTML header had two "Exit" columns — changed second to "Result"
   - Added `scrollIntoView` on new trade rows for visibility
   - Files: `index.html`, `ResultsPanel.ts`

### AC Results (Acceptance Auditor)

- AC#1: PARTIALLY MET → **FULLY MET** (patches 1-2)
- AC#2: FULLY MET
- AC#3: FULLY MET
- AC#4: PARTIALLY MET → **FULLY MET** (patch 4)
- AC#5: FULLY MET

### Deferred

- Forced-close during reset: trade row added then immediately cleared — single-threaded, no visible flash, defer
- innerHTML with unvalidated string fields — all data is internal type-safe payload, defer
- DOM listener leak on row removal — modern GC handles when node removed, defer
- UTC+7 hardcoded with no timezone label — single-user app, consistent, defer
- Entry time vs exit time ambiguity — design choice, defer

## Story

As a trader,
I want a live results table that updates as each trade completes,
So that I can track session performance without waiting for replay to finish.

## Acceptance Criteria

1. **Given** replay đang chạy
   **When** một lệnh vừa đóng
   **Then** row mới xuất hiện ngay trong results panel với: #, Entry price, Exit price, Exit type (TP/SL/auto), P&L %, timestamp nến trigger

2. **Given** results table đang hiển thị
   **When** replay tiếp tục
   **Then** results table cập nhật real-time — không chờ đến cuối session

3. **Given** mỗi row trong results table
   **When** trader hover
   **Then** hiển thị audit trail: timestamp nến trigger (UTC+7), giá OHLC tại bar trigger

4. **Given** replay kết thúc không có trade nào
   **When** date range đã replay hết
   **Then** hiển thị message "Entry price chưa được chạm trong date range đã chọn"

5. **Given** trader nhấn Reset
   **When** reset hoàn tất
   **Then** results table clear — không còn rows

## Tasks / Subtasks

- [x] Task 1: Cập nhật `frontend/ResultsPanel.ts` — Trade list rendering (AC: #1, #2)
  - [x] Subscribe `tradeCompleted` event → append row
  - [x] Render row: #, direction, entry, exit, type, P&L%, timestamp
  - [x] Color code: win (green), loss (red)

- [x] Task 2: Audit trail hover (AC: #3)
  - [x] Mỗi row: expandable section on hover
  - [x] Hiển thị: timestamp (UTC+7), OHLC tại trigger bar

- [x] Task 3: Zero trades message (AC: #4)
  - [x] Subscribe `replayStateChanged` stopped + check trade count
  - [x] Hiển thị message khi 0 trades

- [x] Task 4: Clear on reset (AC: #5)
  - [x] Subscribe `session:reset` → clear all rows

- [x] Task 5: Cập nhật `static/index.html` — Results panel structure (AC: #1)
  - [x] `#results-table-body` container + header + empty message
  - [x] Table header: #, Type, Entry, Exit, P&L, Time

- [x] Task 6: Cập nhật `static/style.css` — Results table styles (AC: #1)
  - [x] `.results-table-header` / `.results-table-body` styles
  - [x] `.results-row--win` (green accent) / `.results-row--loss` (red accent)
  - [x] `.results-audit` expandable styles

## Dev Notes

### ResultsPanel Architecture

ResultsPanel hiện tại (Phase 2) chỉ có CompletionOverlay. Cần thêm:
- Trade list table
- Real-time row append
- Audit trail expandable

### Trade Row Template

```html
<div class="results-row results-row--win">
  <span class="results-num">#1</span>
  <span class="results-direction direction-long">LONG</span>
  <span class="results-entry">68,000.00</span>
  <span class="results-exit">69,000.00</span>
  <span class="results-type">TP</span>
  <span class="results-pnl">+1.27%</span>
  <span class="results-time">15/03 08:00</span>
</div>
```

### Audit Trail (Expandable)

```html
<div class="results-audit" hidden>
  <div>Trigger: 15/03/2024 08:00 UTC+7</div>
  <div>O: 68,100 H: 69,200 L: 67,900 C: 68,800</div>
</div>
```

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/ResultsPanel.ts` | Trade list, real-time append, audit trail, zero trades |
| `frontend/main.ts` | Wire `replay:tradeAdded` → ResultsPanel |
| `static/index.html` | Results table structure |
| `static/style.css` | Table + row styles |

### Scope Boundary

| Feature | P1-5.4 | Khác |
|---------|--------|------|
| Real-time trade rows | ✓ | |
| P&L per trade | ✓ | |
| Audit trail hover | ✓ | |
| Zero trades message | ✓ | |
| Clear on reset | ✓ | |
| Session summary | ✗ | P1-5.5 |
| Sample size warnings | ✗ | P1-5.5 |

## Dev Agent Record

### Agent Model Used


### Debug Log References

### Completion Notes List

- **Task 1-4**: Updated `ResultsPanel.ts` with trade list rendering. Subscribes to `tradeCompleted` event for real-time row append. Each row shows #, direction, entry, exit, exit type (TP/SL), P&L%, timestamp. Audit trail (OHLC + trigger timestamp) shown on hover. Zero trades message displayed when replay stops with no trades. All rows cleared on `session:reset`.
- **Task 5**: Updated `index.html` with results table structure: header row, scrollable body, empty message element.
- **Task 6**: Added CSS styles for results table: grid layout, color-coded rows (win/loss), audit trail dropdown, sticky header.
- **Wiring**: Imported `resultsPanel` in `main.ts`, called `init()` with status bar element.

### File List

| File | Action | Description |
|------|--------|-------------|
| `frontend/ResultsPanel.ts` | Modified | Added `addTradeRow()`, `clearTradeList()`, `showEmptyMessage()`, event subscriptions for `tradeCompleted`, `chart:dataLoaded`, `replayStateChanged`, `session:reset` |
| `frontend/main.ts` | Modified | Imported `resultsPanel`, added `init()` call with status bar element |
| `static/index.html` | Modified | Replaced placeholder with results table header, body, and empty message elements |
| `static/style.css` | Modified | Added `.results-table-header`, `.results-table-body`, `.results-row`, `.results-audit`, `.results-empty-msg` styles |

## Change Log

- 2026-05-03: Code review — applied 5 patches. Key fixes: actual_exit_price for gap-down accuracy, auto exit type, stepBack row rebuild, showEmptyMessage wiring, header fix. All ACs now fully met.
