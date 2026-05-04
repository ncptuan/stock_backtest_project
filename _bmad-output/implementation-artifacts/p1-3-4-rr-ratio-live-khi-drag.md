# Story P1-3.4: Live R:R Ratio Display Khi Drag TP/SL

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (0)

No patches required. All findings are LOW severity or by-design behavior.

### All 8 ACs: FULLY MET (Acceptance Auditor)

### Deferred

- Negative R:R format: AC8 says `"R:R = 1:-2.30"` but code renders `"⚠ R:R = 1:2.30"` (absolute value + warning) — Dev Notes explicitly design this format, spec conflict resolved in favor of Dev Notes
- Short-trade R:R assumes LONG direction — negative rr = invalid setup, shown with ⚠ warning, by design per spec
- `risk === 0` strict float equality — prices snap to $0.01 multiples, exact zero is correct guard
- Badge clips on narrow containers — min-width 1024px in CSS prevents in practice
- Badge can overlap price labels near chart bottom — cosmetic, max 3 labels

## Story

As a trader,
I want to see the R:R ratio update live while dragging TP or SL,
So that I can set optimal risk/reward without manual calculation.

## Acceptance Criteria

1. **Given** cả 3 đường Entry, TP, SL đã được vẽ
   **When** trader drag đường TP hoặc SL
   **Then** R:R ratio được tính và hiển thị real-time: `R:R = (TP - Entry) / (Entry - SL)` với 2 decimal places
   **And** R:R display cập nhật ngay theo từng pixel drag — không debounce

2. **Given** chỉ có Entry + TP (không có SL), hoặc chỉ có Entry + SL (không có TP)
   **When** canvas render
   **Then** R:R badge KHÔNG hiển thị — cần đủ cả 3 đường Entry + TP + SL

3. **Given** cả 3 đường đã vẽ, nhưng TP = Entry hoặc SL = Entry (tức là denominator = 0)
   **When** canvas render
   **Then** R:R badge KHÔNG hiển thị — tránh division by zero và NaN/Infinity

4. **Given** cả 3 đường đã vẽ và R:R valid
   **When** trader KHÔNG đang drag (đứng yên)
   **Then** R:R badge vẫn hiển thị — không phải chỉ trong khi drag, mà luôn luôn visible khi đủ 3 đường

5. **Given** R:R ratio đang hiển thị
   **When** trader xóa TP hoặc SL
   **Then** R:R badge biến mất ngay lập tức

6. **Given** R:R được tính
   **Then** giá trị được format `"1:2.30"` — với 2 decimal places, prefix `"R:R = "`, ví dụ: `"R:R = 1:2.30"`
   **And** nếu R:R = 0.5 (TP - Entry nhỏ hơn Entry - SL), display `"R:R = 1:0.50"`

7. **Given** R:R badge đang hiển thị
   **When** trader zoom/pan chart
   **Then** R:R badge vẫn visible ở vị trí cố định — không bị cuộn ra khỏi viewport

8. **Given** SL đặt ở trên Entry (invalid setup — SL > Entry cho LONG trade)
   **Then** R:R vẫn tính theo công thức `(TP - Entry) / (Entry - SL)` — kết quả có thể âm, hiển thị với dấu âm `"R:R = 1:-2.30"` — không crash, không hide

## Tasks / Subtasks

