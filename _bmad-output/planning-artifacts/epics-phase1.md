---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
workflowStatus: complete
completedAt: '2026-04-29'
inputDocuments:
  - '_bmad-output/planning-artifacts/prd.md'
  - '_bmad-output/planning-artifacts/architecture.md'
  - '_bmad-output/planning-artifacts/ux-design-specification.md'
---

# stock_backtest_project Phase 1 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for stock_backtest_project Phase 1 (Visual Bar Replay MVP), decomposing the requirements from the PRD, UX Design Specification, and Architecture into implementable stories.

**Context:** Brownfield project — Phase 2 (Supabase Export) đã hoàn thành. Phase 1 là core trading experience: fetch OHLCV từ Binance → render candlestick chart → vẽ Entry/TP/SL lines → bar-by-bar replay → hit detection → per-trade results. Phần EventBus, ReplayEngine stub, ResultsPanel stub, và TypeScript/esbuild setup đã có sẵn.

## Requirements Inventory

### Functional Requirements

FR1: Trader fetch được dữ liệu OHLCV lịch sử của một trading pair từ Binance public API (không cần API key)
FR2: Hệ thống tự động lưu data đã fetch xuống local Parquet cache per (symbol, timeframe) để sử dụng offline
FR3: Trader trigger "Refresh Data" để overwrite toàn bộ cache và fetch fresh từ Binance
FR4: Hệ thống detect và cảnh báo khi có data gaps trong date range đã chọn
FR5: Hệ thống hỗ trợ 5 timeframes (5m, 30m, 1h, 4h, 1D) với lazy loading — chỉ fetch khi user chọn lần đầu
FR6: Hệ thống clip date range về giới hạn data có sẵn và thông báo user
FR7: Trader xem được candlestick chart với dữ liệu OHLCV
FR8: Trader chọn timeframe để hiển thị chart
FR9: Trader chọn date range để xem giai đoạn cụ thể
FR10: Trader hover lên nến để xem thông tin OHLCV chi tiết (Open, High, Low, Close, Volume, timestamp)
FR11: Trader xem MA và EMA overlay trên chart — chỉ hiển thị đến nến hiện tại trong replay
FR12: Hệ thống chỉ hiển thị data và indicators của các nến đã đóng hoàn toàn trong replay mode
FR13: Trader vẽ đường ngang Entry lên chart bằng click
FR14: Trader vẽ đường ngang Take Profit lên chart bằng click
FR15: Trader vẽ đường ngang Stop Loss lên chart bằng click
FR16: Hệ thống tự động snap đường vẽ vào mức giá gần nhất khi user đặt đường
FR17: Trader kéo (drag) đường đã vẽ để thay đổi vị trí mà không cần xóa và vẽ lại
FR17b: Trader xóa một đường đơn lẻ (click chọn đường → nhấn Delete/Backspace hoặc nút xóa trên đường)
FR18: Hệ thống hiển thị price label trên đường vẽ để trader biết giá chính xác
FR19: Hệ thống phân biệt rõ ràng 3 loại đường bằng màu sắc: Entry (xanh), Take Profit (teal), Stop Loss (đỏ)
FR19b: Hệ thống giới hạn tối đa 1 Entry + 1 TP + 1 SL tại một thời điểm — vẽ đường mới cùng loại thay thế cũ
FR19c: Khi user switch timeframe, tất cả drawings bị xóa — chart là blank slate cho timeframe mới
FR20: Trader bắt đầu replay bar-by-bar từ đầu date range đã chọn
FR21: Trader pause và resume replay tại bất kỳ vị trí nào
FR22: Trader điều chỉnh tốc độ replay: Slow (~500ms/nến), Normal (~150ms/nến), Fast (~30ms/nến) — bằng UI button hoặc phím tắt 1/2/3
FR23: Trader reset replay về đầu date range mà không mất các đường đã vẽ — chart scroll về đầu, zoom level giữ nguyên
FR24: Hệ thống reveal từng nến theo thứ tự thời gian — không hiển thị nến tương lai
FR25: Hệ thống chỉ check điều kiện entry/TP/SL tại thời điểm nến đóng hoàn toàn (close(N) → execute tại open(N+1))
FR26: Tại close(N): nếu high(N) ≥ Entry price và chưa có position mở → ghi nhận lệnh mở tại open(N+1)
FR27: Tại close(N) khi có position mở: nếu high(N) ≥ TP price → đóng lệnh thắng tại TP price
FR28: Tại close(N) khi có position mở: nếu low(N) ≤ SL price → đóng lệnh thua tại SL price. Gap-down: nếu open(N) < SL → đóng tại open(N)
FR29: Tại close(N) khi TP và SL đều bị touch: nến bullish → check TP trước; nến bearish → check SL trước
FR30: Khi lệnh mở không có TP/SL, hệ thống tự động đóng lệnh tại nến cuối date range
FR31: Hệ thống tính P&L có tính commission 0.1% mỗi chiều cho mỗi lệnh. P&L lock tại thời điểm nhấn Play
FR32: Hệ thống giới hạn 1 position mở tại một thời điểm — Entry hit tiếp theo bị ignore khi đang có position
FR33: Hệ thống hiển thị visual marker trên chart tại điểm entry và exit của mỗi lệnh
FR34: Trader xem danh sách tất cả lệnh trong session: entry price, exit price, loại exit (TP/SL/auto-close), P&L, timestamp nến trigger
FR35: Trader xem tổng kết session: số lệnh thắng, số lệnh thua, tổng P&L %
FR36: Hệ thống cảnh báo khi số lệnh < 30 (warning nhẹ) và < 10 (warning mạnh — "không có ý nghĩa thống kê")
FR37: Hệ thống cung cấp audit trail per lệnh: timestamp nến trigger, giá OHLC tại thời điểm trigger
FR38: Hệ thống hiển thị empty state rõ ràng khi chưa có data, hướng dẫn user fetch data lần đầu
FR38b: Hệ thống hiển thị thông báo rõ ràng khi replay kết thúc với 0 lệnh
FR39: Hệ thống hiển thị progress indicator trong quá trình fetch data từ Binance (% + status text)
FR40: Hệ thống hiển thị getting started guide 3 bước cho lần đầu dùng tool
FR41: Hệ thống tự động retry khi fetch data thất bại và thông báo trạng thái cho user
FR42: Hệ thống có thể cấu hình host, port, cache directory và authentication mode không cần thay đổi source code
FR43: Khi `APP_PASSWORD` được set, hệ thống yêu cầu HTTP Basic Auth trước khi trả về data
FR44: Hệ thống hoạt động hoàn toàn offline sau khi data đã được cache local

