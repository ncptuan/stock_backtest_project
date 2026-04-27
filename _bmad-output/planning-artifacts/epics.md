---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
workflowStatus: complete
completedAt: '2026-04-26'
inputDocuments:
  - '_bmad-output/planning-artifacts/prd-phase2-supabase.md'
  - '_bmad-output/planning-artifacts/architecture.md'
  - '_bmad-output/planning-artifacts/ux-design-specification.md'
---

# stock_backtest_project Phase 2 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for stock_backtest_project Phase 2 (Supabase Integration), decomposing the requirements from the PRD Phase 2, UX Design Addendum, and Architecture into implementable stories.

**Context:** Brownfield feature addition — Phase 1 (Visual Bar Replay Tool) is complete and running. Phase 2 adds Supabase export capability without breaking Phase 1 flows.

## Requirements Inventory

### Functional Requirements

FR1: Narron có thể xem danh sách backtest sessions đã lưu trong local cache
FR2: Narron có thể load session từ danh sách để chuẩn bị export
FR3: Hệ thống thông báo khi session được chọn không còn tồn tại trong cache
FR4: Export disabled khi replay đang playing — enabled khi stopped hoặc session có trades từ previous replay
FR5: Export chỉ available khi SUPABASE_ENABLED=true trong config
FR6: Narron xem tóm tắt session trước export: tổng trades, win rate, quality gate result (pass/fail)
FR7: Narron đặt tên strategy cho session trước export (default: {symbol}_{timeframe})
FR8: Narron review và edit reasoning_summary per-trade trong ExportPreview — mỗi trade có 1 textarea riêng, pre-filled từ backend template
FR9: Narron đóng export preview — nếu đã edit bất kỳ textarea nào thì có confirm dialog; nếu chưa edit thì đóng ngay không confirm
FR10: Export bị từ chối nếu trade count < 10 (CRITICAL)
FR11: Export bị từ chối nếu win rate < 55% (CRITICAL)
FR12: Lý do từ chối được hiển thị cụ thể
FR13: Narron khởi động export session vào Supabase Backtest DB
FR14: Hệ thống ghi vào signal_comparisons theo đúng bot schema
FR15: Hệ thống ghi vào signal_cases theo đúng bot schema
FR16: Atomic: nếu signal_cases fail → rollback signal_comparisons (CRITICAL)
FR17: Duplicate export bị từ chối dựa trên session filename (CRITICAL)
FR18: Narron nhận xác nhận thành công: row counts + Supabase link
FR19: Progress indicator hiển thị trong khi ghi Supabase
FR20: Thông báo lỗi bao gồm nguyên nhân cụ thể và bước khắc phục
FR21: Narron retry export sau khi sửa lỗi mà không cần restart session
FR22: Export fail không ảnh hưởng đến Parquet local cache
FR23: signal_id unique với prefix backtest_ cho mỗi trade (CRITICAL)
FR24: Outcome map đúng từ replay (TP/SL hit) → bot format (win/loss, TP hit/SL hit)
FR25: Entry timestamp ghi theo Unix milliseconds UTC
FR26: Mỗi trade trong ExportPreview có reasoning_summary textarea pre-filled với template per-trade — giá trị lấy tại candle trước entry (slice-first, no look-ahead)
FR27: Narron bật/tắt Supabase integration qua environment config
FR28: Phase 1 features hoạt động bình thường khi Supabase disabled
FR29: Supabase credentials được validate khi khởi động export, lỗi rõ nếu sai
FR30: Trạng thái replay hiện tại (playing/paused/stopped) được expose cho các components khác
FR31: Trade completion tracking — dữ liệu trade đầy đủ available cho export
FR32: Trades array reset khi session mới bắt đầu (CRITICAL)
FR33: Session list hiển thị visual indicator cho sessions đã export (CRITICAL — prevent duplicate)
FR34: Backend đọc Parquet để lấy EMA20, EMA50, volume tại bar_index - 1 cho từng trade; gửi pre-fill templates về cùng GET /api/sessions/{filename}/preview response
FR35: Draft reasoning_summary per-trade được auto-save vào sessionStorage mỗi 3s — bị xóa khi export thành công hoặc session reset
FR36: Confirm Export button bị disable cho đến khi Narron scroll đến trade cuối cùng (IntersectionObserver) — enforce review toàn bộ danh sách

**Total FRs: 36**

### NonFunctional Requirements

