---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete', 'step-e-01-discovery', 'step-e-02-review', 'step-e-03-edit']
lastEdited: '2026-04-23'
editHistory:
  - date: '2026-04-23'
    changes: 'FR2: remove Parquet implementation detail; FR42: remove env var names keep categories; NFR26: add concrete test criteria; Domain-Specific: add Compliance Context section'
inputDocuments:
  - '_bmad-output/planning-artifacts/research/domain-crypto-backtest-research-2026-04-23.md'
workflowType: 'prd'
briefCount: 0
researchCount: 1
brainstormingCount: 0
projectDocsCount: 0
classification:
  projectType: web_app
  domain: fintech
  complexity: high
  projectContext: greenfield
  architecture: 'Python FastAPI backend + Vanilla JS + Lightweight Charts'
  coreUX: 'Draw tools (horizontal lines) + bar replay + per-trade results'
  keyFeatures:
    - 'TP/SL exit lines with price snap'
    - 'bar-by-bar replay with speed control'
    - 'look-ahead bias prevention'
    - 'per-trade audit trail'
    - 'local Parquet cache'
  scopeExclusion:
    - 'live trading'
    - 'Supabase (Phase 2)'
    - 'RSI/MACD/BB/VWAP (Phase 2)'
---

# Product Requirements Document - stock_backtest_project

**Author:** Narron
**Date:** 2026-04-23

## Executive Summary

**TradingView Bar Replay Alternative** — công cụ backtest visual self-hosted cho trader crypto cá nhân muốn xác nhận trading edge là skill thật sự hay variance ngắn hạn. Tool mô phỏng điều kiện ra quyết định thực tế (không biết tương lai) qua bar-by-bar chart replay, cho phép luyện tập với sample size đủ lớn mà không bị giới hạn bởi subscription hay số lệnh live.

**Target user:** Trader crypto cá nhân profitable, kinh nghiệm thực chiến, muốn luyện tập strategy mà không tốn phí TradingView Pro ($15–60/tháng). Win rate hiện tại 56–58%, mục tiêu cải thiện qua structured practice.

**Problem:** Trader không thể tích lũy đủ sample size từ live trading (vài chục lệnh/tháng) để kết luận strategy có edge nhất quán. Backtest tools hiện có (Backtrader, VectorBT) chỉ cho kết quả số — không có context visual để hiểu *tại sao* mỗi lệnh thắng/thua. TradingView Bar Replay giải quyết đúng vấn đề nhưng khóa sau paywall.

**Differentiator:** Self-hosted, zero subscription cost — trader vẽ điều kiện entry/exit trực tiếp lên chart (horizontal lines cho Entry/TP/SL) thay vì viết code. Bar replay animate từng nến như video, cho phép trader "cảm" được thị trường thay vì chỉ đọc kết quả cuối.

**Core insight:** Luyện tập trade hiệu quả đòi hỏi *context thời gian thực* — biết chính xác thông tin nào có sẵn tại thời điểm ra quyết định. Chỉ bar-by-bar visual replay mới simulate được điều này.

## Project Classification

| Thuộc tính | Giá trị |
|---|---|
| **Project Type** | Web App (local-first, single-user) |
| **Domain** | Fintech — Crypto Trading Education |
| **Complexity** | High |
| **Project Context** | Greenfield |
| **Architecture** | Python FastAPI + Vanilla JS + Lightweight Charts (MIT) |
| **Scope** | Personal tool, không có live trading |

## Success Criteria

### User Success

- Flow từ mở app → bắt đầu replay ≤ 4 user actions
- Trader test được ≥ 2 variant TP/SL trên cùng data và so sánh kết quả
- Sau 10 sessions replay, trader có thể articulate ≥ 2 điều kiện thị trường cụ thể khiến strategy fail
- Win rate baseline 56–58% có thể được track và so sánh qua thời gian

### Business Success

- Zero critical bugs trong core replay flow (chart display → drawing → replay → results)
- Zero subscription/API cost — chạy hoàn toàn với free tier Binance public API
- Chạy local không cần internet sau khi data cached

### Technical Success

- Replay animation ≥ 30fps, không drop frame khi đổi tốc độ
- Drawing tool: đặt đường tại đúng price level trong < 3 clicks với price snap
- Per-trade breakdown: entry price, exit price (TP/SL), P&L từng lệnh, timestamp nến trigger
- Data fetch < 5 phút lần đầu (2 năm data trên Wifi ổn định), load từ cache < 2 giây
- Không có look-ahead bias trong tính toán kết quả