### NonFunctional Requirements

NFR1: Chart render candlestick data từ local cache trong < 2 giây cho tất cả timeframes
NFR2: Bar replay animation duy trì ≥ 30fps ở tất cả tốc độ trên Chrome và Safari (Critical)
NFR3: Indicator calculation (MA, EMA) hiển thị trong < 3 giây sau khi data load
NFR4: API response từ FastAPI backend (OHLCV + indicators từ cache) < 500ms
NFR5: Data fetch lần đầu từ Binance cho 2 năm data hoàn thành trong < 5 phút trên Wifi ổn định
NFR6: Replay engine không block UI thread — user có thể interact với controls trong khi replay đang chạy
NFR7: App sẵn sàng nhận requests trong < 10 giây sau khi chạy lệnh khởi động
NFR8: Hệ thống hoạt động bình thường khi load 5m data 2 năm trên máy 8GB RAM — không OOM
NFR9: Khi `APP_PASSWORD` được set, tất cả endpoints yêu cầu authentication
NFR10: Khi chạy local (`APP_PASSWORD` empty), app chỉ bind trên localhost
NFR11: API keys và credentials không hardcode trong source code
NFR12: Hệ thống không sử dụng bất kỳ thông tin nào của nến N+1 trở đi khi đang replay tại nến N (Critical)
NFR13: Timestamp trong cache luôn store dạng UTC
NFR14: Kết quả P&L phải reproducible — cùng data + strategy → cùng kết quả (Critical)
NFR15: Cache data phải được validate (dedup timestamps, sort ascending) trước khi sử dụng
NFR16: Indicators tính incremental — giá trị tại nến N chỉ dùng data [0..N] (Critical)
NFR17: Cache load validate data types: timestamp là int64 (Unix ms), OHLCV là float64
NFR18: Commission 0.1% mỗi chiều bắt buộc được tính vào mọi P&L calculation (Critical)
NFR19: Hệ thống tự động rate-limit requests, không vượt quá 1200 weight/phút. Khi nhận 429, wait và retry
NFR20: Khi Binance API không khả dụng, fallback sang cached data và thông báo rõ ràng
NFR21: Binance API pagination tự động xử lý — user không cần biết giới hạn 1000 candles/request
NFR22: Cache Parquet files tương thích với pandas trên macOS và Linux
NFR23: Corrupt cache files được tự động detect và xóa — không gây crash app (Critical)
NFR24: Lỗi fetch data không crash app — hiển thị error message và cho phép retry
NFR25: App khởi động thành công ngay cả khi chưa có bất kỳ cache data nào (Critical)
NFR26: Chart rendering và drawing tools cho kết quả nhất quán trên Chrome latest và Safari latest

### Additional Requirements

- Gap 1 (Critical): API phải slice OHLCV trước khi compute indicators — `df.iloc[:date_end_index].ewm(...)` — không gọi indicators trên full DataFrame
- Gap 2 (Critical): Atomic Parquet write — write-to-temp (`*.parquet.tmp`) + rename, tránh partial write corruption
- Gap 3 (High): Replay timing dùng delta-time accumulation — track `lastTimestamp`, accumulate `elapsed`, advance bar khi `elapsed >= targetInterval` — không dùng naive setTimeout
- Gap 4 (High): DrawingManager subscribe vào Lightweight Charts zoom/pan events để re-render overlay. CoordinateTranslator là independent module
- Gap 5 (High): Binance fetch là async FastAPI endpoint (non-blocking). Progress dùng SSE StreamingResponse
- Gap 8 (Medium): Validate `received_rows == expected_rows` sau mỗi Binance API page — retry page nếu thiếu
- Gap 9 (High): SSE heartbeat ping mỗi 15 giây để giữ connection qua proxy. Fallback polling nếu SSE lost
- Gap 10 (High): Job lock per (symbol, timeframe) — 409 Conflict nếu fetch job đang chạy
- Gap 11 (High): Cancellable asyncio.Task dict — cancel task cũ khi new request cùng key, cleanup temp file
- Gap 14 (High): CoordinateTranslator lazy init — `series.priceToCoordinate()` chỉ valid sau chart render
- Gap 15 (Medium): MVP drawing chỉ cần Y-axis (price) translation — không build 2D coordinate system
- ADR-07: pandas built-in `ewm()` cho EMA, `rolling().mean()` cho MA — không dùng pandas-ta trong MVP
- ADR-08: Python environment dùng `uv` hoặc standard `pip` — pyproject.toml là source of truth

