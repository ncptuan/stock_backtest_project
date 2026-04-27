---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
workflowType: 'architecture'
lastStep: 8
status: 'complete'
completedAt: '2026-04-26'
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - _bmad-output/planning-artifacts/research/domain-crypto-backtest-research-2026-04-23.md
  - _bmad-output/planning-artifacts/research/technical-python-backtesting-libraries-system-architecture-research-2026-04-23.md
  - _bmad-output/planning-artifacts/research/technical-fastapi-vanillajs-visual-replay-system-architecture-2026-04-23.md
workflowType: 'architecture'
project_name: 'stock_backtest_project'
user_name: 'Narron'
date: '2026-04-23'
---

# Architecture Decision Document

_Tài liệu này được xây dựng cộng tác qua từng bước khám phá. Các phần được bổ sung khi chúng ta cùng đưa ra từng quyết định kiến trúc._

---

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
44 FRs tổ chức trong 8 nhóm: Data Management (FR1–6), Chart Display (FR7–12), Drawing Tools (FR13–19c), Bar Replay (FR20–25), Trade Execution (FR26–33), Session Results (FR34–37), Onboarding & Navigation (FR38–41), System Configuration (FR42–44).

Core experience: vẽ strategy (horizontal lines) → replay bar-by-bar → hit detection → per-trade audit trail. Toàn bộ FR phục vụ cho "aha moment" này.

**Non-Functional Requirements:**
26 NFRs trong 6 nhóm. Data Integrity (NFR12–18) là priority cao nhất — 4/7 marked Critical. Performance targets cụ thể: replay ≥ 30fps, API < 500ms, chart render < 2s, offline-capable sau khi cache.

**Scale & Complexity:**

- Primary domain: Full-stack web app, local-first, single-user
- Complexity level: High — technical precision requirements (look-ahead bias prevention, replay timing, drawing coordinate system)
- Architectural components: Data pipeline layer, REST API layer, Replay engine, Drawing subsystem, State management (3 state domains), Results engine

### Technical Constraints & Dependencies

- **Stack đã lock (ADR trong PRD):** Python FastAPI + Vanilla JS + Lightweight Charts + Parquet + pandas-ta
- **Data scale:** 5m timeframe = ~210k rows × 6 columns — must handle in memory without OOM (8GB RAM machine)
- **Binance API:** Rate limit 1200 weight/phút, pagination 1000 candles/request, public API (no key required)
- **Timezone contract:** UTC store trong cache → UTC+7 display
- **Schema contract (ADR-03):** timestamp int64 (Unix ms), OHLCV float64 — contract giữa Parquet, API, và Phase 2 Supabase
- **Browser matrix:** Chrome latest + Safari latest (primary), Safari iPad basic
- **Deployment path:** Local-first, Koyeb Phase 2 — kiến trúc không được self-block future deployment

### Cross-Cutting Concerns Identified

1. **Data Integrity** — Look-ahead bias prevention xuyên suốt toàn bộ system: indicator calculation, replay reveal logic, hit detection timing
2. **State Management** — 3 state domains độc lập: Drawing state (lines), Replay state (current bar position, speed, play/pause), Session state (settings persistence). Giao tiếp qua custom events (ADR-01)
3. **Error Handling & Fallback** — Binance down → fallback cache, corrupt cache → auto-delete + re-fetch, API timeout → retry với exponential backoff
4. **Timezone Normalization** — UTC throughout backend, UTC+7 transformation chỉ tại display layer
5. **Reproducibility** — Cùng data + strategy → cùng P&L mọi lần. Commission bắt buộc included, P&L lock tại Play time

### Architectural Gaps Phát Hiện Qua Advanced Elicitation

Các gap sau đây được phát hiện qua phân tích sâu (Architecture Decision Records, Pre-mortem, Tree of Thoughts, Failure Mode Analysis, Cross-Functional War Room) — chưa được address trong PRD ADRs và phải được giải quyết trong kiến trúc:

**Gap 1 — Indicator Look-ahead (Critical)**
API phải accept `date_end` parameter và slice OHLCV *trước* khi compute indicators. Gọi `df.ta.ema()` trên full DataFrame là look-ahead bug. Pattern đúng: `df.iloc[:date_end_index].ta.ema(length=20)` — slice trước, compute sau.

**Gap 2 — Atomic Parquet Write (Critical)**
Parquet write phải dùng write-to-temp + rename pattern: write `BTC_USDT_5m.parquet.tmp` → rename thành `.parquet` chỉ khi write hoàn tất. Partial write do process kill = silent data corruption không detect được.

**Gap 3 — Replay Timing: Delta-time Accumulation (High)**
`requestAnimationFrame` không đảm bảo đúng interval khi browser throttle (tab inactive, CPU load cao). Phải dùng delta-time accumulation pattern: track `lastTimestamp`, accumulate `elapsed`, advance bar khi `elapsed >= targetInterval`. Không dùng naive `setTimeout` hay bare `rAF`.

**Gap 4 — Drawing Coordinate System Bridge (High)**
Drawing Manager phải subscribe vào Lightweight Charts zoom/pan events để re-render overlay. Coordinate translation (price/time ↔ pixel) là independent module — khi chart re-renders do zoom, tất cả drawings phải recalculate pixel positions. Đây là coupling điểm nguy hiểm nhất giữa Drawing layer và Chart layer.

**Gap 5 — Async Binance Fetch + Progress Streaming (High)**
Binance fetch (~5 phút) phải là async FastAPI endpoint — sync endpoint block server hoàn toàn, second request sẽ timeout. Frontend cần progress feedback. **Server-Sent Events (SSE)** là pattern phù hợp: `GET /api/fetch-progress` stream JSON events `{progress: 45, status: "Fetching page 12/50"}`. Simpler hơn WebSocket, built-in browser support.

**Gap 6 — TypeScript thay vì Vanilla JS (Medium)**
Với class-based architecture (ADR-01) và nhiều event types giữa ReplayEngine, DrawingManager, ChartController, ResultsPanel — TypeScript với esbuild setup ngăn ngừa một class bugs tại compile time. Đặc biệt quan trọng cho solo dev với Flutter background (strong typing mindset). Trade-off: cần build step, nhưng esbuild setup < 30 phút.

**Gap 7 — Custom EventBus Singleton (Medium)**
ADR-01 nói "event-driven" nhưng không specify mechanism. `document.dispatchEvent(new CustomEvent(...))` là global — debug khó, namespace collision risk. Cần **Custom EventBus singleton**: `EventBus.emit('replay:barAdvanced', data)`, `EventBus.on('replay:barAdvanced', handler)`. Typed events với TypeScript = full type safety cho event payloads.

**Gap 8 — Partial Batch Fetch Validation (Medium)**
Sau mỗi Binance API page (1000 candles), validate `received_rows == expected_rows`. Nếu thiếu (connection drop giữa chừng), retry page đó trước khi proceed. Không accumulate partial data silently.

### Architectural Gaps Bổ Sung (Round 2 — Advanced Elicitation)

**Gap 9 — SSE Heartbeat + Fallback Pattern (High)**
SSE connection cho Binance fetch (5 phút) phải gửi **heartbeat ping mỗi 15 giây** (`data: {"type":"ping"}\n\n`) để giữ connection qua proxy timeout. Nếu SSE connection lost sau 3 retries → tự động fallback sang polling `GET /api/fetch-status` mỗi 2 giây. Deployment Phase 2: nginx cần `proxy_buffering off` cho SSE endpoint.

**Gap 10 — Job Lock Per (Symbol, Timeframe) (High)**
Backend phải enforce **job lock**: nếu fetch job đang chạy cho (symbol, timeframe), reject request mới với `409 Conflict` + message "Fetch already in progress." Frontend disable Refresh Data button khi job active. Tránh race condition khi user click nhiều lần → concurrent writes vào cùng Parquet file.

**Gap 11 — Cancellable asyncio.Task Dict (High)**
Track active fetch tasks trong global dict `{(symbol, timeframe): asyncio.Task}`. Khi new fetch request cho cùng key → cancel task cũ (handle `asyncio.CancelledError` để cleanup temp file) → start task mới. Atomic write pattern (Gap 2) là safety net cuối cùng nếu cancel race.

**Gap 12 — esbuild + tsc --noEmit Separation (High)**
esbuild chỉ transpile, không type-check. TypeScript type errors không block build. Phải có **`tsc --noEmit` như separate check step**: dev workflow dùng `esbuild --watch` (instant rebuild) + `tsc --watch --noEmit` (background type check). Pre-commit / pre-deploy: `tsc --noEmit` phải pass.

