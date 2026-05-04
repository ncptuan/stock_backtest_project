# Story P1-5.5: Session summary + sample size warnings

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (3)

1. **stepBack entry marker at exit bar_index** — HIGH (Blind + Edge)
   - `TradeCompletedPayload` lacked `entry_bar_index` — stepBack re-emitted entry markers at exit bar
   - Added `entry_bar_index` field to payload, populated in `handleTradeClose()`
   - Fixed stepBack rebuild to use `trade.entry_bar_index` for entry markers
   - Files: `types.ts`, `ReplayEngine.ts`

2. **stepBack leaves summary empty** — MED (Edge)
   - After stepBack rebuild, summary panel stayed blank until next replay stop
   - Made `showSummary()` public, added `session:rebuilt` event
   - ResultsPanel listens for `session:rebuilt` → calls `showSummary()`
   - Files: `ResultsPanel.ts`, `types.ts`, `ReplayEngine.ts`

3. **Zero-trades message text mismatch** — MED (Acceptance Auditor)
   - AC expects: "Entry price chưa được chạm — thử mở rộng date range hoặc điều chỉnh Entry"
   - showEmptyMessage() had P1-5.4 text instead
   - Updated text to match P1-5.5 AC
   - File: `ResultsPanel.ts`

### AC Results (Acceptance Auditor)

- AC#1: FULLY MET (summary stats)
- AC#2: FULLY MET (warning < 30)
- AC#3: FULLY MET (warning < 10, more prominent)
- AC#4: NOT MET → **FULLY MET** (patch 3)

### Deferred

- reset() summary flash (showSummary fires before clearTradeList) — zero-frame DOM batch, not visible, defer
- LONG-only win/loss heuristic in auto-close — SHORT not supported, dormant, defer
- .summary-warning--info CSS unused in source — harmless, defer
- showEmptyMessage targets different DOM element than showSummary — both elements exist, visual OK, defer
- Rounding asymmetry near zero — JS standard behavior, cosmetic, defer

## Story

As a trader,
I want a session summary with win rate and warnings when sample size is too small,
So that I can judge whether my results are statistically meaningful.

## Acceptance Criteria

1. **Given** session kết thúc (replay done hoặc trader dừng)
   **When** results panel hiển thị summary
   **Then** summary gồm: tổng số lệnh, số thắng, số thua, win rate %, tổng P&L %

2. **Given** số lệnh trong session < 30
   **When** summary hiển thị
   **Then** warning nhẹ: "⚠ Sample size < 30 — kết quả chưa đủ tin cậy"

3. **Given** số lệnh trong session < 10
   **When** summary hiển thị
   **Then** warning mạnh: "⛔ Sample size < 10 — kết quả không có ý nghĩa thống kê"
   **And** warning mạnh hiển thị nổi bật hơn warning nhẹ

4. **Given** replay kết thúc với 0 lệnh
   **When** summary hiển thị
   **Then** message: "Entry price chưa được chạm — thử mở rộng date range hoặc điều chỉnh Entry"

## Tasks / Subtasks

- [x] Task 1: Cập nhật `frontend/ReplayEngine.ts` — `getSummary()` (AC: #1)
  - [x] `getSummary()`: return `{ total, wins, losses, winRate, totalPnl }`
  - [x] Tính từ trade log array

- [x] Task 2: Cập nhật `frontend/ResultsPanel.ts` — Summary display (AC: #1, #2, #3, #4)
  - [x] Subscribe `replayStateChanged` stopped → show summary
  - [x] Render summary stats
  - [x] Sample size warnings (< 30, < 10)
  - [x] Zero trades message

- [x] Task 3: Cập nhật `static/style.css` — Summary styles (AC: #2, #3)
  - [x] `.results-summary` container
  - [x] `.summary-stat` individual stat
  - [x] `.summary-warning--light` (< 30)
  - [x] `.summary-warning--strong` (< 10)

## Dev Notes

### getSummary() Implementation

```typescript
// frontend/ReplayEngine.ts

interface SessionSummary {
  total: number;
  wins: number;
  losses: number;
  winRate: number;    // 0–100 percentage
  totalPnl: number;   // sum of all P&L %
}

getSummary(): SessionSummary {
  const trades = this.getTradeLog();
  const wins = trades.filter(t => t.result === 'win').length;
  const losses = trades.length - wins;
  return {
    total: trades.length,
    wins,
    losses,
    winRate: trades.length > 0 ? (wins / trades.length) * 100 : 0,
    totalPnl: trades.reduce((sum, t) => sum + t.pnl, 0),
  };
}
```

### Summary HTML Template

```html
<div class="results-summary">
  <div class="summary-stats">
    <span class="summary-stat">Lệnh: 15</span>
    <span class="summary-stat summary-stat--win">Thắng: 10 (66.7%)</span>
    <span class="summary-stat summary-stat--loss">Thua: 5</span>
    <span class="summary-stat">P&L: +8.35%</span>
  </div>
  <div class="summary-warning summary-warning--light">
    ⚠ Sample size < 30 — kết quả chưa đủ tin cậy
  </div>
</div>
```

### Warning Thresholds

| Trades | Warning | Style |
|--------|---------|-------|
| ≥ 30 | None | — |
| 10–29 | ⚠ nhẹ | yellow border |
| 1–9 | ⚠ mạnh | red border, bold |
| 0 | Message | muted text |

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/ReplayEngine.ts` | `getSummary()` method |
| `frontend/ResultsPanel.ts` | Summary display + warnings |
| `static/style.css` | Summary + warning styles |

### Scope Boundary

| Feature | P1-5.5 | Khác |
|---------|--------|------|
| Session summary stats | ✓ | |
| Win rate % | ✓ | |
| Total P&L % | ✓ | |
| Sample size < 30 warning | ✓ | |
| Sample size < 10 warning | ✓ | |
| Zero trades message | ✓ | |
| Per-trade rows | ✗ | P1-5.4 |

## Dev Agent Record

### Agent Model Used
mimo-v2.5-pro

### Debug Log References
- TypeScript typecheck: pass
- esbuild bundle: pass (366.4kb)

### Completion Notes List
- Added `tradeLog` array to ReplayEngine to accumulate trades across session
- Added `getSummary()` method returning `{ total, wins, losses, winRate, totalPnl }`
- Trade log cleared on `start()` and `reset()`
- ResultsPanel subscribes to `replayStateChanged` stopped to show summary
- Summary renders: total trades, wins, losses, win rate %, total P&L %
- Sample size warnings: < 30 (yellow border), < 10 (red border, bold)
- Zero trades shows info message instead of summary
- Summary cleared on `session:reset`
- `setReplayEngine()` added to ResultsPanel for dependency injection from main.ts

### File List
- frontend/ReplayEngine.ts (modified: tradeLog, getSummary())
- frontend/ResultsPanel.ts (modified: showSummary(), clearSummary(), setReplayEngine())
- frontend/main.ts (modified: resultsPanel.setReplayEngine())
- static/index.html (modified: #results-summary div)
- static/style.css (modified: .results-summary, .summary-stats, .summary-warning--light/strong/info)

## Change Log

- 2026-05-03: Code review — applied 3 patches. Key fixes: entry_bar_index for stepBack marker rebuild, summary rebuild after stepBack, zero-trades message text. All ACs now fully met.