### UX Design Requirements

UX-DR1: Pre-flight checklist trước Play — hiển thị "✓ Entry set | ✓ TP set | ✓ SL set | ✓ Date range: 6 months | [Start Replay]". Start Replay disabled khi chưa đủ điều kiện
UX-DR2: Live R:R ratio display khi drag TP/SL line — hiển thị ngay "R:R = 1:2.3" trong setup mode
UX-DR3: Toast + 5-giây timed undo khi switch timeframe (destructive action xóa drawings)
UX-DR4: Setup mode vs Replay mode — 2 distinct UI states với different controls và keyboard scope
UX-DR5: Session Fingerprint header — hiển thị exact conditions (symbol, timeframe, date range, line prices) trước khi Play
UX-DR6: Rapid iteration UX — Reset button prominent, drawings persist through reset, replay restart là 1-click
UX-DR7: Chart markers (entry/exit dots) là primary results view. Brief pulse animation 1 lần khi trade hit
UX-DR8: Last-used settings persistence (timeframe, date range, drawing positions) qua localStorage
UX-DR9: Indicators OFF by default — trader opt-in bật MA/EMA toolbar toggle
UX-DR10: Keyboard shortcuts — Space (play/pause), 1/2/3 (speed Slow/Normal/Fast), arrows (step forward/back), `?` (cheat sheet)
UX-DR11: Disk space warning trước khi fetch 5m data (~50MB)
UX-DR12: Empty state với placeholder ghost drawings mẫu trên chart + inline 3-step guide
UX-DR13: Progress indicator % + current status text khi fetch Binance (5 phút fetch)
UX-DR14: Bloomberg error block format — bordered block, icon + 2 actionable lines (what happened + what to do)
UX-DR15: Smooth candle animation — slide in từ phải khi reveal, không teleport
UX-DR16: Real-time results table update trong replay (live scoring feeling)
UX-DR17: CSS design tokens system — `--{tier}-{category}-{property}` naming, `@layer reset, tokens, components, utilities`
UX-DR18: Layout — chart ≥ 70% screen, results panel max-width 400px, min-width 1024px overall
UX-DR19: Volume bars OFF by default, 1-click toolbar toggle để bật

### FR Coverage Map

FR1: Epic 1 — Fetch OHLCV từ Binance public API
FR2: Epic 1 — Lưu Parquet cache per (symbol, timeframe)
FR3: Epic 1 — Refresh Data button — overwrite cache
FR4: Epic 1 — Detect và cảnh báo data gaps
FR5: Epic 1 — 5 timeframes, lazy load
FR6: Epic 1 — Clip date range + thông báo
FR7: Epic 2 — Candlestick chart render
FR8: Epic 2 — Timeframe selector
FR9: Epic 2 — Date range selector
FR10: Epic 2 — OHLCV hover tooltip
FR11: Epic 3 — MA/EMA overlay (slice-first, no look-ahead)
FR12: Epic 4 — Chỉ hiển thị nến đã đóng trong replay (replay constraint)
FR13: Epic 3 — Vẽ Entry line
FR14: Epic 3 — Vẽ TP line
FR15: Epic 3 — Vẽ SL line
FR16: Epic 3 — Price snap
FR17: Epic 3 — Drag to move
FR17b: Epic 3 — Delete line
FR18: Epic 3 — Price label trên line
FR19: Epic 3 — Màu phân biệt 3 loại line
FR19b: Epic 3 — Max 1 line per type
FR19c: Epic 3 — Xóa drawings khi switch timeframe
FR20: Epic 4 — Start replay
FR21: Epic 4 — Pause/resume
FR22: Epic 4 — 3 tốc độ (Slow/Normal/Fast)
FR23: Epic 4 — Reset giữ drawings
FR24: Epic 4 — Reveal nến từng cây, không look-ahead
FR25: Epic 5 — Hit detection tại close(N)
FR26: Epic 5 — Entry trigger logic
FR27: Epic 5 — TP hit logic
FR28: Epic 5 — SL hit logic (gap-down slippage)
FR29: Epic 5 — TP vs SL same candle priority
FR30: Epic 5 — Auto-close tại nến cuối
FR31: Epic 5 — P&L + commission 0.1%
FR32: Epic 5 — 1 position at a time
FR33: Epic 5 — Visual markers entry/exit trên chart
FR34: Epic 5 — Per-trade list
FR35: Epic 5 — Session summary stats
FR36: Epic 5 — Sample size warnings
FR37: Epic 5 — Audit trail per trade
FR38: Epic 6 — Empty state + getting started guide
FR38b: Epic 5 — 0-trade warning khi replay xong với 0 lệnh
FR39: Epic 1 — Progress indicator khi fetch Binance
FR40: Epic 6 — Getting started guide 3 bước
FR41: Epic 1 — Auto-retry khi fetch fail
FR42: Epic 1 — Env vars config (host, port, cache dir, auth)
FR43: Epic 1 — HTTP Basic Auth khi APP_PASSWORD set
FR44: Epic 1 — Offline mode sau khi data cached

## Epic List

### Epic 1: Backend Data Pipeline — Fetch, Cache, OHLCV API

Trader có thể fetch dữ liệu OHLCV BTC/USDT từ Binance (async, non-blocking), lưu xuống local Parquet cache, và backend serve data qua REST API. App hoạt động offline sau khi data cached.