### Measurable Outcomes

| Metric | Target |
|---|---|
| User actions (open → replay) | ≤ 4 bước |
| Replay frame rate | ≥ 30fps, không drop frame |
| Drawing precision | Đặt đường đúng price level < 3 clicks |
| Data load (cached) | < 2 giây |
| Data fetch (first run, 2 năm) | < 5 phút trên Wifi |
| Critical bugs trong core flow | 0 |

## Product Scope

### Phase 1 — MVP

**Core experience:** Vẽ strategy → replay → thấy lệnh hit → đọc kết quả

| Feature | Ghi chú |
|---|---|
| Candlestick chart BTC/USDT | Lightweight Charts |
| Timeframe 5m, 30m, 1h, 4h, 1D | Lazy load per timeframe |
| Date range selection | Chọn giai đoạn luyện tập |
| Bar replay (play/pause + 3 tốc độ) | requestAnimationFrame |
| Horizontal line drawing (Entry/TP/SL) | Click để vẽ |
| Price snap + drag to move lines | Drawing UX |
| Reset replay giữ nguyên drawings | Cho phép so sánh variant |
| MA/EMA overlay | Incremental calculation, no look-ahead |
| OHLCV tooltip khi hover | Debug + learning |
| Per-trade breakdown (entry/exit/P&L/timestamp) | Audit trail |
| Summary stats (win/loss, tổng P&L %) | Text đơn giản |
| Commission 0.1% per side | Hardcoded, không có settings UI |
| Warning khi sample size < 10 lệnh | Result reliability |
| Local Parquet cache | Offline-capable sau lần đầu |
| "Refresh Data" button | Overwrite cache, fetch fresh từ Binance |
| Deploy-ready config (env vars) | Future-proof architecture |
| Onboarding empty state + getting started guide | Static text, 3 bước |

**MVP cuts (explicit):**
- Supabase cache sync → Phase 2
- RSI, MACD, Bollinger Bands, VWAP → Phase 2
- Commission settings UI → Phase 2
- Rectangle/zone drawing tools → Phase 2
- Session naming và history persistence → Phase 2
- Multiple concurrent positions → không trong scope

### Phase 2 — Growth

- Supabase hybrid cache (cross-device sync, hot path: Local → Supabase → Binance)
- Auto-incremental data update (chỉ fetch candles mới kể từ `last_candle_timestamp`)
- Session naming và history persistence
- Progress tracking (win rate theo thời gian, equity curve)
- Market regime tagging (bull/bear/sideways)
- Indicators bổ sung: RSI, MACD, Bollinger Bands, VWAP
- Commission settings UI
- Drawing tools nâng cao: zones, trendlines
- Basic iPad touch optimization
- Koyeb deployment

### Phase 3 — Vision

- Multi-pair support (ETH/USDT, SOL/USDT, v.v.)
- Practice mode (ẩn tương lai, trader tự đặt lệnh trước khi reveal)
- Trade journal tự động (export CSV/PDF)
- Strategy comparison (2 variant song song trên cùng data)
- Reflection mode + decision quality score
- AI coaching từ behavioral patterns
- Scenario packs (flash crash, bull run, sideways)

## User Journeys

### Journey 1: Luyện tập hàng ngày (Happy Path)

**Context:** 9 giờ tối, Narron vừa đóng phiên live. Có 2 lệnh hôm nay: 1 thắng, 1 thua. Lệnh thua: SL hit rồi giá đảo chiều ngay. Anh mở tool để luyện tập thêm trên data lịch sử, muốn hiểu khi nào nên giữ SL rộng hơn.

**Flow:**
1. Chọn BTC/USDT 4h, kéo date range về tháng 3/2024 (giai đoạn nhiều false breakout)
2. Vẽ 3 đường: entry 68,500 / TP 71,000 / SL 67,800
3. Nhấn Play (tốc độ Normal) — nến chạy từng cây, lệnh hit
4. Lệnh thứ 3: SL tại 67,800 bị hit, nhưng nếu rộng hơn 200 điểm thì thắng
5. Pause → drag SL xuống 67,600 → Reset Replay (drawings giữ nguyên) → chạy lại
6. So sánh: SL chặt (67,800) → 4W/6L; SL rộng (67,600) → 7W/3L

**Outcome:** Per-trade breakdown với timestamp cho thấy 3 lệnh thua đều là noise ngắn hạn. Insight cụ thể: setup 4h cần SL tối thiểu 300 điểm.

