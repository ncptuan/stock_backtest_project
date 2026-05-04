# Story P1-5.2: P&L calculation + commission

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patch Applied (1)

1. **Auto-close at last bar uses slPrice instead of close price** — MED (Edge)
   - `handleTradeClose(this.currentIndex, 'loss')` without exitPrice fell back to slPrice
   - If position was in profit at last bar, P&L was incorrectly calculated against SL
   - Fixed: use last bar's close price, determine result from actual P&L direction
   - Applied in 3 locations: advanceBar(), stepForward(), reset()
   - File: `ReplayEngine.ts`

### All 4 ACs: FULLY MET (Acceptance Auditor)

### Deferred

- SHORT direction P&L formula inverted — `(exit-entry)/entry*100` is LONG-only — dormant (LONG-only entry path), defer to SHORT support scope
- Negative P&L rounding asymmetry — JS `Math.round(-1.665*100)/100` = -1.66 not -1.67 — consistent JS behavior, defer
- Division by zero if entryPrice = 0 — normalize rounds to 0 for prices < 0.005 — unreachable with real BTC data, defer

## Story

As a trader,
I want P&L calculated with commission included and locked at Play time,
So that results reflect real trading costs and are reproducible.

## Acceptance Criteria

1. **Given** lệnh đã đóng với entry price và exit price
   **When** P&L được tính
   **Then** `P&L % = (exit_price - entry_price) / entry_price * 100 - 0.1% - 0.1%`
   **And** commission 0.1% mỗi chiều (buy + sell) bắt buộc tính vào mọi P&L

2. **Given** P&L được lock tại thời điểm nhấn Play
   **When** trader drag đường sau khi Play
   **Then** P&L của session đang chạy KHÔNG thay đổi — snapshot frozen

3. **Given** cùng data + cùng Entry/TP/SL prices
   **When** trader chạy replay nhiều lần
   **Then** P&L kết quả phải giống nhau mọi lần (reproducible)

4. **Given** trade đóng bởi gap-down slippage (exit tại open, không tại SL)
   **When** P&L được tính
   **Then** dùng actual exit price (open price) cho P&L calculation — không dùng SL price

## Tasks / Subtasks