NFR1 (Medium): Session list load < 200ms (filename parse only, local machine)
NFR2 (Medium): Export preview render < 500ms cho session ≤ 200 trades (bao gồm backend fetch reasoning templates)
NFR3 (Medium): UI feedback < 100ms cho mọi user action trong export flow
NFR4 (Medium): Supabase write chạy async — UI không block trong khi ghi
NFR5 (Critical): Supabase credentials chỉ load từ env vars — không hardcode, không commit vào git
NFR6 (Medium): SUPABASE_SERVICE_KEY chỉ dùng cho POST tới signal_cases — anon key cho mọi operation khác
NFR7 (Low — Koyeb only): /api/export yêu cầu authentication nếu deployed lên Koyeb
NFR8 (Critical): Type mismatch giữa export payload và Supabase schema phải bị catch và report trước khi bất kỳ row nào được ghi
NFR9 (High): signal_id unique trong Supabase Backtest DB, không conflict với live signal IDs
NFR10 (High): Tất cả timestamp fields là Unix milliseconds int64 — consistent với ADR-03
NFR11 (Critical): Supabase Backtest DB và Production Bot DB là hai projects riêng biệt — không có connection chéo trong code
NFR12 (Critical): Mỗi export atomic — không partial state sau khi hoàn tất (success hoặc fully rolled back)
NFR13 (Critical): Outcome mapping 100% accurate — result khớp chính xác với TP/SL hit detection của ReplayEngine
NFR14 (High): Export fail không corrupt hoặc modify Parquet local cache
NFR15 (High): signal_cases row count = signal_comparisons row count cho cùng session sau mỗi export
NFR16 (Medium): Supabase integration code isolated trong services/supabase.py
NFR17 (Medium): Backend log Supabase operations ở info level, failures ở error level với rollback status
NFR18 (Low): .env.example document đủ tất cả Supabase env vars cần thiết
NFR19 (Medium): Quality gate logic, signal_id generation, outcome mapping, reasoning template generation có pytest unit tests — không cần Supabase connection

**Total NFRs: 19**

### Additional Requirements

**Từ Architecture.md (Phase 1 — áp dụng cho Phase 2):**
- ADR-03: timestamp int64 Unix ms — schema contract bắt buộc với Supabase
- ADR-01: EventBus singleton pattern — Phase 2 events phải dùng cùng EventBus
- ADR-07: pandas built-in `ewm()` + `rolling().mean()` cho EMA/MA — dùng cho FR34 reasoning templates
- Gap-1: Slice DataFrame trước khi compute indicators — FR34 phải dùng `df.iloc[:bar_index]` trước EMA compute
- Brownfield: Phase 1 code không được break — `replayStateChanged` event thêm phải backward-compatible

**Từ PRD Phase 2 Technical Architecture:**
- httpx trực tiếp (không supabase-py) — ít deps, dễ trace errors
- 2 functions: `write_signal_comparisons(trades)`, `write_signal_cases(trades)` — YAGNI
- Atomic rollback: DELETE signal_comparisons WHERE signal_id LIKE 'backtest_{session_id}_%'
- signal_id format: `backtest_{yyyymmdd}_{strategy_name}_{bar_index:05d}`
- market_regime: hardcoded "unknown" trong MVP
- GET /api/sessions: parse filename only — không đọc file content
- GET /api/sessions/{filename}/preview: đọc Parquet, compute EMA templates, trả về trade list + reasoning_template per trade

### UX Design Requirements

**Từ UX Design Specification Phase 2 Addendum:**

UX-DR1: CompletionOverlay Phase 1 cần thêm button "📤 Lưu vào Supabase" — chỉ render nếu SUPABASE_ENABLED=true; click → dismiss overlay → mở SessionListPanel
UX-DR2: StatusBar (Complete mode) thêm secondary "Export" link bên phải — fallback entry point sau khi CompletionOverlay dismiss
UX-DR3: SessionListPanel component — modal 680px × 80vh, scrollable session list, mỗi session row hiển thị symbol + timeframe + date + trades + win rate badge + Export/Re-export button
UX-DR4: Session row states: eligible (green badge), blocked-winrate (yellow ⚠️), blocked-quality (red ⚠️), already-exported (gray "Đã export {date}")
UX-DR5: ExportPreview component — full-screen overlay; per-trade list; summary bar sticky top (trades count, win rate, quality gate); scroll progress "Đã xem N/M trades"; Confirm Export disabled cho đến khi trade cuối visible
UX-DR6: Per-trade reasoning_summary textarea trong ExportPreview — pre-filled, 2 rows expandable tới 5, maxlength 500, character counter khi focus, Tab navigation giữa các textareas
UX-DR7: ExportPreview close behavior — confirm dialog nếu đã edit bất kỳ textarea; đóng ngay nếu chưa edit
UX-DR8: QualityGateBlock component — modal 480px, icon ⚠️, lý do cụ thể (trade count / win rate), không có override button
UX-DR9: ExportProgressOverlay component — 3 states: In Progress (spinner + step-by-step progress text realtime), Success (row counts + Supabase link + Reset Replay button), Error (actionable message + collapsible raw error + Thử lại button)
UX-DR10: Rollback feedback trong ExportProgressOverlay — nếu signal_cases fail → "Đã rollback signal_comparisons (0/31 được giữ lại)"
UX-DR11: SessionListPanel "already-exported" tracking — dùng localStorage để track ngày export; "Re-export" button thay vì "Export"
UX-DR12: Accessibility cho tất cả Phase 2 modals: role="dialog"/role="alertdialog", aria-modal="true", focus trap, Escape để dismiss
UX-DR13: strategy name input field trong ExportPreview — text input, default "{symbol}_{timeframe}", editable trước khi confirm

**Total UX-DRs: 13**

### FR Coverage Map