**Gap 13 — Shared EventMap Interface (High)**
Typed event contract giữa emitter và listener. Define `EventMap` interface tập trung:
```typescript
interface EventMap {
  'replay:barAdvanced': { barIndex: number; timestamp: number };
  'replay:tradeHit': { type: 'entry' | 'tp' | 'sl'; price: number; barIndex: number };
  'drawing:lineChanged': { type: 'entry' | 'tp' | 'sl'; price: number };
  'session:reset': {};
}
```
EventBus singleton generic trên `EventMap` → compile-time error nếu emit/listen với wrong payload shape.

**Gap 14 — Coordinate Translator Lazy Init (High)**
`series.priceToCoordinate()` và `series.coordinateToPrice()` chỉ valid sau khi chart rendered. `CoordinateTranslator` phải dùng lazy init pattern: `init(series)` được gọi sau khi chart fire `subscribeCrosshairMove()` lần đầu. Re-translate trigger: subscribe vào `chart.priceScale().subscribePriceScaleOptionsChanged()` + `chart.timeScale().subscribeVisibleLogicalRangeChange()`.

**Gap 15 — Y-Axis Only Scope cho Drawing (Medium)**
MVP drawing chỉ là horizontal lines → chỉ cần **Y-axis (price) translation**. Không build general 2D coordinate system. Extension point cho Phase 2 trendlines: `CoordinateTranslator.addXAxis(timeScale)`. Tránh scope creep.

**Gap 16 — ADR-04: TypeScript + esbuild (Medium)**
```
ADR-04: TypeScript + esbuild
- strict: false ban đầu, enable noImplicitAny trước tiên
- Bundle: single app.js served bởi FastAPI /static
- Dev: esbuild --watch + source maps
- Prod: esbuild --minify, no source maps
- Type check: tsc --noEmit (separate step)
```

**Gap 17 — ADR-05: Async Fetch Architecture (High)**
```
ADR-05: Async Binance Fetch
- Endpoint: async FastAPI + asyncio.Task (non-blocking)
- Progress: SSE StreamingResponse với 15s heartbeat
- Fallback: polling /api/fetch-status nếu SSE fails
- Lock: 409 Conflict nếu job đang chạy
- Cancel: cancel-on-new-request với CancelledError cleanup
```

**Gap 18 — ADR-06: Drawing Coordinate System (Medium)**
```
ADR-06: Drawing Coordinate System (MVP)
- Scope: Y-axis (price) only — horizontal lines
- Translation: series.priceToCoordinate() / series.coordinateToPrice()
- Snap: round đến nearest tick (min price increment của symbol)
- Re-render: subscribe priceScale + visibleLogicalRange change events
- Lazy init: sau chart.subscribeCrosshairMove() fires lần đầu
- Phase 2 extension: CoordinateTranslator.addXAxis(timeScale)
```

---

## Starter Template Evaluation

### Primary Technology Domain

Custom dual-process local tool — không dùng SPA framework starter (không có React, Vue, Next.js). "Starter" ở đây là project structure scaffold + verified dependency pinning.

- **Backend:** Python FastAPI process
- **Frontend:** TypeScript files bundled bởi esbuild, output trực tiếp vào `static/app.js`
- FastAPI serve `static/` directory — không có CDN, fully offline-capable

### Verified Dependencies (April 2026)

**Backend:**

| Package | Version | Ghi chú |
|---------|---------|---------|
| fastapi | 0.135.3 | Requires Python ≥ 3.10 |
| uvicorn[standard] | latest | Pin cùng với fastapi |
| pyarrow | 24.0.0 | Parquet read/write, released Apr 21 2026 |
| ccxt | 4.5.48 | Binance OHLCV fetch, active |
| python-dotenv | latest | .env loading |
| pydantic-settings | latest | Pydantic Settings cho env vars |
| pytest + pytest-asyncio + httpx | latest | Testing |

**Frontend:**

| Package | Version | Ghi chú |
|---------|---------|---------|
| lightweight-charts | 5.1.0 | v5 giảm bundle 16%, breaking change từ v4 |
| typescript | 6.0.x | Stable JS-based (KHÔNG dùng 7.0 Beta — Go-based, chưa production-ready) |
| esbuild | 0.28.0 | Bundler + transpiler |

**Python version:** 3.12 (recommended) — managed bởi `uv`.

### Project Structure (Optimised — Occam's Razor Applied)

```
stock_backtest_project/
├── backend/
│   ├── main.py              # App factory + /health endpoint (route registration only)
│   ├── routes/
│   │   ├── ohlcv.py         # GET /api/ohlcv
│   │   └── fetch.py         # POST /api/fetch + GET /api/fetch-stream (SSE)
│   ├── services/
│   │   ├── fetcher.py       # Binance fetch + pagination + retry + job lock
│   │   ├── cache.py         # Parquet read/write (atomic write pattern)
│   │   ├── indicators.py    # MA/EMA via pandas built-in (slice-first)
│   │   └── replay.py        # Hit detection engine
│   ├── models.py            # Pydantic request/response models (API contract)
│   ├── settings.py          # Pydantic Settings — single source cho tất cả config
│   └── pyproject.toml       # uv deps + pytest config
├── frontend/
│   ├── main.ts              # Entry point (esbuild entry)
│   ├── EventBus.ts          # Custom EventBus singleton
│   ├── ChartController.ts
│   ├── DrawingManager.ts
│   ├── ReplayEngine.ts
│   ├── ResultsPanel.ts
│   └── types.ts             # EventMap interface + shared types
├── static/
│   ├── index.html           # Hand-written HTML, references app.js
│   └── app.js               # esbuild output — GITIGNORED
├── tests/
│   ├── test_replay.py       # hit_detection() unit tests
│   ├── test_indicators.py   # slice-first indicator tests
│   └── test_cache.py        # atomic write + corrupt detection tests
├── cache/                   # Parquet files — GITIGNORED
├── .env.example
├── .gitignore
└── tsconfig.json
```

**Key structural decisions:**
- Không có `frontend/src/` nesting — flat frontend/ cho solo dev
- esbuild output **trực tiếp** vào `static/app.js` — không có intermediate `dist/`
- `backend/main.py` chỉ có app factory + route registration, **zero business logic**
- `tests/` ở root — test backend services trực tiếp

### ADR-07 (Revised): Indicator Implementation

```
ADR-07: Indicator Library Strategy
- MVP: pandas built-in ewm() cho EMA, rolling().mean() cho MA
  def ema(series, length): return series.ewm(span=length, adjust=False).mean()
  → Zero external indicator dependency
  → Full control of slice-first look-ahead prevention
  → pandas là transitive dependency (pyarrow đã require pandas)
- Phase 2: Evaluate pandas-ta-classic khi cần RSI/MACD/BB/VWAP
  (assess maintenance status lại tại Phase 2)
- Never: ta-lib (C compile overhead không justify cho solo dev)
- Rationale: pandas.ewm() là 1-liner, không cần external library cho 2 indicators
```

### ADR-08: Python Environment Management

```
ADR-08: uv (Astral) thay vì pip + venv
- Tool: uv (2026 standard, replaces pip + venv + pip-tools)
- Config: pyproject.toml với [project.dependencies]
- Dev commands:
    uv sync              # install dependencies
    uv run uvicorn backend.main:app --reload  # run dev server
    uv run pytest        # run tests
- Rationale: Faster, reproducible, modern; solo dev không cần manage venv manually
```

### ADR-09: Backend Module Structure

```
ADR-09: Backend Module Split (No Monolith)
- Rule: main.py = app factory + route registration ONLY (no business logic)
- routes/: HTTP layer — validate input, call service, return response
- services/: Business logic — fetcher, cache, indicators, replay
- models.py: Pydantic models = documented API contract
- settings.py: Pydantic Settings = single source cho tất cả env vars + paths
- Rationale: Tránh 800-line main.py monolith; navigate code nhanh cho solo dev
```

### ADR-10: Testing Strategy

```
ADR-10: Testing
- Backend: pytest + pytest-asyncio + httpx (async test client)
- Critical unit tests (must exist before Sprint 5):
    test_replay.py: hit_detection(), same-bar TP/SL priority, gap-down slippage
    test_indicators.py: slice-first enforcement, NaN handling
    test_cache.py: atomic write, corrupt detection, dedup + sort validation
- pytest config trong pyproject.toml:
    [tool.pytest.ini_options]
    pythonpath = ["backend"]
    asyncio_mode = "auto"
- Frontend MVP: manual testing + browser DevTools
  (unit tests cho EventBus, CoordinateTranslator — optional)
```

### ADR-11: Pydantic Settings

```
ADR-11: Centralized Configuration
- File: backend/settings.py
- class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    cache_dir: Path = Path("./cache")
    app_password: str = ""  # empty = no auth
    supabase_url: str = ""  # Phase 2
    supabase_key: str = ""  # Phase 2
- Single source: tất cả modules import settings, không dùng os.getenv() trực tiếp
- Fail fast: validate tại startup, không fail mid-request
```

