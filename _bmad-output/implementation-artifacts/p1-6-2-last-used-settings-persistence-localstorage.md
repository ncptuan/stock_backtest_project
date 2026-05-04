# Story P1-6.2: Last-used settings persistence qua localStorage

Status: done

## Story

As a returning trader,
I want my previous timeframe, date range, and drawing positions restored automatically,
So that I can continue practice sessions without reconfiguring from scratch.

## Acceptance Criteria

1. **Given** trader đã dùng app trước đó với timeframe 4h, date range và 3 đường đã vẽ
   **When** trader mở app lại (fresh page load)
   **Then** timeframe tự động set về giá trị đã lưu
   **And** date range tự động set về range đã lưu
   **And** drawings (Entry/TP/SL với prices đã lưu) được restore lên chart

2. **Given** localStorage bị corrupt hoặc không có dữ liệu saved
   **When** app load
   **Then** app load với defaults (timeframe 4h, date range 6 tháng gần nhất) — không crash
   **And** không có error message hiển thị cho user — degrade gracefully

3. **Given** trader thay đổi settings trong session
   **When** settings thay đổi
   **Then** localStorage được update ngay (debounced)

## Tasks / Subtasks

- [x] Task 1: Cập nhật `frontend/SettingsManager.ts` — Extend persistence (AC: #1, #2, #3)
  - [x] Thêm `drawings` vào PersistedSettings: `{ entry: number|null, tp: number|null, sl: number|null }`
  - [x] `save()`: include drawings snapshot
  - [x] `load()`: restore drawings nếu có
  - [x] Debounce save (500ms) để avoid excessive writes

- [x] Task 2: Cập nhật `frontend/types.ts` — Extend PersistedSettings (AC: #1)
  - [x] Thêm `drawings?: { entry: number|null, tp: number|null, sl: number|null }`

- [x] Task 3: Cập nhật `frontend/main.ts` — Restore drawings on load (AC: #1)
  - [x] Sau `settingsManager.load()`: check `settings.drawings`
  - [x] Nếu có drawings → `drawingManager.setLine()`
  - [x] Wire drawing changes → `settingsManager.save()`

- [x] Task 4: Error handling (AC: #2)
  - [x] Try/catch JSON.parse trong load()
  - [x] Default values khi corrupt

## Dev Notes

### SettingsManager Architecture

```typescript
// frontend/SettingsManager.ts

const STORAGE_KEY = 'btcReplay_lastSettings';

interface PersistedSettings {
  timeframe: string;
  dateStart: string;
  dateEnd: string;
  drawings?: {
    entry: number | null;
    tp: number | null;
    sl: number | null;
  };
}

class SettingsManager {
  private saveTimeout: number | null = null;

  save(settings: PersistedSettings): void {
    if (this.saveTimeout) clearTimeout(this.saveTimeout);
    this.saveTimeout = window.setTimeout(() => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
      } catch (e) {
        // localStorage full or disabled — silent fail
      }
    }, 500);
  }

  load(): PersistedSettings {
    const defaults: PersistedSettings = {
      timeframe: '4h',
      dateStart: this._sixMonthsAgo(),
      dateEnd: this._today(),
    };

    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return defaults;
      const parsed = JSON.parse(raw);
      return { ...defaults, ...parsed };
    } catch {
      return defaults;
    }
  }
}
```

### Restore Drawings Flow

```typescript
// frontend/main.ts — sau init

const settings = settingsManager.load();
currentSettings = settings;

// Restore drawings
if (settings.drawings) {
  const { entry, tp, sl } = settings.drawings;
  if (entry !== null && entry !== undefined) drawingManager.setLine('entry', entry);
  if (tp !== null && tp !== undefined) drawingManager.setLine('tp', tp);
  if (sl !== null && sl !== undefined) drawingManager.setLine('sl', sl);
}

// Auto-save on drawing changes
eventBus.on('drawing:lineChanged', () => {
  settingsManager.save({
    ...currentSettings,
    drawings: {
      entry: drawingManager.getEntryPrice() ?? null,
      tp: drawingManager.getTpPrice() ?? null,
      sl: drawingManager.getSlPrice() ?? null,
    },
  });
});

eventBus.on('drawing:cleared', () => {
  settingsManager.save({
    ...currentSettings,
    drawings: { entry: null, tp: null, sl: null },
  });
});
```

### Files cần modify

| File | Thay đổi |
|------|----------|
| `frontend/SettingsManager.ts` | Extend with drawings, debounce save |
| `frontend/types.ts` | Extend PersistedSettings interface |
| `frontend/main.ts` | Restore drawings + auto-save wiring |

### Files KHÔNG được touch

- `frontend/DrawingManager.ts` — `setLine()` đã có
- `frontend/ChartController.ts` — không liên quan
- Backend — frontend only

### Scope Boundary

| Feature | P1-6.2 | Khác |
|---------|--------|------|
| Persist timeframe + date range | ✓ | |
| Persist drawings (Entry/TP/SL) | ✓ | |
| Auto-restore on load | ✓ | |
| Debounced save | ✓ | |
| Graceful degradation | ✓ | |
| Empty state | ✗ | P1-6.1 |

### Edge Cases

1. **localStorage disabled (incognito)**: try/catch → use defaults
2. **Corrupt JSON**: try/catch → use defaults
3. **Saved drawing price out of current data range**: restore anyway — chart will show it
4. **Multiple tabs**: no sync — each tab has own state (acceptable for MVP)

## Dev Agent Record

### Agent Model Used
mimo-v2.5-pro

### Debug Log References
- TypeScript typecheck: pass
- esbuild bundle: pass (367.4kb)

### Completion Notes List
- Extended `PersistedSettings` interface with optional `drawings` field
- Added debounce (500ms) to `SettingsManager.save()` to avoid excessive localStorage writes
- `load()` preserves `drawings` field from parsed JSON
- Error handling: try/catch in both load() and save() with graceful degradation to defaults
- Restore flow: after `settingsManager.load()`, check `settings.drawings` and call `drawingManager.setLine()` for each non-null price
- Auto-save: `drawing:lineChanged` and `drawing:cleared` events trigger save with current drawings snapshot
- Drawing prices stored as `{ entry: number|null, tp: number|null, sl: number|null }`

### File List
- frontend/types.ts (modified: PersistedSettings.drawings optional field)
- frontend/SettingsManager.ts (modified: debounce save, preserve drawings in load)
- frontend/main.ts (modified: restore drawings on load, auto-save on drawing events)

## Review Findings (2026-05-03)

**Agents:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

### Patches Applied (1)

1. **handleLoad drops persisted drawings** — HIGH (Edge Case Hunter + Blind Hunter)
   - `handleLoad` created `newSettings` with `{ timeframe, dateStart, dateEnd }` — no `drawings` field
   - `doLoad` then saved these settings to localStorage via `settingsManager.save(settings)`, overwriting existing drawings
   - On next page load, drawings were gone
   - Fixed: `handleLoad` now passes `drawings: currentSettings.drawings` to preserve persisted drawings across date range changes
   - File: `frontend/main.ts`

### AC Results (Acceptance Auditor)

- AC#1: FULLY MET (restore timeframe, date range, drawings on load)
- AC#2: FULLY MET (graceful degradation on corrupt/missing localStorage)
- AC#3: FULLY MET (debounced save on settings change)

### Deferred

- save() race on page unload — 500ms debounce means changes within 500ms of tab close may be lost; setTimeout unreliable during page teardown, defer
- Debounce race: drawing save vs doLoad save — both use same 500ms debounce, whichever schedules last wins; mitigated by handleLoad fix preserving drawings, defer
- No runtime validation of drawings shape on load — corrupt localStorage entry with non-number drawings passes through; setLine handles NaN gracefully, defer
- Multi-tab write conflict — no `storage` event listener, two tabs silently overwrite each other; explicit per scope ("Multiple tabs: no sync"), defer

## Change Log

- 2026-05-03: Code review — applied 1 patch. Key fix: handleLoad preserves persisted drawings when saving new date range. All ACs fully met.
