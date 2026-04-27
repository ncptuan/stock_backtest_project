# Story 2.3: Per-Trade Reasoning Summary Textarea với Auto-Save

Status: done

## Story

As a trader,
I want draft reasoning của mình tự động được lưu khi tôi đang edit và được phục hồi khi mở lại ExportPreview,
So that tôi có thể customize context cho từng trade mà không sợ mất công nếu lỡ đóng preview.

## Acceptance Criteria

1. **Given** ExportPreview render với 31 trades — **When** trade list hiển thị — **Then** mỗi trade row có 1 textarea với: pre-filled template từ backend (`reasoning_template`), 2 rows mặc định, maxlength 500, placeholder text nếu template trống.

2. **Given** Narron click vào textarea của trade #5 — **When** focus event — **Then** textarea expand từ 2 → 5 rows + character counter xuất hiện "87/500" phía dưới textarea.

3. **Given** Narron đang ở trong ExportPreview — **When** dùng Tab key — **Then** focus nhảy sang textarea của trade tiếp theo — keyboard navigation qua toàn bộ trade list (Tab = next, Shift+Tab = prev).

4. **Given** Narron đã edit textarea của trade #3 và 3 giây trôi qua kể từ lần gõ cuối — **When** debounce timer fire — **Then** draft được lưu vào `sessionStorage` với key `export_draft_{session_filename}` — silent save, không có UI feedback (không toast, không spinner).

5. **Given** draft đã lưu trong sessionStorage và Narron mở lại ExportPreview cho cùng session — **When** ExportPreview render — **Then** textarea content được restore từ sessionStorage — toast "Đã khôi phục draft trước đó" hiển thị 3 giây — edited textareas hiển thị lại nội dung đã sửa.

6. **Given** Narron xóa hết nội dung của textarea của trade #7 — **When** textarea blur với value rỗng — **Then** border highlight yellow-300 + hint text "Trống — pre-fill template đã bị xóa" xuất hiện bên dưới textarea — **Không block** Confirm Export.

7. **Given** export thành công (sau `exportpreview:confirmed`) hoặc Narron reset sang session mới — **When** cleanup trigger — **Then** `sessionStorage.removeItem('export_draft_{session_filename}')` — draft không persist sang session sau.

## Tasks / Subtasks

Story 2.3 **thêm vào** `frontend/ExportPreview.ts` (đã tạo trong Story 2.2) — không tạo file mới, không thay thế logic cũ.