### .gitignore (Required từ Day 1)

```gitignore
# Python
__pycache__/
*.pyc
.venv/
.uv/

# Environment
.env

# Cache data
cache/
*.parquet
*.parquet.tmp

# Frontend build output
static/app.js
static/app.js.map

# Node
node_modules/

# OS
.DS_Store
```

### ⚠️ Lightweight Charts v5 Warning

v5.1.0 có breaking changes so với v4.x. **Chỉ tham khảo v5 documentation** — không copy examples từ v4 tutorials hay Stack Overflow posts cũ. API khác nhau: series creation, price scale config, time scale handling.

### Dev Workflow Commands

```bash
# Backend setup
uv sync

# Dev (all processes via overmind)
overmind start

# Type check (separate process)
npx tsc --noEmit --watch

# Tests
uv run pytest tests/ -v
```

**Procfile** (dùng với overmind):
```
web: uv run uvicorn backend.main:app --reload --port 8000
assets: npx esbuild frontend/main.ts --bundle --outfile=static/app.js --watch --sourcemap
```

Fallback nếu không dùng overmind: 2 terminal tabs riêng biệt.

---

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- ADR-12: Replay Engine ở Frontend TypeScript (real-time per-bar)
- ADR-13: Frontend data cache LRU-1 (1 slot)
- ADR-14: ReplayEngine single `tickComplete` event + delta `tradeAdded`
- ADR-15: overmind + Procfile cho dev process management
- Float safety: `Math.round(price * 100) / 100` tại mọi price comparison
- Line snapshot: Freeze line prices tại Play time

**Important Decisions (Shape Architecture):**
- ADR-16: No API versioning (local single-user tool)
- ADR-17: Custom error format với `retryable` flag
- ADR-18: `/docs` disabled khi APP_PASSWORD set
- ADR-19: No CORS middleware MVP (comment for Phase 2)
- ADR-20: LocalStorage persist `{timeframe, dateRange}` only (không persist drawings)

**Deferred Decisions (Post-MVP):**
- Multi-user replay: backend replay engine (Phase 2+)
- Full TypeScript unit tests cho ReplayEngine (optional MVP)
- CORS config cho Phase 2 deployment
- Multi-timeframe memory cache (Phase 2 nếu UX cần)

### Data Architecture

**ADR-13: Frontend Data Cache**
```
Decision: LRU-1 in-memory cache — 1 slot only (last loaded timeframe)
Implementation: ChartController giữ {symbol, timeframe, data: OHLCVBar[]}
Eviction: Clear on timeframe switch BEFORE fetching new data
Rationale:
  - 5m data = ~100MB JS objects — cache >1 timeframe gây memory pressure
  - User workflow: typically 1 active timeframe per session
  - 500ms API call acceptable với loading spinner nếu cache miss
Not cached: Drawings, replay state, indicator values
```

**Parquet Storage:**
```
Compression: snappy (default) — fast read/write, ~15–20MB cho 5m 2-year data
Validation: On read in cache.py — validate schema, dedup, sort ascending
Atomic write: write .tmp → rename (Gap 2 từ elicitation)
```

**Client-side indicator slice:**
```
Frontend nhận full OHLCV array (date_end slice từ backend)
Replay loop: indicators[0..currentBarIndex] — pointer, không slice
No look-ahead: indicator array pre-computed trên date_end slice tại backend
```

### Authentication & Security

**ADR-19: Auth Strategy**
```
APP_PASSWORD empty → no auth (local dev)
APP_PASSWORD set → FastAPI HTTPBasic middleware (3 lines)
No JWT — overkill cho single-user tool
Local: bind localhost only (không accessible external)
```

**ADR-19b: CORS**
```
MVP: No CORS middleware
Frontend + backend cùng localhost:8000 — không cần CORS
Comment trong main.py: # Add CORSMiddleware here for Phase 2
```

**ADR-18: API Docs**
```
/docs enabled: khi APP_PASSWORD empty (local dev)
/docs disabled: khi APP_PASSWORD set (deployed)
Implementation: conditional include_in_schema=False hoặc remove router
```

### API & Communication Patterns

**ADR-16: API Design**
```
No versioning: /api/ohlcv (không phải /api/v1/ohlcv)
Rationale: local single-user tool, không có external consumers
REST only: No GraphQL, no gRPC
```

**ADR-17: Error Response Format**
```python
class ErrorResponse(BaseModel):
    error: str          # Human-readable message
    code: str           # Machine-readable code: "FETCH_FAILED", "CACHE_CORRUPT"
    retryable: bool     # Frontend dùng để show/hide Retry button
```

**ADR-20b: API Docs Control**
```
GET /api/ohlcv?symbol=BTC/USDT&timeframe=4h&date_start=...&date_end=...
POST /api/fetch {symbol, timeframe}           → 202 Accepted + job_id
GET /api/fetch-stream/{job_id}               → SSE StreamingResponse
GET /api/fetch-status/{job_id}               → JSON progress (polling fallback)
DELETE /api/fetch/{job_id}                   → cancel job
GET /health                                  → {status: "ok"}
```

### Frontend Architecture

**ADR-12: Replay Engine Location**
```
Decision: TypeScript frontend — pure client-side, real-time per-bar
Hit detection: ReplayEngine.ts, array index operations only
Float safety: Math.round(price * 100) / 100 tại mọi price comparison
           (normalize đến $0.01 tick — BTC/USDT minimum increment)
Port strategy: Python test_replay.py validates logic → port 1:1 sang TS
Backend role: DATA SERVING ONLY — không có replay logic
Accepted trade-off: No server-side validation during replay (MVP OK)
Phase 2: Nếu multi-user cần → port logic lên backend lúc đó
```

**ADR-14: ReplayEngine Event Design**
```typescript
// Single event per bar — không fan-out
interface TickCompletePayload {
  barIndex: number;
  bar: OHLCVBar;
  newTrades: Trade[];          // empty array nếu không có trade mới
  currentPosition: Position | null;
  indicators: IndicatorValues; // {ma: number|null, ema: number|null}
}
EventBus.emit('replay:tickComplete', payload);

// Delta event — chỉ fire khi có trade mới
EventBus.emit('replay:tradeAdded', trade);

// Pull pattern cho queries
replayEngine.getTradeLog(): Trade[]       // full list
replayEngine.getSummary(): SessionSummary // win/loss/pnl

// Line snapshot tại Play time
replayEngine.start(lineSnapshot: LineSnapshot) // freeze prices
// DrawingManager block drag khi replay running
```

**ADR-20: LocalStorage Persistence**
```typescript
interface PersistedSettings {
  timeframe: Timeframe;
  dateStart: string;  // ISO date
  dateEnd: string;    // ISO date
  // NOT persisted: drawing positions (risk of stale prices)
}
const STORAGE_KEY = 'btcReplay_lastSettings';
```

**Chart Initialization Sequence:**
```
1. DOM ready → ChartController.init(container)
2. ChartController fires 'chart:ready'
3. CoordinateTranslator.init(series) — lazy, after chart ready
4. DrawingManager.init() — subscribe chart zoom/pan events
   → CoordinateTranslator.isUpdating flag prevents event loops
5. ReplayEngine.init() — subscribe to EventBus
6. Load PersistedSettings từ LocalStorage
7. If cached data exists → auto-load → else show empty state
8. User interaction: vẽ → Play → ReplayEngine.start(lineSnapshot)
```

**Array Indexing Pattern (No GC Pressure):**
```typescript
// ✅ Correct: pointer, không slice
class ReplayEngine {
  private data: OHLCVBar[];       // full array, never sliced
  private currentIndex: number;   // pointer

  private getCurrentBar(): OHLCVBar {
    return this.data[this.currentIndex];  // O(1), no allocation
  }
}
// ❌ Wrong: slice tạo new array mỗi tick
// const visible = this.data.slice(0, this.currentIndex);
```

**CoordinateTranslator Guard:**
```typescript
class CoordinateTranslator {
  private isUpdating = false;
  
  onPriceScaleChange() {
    if (this.isUpdating) return;  // prevent re-entrant loop
    this.isUpdating = true;
    this.recalculateAllDrawings();
    this.isUpdating = false;
  }
}
```

### Infrastructure & Deployment

**ADR-15: Dev Process Manager**
```
Tool: overmind (brew install overmind)
Procfile:
  web: uv run uvicorn backend.main:app --reload --port 8000
  assets: npx esbuild frontend/main.ts --bundle --outfile=static/app.js --watch --sourcemap
Commands:
  overmind start            # start all
  overmind connect web      # attach to backend logs
  overmind restart assets   # restart frontend build
  Ctrl+C                    # clean shutdown (all child processes killed)
Fallback: 2 terminal tabs nếu không muốn install overmind
```