FR1: Epic 1 — Session list UI
FR2: Epic 1 — Load session từ list
FR3: Epic 1 — Thông báo session không tồn tại
FR4: Epic 1 — Export disabled khi playing
FR5: Epic 1 — Export khi SUPABASE_ENABLED=true
FR6: Epic 2 — Preview summary (trades, win rate)
FR7: Epic 2 — Strategy name input
FR8: Epic 2 — Per-trade reasoning textarea
FR9: Epic 2 — Close preview behavior
FR10: Epic 2 — Quality gate: trades < 10 block
FR11: Epic 2 — Quality gate: win rate < 55% block
FR12: Epic 2 — Rejection reason displayed
FR13: Epic 3 — Trigger export
FR14: Epic 3 — Write signal_comparisons
FR15: Epic 3 — Write signal_cases
FR16: Epic 3 — Atomic rollback on fail
FR17: Epic 3 — Duplicate detection by filename
FR18: Epic 3 — Success: row counts + link
FR19: Epic 3 — Progress indicator
FR20: Epic 3 — Actionable error messages
FR21: Epic 3 — Retry without restart
FR22: Epic 3 — Parquet unaffected on fail
FR23: Epic 4 — signal_id unique backtest_ prefix
FR24: Epic 4 — Outcome mapping TP/SL → win/loss
FR25: Epic 4 — Unix ms UTC timestamps
FR26: Epic 4 — Per-trade reasoning template
FR27: Epic 1 — SUPABASE_ENABLED config
FR28: Epic 1 — Phase 1 unaffected when disabled
FR29: Epic 4 — Credentials validated on export
FR30: Epic 1 — replayStateChanged event
FR31: Epic 1 — tradeCompleted event
FR32: Epic 1 — Trades array reset
FR33: Epic 1 — "Đã export" visual indicator
FR34: Epic 4 — Backend Parquet → EMA templates
FR35: Epic 2 — sessionStorage auto-save draft
FR36: Epic 2 — Scroll gate — Confirm disabled

## Epic List

### Epic 1: Xem và chọn session để export
Narron có thể browse danh sách sessions Parquet local, thấy ngay session nào đủ điều kiện, và chọn session để bắt đầu export flow — mà không cần nhớ tên file hay biết Parquet là gì. Bao gồm cả việc expose replay state qua EventBus để ExportPanel có thể react.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR27, FR28, FR30, FR31, FR32, FR33
**UX-DRs covered:** UX-DR1, UX-DR2, UX-DR3, UX-DR4, UX-DR11

### Epic 2: Review trades và confirm trước khi commit
Narron có thể xem chi tiết từng trade trong session, đọc và edit reasoning per-trade (pre-filled từ template), và chỉ confirm export sau khi đã scroll qua toàn bộ danh sách. Quality gate enforced — không export data mình chưa hiểu.
**FRs covered:** FR6, FR7, FR8, FR9, FR10, FR11, FR12, FR35, FR36
**UX-DRs covered:** UX-DR5, UX-DR6, UX-DR7, UX-DR8, UX-DR13

### Epic 3: Ghi kết quả vào Supabase và xác nhận
Narron có thể thực sự ghi session đã review vào Supabase Backtest DB — với progress feedback realtime, atomic rollback nếu fail, và link Supabase để verify ngay sau khi xong.
**FRs covered:** FR13, FR14, FR15, FR16, FR17, FR18, FR19, FR20, FR21, FR22
**UX-DRs covered:** UX-DR9, UX-DR10, UX-DR12

### Epic 4: Data integrity — bot nhận đúng data để học
Mỗi row ghi vào Supabase phải đúng schema của production bot — signal_id format, timestamp Unix ms, outcome mapping chính xác, reasoning template có context EMA/volume từ candle trước entry. Có pytest coverage cho critical paths.
**FRs covered:** FR23, FR24, FR25, FR26, FR29, FR34
**NFRs covered:** NFR5, NFR6, NFR8, NFR9, NFR10, NFR11, NFR12, NFR13, NFR15, NFR16, NFR17, NFR18, NFR19

---

## Epic 1: Xem và chọn session để export

Narron có thể browse danh sách sessions Parquet local, thấy ngay session nào đủ điều kiện, và chọn session để bắt đầu export flow — mà không cần nhớ tên file hay biết Parquet là gì. Bao gồm cả việc expose replay state và trade data qua EventBus để ExportPanel có thể react.

### Story 1.1: Thêm Supabase config vào backend settings

As a developer,
I want Supabase credentials và SUPABASE_ENABLED flag được load từ env vars qua Pydantic Settings,
So that toàn bộ Phase 2 features có thể bật/tắt bằng 1 flag mà không ảnh hưởng Phase 1.

**Acceptance Criteria:**

**Given** file `.env` có `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ENABLED=false`
**When** FastAPI server khởi động
**Then** `Settings` object có đủ 4 fields mới, không raise validation error

**Given** `SUPABASE_ENABLED=false` trong `.env`
**When** bất kỳ Phase 1 feature nào được dùng (fetch OHLCV, replay, draw)
**Then** Phase 1 hoạt động bình thường — không có bất kỳ error hay warning nào liên quan Supabase

