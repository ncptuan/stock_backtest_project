# Story P1-3.2: Drag to Move + Delete Line

Status: done

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (3)

1. **`onMove`/`onUp` lack guards for container null + replayLocked mid-drag** — HIGH (Blind + Edge Case)
   - Extracted `cleanup()` helper that removes document listeners + resets cursor + clears `dragging`
   - `onMove`: guard `if (!this.container || this.replayLocked)` → cleanup and return
   - `onUp`: calls `cleanup()` first, then guards `if (!this.container || this.replayLocked)` → return
   - File: `DrawingManager.ts`

2. **`deleteSelected()` during drag on same line → line resurrection** — MED (Blind)
   - Added `this.lines.get(type)` check in `onMove` — if line was deleted, skip update
   - File: `DrawingManager.ts`

3. **`selectedType` survives `freeze()` → stale delete after unfreeze** — LOW (Blind)
   - Added `this.selectedType = null` in `freeze()`
   - File: `DrawingManager.ts`

### All 8 ACs: FULLY MET (Acceptance Auditor)

### Deferred

- Delete during active drag is benign no-op — could add UX cancel, defer
- Rapid container resize during drag causes cosmetic handle flicker — no crash, defer
- Handle mousedown listener lifecycle — confirmed correct, no leak

## Story

As a trader,
I want to reposition lines by dragging and delete them individually,
So that I can iterate on strategy variants quickly without redrawing from scratch.

## Acceptance Criteria

1. **Given** đường Entry/TP/SL đã được vẽ trên canvas (từ p1-3-1)
   **When** trader hover cursor lên gần một đường (trong ±5px Y từ đường)
   **Then** cursor đổi thành `ns-resize` — gợi ý có thể kéo dọc
   **And** LW Charts vẫn nhận pan/zoom events khi cursor không near bất kỳ đường nào

2. **Given** cursor đang near một đường
   **When** trader mousedown và drag theo chiều dọc
   **Then** đường di chuyển theo cursor real-time — không lag, smooth trên Chrome và Safari
   **And** price label (nếu đã có từ p1-3-3) cập nhật real-time theo giá mới trong khi drag

3. **Given** trader đang drag một đường
   **When** trader release mouse (mouseup)
   **Then** đường snap vào price: `Math.round(price * 100) / 100` ($0.01 tick)
   **And** đường ở lại vị trí mới — không revert về vị trí cũ

4. **Given** trader đang drag một đường và cursor ra ngoài chart container
   **When** mouseup xảy ra ở bất kỳ đâu trên document
   **Then** drag kết thúc bình thường — đường ở vị trí cursor lúc mouseup (nếu valid)
   **And** cursor trở về bình thường sau khi release

5. **Given** trader click lên gần một đường (không drag — moved < 3px)
   **When** mouseup xảy ra tại cùng vị trí mousedown
   **Then** đường đó được mark là "selected" (selected state được lưu internally)
   **And** drawing mode (activeType) bị cancel nếu đang active

6. **Given** trader đã click-select một đường
   **When** trader nhấn Delete hoặc Backspace
   **Then** đường bị xóa khỏi canvas ngay lập tức
   **And** trader có thể vẽ đường mới cùng loại ngay sau đó
   **And** `e.preventDefault()` được gọi để tránh browser back navigation (Backspace)

7. **Given** trader click lên vùng chart trống (không near bất kỳ đường nào)
   **When** click xảy ra
   **Then** selectedType bị deselect — Delete key không xóa gì

8. **Given** replay đang chạy (ReplayEngine.isRunning === true)
   **When** trader cố hover hoặc drag một đường
   **Then** cursor KHÔNG đổi thành `ns-resize` — handle divs bị disabled
   **And** drag không xảy ra — lines bị frozen trong Replay mode

## Tasks / Subtasks