**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR39, FR41, FR42, FR43, FR44
**NFRs:** NFR4, NFR5, NFR7, NFR8, NFR9, NFR10, NFR11, NFR13, NFR15, NFR17, NFR19, NFR20, NFR21, NFR22, NFR23, NFR24, NFR25
**Architecture gaps:** Gap 2 (atomic Parquet write), Gap 5 (async SSE fetch), Gap 8 (batch validation), Gap 9 (SSE heartbeat + fallback), Gap 10 (job lock), Gap 11 (cancellable task), ADR-07 (pandas ewm/rolling), ADR-08 (uv/pip)
**UX:** UX-DR13 (progress % + status text), UX-DR14 (Bloomberg error format)

---

### Epic 2: Chart UI + Toolbar

Trader có thể xem candlestick chart OHLCV, chọn timeframe và date range, hover để xem OHLCV tooltip. Frontend dùng mock API trước (unblock khỏi Epic 1). Design tokens và layout được thiết lập cho toàn bộ app.

**FRs covered:** FR7, FR8, FR9, FR10
**NFRs:** NFR1, NFR3, NFR26
**UX:** UX-DR17 (CSS design tokens — foundation cho toàn app), UX-DR18 (layout: chart ≥ 70%, results panel max 400px), UX-DR19 (volume OFF default), UX-DR9 (indicators OFF default)

---

### Epic 3: Drawing Tools (Entry/TP/SL Lines)

Trader có thể vẽ, drag, xóa các đường ngang Entry/TP/SL trên chart với price snap, price label, màu phân biệt, R:R ratio live khi drag, và toast+undo khi switch timeframe.

**FRs covered:** FR11, FR13, FR14, FR15, FR16, FR17, FR17b, FR18, FR19, FR19b, FR19c
**NFRs:** NFR16, NFR26
**Architecture gaps:** Gap 4 (coordinate bridge — subscribe zoom/pan), Gap 14 (CoordinateTranslator lazy init), Gap 15 (Y-axis only scope)
**UX:** UX-DR2 (R:R ratio live khi drag), UX-DR3 (toast + 5s undo khi switch timeframe)

---

### Epic 4: Bar Replay Engine

Trader có thể play/pause replay bar-by-bar, chọn 3 tốc độ, reset giữ drawings, với smooth candle animation. Chart chỉ reveal nến đã đóng — không look-ahead. Pre-flight checklist trước Play.

**FRs covered:** FR12, FR20, FR21, FR22, FR23, FR24
**NFRs:** NFR2, NFR6, NFR12
**Architecture gaps:** Gap 3 (delta-time accumulation cho rAF), Gap 12 (tsc --noEmit), Gap 13 (EventMap typed)
**UX:** UX-DR1 (pre-flight checklist), UX-DR4 (setup mode vs replay mode), UX-DR5 (session fingerprint header), UX-DR6 (rapid iteration — reset 1-click), UX-DR10 (keyboard shortcuts: Space/1/2/3/arrows), UX-DR15 (smooth candle slide-in animation)

---

### Epic 5: Hit Detection, Trade Execution + Results

Trader thấy visual markers khi trade hit, xem per-trade breakdown với P&L/timestamp/audit trail, và tổng kết session với sample size warnings. Hit detection tuân thủ strict look-ahead prevention.

**FRs covered:** FR25, FR26, FR27, FR28, FR29, FR30, FR31, FR32, FR33, FR34, FR35, FR36, FR37, FR38b
**NFRs:** NFR14, NFR18
**UX:** UX-DR7 (chart markers primary — brief pulse animation khi hit), UX-DR16 (real-time results table update trong replay)

---

### Epic 6: Onboarding, UX Polish + Settings Persistence

Trader lần đầu dùng tool thấy empty state rõ ràng với getting started guide. Settings (timeframe, date range, drawing positions) được tự động restore lần tiếp theo mở app.

**FRs covered:** FR38, FR40
**UX:** UX-DR8 (last-used settings persistence qua localStorage), UX-DR12 (empty state với placeholder ghost drawings)

---

## Epic 6: Onboarding, UX Polish + Settings Persistence

Trader lần đầu dùng tool thấy empty state rõ ràng với getting started guide. Settings (timeframe, date range, drawing positions) được tự động restore lần tiếp theo mở app.

### Story 6.1: Empty state + Getting started guide

As a first-time trader,
I want to see clear guidance when the app has no data,
So that I know exactly what to do to start my first replay session.

**Acceptance Criteria:**

**Given** app load lần đầu và cache rỗng (không có Parquet file nào)
**When** chart area render
**Then** hiển thị empty state với placeholder ghost drawings mẫu trên chart (Entry/TP/SL ở vị trí tiêu biểu, mờ/dim)
**And** getting started guide 3 bước hiển thị inline:
  1. "Fetch data: Chọn symbol + timeframe → Click Fetch"
  2. "Vẽ strategy: Click để đặt Entry, TP, SL lên chart"
  3. "Replay: Nhấn Play để xem kết quả từng lệnh"
**And** ghost drawings biến mất ngay khi trader vẽ đường đầu tiên của mình
**And** guide biến mất khi data đã có và trader bắt đầu tương tác

### Story 6.2: Last-used settings persistence qua localStorage

As a returning trader,
I want my previous timeframe, date range, and drawing positions restored automatically,
So that I can continue practice sessions without reconfiguring from scratch.

**Acceptance Criteria:**

**Given** trader đã dùng app trước đó với timeframe 4h, date range và 3 đường đã vẽ
**When** trader mở app lại (fresh page load)
**Then** timeframe tự động set về giá trị đã lưu
**And** date range tự động set về range đã lưu
**And** drawings (Entry/TP/SL với prices đã lưu) được restore lên chart