**Given** `SUPABASE_ENABLED=true` nhưng `SUPABASE_URL` bị bỏ trống
**When** FastAPI server khởi động
**Then** server raise `ValidationError` với message rõ ràng chỉ ra field nào bị thiếu

**Given** `.env.example` trong repo
**When** developer xem file này
**Then** thấy đủ 4 env vars mới với comment giải thích từng field (URL, anon key, service key, enabled flag)

---

### Story 1.2: EventBus — replayStateChanged và tradeCompleted events

As a trader,
I want trạng thái replay và data từng trade completed được expose qua EventBus,
So that ExportPanel có thể biết khi nào replay stopped và có đủ trade data để chuẩn bị export.

**Acceptance Criteria:**

**Given** `types.ts` EventMap interface
**When** developer thêm 2 events mới
**Then** TypeScript compile không có error: `replayStateChanged: { state: 'playing' | 'paused' | 'stopped' }` và `tradeCompleted: { bar_index: number; entry_timestamp_ms: number; direction: 'LONG' | 'SHORT'; entry_price: number; tp_price: number; sl_price: number; result: 'win' | 'loss'; bars_to_exit: number }`

**Given** replay đang chạy và một trade hit (TP hoặc SL chạm)
**When** ReplayEngine detect hit
**Then** EventBus emit `tradeCompleted` với đầy đủ 8 fields — đúng 1 lần duy nhất per closed trade, không emit duplicate

**Given** Narron nhấn Play
**When** replay bắt đầu
**Then** EventBus emit `replayStateChanged` với `state: 'playing'`

**Given** Narron nhấn Stop hoặc replay hoàn thành hết bars
**When** replay dừng
**Then** EventBus emit `replayStateChanged` với `state: 'stopped'`

**Given** Narron nhấn Reset
**When** session reset
**Then** EventBus emit `replayStateChanged` với `state: 'stopped'` — toàn bộ Phase 1 flows (ResultsPanel, DrawingManager) vẫn hoạt động bình thường như trước khi thêm event

---

### Story 1.3: GET /api/sessions — danh sách Parquet sessions

As a trader,
I want backend trả về danh sách sessions Parquet trong local cache,
So that frontend có thể hiển thị sessions mà không cần Narron tự tìm file trong filesystem.

**Acceptance Criteria:**

**Given** thư mục `cache/` chứa files `BTCUSDT_4h_20260420.parquet` và `ETHUSDT_1h_20260415.parquet`
**When** `GET /api/sessions` được gọi
**Then** trả về array 2 objects: `[{"filename": "BTCUSDT_4h_20260420.parquet", "symbol": "BTCUSDT", "timeframe": "4h", "date": "2026-04-20", "exported": false}, ...]`

**Given** thư mục `cache/` trống hoặc không tồn tại
**When** `GET /api/sessions` được gọi
**Then** trả về `[]` với HTTP 200 — không phải 404

**Given** thư mục `cache/` chứa file tên không match pattern `{SYMBOL}_{timeframe}_{date}.parquet`
**When** `GET /api/sessions` được gọi
**Then** file đó bị skip — không crash endpoint, không xuất hiện trong response

**Given** `SUPABASE_ENABLED=false`
**When** `GET /api/sessions` được gọi
**Then** endpoint vẫn hoạt động bình thường và trả về session list (endpoint không phụ thuộc vào Supabase flag)

**Given** `exported` field trong response
**When** một session chưa từng export
**Then** `exported: false` — logic track `exported` state sẽ được implement ở story sau (hiện tại hardcode false)

---

### Story 1.4: SessionListPanel — UI browse và chọn session

As a trader,
I want xem danh sách sessions trong một panel và chọn session để bắt đầu export flow,
So that tôi có thể tìm đúng session muốn export mà không cần nhớ tên file.

**Acceptance Criteria:**

**Given** Narron vừa hoàn thành replay (CompletionOverlay hiển thị) và `SUPABASE_ENABLED=true`
**When** CompletionOverlay render
**Then** button "📤 Lưu vào Supabase" xuất hiện cạnh nút Reset

**Given** `SUPABASE_ENABLED=false`
**When** CompletionOverlay render
**Then** button "📤 Lưu vào Supabase" không hiển thị — Phase 1 UI giữ nguyên

**Given** Narron click "📤 Lưu vào Supabase" trong CompletionOverlay
**When** click event
**Then** CompletionOverlay dismiss ngay lập tức → SessionListPanel mở với danh sách sessions từ `GET /api/sessions`

**Given** SessionListPanel mở
**When** sessions đang load từ API
**Then** skeleton loader hiển thị — không blank screen

**Given** SessionListPanel có sessions
**When** Narron nhìn vào mỗi session row
**Then** thấy: symbol, timeframe, date, và "Export" button (hoặc trạng thái "Đã export {date}" nếu đã export)

**Given** Narron nhấn Escape hoặc click nút Đóng trong SessionListPanel
**When** close action
**Then** SessionListPanel đóng lại — không có side effect, không trigger export