**Capabilities required:** Date range selection, drawing tools + price snap + drag to move, bar replay controls, reset replay giữ drawings, per-trade breakdown với timestamp, summary stats, commission 0.1% per side.

---

### Journey 2: First-time Setup

**Context:** Narron vừa clone repo, chạy lệnh khởi động. Lần đầu mở browser — app ở empty state, chưa có data.

**Flow:**
1. App hiển thị: "Chưa có data — Fetch BTC/USDT?" + nút confirm
2. Click confirm → progress indicator → tối đa 5 phút (điều kiện Wifi ổn định): 2 năm data cached
3. Getting started guide: (1) Chọn timeframe, (2) Vẽ entry line, (3) Nhấn Play
4. Hover lên chart → price label snap vào giá gần nhất → click đặt entry line
5. Chọn type "Entry" → vẽ TP → vẽ SL → nhấn Play
6. Lần đầu tiên thấy marker "BUY" khi giá chạm entry line

**Outcome:** 10 phút sau khi mở app lần đầu, session replay đầu tiên hoàn thành. Data cached — lần sau load < 2 giây. Nếu Binance API down: app fallback sang cached data, không crash.

**Capabilities required:** Onboarding empty state, data fetch + progress indicator + auto-retry, local caching, drawing type selector (Entry/TP/SL), getting started guide 3 bước, API error handling.

---

### Journey 3: Test Strategy Mới

**Context:** Narron đọc thread về "Liquidity Sweep" strategy — chưa từng dùng, muốn backtest trước khi dùng tiền thật.

**Flow:**
1. Chọn date range cả năm 2023 (đủ sample)
2. Vẽ entry thấp hơn swing low, TP tại previous high, SL 150 điểm bên dưới entry
3. Replay chạy — pattern xuất hiện thưa hơn dự kiến
4. App hiển thị warning sau 100 nến: "Chỉ có 3 lệnh — sample size chưa đủ tin cậy"
5. Replay xong cả năm: 8 lệnh, 5W/3L, win rate 62.5%
6. Per-trade breakdown với timestamp: 3 lệnh thua đều trong tháng 11–12/2023 (bull run mạnh)

**Outcome:** Insight rõ: strategy fail trong strong trend. Quyết định không dùng trong bull market.

**Capabilities required:** Date range dài (1 năm), warning sample size < 10 lệnh, per-trade timestamp, OHLCV tooltip khi hover nến.

---

### Journey 4: Debugging Look-ahead Bias

**Context:** Narron chạy session, kết quả win rate 89% — quá cao, nghi ngờ look-ahead bias.

**Flow:**
1. Kiểm tra per-trade breakdown: lệnh số 5 có timestamp trùng với nến chưa đóng
2. Hover lên nến đó → tooltip OHLCV hiện ra → confirm giá trigger là close của nến chưa đóng
3. Reset session với date range nhỏ (1 tuần), quan sát kỹ từng trigger
4. Per-trade log hiển thị: "Trigger tại nến đóng [2024-03-15 08:00]"
5. Fix logic: chỉ check điều kiện khi nến đóng hoàn toàn
6. Win rate về 61% — hợp lý

**Outcome:** OHLCV tooltip và per-trade audit trail là công cụ debug thiết yếu cho data integrity.

**Capabilities required:** Per-trade audit trail (nến trigger, timestamp exact, giá OHLC tại trigger), OHLCV tooltip khi hover, trigger rule explicit (chỉ tại nến đóng).

---

### Business Rules

| Rule | Specification |
|---|---|
| Entry trigger | Kích hoạt khi nến đóng hoàn toàn — không intra-candle |
| TP vs SL cùng nến | Nến bullish → check TP trước; nến bearish → check SL trước |
| Lệnh không có TP/SL | Auto-close tại nến cuối date range |
| Concurrent positions | MVP: 1 position tại một thời điểm |
| Commission | 0.1% mỗi chiều — hardcoded, không có settings UI trong MVP |
| P&L calculation | Tính theo % price move × commission — reproducible cho cùng data + strategy |

## Domain-Specific Requirements

### Compliance Context

Tool này được classify là Fintech domain nhưng là **educational/personal tool** — không xử lý real financial transactions, không có user funds, không có live trading. Standard fintech compliance (PCI-DSS, KYC/AML, SOX) **không applicable**. Security requirements giới hạn ở authentication khi deployed (FR42–FR43) và data integrity cho backtest accuracy (NFR12–NFR18).