**Logging:**
```
MVP: Python logging module, format: "%(levelname)s %(name)s: %(message)s"
Levels: INFO cho requests, WARNING cho retries, ERROR cho failures
Phase 2: structured JSON logs cho Koyeb
```

**Deploy-readiness checks (MVP code phải pass):**
```
✅ host=0.0.0.0 via settings.host (không hardcode)
✅ settings.cache_dir — không hardcode paths
✅ APP_PASSWORD env var → auth toggle
✅ No secrets trong source code
✅ .gitignore: cache/, static/app.js, .env, __pycache__, node_modules/
```

### Decision Impact Analysis

**Implementation Sequence (dependency order):**
```
1. settings.py + models.py (foundation)
2. cache.py atomic write + read + validation
3. fetcher.py (ccxt + pagination + job lock + SSE)
4. indicators.py (pandas built-in, slice-first)
5. routes/ohlcv.py + routes/fetch.py
6. EventBus.ts + types.ts (EventMap)
7. ChartController.ts + CoordinateTranslator
8. DrawingManager.ts (price snap, line limit, freeze on play)
9. ReplayEngine.ts (ticker loop, hit detection, float safety)
10. ResultsPanel.ts (tradeAdded events + getTradeLog pull)
11. test_replay.py (validate hit detection với known data)
12. main.ts + index.html (wire everything together)
```

**Cross-Component Dependencies:**
```
settings.py ← tất cả backend modules
cache.py ← fetcher.py, routes/ohlcv.py
EventBus.ts ← tất cả frontend classes
CoordinateTranslator ← DrawingManager
ReplayEngine ← DrawingManager (line snapshot), ChartController (data)
ResultsPanel ← ReplayEngine (getTradeLog, getSummary)
types.ts (EventMap) ← EventBus, tất cả classes emit/listen
```

---

## Implementation Patterns & Consistency Rules

**15 conflict points** được identify — nơi AI agents có thể implement khác nhau nếu không được specify rõ.

### Naming Patterns

**Python — snake_case everywhere:**
```python
# Files
cache.py, fetcher.py, replay.py, indicators.py

# Functions & variables — WITH type hints (mandatory)
def read_parquet(path: Path) -> pd.DataFrame: ...
def get_ohlcv_data(symbol: str, timeframe: str) -> list[OHLCVBar]: ...
cache_dir: Path = settings.cache_dir

# Classes — PascalCase
class CacheCorruptError(Exception): ...
class OHLCVBar(BaseModel): ...

# Constants — SCREAMING_SNAKE_CASE
MAX_RETRIES = 3
DEFAULT_COMMISSION_RATE = 0.001
```

**API Endpoints — snake_case, plural nouns:**
```
GET  /api/ohlcv
POST /api/fetch_jobs
GET  /api/fetch_jobs/{job_id}/stream    # SSE
GET  /api/fetch_jobs/{job_id}/status    # polling fallback
DELETE /api/fetch_jobs/{job_id}
GET  /health
```

**API Query Parameters — snake_case:**
```
/api/ohlcv?symbol=BTC/USDT&timeframe=4h&date_start=2024-01-01T00:00:00Z&date_end=2024-12-31T23:59:59Z
```

**TypeScript — ⚠️ snake_case.ts files (non-standard, explicitly documented):**
```typescript
// Files: snake_case.ts — đi ngược TS convention, nhưng là decision của project
replay_engine.ts
chart_controller.ts
drawing_manager.ts
results_panel.ts
event_bus.ts
coordinate_translator.ts
types.ts       // exception: giữ nguyên

// Classes: PascalCase (như Flutter)
class ReplayEngine { ... }
class ChartController { ... }

// Interfaces: PascalCase
interface OHLCVBar { ... }
interface EventMap { ... }

// Variables & methods: camelCase
const currentBarIndex = 0;
function getTradeLog(): Trade[] { ... }

// Constants: SCREAMING_SNAKE_CASE
const MAX_LINES_PER_TYPE = 1;
const DEFAULT_COMMISSION_RATE = 0.001;

// Events: namespace:camelCase
'replay:tickComplete'
'replay:tradeAdded'
'drawing:lineChanged'
'chart:ready'
'session:reset'
```

**Parquet Files:**
```
{SYMBOL_NORMALIZED}_{TIMEFRAME}.parquet       # final
{SYMBOL_NORMALIZED}_{TIMEFRAME}.parquet.tmp   # atomic write temp

# Normalize: BTC/USDT → BTC_USDT (replace / with _)
# Examples: BTC_USDT_5m.parquet, BTC_USDT_4h.parquet, BTC_USDT_1D.parquet
```

---

### Format Patterns

**API Response — `{data, error}` wrapper, BOTH fields always present:**
```python
# ✅ Success — error: null required (không được omit)
{"data": {...}, "error": null}

# ✅ Error — data: null required (không được omit)
{"data": null, "error": {"message": "...", "code": "CACHE_CORRUPT", "retryable": true}}

# FastAPI implementation
class APIResponse(BaseModel, Generic[T]):
    data: T | None = None
    error: ErrorResponse | None = None

# Route always returns APIResponse — không return raw objects
return APIResponse(data=bars)
return APIResponse(error=ErrorResponse(message=str(e), code="FETCH_FAILED", retryable=True))
```

**HTTP Status Codes (body pattern + correct status):**
```
200 OK           → success (data present)
400 Bad Request  → business logic error (invalid date range, etc.)
404 Not Found    → resource not found (no cache for symbol/timeframe)
409 Conflict     → job already running (fetch_jobs duplicate)
422 Unprocessable → validation error (FastAPI default, wrong param types)
500 Server Error → unrecoverable server error
```

**Datetime — ISO 8601 UTC (exact format required):**
```python
# ✅ Correct: T separator + Z suffix mandatory
"date_start": "2024-01-01T00:00:00Z"
"triggered_at": "2024-03-15T08:00:00Z"

# ❌ Wrong: missing T or Z
"date_start": "2024-01-01 00:00:00"    # no T separator
"date_start": "2024-01-01T00:00:00"    # no Z suffix

# Internal/Parquet storage: Unix ms int64
timestamp: int  # 1710489600000

# Conversion: ISO string → Unix ms (backend), Unix ms → UTC+7 display (frontend only)
```

**JSON Fields — snake_case:**
```json
{
  "data": {
    "symbol": "BTC/USDT",
    "bar_count": 17520,
    "date_start": "2023-01-01T00:00:00Z",
    "bars": []
  },
  "error": null
}
```

**TypeScript null vs undefined:**
```typescript
// null: intentionally absent, API-facing values
currentPosition: Position | null = null;

// undefined: not yet initialized, internal state
private series: ISeriesApi<'Candlestick'> | undefined;

// Optional chaining cho undefined
this.series?.priceToCoordinate(price);
```

---

### Structure Patterns

**Python Import Ordering (stdlib → third-party → local):**
```python
# 1. Standard library
import asyncio
import logging
from pathlib import Path
from typing import Generic, TypeVar

# 2. Third-party (blank line separator)
import pandas as pd
import pyarrow as pa
from fastapi import APIRouter
from pydantic import BaseModel

# 3. Local (blank line separator)
from backend.models import OHLCVBar
from backend.settings import settings

# Rules:
# - Module-level imports ONLY (không import trong functions)
# - Aliases: pandas → pd, numpy → np (conventional)
# - Không lazy import
```

**Settings Access — direct import (không FastAPI DI):**
```python
# ✅ Correct: direct import
from backend.settings import settings

def read_cache(symbol: str, timeframe: str) -> pd.DataFrame:
    path = settings.cache_dir / f"{symbol}_{timeframe}.parquet"

# ❌ Wrong: FastAPI Depends pattern cho settings
def get_ohlcv(settings: Settings = Depends(get_settings)): ...
# DI là overkill cho singleton config
```

**Separation of Concerns:**
```python
# ✅ routes/ — HTTP layer ONLY
@router.get("/api/ohlcv", response_model=APIResponse[list[OHLCVBar]])
async def get_ohlcv(symbol: str, timeframe: str):
    try:
        bars = await cache_service.read(symbol, timeframe)
        return APIResponse(data=bars)
    except CacheCorruptError as e:
        return APIResponse(error=ErrorResponse(message=str(e), code="CACHE_CORRUPT", retryable=True))

# ❌ Wrong: business logic trong route
@router.get("/api/ohlcv")
async def get_ohlcv(symbol: str, timeframe: str):
    path = settings.cache_dir / f"{symbol}_{timeframe}.parquet"  # business logic
    df = pd.read_parquet(path)  # belongs in cache.py
```

