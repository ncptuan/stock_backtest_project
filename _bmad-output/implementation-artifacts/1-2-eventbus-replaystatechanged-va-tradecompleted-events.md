# Story 1.2: EventBus — replayStateChanged và tradeCompleted Events

Status: done

## Story

As a trader,
I want trạng thái replay và data từng trade completed được expose qua EventBus,
so that ExportPanel có thể biết khi nào replay stopped và có đủ trade data để chuẩn bị export.

## Acceptance Criteria

1. **Given** `types.ts` EventMap interface — **When** developer thêm 2 events mới — **Then** TypeScript compile không có error: `replayStateChanged: { state: 'playing' | 'paused' | 'stopped' }` và `tradeCompleted: { bar_index: number; entry_timestamp_ms: number; direction: 'LONG' | 'SHORT'; entry_price: number; tp_price: number; sl_price: number; result: 'win' | 'loss'; bars_to_exit: number }`.

2. **Given** replay đang chạy và một trade hit (TP hoặc SL chạm) — **When** ReplayEngine detect hit — **Then** EventBus emit `tradeCompleted` với đầy đủ 8 fields — đúng 1 lần duy nhất per closed trade, không emit duplicate.

3. **Given** Narron nhấn Play — **When** replay bắt đầu — **Then** EventBus emit `replayStateChanged` với `state: 'playing'`.

4. **Given** Narron nhấn Stop hoặc replay hoàn thành hết bars — **When** replay dừng — **Then** EventBus emit `replayStateChanged` với `state: 'stopped'`.

5. **Given** Narron nhấn Reset — **When** session reset — **Then** EventBus emit `replayStateChanged` với `state: 'stopped'` — toàn bộ Phase 1 flows (ResultsPanel, DrawingManager) vẫn hoạt động bình thường như trước khi thêm event.

## Tasks / Subtasks

