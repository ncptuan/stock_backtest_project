---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
workflowStatus: complete
completedAt: '2026-04-26'
inputDocuments:
  - 'docs/project-context.md'
  - 'docs/user_database'
workflowType: 'prd'
briefCount: 0
researchCount: 0
brainstormingCount: 0
projectDocsCount: 2
classification:
  projectType: web_app_feature_addition
  domain: fintech_crypto_trading
  complexity: high
  projectContext: brownfield
  exportMode: manual
  signalCasesAutoFill: true
---

# Product Requirements Document — Phase 2: Supabase Integration

**Project:** stock_backtest_project  
**Author:** Narron  
**Date:** 2026-04-26  
**Type:** Brownfield Feature Addition — extends Phase 1 (Visual Bar Replay Tool)

---

## Executive Summary

**stock_backtest_project Phase 2** thêm khả năng export kết quả backtest vào Supabase theo đúng schema của trading bot production (`stock_quant_tracker` trên Koyeb). Người dùng duy nhất: Narron — trader crypto cá nhân.

**Vấn đề:** Sau mỗi backtest session, kiến thức về strategy chỉ tồn tại trong đầu trader. Không có cơ chế transfer kiến thức có cấu trúc vào bot — mỗi insight phải được nhớ thủ công.

**Giải pháp:** Mỗi session đạt chất lượng được "commit" vào Supabase Backtest DB (project riêng, cùng schema với production bot DB). Sau khi review và validate, Narron import thủ công vào production DB — bot nhận case studies mới và cải thiện quyết định.

### What Makes This Special

**Schema contract là differentiator:** Phase 2 export behavioral case studies theo đúng format mà bot đang chờ (`signal_comparisons` + `signal_cases`) — không cần ETL, không cần transformation. Trader và bot dùng cùng ngôn ngữ.

**Knowledge pipeline, không phải export tool:** Mental model: "commit kiến thức vào bot memory." Mỗi session backtest tốt → tập case studies → bot học. Trader improve → bot improve, trong cùng workflow.

**Quality gate built-in:** Hard block khi session không đủ tiêu chuẩn (win rate < 55% hoặc trades < 10) — bot không học từ noise. Learning enforced: Narron phải viết session reasoning trước khi confirm export.

**Learning loop khép kín cho solo trader:** Chuỗi `backtest → validate → commit → bot learns` thường chỉ có ở institutional systems. Phase 2 mang pattern này về personal scale, zero infrastructure overhead.

## Project Classification

| Thuộc tính | Giá trị |
|---|---|
| **Project Type** | Web App — Feature Addition (brownfield) |
| **Domain** | Fintech / Crypto Trading Tools |
| **Complexity** | High (schema contract với production system, dual Supabase isolation) |
| **Target User** | Single user (Narron) — personal tool, không phải SaaS |
| **Export Mode** | Thủ công — nút "Export to Supabase" sau session hoàn chỉnh |
| **Solo Developer** | Narron — scope trimmed aggressively |

## Success Criteria

### User Success

- Narron có thể đọc bất kỳ row nào trong `signal_cases` sau export và confirm: *"Đây là trade tôi hiểu, context đúng, tôi đồng ý với outcome được ghi"*
- Config một lần (`.env`), export flow lặp lại không cần setup lại
- Narron viết session reasoning trước khi confirm — không export data mình chưa hiểu

### Business Success

- Tool hỗ trợ việc học, không bypass — Narron review session summary trước khi commit
- UI neutral về timing: không có countdown, gamification, hoặc pressure để export nhanh
- Sau 3–5 sessions (≥ 10 trades/session), Narron tự tin đủ để import vào production bot (1-tháng milestone của Narron, không phải tool metric)

### Technical Success

- Export ghi đúng và đủ vào cả `signal_comparisons` và `signal_cases`
- `signal_cases` row count = `signal_comparisons` row count cho cùng session
- `signal_id` prefix `backtest_` — không conflict với live signals
- Supabase Backtest DB hoàn toàn isolated khỏi production bot DB trong code

### Measurable Outcomes

