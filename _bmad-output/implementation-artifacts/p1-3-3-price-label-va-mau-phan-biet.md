# Story P1-3.3: Price Label + Màu Phân Biệt

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (2)

1. **`_drawLabel()` leaks canvas context state — no save/restore** — MED (Blind + Edge Case)
   - Wrapped `_drawLabel()` body in `ctx.save()` / `ctx.restore()`
   - Prevents font, fillStyle, strokeStyle, textBaseline, setLineDash from bleeding into subsequent draw calls
   - File: `DrawingManager.ts`

2. **Overlap prevention pushes labels off-canvas bottom** — MED (Blind + Edge Case)
   - Added `labelY = Math.min(labelY, this.cssHeight - LABEL_HEIGHT / 2)` clamp after overlap adjustment
   - File: `DrawingManager.ts`

### All 8 ACs: FULLY MET (Acceptance Auditor)

### Deferred

- Label connector line for displaced labels (when overlap shifts label far from its line) — UX enhancement, defer
- rectX clamping on narrow containers (long price text + narrow panel) — min-width 1024px in CSS prevents, defer
- `_formatPrice` NaN/Infinity guard — upstream data validated, defer
- Sort determinism for same-price lines (secondary sort by type) — cosmetic, defer
- toLocaleString perf on every redraw — max 3 calls per frame, acceptable, defer

## Story

As a trader,
I want to see a price label on each drawn line showing the type and exact price,
So that I can read my Entry/TP/SL prices at a glance without hovering or guessing.

## Acceptance Criteria

1. **Given** đường Entry đã được vẽ trên canvas
   **When** canvas render
   **Then** label "Entry 68,500.00" xuất hiện tại phần tử phải của đường (cách right edge 8px)
   **And** label có nền màu xanh `rgba(47, 129, 247, 0.85)` (blue semi-transparent) với border-radius 3px
   **And** text màu trắng `#ffffff`, font 11px monospace, padding 2px 6px

2. **Given** đường TP đã được vẽ
   **When** canvas render
   **Then** label "TP 68,500.00" tại right edge
   **And** label có nền `rgba(63, 185, 80, 0.85)` (green semi-transparent)

3. **Given** đường SL đã được vẽ
   **When** canvas render
   **Then** label "SL 68,500.00" tại right edge
   **And** label có nền `rgba(248, 81, 73, 0.85)` (red semi-transparent)

4. **Given** price = 68500 (integer)
   **When** label render
   **Then** format hiển thị: `"68,500.00"` — comma separator, 2 decimal places
   **And** price = 68499.73 → `"68,499.73"`
   **And** price = 100000 → `"100,000.00"`

5. **Given** trader đang drag một đường
   **When** mouse di chuyển
   **Then** label cập nhật ngay lập tức với giá mới theo từng pixel drag — không debounce
   **And** label không flicker hoặc bị lag trong khi drag

6. **Given** trader đã click-select một đường (selectedType từ p1-3-2)
   **When** đường đó render
   **Then** label có border trắng 1px `rgba(255,255,255,0.8)` xung quanh để phân biệt selected state
   **And** đường line có lineWidth tăng +0.5px (Entry: 2.5, TP/SL: 2.0) — subtle thicker

7. **Given** trader đặt 2 đường có label gần nhau (< 15px Y distance)
   **When** canvas render
   **Then** label không bị overlap — label bên dưới được shift xuống để tránh overlap

8. **Given** price label đang hiển thị
   **When** trader zoom chart (visible range thay đổi)
   **Then** label vẫn ở right edge của canvas — không bị scroll ra ngoài vùng nhìn thấy

## Tasks / Subtasks