### Data Pipeline

- Lazy loading per (symbol, timeframe) — fetch khi user chọn lần đầu
- Cache format: **Parquet** per (symbol, timeframe): `cache/BTC_USDT_5m.parquet`
- Filename encode metadata — không cần manifest JSON
- Dedup duplicate timestamps sau mỗi fetch batch
- Sort by timestamp ascending tại mọi data load point
- Detect và warn khi có data gaps trong range đã chọn
- Auto-retry 3 lần với exponential backoff khi fetch fail
- Clip date range về max available nếu vượt quá data cached, thông báo user
- Disk space warning trước khi fetch 5m data (~50MB)

### Timeframes

5m, 30m, 1h, 4h, 1D — lazy load, cache riêng biệt per timeframe

### Indicators (MVP)

Pre-compute incremental tại data load: **MA, EMA**

- Chỉ tính với data [0..N] — không dùng dữ liệu tương lai
- Warning khi date range ngắn hơn indicator period
- Indicator NaN đầu series → không vẽ, không crash

*Phase 2: RSI, MACD, Bollinger Bands, VWAP*

### Execution Model (Look-ahead Bias Prevention)

- **Signal tại close(N) → Execute tại open(N+1)** — realistic execution model
- Chỉ reveal OHLC của nến sau khi nến complete trong replay loop
- Per-trade audit trail hiển thị: nến trigger, timestamp exact, giá OHLC tại trigger

### Display & Timezone

- Store timestamp dạng **UTC** trong cache
- Display theo **UTC+7** (Vietnam) trên chart

### Error Handling

- Cache corrupt → delete + re-fetch tự động, thông báo user
- Date range vượt cache → clip + warn rõ ràng
- Binance API down → fallback sang cached data, không crash
- Loading spinner khi fetch/calculate (non-blocking UI)

## Innovation & Competitive Differentiation

### Detected Innovation Areas

1. **Visual-first strategy definition** — Drawing là native language của trader thực chiến. Không cần code, không cần form — trader express trading intent bằng cách vẽ trực tiếp lên chart. Zero cognitive translation overhead so với backtest tools hiện tại.

2. **Time compression** — Test 1 năm market data trong 10 phút. Paper trading yêu cầu đợi market diễn ra theo thời gian thật; tool này compress experience để tích lũy đủ sample size trong thời gian ngắn.

3. **Embodied learning** — Bar replay tạo emotional engagement: trader *relive* market moment với đầy đủ context, không chỉ đọc aggregate statistics. Learning xảy ra qua experience, không qua analysis.

4. **Trading flight simulator framing** — Fail safely without real consequences, build intuition qua repetition, compress years of experience. Framing khác biệt so với "backtest tool."

5. **Opinionated simplicity** — 1 position at a time là design decision có chủ đích. Zero-friction flow: vẽ → play → result. Không có configuration overhead.

### Competitive Landscape

| Tool | Gap |
|---|---|
| TradingView Bar Replay | Giải quyết đúng vấn đề, nhưng $15–60/tháng |
| Backtrader / VectorBT | Powerful nhưng yêu cầu coding — barrier cao với trader |
| Paper trading | Real-time only — không compress được time |
| **This tool** | Visual-first + time compression + zero-cost + self-hosted |

### Validation Approach

- Narron dùng tool luyện tập ≥ 10 sessions, so sánh insights với live trading experience
- Core metric: Identify ≥ 2 điều kiện thị trường cụ thể từ replay sessions
- Qualitative signal: Replay experience gần với live trading hơn là đọc số liệu

### Future Innovation Angles (Vision)

- **Reflection mode:** Trader tự đánh giá quyết định trước khi thấy outcome
- **Decision quality score:** Phân biệt lucky profit vs good decision
- **Scenario packs:** Standardized market scenarios (flash crash, bull run, sideways)
- **AI coaching:** Phân tích behavioral patterns — "Bạn thường cut winners quá sớm"

## Web App Specific Requirements

### Architecture Overview

Single Page Application (SPA), local-first, single-user. **Design principle: Local-first, Deploy-ready** — build cho local trước nhưng architecture không block future deployment.

**Frontend:** Vanilla JS (không dùng React/Vue để giảm complexity) + Lightweight Charts (TradingView open-source, MIT) — canvas-based rendering, tối ưu cho financial charts với 210k+ data points (5m timeframe).