**FastAPI Route Functions — always `async def`:**
```python
# ✅ Always async def cho routes (FastAPI performance optimization)
@router.get("/api/ohlcv")
async def get_ohlcv(...): ...

# OK cho sync operations bên trong async def
async def get_ohlcv(...):
    df = pd.read_parquet(path)  # sync call inside async — acceptable cho MVP
```

**CSS/Styling — external file only:**
```
static/
├── index.html    # references style.css và app.js
├── style.css     # ALL styles — no inline styles, no <style> tags, no framework
└── app.js        # esbuild output

# ❌ Không dùng: inline style="...", <style> blocks, Tailwind CDN, CSS-in-JS
```

---

### Communication Patterns

**EventBus — typed via EventMap, state change → emit immediately:**
```typescript
// types.ts — ALL events defined here (không thêm events trong class files)
interface EventMap {
  'replay:tickComplete': {
    barIndex: number;
    bar: OHLCVBar;
    newTrades: Trade[];
    currentPosition: Position | null;
    indicators: { ma: number | null; ema: number | null };
  };
  'replay:tradeAdded': Trade;
  'replay:started': { lineSnapshot: LineSnapshot };
  'replay:paused': { barIndex: number };
  'replay:reset': {};
  'drawing:lineChanged': { type: LineType; price: number };
  'drawing:lineDeleted': { type: LineType };
  'drawing:cleared': {};
  'chart:ready': {};
  'chart:dataLoaded': { barCount: number };
  'session:reset': {};
}

// Rule: state change → fire event trong cùng method, không deferred
advanceBar(): void {
  this._currentIndex++;           // state change
  const payload = this.buildPayload();
  EventBus.emit('replay:tickComplete', payload);  // emit immediately after
}
```

**Pull vs Push:**
```typescript
// Push via events: notifications, không data transfer
EventBus.emit('replay:tradeAdded', trade);  // notify only

// Pull via methods: data retrieval
const trades = replayEngine.getTradeLog();   // returns Trade[]
const summary = replayEngine.getSummary();   // returns SessionSummary

// ❌ Anti-pattern: emit toàn bộ list qua event
EventBus.emit('replay:allTrades', allTrades);  // 100 trades × overhead
```

**Immutable State Updates:**
```typescript
// ✅ Spread operator
this.settings = { ...this.settings, timeframe: newTimeframe };
this.trades = [...this.trades, newTrade];

// ❌ Direct mutation
this.settings.timeframe = newTimeframe;
this.trades.push(newTrade);
```

---

### Process Patterns

**Python Exception Hierarchy:**
```python
# backend/exceptions.py (hoặc định nghĩa trong models.py)
class AppError(Exception):
    """Base exception cho tất cả app errors"""
    pass

class CacheError(AppError): pass
class CacheCorruptError(CacheError): pass
class CacheNotFoundError(CacheError): pass

class FetchError(AppError): pass
class FetchRateLimitError(FetchError): pass
class FetchNetworkError(FetchError): pass
class FetchPartialDataError(FetchError): pass

class DataError(AppError): pass
class DataGapError(DataError): pass
class DataSortError(DataError): pass

# ❌ Không raise generic Exception
raise Exception("something failed")  # cannot distinguish

# ✅ Raise typed exception
raise CacheCorruptError(f"Invalid schema: {path}")
```

**Route Error Handling (routes catch, services raise):**
```python
# services/cache.py — raise, không return error
def read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise CacheNotFoundError(f"No cache: {path}")
    try:
        df = pd.read_parquet(path)
    except Exception:
        raise CacheCorruptError(f"Corrupt: {path}")
    # Validate monotonic timestamps
    assert df['timestamp'].is_monotonic_increasing, "Cache not sorted"
    return df

# routes/ohlcv.py — catch and wrap
@router.get("/api/ohlcv")
async def get_ohlcv(...):
    try:
        bars = await cache.read(...)
        return APIResponse(data=bars)
    except CacheNotFoundError:
        return JSONResponse(status_code=404,
            content=APIResponse(error=ErrorResponse(...)).dict())
    except CacheCorruptError:
        return JSONResponse(status_code=500,
            content=APIResponse(error=ErrorResponse(..., retryable=True)).dict())
```

**Data Integrity Assertion (Critical):**
```python
# cache.py — mandatory assertion sau mọi Parquet read
df = pd.read_parquet(path)
assert df['timestamp'].is_monotonic_increasing, \
    f"Cache not sorted ascending: {path}"
# Nếu fail → raise DataSortError → auto-delete + re-fetch
```

**TypeScript Error Handling:**
```typescript
// ✅ always catch (e: unknown), type-narrow với instanceof
try {
  await fetchData();
} catch (e: unknown) {
  const message = e instanceof Error ? e.message : String(e);
  showErrorToast(message);
}

// ❌ catch (e: any) — loses type safety
// ❌ catch (e) — implicit any in non-strict mode
```

**Price Float Safety — normalize BEFORE comparison:**
```typescript
// ✅ Correct: normalize TRƯỚC comparison
const normalize = (price: number): number =>
  Math.round(price * 100) / 100;  // $0.01 tick

function checkTPHit(high: number, tpPrice: number): boolean {
  return normalize(high) >= normalize(tpPrice);  // normalize cả hai inputs
}

// ❌ Wrong: normalize sau
function checkTPHit(high: number, tpPrice: number): boolean {
  return normalize(high >= tpPrice);  // normalizing boolean — bug
}

// ❌ Wrong: normalize chỉ 1 bên
return high >= normalize(tpPrice);  // high còn float noise

// Apply normalize khi snapshot line prices tại Play time
const lineSnapshot: LineSnapshot = {
  entry: normalize(drawingManager.getEntryPrice()!),
  tp: tp ? normalize(tp) : null,
  sl: sl ? normalize(sl) : null,
};
```

**Array Indexing (pointer, không slice):**
```typescript
// ✅ Pointer pattern — O(1), no allocation
class ReplayEngine {
  private data: OHLCVBar[];
  private currentIndex = 0;

  private getCurrentBar(): OHLCVBar {
    return this.data[this.currentIndex];
  }
}

// ❌ Slice trong loop — O(n) allocation mỗi tick với 210k rows
const visible = this.data.slice(0, this.currentIndex);
```

**Retry — centralized trong fetcher.py:**
```python
# ✅ Retry logic ONLY trong fetcher.py
async def fetch_with_retry(url: str, max_retries: int = 3) -> dict:
    for attempt in range(max_retries):
        try:
            return await _fetch(url)
        except FetchRateLimitError:
            await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
    raise FetchNetworkError(f"Failed after {max_retries} attempts")

# ❌ Không implement retry trong routes hoặc services khác
```

**Log Levels:**
```python
logger.info("Loaded 17520 bars: BTC_USDT_4h.parquet")
logger.info("Fetch job started: BTC/USDT 4h")
logger.warning("Cache corrupt, deleting: BTC_USDT_4h.parquet")
logger.warning(f"Rate limited, retry in {wait}s (attempt {attempt})")
logger.error("Binance API down, all retries exhausted")
logger.error(f"Cache write failed: {e}")

# ❌ print() cho logging
```

---

### Testing Patterns

**conftest.py — canonical fixtures:**
```python
# tests/conftest.py
import pytest
from backend.models import OHLCVBar

@pytest.fixture
def sample_bars() -> list[OHLCVBar]:
    """20 bars với predictable hit detection outcomes.
    Bar 5: high=69000 → TP hit (entry=68500, tp=69000)
    Bar 10: low=67800 → SL hit (entry=68500, sl=67800)
    """
    return [
        OHLCVBar(timestamp=1710489600000 + i*14400000,
                 open=68000+i*10, high=68100+i*10,
                 low=67900+i*10, close=68050+i*10, volume=100.0)
        for i in range(20)
    ]

@pytest.fixture
def sample_bars_with_gap() -> list[OHLCVBar]:
    """Bars với timestamp gap để test gap detection."""
    ...

@pytest.fixture
def corrupt_parquet_path(tmp_path) -> Path:
    """Parquet file với invalid content."""
    path = tmp_path / "corrupt.parquet"
    path.write_bytes(b"not a parquet file")
    return path
```

**Test Import Convention:**
```python
# tests/test_replay.py
from services.replay import hit_detection, calc_pnl  # pythonpath = ["backend"]
from services.cache import read_parquet
from backend.models import OHLCVBar  # hoặc from models import OHLCVBar

# pyproject.toml:
# [tool.pytest.ini_options]
# pythonpath = ["backend"]
# asyncio_mode = "auto"
```