| Outcome | Target |
|---|---|
| Export progress | Progress indicator hiển thị — không bao giờ blank screen |
| Error messages | Bao gồm nguyên nhân cụ thể và bước khắc phục |
| Duplicate handling | Fail với message: "Session đã export — xóa trên Supabase trước nếu muốn re-export" |
| Data integrity | `signal_cases` count = `signal_comparisons` count sau mỗi export |

## Product Scope

### MVP (Phase 2)

| Capability | Quyết định |
|---|---|
| Session list UI | Browse Parquet sessions, visual indicator cho sessions đã export |
| Export preview | Per-trade list với summary bar — trade count, win rate, từng trade có reasoning textarea |
| Session reasoning | Per-trade `reasoning_summary` textarea, pre-filled từ backend (EMA values, price) |
| Quality gate | Hard block: win rate ≥ 55% AND trades ≥ 10, no override |
| Atomic export | `signal_comparisons` → `signal_cases` theo thứ tự, rollback nếu fail |
| `market_regime` | Default "unknown" — Narron fill thủ công trên Supabase |
| Event system | `replayStateChanged` + `tradeCompleted` events mới |
| Error handling | Actionable messages, orphan rows acceptable |
| Config | `SUPABASE_ENABLED` flag, graceful degradation |

### Growth (Post-MVP)

- `market_regime` auto-detection từ EMA9/EMA21
- Configurable win-rate threshold
- Session history (list sessions đã export)
- Batch edit reasoning_summary
- Duplicate detection UI

### Vision (Future)

- Reverse direction: import bot live trades vào backtest tool để replay và analyze
- Multi-strategy comparison trong Supabase

## User Journeys

### Journey 1: Happy Path — "Commit kiến thức sau một ngày suy ngẫm"

**Opening Scene:** Sáng thứ Ba, Narron vừa uống cà phê. Tối qua replay 3 tiếng BTC/USDT 4H, 31 trades, win rate 67%. Đã ngủ một giấc — sáng nay anh hiểu rõ pattern của những lệnh loss: entry quá sớm trước khi EMA confirm. Sẵn sàng commit.

**Rising Action:** Narron mở tool, thấy session list — danh sách sessions Parquet local với symbol, timeframe, date, trade count. Chọn session tối qua (không có indicator "đã export" → chưa export lần nào). Bấm "Export to Supabase" — preview hiện ra: summary bar (31 trades, 67% ✅ Pass) + danh sách 31 trades, mỗi trade đã được pre-fill reasoning template từ backend. Narron scroll qua, đọc từng trade — sửa vài cái template trống nghĩa: *"Entry trước EMA confirm — lesson: chờ candle close"*. Scroll đến cuối → Confirm Export button bật sáng.

**Climax:** Spinner — *"Đang ghi vào Supabase..."* Vài giây: *"✅ 31 rows → signal_comparisons | 31 rows → signal_cases"* + link Supabase. Session list cập nhật indicator "đã export". Narron click link verify — data đúng.

**Resolution:** Bookmark session để review lại trước khi import production. Bot không bị ảnh hưởng — Supabase Backtest DB hoàn toàn isolated.

**Capabilities:** Session list UI, export preview (per-trade list + summary bar), per-trade reasoning textarea (pre-filled), scroll gate, atomic export, row count confirmation, Supabase direct link, exported indicator.

---

### Journey 2: Quality Gate — "Tool dạy bài học không cần lời"

**Opening Scene:** Narron thử strategy mới — mean reversion 1H. Session ngắn: 7 trades, 5 win = 71%.

**Rising Action:** Mở export preview → hard block: *"⚠️ Không thể export: 7 trades — cần tối thiểu 10. Win rate 71% trên sample nhỏ không đáng tin cậy."* Không có override button.

**Resolution:** Narron đóng preview, không frustrated. Tuần sau replay dài hơn để có ≥ 15 trades. Tool enforce discipline mà không cần giải thích dài dòng.

**Capabilities:** Hard block quality gate (win rate ≥ 55% AND trades ≥ 10), explanatory message, no override.

---

### Journey 3: Config Error — "Một lần fix, dùng mãi"

**Opening Scene:** Narron setup Supabase Backtest project lần đầu. Copy-paste URL và key vào `.env`. Export lần đầu — fail.