**Given** StatusBar ở Complete mode và `SUPABASE_ENABLED=true`
**When** CompletionOverlay đã dismiss
**Then** StatusBar hiển thị secondary "Export" link text bên phải — click mở lại SessionListPanel

**Given** SessionListPanel
**When** mở lần đầu sau khi Narron vừa replay xong session X
**Then** session X được highlight là session hiện tại


---

## Epic 2: Review trades và confirm trước khi commit

Narron có thể xem chi tiết từng trade trong session, đọc và edit reasoning per-trade (pre-filled từ backend template), và chỉ confirm export sau khi đã scroll qua toàn bộ danh sách. Quality gate enforced — không export data mình chưa hiểu.

### Story 2.1: GET /api/sessions/{filename}/preview — trade list với reasoning templates

As a trader,
I want backend trả về danh sách trades của session với reasoning template được pre-fill từ EMA/volume data,
So that ExportPreview có thể hiển thị context indicator cho từng trade mà không cần tôi nhập thủ công.

**Acceptance Criteria:**

**Given** file `BTCUSDT_4h_20260420.parquet` tồn tại trong `cache/` và có trade data (accumulated từ replay qua EventBus)
**When** `GET /api/sessions/BTCUSDT_4h_20260420.parquet/preview` được gọi với trade list trong request body
**Then** trả về `trade_count`, `win_rate`, `quality_gate` ("pass"/"fail") và array `trades` với `reasoning_template` per trade

**Given** trade tại `bar_index=42` (entry candle)
**When** backend compute reasoning template
**Then** EMA20, EMA50, volume được lấy tại `df.iloc[41]` (bar_index - 1, slice-first — không look-ahead), format: `"4H | Entry $43,250 | EMA20=$42,100 | EMA50=$41,800 | Vol=1.8x | Outcome: WIN"`

**Given** file Parquet được chỉ định không tồn tại trong `cache/`
**When** `GET /api/sessions/{filename}/preview` được gọi
**Then** HTTP 404 với message: "Session file không tồn tại — có thể đã bị xóa"

**Given** session có 7 trades với win rate 71%
**When** preview response
**Then** `quality_gate: "fail"` với `quality_gate_reason: "7 trades — cần tối thiểu 10"` — mặc dù win rate pass

**Given** session có 15 trades với win rate 48%
**When** preview response
**Then** `quality_gate: "fail"` với `quality_gate_reason: "48% win rate — cần tối thiểu 55%"` — mặc dù trade count pass

---

### Story 2.2: ExportPreview component — per-trade list với scroll gate

As a trader,
I want xem toàn bộ danh sách trades trong ExportPreview và phải scroll đến cuối trước khi có thể confirm,
So that tôi không vô tình commit data mình chưa review.

**Acceptance Criteria:**

**Given** Narron click "Export" button trên một session row trong SessionListPanel
**When** ExportPreview mở
**Then** full-screen overlay hiển thị với: summary bar sticky top (trade count, win rate, quality gate status) + scrollable trade list + strategy name input (default: `{symbol}_{timeframe}`) + scroll progress "Đã xem 0/N trades"

**Given** ExportPreview vừa mở với 31 trades
**When** Narron chưa scroll
**Then** "Confirm Export" button có `aria-disabled="true"` và không clickable — không thể bypass

**Given** Narron scroll đến trade cuối cùng (IntersectionObserver detect row cuối visible)
**When** trade cuối visible trong viewport
**Then** "Confirm Export" button enable với brief glow animation 1 lần + scroll progress update thành "Đã xem 31/31 trades"

**Given** session bị quality gate fail (trade count < 10 hoặc win rate < 55%)
**When** Narron click "Export" trên session row đó
**Then** QualityGateBlock modal mở (không phải ExportPreview) — hiển thị lý do cụ thể, không có override button

**Given** ExportPreview đang hiển thị
**When** Narron nhấn ✕ hoặc Escape
**Then** nếu chưa edit bất kỳ textarea nào → đóng ngay, không confirm dialog; nếu đã edit → confirm dialog "Đóng preview? Draft đã lưu — có thể tiếp tục sau"

---

### Story 2.3: Per-trade reasoning_summary textarea với auto-save

As a trader,
I want mỗi trade có textarea reasoning được pre-fill sẵn và tự động save draft khi tôi edit,
So that tôi có thể customize context cho từng trade mà không sợ mất công nếu lỡ đóng preview.

**Acceptance Criteria:**

**Given** ExportPreview render với 31 trades
**When** trade list hiển thị
**Then** mỗi trade row có 1 textarea với: pre-filled template từ backend (`reasoning_template`), 2 rows mặc định, maxlength 500, placeholder text nếu template trống

**Given** Narron click vào textarea của trade #5
**When** focus event
**Then** textarea expand từ 2 → 5 rows + character counter xuất hiện "87/500"

**Given** Narron dùng Tab key trong ExportPreview
**When** Tab press
**Then** focus nhảy sang textarea của trade tiếp theo — keyboard navigation qua toàn bộ trade list