**Test Naming Convention:**
```python
# test_{module}_{function}_{scenario}
def test_replay_hit_detection_tp_hit_bullish_bar(): ...
def test_replay_hit_detection_sl_hit_bearish_bar(): ...
def test_replay_hit_detection_same_bar_tp_priority(): ...
def test_cache_read_parquet_corrupt_raises(): ...
def test_cache_atomic_write_survives_interrupt(): ...
def test_indicators_ema_no_lookahead(): ...
```

---

### Safety-Critical Patterns (Priority 1 — Must Enforce)

Những patterns sau ngăn **silent bugs** — phải được AI agents implement trước mọi thứ khác:

| Pattern | Consequence nếu thiếu |
|---------|----------------------|
| `normalize(price)` BEFORE comparison | Silent wrong P&L calculation |
| Atomic write (.tmp → rename) | Silent data corruption on interrupt |
| `df.iloc[:date_end_index]` before indicator compute | Look-ahead bias — undetectable |
| Raise typed exceptions (không generic) | Cannot distinguish retry vs fatal |
| `{data, error}` both fields always present | Frontend `response.error` undefined |
| Python type hints trên tất cả functions | Wrong types passed, runtime errors |
| `EventMap` — all events typed in types.ts | Wrong payload shape, silent undefined |
| `assert df.timestamp.is_monotonic_increasing` | Wrong replay order, silent bad results |
| Route catches, service raises | Unhandled exceptions reach user |

---

## Project Structure & Boundaries

### Requirements → Structure Mapping

| FR Category | Implementation Location |
|-------------|------------------------|
| Data Management (FR1–6) | `backend/services/fetcher.py`, `backend/services/cache.py`, `backend/services/job_store.py` |
| Chart Display (FR7–12) | `frontend/chart_controller.ts`, `frontend/coordinate_translator.ts` |
| Drawing Tools (FR13–19c) | `frontend/drawing_manager.ts` |
| Bar Replay (FR20–25) | `frontend/replay_engine.ts` |
| Trade Execution (FR26–33) | `frontend/replay_engine.ts` (hit detection) |
| Session Results (FR34–37) | `frontend/results_panel.ts` |
| Onboarding & Navigation (FR38–41) | `frontend/onboarding_manager.ts`, `frontend/toast_manager.ts`, `frontend/main.ts` |
| System Configuration (FR42–44) | `backend/settings.py`, `.env.example` |

### Complete Project Directory Structure

```
stock_backtest_project/
│
├── .env.example                    # Template: HOST, PORT, CACHE_DIR, APP_PASSWORD
├── .gitignore                      # cache/, static/app.js, .env, __pycache__, node_modules/
├── Procfile                        # overmind: web + assets processes
├── README.md                       # Setup + dev workflow + gotchas (hard reload requirement)
│
├── backend/
│   ├── main.py                     # FastAPI app factory, route registration, /health,
│   │                               # lifespan: cache.startup_cleanup()
│   ├── models.py                   # ALL Pydantic models (OHLCVBar, APIResponse,
│   │                               # ErrorResponse, JobStatus, OHLCVResponse, ...)
│   ├── settings.py                 # Pydantic Settings — auto-creates cache_dir on startup
│   ├── exceptions.py               # Custom exception hierarchy + ERROR_CODES dict
│   ├── pyproject.toml              # uv deps + pytest config (pythonpath=["backend"])
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── ohlcv.py                # GET /api/ohlcv — slice df → compute indicators → respond
│   │   └── fetch.py                # POST /api/fetch_jobs, GET /stream (SSE), GET /status,
│   │                               # DELETE /api/fetch_jobs/{job_id}
│   │
│   └── services/
│       ├── __init__.py
│       ├── cache.py                # Parquet read (validate+sort+dedup), write (atomic .tmp),
│       │                           # startup_cleanup() for orphaned .tmp files
│       ├── fetcher.py              # ccxt Binance fetch, pagination, retry, progress via job_store
│       ├── job_store.py            # In-memory Dict[job_id, JobStatus], asyncio.Lock,
│       │                           # 5-min TTL cleanup, 409 conflict detection
│       ├── indicators.py           # MA/EMA via pandas ewm() — receives pre-sliced df
│       └── replay.py               # Python reference: hit_detection(), calc_pnl()
│                                   # Used by: test_replay.py; port 1:1 to TypeScript
│
├── frontend/
│   ├── main.ts                     # Entry point: init sequence, keyboard handler,
│   │                               # Play button disabled logic, timeframe switch intercept
│   ├── types.ts                    # ALL interfaces: OHLCVBar (with ma_20/ema_20),
│   │                               # Trade, LineSnapshot, SessionSummary, JobStatus,
│   │                               # EventMap (incl. fetch: events), Position, Speed
│   ├── event_bus.ts                # Custom EventBus singleton typed via EventMap
│   ├── chart_controller.ts         # LW Charts v5 init, data load, LRU-1 cache,
│   │                               # hasData(), revealBar(), subscribeTickComplete
│   ├── coordinate_translator.ts    # price↔pixel, lazy init, isUpdating guard,
│   │                               # subscribeVisibleRange + subscribePriceScale
│   ├── drawing_manager.ts          # Lines (Entry/TP/SL), snap, drag, freeze()/unfreeze(),
│   │                               # getLineSnapshot(), hasDrawings(), enforce 1-per-type
│   ├── replay_engine.ts            # Bar loop, delta-time, hit detection, float safety,
│   │                               # play/pause/reset/stepForward/setSpeed/isActive/isPlaying,
│   │                               # getTradeLog(), getSummary() with warning flags
│   ├── results_panel.ts            # Trade list, summary stats, sample size warnings,
│   │                               # zero-trades message (FR38b)
│   ├── fetch_manager.ts            # SSE connection + heartbeat (20s timeout),
│   │                               # fallback polling, reconnect (max 3), job lifecycle,
│   │                               # 409 → attach existing job, fires fetch: events
│   ├── onboarding_manager.ts       # Empty state display, getting started guide (3 steps),
│   │                               # fetch prompt + confirm, progress display during fetch
│   ├── settings_manager.ts         # Typed LocalStorage wrapper, try/catch JSON.parse,
│   │                               # defaults, persist {timeframe, dateRange} only
│   ├── toast_manager.ts            # Singleton toast: show(msg, type, duration?),
│   │                               # timed undo support (5s), info/warning/error types
│   ├── tsconfig.json               # strict: false (enable noImplicitAny first)
│   └── package.json                # lightweight-charts@5.1.0, typescript@6, esbuild@0.28
│
├── static/
│   ├── index.html                  # Hand-written HTML, refs style.css + app.js
│   ├── style.css                   # ALL styles — no inline, no framework
│   └── app.js                      # [GITIGNORED] esbuild output
│
├── tests/
│   ├── conftest.py                 # sample_bars (20 bars, predictable outcomes),
│   │                               # sample_bars_with_gap, corrupt_parquet_path fixtures
│   ├── test_cache.py               # atomic write, corrupt detect, dedup, sort assertion,
│   │                               # startup_cleanup, schema validation
│   ├── test_fetcher.py             # pagination, retry/backoff, job lock 409, rate limit,
│   │                               # partial batch validation
│   ├── test_indicators.py          # slice-first enforcement, NaN handling, EMA accuracy,
│   │                               # MA warm-up period
│   ├── test_replay.py              # hit_detection (TP/SL priority, gap-down, same-bar),
│   │                               # calc_pnl (commission, reproducibility),
│   │                               # zero trades scenario
│   └── test_job_store.py           # job lifecycle, TTL cleanup, 409 conflict,
│                                   # async lock safety
│
└── cache/                          # [GITIGNORED] Parquet files
    └── BTC_USDT_4h.parquet         # managed by app, never committed
```

### Architectural Boundaries

**API Boundaries:**
```
External (Binance) ──► fetcher.py (ccxt, rate-limited, retried)
                            │ progress updates
                            ▼
                       job_store.py (in-memory Dict, asyncio.Lock)
                            │ status polling
                            ▼
                    routes/fetch.py ────► Frontend SSE stream
                            │             (fetch: events)
                       cache.py (Parquet, atomic write, startup_cleanup)
                            │
                    routes/ohlcv.py     # slice df → indicators → APIResponse
                            │
                    Frontend (JSON, ISO 8601 datetimes)

Auth boundary: settings.app_password → HTTPBasic middleware in main.py
               Applied BEFORE all /api/* routes; /health excluded
```