**Given** localStorage bị corrupt hoặc không có dữ liệu saved
**When** app load
**Then** app load với defaults (timeframe 4h, date range 6 tháng gần nhất) — không crash
**And** không có error message hiển thị cho user — degrade gracefully

---

## Epic 5: Hit Detection, Trade Execution + Results

Trader thấy visual markers khi trade hit, xem per-trade breakdown với P&L/timestamp/audit trail, và tổng kết session với sample size warnings. Hit detection tuân thủ strict look-ahead prevention.

### Story 5.1: Hit detection engine — Entry/TP/SL logic

As a trader,
I want the system to detect entry and exit conditions accurately at candle close,
So that results reflect realistic execution without look-ahead bias.

**Acceptance Criteria:**

**Given** replay tại close(N), chưa có position mở
**When** `high(N) >= Entry price`
**Then** lệnh được ghi nhận mở tại `open(N+1)` — không intra-candle
**And** khi đã có position mở, Entry hit tiếp theo bị ignore hoàn toàn (max 1 position at a time)

**Given** replay tại close(N), đang có position mở
**When** `high(N) >= TP price` và/hoặc `low(N) <= SL price`
**Then** nếu chỉ TP → đóng lệnh thắng tại TP price
**And** nếu chỉ SL → đóng lệnh thua tại SL price
**And** nếu cả hai cùng nến: nến bullish (close > open) → check TP trước; nến bearish → check SL trước
**And** gap-down: nếu `open(N) < SL price` → đóng tại `open(N)` (slippage), không tại SL price

**Given** lệnh mở không có TP/SL
**When** replay đến nến cuối date range
**Then** lệnh tự động đóng tại close của nến cuối

### Story 5.2: P&L calculation + commission

As a trader,
I want P&L calculated with commission included and locked at Play time,
So that results reflect real trading costs and are reproducible.

**Acceptance Criteria:**

**Given** lệnh đã đóng với entry price và exit price
**When** P&L được tính
**Then** `P&L % = (exit_price - entry_price) / entry_price * 100 - 0.1% - 0.1%` (commission 0.1% mỗi chiều)
**And** P&L được lock tại thời điểm nhấn Play — drag đường sau khi Play không ảnh hưởng session đang chạy
**And** cùng data + cùng Entry/TP/SL prices → cùng P&L kết quả mọi lần chạy (reproducible)

### Story 5.3: Visual trade markers trên chart

As a trader,
I want to see entry and exit markers on the chart,
So that I can visually understand where each trade occurred in the context of price action.

**Acceptance Criteria:**

**Given** lệnh vừa được mở tại bar N+1
**When** replay reveal bar N+1
**Then** marker "▲ Entry" xuất hiện tại đáy nến entry — màu xanh
**And** marker có brief pulse animation 1 lần khi xuất hiện (không loop)

**Given** lệnh đóng tại bar M (TP hoặc SL hit)
**When** replay reveal bar M
**Then** marker "✓ TP" hoặc "✗ SL" xuất hiện tại bar exit với màu tương ứng (teal / đỏ)
**And** markers cho tất cả trades trong session tích lũy trên chart — không bị xóa khi replay tiếp tục
**And** markers bị xóa khi trader nhấn Reset

### Story 5.4: Per-trade results panel + real-time update

As a trader,
I want a live results table that updates as each trade completes,
So that I can track session performance without waiting for replay to finish.

**Acceptance Criteria:**

**Given** replay đang chạy
**When** một lệnh vừa đóng
**Then** row mới xuất hiện ngay trong results panel với: #, Entry price, Exit price, Exit type (TP/SL/auto), P&L %, timestamp nến trigger
**And** results table cập nhật real-time trong replay — không chờ đến cuối session
**And** mỗi row có audit trail: timestamp nến trigger (UTC+7), giá OHLC tại bar trigger

**Given** replay kết thúc không có trade nào
**When** date range đã replay hết
**Then** hiển thị message "Entry price chưa được chạm trong date range đã chọn — thử mở rộng date range hoặc điều chỉnh vị trí đường Entry"

### Story 5.5: Session summary + sample size warnings

As a trader,
I want a session summary with win rate and warnings when sample size is too small,
So that I can judge whether my results are statistically meaningful.

**Acceptance Criteria:**

**Given** session kết thúc (replay done hoặc trader dừng)
**When** results panel hiển thị summary
**Then** summary gồm: tổng số lệnh, số thắng, số thua, win rate %, tổng P&L %

**Given** số lệnh trong session < 30
**When** summary hiển thị
**Then** warning nhẹ: "⚠ Sample size < 30 — kết quả chưa đủ tin cậy"

**Given** số lệnh trong session < 10
**When** summary hiển thị
**Then** warning mạnh: "⛔ Sample size < 10 — kết quả không có ý nghĩa thống kê. Mở rộng date range."
**And** warning mạnh được hiển thị nổi bật hơn warning nhẹ

---

## Epic 4: Bar Replay Engine

Trader có thể play/pause replay bar-by-bar, chọn 3 tốc độ, reset giữ drawings, với smooth candle animation và look-ahead prevention. Pre-flight checklist đảm bảo setup đầy đủ trước khi Play.

### Story 4.1: ReplayEngine — delta-time bar advancement loop

As a trader,
I want bar replay to advance smoothly at consistent speed,
So that I experience the market flow accurately even when the browser tab is throttled.