**Given** Narron đã edit textarea của trade #3 (đã 3+ giây trôi qua)
**When** auto-save trigger
**Then** draft được lưu vào `sessionStorage` với key `export_draft_{session_filename}` — không có UI feedback, silent save

**Given** draft đã lưu trong sessionStorage và Narron mở lại ExportPreview cho cùng session
**When** ExportPreview render
**Then** textarea content được restore từ sessionStorage — edited textareas hiển thị lại nội dung đã sửa

**Given** Narron xóa hết nội dung của textarea (blank)
**When** textarea trống
**Then** border highlight yellow-300 + hint text "Trống — pre-fill template đã bị xóa" — không block Confirm

**Given** export thành công hoặc Narron nhấn Reset session mới
**When** cleanup trigger
**Then** `sessionStorage` key `export_draft_{session_filename}` bị xóa — draft không persist sang session sau

---

### Story 2.4: Trades array management trong ExportPanel

As a trader,
I want trades từ replay được tự động thu thập và reset đúng lúc,
So that ExportPreview luôn có đúng danh sách trades của session hiện tại, không bao giờ lẫn với session cũ.

**Acceptance Criteria:**

**Given** ExportPanel component đã mounted
**When** component init
**Then** trades array = `[]` (empty), subscribe vào `tradeCompleted` event và `replayStateChanged` event từ EventBus

**Given** replay đang chạy và trade hit (TP hoặc SL)
**When** `tradeCompleted` event fire
**Then** trade object được append vào trades array — `trades.length` tăng 1

**Given** Narron nhấn Reset trong Phase 1 UI
**When** `replayStateChanged` với `state: 'stopped'` fire (hoặc reset signal)
**Then** trades array bị clear về `[]` — data của session cũ không còn trong memory

**Given** `replayStateChanged` với `state: 'stopped'` và trades array có data
**When** Export button render
**Then** Export button enabled (không disabled) — Narron có thể export ngay cả khi chưa replay lại

**Given** `replayStateChanged` với `state: 'playing'`
**When** Export button render
**Then** Export button disabled — không thể trigger export khi replay đang chạy


---

## Epic 3: Ghi kết quả vào Supabase và xác nhận

Narron có thể thực sự ghi session đã review vào Supabase Backtest DB — với progress feedback realtime, atomic rollback nếu fail, và link Supabase để verify ngay sau khi xong.

### Story 3.1: POST /api/export — write signal_comparisons và signal_cases

As a developer,
I want backend endpoint nhận trade list và ghi atomic vào cả 2 Supabase tables,
So that Narron có thể commit kiến thức vào Supabase Backtest DB với guarantee: hoặc tất cả rows thành công, hoặc không có gì được ghi.

**Acceptance Criteria:**

**Given** `POST /api/export` với valid payload (session_filename, strategy_name, trades array có đủ fields)
**When** endpoint được gọi và `SUPABASE_ENABLED=true`
**Then** backend ghi `signal_comparisons` trước → nếu thành công → ghi `signal_cases` → return `{"signal_comparisons_count": N, "signal_cases_count": N, "first_signal_id": "backtest_...", "supabase_url": "..."}`

**Given** `signal_comparisons` ghi thành công nhưng `signal_cases` fail (ví dụ: auth error với service key)
**When** partial failure xảy ra
**Then** backend execute `DELETE FROM signal_comparisons WHERE signal_id LIKE 'backtest_{date}_{strategy}_%'` → return HTTP 500 với `{"error": "partial_write_rolled_back", "message": "Authentication failed cho signal_cases (RLS enabled) — Kiểm tra SUPABASE_SERVICE_KEY trong .env. Đã rollback signal_comparisons."}`

**Given** session đã được export trước đó (duplicate detection)
**When** `POST /api/export` với cùng `session_filename`
**Then** HTTP 409 với `{"error": "duplicate", "message": "Session BTCUSDT_4h_20260420.parquet đã export — xóa rows trên Supabase trước nếu muốn re-export"}` — không có row nào được ghi

**Given** `SUPABASE_ENABLED=false`
**When** `POST /api/export` được gọi
**Then** HTTP 503 với `{"error": "disabled", "message": "Supabase integration chưa được bật — set SUPABASE_ENABLED=true trong .env"}` — không attempt kết nối Supabase

**Given** Supabase đang wake up từ idle (free tier) và request timeout sau 30s
**When** timeout xảy ra
**Then** HTTP 504 với `{"error": "timeout", "message": "Supabase đang wake up — thử lại sau 30 giây"}` — không partial write

**Given** backend log trong quá trình export
**When** export thành công
**Then** log INFO: "Exported session {filename}: {N} signal_comparisons + {N} signal_cases"

**Given** backend log trong quá trình export
**When** export fail và rollback
**Then** log ERROR: "Export failed, rolled back {N} signal_comparisons rows. Error: {error_detail}"

---

### Story 3.2: ExportProgressOverlay — feedback realtime và kết quả

As a trader,
I want thấy progress step-by-step khi đang ghi Supabase và kết quả rõ ràng khi xong,
So that tôi không bao giờ thấy app im lặng và không biết chuyện gì đang xảy ra.

**Acceptance Criteria:**