- [x] Task 1: Cập nhật `frontend/ReplayEngine.ts` — P&L calculation (AC: #1, #4)
  - [x] `calcPnL(entryPrice, exitPrice): number` — tính P&L % với commission
  - [x] Công thức: `((exit - entry) / entry * 100) - 0.2` (0.1% × 2 sides)
  - [x] Gọi trong `handleTradeClose()` — tính P&L trước khi emit event

- [x] Task 2: Cập nhật `frontend/types.ts` — Thêm P&L fields vào Trade (AC: #1)
  - [x] `Trade` interface: thêm `pnl: number`, `commission: number`
  - [x] `TradeCompletedPayload`: thêm `pnl_percent: number`

- [x] Task 3: Cập nhật `frontend/ReplayEngine.ts` — P&L lock tại Play (AC: #2)
  - [x] `lineSnapshot` đã frozen tại Play time (từ P1-4.1)
  - [x] Verify P&L dùng snapshot prices, không re-read từ DrawingManager

- [x] Task 4: Tạo `tests/test_pnl_calculation.py` — Unit tests (AC: #1–#4)
  - [x] Test P&L win: entry=68000, exit=69000 → (1000/68000*100) - 0.2 = ~1.27%
  - [x] Test P&L loss: entry=68000, exit=67000 → (-1000/68000*100) - 0.2 = ~-1.67%
  - [x] Test commission impact: không commission → P&L khác có commission
  - [x] Test gap-down: exit tại open (66000) thay vì SL (67000)
  - [x] Test reproducibility: cùng inputs → cùng output

## Dev Notes

### P&L Formula

```typescript
// frontend/ReplayEngine.ts

private static readonly COMMISSION_RATE = 0.001; // 0.1% per side

private calcPnL(entryPrice: number, exitPrice: number): number {
  const rawPnl = ((exitPrice - entryPrice) / entryPrice) * 100;
  const commission = ReplayEngine.COMMISSION_RATE * 2 * 100; // 0.2% total
  return rawPnl - commission;
}
```

**Ví dụ:**
- Entry: 68,000 → TP: 69,000
- Raw P&L: (69000 - 68000) / 68000 × 100 = 1.4706%
- Commission: 0.2%
- Net P&L: 1.4706 - 0.2 = **1.27%**

### handleTradeClose() Update

```typescript
// frontend/ReplayEngine.ts — existing method, add P&L

private handleTradeClose(exitBarIndex: number, result: 'win' | 'loss', exitPrice?: number): void {
  if (!this.openPosition) return;

  // Use provided exit price or TP/SL from snapshot
  const actualExitPrice = exitPrice ?? (result === 'win'
    ? this.openPosition.tpPrice
    : this.openPosition.slPrice);

  const pnl = this.calcPnL(this.openPosition.entryPrice, actualExitPrice);

  const payload: TradeCompletedPayload = {
    bar_index: exitBarIndex,
    entry_timestamp_ms: this.openPosition.entryTimestampMs,
    direction: this.openPosition.direction,
    entry_price: this.openPosition.entryPrice,
    tp_price: this.openPosition.tpPrice,
    sl_price: this.openPosition.slPrice,
    result,
    bars_to_exit: Math.max(0, exitBarIndex - this.openPosition.entryBarIndex),
    pnl_percent: pnl,  // NEW
  };

  eventBus.emit('tradeCompleted', payload);
  eventBus.emit('replay:tradeHit', {
    type: result === 'win' ? 'tp' : 'sl',
    price: actualExitPrice,
    barIndex: exitBarIndex,
  });

  this.openPosition = null;
}
```

### Trade Interface Update

```typescript
// frontend/types.ts

export interface Trade {
  barIndex: number;
  direction: 'LONG' | 'SHORT';
  entryPrice: number;
  tpPrice: number;
  slPrice: number;
  result: 'win' | 'loss';
  pnl: number;          // P&L % with commission
  commission: number;    // 0.2% total
}
```

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/ReplayEngine.ts` | `calcPnL()`, update `handleTradeClose()` |
| `frontend/types.ts` | Thêm `pnl`, `commission` vào Trade + payload |
| `tests/test_pnl_calculation.py` | Unit tests |

### Files KHÔNG được touch

- `frontend/ChartController.ts` — không liên quan
- `frontend/main.ts` — wiring đã có
- Backend — frontend logic

### Scope Boundary

| Feature | P1-5.2 | Khác |
|---------|--------|------|
| P&L calculation với commission | ✓ | |
| 0.1% commission mỗi chiều | ✓ | |
| P&L lock at Play time | ✓ | |
| Reproducible results | ✓ | |
| Gap-down exit price | ✓ | |
| Hit detection logic | ✗ | P1-5.1 |
| Visual markers | ✗ | P1-5.3 |
| Results panel display | ✗ | P1-5.4 |

### Edge Cases

1. **Entry = Exit (breakeven)**: P&L = 0% - 0.2% = **-0.2%** (commission loss)
2. **Very small price diff**: P&L rounding — 2 decimal places
3. **Gap-down slippage**: exit tại open (thấp hơn SL) → P&L tính trên actual exit
4. **TP = 0 (not set)**: auto-close tại last bar → exit = close price
5. **Commission luôn 0.2%**: hardcoded, không configurable trong MVP

## Dev Agent Record

### Agent Model Used


### Debug Log References

### Completion Notes List

- **Task 1**: Added `calcPnL()` method to `ReplayEngine` with formula `((exit - entry) / entry * 100) - 0.2`. Commission rate 0.1% per side hardcoded as `COMMISSION_RATE = 0.001`. Updated `handleTradeClose()` to accept optional `exitPrice` param for gap-down slippage (AC#4).
- **Task 2**: Added `pnl_percent: number` field to `TradeCompletedPayload` in `types.ts`. The `Trade` interface already had `pnl` and `commission` fields from prior work.
- **Task 3**: Verified P&L lock — `openPosition` prices are set from `lineSnapshot` at `openTrade()` time. Snapshot is frozen at Play time (from P1-4.1). P&L calculation uses frozen snapshot prices, not re-read from DrawingManager.
- **Task 4**: Created 10 unit tests in `tests/test_pnl_calculation.py`. All pass. Tests cover: win/loss P&L, commission impact, gap-down slippage, reproducibility. Full regression suite: 189 passed, 2 pre-existing failures in test_settings.py (unrelated).

### File List

| File | Action | Description |
|------|--------|-------------|
| `frontend/ReplayEngine.ts` | Modified | Added `calcPnL()`, `COMMISSION_RATE`, updated `handleTradeClose()` with P&L + exitPrice param, updated gap-down handling |
| `frontend/types.ts` | Modified | Added `pnl_percent: number` to `TradeCompletedPayload` |
| `tests/test_pnl_calculation.py` | Created | 10 unit tests covering AC #1–#4 |

## Change Log

- 2026-05-03: Implemented P&L calculation with commission (0.1% per side). Added `calcPnL()` to ReplayEngine, `pnl_percent` to TradeCompletedPayload, gap-down slippage support, and 10 unit tests. All ACs satisfied.