- [x] Task 1: Cập nhật `frontend/DrawingManager.ts` — Thêm drag infrastructure (AC: #1–#5, #8)
  - [x] Add `private selectedType: LineType | null = null`
  - [x] Add `private replayLocked = false` — frozen khi replay running
  - [x] Add `private container: HTMLElement | null = null` (store trong init())
  - [x] Add `private handles = new Map<LineType, HTMLDivElement | null>`
  - [x] Tại cuối `redrawAll()`: gọi `this._updateHandles()`
  - [x] Implement `_updateHandles()` — tạo/cập nhật/ẩn handle divs theo line positions
  - [x] Implement `_startDrag(type: LineType, e: MouseEvent)` — document mousemove/mouseup pattern
  - [x] Add `freeze(): void` — set `replayLocked = true`, ẩn tất cả handles
  - [x] Add `unfreeze(): void` — set `replayLocked = false`, restore handles
  - [x] Add `deleteSelected(): boolean` — xóa selectedType nếu có, trả về true nếu deleted
  - [x] Add `setSelectedType(type: LineType | null): void` + `getSelectedType(): LineType | null`
  - [x] Cập nhật `_handleChartClick(param)`: thêm `this.selectedType = null` khi click trống

- [x] Task 2: Cập nhật `frontend/main.ts` — Thêm Delete/Backspace handler (AC: #6)
  - [x] Trong keydown handler đã có (ESC), thêm Delete/Backspace branch
  - [x] `drawingManager.deleteSelected()` → nếu true: `e.preventDefault()`

- [x] Task 3: Integrate với ReplayEngine lock (AC: #8)
  - [x] Subscribe `replayStateChanged` EventBus → `drawingManager.freeze()` / `drawingManager.unfreeze()`

## Dev Notes

### Vì sao dùng Handle Div, không phải Canvas Mouse Events

Canvas trong p1-3-1 được thiết kế với `pointer-events: none` để LW Charts nhận mouse events cho pan/zoom. Nếu đổi canvas thành `pointer-events: auto`, LW Charts mất khả năng zoom/pan.

**Giải pháp: Invisible "handle div" per line:**
```
chartContainer (position: relative)
  ├── LW Charts canvas (receives pan/zoom)
  ├── overlay canvas (pointer-events: none — drawings rendered here)
  └── handle div × 3 (position:absolute; pointer-events:auto; z-index:15)
       ↑ these are invisible, transparent, ~10px tall strips
         positioned at each drawn line's Y coordinate
         they intercept mousedown for drag WITHOUT blocking chart pan/zoom
         (since they only exist WHERE lines are drawn)
```

Khi không có đường → không có handle div → LW Charts nhận toàn bộ mouse events.
Khi có đường → handle div chỉ chiếm 10px strip tại đúng Y position của đường.

### _updateHandles() Implementation

```typescript
private _updateHandles(): void {
  if (!this.container || !this.translator.isInitialized()) return;

  for (const [type, line] of this.lines) {
    const existingHandle = this.handles.get(type) ?? null;

    if (!line || this.replayLocked) {
      // Remove handle
      if (existingHandle) {
        existingHandle.remove();
        this.handles.set(type, null);
      }
      continue;
    }

    const y = this.translator.priceToY(line.price);  // CSS pixel Y
    if (y === null || y < 0 || y > this.container.clientHeight) {
      // Line scrolled off screen — hide handle
      if (existingHandle) existingHandle.style.display = 'none';
      continue;
    }

    if (!existingHandle) {
      // Create new handle div
      const div = document.createElement('div');
      div.style.cssText = [
        'position:absolute',
        'left:0',
        'right:0',
        'height:10px',       // hit zone: ±5px
        'cursor:ns-resize',
        'z-index:15',
        'transform:translateY(-50%)',   // center on line Y
        'background:transparent',       // invisible
        'user-select:none',
      ].join(';');
      div.addEventListener('mousedown', (e) => this._startDrag(type, e));
      this.container.appendChild(div);
      this.handles.set(type, div);
    }

    const handle = this.handles.get(type)!;
    handle.style.display = 'block';
    handle.style.top = `${y}px`;
  }
}
```

**Lưu ý về `transform: translateY(-50%)`:**
Handle div có `top: {y}px` và `transform: translateY(-50%)` → center của div nằm tại Y của đường. Vì thế cursor `ns-resize` xuất hiện khi trong vùng ±5px của đường (10px / 2).

### _startDrag() Implementation

```typescript
private _startDrag(type: LineType, e: MouseEvent): void {
  e.preventDefault();   // prevent text selection during drag
  e.stopPropagation(); // prevent LW Charts receiving this mousedown

  if (this.replayLocked) return;

  const startY = e.clientY;
  let maxMoved = 0;

  // Set global drag cursor
  document.body.style.cursor = 'ns-resize';

  const onMove = (mv: MouseEvent) => {
    const moved = Math.abs(mv.clientY - startY);
    if (moved > maxMoved) maxMoved = moved;

    // Convert clientY to chart-relative CSS pixel Y
    const rect = this.container!.getBoundingClientRect();
    const cssY = mv.clientY - rect.top;

    const rawPrice = this.translator.yToPrice(cssY);
    if (rawPrice !== null) {
      // Real-time snap during drag (no debounce per AC)
      const dragging = Math.round(rawPrice * 100) / 100;
      this.lines.set(type, { type, price: dragging });
      this.redrawAll();
    }
  };

  const onUp = (up: MouseEvent) => {
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
    document.body.style.cursor = '';   // restore global cursor

    if (maxMoved < 3) {
      // Treat as click → select line, cancel drawing mode
      this.setActiveType(null);          // cancel any active drawing tool
      this.selectedType = type;
      this.onActiveTypeChange?.(null);   // update toolbar UI
    } else {
      // Drag end → final snap at release point
      const rect = this.container!.getBoundingClientRect();
      const cssY = up.clientY - rect.top;
      const rawPrice = this.translator.yToPrice(cssY);
      if (rawPrice !== null) {
        const finalPrice = Math.round(rawPrice * 100) / 100;
        this.lines.set(type, { type, price: finalPrice });
        this.redrawAll();
      }
    }
  };

  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onUp);
}
```

**Coordinate note:** `translator.yToPrice(cssY)` nhận CSS pixel Y (không nhân DPR). LW Charts API `coordinateToPrice(y)` nhận CSS pixel coordinate. `e.clientY - container.getBoundingClientRect().top` cho ra đúng CSS pixel Y relative to container.

**Drag threshold 3px:** Đủ để distinguish click vs drag ngay cả trên trackpad. Dưới 3px → click (select). Trên hoặc bằng 3px → drag.

### deleteSelected() Implementation

```typescript
deleteSelected(): boolean {
  if (!this.selectedType) return false;
  this.clearLine(this.selectedType);  // clearLine đã gọi redrawAll()
  this.selectedType = null;
  return true;
}

setSelectedType(type: LineType | null): void {
  this.selectedType = type;
}

getSelectedType(): LineType | null {
  return this.selectedType;
}
```

### freeze() / unfreeze() — Replay Lock

```typescript
freeze(): void {
  this.replayLocked = true;
  // Remove all handle divs — drag disabled in replay mode
  for (const [type, handle] of this.handles) {
    if (handle) {
      handle.remove();
      this.handles.set(type, null);
    }
  }
}

unfreeze(): void {
  this.replayLocked = false;
  // Handles will be recreated on next redrawAll()
  this.redrawAll();
}
```

### main.ts — Delete/Backspace Integration

```typescript
// Existing keydown handler (từ p1-3-1):
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    drawingManager.setActiveType(null);
  }
  // THÊM cho p1-3-2:
  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (drawingManager.deleteSelected()) {
      e.preventDefault();  // Prevent browser back navigation (Backspace)
    }
  }
});
```

### main.ts — Replay Lock Integration

Replay lock cần wire khi Play/Stop. Trong Epic P1-4 (ReplayEngine) sẽ có event. Cho story này: thêm placeholder comment và wire tạm với EventBus nếu event đã có.

```typescript
// Wire replay lock — EventBus 'replayStateChanged' (Phase 2 event đã có trong ReplayEngine.ts)
eventBus.on('replayStateChanged', ({ state }) => {
  if (state === 'playing') {
    drawingManager.freeze();
  } else if (state === 'stopped' || state === 'paused') {
    drawingManager.unfreeze();
  }
});
```

**Note:** `replayStateChanged` đã có trong `EventMap` (Phase 2). DrawingManager freeze khi `playing`, unfreeze khi `stopped`/`paused` (paused vẫn allow drawing adjustment theo UX spec).

Wait — check UX spec line 118: "Replay mode — drawing locked". Nhưng pause cũng là Replay mode theo UX spec (bars paused nhưng vẫn in replay mode). Cần xem xét cẩn thận:
- Epic 4 Story 4.2 AC: Reset → trở về Setup mode → drawings allowed
- Pause → vẫn in Replay mode → drawings locked
- Stop/Reset → Setup mode → unfreeze

**Rule cho story này:** `freeze()` khi `playing`. `unfreeze()` chỉ khi `stopped` (Reset). Pause vẫn frozen. Thực hiện đơn giản:

```typescript
eventBus.on('replayStateChanged', ({ state }) => {
  if (state === 'playing') {
    drawingManager.freeze();
  } else if (state === 'stopped') {
    drawingManager.unfreeze();
  }
  // 'paused': giữ nguyên frozen state
});
```

### _handleChartClick — Deselect on Empty Chart Click

Cần thêm deselect vào `_handleChartClick` trong DrawingManager (đã có từ p1-3-1):

```typescript
private _handleChartClick(param: MouseEventParams): void {
  this.selectedType = null;   // THÊM: deselect khi click empty chart area

  if (!this.activeType) return;
  if (!param.point) return;
  if (!this.translator.isInitialized()) return;
  // ... rest of existing logic
}
```

**Note:** `chart.subscribeClick` chỉ fire khi click LW Charts canvas (không có handle div tại điểm đó). Vì thế, click trên handle div KHÔNG deselect (handle div intercepts DOM event). Click trên empty chart area → chart.subscribeClick fires → deselect.

### Diagram: Event Flow

```
[Hover near line]
  Handle div mousedown
    → _startDrag(type, e)
      → document.mousemove: update line price + redrawAll + _updateHandles
      → document.mouseup: finalize snap + restore cursor
        IF maxMoved < 3: select line (selectedType = type)
        IF maxMoved >= 3: drag complete

[Delete selected line]
  document.keydown('Delete' / 'Backspace')
    → drawingManager.deleteSelected()
      → clearLine(selectedType) → redrawAll → _updateHandles (removes handle)
      → returns true → e.preventDefault()

[Click empty chart]
  chart.subscribeClick
    → _handleChartClick
      → selectedType = null   (deselect)
      IF activeType: place new line

[Replay starts]
  eventBus.on('replayStateChanged', { state: 'playing' })
    → drawingManager.freeze()
      → replayLocked = true, remove all handle divs
```

### Về pointer-events và LW Charts Compatibility

Khi handle div tồn tại:
- Handle div có `pointer-events: auto` và `z-index: 15`
- LW Charts canvas có lower z-index
- Mouse events trên handle div → intercepted by handle (drag starts)
- Mouse events on empty chart → LW Charts canvas gets them (pan/zoom works)

Khi không có handle div (no drawings, or replay frozen):
- Tất cả mouse events → LW Charts canvas → pan/zoom bình thường

**KHÔNG cần disable LW Charts pan/zoom** khi drag một line — vì drag chỉ xảy ra khi mousedown trên handle div, và document-level mousemove/mouseup handle phần còn lại.

### CSS cho Handle Divs

Handle divs không cần CSS trong style.css — styles được set inline trong JavaScript vì chúng là dynamically created. Không cần CSS class.

### Performance — redrawAll trong drag

`redrawAll` được gọi mỗi `mousemove` event trong khi drag. Điều này là intentional (per AC: "price label cập nhật real-time theo từng pixel drag"). Canvas operations (clearRect + strokePath) rất nhanh — không gây performance issue.

Nếu cần optimize cho slow devices: có thể throttle với `requestAnimationFrame`:
```typescript
// Optional optimization (MVP không cần):
private _rafPending = false;
private _scheduleRedraw(): void {
  if (this._rafPending) return;
  this._rafPending = true;
  requestAnimationFrame(() => {
    this._rafPending = false;
    this.redrawAll();
  });
}
```
**Không implement optimization trong story này** — chỉ gọi `redrawAll()` trực tiếp.

### Edge Cases

1. **Drag line off top/bottom of chart:** `yToPrice(cssY)` có thể return null khi Y out of range. Guard: `if (rawPrice !== null)` → line chỉ update khi price valid. Khi drag trở lại visible area: line resume updating.

2. **Two lines at same price:** Map<LineType, DrawingLine> không cho phép overlap — mỗi type là 1 key. Hai lines cùng type thì type-2 overwrites type-1 (đã xử lý trong p1-3-1).

3. **Draw mode active + hover near existing line:** Handle div có `z-index: 15` → mousedown trên handle → `_startDrag()` xử lý (không phải `_handleChartClick`). Trong `_startDrag`, nếu `maxMoved < 3` → `setActiveType(null)` cancel drawing mode và select line. Nếu drag: line moves, drawing mode vẫn active. Acceptable MVP behavior.

4. **Handle div position after zoom/pan:** `redrawAll()` được gọi bởi `subscribeVisibleLogicalRangeChange` và `subscribePriceScaleOptionsChanged` từ p1-3-1. Sau redrawAll, `_updateHandles()` cập nhật handle positions. Handles always stay in sync.

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/DrawingManager.ts` | Add: `handles` map, `_updateHandles()`, `_startDrag()`, `freeze()`, `unfreeze()`, `deleteSelected()`, `setSelectedType()`, `getSelectedType()`, `replayLocked`; update `redrawAll()` + `_handleChartClick()` + `destroy()` |
| `frontend/main.ts` | Add Delete/Backspace to keydown handler; subscribe `replayStateChanged` → freeze/unfreeze |

### Files KHÔNG được touch

- `frontend/CoordinateTranslator.ts` — không cần thay đổi
- `frontend/types.ts` — không cần type mới (`LineType`, `DrawingLine` đã đủ)
- `static/index.html` — không cần HTML mới
- `static/style.css` — handle divs dùng inline styles
- Backend files — story này chỉ là frontend

### Dependency từ p1-3-1

Story này extends `DrawingManager.ts` từ p1-3-1. Các methods đã có cần dùng:
- `clearLine(type)` → được gọi trong `deleteSelected()`
- `redrawAll()` → được gọi trong `_startDrag()` và `unfreeze()`
- `setActiveType(null)` → được gọi trong `_startDrag()` khi click (maxMoved < 3)
- `onActiveTypeChange` callback → trigger toolbar UI update sau setActiveType

### Thứ tự implement

1. `DrawingManager.ts`: Thêm fields + `_updateHandles()` + gọi từ `redrawAll()`
2. `DrawingManager.ts`: Thêm `_startDrag()` với document event pattern
3. `DrawingManager.ts`: Thêm `freeze()`, `unfreeze()`, `deleteSelected()`
4. `DrawingManager.ts`: Update `_handleChartClick()` với deselect + update `destroy()`
5. `main.ts`: Thêm Delete/Backspace handler + replay state subscriber

## Dev Agent Record

### Agent Model Used

mimo-v2.5-pro

### Debug Log References

- Build: 306.6kb, esbuild 40ms
- Typecheck: passed (tsc --noEmit)

### Completion Notes List

- All 3 tasks completed
- DrawingManager extended with handle div pattern for drag (invisible 10px strips at line Y positions)
- `_startDrag()` uses document-level mousemove/mouseup for smooth drag outside container
- Drag threshold: 3px — below = click/select, above = drag
- `freeze()` removes all handle divs; `unfreeze()` restores via redrawAll
- `deleteSelected()` clears selected line, returns boolean for preventDefault
- Replay lock wired via `replayStateChanged` EventBus event
- No new CSS needed — handle divs use inline styles

### File List

- `frontend/DrawingManager.ts` — added handles, _updateHandles, _startDrag, freeze/unfreeze, deleteSelected, selectedType, replayLocked
- `frontend/main.ts` — added eventBus import, Delete/Backspace handler, replay state subscriber