**Given** Narron click "Confirm Export" trong ExportPreview (sau khi scroll đến cuối)
**When** export trigger
**Then** ExportPreview đóng → ExportProgressOverlay mở với state "In Progress": spinner + "Đang ghi vào Supabase..." + step text: "⏳ Đang ghi signal_comparisons..."

**Given** ExportProgressOverlay đang ở state "In Progress"
**When** signal_comparisons ghi xong
**Then** step text update: "✅ signal_comparisons (31/31)" + "⏳ Đang ghi signal_cases..."

**Given** cả 2 tables ghi thành công
**When** backend trả về success response
**Then** ExportProgressOverlay chuyển sang state "Success": icon ✅ + "Export thành công!" + "31 rows → signal_comparisons | 31 rows → signal_cases" + clickable "Xem trên Supabase →" link + button "Reset Replay"

**Given** export fail (ví dụ: auth error)
**When** backend trả về error response
**Then** ExportProgressOverlay chuyển sang state "Error": icon ❌ + actionable error message + collapsible "Xem chi tiết kỹ thuật" + button "Thử lại"

**Given** rollback xảy ra (signal_cases fail sau khi signal_comparisons đã ghi)
**When** rollback complete
**Then** ExportProgressOverlay Error state hiển thị: "Đã rollback signal_comparisons (0/31 được giữ lại)" — Narron biết state sạch, có thể retry

**Given** Narron click "Thử lại" trong Error state
**When** retry action
**Then** ExportProgressOverlay reset về In Progress state → gửi lại `POST /api/export` request — không cần đóng overlay hay navigate lại

**Given** Narron click "Reset Replay" trong Success state
**When** action
**Then** ExportProgressOverlay đóng + EventBus emit reset signal → Phase 1 UI reset về Setup mode

---

### Story 3.3: Session exported indicator và duplicate prevention

As a trader,
I want sessions đã export có visual indicator rõ ràng và không thể export lại vô tình,
So that tôi không bao giờ ghi duplicate data vào Supabase Backtest DB.

**Acceptance Criteria:**

**Given** export thành công cho session `BTCUSDT_4h_20260420.parquet`
**When** SessionListPanel được mở lại (refresh)
**Then** session row đó hiển thị badge gray "Đã export {date}" thay vì "Export" button — indicator này persist qua browser refresh (lưu vào localStorage)

**Given** session có badge "Đã export {date}" trong SessionListPanel
**When** Narron muốn re-export
**Then** "Re-export" button hiển thị thay vì "Export" — click → toast warning: "Session đã export ngày {date}. Backend sẽ từ chối nếu rows chưa được xóa trên Supabase"

**Given** `POST /api/export` trả về HTTP 409 (duplicate từ backend)
**When** frontend nhận 409
**Then** ExportProgressOverlay Error state hiển thị message: "Session đã export — xóa rows trên Supabase trước nếu muốn re-export" — không crash, không silent fail

**Given** localStorage bị clear hoặc first run trên browser mới
**When** SessionListPanel load
**Then** tất cả sessions hiển thị "Export" button — backend là source of truth cho duplicate detection; localStorage chỉ là UI cache


---

## Epic 4: Data integrity — bot nhận đúng data để học

Mỗi row ghi vào Supabase phải đúng schema của production bot — signal_id format, timestamp Unix ms, outcome mapping chính xác, reasoning template có context EMA/volume từ candle trước entry. Có pytest coverage cho critical paths.

### Story 4.1: services/supabase.py — write functions và schema mapping

As a developer,
I want 2 functions isolated trong services/supabase.py map chính xác từ trade object sang Supabase schema,
So that mọi field ghi vào database khớp với format mà production bot đang expect — zero ETL needed.

**Acceptance Criteria:**

**Given** `services/supabase.py` được tạo
**When** file được import
**Then** chứa đúng 2 functions: `write_signal_comparisons(trades: list[dict], settings: Settings) -> int` và `write_signal_cases(trades: list[dict], settings: Settings) -> int` — không có class, không có helper functions thừa (YAGNI)

**Given** trade object `{bar_index: 42, entry_timestamp_ms: 1745625600000, direction: "LONG", result: "win", strategy_name: "breakout_4h", session_date: "20260426", ...}`
**When** `write_signal_comparisons` map sang `signal_comparisons` row
**Then** fields được map đúng: `signal_id = "backtest_20260426_breakout_4h_00042"`, `timestamp = 1745625600000` (int64), `type = "LONG"`, `bot_verdict = "BUY"`, `result = "win"`, `follow = "TP hit"`, `invalidation_condition = "SL tại 42800.0"`, `telegram_sent = false`, `claude_verdict = null`

**Given** cùng trade object
**When** `write_signal_cases` map sang `signal_cases` row
**Then** fields: `signal_id = "backtest_20260426_breakout_4h_00042"`, `signal_sent_at = ISO8601 UTC từ entry_timestamp_ms`, `market_regime = "unknown"`, `claude_action = "BUY"`, `bot_action = "BUY"`, `outcome = "TP_HIT"`, `reasoning_summary = "{trade.reasoning_summary}"`, `invalidation_condition = "SL tại 42800.0"`, `metadata = {"entry_price": 43250.0, "tp_price": 44000.0, "sl_price": 42800.0, "bars_to_exit": 7, "timeframe": "4h", "schema_version": "1.0"}`