**Frontend State Management (ADR-01):** Class-based modules, event-driven communication — `ReplayEngine`, `DrawingManager`, `ChartController`, `ResultsPanel`. Mỗi class own state của mình, communicate qua custom events. Phù hợp Flutter Widget mindset — không dùng global mutable state.

**Backend:** Python FastAPI — serve OHLCV data, tính indicators, xử lý cache pipeline. REST API, không cần WebSocket trong MVP.

**Indicator Transport (ADR-02):** Indicators được tính trên backend (pandas-ta), trả về cùng OHLCV response dưới dạng extra columns. 210k rows × 6+ columns compressed Parquet ~15MB — acceptable cho local transport. Không paginate trong MVP.

**Canonical OHLCV Schema (ADR-03):**
```
timestamp: int64  (Unix milliseconds, UTC)
open:      float64
high:      float64
low:       float64
close:     float64
volume:    float64
```
Schema này là contract giữa backend cache (Parquet), API response (JSON), và Phase 2 Supabase table. Mọi thay đổi schema phải update PRD trước.

### Browser Matrix

| Browser | Support Level |
|---|---|
| Chrome latest | Primary — full support |
| Safari desktop latest | Primary — full support |
| Safari iPad latest | Basic — touch drawing works, không optimized |
| Firefox | Not required |

### Configuration

Tất cả qua environment variables, không hardcode:

```
HOST=0.0.0.0
PORT=8000
CACHE_DIR=./cache
APP_PASSWORD=          # empty = no auth (local); set = HTTP Basic Auth (deployed)
SUPABASE_URL=          # optional, Phase 2
SUPABASE_KEY=          # optional, Phase 2
```

### Data Cache Architecture

**Cache Priority Flow:**
```
1. Local Parquet (fastest, offline-capable)
2. Supabase (Phase 2 — cross-device sync)
3. Binance API (source of truth)
```

**"Refresh Data" Button (MVP):**
- User-triggered manual refresh
- Overwrite toàn bộ cache cho symbol/timeframe hiện tại
- Fetch fresh từ Binance → save local
- Use case: khi nghi ngờ data bị sai

**Auto-incremental Update (Phase 2):**
- Check `last_candle_timestamp` khi mở app
- Nếu cache cũ hơn threshold → fetch phần mới, merge vào cache hiện có
- Không interrupt user nếu data đủ fresh

### Performance Targets

| Metric | Target |
|---|---|
| Initial page load | < 3 giây |
| Chart render từ cache | < 2 giây |
| Replay frame rate | ≥ 30fps ở mọi tốc độ |
| API response (OHLCV + indicators từ cache) | < 500ms |
| 5m data load (210k rows) | < 5 giây |
| App startup | < 10 giây từ lệnh khởi động |

### Deploy-Ready Architecture Decisions

Các decisions trong MVP code để không self-block future deployment:
- `host=0.0.0.0` default (override qua env var)
- `APP_PASSWORD` env var — empty = no auth, set = HTTP Basic Auth
- `getEventCoordinates(e)` helper — abstract mouse/touch input (enables iPad)
- Layout `min-width: 1024px`, chart `width: 100%` của container
- Không hardcode paths hay URLs

**Deployment Path (Phase 2, ngoài MVP scope):**
- Platform: Koyeb free plan (Docker/buildpack, đã proven)
- HTTPS: Koyeb handles tự động
- Env vars: set trên Koyeb dashboard

### Accessibility & SEO

- SEO: Không applicable — local/personal tool
- Keyboard shortcuts: Space (play/pause), arrow keys (step forward/back), phím 1/2/3 (speed Slow/Normal/Fast)
- No WCAG compliance required

## Development Plan

### MVP Strategy

**MVP Approach:** Experience MVP — deliver core "aha moment" trước: vẽ strategy → replay → thấy lệnh hit trên chart. Mọi feature khác phục vụ cho moment này.

**Resource:** Solo developer (Narron), Flutter background, learning JS + Python. No hard deadline — learning-first approach.

**Learning Path:** Python basics (1 tuần) → FastAPI backend → JS frontend. Không học 2 language song song.

**Technical Spike (trước Sprint 1):** Validate Lightweight Charts + custom horizontal line drawing trong 1–2 ngày. Nếu không khả thi → evaluate Chart.js hoặc Apache ECharts.

### Sprint Plan

**Timeline là estimate, không phải deadline.** "MVP done" = có thể chạy một replay session hoàn chỉnh end-to-end, không phụ thuộc vào số tuần. Với learning curve JS + Python, thực tế có thể stretch 1.5–2x.