**Rising Action:** *"❌ Authentication failed cho signal_cases (RLS enabled) — Kiểm tra SUPABASE_SERVICE_KEY trong .env. signal_cases yêu cầu service role key, không phải anon key."* Narron sửa key, retry. Atomic export đảm bảo không có partial write từ lần thử đầu.

**Resolution:** Config đúng một lần — không bao giờ xảy ra lại.

**Capabilities:** Actionable error messages, atomic rollback (không partial write khi retry), idempotent export.

---

### Journey 4: Conscious Rejection — "Xem lại và quyết định chưa đủ tốt"

**Opening Scene:** Narron mở session list, chọn session 2 tuần trước — scalp 15m, 12 trades, 58% win rate. Đủ điều kiện export. Nhưng muốn xem lại trước.

**Rising Action:** Mở export preview, đọc summary. Nhớ lại — 5 loss trades đều xảy ra trong cùng market condition. 58% thực chất là 0% edge sau khi filter. Narron đóng preview mà không export.

**Resolution:** Không có áp lực, không có confirm dialog. Tool neutral. Narron note insight và chuẩn bị test lại với filtered condition. Đây là learning thực sự — xảy ra nhiều hơn export thực sự.

**Capabilities:** Session browsing không commit, preview closeable mà không side effect, UI neutral.

---

### Journey Requirements Summary

| Journey | Capabilities cần có |
|---|---|
| Happy path | Session list, export preview (per-trade list + summary bar), per-trade reasoning textarea (pre-filled), scroll gate, atomic export, row count confirm, Supabase link, exported indicator |
| Quality gate | Hard block (win rate ≥ 55% AND trades ≥ 10), no override, explanatory message |
| Config error | Actionable errors, atomic rollback, idempotent retry, Parquet safe |
| Conscious rejection | Session browsing không commit, neutral UI, preview closeable (confirm nếu đã edit) |

## Domain-Specific Requirements

### Data Integrity Constraints