**Given** `write_signal_comparisons` sử dụng Supabase anon key
**When** function gọi Supabase REST API
**Then** dùng `httpx` với header `Authorization: Bearer {settings.supabase_key}` — không dùng `settings.supabase_service_key`

**Given** `write_signal_cases` sử dụng Supabase service role key
**When** function gọi Supabase REST API
**Then** dùng `httpx` với header `Authorization: Bearer {settings.supabase_service_key}` — không dùng anon key

**Given** Supabase trả về type mismatch error (ví dụ: timestamp là string thay vì int)
**When** error response từ Supabase
**Then** function raise exception với message cụ thể: "Schema mismatch: field 'timestamp' — expected int64, got string" — không silent fail, không ghi partial data

---

### Story 4.2: Pytest unit tests cho critical paths

As a developer,
I want unit tests cover quality gate, signal_id generation, outcome mapping, và reasoning template,
So that những logic critical này được verify tự động — không cần Supabase connection để chạy tests.

**Acceptance Criteria:**

**Given** `tests/test_export.py` được tạo
**When** `pytest tests/test_export.py` chạy
**Then** tất cả tests pass — không cần Supabase credentials, không cần internet connection

**Given** quality gate logic
**When** test cases: `(trades=7, win_rate=0.71)`, `(trades=15, win_rate=0.48)`, `(trades=10, win_rate=0.55)`, `(trades=9, win_rate=0.60)`
**Then** kết quả đúng: fail, fail, pass, fail — với reason message cụ thể cho từng fail case

**Given** signal_id generation function
**When** input `(session_date="20260426", strategy_name="breakout_4h", bar_index=42)`
**Then** output = `"backtest_20260426_breakout_4h_00042"` — zero-padded 5 digits

**Given** signal_id với strategy_name chứa spaces hoặc special chars
**When** `strategy_name="Breakout 4H / EMA"`
**Then** output sanitized: `"backtest_20260426_breakout_4h_ema_00042"` — lowercase, spaces và `/` thay bằng `_`

**Given** outcome mapping tests
**When** input `result="win"` → `follow="TP hit"`, `outcome="TP_HIT"`; input `result="loss"` → `follow="SL hit"`, `outcome="SL_HIT"`; input `direction="LONG"` → `bot_verdict="BUY"`, `claude_action="BUY"`; input `direction="SHORT"` → `bot_verdict="SELL"`, `claude_action="SELL"`
**Then** tất cả 4 mapping đúng

**Given** reasoning template generation với Parquet data
**When** trade tại bar_index=42, timeframe="4h", entry_price=43250, result="win"
**Then** template = `"4H | Entry $43,250 | EMA20=$42,100 | EMA50=$41,800 | Vol=1.8x | Outcome: WIN"` — EMA values lấy từ `df.iloc[41]` (bar_index - 1, slice-first)

**Given** bars_to_exit off-by-one test
**When** trade entry tại bar 42 và exit tại bar 49
**Then** `bars_to_exit = 7` — explicit assertion cho off-by-one edge case

---

### Story 4.3: Credentials validation và .env.example

As a developer,
I want Supabase credentials được validate khi bắt đầu export và .env.example document đầy đủ,
So that Narron nhận error ngay lập tức với hướng dẫn rõ ràng nếu config sai — không phải sau khi 30 rows đã được ghi.

**Acceptance Criteria:**

**Given** `POST /api/export` nhận request
**When** đây là operation đầu tiên với Supabase
**Then** backend validate credentials trước khi ghi bất kỳ row nào: test `GET` đơn giản đến Supabase để verify URL + key hợp lệ

**Given** anon key sai (cho signal_comparisons)
**When** validation check
**Then** HTTP 401 với message: "SUPABASE_KEY không hợp lệ — Kiểm tra anon key trong .env (dùng cho signal_comparisons)" — không row nào được ghi

**Given** service key sai (cho signal_cases)
**When** validation check
**Then** HTTP 401 với message: "SUPABASE_SERVICE_KEY không hợp lệ — Kiểm tra service role key trong .env (dùng cho signal_cases, RLS enabled)" — không row nào được ghi

**Given** `.env.example` trong root directory
**When** developer mở file
**Then** thấy đủ 4 vars với comments:
```
SUPABASE_URL=https://your-project.supabase.co  # URL của Supabase Backtest project (KHÔNG phải production bot)
SUPABASE_KEY=your-anon-key                      # Anon key — dùng cho signal_comparisons (RLS disabled)
SUPABASE_SERVICE_KEY=your-service-role-key      # Service role key — dùng cho signal_cases (RLS enabled)
SUPABASE_ENABLED=false                          # Set true để bật Supabase integration
```

**Given** Supabase URL format sai (ví dụ: thiếu https://)
**When** Pydantic Settings validate
**Then** FastAPI không start với ValidationError rõ ràng chỉ ra field nào sai format