| Sprint | Tuần (estimate) | Deliverable | Done-criteria |
|---|---|---|---|
| Spike | 1 | Lightweight Charts + 1 horizontal line prototype | **Go/No-Go gate** — nếu fail → re-scope drawing trước Sprint 1 |
| 1 | 2–3 | FastAPI + Binance fetch + local Parquet cache | Mock OHLCV endpoint trả data cho frontend — không block UI |
| 2 | 4–5 | Candlestick chart render từ API | API call từ browser hiển thị chart thành công — không phải UI đẹp |
| 3 | 6–7 | Horizontal line drawing + price snap + drag to move | Drawing là **highest technical risk** — nếu stuck > 2 tuần → re-evaluate |
| 4 | 8–9 | Bar replay loop (requestAnimationFrame) | Nến reveal từng cây đúng thứ tự, không flicker |
| 5 | 10–11 | Hit detection + per-trade result display | 1 lệnh hit được ghi nhận đúng với entry/exit/P&L |
| 6 | 12+ | MA/EMA + polish + **dogfooding** | Narron ngồi dùng như trader (không phải developer) ≥ 1 session hoàn chỉnh |

### Risk Mitigation

| Risk | Mitigation |
|---|---|
| Lightweight Charts không support custom drawing natively | Technical spike (2 ngày) là Go/No-Go gate. Fallback: overlay HTML5 canvas — trade-off: sync coordinate system + pixel ratio + touch events thủ công |
| Tất cả chart library candidates đều fail | Evaluate Apache ECharts hoặc Chart.js — nếu cả 3 fail, scope MVP-lite: click để nhập price thay vì drag-to-draw |
| Horizontal line drawing stuck quá lâu | Hard rule: stuck > 2 tuần ở Sprint 3 → re-scope trước khi tiếp tục |
| Data pipeline rabbit hole | Sprint 1 ship mock OHLCV endpoint song song — frontend không bị block |
| UI perfectionism | Sprint 2 done-criteria: API call từ browser thành công — không phải UI đẹp |
| JS `this` binding | Arrow functions hoặc `.bind(this)` từ đầu |
| Replay timing accuracy | `requestAnimationFrame` từ đầu, không dùng `setInterval` |
| FastAPI async complexity | Synchronous endpoints trước, optimize sau — đủ cho single-user |
| Build mode vs use mode | Dogfooding milestone bắt buộc ở Sprint 6 — dùng như trader, không phải developer |

### Implementation Notes (Flutter Dev → JS/Python)

- **JS code style:** Class-based từ đầu — tương tự Flutter Widget mindset
- **FastAPI auto-docs:** Test API qua `/docs` endpoint trước khi viết frontend
- **pandas-ta:** `df.ta.ema(length=20)` — không implement formula thủ công
- **Lightweight Charts:** Copy-paste official examples, modify — không viết từ đầu
- **Browser cache:** Thêm `?v=timestamp` vào script tags khi JS/CSS không update

## Functional Requirements

### 1. Data Management

- **FR1:** Trader fetch được dữ liệu OHLCV lịch sử của một trading pair từ Binance public API (không cần API key)
- **FR2:** Hệ thống tự động lưu data đã fetch xuống local storage per (symbol, timeframe) để sử dụng offline
- **FR3:** Trader trigger "Refresh Data" để overwrite toàn bộ cache và fetch fresh từ Binance
- **FR4:** Hệ thống detect và cảnh báo khi có data gaps trong date range đã chọn
- **FR5:** Hệ thống hỗ trợ 5 timeframes (5m, 30m, 1h, 4h, 1D) với lazy loading — chỉ fetch khi user chọn lần đầu
- **FR6:** Hệ thống clip date range về giới hạn data có sẵn và thông báo user

### 2. Chart Display

- **FR7:** Trader xem được candlestick chart với dữ liệu OHLCV
- **FR8:** Trader chọn timeframe để hiển thị chart
- **FR9:** Trader chọn date range để xem giai đoạn cụ thể
- **FR10:** Trader hover lên nến để xem thông tin OHLCV chi tiết (Open, High, Low, Close, Volume, timestamp)
- **FR11:** Trader xem MA và EMA overlay trên chart — chỉ hiển thị đến nến hiện tại trong replay
- **FR12:** Hệ thống chỉ hiển thị data và indicators của các nến đã đóng hoàn toàn trong replay mode