**Acceptance Criteria:**

**Given** trader nhấn Play
**When** replay loop chạy qua `requestAnimationFrame`
**Then** engine dùng delta-time accumulation: track `lastTimestamp`, accumulate `elapsed`, advance bar chỉ khi `elapsed >= targetInterval`
**And** Slow = 500ms/bar, Normal = 150ms/bar, Fast = 30ms/bar — tất cả 3 speeds reveal từng nến một (Fast không skip nến)
**And** khi tab bị throttle (background tab), replay không advance nhiều bar cùng lúc — chỉ advance 1 bar mỗi tick
**And** replay không block UI thread — trader có thể click controls trong khi replay đang chạy

### Story 4.2: Play/Pause/Reset controls + keyboard shortcuts

As a trader,
I want Play, Pause, and Reset controls with keyboard shortcuts,
So that I can control replay flow without reaching for the mouse.

**Acceptance Criteria:**

**Given** trader đang ở Setup mode (chưa Play)
**When** trader nhấn nút Play hoặc phím Space
**Then** replay bắt đầu từ đầu date range, UI chuyển sang Replay mode
**And** toolbar chuyển sang hiển thị Pause button thay thế Play button

**Given** replay đang chạy
**When** trader nhấn Pause hoặc Space
**Then** replay dừng tại bar hiện tại — chart giữ nguyên vị trí

**Given** replay đang chạy hoặc đã pause
**When** trader nhấn Reset
**Then** chart scroll về đầu date range, tất cả trade markers bị xóa, drawings giữ nguyên
**And** UI trở về Setup mode — trader có thể điều chỉnh drawings và Play lại
**And** phím 1/2/3 đổi speed (Slow/Normal/Fast) bất kỳ lúc nào kể cả khi đang replay

### Story 4.3: Look-ahead prevention — chỉ reveal nến đã đóng

As a trader,
I want the chart to only show candles that have fully closed during replay,
So that I can practice without accidentally seeing future price action.

**Acceptance Criteria:**

**Given** replay đang chạy tại bar index N
**When** chart render
**Then** chỉ hiển thị nến từ index 0 đến N (inclusive) — nến N+1 trở đi không visible
**And** MA/EMA overlay cũng chỉ vẽ đến bar N — không extend vào tương lai
**And** OHLCV tooltip chỉ hoạt động cho nến đã revealed — hover lên vùng chưa render thì không có tooltip

### Story 4.4: Pre-flight checklist + Session Fingerprint

As a trader,
I want a checklist before starting replay and a session fingerprint header,
So that I don't accidentally run a session with missing lines or wrong settings.

**Acceptance Criteria:**

**Given** trader chưa vẽ đủ Entry + TP + SL
**When** trader nhấn Play
**Then** Play button bị disabled và pre-flight checklist hiển thị trạng thái từng item:
  ✓/✗ Entry set (price) | ✓/✗ TP set (price) | ✓/✗ SL set (price) | ✓ Date range
**And** Play button chỉ enabled khi đủ cả 3 đường Entry + TP + SL

**Given** trader đã đủ điều kiện và nhấn Play
**When** replay bắt đầu
**Then** Session Fingerprint header hiển thị: symbol, timeframe, date range, Entry/TP/SL prices — frozen tại thời điểm Play
**And** drag đường sau khi Play không thay đổi fingerprint

### Story 4.5: Smooth candle animation (slide-in từ phải)

As a trader,
I want each new candle to slide in smoothly from the right,
So that replay feels like watching the market unfold rather than a slideshow.

**Acceptance Criteria:**

**Given** replay đang chạy
**When** một nến mới được reveal
**Then** nến slide in từ phải với `transform: translateX` transition — không teleport
**And** animation dùng `transform` + `opacity` — không dùng `width`/`height` transitions (tránh layout reflow)
**And** chart tự động scroll sang phải để luôn hiển thị nến mới nhất trong viewport
**And** animation mượt mà ở cả 3 tốc độ — Fast (30ms) không gây flicker

---

## Epic 3: Drawing Tools (Entry/TP/SL Lines)

Trader có thể vẽ, drag, xóa các đường ngang Entry/TP/SL trên chart với price snap, price label, màu phân biệt, R:R ratio live khi drag, và toast+undo khi switch timeframe.

### Story 3.1: CoordinateTranslator + DrawingManager scaffold

As a trader,
I want drawing infrastructure ready on the chart,
So that lines can be placed at accurate price levels that stay correct after zoom and pan.

**Acceptance Criteria:**

**Given** chart đã render và `subscribeCrosshairMove()` đã fire lần đầu
**When** `CoordinateTranslator` được khởi tạo (lazy init)
**Then** `series.priceToCoordinate(price)` và `series.coordinateToPrice(y)` hoạt động chính xác
**And** khi chart zoom/pan, `DrawingManager` subscribe vào `priceScale` và `visibleLogicalRange` change events để re-render overlay
**And** coordinate translation chỉ handle Y-axis (price) — không build 2D system trong MVP

### Story 3.2: Vẽ đường Entry/TP/SL bằng click + price snap

As a trader,
I want to place Entry, TP, and SL lines on the chart with a single click,
So that I can define my strategy visually without entering numbers.

**Acceptance Criteria:**

**Given** trader chọn tool "Entry" (hoặc TP / SL) từ toolbar
**When** trader click lên chart
**Then** đường ngang xuất hiện tại mức giá gần nhất (price snap — round đến nearest tick)
**And** đường Entry màu xanh, TP màu teal, SL màu đỏ — consistent trên Chrome và Safari
**And** price label hiển thị trên đường với giá chính xác (ví dụ: "68,500.00")
**And** nếu đã có đường cùng loại, đường mới thay thế đường cũ (max 1 Entry + 1 TP + 1 SL)