- **Schema contract:** `signal_id` (text), `timestamp` (Unix ms int64), `result` enum ("win"/"loss"/"pending") phải khớp chính xác với production bot schema — type mismatch làm bot đọc sai
- **Timezone:** UTC trong mọi storage/calculation, chỉ convert UTC+7 tại display layer (Project Rule #5)
- **Atomic export:** Partial write vào production bot DB nguy hiểm hơn không có data — correctness requirement, không phải nice-to-have

### Audit & Traceability

- `signal_id` prefix `backtest_` — bot production filter riêng backtest vs live signals
- `created_at` — Supabase auto-fill; rows không được overwrite khi re-import (duplicate detection chặn trước)
- Schema version trong `metadata` JSONB — detect schema drift nếu bot thay đổi schema

### Regulatory

Không có regulatory requirement — personal backtesting tool, không quản lý tiền của người khác.

## Innovation & Novel Patterns

**Schema-first knowledge transfer:** Thay vì export số liệu thống kê (win rate, P&L), Phase 2 export behavioral case studies theo format bot đang chờ — zero ETL, zero transformation.

**Learning loop cho solo trader:** Chuỗi `backtest → validate → commit → bot learns` về personal scale, zero infrastructure overhead.

**Validation:** Sau import, bot trigger signals dựa trên case studies mới. Chất lượng `reasoning_summary` là proxy cho learning quality.

**Risk:** Schema drift — bot thay đổi schema → wrong format → import fail. Mitigate: schema version trong `metadata` JSONB.

## Technical Architecture

### Overview

Feature addition vào SPA hiện tại (TypeScript + esbuild + FastAPI). Không có architectural change — thêm 1 frontend component, 1 backend route, 1 service module, 2 new endpoints.

### Frontend — `ExportPanel.ts`

- Direct fetch call đến backend — không qua EventBus (export là imperative action)
- Explicit state machine: `idle → loading_preview → preview_shown → exporting → success | error`
- `reasoning_summary` per-trade — pre-filled từ backend template (EMA values, price, outcome); auto-save vào `sessionStorage` mỗi 3s; clear khi export complete hoặc session reset
- Scroll gate: `Confirm Export` disabled cho đến khi trade cuối cùng visible trong viewport (`IntersectionObserver`)
- Export button enable khi `replayStateChanged.state === 'stopped'` VÀ `SUPABASE_ENABLED=true`

### Backend — `routes/export.py` + `services/supabase.py`

- `httpx` trực tiếp (không `supabase-py`) — ít deps, dễ trace errors
- 2 functions: `write_signal_comparisons(trades)`, `write_signal_cases(trades)` — YAGNI, không cần class
- `POST /api/export` return 503 nếu `SUPABASE_ENABLED=false`
- Atomic rollback: nếu `signal_cases` fail → `DELETE FROM signal_comparisons WHERE signal_id LIKE 'backtest_{session_id}_%'`

### Session List — `GET /api/sessions`

- Parse metadata từ Parquet filename (`{symbol}_{timeframe}_{date}.parquet`) — không đọc file content
- Return `[]` nếu `cache/` trống, không 404; skip corrupt files

### API Contract

**`GET /api/sessions`**
```json
[{
  "filename": "BTCUSDT_4h_20260420.parquet",
  "symbol": "BTCUSDT",
  "timeframe": "4h",
  "date": "2026-04-20",
  "exported": false
}]
```

**`GET /api/sessions/{filename}/preview`** *(mới — FR6, FR26, FR34)*
```json
{
  "symbol": "BTCUSDT",
  "timeframe": "4h",
  "date": "2026-04-20",
  "trade_count": 31,
  "win_rate": 0.67,
  "quality_gate": "pass",
  "trades": [{
    "bar_index": 42,
    "entry_timestamp_ms": 1745625600000,
    "direction": "LONG",
    "entry_price": 43250.0,
    "tp_price": 44000.0,
    "sl_price": 42800.0,
    "result": "win",
    "bars_to_exit": 7,
    "reasoning_template": "4H | Entry $43,250 | EMA20=$42,100 | EMA50=$41,800 | Vol=1.8x | Outcome: WIN"
  }]
}
```

**`POST /api/export` Request**
```json
{
  "session_filename": "BTCUSDT_4h_20260420.parquet",
  "strategy_name": "breakout_4h",
  "timeframe": "4h",
  "session_win_rate": 0.67,
  "trades": [{
    "bar_index": 42,
    "entry_timestamp_ms": 1745625600000,
    "direction": "LONG",
    "entry_price": 43250.0,
    "tp_price": 44000.0,
    "sl_price": 42800.0,
    "result": "win",
    "bars_to_exit": 7,
    "reasoning_summary": "4H | Entry $43,250 | EMA20=$42,100 | EMA50=$41,800 | Vol=1.8x | Outcome: WIN"
  }]
}
```

**`POST /api/export` Response**
```json
// Success
{
  "signal_comparisons_count": 31,
  "signal_cases_count": 31,
  "first_signal_id": "backtest_20260426_breakout_4h_00042",
  "supabase_url": "https://xxx.supabase.co/..."
}
// Error
{
  "error": "quality_gate|duplicate|auth_failed|partial_write_rolled_back",
  "message": "...actionable instruction..."
}
```

**Backend-generated fields** (không cần frontend pass):
- `signal_id`: `backtest_{yyyymmdd}_{strategy_name}_{bar_index:05d}`
- `market_regime`: default `"unknown"` (Growth: detect từ EMA9/EMA21)
- `invalidation_condition`: `"SL tại {sl_price}"`
- `bot_verdict` / `claude_action`: map từ `direction`
- `signal_sent_at`: convert từ `entry_timestamp_ms`

### EventBus Changes (types.ts)

```typescript
replayStateChanged: { state: 'playing' | 'paused' | 'stopped' }
tradeCompleted: {
  bar_index: number
  entry_timestamp_ms: number
  direction: 'LONG' | 'SHORT'
  entry_price: number
  tp_price: number
  sl_price: number
  result: 'win' | 'loss'
  bars_to_exit: number
}
```

ExportPanel listeners: `replayStateChanged` → enable/disable button; `tradeCompleted` → accumulate trades array; `replayReset` → clear trades array.

### UI Additions

- Strategy name input: text field, default `"{symbol}_{timeframe}"`, editable
- ExportPreview: per-trade list, mỗi trade có `reasoning_summary` textarea (pre-filled từ backend template, editable, maxlength 500)
- Scroll progress indicator: "Đã xem N/M trades" — `Confirm Export` disabled cho đến khi trade cuối visible
- Session list: visual indicator "✓ exported" cho sessions đã export

### Failure Handling

| Scenario | Behavior |
|---|---|
| Parquet file bị xóa sau khi chọn | Backend 404 → frontend error rõ |
| Supabase suspended (free tier idle) | Timeout → "Supabase đang wake up, thử lại sau 30 giây" |
| `SUPABASE_ENABLED=false` | Return 503 với hướng dẫn enable |
| Export fail giữa chừng | Atomic rollback: DELETE signal_comparisons rows của session |
| Session list có file corrupt | Skip + log, không crash list |
| Export triggered khi replay đang playing | Button disabled — không thể trigger |

## Project Scoping & Phased Development

### MVP Strategy

**Approach:** Problem-solving MVP — giải quyết đúng 1 pain point: đưa backtest knowledge vào bot memory không có friction. Trim aggressively cho solo developer.

**True MVP core:** `tradeCompleted` event + quality gate + atomic export → Supabase + basic UI.

### Risk Mitigation

| Risk | Mitigation |
|---|---|
| `replayStateChanged` regression vào Phase 1 | Verify EventMap + test Phase 1 flows sau khi add event |
| `tradeCompleted` duplicate events | 1 event per closed trade (exit hit), full data |
| `bars_to_exit` off-by-one | Explicit pytest test case |
| Orphan rows nếu rollback fail | Acceptable — error message hướng dẫn manual cleanup |
| Schema drift | Schema version trong `metadata` JSONB |

## Functional Requirements

### Session Management

- **FR1:** Narron có thể xem danh sách backtest sessions đã lưu trong local cache
- **FR2:** Narron có thể load session từ danh sách để chuẩn bị export
- **FR3:** Hệ thống thông báo khi session được chọn không còn tồn tại trong cache
- **FR33:** Session list hiển thị visual indicator cho sessions đã export *(CRITICAL — prevent duplicate)*

### Export Readiness

- **FR4:** Export disabled khi replay đang playing — enabled khi stopped hoặc session có trades từ previous replay
- **FR5:** Export chỉ available khi `SUPABASE_ENABLED=true` trong config
- **FR6:** Narron xem tóm tắt session trước export: tổng trades, win rate, quality gate result (pass/fail)
- **FR7:** Narron đặt tên strategy cho session trước export (default: `{symbol}_{timeframe}`)
- **FR8:** Narron review và edit `reasoning_summary` per-trade trong ExportPreview — mỗi trade có 1 textarea riêng, pre-filled từ backend template
- **FR9:** Narron đóng export preview — nếu đã edit bất kỳ textarea nào thì có confirm dialog; nếu chưa edit thì đóng ngay không confirm
- **FR35:** Draft `reasoning_summary` per-trade được auto-save vào `sessionStorage` mỗi 3s — tránh mất edit nếu đóng nhầm; bị xóa khi export thành công hoặc session reset
- **FR36:** `Confirm Export` button bị disable cho đến khi Narron scroll đến trade cuối cùng (`IntersectionObserver`) — enforce review toàn bộ danh sách

### Quality Gate

- **FR10:** Export bị từ chối nếu trade count < 10 *(CRITICAL)*
- **FR11:** Export bị từ chối nếu win rate < 55% *(CRITICAL)*
- **FR12:** Lý do từ chối được hiển thị cụ thể

### Export Execution

- **FR13:** Narron khởi động export session vào Supabase Backtest DB
- **FR14:** Hệ thống ghi vào `signal_comparisons` theo đúng bot schema
- **FR15:** Hệ thống ghi vào `signal_cases` theo đúng bot schema
- **FR16:** Atomic: nếu `signal_cases` fail → rollback `signal_comparisons` *(CRITICAL)*
- **FR17:** Duplicate export bị từ chối dựa trên session filename *(CRITICAL)*
- **FR18:** Narron nhận xác nhận thành công: row counts + Supabase link

### Error Handling & Recovery

- **FR19:** Progress indicator hiển thị trong khi ghi Supabase
- **FR20:** Thông báo lỗi bao gồm nguyên nhân cụ thể và bước khắc phục
- **FR21:** Narron retry export sau khi sửa lỗi mà không cần restart session
- **FR22:** Export fail không ảnh hưởng đến Parquet local cache

### Data Integrity

- **FR23:** `signal_id` unique với prefix `backtest_` cho mỗi trade *(CRITICAL)*
- **FR24:** Outcome map đúng từ replay (TP/SL hit) → bot format (win/loss, TP hit/SL hit)
- **FR25:** Entry timestamp ghi theo Unix milliseconds UTC
- **FR26:** Mỗi trade trong ExportPreview có `reasoning_summary` textarea pre-filled với template per-trade: `{timeframe} | Entry {entry_price} | EMA20={val} | EMA50={val} | Vol={ratio}x | Outcome: {WIN/LOSS}` — giá trị lấy tại candle *trước* entry (slice-first, no look-ahead)
- **FR34:** Backend đọc Parquet để lấy EMA20, EMA50, volume tại `bar_index - 1` cho từng trade; gửi pre-fill templates về cùng với `GET /api/sessions/{filename}/preview` response

### Configuration

- **FR27:** Narron bật/tắt Supabase integration qua environment config
- **FR28:** Phase 1 features hoạt động bình thường khi Supabase disabled
- **FR29:** Supabase credentials được validate khi khởi động export, lỗi rõ nếu sai

### Event System & State Tracking

- **FR30:** Trạng thái replay hiện tại (playing/paused/stopped) được expose cho các components khác
- **FR31:** Trade completion tracking — dữ liệu trade đầy đủ available cho export
- **FR32:** Trades array reset khi session mới bắt đầu *(CRITICAL)*

## Non-Functional Requirements

### Performance

- **NFR1** *(Medium):* Session list load < 200ms (filename parse only, local machine)
- **NFR2** *(Medium):* Export preview render < 500ms cho session ≤ 200 trades (bao gồm backend fetch reasoning templates)
- **NFR3** *(Medium):* UI feedback < 100ms cho mọi user action trong export flow
- **NFR4** *(Medium):* Supabase write chạy async — UI không block trong khi ghi

### Security

- **NFR5** *(Critical):* Supabase credentials chỉ load từ env vars — không hardcode, không commit vào git
- **NFR6** *(Medium):* `SUPABASE_SERVICE_KEY` chỉ dùng cho POST tới `signal_cases` — anon key cho mọi operation khác
- **NFR7** *(Low — Koyeb only):* `/api/export` yêu cầu authentication nếu deployed lên Koyeb

### Integration

- **NFR8** *(Critical):* Type mismatch giữa export payload và Supabase schema phải bị catch và report trước khi bất kỳ row nào được ghi
- **NFR9** *(High):* `signal_id` unique trong Supabase Backtest DB, không conflict với live signal IDs
- **NFR10** *(High):* Tất cả `timestamp` fields là Unix milliseconds int64 — consistent với ADR-03
- **NFR11** *(Critical):* Supabase Backtest DB và Production Bot DB là hai projects riêng biệt — không có connection chéo trong code

### Reliability & Data Correctness

- **NFR12** *(Critical):* Mỗi export atomic — không partial state sau khi hoàn tất (success hoặc fully rolled back)
- **NFR13** *(Critical):* Outcome mapping 100% accurate — `result` khớp chính xác với TP/SL hit detection của ReplayEngine
- **NFR14** *(High):* Export fail không corrupt hoặc modify Parquet local cache
- **NFR15** *(High):* `signal_cases` row count = `signal_comparisons` row count cho cùng session sau mỗi export

### Maintainability & Operability

- **NFR16** *(Medium):* Supabase integration code isolated trong `services/supabase.py`
- **NFR17** *(Medium):* Backend log Supabase operations ở info level, failures ở error level với rollback status
- **NFR18** *(Low):* `.env.example` document đủ tất cả Supabase env vars cần thiết

### Testability

- **NFR19** *(Medium):* Quality gate logic, signal_id generation, outcome mapping, reasoning template generation có pytest unit tests — không cần Supabase connection