### 3. Drawing Tools

- **FR13:** Trader vẽ đường ngang Entry lên chart bằng click
- **FR14:** Trader vẽ đường ngang Take Profit lên chart bằng click
- **FR15:** Trader vẽ đường ngang Stop Loss lên chart bằng click
- **FR16:** Hệ thống tự động snap đường vẽ vào mức giá gần nhất khi user đặt đường
- **FR17:** Trader kéo (drag) đường đã vẽ để thay đổi vị trí mà không cần xóa và vẽ lại
- **FR17b:** Trader xóa một đường đơn lẻ (click chọn đường → nhấn Delete/Backspace hoặc nút xóa trên đường)
- **FR18:** Hệ thống hiển thị price label trên đường vẽ để trader biết giá chính xác
- **FR19:** Hệ thống phân biệt rõ ràng 3 loại đường bằng màu sắc: Entry, Take Profit, Stop Loss
- **FR19b:** Hệ thống giới hạn tối đa 1 Entry + 1 TP + 1 SL tại một thời điểm — vẽ đường mới cùng loại sẽ thay thế đường cũ
- **FR19c:** Khi user switch timeframe, tất cả drawings bị xóa — chart là blank slate cho timeframe mới

### 4. Bar Replay

- **FR20:** Trader bắt đầu replay bar-by-bar từ đầu date range đã chọn
- **FR21:** Trader pause và resume replay tại bất kỳ vị trí nào
- **FR22:** Trader điều chỉnh tốc độ replay: Slow (~500ms/nến), Normal (~150ms/nến), Fast (~30ms/nến) — bằng UI button hoặc phím tắt 1/2/3. Tất cả 3 speeds đều reveal từng nến một — Fast không skip nến, chỉ nhanh hơn
- **FR23:** Trader reset replay về đầu date range mà không mất các đường đã vẽ — chart scroll về đầu date range, zoom level giữ nguyên
- **FR24:** Hệ thống reveal từng nến theo thứ tự thời gian — không hiển thị nến tương lai
- **FR25:** Hệ thống chỉ check điều kiện entry/TP/SL tại thời điểm nến đóng hoàn toàn (close(N) → execute tại open(N+1))

### 5. Trade Execution & Results

- **FR26:** Tại close(N): nếu high(N) ≥ Entry price và chưa có position mở → ghi nhận lệnh mở tại open(N+1). Không check intra-candle
- **FR27:** Tại close(N) khi có position mở: nếu high(N) ≥ TP price → đóng lệnh thắng tại TP price
- **FR28:** Tại close(N) khi có position mở: nếu low(N) ≤ SL price → đóng lệnh thua tại SL price. Edge case gap-down: nếu open(N) < SL price → đóng tại open(N) (slippage), không tại SL price
- **FR29:** Tại close(N) khi TP và SL đều bị touch trong cùng một nến: nến bullish (close > open) → check TP trước; nến bearish (close < open) → check SL trước
- **FR30:** Khi lệnh mở không có TP/SL, hệ thống tự động đóng lệnh tại nến cuối date range
- **FR31:** Hệ thống tính P&L có tính commission 0.1% mỗi chiều cho mỗi lệnh. P&L được lock tại thời điểm nhấn Play — drag đường sau khi Play không ảnh hưởng session đang chạy
- **FR32:** Hệ thống giới hạn 1 position mở tại một thời điểm — khi đang có position, Entry hit tiếp theo bị ignore hoàn toàn (không signal, không log)
- **FR33:** Hệ thống hiển thị visual marker trên chart tại điểm entry và exit của mỗi lệnh

### 6. Session Results

- **FR34:** Trader xem danh sách tất cả lệnh trong session: entry price, exit price, loại exit (TP/SL/auto-close), P&L, timestamp nến trigger
- **FR35:** Trader xem tổng kết session: số lệnh thắng, số lệnh thua, tổng P&L %
- **FR36:** Hệ thống cảnh báo khi số lệnh trong session < 30 với 2 mức: warning nhẹ (< 30 lệnh: "sample size chưa đủ tin cậy") và warning mạnh (< 10 lệnh: "kết quả không có ý nghĩa thống kê")
- **FR37:** Hệ thống cung cấp audit trail per lệnh: timestamp nến trigger, giá OHLC tại thời điểm trigger

### 7. Onboarding & Navigation