### Story 3.3: Drag to move + Delete line

As a trader,
I want to reposition lines by dragging and delete them individually,
So that I can iterate on strategy variants quickly without redrawing from scratch.

**Acceptance Criteria:**

**Given** đường Entry/TP/SL đã được vẽ
**When** trader click và drag đường theo chiều dọc
**Then** đường di chuyển theo cursor, price label cập nhật real-time theo giá mới
**And** khi release, đường snap vào price level gần nhất
**And** drag không bị lag — smooth trên Chrome và Safari

**Given** trader muốn xóa một đường
**When** trader click chọn đường rồi nhấn Delete hoặc Backspace
**Then** đường bị xóa khỏi chart
**And** trader có thể vẽ đường mới cùng loại ngay sau đó

### Story 3.4: Live R:R ratio display khi drag TP/SL

As a trader,
I want to see the R:R ratio update live while dragging TP or SL,
So that I can set optimal risk/reward without manual calculation.

**Acceptance Criteria:**

**Given** cả 3 đường Entry, TP, SL đã được vẽ
**When** trader drag đường TP hoặc SL
**Then** R:R ratio được tính và hiển thị real-time: `R:R = (TP - Entry) / (Entry - SL)` với 2 decimal places
**And** R:R display cập nhật ngay theo từng pixel drag — không debounce
**And** nếu chỉ có Entry + một trong hai TP/SL, R:R không hiển thị (cần đủ 3 đường)

### Story 3.5: Toast + 5s undo khi switch timeframe

As a trader,
I want a brief undo window when switching timeframe,
So that I don't accidentally lose drawings I spent time placing.

**Acceptance Criteria:**

**Given** trader đã vẽ ít nhất 1 đường
**When** trader switch sang timeframe khác
**Then** tất cả drawings bị xóa ngay lập tức (blank slate cho timeframe mới)
**And** toast notification xuất hiện: "Drawings đã bị xóa — [Undo] (5s)" với countdown
**And** nếu trader click Undo trong 5 giây, drawings của timeframe cũ được restore và timeframe switch bị hoàn tác
**And** nếu hết 5 giây không Undo, toast tự ẩn và không thể undo nữa
**And** Ctrl+Z cũng trigger cùng undo action như button Undo trong toast

---

## Epic 2: Chart UI + Toolbar

Trader có thể xem candlestick chart OHLCV, chọn timeframe và date range, hover để xem OHLCV tooltip. Design tokens và layout foundation được thiết lập cho toàn bộ app.

### Story 2.1: CSS Design Token System + App Layout

As a trader,
I want a consistent dark UI layout,
So that the chart feels professional and every component shares the same visual language.

**Acceptance Criteria:**

**Given** app load lần đầu
**When** `index.html` render
**Then** layout có chart area chiếm ≥ 70% screen width, results panel max-width 400px bên phải, toolbar ở trên
**And** CSS sử dụng `@layer reset, tokens, components, utilities` — không có literal hex/px ngoài `:root`
**And** design tokens được định nghĩa: `--prim-gray-*` (màu), `--sem-bg-*`, `--sem-text-*`, `--sem-anim-*`
**And** min-width là 1024px; app responsive theo container width

### Story 2.2: Candlestick chart render từ API

As a trader,
I want to see a candlestick chart loaded from the backend,
So that I can visually analyze OHLCV price data.

**Acceptance Criteria:**

**Given** backend trả về OHLCV data (hoặc mock data trong dev)
**When** `ChartController` nhận data
**Then** Lightweight Charts render candlestick series với đúng OHLCV values
**And** timestamp UTC được convert sang UTC+7 để display trên time axis
**And** chart render trong < 2 giây cho tất cả timeframes
**And** chart width = 100% container, tự động resize khi window resize
**And** nến bullish màu xanh, nến bearish màu đỏ — consistent trên Chrome và Safari

### Story 2.3: Timeframe selector + Date range picker

As a trader,
I want to select timeframe and date range,
So that I can analyze different periods and granularities.

**Acceptance Criteria:**

**Given** app đã load
**When** trader chọn timeframe từ toolbar (5m / 30m / 1h / 4h / 1D)
**Then** chart reload với data của timeframe đó
**And** nếu cache không có cho timeframe đó, hiển thị message "Chưa có data — fetch trước"

**Given** trader thay đổi date range (date_start, date_end)
**When** trader confirm selection
**Then** chart slice về đúng range đó
**And** nếu date range vượt quá data có sẵn trong cache, chart clip về max available và hiển thị warning "Date range đã được clip về [actual_start] — [actual_end]"

### Story 2.4: OHLCV hover tooltip

As a trader,
I want to see OHLCV details when hovering over a candle,
So that I can audit exact price values and timestamps.

**Acceptance Criteria:**

**Given** chart đã render với data
**When** trader hover lên một nến
**Then** tooltip hiển thị: Open, High, Low, Close, Volume, và timestamp dạng "DD/MM/YYYY HH:mm UTC+7"
**And** tooltip không che khuất khu vực chart chính — xuất hiện ở góc không overlap với nến đang hover
**And** khi hover ra ngoài chart, tooltip ẩn đi

### Story 2.5: MA/EMA overlay toggle trên chart

As a trader,
I want to optionally show MA and EMA overlays,
So that I can analyze trend context without cluttering the chart by default.