- [x] Task 1: Textarea expand-on-focus và character counter trong `ExportPreview.ts` (AC: #2, #3)
  - [ ] Trong `render()`: textareas đã có `rows="2"` (từ Story 2.2) — thêm `data-min-rows="2"` và `data-max-rows="5"` attributes
  - [ ] Wire `focus` event trên mỗi textarea: set `rows = 5`
  - [ ] Wire `blur` event trên mỗi textarea: set `rows = 2` nếu value.trim() === pre-filled template (không edit); giữ 5 nếu đã edit — hoặc đơn giản hơn: luôn set về `rows = 2` khi blur
  - [ ] Focus event: tạo/update character counter `<span class="char-counter">` bên dưới textarea — hiển thị `{currentLength}/500`
  - [ ] `input` event trên textarea: update counter
  - [ ] Blur event: ẩn hoặc giữ counter (xem UX note bên dưới) + trigger blank check
  - [ ] Blank check khi blur: nếu value.trim() === '' → thêm class `textarea--blank` + render hint "Trống — pre-fill template đã bị xóa" bên dưới; nếu value !== '' → xóa class + hint
  - [ ] Tab navigation: textareas mặc định đã có tabindex; verify `tabIndex` không bị xóa trong render

- [x] Task 2: Auto-save draft vào sessionStorage trong `ExportPreview.ts` (AC: #4, #7)
  - [ ] Thêm private field `_saveTimer: ReturnType<typeof setTimeout> | null = null` vào class ExportPreview
  - [ ] Thêm private field `_draftKey: string | null = null` (set khi `open()` được gọi: `export_draft_${filename}`)
  - [ ] Trong `open()`: set `this._draftKey = \`export_draft_${filename}\``
  - [ ] Implement `_scheduleSave()`: cancel timer cũ → set timer 3000ms → callback gọi `_saveDraft()`
  - [ ] Implement `_saveDraft()`: collect tất cả textarea values vào object `{ [tradeIndex]: value }` → `sessionStorage.setItem(this._draftKey!, JSON.stringify(draft))` wrapped in `try/catch QuotaExceededError` → fail silently
  - [ ] Wire `input` event trên mỗi textarea: gọi `this._scheduleSave()`
  - [ ] Implement `_clearDraft()`: `if (this._draftKey) sessionStorage.removeItem(this._draftKey)`
  - [ ] Gọi `_clearDraft()` từ: `cleanup()` sau export success (khi `force=true`) và khi ExportPanel nhận signal reset session
  - [ ] Trong `cleanup()`: cancel `_saveTimer` (clearTimeout) để không fire sau khi overlay đã đóng

- [x] Task 3: Draft restore khi mở lại ExportPreview trong `ExportPreview.ts` (AC: #5)
  - [ ] Trong `open()` sau khi DOM đã render: gọi `_tryRestoreDraft()`
  - [ ] Implement `_tryRestoreDraft()`:
    1. `const raw = sessionStorage.getItem(this._draftKey!)`
    2. Nếu null/empty → return (không toast)
    3. Parse JSON → `draft: { [tradeIndex]: string }`
    4. Với mỗi `tradeIndex` có trong draft: tìm `textarea[data-trade-index="${tradeIndex}"]` → set `value = draft[tradeIndex]`
    5. Gọi `_setHasEdited()` nếu có ít nhất 1 textarea restored
    6. Hiển thị toast "Đã khôi phục draft trước đó" 3 giây (dùng toastManager nếu có, fallback: tạo inline toast element trong overlay)
  - [ ] Inline toast fallback: nếu toastManager không available → tạo `<div class="export-preview-toast">Đã khôi phục draft trước đó</div>` append vào overlay, auto-remove sau 3s

- [x] Task 4: CSS additions trong `static/style.css` (AC: #2, #6)
  - [ ] `.trade-reasoning-textarea:focus { rows attribute handled via JS }` (không có pure CSS solution)
  - [ ] `.char-counter { font-size: 11px; color: var(--sem-text-secondary); text-align: right; display: none; }` — hiển thị khi textarea focused
  - [ ] `.char-counter--visible { display: block; }`
  - [ ] `.textarea--blank { border-color: var(--prim-yellow-300, #d29922) !important; }`
  - [ ] `.textarea-blank-hint { font-size: 11px; color: var(--prim-yellow-300, #d29922); margin-top: 2px; display: none; }`
  - [ ] `.textarea-blank-hint--visible { display: block; }`
  - [ ] `.export-preview-toast { position: sticky; top: 56px; z-index: 20; background: var(--sem-bg-panel); border: 1px solid var(--sem-border); border-radius: 4px; padding: 6px 12px; font-size: 12px; color: var(--sem-text-primary); text-align: center; margin: 4px 16px; }`

## Dev Notes

### ⚠️ CRITICAL: ADD Vào ExportPreview.ts — Không Tạo Lại

Story 2.3 chỉ **thêm phương thức và event listeners** vào `class ExportPreview` đã tạo trong Story 2.2.

> **Pattern thêm vào ExportPreview.ts:**
> 1. Thêm private fields mới vào đầu class
> 2. Thêm calls trong `open()` (sau render: `_tryRestoreDraft()`, set `_draftKey`)
> 3. Thêm wire trong `render()` (thêm vào event listener loops có sẵn)
> 4. Thêm calls trong `cleanup()` (clearTimeout, cancel _saveTimer)
> 5. Thêm methods mới vào cuối class
>
> **Không** xóa/thay đổi bất kỳ logic nào từ Story 2.2.

---

### sessionStorage Draft Schema

**Key format:** `export_draft_{filename}`

Ví dụ: `export_draft_BTCUSDT_4h_20260420.parquet`

**Value format:**
```json
{
  "0": "4H | Entry $43,250 | EMA20=$42,100 | EMA50=$41,800 | Vol=1.8x | Outcome: WIN — lesson: entry confirmed by EMA20 cross",
  "3": "",
  "7": "Tùy chỉnh của Narron cho trade #8"
}
```

- Keys: trade index (string, vì JSON keys là string)
- Values: current textarea content (kể cả empty string nếu user xóa hết)
- **Chỉ lưu indexes đã thay đổi** để tiết kiệm storage — HOẶC lưu tất cả (simpler, acceptable)
- Recommendation: lưu tất cả indexes để restore đơn giản hơn

**Không lưu** strategy name input vào draft — chỉ textareas của trades.

---

### Auto-Save Strategy — Debounce 3s

```typescript
private _scheduleSave(): void {
  if (this._saveTimer !== null) {
    clearTimeout(this._saveTimer);
  }
  this._saveTimer = setTimeout(() => {
    this._saveDraft();
    this._saveTimer = null;
  }, 3000);
}

private _saveDraft(): void {
  if (!this._draftKey || !this.overlay) return;
  const textareas = this.overlay.querySelectorAll('.trade-reasoning-textarea');
  const draft: Record<string, string> = {};
  textareas.forEach((ta, i) => {
    draft[String(i)] = (ta as HTMLTextAreaElement).value;
  });
  try {
    sessionStorage.setItem(this._draftKey, JSON.stringify(draft));
  } catch (e) {
    // QuotaExceededError — fail silently
  }
}
```

**Trigger:** `input` event trên bất kỳ textarea nào → `_scheduleSave()`

**Cleanup:** `clearTimeout(this._saveTimer)` trong `cleanup()` để cancel pending save sau khi overlay đóng.

---

### Draft Restore — Chi Tiết Implementation

```typescript
private _tryRestoreDraft(): void {
  if (!this._draftKey || !this.overlay) return;
  let raw: string | null = null;
  try {
    raw = sessionStorage.getItem(this._draftKey);
  } catch {
    return;  // private mode / storage blocked
  }
  if (!raw) return;

  let draft: Record<string, string>;
  try {
    draft = JSON.parse(raw) as Record<string, string>;
  } catch {
    return;  // corrupt data
  }

  let restored = 0;
  Object.entries(draft).forEach(([idx, value]) => {
    const ta = this.overlay!.querySelector(
      `.trade-reasoning-textarea[data-trade-index="${idx}"]`
    ) as HTMLTextAreaElement | null;
    if (ta) {
      ta.value = value;
      restored++;
      // Trigger blank check on restored empty textareas
      if (value.trim() === '') {
        ta.classList.add('textarea--blank');
        this._showBlankHint(ta);
      }
    }
  });

  if (restored > 0) {
    this._hasEdited = true;
    this._showRestoreToast();
  }
}

private _showRestoreToast(): void {
  // Try global toastManager first
  if (typeof (window as any).toastManager !== 'undefined') {
    (window as any).toastManager.show('Đã khôi phục draft trước đó', 'info');
    return;
  }
  // Fallback: inline toast within overlay
  const toast = document.createElement('div');
  toast.className = 'export-preview-toast';
  toast.textContent = 'Đã khôi phục draft trước đó';
  // Insert after summary bar (first child = header, second = summary, third = trade list)
  const tradeList = this.overlay!.querySelector('.export-preview-trade-list');
  tradeList?.insertAdjacentElement('beforebegin', toast);
  setTimeout(() => toast.remove(), 3000);
}
```

---

### Character Counter + Expand — Event Wiring

Thêm vào loop `this.overlay.querySelectorAll('.trade-reasoning-textarea').forEach(...)` trong `render()`:

```typescript
this.overlay.querySelectorAll('.trade-reasoning-textarea').forEach((ta) => {
  const textarea = ta as HTMLTextAreaElement;

  // Story 2.2 wires: input → _hasEdited, input → _scheduleSave (Story 2.3)
  textarea.addEventListener('input', () => {
    this._hasEdited = true;
    this._scheduleSave();          // Story 2.3
    this._updateCharCounter(textarea);  // Story 2.3
  });

  // Story 2.3: expand on focus + show counter
  textarea.addEventListener('focus', () => {
    textarea.rows = 5;
    this._showCharCounter(textarea);
  });

  // Story 2.3: collapse on blur + blank check
  textarea.addEventListener('blur', () => {
    textarea.rows = 2;
    this._hideCharCounter(textarea);
    this._checkBlankTextarea(textarea);
  });
});
```

---

### Blank Textarea — Chi Tiết

```typescript
private _checkBlankTextarea(textarea: HTMLTextAreaElement): void {
  const hint = textarea.nextElementSibling?.classList.contains('textarea-blank-hint')
    ? (textarea.nextElementSibling as HTMLElement)
    : null;

  if (textarea.value.trim() === '') {
    textarea.classList.add('textarea--blank');
    if (hint) {
      hint.textContent = 'Trống — pre-fill template đã bị xóa';
      hint.classList.add('textarea-blank-hint--visible');
    }
  } else {
    textarea.classList.remove('textarea--blank');
    if (hint) {
      hint.classList.remove('textarea-blank-hint--visible');
    }
  }
}

private _showBlankHint(textarea: HTMLTextAreaElement): void {
  const hint = textarea.nextElementSibling as HTMLElement | null;
  if (hint?.classList.contains('textarea-blank-hint')) {
    hint.textContent = 'Trống — pre-fill template đã bị xóa';
    hint.classList.add('textarea-blank-hint--visible');
  }
}
```

**Quan trọng:** Render mỗi trade row phải thêm blank-hint element SAU textarea:

```html
<textarea class="trade-reasoning-textarea" ...>...</textarea>
<span class="textarea-blank-hint"></span>
```

Thêm vào template string trong `renderTradeRow()` của Story 2.2.

---

### Character Counter DOM Pattern

Tương tự blank hint — render counter element SAU textarea và blank-hint:

```html
<textarea class="trade-reasoning-textarea" ...>...</textarea>
<span class="textarea-blank-hint"></span>
<span class="char-counter"></span>
```

```typescript
private _showCharCounter(textarea: HTMLTextAreaElement): void {
  const counter = this._getCharCounter(textarea);
  if (counter) {
    counter.textContent = `${textarea.value.length}/500`;
    counter.classList.add('char-counter--visible');
  }
}

private _hideCharCounter(textarea: HTMLTextAreaElement): void {
  const counter = this._getCharCounter(textarea);
  counter?.classList.remove('char-counter--visible');
}

private _updateCharCounter(textarea: HTMLTextAreaElement): void {
  const counter = this._getCharCounter(textarea);
  if (counter?.classList.contains('char-counter--visible')) {
    counter.textContent = `${textarea.value.length}/500`;
  }
}

private _getCharCounter(textarea: HTMLTextAreaElement): HTMLElement | null {
  // char-counter is 2nd sibling after textarea
  const next1 = textarea.nextElementSibling;  // blank-hint
  const next2 = next1?.nextElementSibling;     // char-counter
  return (next2?.classList.contains('char-counter') ? next2 : null) as HTMLElement | null;
}
```

---

### Draft Cleanup — Khi Nào Clear

| Trigger | Method | Lý do |
|---------|--------|-------|
| Export success (`exportpreview:confirmed` fired, `cleanup(force=true)`) | `_clearDraft()` trong `cleanup()` khi `force=true` | Draft đã được submit, không cần giữ |
| Narron đóng ExportPreview khi đã confirm close dialog | `cleanup()` thường (force=false) — **KHÔNG** clear draft | User chỉ đóng, chưa export — giữ draft để restore sau |
| ExportPanel nhận session reset signal (Story 2.4: `replayStateChanged: stopped`) | `exportPanel.clearDraftForSession(filename)` | Session cũ reset, trades array clear |

> **Key insight:** Draft chỉ bị xóa khi **export thành công** hoặc **session bị reset**. Khi user đóng ExportPreview mà chưa export → draft VẪN CÒN trong sessionStorage → lần mở lại sẽ restore.

---

### Tích Hợp với ExportPanel (Story 2.4)

Story 2.4 sẽ cần biết filename để clear draft khi session reset. Thêm method public vào ExportPanel (Story 2.3 không cần implement, nhưng dev nên biết để không block):

```typescript
// Trong ExportPanel (Story 2.4 sẽ gọi method này):
clearDraftForSession(filename: string): void {
  sessionStorage.removeItem(`export_draft_${filename}`);
}
```

Story 2.3 không cần implement method này — đây là context cho Story 2.4 dev.

---

### renderTradeRow() — Updated Với Story 2.3 Elements

Story 2.3 thêm 2 elements vào `renderTradeRow()` (phương thức đã có từ Story 2.2). Dev phải **thêm vào** template string, không tạo lại method:

```typescript
// Thay đổi trong renderTradeRow() — thêm 2 dòng sau </textarea>:
`<textarea
  class="trade-reasoning-textarea"
  data-trade-index="${index}"
  ...
>${this.escapeHtml(trade.reasoning_template)}</textarea>
<span class="textarea-blank-hint"></span>
<span class="char-counter"></span>`
```

---

### UX Notes

**Tại sao silent auto-save (không toast)?**
- 3-second debounce save: Narron đang trong flow edit → toast interrupt sẽ distract
- Draft restore (khi mở lại): CÓ toast vì user cần biết content đã được khôi phục, không phải fresh pre-fill

**Blank warning không block Confirm:**
- Pre-fill template là valid reasoning — Narron không bắt buộc phải edit
- Blank = user chủ động xóa → warning là signal, không phải blocker
- Bot học tốt hơn từ reasoning nhưng Narron vẫn được phép export với blank reasoning

**rows 2 → 5 khi focus, 5 → 2 khi blur:**
- 2 rows mặc định để list trades compact, dễ scroll qua
- 5 rows khi edit để đủ chỗ nhìn thấy nội dung đã viết
- Blur về 2 rows giảm visual noise cho trades chưa/đã edit

**Không lưu draft khi user chỉ navigate (blur mà không edit):**
- `_scheduleSave()` chỉ trigger khi `input` event, không phải `blur`
- Nếu Narron scroll qua mà không gõ gì → sessionStorage không bị write

---

### Phụ Thuộc

Story 2.3 phụ thuộc:
- **Story 2.2 phải complete:** `frontend/ExportPreview.ts` phải tồn tại với `class ExportPreview`, `renderTradeRow()`, `cleanup()`, `open()`
- **Story 2.2:** textareas phải có `data-trade-index` attribute (dùng để map với draft keys)

Story 2.3 **không** phụ thuộc:
- Story 2.4 (trades array) — Story 2.3 là pure UX enhancement, không liên quan đến trades data
- Backend — không có backend changes trong Story 2.3

---

### Files Modified trong Story 2.3

| File | Change |
|------|--------|
| `frontend/ExportPreview.ts` | **THÊM VÀO** private fields, methods, event wires — không thay thế |
| `static/style.css` | Thêm `.char-counter`, `.textarea--blank`, `.textarea-blank-hint`, `.export-preview-toast` |

**Không tạo file mới.**
**Không sửa** backend, EventBus, SessionListPanel, QualityGateBlock, types.ts.

---

### NFR Compliance

- **NFR3 (Medium):** UI feedback < 100ms — expand-on-focus là đồng bộ (rows attribute set), không async
- **NFR-storage:** sessionStorage `try/catch QuotaExceededError` — fail silently không crash app
- **NFR5 (Critical):** Không hardcode credentials — Story 2.3 chỉ dùng sessionStorage, không liên quan đến credentials

### References

- [epics.md - Story 2.3 Acceptance Criteria](_bmad-output/planning-artifacts/epics.md#story-23-per-trade-reasoning-summary-textarea-với-auto-save)
- [ux-design-specification.md - reasoning_summary textarea behaviors (line 1813)](_bmad-output/planning-artifacts/ux-design-specification.md)
- [prd-phase2-supabase.md - FR8, FR35](_bmad-output/planning-artifacts/prd-phase2-supabase.md)
- [2-2-exportpreview-component-per-trade-list-voi-scroll-gate.md - ExportPreview base](_bmad-output/implementation-artifacts/2-2-exportpreview-component-per-trade-list-voi-scroll-gate.md)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

### Completion Notes List

- Tất cả 4 tasks hoàn thành. tsc --noEmit exit 0. 24 pytest tests vẫn pass (không có backend changes trong story này).
- **Task 1**: Thêm `focus` (rows=5, showCharCounter) + `blur` (rows=2, hideCharCounter, checkBlank) + `input` (đã bao gồm _scheduleSave + _updateCharCounter) event listeners vào textarea loop trong `render()`. Thêm `<span class="textarea-blank-hint">` + `<span class="char-counter">` sau mỗi textarea trong `renderTradeRow()`.
- **Task 2**: Thêm private fields `_saveTimer` + `_draftKey`. `_scheduleSave()` debounce 3s. `_saveDraft()` collect tất cả textarea values vào `sessionStorage` với `try/catch QuotaExceededError`. `_clearDraft()` gọi từ `cleanup(clearDraft=true)` khi export success (`handleConfirm` gọi `cleanup(true)`).
- **Task 3**: `_tryRestoreDraft()` gọi sau render trong `open()`. Parse JSON, set textarea.value, gọi `_showRestoreToast()` inline fallback (vì không có global toastManager).
- **Task 4**: Thêm `.char-counter`, `.char-counter--visible`, `.textarea--blank`, `.textarea-blank-hint`, `.textarea-blank-hint--visible`, `.export-preview-toast` vào `static/style.css`.

### File List

- `frontend/ExportPreview.ts` — MODIFIED (thêm fields, methods, event wires; không có file mới)
- `static/style.css` — MODIFIED (thêm CSS classes cho Story 2.3)

### Review Findings

- [x] [Review][Defer] AC3 Tab/Shift+Tab navigation — native Tab browser behavior đủ cho MVP; custom focus trap + wrap-around defer sang Story 4.x UX refinement sprint [frontend/ExportPreview.ts] — deferred, native Tab hoạt động đúng DOM order
- [x] [Review][Patch] F1: `_saveDraft()` dùng positional index `i` thay vì `data-trade-index` — không nhất quán với `_tryRestoreDraft()` [frontend/ExportPreview.ts:357] — fixed
- [x] [Review][Patch] F2: `open()` không cancel `_saveTimer` từ session cũ — stale timer có thể fire sau khi `_draftKey` đã đổi [frontend/ExportPreview.ts:21] — fixed
- [x] [Review][Patch] F3: `replayStateChanged:stopped` xóa sessionStorage nhưng không cancel pending `_saveTimer` trong ExportPreview — draft bị re-create ngay sau khi xóa [frontend/export_panel.ts:114-135] — fixed
- [x] [Review][Patch] F5: `_saveDraft()` save ALL textareas kể cả unedited → `restored` count luôn = total trades → restore toast fire ngay cả khi user chưa edit gì [frontend/ExportPreview.ts:353-365] — fixed
- [x] [Review][Patch] F6: `open()` không clear previous session's draft trước khi overwrite `_draftKey` — stale drafts tích tụ trong sessionStorage [frontend/ExportPreview.ts:26-32] — fixed
- [x] [Review][Patch] F11: `.quality-fail` CSS class thiếu color rule — badge hiển thị default color thay vì màu cảnh báo [static/style.css:595] — fixed
- [x] [Review][Patch] F12: `_tryRestoreDraft()` set `_hasEdited=true` kể cả khi restored values = original template → close dialog fire sai khi user chưa thực sự edit [frontend/ExportPreview.ts:408-410] — fixed
- [x] [Review][Defer] F8: `_checkBlankTextarea()` chỉ fire trên `blur`, không fire trên `input` — blank warning không xuất hiện nếu user xóa rồi click Confirm không qua blur [frontend/ExportPreview.ts:134] — deferred, UX advisory only, không block export
- [x] [Review][Defer] F9: `data-min-rows`/`data-max-rows` attributes render nhưng không được đọc trong JS logic [frontend/ExportPreview.ts:180-181] — deferred, dead attributes, cosmetic
- [x] [Review][Defer] F10: Glow `setTimeout(800ms)` không cancel trong `cleanup()` — fires trên detached DOM node [frontend/ExportPreview.ts:247] — deferred, no-op trên detached DOM, không gây crash
- [x] [Review][Defer] F13: `cleanup(true)` clear draft trước khi export listener có thể fail-recover — design tradeoff Story 3.x [frontend/ExportPreview.ts:305] — deferred, depends on Story 3.x error handling design
- [x] [Review][Defer] F14: `.export-preview-toast` position:sticky có thể không hoạt động đúng trong flex column context [static/style.css:769] — deferred, marginal layout risk, MVP acceptable
- [x] [Review][Defer] F15: `_getCharCounter()` + `_checkBlankTextarea()` brittle sibling traversal — break nếu thêm element giữa textarea và hint [frontend/ExportPreview.ts:453-474] — deferred, không phải regression hôm nay