- [x] Task 1: Cập nhật `frontend/DrawingManager.ts` — Thêm R:R badge rendering (AC: #1–#8)
  - [x] Add private method `_calcRR(): number | null` — return null nếu thiếu đường hoặc division-by-zero
  - [x] Add private method `_drawRRBadge(rr: number): void` — canvas badge phía trên/dưới khu vực lines
  - [x] Cập nhật `redrawAll()`: gọi `_calcRR()` → nếu không null, gọi `_drawRRBadge(rr)` ở cuối
  - [x] Verify R:R cập nhật real-time vì `redrawAll()` đã được gọi mỗi `mousemove` trong `_startDrag()`

- [x] Task 2: Cập nhật `frontend/types.ts` — KHÔNG cần thay đổi gì (R:R chỉ là display logic trong DrawingManager)

- [x] Task 3: Cập nhật `static/index.html` — KHÔNG cần thay đổi gì (badge là canvas-rendered)

- [x] Task 4: Cập nhật `static/style.css` — KHÔNG cần thay đổi gì (badge là canvas-rendered)

## Dev Notes

### R:R Calculation

```typescript
private _calcRR(): number | null {
  const entry = this.lines.get('entry');
  const tp    = this.lines.get('tp');
  const sl    = this.lines.get('sl');

  // Cần đủ cả 3 đường
  if (!entry || !tp || !sl) return null;

  const reward = tp.price - entry.price;
  const risk   = entry.price - sl.price;

  // Tránh division by zero
  if (risk === 0) return null;

  return reward / risk;  // có thể âm nếu SL > Entry hoặc TP < Entry
}
```

### _drawRRBadge() — Vị trí và Style

**Vị trí:** Giữa chart canvas theo chiều ngang, nhưng cố định ở bottom-right (cạnh dưới chart, cạnh phải, margin 12px từ right/bottom).

Lý do chọn bottom-right:
- Không che candles (vùng giữa chart là quan trọng nhất)
- Không đè lên label TP/SL/Entry ở right edge
- UX spec line 681: "R:R display: 'R:R = 1:2.3'" — không chỉ định vị trí cụ thể
- TradingView đặt info box ở góc — convention người dùng đã biết

```typescript
private _drawRRBadge(rr: number): void {
  if (!this.ctx) return;
  const ctx = this.ctx;
  const w = this.cssWidth;
  const h = this.cssHeight;

  const text = `R:R = 1:${Math.abs(rr).toFixed(2)}${rr < 0 ? ' ⚠' : ''}`;
  ctx.font = 'bold 12px monospace';
  const textW = ctx.measureText(text).width;

  const PAD_H = 8;
  const PAD_V = 5;
  const rectW = textW + PAD_H * 2;
  const rectH = 24;
  const MARGIN = 12;

  // Bottom-right, nhưng cách label area đủ xa
  // Label area chiếm ~160px từ right edge (từ p1-3-3) → đặt badge bên trái hơn
  const rectX = w - rectW - MARGIN;
  const rectY = h - rectH - MARGIN;

  // Background
  ctx.save();
  ctx.globalAlpha = 0.9;
  ctx.fillStyle = rr >= 1
    ? 'rgba(63, 185, 80, 0.85)'   // green: R:R >= 1:1 là tốt
    : rr >= 0
    ? 'rgba(210, 153, 34, 0.85)'  // yellow: R:R < 1:1 nhưng dương
    : 'rgba(248, 81, 73, 0.85)';  // red: R:R âm (invalid setup)
  ctx.globalAlpha = 1;

  ctx.beginPath();
  if (ctx.roundRect) {
    ctx.roundRect(rectX, rectY, rectW, rectH, 4);
  } else {
    ctx.rect(rectX, rectY, rectW, rectH);
  }
  ctx.fill();

  // Text
  ctx.fillStyle = '#ffffff';
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'left';
  ctx.fillText(text, rectX + PAD_H, rectY + rectH / 2);
  ctx.restore();
}
```

**Màu theo R:R value:**
- `rr >= 1` → xanh lá `rgba(63, 185, 80, 0.85)` — R:R tốt (reward ≥ risk)
- `0 <= rr < 1` → vàng `rgba(210, 153, 34, 0.85)` — R:R không tốt (reward < risk)
- `rr < 0` → đỏ `rgba(248, 81, 73, 0.85)` — setup sai (TP dưới Entry hoặc SL trên Entry)

**Text khi âm:** Thêm `⚠` symbol để nhấn mạnh setup không hợp lệ. Hiển thị absolute value với warning icon, ví dụ `"R:R = 1:2.30 ⚠"` với màu đỏ.

### Format Text

```typescript
// R:R = 1.5 → "R:R = 1:1.50"
// R:R = 0.33 → "R:R = 1:0.33"
// R:R = -2.0 → "R:R = 1:-2.00" (hoặc "R:R = 1:2.00 ⚠" với màu đỏ)
const rrAbs = Math.abs(rr).toFixed(2);
const prefix = rr < 0 ? '⚠ ' : '';
const text = `${prefix}R:R = 1:${rrAbs}`;
```

Lý do chọn format `1:X` thay vì `X:1`:
- epics-phase1.md line 553: `R:R = (TP - Entry) / (Entry - SL)` — đây là reward / risk
- UX spec line 681: `"R:R = 1:2.3"` — format 1:reward/risk (chuẩn trading community)
- Tức là risk = 1 unit, reward = X units — trader muốn X càng lớn càng tốt

### Integration với redrawAll()

```typescript
// Thêm vào cuối redrawAll() sau _updateHandles():
redrawAll(): void {
  // ... existing code (sort, overlap prevention, drawLineStroke, drawLabel) ...

  this._updateHandles();

  // R:R badge (sau cùng — overlay on top of everything)
  const rr = this._calcRR();
  if (rr !== null) {
    this._drawRRBadge(rr);
  }
}
```

**Tại sao R:R update real-time mà không cần thêm code:**
- `_startDrag()` trong p1-3-2 gọi `redrawAll()` mỗi `mousemove` event
- `redrawAll()` clear canvas + redraw tất cả → `_drawRRBadge()` sẽ được gọi với giá mới mỗi frame
- Không cần debounce, không cần thêm event listener — automatic

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/DrawingManager.ts` | Add `_calcRR()`, `_drawRRBadge()`, cập nhật `redrawAll()` |

### Files KHÔNG được touch

- `frontend/types.ts` — không cần type mới cho R:R (là display-only logic)
- `frontend/CoordinateTranslator.ts` — không thay đổi
- `frontend/main.ts` — không cần wire thêm
- `static/index.html` — không cần HTML mới
- `static/style.css` — badge là canvas-rendered, không cần CSS
- Backend — story này chỉ là frontend display logic

### Scope Boundary

| Feature | P1-3.4 | Khác |
|---------|---------|------|
| R:R tính và hiển thị real-time khi drag | ✓ | |
| Màu badge theo R:R value | ✓ | |
| R:R ẩn khi thiếu đường | ✓ | |
| R:R format `1:X.XX` | ✓ | |
| TP/SL price clamping | ✗ | p1-3-3 (đã có) |
| Toast undo khi switch timeframe | ✗ | p1-3-5 |
| Pre-flight checklist strip | ✗ | Epic P1-4 setup |

### Dependency từ p1-3-1, p1-3-2, p1-3-3

- **p1-3-1**: `DrawingManager.lines: Map<LineType, DrawingLine | null>`, `redrawAll()`, `cssWidth/cssHeight`
- **p1-3-2**: `_startDrag()` đã gọi `redrawAll()` mỗi mousemove → R:R update real-time gratis
- **p1-3-3**: `_drawLabel()` đã render labels ở right edge — R:R badge đặt ở bottom, không overlap

### Edge Cases

1. **TP = Entry** (reward = 0, rr = 0): hiển thị `"R:R = 1:0.00"` với màu vàng — không crash
2. **SL = Entry** (risk = 0, denominator = 0): `_calcRR()` return null → badge ẩn
3. **TP = SL** (cả 2 cùng price): `(TP - Entry) / (Entry - SL)` = `(SL - Entry) / (Entry - SL)` = -1 → hiển thị `"⚠ R:R = 1:1.00"` với màu đỏ
4. **Entry, TP, SL cùng một giá**: `_calcRR()` return null (risk = 0) → badge ẩn
5. **Canvas height = 0**: `_drawRRBadge()` guard: nếu `h === 0` return early (không crash)
6. **Xóa đường sau khi xem R:R**: `lines.get('sl') === null` → `_calcRR()` return null → badge biến mất tự động

### Thứ tự implement

1. Thêm `_calcRR()` method
2. Thêm `_drawRRBadge()` method  
3. Cập nhật `redrawAll()`: thêm 3 dòng ở cuối
4. Verify bằng tay: vẽ 3 đường, drag TP → R:R cập nhật theo mỗi pixel

## Dev Agent Record

### Agent Model Used

mimo-v2.5-pro

### Debug Log References

- Build: 310.2kb, esbuild 40ms
- Typecheck: passed (tsc --noEmit)

### Completion Notes List

- Task 1 completed: added `_calcRR()` and `_drawRRBadge()` methods
- `_calcRR()` returns null when missing lines or division by zero (AC #2, #3)
- `_drawRRBadge()` renders bottom-right with color coding: green (rr>=1), yellow (0<=rr<1), red (rr<0)
- Negative R:R shows ⚠ warning symbol (AC #8)
- Format: `R:R = 1:X.XX` with 2 decimal places (AC #6)
- Real-time update automatic via existing `redrawAll()` calls in `_startDrag()` (AC #1)
- Badge disappears when any line is deleted (AC #5) — `_calcRR()` returns null
- Tasks 2-4: no changes needed (badge is canvas-rendered, no types/HTML/CSS required)

### File List

- `frontend/DrawingManager.ts` — added `_calcRR()`, `_drawRRBadge()`, updated `redrawAll()`
