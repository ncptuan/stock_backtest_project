# Story P1-4.4: Pre-flight checklist + Session Fingerprint

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (3)

1. **Drag-to-reposition doesn't emit `drawing:lineChanged`** — HIGH (Edge)
   - `_startDrag()` onUp handler set `this.lines.set()` + `redrawAll()` directly without emitting event
   - Checklist and auto-save never triggered after drag — data lost on refresh
   - Added `eventBus.emit('drawing:lineChanged', { type, price: finalPrice })` after `redrawAll()`
   - File: `DrawingManager.ts`

2. **`restore()` doesn't emit events — undo after timeframe change leaves checklist stale** — MED (Edge)
   - `restore()` set `this.lines` + `redrawAll()` without emitting events
   - After undo restores drawings, `updatePreflightChecklist()` never called
   - Added event emission for each non-null line after restore
   - File: `DrawingManager.ts`

3. **Missing "Date range" 4th checklist item** — MED (Acceptance Auditor)
   - AC#1 requires "✓ Date range" as a 4th item
   - Added `{ label: 'Date', price: currentSettings?.dateStart ? 1 : null }` to items array
   - File: `main.ts`

### AC Results (Acceptance Auditor)

- AC#1: PARTIALLY MET → FULLY MET (after patch)
- AC#2-5: FULLY MET

### Deferred

- innerHTML reflows on every drawing:lineChanged — no child listeners exist today, perf sprint if drag becomes laggy
- Button disabled state + click handler guard redundancy — cosmetic duplication, both correct
- Fingerprint not hidden on replay engine error — defensive cleanup, no current error path
- `toLocaleString` inconsistency across environments — cosmetic, single-user app

## Story

As a trader,
I want a checklist before starting replay and a session fingerprint header,
So that I don't accidentally run a session with missing lines or wrong settings.

## Acceptance Criteria

1. **Given** trader chưa vẽ đủ Entry + TP + SL
   **When** trader nhìn toolbar
   **Then** Play button bị disabled
   **And** pre-flight checklist hiển thị trạng thái từng item:
     - ✓/✗ Entry set (price) | ✓/✗ TP set (price) | ✓/✗ SL set (price) | ✓ Date range

2. **Given** trader đã vẽ đủ 3 đường
   **When** trader nhìn toolbar
   **Then** Play button enabled
   **And** checklist hiển thị ✓ cho tất cả items với prices

3. **Given** trader đã đủ điều kiện và nhấn Play
   **When** replay bắt đầu
   **Then** Session Fingerprint header hiển thị: symbol, timeframe, date range, Entry/TP/SL prices
   **And** fingerprint frozen tại thời điểm Play — drag đường sau khi Play không thay đổi fingerprint

4. **Given** replay đang chạy
   **When** trader nhìn fingerprint
   **Then** fingerprint hiển thị conditions đã lock — không update dù drawings bị drag

5. **Given** trader vẽ/xóa đường trong Setup mode
   **When** drawings thay đổi
   **Then** checklist update real-time — ✓/✗ reflect trạng thái hiện tại

## Tasks / Subtasks

- [x] Task 1: Cập nhật `static/index.html` — Thêm pre-flight checklist element (AC: #1, #2)
  - [x] Thêm `#preflight-checklist` div trong toolbar area
  - [x] Thêm `#session-fingerprint` div dưới toolbar

- [x] Task 2: Cập nhật `frontend/main.ts` — Checklist logic (AC: #1, #2, #5)
  - [x] Subscribe `drawing:lineChanged` + `drawing:cleared` events → update checklist
  - [x] Update Play button disabled state dựa trên drawings
  - [x] Format: "✓ Entry 68,500.00 | ✗ TP —— | ✓ SL 67,800.00"

- [x] Task 3: Cập nhật `frontend/main.ts` — Session Fingerprint (AC: #3, #4)
  - [x] Khi Play: freeze snapshot từ `drawingManager.getSnapshot()`
  - [x] Hiển thị fingerprint header: "BTC/USDT · 4h · 2024-01-01 → 2024-06-30 · Entry 68,500.00 · TP 69,500.00 · SL 67,800.00"
  - [x] Fingerprint stored trong variable, không re-read từ DrawingManager

- [x] Task 4: Cập nhật `static/style.css` — Checklist + fingerprint styles
  - [x] `.preflight-checklist` styles
  - [x] `.checklist-item--ok` (✓ green) / `.checklist-item--missing` (✗ muted)
  - [x] `.session-fingerprint` styles

## Dev Notes

### Pre-flight Checklist UX

Checklist hiển thị inline trong toolbar, bên phải replay controls:

```
[▶ Play] [⟲ Reset] [Slow] [Normal] [Fast] | ✓ Entry 68,500 ✓ TP 69,500 ✗ SL -- ✓ Date
```

Hoặc dưới toolbar nếu không đủ chỗ:

```
Pre-flight: ✓ Entry 68,500.00 | ✓ TP 69,500.00 | ✗ SL —— | ✓ Date range 6 months
```

### Checklist Update Logic

```typescript
// frontend/main.ts

function updatePreflightChecklist(): void {
  const entry = drawingManager.getEntryPrice();
  const tp = drawingManager.getTpPrice();
  const sl = drawingManager.getSlPrice();

  const items = [
    { label: 'Entry', price: entry },
    { label: 'TP', price: tp },
    { label: 'SL', price: sl },
    { label: 'Date', price: currentSettings.dateStart ? 1 : null }, // always set
  ];

  const allSet = items.every(i => i.price !== null && i.price !== undefined);

  // Update Play button
  const btnPlay = document.getElementById('btn-replay-play') as HTMLButtonElement;
  if (btnPlay) btnPlay.disabled = !allSet;

  // Update checklist display
  const checklistEl = document.getElementById('preflight-checklist');
  if (checklistEl) {
    checklistEl.innerHTML = items.map(item => {
      const ok = item.price !== null && item.price !== undefined;
      const priceStr = ok && item.label !== 'Date'
        ? ` ${item.price!.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
        : '';
      return `<span class="checklist-item checklist-item--${ok ? 'ok' : 'missing'}">${ok ? '✓' : '✗'} ${item.label}${priceStr}</span>`;
    }).join(' ');
  }
}