- **FR38:** Hệ thống hiển thị empty state rõ ràng khi chưa có data, hướng dẫn user fetch data lần đầu
- **FR38b:** Hệ thống hiển thị thông báo rõ ràng khi replay kết thúc với 0 lệnh: "Entry price chưa được chạm trong date range đã chọn — thử mở rộng date range hoặc điều chỉnh vị trí đường Entry"
- **FR39:** Hệ thống hiển thị progress indicator trong quá trình fetch data từ Binance
- **FR40:** Hệ thống hiển thị getting started guide 3 bước cho lần đầu dùng tool
- **FR41:** Hệ thống tự động retry khi fetch data thất bại và thông báo trạng thái cho user

### 8. System Configuration

- **FR42:** Hệ thống có thể cấu hình host, port, cache directory và authentication mode không cần thay đổi source code
- **FR43:** Khi `APP_PASSWORD` được set, hệ thống yêu cầu HTTP Basic Auth trước khi trả về data
- **FR44:** Hệ thống hoạt động hoàn toàn offline sau khi data đã được cache local

## Non-Functional Requirements

### Performance

- **NFR1:** Chart render candlestick data từ local cache trong < 2 giây cho tất cả timeframes
- **NFR2:** Bar replay animation duy trì ≥ 30fps ở tất cả tốc độ trên Chrome và Safari *(Critical)* — Slow: ~500ms/nến, Normal: ~150ms/nến, Fast: ~30ms/nến
- **NFR3:** Indicator calculation (MA, EMA) hiển thị trong < 3 giây sau khi data load
- **NFR4:** API response từ FastAPI backend (OHLCV + indicators từ cache) < 500ms
- **NFR5:** Data fetch lần đầu từ Binance cho 2 năm data hoàn thành trong < 5 phút trên Wifi ổn định
- **NFR6:** Replay engine không block UI thread — user có thể interact với controls trong khi replay đang chạy
- **NFR7:** App sẵn sàng nhận requests trong < 10 giây sau khi chạy lệnh khởi động
- **NFR8:** Hệ thống hoạt động bình thường khi load 5m data 2 năm trên máy có 8GB RAM — không gây Out of Memory

### Security

- **NFR9:** Khi `APP_PASSWORD` được set, tất cả endpoints yêu cầu authentication trước khi trả về data
- **NFR10:** Khi chạy local (`APP_PASSWORD` empty), app chỉ bind trên localhost — không accessible từ external network
- **NFR11:** API keys và credentials không hardcode trong source code — luôn qua environment variables

### Data Integrity *(Highest Priority)*

- **NFR12:** Hệ thống không sử dụng bất kỳ thông tin nào của nến N+1 trở đi khi đang replay tại nến N *(Critical)*
- **NFR13:** Timestamp trong cache luôn store dạng UTC — không phụ thuộc vào system timezone
- **NFR14:** Kết quả P&L phải reproducible — cùng data + cùng strategy → cùng kết quả mỗi lần chạy *(Critical)*
- **NFR15:** Cache data phải được validate (dedup timestamps, sort ascending) trước khi sử dụng
- **NFR16:** Indicators tính incremental — giá trị tại nến N chỉ dùng data [0..N] *(Critical)*
- **NFR17:** Cache load validate data types: timestamp là int64 (Unix ms), OHLCV là float64
- **NFR18:** Commission 0.1% mỗi chiều bắt buộc được tính vào mọi P&L calculation — không có option bỏ qua *(Critical)*

### Integration

- **NFR19:** Hệ thống tự động rate-limit requests, không vượt quá 1200 weight/phút. Khi nhận 429, tự động wait và retry
- **NFR20:** Khi Binance API không khả dụng, fallback sang cached data và thông báo rõ ràng
- **NFR21:** Binance API pagination tự động xử lý — user không cần biết giới hạn 1000 candles/request
- **NFR22:** Cache Parquet files tương thích với pandas trên macOS và Linux

### Reliability

- **NFR23:** Corrupt cache files được tự động detect và xóa — không gây crash app *(Critical)*
- **NFR24:** Lỗi fetch data không crash app — hiển thị error message và cho phép retry
- **NFR25:** App khởi động thành công ngay cả khi chưa có bất kỳ cache data nào *(Critical)*

### Browser Compatibility

- **NFR26:** Chart rendering và drawing tools cho kết quả nhất quán trên Chrome latest và Safari latest — không có sai lệch về giá trị OHLC hiển thị, vị trí drawing lines, màu sắc Entry/TP/SL, hoặc vị trí trade markers