- [x] Task 1: Tạo TypeScript toolchain setup (AC: #1)
  - [x] Tạo `package.json` với dev dependencies: `typescript`, `esbuild`
  - [x] Tạo `tsconfig.json` với strict config đúng project convention
  - [x] Verify `npx tsc --noEmit` pass sau khi tạo types.ts

- [x] Task 2: Tạo `frontend/types.ts` với đầy đủ EventMap (AC: #1)
  - [x] Định nghĩa Phase 1 events: `replay:barAdvanced`, `replay:tradeHit`, `drawing:lineChanged`, `session:reset`
  - [x] Thêm Phase 2 events: `replayStateChanged` và `tradeCompleted` với đúng payload shapes
  - [x] Định nghĩa shared types: `OHLCVBar`, `Trade`, `Position`, `LineSnapshot`, `IndicatorValues`

- [x] Task 3: Tạo `frontend/EventBus.ts` singleton (AC: #2, #3, #4, #5)
  - [x] Implement generic `EventBus<T extends { [K in keyof T]: unknown }>` class
  - [x] Implement `emit<K extends keyof T>(event: K, payload: T[K]): void`
  - [x] Implement `on<K extends keyof T>(event: K, handler: (payload: T[K]) => void): () => void` (returns unsubscribe function)
  - [x] Implement `off<K extends keyof T>(event: K, handler: (payload: T[K]) => void): void`
  - [x] Export singleton: `export const eventBus = new EventBusImpl<EventMap>()`

- [x] Task 4: Tạo `frontend/ReplayEngine.ts` stub với Phase 2 event emission (AC: #2, #3, #4, #5)
  - [x] Implement `start(lineSnapshot: LineSnapshot, data: OHLCVBar[]): void` → emit `replayStateChanged: { state: 'playing' }`
  - [x] Implement `stop(): void` → emit `replayStateChanged: { state: 'stopped' }`
  - [x] Implement `reset(): void` → emit `replayStateChanged: { state: 'stopped' }`
  - [x] Implement private `handleTradeClose` + `openTrade` — với position tracking để emit `tradeCompleted` đúng 1 lần
  - [x] Track `entryBarIndex` và `entryTimestampMs` khi position open để compute `bars_to_exit`
  - [x] Đảm bảo không emit `tradeCompleted` duplicate (position set null sau khi emit)

- [x] Task 5: Verify TypeScript compilation (AC: #1)
  - [x] Chạy `npx tsc --noEmit` — pass 0 errors (exit 0)
  - [x] EventMap có đủ 6 event keys (4 Phase 1 + 2 Phase 2)

## Dev Notes

### ⚠️ CRITICAL: Không có Phase 1 code nào tồn tại trước story này

Story 1.1 chỉ tạo **backend scaffold** (Python). Story 1.2 là story đầu tiên tạo **frontend TypeScript infrastructure**. Dev phải tạo hoàn toàn mới:

- TypeScript toolchain (`package.json`, `tsconfig.json`)
- `frontend/EventBus.ts` — Phase 1 component, tạo từ đầu
- `frontend/types.ts` — Phase 1 + Phase 2 events, tạo từ đầu
- `frontend/ReplayEngine.ts` — STUB ONLY trong story này (full implementation là Phase 1, nhưng Phase 2 event hooks phải có ngay)

### Scope rõ ràng của story này

**IN SCOPE (phải implement):**
- `types.ts` EventMap đầy đủ
- `EventBus.ts` singleton (có thể emit/on/off)
- `ReplayEngine.ts` stub với: state tracking, event emission cho 2 Phase 2 events

**OUT OF SCOPE (story sau implement):**
- Bar advancement loop (delta-time accumulation — Gap 3 trong architecture)
- Hit detection algorithm (test_replay.py validates this)
- `ChartController.ts`, `DrawingManager.ts`, `ResultsPanel.ts`, `main.ts`
- `frontend/main.ts` và `static/index.html`

### File Locations (theo project-context.md)

```
stock_backtest_project/
├── frontend/
│   ├── EventBus.ts          ← TẠO MỚI trong story này
│   ├── ReplayEngine.ts      ← TẠO MỚI (stub) trong story này
│   └── types.ts             ← TẠO MỚI trong story này
├── tsconfig.json            ← TẠO MỚI trong story này
└── package.json             ← TẠO MỚI trong story này
```

> **Không được tạo file trong thư mục con** — `frontend/` là flat directory, không có `src/`.

### `frontend/types.ts` — Implementation Chính Xác

```typescript
// EventMap — typed contract giữa tất cả emitters và listeners
// Phase 1 events (namespace:camelCase per ADR Gap 13)
// Phase 2 events (flat names per Epic 1 Story 1.2 spec — không namespace)
export interface EventMap {
  // Phase 1 events
  'replay:barAdvanced': { barIndex: number; timestamp: number };
  'replay:tradeHit': { type: 'entry' | 'tp' | 'sl'; price: number; barIndex: number };
  'drawing:lineChanged': { type: 'entry' | 'tp' | 'sl'; price: number };
  'session:reset': Record<string, never>;

  // Phase 2 events — ExportPanel listens to these
  replayStateChanged: { state: 'playing' | 'paused' | 'stopped' };
  tradeCompleted: TradeCompletedPayload;
}

// Phase 2 trade payload — 8 fields required by Epic 1 AC
export interface TradeCompletedPayload {
  bar_index: number;           // bar index khi trade CLOSE (exit bar)
  entry_timestamp_ms: number;  // Unix ms UTC của entry candle (ADR-03)
  direction: 'LONG' | 'SHORT';
  entry_price: number;
  tp_price: number;
  sl_price: number;
  result: 'win' | 'loss';
  bars_to_exit: number;        // exit_bar_index - entry_bar_index
}

// Shared types (used by EventMap payloads and components)
export interface OHLCVBar {
  timestamp: number;  // Unix ms int64 (ADR-03)
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface LineSnapshot {
  entry: number;  // price frozen tại Play time
  tp: number;
  sl: number;
}

export interface IndicatorValues {
  ema20: number | null;
  ema50: number | null;
}

export interface Trade {
  barIndex: number;
  direction: 'LONG' | 'SHORT';
  entryPrice: number;
  tpPrice: number;
  slPrice: number;
  result: 'win' | 'loss';
  pnl: number;
  commission: number;
}
```

> **Naming Note:** Phase 2 events (`replayStateChanged`, `tradeCompleted`) dùng plain camelCase thay vì `namespace:camelCase` của Phase 1. Đây là decision từ epics spec — document để tránh inconsistency drift trong stories sau.

### `frontend/EventBus.ts` — Implementation Chính Xác

```typescript
type Handler<T> = (payload: T) => void;

class EventBusImpl<T extends Record<string, unknown>> {
  private handlers = new Map<keyof T, Set<Handler<unknown>>>();

  emit<K extends keyof T>(event: K, payload: T[K]): void {
    const set = this.handlers.get(event);
    if (!set) return;
    set.forEach((handler) => (handler as Handler<T[K]>)(payload));
  }

  on<K extends keyof T>(event: K, handler: Handler<T[K]>): () => void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, new Set());
    }
    this.handlers.get(event)!.add(handler as Handler<unknown>);
    // Returns unsubscribe function — MUST be called on component unmount
    return () => this.off(event, handler);
  }

  off<K extends keyof T>(event: K, handler: Handler<T[K]>): void {
    this.handlers.get(event)?.delete(handler as Handler<unknown>);
  }
}

import type { EventMap } from './types';

// Singleton — tất cả frontend modules import từ đây
export const eventBus = new EventBusImpl<EventMap>();
```

### `frontend/ReplayEngine.ts` — Stub với Phase 2 Emission

```typescript
import { eventBus } from './EventBus';
import type { OHLCVBar, LineSnapshot, TradeCompletedPayload } from './types';

export class ReplayEngine {
  private data: OHLCVBar[] = [];
  private currentIndex = 0;
  private isRunning = false;

  // Phase 2 trade tracking
  private openPosition: {
    direction: 'LONG' | 'SHORT';
    entryPrice: number;
    tpPrice: number;
    slPrice: number;
    entryBarIndex: number;
    entryTimestampMs: number;
  } | null = null;

  start(lineSnapshot: LineSnapshot, data: OHLCVBar[]): void {
    if (this.isRunning) return;
    this.data = data;
    this.isRunning = true;

    // Phase 2: notify ExportPanel replay started
    eventBus.emit('replayStateChanged', { state: 'playing' });

    // TODO (Phase 1 story): implement delta-time bar advancement loop (Gap 3)
    // For now: stub — bar loop implemented in later story
  }

  stop(): void {
    if (!this.isRunning) return;
    this.isRunning = false;

    // Phase 2: notify ExportPanel replay stopped
    eventBus.emit('replayStateChanged', { state: 'stopped' });
  }

  reset(): void {
    this.isRunning = false;
    this.currentIndex = 0;
    this.openPosition = null;

    // Phase 2: notify ExportPanel (Reset = stopped state)
    // Also triggers trades array reset in ExportPanel (Story 2.4)
    eventBus.emit('replayStateChanged', { state: 'stopped' });

    // Phase 1: notify other components
    eventBus.emit('session:reset', {});
  }

  // Called by bar advancement loop when TP or SL is detected
  // NOT called directly from outside — internal to ReplayEngine
  private handleTradeClose(
    exitBarIndex: number,
    result: 'win' | 'loss'
  ): void {
    if (!this.openPosition) return; // guard: no open position

    const payload: TradeCompletedPayload = {
      bar_index: exitBarIndex,
      entry_timestamp_ms: this.openPosition.entryTimestampMs,
      direction: this.openPosition.direction,
      entry_price: this.openPosition.entryPrice,
      tp_price: this.openPosition.tpPrice,
      sl_price: this.openPosition.slPrice,
      result,
      bars_to_exit: exitBarIndex - this.openPosition.entryBarIndex,
    };

    // Phase 2: notify ExportPanel trade completed
    eventBus.emit('tradeCompleted', payload);

    // Phase 1: notify ResultsPanel (legacy event)
    eventBus.emit('replay:tradeHit', {
      type: result === 'win' ? 'tp' : 'sl',
      price: result === 'win' ? this.openPosition.tpPrice : this.openPosition.slPrice,
      barIndex: exitBarIndex,
    });

    // Clear position — prevents duplicate emit
    this.openPosition = null;
  }

  // Called by bar advancement loop when entry bar reached
  openTrade(
    barIndex: number,
    lineSnapshot: LineSnapshot,
    direction: 'LONG' | 'SHORT'
  ): void {
    if (this.openPosition) return; // guard: already in trade
    const bar = this.data[barIndex];
    this.openPosition = {
      direction,
      entryPrice: lineSnapshot.entry,
      tpPrice: lineSnapshot.tp,
      slPrice: lineSnapshot.sl,
      entryBarIndex: barIndex,
      entryTimestampMs: bar.timestamp,
    };
  }

  // TODO (Phase 1 story): getTradeLog(), getSummary() — implements pull pattern from ADR-14
}
```

### `tsconfig.json` — Config Chính Xác

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": false,
    "noImplicitAny": true,
    "outDir": "./static",
    "rootDir": "./frontend",
    "skipLibCheck": true,
    "sourceMap": true,
    "lib": ["ES2020", "DOM"]
  },
  "include": ["frontend/**/*"],
  "exclude": ["node_modules", "static"]
}
```

> **ADR-16 note:** `strict: false` ban đầu, enable `noImplicitAny` trước tiên — đây là phase đầu tiên.

### `package.json` — Frontend Toolchain

```json
{
  "name": "stock_backtest_project",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "build": "esbuild frontend/main.ts --bundle --outfile=static/app.js --sourcemap",
    "build:prod": "esbuild frontend/main.ts --bundle --outfile=static/app.js --minify",
    "watch": "esbuild frontend/main.ts --bundle --outfile=static/app.js --watch --sourcemap",
    "typecheck": "tsc --noEmit",
    "typecheck:watch": "tsc --noEmit --watch"
  },
  "devDependencies": {
    "typescript": "^6.0.0",
    "esbuild": "^0.28.0",
    "lightweight-charts": "^5.1.0"
  }
}
```

### Critical Architecture Rules (story này phải tuân theo)

| Rule | Source | Áp dụng thế nào |
|------|--------|----------------|
| EventBus singleton — không dùng `document.dispatchEvent` | ADR Gap 7 | Import `eventBus` từ `EventBus.ts` |
| EventMap typed — không emit untyped events | ADR Gap 13 | Mọi emit/on đều qua EventMap type |
| `noImplicitAny: true` | ADR Gap 16 | TypeScript config đã set |
| esbuild transpile KHÔNG type-check | ADR Gap 12 | Dùng `tsc --noEmit` riêng để verify |
| `frontend/` flat — không nest trong `src/` | Architecture project structure | Tất cả files ở `frontend/*.ts` |
| PascalCase filename cho frontend files | project-context.md (override arch naming) | `EventBus.ts`, `ReplayEngine.ts`, `types.ts` |
| Unsubscribe function pattern | EventBus.on() returns `() => void` | Components gọi unsubscribe khi unmount |

### Verify Bước Cuối

Sau khi tạo đủ 5 files, chạy:

```bash
npm install          # install typescript + esbuild
npx tsc --noEmit     # phải pass 0 errors
```

**Expected output:** (no errors, no output — tsc silent trên success)

> **Lưu ý:** `npx esbuild frontend/main.ts ...` sẽ FAIL trong story này vì `frontend/main.ts` chưa tồn tại — đây là expected, esbuild chỉ dùng sau khi Phase 1 stories hoàn tất. CHỈ verify với `tsc --noEmit`.

### Backward-Compatibility với Phase 1

Hai events Phase 2 (`replayStateChanged`, `tradeCompleted`) không ảnh hưởng Phase 1 flows vì:

1. **Additive only**: Chỉ thêm keys mới vào EventMap — không sửa hay remove existing events
2. **EventBus fan-out**: Phase 1 components (`ResultsPanel`, `DrawingManager`) chỉ subscribe events của họ — không nhận Phase 2 events
3. **`session:reset` emission vẫn giữ** trong `ReplayEngine.reset()` — Phase 1 components rely on this

### References

- [epics.md - Story 1.2 Acceptance Criteria](../_bmad-output/planning-artifacts/epics.md#story-12-eventbus--replaystatechanged-và-tradecompleted-events)
- [architecture.md - ADR Gap 7: Custom EventBus Singleton](../_bmad-output/planning-artifacts/architecture.md#gap-7--custom-eventbus-singleton-medium)
- [architecture.md - ADR Gap 13: Shared EventMap Interface](../_bmad-output/planning-artifacts/architecture.md#gap-13--shared-eventmap-interface-high)
- [architecture.md - ADR-14: ReplayEngine Event Design](../_bmad-output/planning-artifacts/architecture.md#adr-14-replayengine-event-design)
- [architecture.md - ADR Gap 16: TypeScript + esbuild](../_bmad-output/planning-artifacts/architecture.md#gap-16--adr-04-typescript--esbuild-medium)
- [project-context.md - Frontend structure](../docs/project-context.md)
- [prd-phase2-supabase.md - FR30, FR31](../_bmad-output/planning-artifacts/prd-phase2-supabase.md)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

Fix TypeScript error: `EventMap` dùng string literal keys (`'replay:barAdvanced'`, v.v.) không compatible với `Record<string, unknown>` constraint. Fix: đổi thành `{ [K in keyof T]: unknown }` — identity constraint, không require index signature.

### Completion Notes List

- ✅ Task 1: `package.json` (typescript ^6, esbuild ^0.28, lightweight-charts ^5.1) + `tsconfig.json` (strict: false, noImplicitAny: true, ES2020 target)
- ✅ Task 2: `frontend/types.ts` — EventMap 6 keys (4 Phase 1 + 2 Phase 2), `TradeCompletedPayload` 8 fields, shared types: OHLCVBar, LineSnapshot, IndicatorValues, Trade
- ✅ Task 3: `frontend/EventBus.ts` — generic `EventBusImpl<T>`, emit/on/off, on() returns unsubscribe fn, singleton `eventBus`
- ✅ Task 4: `frontend/ReplayEngine.ts` stub — start/stop/reset emit `replayStateChanged`, `handleTradeClose` emit `tradeCompleted` + `replay:tradeHit`, position null sau emit (no duplicate), `openTrade()` bảo vệ bằng guard
- ✅ Task 5: `npx tsc --noEmit` exit 0 — 0 TypeScript errors

### File List

- `package.json` (tạo mới — frontend toolchain: typescript, esbuild, lightweight-charts)
- `tsconfig.json` (tạo mới — strict:false, noImplicitAny:true, ES2020, moduleResolution:bundler)
- `frontend/types.ts` (tạo mới — EventMap 6 keys, TradeCompletedPayload, OHLCVBar, LineSnapshot, IndicatorValues, Trade)
- `frontend/EventBus.ts` (tạo mới — EventBusImpl generic class, eventBus singleton)
- `frontend/ReplayEngine.ts` (tạo mới — stub với Phase 2 event emissions, position tracking)

### Review Findings

- [x] [Review][Patch] `openTrade()` không bounds-check `barIndex` — fixed: thêm `if (!bar) return` [`frontend/ReplayEngine.ts`, `openTrade()`]
- [x] [Review][Patch] `reset()` drop open trade không emit `tradeCompleted` — fixed: gọi `handleTradeClose` trước khi clear [`frontend/ReplayEngine.ts`, `reset()`]
- [x] [Review][Patch] `start()` không reset `currentIndex`/`openPosition` — fixed: reset cả hai trong `start()` [`frontend/ReplayEngine.ts`, `start()`]
- [x] [Review][Patch] `bars_to_exit` có thể âm — fixed: `Math.max(0, exitBarIndex - entryBarIndex)` [`frontend/ReplayEngine.ts`, `handleTradeClose()`]
- [x] [Review][Patch] `lightweight-charts` đặt sai trong `devDependencies` — fixed: chuyển sang `dependencies` [`package.json`]
- [x] [Review][Patch] EventBus `emit()` iterate Set đang bị mutate — fixed: `[...set].forEach(...)` [`frontend/EventBus.ts`, `emit()`]
- [x] [Review][Defer] `typescript: "^6.0.0"` chưa release stable [`package.json:14`] — deferred, pre-existing — defer khi TypeScript 6 stable
- [x] [Review][Defer] `strict: false` ẩn nhiều null-related bugs [`tsconfig.json:5`] — deferred, pre-existing — defer theo ADR-16 rollout plan

## Change Log

| Date | Change | Author |
|---|---|---|
| 2026-04-27 | Story 1.2 implemented: TypeScript toolchain (package.json, tsconfig.json), frontend/types.ts (EventMap 6 events), frontend/EventBus.ts (singleton), frontend/ReplayEngine.ts (stub với Phase 2 event hooks). tsc --noEmit exit 0. | claude-sonnet-4-6 |
| 2026-04-27 | Code review: 6 patch findings, 2 deferred, 5 dismissed | claude-sonnet-4-6 |