// Wire events
eventBus.on('drawing:lineChanged', updatePreflightChecklist);
eventBus.on('drawing:cleared', updatePreflightChecklist);
```

### Session Fingerprint

```typescript
// frontend/main.ts

let frozenFingerprint: string = '';

function showSessionFingerprint(): void {
  const snapshot = drawingManager.getLineSnapshot();
  const settings = currentSettings;

  frozenFingerprint = [
    SYMBOL,
    settings.timeframe,
    `${settings.dateStart} → ${settings.dateEnd}`,
    `Entry ${snapshot.entry.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
    `TP ${snapshot.tp.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
    `SL ${snapshot.sl.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
  ].join(' · ');

  const fpEl = document.getElementById('session-fingerprint');
  if (fpEl) {
    fpEl.textContent = frozenFingerprint;
    fpEl.style.display = 'block';
  }
}

// Show khi Play, hide khi Reset
eventBus.on('replayStateChanged', ({ state }) => {
  const fpEl = document.getElementById('session-fingerprint');
  if (state === 'playing') {
    showSessionFingerprint();
  } else if (state === 'stopped') {
    if (fpEl) fpEl.style.display = 'none';
    frozenFingerprint = '';
  }
});
```

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/main.ts` | Checklist logic + fingerprint display |
| `static/index.html` | Thêm checklist + fingerprint elements |
| `static/style.css` | Checklist + fingerprint styles |

### Files KHÔNG được touch

- `frontend/ReplayEngine.ts` — không cần sửa
- `frontend/DrawingManager.ts` — `getLineSnapshot()` đã có
- Backend — frontend only

### Scope Boundary

| Feature | P1-4.4 | Khác |
|---------|--------|------|
| Pre-flight checklist (✓/✗) | ✓ | |
| Play button disabled khi thiếu | ✓ | |
| Session Fingerprint header | ✓ | |
| Fingerprint frozen at Play | ✓ | |
| Checklist update real-time | ✓ | |
| Delta-time loop | ✗ | P1-4.1 |
| Look-ahead prevention | ✗ | P1-4.2-3 |
| Reset | ✗ | P1-4.3 |

### Edge Cases

1. **Vẽ 2 đường, xóa 1**: checklist update ngay → Play disabled
2. **Play, drag line**: fingerprint không đổi (frozen)
3. **Reset + Play lại**: fingerprint update với drawings mới
4. **Không có date range**: Date item hiển thị ✗ → Play disabled

## Dev Agent Record

### Agent Model Used

mimo-v2.5-pro

### Debug Log References

- Build: 326.4kb, esbuild 29ms
- Typecheck: passed (tsc --noEmit)

### Completion Notes List

- Pre-flight checklist: 3 items (Entry, TP, SL) — Play button disabled until all 3 drawn
- Checklist subscribes to drawing:lineChanged + drawing:cleared for real-time updates
- Session fingerprint: frozen at Play time, shows symbol/timeframe/date range/prices
- Fingerprint hidden on reset (replayStateChanged:stopped)
- Used DrawingManager.getSnapshot() instead of non-existent getLineSnapshot()

### File List

- `frontend/main.ts` — added updatePreflightChecklist(), showSessionFingerprint(), event wiring, Play button disabled logic, fingerprint show/hide
- `static/index.html` — added #preflight-checklist and #session-fingerprint elements
- `static/style.css` — added .preflight-checklist, .checklist-item--ok/missing, .session-fingerprint styles