- [x] Task 1: Cập nhật `frontend/DrawingManager.ts` — Thêm label rendering vào `_drawLine()` (AC: #1–#6)
  - [x] Add label text constants: `LINE_LABEL: Record<LineType, string> = { entry: 'Entry', tp: 'TP', sl: 'SL' }`
  - [x] Add label background colors: `LINE_LABEL_BG: Record<LineType, string>` (rgba semi-transparent)
  - [x] Implement `_formatPrice(price: number): string` — `toLocaleString` với en-US, 2 decimal places
  - [x] Rename `_drawLine()` → `_drawLineStroke()`, thêm `isSelected` param
  - [x] Implement `_drawLabel(line, y, isSelected)` với roundRect + selected border
  - [x] Cập nhật `redrawAll()`: collect → sort → overlap-fix → draw stroke + label

- [x] Task 2: Thêm overlap prevention vào `redrawAll()` (AC: #7)
  - [x] Collect all `(type, y)` pairs cho non-null lines
  - [x] Sort by Y ascending
  - [x] Nếu `y[i+1] - y[i] < 15`: shift `y[i+1]` xuống để label không overlap
  - [x] Pass adjusted Y vào `_drawLabel()` (đường vẫn draw tại real Y — chỉ label bị adjusted)

## Dev Notes

### Canvas Label Rendering — Full Implementation

```typescript
// Constants thêm vào DrawingManager.ts (sau LINE_CONFIG)
const LINE_LABEL: Record<LineType, string> = {
  entry: 'Entry',
  tp:    'TP',
  sl:    'SL',
};

const LINE_LABEL_BG: Record<LineType, string> = {
  entry: 'rgba(47, 129, 247, 0.85)',   // --prim-blue-500 semi-transparent
  tp:    'rgba(63, 185, 80, 0.85)',    // --prim-green-500 semi-transparent
  sl:    'rgba(248, 81, 73, 0.85)',    // --prim-red-500 semi-transparent
};

const LABEL_FONT = '11px monospace';
const LABEL_PADDING_H = 6;   // horizontal padding in px
const LABEL_PADDING_V = 2;   // vertical padding in px
const LABEL_HEIGHT = 18;     // total label height: 11px font + 2*2px padding + rounding
const LABEL_RIGHT_MARGIN = 8; // px from right edge of canvas
```

### _formatPrice() — Locale-safe formatting

```typescript
private _formatPrice(price: number): string {
  return price.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}
```

**Lý do dùng `en-US` locale hardcode:** Tool là BTC/USDT trading tool — USD price convention (comma separator, dot decimal) là expected. Không dùng system locale vì user có thể có locale khác gây format khác nhau.

### _drawLabel() — Cụ thể từng bước

```typescript
private _drawLabel(
  line: DrawingLine,
  canvasY: number,         // CSS pixel Y (sau overlap adjustment)
  isSelected: boolean,
): void {
  if (!this.ctx || !this.canvas) return;
  const ctx = this.ctx;
  const canvasW = this.canvas.width / (window.devicePixelRatio || 1);  // CSS pixel width

  const text = `${LINE_LABEL[line.type]} ${this._formatPrice(line.price)}`;
  ctx.font = LABEL_FONT;
  const textW = ctx.measureText(text).width;
  const rectW = textW + LABEL_PADDING_H * 2;
  const rectH = LABEL_HEIGHT;
  const rectX = canvasW - rectW - LABEL_RIGHT_MARGIN;
  const rectY = canvasY - rectH / 2;  // center vertically on line

  // Background rect
  ctx.beginPath();
  ctx.fillStyle = LINE_LABEL_BG[line.type];
  if (ctx.roundRect) {
    ctx.roundRect(rectX, rectY, rectW, rectH, 3);
  } else {
    ctx.rect(rectX, rectY, rectW, rectH);  // fallback for older Safari
  }
  ctx.fill();

  // Selected border
  if (isSelected) {
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
    ctx.lineWidth = 1;
    ctx.setLineDash([]);
    ctx.stroke();
  }

  // Label text
  ctx.fillStyle = '#ffffff';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, rectX + LABEL_PADDING_H, canvasY);
}
```

**IMPORTANT — DPR scaling:** `this.canvas.width` là canvas pixel (×DPR). Để tính CSS pixel vị trí label, cần chia cho DPR. Hoặc nếu `_drawLabel` được gọi trong context đã `ctx.scale(dpr, dpr)`, thì dùng CSS pixels trực tiếp.

Vì p1-3-1 thiết lập `ctx.scale(dpr, dpr)` sau mỗi resize, **tất cả canvas 2D operations trong DrawingManager sử dụng CSS pixels**. Vì thế `canvasW = this.canvas.width / dpr` là đúng.

Alternatively — lưu CSS width riêng:
```typescript
private cssWidth = 0;
private cssHeight = 0;

private _resizeCanvas(container: HTMLElement): void {
  const dpr = window.devicePixelRatio || 1;
  this.cssWidth = container.clientWidth;
  this.cssHeight = container.clientHeight;
  this.canvas!.width = this.cssWidth * dpr;
  this.canvas!.height = this.cssHeight * dpr;
  this.canvas!.style.width = `${this.cssWidth}px`;
  this.canvas!.style.height = `${this.cssHeight}px`;
  this.ctx?.scale(dpr, dpr);  // reset scale after canvas resize
}
```

Sau đó dùng `this.cssWidth` thay vì `this.canvas.width / dpr` trong `_drawLabel`.

### Overlap Prevention trong redrawAll()

```typescript
redrawAll(): void {
  if (!this.ctx || !this.canvas) return;
  this.ctx.clearRect(0, 0, this.cssWidth, this.cssHeight);

  // Collect lines with their Y positions
  const drawItems: Array<{ line: DrawingLine; y: number }> = [];
  for (const line of this.lines.values()) {
    if (!line) continue;
    const y = this.translator.priceToY(line.price);
    if (y === null) continue;
    drawItems.push({ line, y });
  }

  // Sort by Y ascending (top to bottom)
  drawItems.sort((a, b) => a.y - b.y);

  // Adjust label Y positions to prevent overlap
  const MIN_LABEL_GAP = 15; // px minimum between label centers
  const labelYs: number[] = [];
  for (let i = 0; i < drawItems.length; i++) {
    let labelY = drawItems[i].y;
    // Check against previous label
    if (i > 0 && labelY - labelYs[i - 1] < MIN_LABEL_GAP) {
      labelY = labelYs[i - 1] + MIN_LABEL_GAP;
    }
    labelYs.push(labelY);
  }

  // Draw lines at real Y, labels at adjusted Y
  for (let i = 0; i < drawItems.length; i++) {
    const { line } = drawItems[i];
    const realY = drawItems[i].y;
    const labelY = labelYs[i];
    const isSelected = line.type === this.selectedType;

    this._drawLineStroke(line, realY, isSelected);
    this._drawLabel(line, labelY, isSelected);
  }

  // Update drag handle positions
  this._updateHandles();
}
```

### _drawLine split thành _drawLineStroke + _drawLabel

Từ p1-3-1, `_drawLine` vừa draw line vừa (sau story này) draw label. Cần refactor nhẹ:

```typescript
// Rename _drawLine → _drawLineStroke, thêm isSelected param
private _drawLineStroke(line: DrawingLine, y: number, isSelected: boolean): void {
  if (!this.ctx) return;
  const cfg = LINE_CONFIG[line.type];
  const ctx = this.ctx;

  ctx.save();
  ctx.beginPath();
  ctx.strokeStyle = cfg.color;
  // Selected: slightly thicker
  ctx.lineWidth = isSelected ? cfg.width + 0.5 : cfg.width;
  ctx.setLineDash(cfg.dash);
  ctx.moveTo(0, y);
  ctx.lineTo(this.cssWidth, y);
  ctx.stroke();
  ctx.restore();
}
```

### ctx.roundRect() Compatibility

`ctx.roundRect()` được support từ:
- Chrome 99+ (April 2022) ✅
- Safari 15.4+ (March 2022) ✅
- Firefox 112+ (April 2023) ✅

NFR26: Chrome latest + Safari latest → `roundRect` available. Vẫn nên có fallback `ctx.rect()` cho safety.

### Selected State — Visual

**Line thicker:** `lineWidth + 0.5` (Entry: 2→2.5, TP/SL: 1.5→2.0) — đủ để user nhận ra selected mà không làm visual rối.

**Label white border:** `rgba(255,255,255,0.8)` — trắng semi-transparent, dễ thấy trên mọi màu background (blue/green/red label).

**Không thêm glow/shadow** — performance concern với canvas shadow operations (shadow = expensive, không phù hợp với drag real-time).

### Vị trí Label: Right Edge

Label ở right edge của chart (không phải left, không phải center):
- Giống TradingView — mental model match (UX spec line 274)
- Không che candlestick data ở giữa chart
- Luôn visible dù user pan chart sang trái/phải — vì label position = `canvas.width - margin`

**Label không bị ảnh hưởng bởi chart pan/zoom** — vì position là CSS pixel relative to canvas edge, không phải time coordinate. Đây là behavior đúng: price label ở right edge, cố định, luôn thấy.

### Test Cases Tinh Tế

1. **Negative price (futures short):** `price = -100` → format `-100.00` — unlikely cho BTC nhưng format vẫn đúng
2. **Price = 0:** `0.00` — edge case, render OK
3. **3 lines tại cùng giá:** Giả sử Entry = TP = SL (user mistake). Labels sẽ shift: Entry ở Y, TP ở Y+15, SL ở Y+30. Không crash.
4. **Canvas width = 0 (hidden chart):** `_drawLabel` guard: nếu `this.cssWidth === 0` return early. Hoặc `if (!this.canvas) return`.
5. **DPR = 2 (Retina):** Verify label sharp, không blurry — vì `ctx.scale(dpr, dpr)` đã được setup trong resize.

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/DrawingManager.ts` | Add: `LINE_LABEL`, `LINE_LABEL_BG`, `_formatPrice()`, `_drawLabel()`, `_drawLineStroke()`; refactor `redrawAll()` với overlap prevention; add `cssWidth/cssHeight` fields |

### Files KHÔNG được touch

- `frontend/types.ts` — không cần type mới
- `frontend/CoordinateTranslator.ts` — không thay đổi
- `frontend/main.ts` — không cần wire thêm
- `static/index.html` — không cần HTML mới
- `static/style.css` — labels là canvas, không cần CSS
- Backend — story này chỉ là frontend

### Dependency từ p1-3-1 và p1-3-2

- **p1-3-1**: `DrawingManager._drawLine()`, `redrawAll()`, canvas setup với DPR scaling, `cssWidth/cssHeight` fields (hoặc phải add trong story này nếu p1-3-1 chưa có)
- **p1-3-2**: `selectedType` field → `isSelected` param cho `_drawLineStroke()` và `_drawLabel()`

**Nếu p1-3-1 chưa có `cssWidth/cssHeight`:** Thêm trong story này. Check DrawingManager implementation trước khi code.

### Thứ tự implement

1. Thêm `cssWidth`, `cssHeight` fields + update `_resizeCanvas()`
2. Thêm `LINE_LABEL`, `LINE_LABEL_BG` constants
3. Thêm `_formatPrice()` method
4. Rename `_drawLine()` → `_drawLineStroke()`, thêm `isSelected` param
5. Implement `_drawLabel()`
6. Refactor `redrawAll()`: collect → sort → overlap-fix → draw stroke + label

## Dev Agent Record

### Agent Model Used

mimo-v2.5-pro

### Debug Log References

- Build: 308.7kb, esbuild 38ms
- Typecheck: passed (tsc --noEmit)

### Completion Notes List

- Both tasks completed
- Added `cssWidth`/`cssHeight` fields for DPR-safe label positioning
- Refactored `_drawLine()` → `_drawLineStroke()` + `_drawLabel()` separation
- Labels: right-edge positioned, en-US locale formatting, roundRect with 3px radius
- Overlap prevention: sort by Y, shift labels down when < 15px gap
- Selected state: white border on label + 0.5px thicker line
- `roundRect` with `rect()` fallback for older Safari

### File List

- `frontend/DrawingManager.ts` — added LINE_LABEL, LINE_LABEL_BG, _formatPrice, _drawLabel, _drawLineStroke; refactored redrawAll with overlap prevention; added cssWidth/cssHeight fields