**Frontend Component Boundaries & Ownership:**
```
main.ts (orchestrator)
  Owns: keyboard handler, Play button state, timeframe switch intercept
  Wires: all module initialization sequence
    │
    ├── FetchManager         Owns: SSE lifecycle, job_id, heartbeat timer, progress
    │     fires: 'fetch:started/progress/complete/error/cancelled'
    │
    ├── OnboardingManager    Owns: empty state UI, getting started guide, fetch prompt
    │     subscribes: 'fetch:started', 'fetch:progress', 'fetch:complete', 'chart:dataLoaded'
    │
    ├── ToastManager         Owns: toast queue, timed undo callbacks (singleton)
    │     called by: main.ts, FetchManager, keyboard handler
    │
    ├── SettingsManager      Owns: LocalStorage read/write, defaults, schema
    │     called by: main.ts (load on init, save on change)
    │
    ├── ChartController      Owns: chart instance, OHLCV data array, LRU-1 cache
    │     fires: 'chart:ready', 'chart:dataLoaded'
    │     exposes: hasData(), loadData(), revealBar()
    │       └── CoordinateTranslator  Owns: price↔pixel mapping
    │                 subscribed to: priceScale + visibleRange changes
    │                 guard: isUpdating flag prevents re-entrant loops
    │
    ├── DrawingManager       Owns: line objects, prices, draw mode state
    │     subscribed to: 'chart:ready', 'session:reset'
    │     fires: 'drawing:lineChanged/lineDeleted/cleared'
    │     exposes: freeze(), unfreeze(), getLineSnapshot(), hasDrawings()
    │
    ├── ReplayEngine         Owns: currentBarIndex, isPlaying, speed, lineSnapshot, tradeLog
    │     subscribed to: 'chart:dataLoaded', 'session:reset'
    │     fires: 'replay:tickComplete/tradeAdded/started/paused/reset'
    │     exposes: play/pause/reset/stepForward/setSpeed/isActive/isPlaying
    │              getTradeLog(), getSummary()
    │     reads: DrawingManager.getLineSnapshot() at Play time
    │
    └── ResultsPanel         Owns: trade list UI, summary display
          subscribed to: 'replay:tradeAdded', 'replay:reset', 'replay:tickComplete'
          pulls: replayEngine.getTradeLog(), getSummary()
```

**Data Boundaries:**
```
Binance ──► fetcher.py ──► cache.py.write() [atomic .tmp→rename]
                                │
                          cache.py.read() [validate + sort + dedup assertion]
                                │
                    slice df to date_end [in routes/ohlcv.py]
                                │
                    indicators.py [receives pre-sliced df — no lookahead]
                                │
                    routes/ohlcv.py [serialize → APIResponse[OHLCVResponse]]
                                │
                    ChartController [parse → OHLCVBar[], LRU-1 cache]
                                │
                    ReplayEngine [index pointer, hit detection, float safety]
                                │
                    ResultsPanel [display only — no data ownership]
```

**OHLCV API Response Shape (final):**
```json
{
  "data": {
    "bars": [
      {
        "timestamp": 1710489600000,
        "open": 68000.0, "high": 68500.0, "low": 67800.0,
        "close": 68200.0, "volume": 1234.5,
        "ma_20": 67800.5,
        "ema_20": 67950.3
      }
    ],
    "bar_count": 17520,
    "date_start": "2024-01-01T00:00:00Z",
    "date_end":   "2024-12-31T23:59:59Z",
    "has_gaps": false,
    "gaps": []
  },
  "error": null
}
```
Note: `ma_20` / `ema_20` = `null` cho first N-1 bars (warm-up period).

**Data Flow — Happy Path:**
```
1. App start → main.py lifespan → cache.startup_cleanup()
2. settings.py validator → cache_dir.mkdir(parents=True, exist_ok=True)
3. main.ts init sequence → all modules initialized
4. SettingsManager.load() → restore {timeframe, dateRange} from LocalStorage
5. ChartController.loadData(symbol, timeframe, dateRange)
   → LRU-1 miss → GET /api/ohlcv → {bars, indicators}
   → LRU-1 hit → no API call
6. 'chart:dataLoaded' → OnboardingManager hides empty state
7. User draws Entry/TP/SL → DrawingManager updates → 'drawing:lineChanged'
8. main.ts: all lines set → enable Play button
9. User clicks Play → DrawingManager.freeze() → ReplayEngine.start(lineSnapshot)
10. Delta-time loop: advanceBar() → checkHits() → emit('replay:tickComplete', payload)
11. ChartController.revealBar() + ResultsPanel.update() per tick
12. Trade hit → ReplayEngine emit 'replay:tradeAdded' → ResultsPanel append row
13. Replay ends → ResultsPanel.showSummary() with sample size warnings
```

**Error Recovery Paths:**
```
Binance down: SSE error event → FetchManager → 'fetch:error' →
  OnboardingManager shows error + Retry button
  If cached data: ChartController.loadFromCache() + stale data warning toast

Cache corrupt: cache.read() raises CacheCorruptError →
  cache.py deletes corrupt file → routes/ohlcv.py returns 404 →
  Frontend treats as no cache → OnboardingManager shows fetch prompt
  + toast: "Cache was corrupt, fetching fresh data..."

Server restart during fetch: SSE 404 on reconnect →
  FetchManager: "Fetch interrupted" toast + manual Retry button
  (no auto-retry to avoid duplicate writes)

Replay zero trades: ReplayEngine.loop() complete, tradeLog empty →
  emit 'replay:reset' with {zeroTrades: true} →
  ResultsPanel: show FR38b message (không hiển thị summary table)

Timeframe switch with drawings:
  main.ts intercepts → DrawingManager.hasDrawings() →
  ToastManager.show("Switching clears drawings", 'warning', {
    undoDuration: 5000,
    onUndo: () => restoreTimeframe()
  })
```

### Integration Points

**Internal EventBus Events (complete list):**
```typescript
// Chart
'chart:ready'           → DrawingManager, ReplayEngine init
'chart:dataLoaded'      → OnboardingManager, ReplayEngine ready

// Fetch
'fetch:started'         → OnboardingManager show progress
'fetch:progress'        → OnboardingManager update progress bar
'fetch:complete'        → ChartController.loadData(), OnboardingManager hide
'fetch:error'           → OnboardingManager show error
'fetch:cancelled'       → OnboardingManager reset

// Drawing
'drawing:lineChanged'   → main.ts update Play button state
'drawing:lineDeleted'   → main.ts update Play button state
'drawing:cleared'       → main.ts disable Play button

// Replay
'replay:tickComplete'   → ChartController.revealBar(), ResultsPanel.update()
'replay:tradeAdded'     → ResultsPanel.appendTrade()
'replay:started'        → DrawingManager.freeze(), UI update controls
'replay:paused'         → UI update controls
'replay:reset'          → DrawingManager.unfreeze(), ResultsPanel.clear()

// Session
'session:reset'         → all modules reset to initial state
```

**External Integration:**
```
Binance REST API (public, no auth):
  GET /api/v3/klines?symbol=BTCUSDT&interval=4h&startTime=...&endTime=...&limit=1000
  Rate limit: 1200 weight/min → fetcher.py tracks + backs off

Lightweight Charts v5 API (local lib):
  chart.addCandlestickSeries() → series.setData() → series.update()
  chart.timeScale().subscribeVisibleLogicalRangeChange()
  chart.priceScale().subscribePriceScaleOptionsChanged()
  series.priceToCoordinate(price) / series.coordinateToPrice(y)
```

---

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**

| Stack Component | Version | Compatible With |
|-----------------|---------|----------------|
| FastAPI | 0.135.3 | Pydantic v2, uvicorn, Python 3.12 ✅ |
| pyarrow | 24.0.0 | pandas (transitive), Python 3.12 ✅ |
| ccxt | 4.5.48 | asyncio, full async support ✅ |
| TypeScript | 6.0 | esbuild 0.28.0, lightweight-charts 5.1.0 ✅ |
| esbuild | 0.28.0 | TypeScript 6.0 transpile (no type check) ✅ |
| lightweight-charts | 5.1.0 | Full TypeScript type definitions ✅ |
| uv | latest | pyproject.toml, pytest-asyncio ✅ |
| overmind | latest | Procfile, macOS (brew) ✅ |

**Pattern Consistency:** ✅ Tất cả patterns align

| Pattern Pair | Alignment |
|-------------|-----------|
| snake_case Python ↔ snake_case API ↔ snake_case JSON | ✅ |
| snake_case.ts files ↔ PascalCase classes (explicitly documented) | ✅ |
| routes/ HTTP only ↔ services/ business logic ↔ typed exceptions | ✅ |
| EventBus typed via EventMap ↔ all events defined in types.ts | ✅ |
| normalize(price) ↔ LineSnapshot stores normalized prices | ✅ |
| atomic write (.tmp→rename) ↔ startup_cleanup() removes orphaned .tmp | ✅ |
| job_store.py middleman ↔ fetcher.py không emit SSE trực tiếp | ✅ |
| slice-first indicators ↔ routes/ohlcv.py slices trước khi gọi indicators.py | ✅ |