**Acceptance Criteria:**

**Given** chart đã render
**When** trader bật MA20 hoặc EMA20 từ toolbar toggle
**Then** overlay line xuất hiện trên chart với màu phân biệt
**And** NaN values ở đầu series không được vẽ — không có line tới điểm 0
**And** indicators OFF by default khi mở app
**And** khi date range quá ngắn so với indicator period, hiển thị warning nhỏ "Date range quá ngắn cho MA/EMA period"

---

## Epic 1: Backend Data Pipeline — Fetch, Cache, OHLCV API

Trader có thể fetch dữ liệu OHLCV BTC/USDT từ Binance (async, non-blocking), lưu xuống local Parquet cache, và backend serve data qua REST API. App hoạt động offline sau khi data cached.

### Story 1.1: GET /api/ohlcv — Serve OHLCV từ Parquet cache

As a trader,
I want the backend to serve OHLCV data from local Parquet cache,
So that the frontend can render the chart without waiting for Binance.

**Acceptance Criteria:**

**Given** file `cache/BTCUSDT_1h.parquet` tồn tại
**When** frontend gọi `GET /api/ohlcv?symbol=BTCUSDT&timeframe=1h&date_start=2024-01-01&date_end=2024-03-01`
**Then** backend trả về JSON `{data: [{timestamp, open, high, low, close, volume}, ...]}` với status 200
**And** data được slice theo `date_start`/`date_end` — không trả về toàn bộ cache
**And** timestamp là int64 Unix milliseconds UTC
**And** nếu cache không tồn tại, trả về `{error: "no_cache", message: "..."}` với status 404

### Story 1.2: POST /api/fetch — Async Binance fetch với SSE progress

As a trader,
I want to trigger a data fetch from Binance with real-time progress,
So that I can see how long the download will take without the UI freezing.

**Acceptance Criteria:**

**Given** trader muốn fetch BTCUSDT 1h
**When** frontend gọi `POST /api/fetch` với `{symbol, timeframe, date_start, date_end}`
**Then** backend trả về `{job_id: "..."}` ngay lập tức (non-blocking)
**And** fetch chạy async trong background — server vẫn nhận requests khác
**And** nếu fetch job đang chạy cho cùng (symbol, timeframe), trả về 409 Conflict với message "Fetch already in progress"

**Given** fetch job đang chạy
**When** frontend connect `GET /api/fetch-stream?job_id=...` (SSE)
**Then** backend stream JSON events `{type: "progress", percent: 45, status: "Fetching page 12/50"}`
**And** backend gửi heartbeat `{type: "ping"}` mỗi 15 giây để giữ connection qua proxy
**And** khi done: `{type: "done", rows: 52000}`; khi lỗi: `{type: "error", message: "..."}`

### Story 1.3: Atomic Parquet write + cache validation

As a trader,
I want the cache to never be corrupted even if the server crashes mid-write,
So that I can trust the data is always complete and valid.

**Acceptance Criteria:**

**Given** fetch hoàn thành và data sẵn sàng ghi
**When** backend ghi Parquet file
**Then** backend write vào `*.parquet.tmp` trước, rename thành `*.parquet` chỉ khi write hoàn tất
**And** nếu process bị kill trong khi write, file `.tmp` không được giữ lại — bị cleanup khi server restart

**Given** backend load cache khi có request GET /api/ohlcv
**When** Parquet file bị corrupt (không parse được)
**Then** backend tự động xóa file corrupt và trả về 404 với `{error: "cache_corrupted", message: "Cache đã bị xóa — fetch lại để tạo mới"}`
**And** OHLCV columns được validate: timestamp là int64, OHLCV là float64; duplicate timestamps bị dedup; data sort ascending

### Story 1.4: Binance pagination, rate-limit và auto-retry

As a trader,
I want Binance fetching to handle API limits automatically,
So that I don't have to manage pagination or wait after rate-limit errors.

**Acceptance Criteria:**

**Given** cần fetch 2 năm data (>500 pages × 1000 candles/page)
**When** backend gọi Binance API
**Then** backend tự động paginate — user không cần biết giới hạn 1000 candles/request
**And** sau mỗi page, validate `received_rows == expected_rows`; nếu thiếu, retry page đó trước khi tiếp tục
**And** backend không vượt quá 1200 weight/phút; khi nhận 429, wait theo `Retry-After` header rồi retry
**And** tự động retry tối đa 3 lần với exponential backoff khi fetch fail; sau 3 lần, SSE gửi `{type: "error", message: "..."}`
**And** khi Binance API không khả dụng và cache tồn tại, GET /api/ohlcv vẫn serve từ cache bình thường

### Story 1.5: MA/EMA tính slice-first trên backend (no look-ahead)

As a trader,
I want MA and EMA calculated without look-ahead bias,
So that indicator values during replay accurately reflect only data available at that bar.

**Acceptance Criteria:**

**Given** request `GET /api/ohlcv` với `date_end=2024-03-01`
**When** backend tính EMA20 và MA20
**Then** backend slice DataFrame tới `date_end` trước khi compute: `df.iloc[:date_end_idx].ewm(span=20, adjust=False).mean()` — không compute trên full DataFrame
**And** EMA và MA được trả về cùng response dưới dạng extra columns `ema_20`, `ma_20`
**And** NaN values ở đầu series (warm-up period) được trả về là `null` — không crash, không interpolate
**And** khi date range ngắn hơn indicator period, backend vẫn trả về data với NaN values (không error)