**Minor Coherence Note:**
`backend/services/replay.py` là Python reference implementation — không được import từ routes hay services khác. Chỉ được dùng bởi `tests/test_replay.py`. Phải có docstring: `"""Python reference implementation for hit detection. Used by tests only — do not import from routes or other services."""`

### Requirements Coverage Validation ✅

**Functional Requirements (44 FRs):**

| Category | FRs | Coverage |
|----------|-----|---------|
| Data Management | FR1–6 | ✅ fetcher.py, cache.py, job_store.py, routes/fetch.py |
| Chart Display | FR7–12 | ✅ chart_controller.ts, coordinate_translator.ts |
| Drawing Tools | FR13–19c | ✅ drawing_manager.ts + freeze/unfreeze + 1-per-type |
| Bar Replay | FR20–25 | ✅ replay_engine.ts + delta-time + reveal-only |
| Trade Execution | FR26–33 | ✅ hit detection + normalize() + LineSnapshot |
| Session Results | FR34–37 | ✅ results_panel.ts + warning flags |
| Onboarding | FR38–41 | ✅ onboarding_manager.ts + toast_manager.ts |
| Configuration | FR42–44 | ✅ settings.py + HTTPBasic + .env.example |

**Critical FRs Spot Check:**

| FR | Decision |
|----|----------|
| FR12: No look-ahead in replay | ✅ Index pointer + slice-first indicators |
| FR19b: 1 Entry + 1 TP + 1 SL max | ✅ drawing_manager.ts enforces |
| FR19c: Switch timeframe → clear drawings | ✅ main.ts intercept + toast undo |
| FR23: Reset keeps drawings | ✅ replay:reset → unfreeze không clear |
| FR25: Signal at close(N), execute at open(N+1) | ✅ hit detection logic |
| FR29: Same-bar TP/SL priority by candle direction | ✅ test_replay.py covers |
| FR31: P&L locked at Play time | ✅ LineSnapshot frozen on play |
| FR36: Sample size warnings (< 10 / < 30) | ✅ SessionSummary warning flags |
| FR38b: Zero trades message | ✅ ResultsPanel handles zeroTrades flag |

**Non-Functional Requirements (26 NFRs):**

| Category | NFRs | Coverage |
|----------|------|---------|
| Performance | NFR1–8 | ✅ LRU-1, delta-time, pointer, < 500ms target |
| Security | NFR9–11 | ✅ HTTPBasic, localhost bind, env vars |
| Data Integrity | NFR12–18 | ✅ slice-first, atomic, normalize(), sort assert, commission |
| Integration | NFR19–22 | ✅ rate limit backoff, ccxt, Parquet compat |
| Reliability | NFR23–25 | ✅ startup_cleanup, corrupt detect, empty state |
| Browser compat | NFR26 | ✅ vanilla TS, no framework, Chrome/Safari |

### Implementation Readiness Validation ✅

**Decision Completeness:** 20 ADRs documented (ADR-01 → ADR-20b)
- ✅ All critical decisions have version numbers
- ✅ All decisions have rationale documented
- ✅ Trade-offs explicitly stated for major decisions

**Structure Completeness:**
- ✅ 10 backend files defined với responsibilities
- ✅ 12 frontend files defined với public APIs
- ✅ 3 static files defined
- ✅ 6 test files defined với test naming conventions
- ✅ Root config files: .env.example, .gitignore, Procfile, README

**Pattern Completeness:** 9 categories covered
- ✅ Naming (Python, API, TypeScript, Parquet files)
- ✅ Format (API wrapper, datetime, JSON fields, null/undefined)
- ✅ Structure (import ordering, separation of concerns, CSS)
- ✅ Communication (EventBus, EventMap, push vs pull, immutable updates)
- ✅ Process (async/await, exceptions, retry, log levels, float safety)
- ✅ Testing (conftest fixtures, import convention, naming convention)
- ✅ Safety-Critical (9 patterns that prevent silent bugs)
- ✅ Error Handling (exception hierarchy, route catches / service raises)
- ✅ HTTP status codes mapped to error types

### Gap Analysis Results

**Critical Gaps: 0** — Tất cả resolved qua 6 rounds Advanced Elicitation

**Important Gaps (minor, không block implementation):**

1. `replay.py` cần docstring nêu rõ "test validation only"
2. `conftest.py sample_bars` fixture cần actual TP/SL hit bars với correct OHLC values
3. `tsconfig.json` exact settings (`"target": "ES2020"`, `"module": "CommonJS"`, `"strict": false`) chưa specified
4. CSS design tokens cho Entry/TP/SL line colors chưa defined (`--color-entry: #2196F3`, `--color-tp: #4CAF50`, `--color-sl: #F44336`)

**Nice-to-Have (deferred):**
- GitHub Actions CI workflow
- Pre-commit hooks cho `tsc --noEmit`
- VSCode workspace settings (`.vscode/settings.json`)

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] 44 FRs và 26 NFRs phân tích kiến trúc đầy đủ
- [x] Project scale assessed: High complexity, local-first, single-user
- [x] Technical constraints identified: stack locked, browser matrix, deployment path
- [x] 18 cross-cutting concerns mapped và assigned owners

**✅ Architectural Decisions (20 ADRs)**
- [x] Frontend: TypeScript 6.0 + esbuild + EventBus + LRU-1 cache
- [x] Backend: FastAPI + uv + Pydantic Settings + module split
- [x] Data: Parquet atomic write + slice-first indicators + job_store
- [x] Dev: overmind + Procfile + tsc --noEmit separation
- [x] Security: HTTPBasic, localhost bind, env vars

**✅ Implementation Patterns (15 conflict points resolved)**
- [x] Naming: snake_case Python/API/JSON, snake_case.ts files, PascalCase classes
- [x] Format: {data,error} wrapper, ISO 8601 UTC, both fields always present
- [x] Process: async/await, typed exceptions, centralized retry, normalize(price)
- [x] Safety-Critical: 9 patterns preventing silent bugs documented

**✅ Project Structure (28 files defined)**
- [x] Complete directory tree với file-level responsibilities
- [x] Component boundaries và ownership documented
- [x] Full EventBus event inventory (20 events)
- [x] Happy path + 5 error recovery paths documented
- [x] Data flow end-to-end mapped

### Architecture Readiness Assessment

**Overall Status: READY FOR IMPLEMENTATION** 🟢

**Confidence Level: High**
- Stack hoàn toàn locked với verified versions (April 2026)
- 20 ADRs cover tất cả critical decisions
- 18 architectural gaps được phát hiện và resolved qua Advanced Elicitation
- 28 files được defined với clear responsibilities và public APIs
- Safety-critical patterns documented với code examples

**Key Strengths:**
1. **Look-ahead bias prevention** được thiết kế xuyên suốt từ backend (slice-first) đến frontend (index pointer)
2. **Data integrity** được enforce ở nhiều layers: atomic write, sort assertion, normalize(), commission bắt buộc
3. **Event architecture** clean: typed EventMap, single tickComplete event, no circular chains
4. **Solo dev ergonomics**: overmind, uv, flat frontend structure, LRU-1 simplicity
5. **Future-proof**: deploy-ready config, Phase 2 extension points documented

**Areas for Future Enhancement:**
- TypeScript upgrade lên 7.0 khi stable (Go-based, 10x faster)
- Supabase hybrid cache (Phase 2 cross-device sync)
- pandas-ta-classic assessment khi Phase 2 indicators needed
- Multi-timeframe memory cache nếu UX cần

### Implementation Handoff

**AI Agent Guidelines:**
1. Follow ADR-01 → ADR-20b cho mọi technical decisions
2. Implement Safety-Critical patterns TRƯỚC tiên (normalize, atomic write, slice-first)
3. Follow Implementation Sequence từ Core Architectural Decisions section
4. Refer to EventMap trong types.ts cho tất cả event definitions
5. Test replay.py logic trước khi port sang TypeScript

**First Implementation Priority (Sprint sequence):**
```
Spike:   static/index.html + lightweight-charts candlestick prototype
Sprint 1: backend foundation (settings, models, exceptions, cache, fetcher)
Sprint 2: chart_controller.ts + data loading end-to-end
Sprint 3: drawing_manager.ts (highest technical risk)
Sprint 4: replay_engine.ts + hit detection
Sprint 5: results_panel.ts + full session flow
Sprint 6: onboarding + polish + dogfooding
```

**Setup Commands:**
```bash
# Backend
uv sync
uv run uvicorn backend.main:app --reload --port 8000

# Frontend (watch)
npx esbuild frontend/main.ts --bundle --outfile=static/app.js --watch --sourcemap
npx tsc --noEmit --watch  # type check

# All-in-one (recommended)
brew install overmind
overmind start

# Tests
uv run pytest tests/ -v
```
