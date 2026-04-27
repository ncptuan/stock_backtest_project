# Project Context — stock_backtest_project

**Tác giả:** Narron  
**Ngày tạo:** 2026-04-26  
**Mục đích:** AI context file — cung cấp đủ context để bất kỳ AI agent nào cũng có thể hiểu dự án mà không cần đọc lại toàn bộ PRD/Architecture.

---

## 1. Dự án là gì

**stock_backtest_project** là một Visual Bar Replay Tool — thay thế TradingView Bar Replay, self-hosted, zero-cost. Trader vẽ strategy (horizontal lines Entry/TP/SL) lên chart, replay từng nến bar-by-bar, thấy kết quả từng lệnh với audit trail đầy đủ.

**Mental model:** "Trading flight simulator" — fail safely, build intuition qua repetition.

**Người dùng duy nhất:** Narron — trader crypto cá nhân, win rate 56–58%, intermediate tech skill.

---

## 2. Stack kỹ thuật

| Layer | Tech |
|---|---|
| Backend | Python FastAPI + uvicorn, managed bởi `uv` |
| Data storage (backtest) | Parquet local cache (`cache/` folder, gitignored) |
| Data storage (bot) | Supabase (PostgreSQL) — project riêng biệt |
| Frontend | TypeScript + esbuild → `static/app.js` |
| Chart | Lightweight Charts v5.1.0 |
| Indicator | pandas built-in `ewm()` + `rolling().mean()` |
| Data source | Binance public API via ccxt |
| Process mgmt | overmind + Procfile |
| Testing | pytest + pytest-asyncio + httpx |
| Deployment (bot) | Koyeb (đang chạy production) |
| Deployment (backtest tool) | Local-first, Phase 2: Koyeb |

---

## 3. Cấu trúc thư mục

```
stock_backtest_project/
├── backend/
│   ├── main.py              # App factory + route registration only
│   ├── routes/
│   │   ├── ohlcv.py         # GET /api/ohlcv
│   │   └── fetch.py         # POST /api/fetch + GET /api/fetch-stream (SSE)
│   ├── services/
│   │   ├── fetcher.py       # Binance fetch + pagination + retry + job lock
│   │   ├── cache.py         # Parquet read/write (atomic write pattern)
│   │   ├── indicators.py    # EMA, MA (slice-first, no look-ahead)
│   │   └── replay.py        # Hit detection engine
│   ├── models.py            # Pydantic request/response models
│   └── settings.py          # Pydantic Settings — single config source
├── frontend/
│   ├── main.ts              # esbuild entry point
│   ├── EventBus.ts          # Custom EventBus singleton
│   ├── ChartController.ts
│   ├── DrawingManager.ts
│   ├── ReplayEngine.ts
│   ├── ResultsPanel.ts
│   └── types.ts             # EventMap interface + shared types
├── static/
│   ├── index.html
│   └── app.js               # esbuild output — GITIGNORED
├── tests/
│   ├── test_replay.py
│   ├── test_indicators.py
│   └── test_cache.py
├── cache/                   # Parquet files — GITIGNORED
├── docs/
│   ├── user_database        # Supabase SQL schema (bot production DB)
│   └── project-context.md   # File này
├── .env.example
└── pyproject.toml
```

---

## 4. Luồng hoạt động chính

```
Binance API → fetcher.py → Parquet cache (local)
                                    ↓
GET /api/ohlcv → indicators.py (slice-first) → Frontend
                                    ↓
         ChartController → DrawingManager → ReplayEngine
                                    ↓
                    Hit detection → ResultsPanel (per-trade P&L)
```

**Look-ahead bias prevention:** Backend nhận `date_end` param, slice DataFrame **trước** khi compute indicators. Frontend chỉ thấy data đến `current_bar_index`.

---

## 5. Kiến trúc hai hệ thống — Backtest Tool & Trading Bot

### Quan hệ giữa hai hệ thống

```
┌─────────────────────────────────┐     ┌──────────────────────────────────┐
│   BACKTEST TOOL (dự án này)     │     │   TRADING BOT (stock_quant_      │
│   Local machine                 │     │   tracker — Koyeb production)    │
│                                 │     │                                  │
│  Parquet cache (local)          │     │  Supabase Production DB          │
│  Supabase Backtest DB ──────────┼─────┼→ Supabase Production DB         │
│  (project riêng)                │     │  (import thủ công sau backtest)  │
└─────────────────────────────────┘     └──────────────────────────────────┘
```

### Tại sao dùng Supabase riêng cho backtest

Backtest tool sẽ generate data **giống hệt schema** của bot production nhưng vào **Supabase project riêng biệt**. Lý do:

- Tránh data backtest làm ô nhiễm learning memory của bot đang chạy live
- Có thể chạy nhiều backtest iteration mà không ảnh hưởng production
- Sau khi backtest đạt kết quả tốt → export ra → import thủ công vào production DB của bot

### Workflow tích hợp

```
1. Chạy backtest tool (local)
        ↓
2. Kết quả ghi vào Supabase Backtest DB (project riêng)
        ↓
3. Kiểm tra, validate data backtest
        ↓
4. Export CSV / SQL từ Supabase Backtest DB
        ↓
5. Import vào Supabase Production DB của bot
        ↓
6. Bot trên Koyeb đọc data mới và học từ historical cases đã backtest
```

---

## 6. Database Schema — Bot Production (docs/user_database)

Schema này thuộc **trading bot (stock_quant_tracker)** đang chạy trên Koyeb. Backtest tool phải generate data **theo đúng schema** này.

### Bảng bot dùng để học (2 bảng chính)

#### `signal_comparisons` — So sánh tín hiệu real-time

Bot dùng bảng này để so sánh quyết định của bot vs Claude verdict theo thời gian thực. Backtest tool sẽ populate bảng này với **historical simulated signals** — mỗi lần entry hit trong replay = 1 row.

```sql
CREATE TABLE signal_comparisons (
  id bigint generated always as identity primary key,
  timestamp bigint not null,           -- Unix ms của entry candle
  signal_id text not null unique,      -- backtest_{session_id}_{bar_index}
  type text not null,                  -- "LONG" hoặc "SHORT"
  bot_verdict text not null,           -- "BUY" / "SELL" / "HOLD"
  claude_verdict text,                 -- null khi chạy backtest (không có Claude review)
  claude_methodology text,             -- null khi backtest
  invalidation_condition text,         -- mô tả điều kiện SL: "SL tại {sl_price}"
  result text not null default 'pending', -- "win" / "loss" / "pending"
  follow text,                         -- "TP hit" / "SL hit" / null
  note text default '',                -- ghi chú thủ công sau khi review
  telegram_sent boolean default false, -- false khi backtest
  created_at timestamptz default now()
);
-- RLS: DISABLED (anon key có write access)
```

**Mapping từ backtest → signal_comparisons:**

| Backtest event | signal_comparisons field |
|---|---|
| Entry line hit tại bar X | `timestamp` = Unix ms của bar X |
| Session ID + bar index | `signal_id` = `"backtest_{session_id}_{bar_index}"` |
| Long/Short direction | `type` = "LONG" hoặc "SHORT" |
| Bot chạy với strategy | `bot_verdict` = "BUY" hoặc "SELL" |
| TP hit → result | `result` = "win", `follow` = "TP hit" |
| SL hit → result | `result` = "loss", `follow` = "SL hit" |
| Giá SL đặt tại | `invalidation_condition` = "SL tại {sl_price}" |

#### `signal_cases` — Learning memory cho Claude (Phase 3)

Bảng này bảo vệ hơn (RLS ENABLED, cần service role key). Chứa case studies đầy đủ để Claude học behavioral patterns. Backtest tool có thể populate bảng này với các **trade cases chất lượng cao** từ kết quả backtest.

```sql
CREATE TABLE signal_cases (
  signal_id             TEXT PRIMARY KEY,    -- khớp với signal_comparisons.signal_id
  signal_sent_at        TIMESTAMPTZ NOT NULL,
  market_regime         TEXT NOT NULL,       -- "bull" / "bear" / "sideways"
  setup_type            TEXT,               -- tên strategy, vd: "breakout_5m"
  claude_action         TEXT NOT NULL,      -- "BUY" / "SELL" / "HOLD"
  bot_action            TEXT NOT NULL,      -- action thực tế của bot/backtest
  claude_confidence     NUMERIC(5,2),       -- null khi backtest
  bot_score             NUMERIC(5,2),       -- score từ backtest (vd: win_rate %)
  outcome               TEXT,              -- "TP_HIT" / "SL_HIT"
  follow                TEXT,              -- ghi chú follow-up
  quality_rating        SMALLINT,          -- 1-5, đánh giá thủ công sau review
  reasoning_summary     TEXT NOT NULL,     -- mô tả điều kiện entry, vd: "EMA cross + volume spike"
  invalidation_condition TEXT NOT NULL,    -- điều kiện làm signal invalid
  metadata              JSONB,             -- dữ liệu bổ sung: entry_price, tp_price, sl_price, bars_to_exit
  created_at            TIMESTAMPTZ DEFAULT now()
);
-- RLS: ENABLED — dùng service role key để write
```

**Mapping từ backtest → signal_cases:**

| Backtest data | signal_cases field |
|---|---|
| signal_id từ signal_comparisons | `signal_id` (khớp FK) |
| Timestamp entry candle | `signal_sent_at` |
| Market condition tại thời điểm entry | `market_regime` |
| Tên strategy đang backtest | `setup_type` |
| Bot action khi backtest | `bot_action` = claude_action (không có Claude) |
| TP/SL hit | `outcome` |
| Điều kiện entry viết tay | `reasoning_summary` |
| Giá SL | `invalidation_condition` |
| `{entry, tp, sl, bars_to_exit, timeframe}` | `metadata` (JSONB) |

### Bảng bot KHÔNG dùng cho backtest

- `cost_log` — chỉ track chi phí API Claude (không liên quan backtest)
- `claude_conversation_history` — lịch sử hội thoại Claude (không liên quan)
- `budget_alert_state` — alert budget Claude (không liên quan)

---

## 7. Yêu cầu Phase 2: Supabase Integration

### Mục tiêu

Backtest tool (Phase 2) cần thêm khả năng:

1. **Ghi kết quả backtest** vào Supabase Backtest DB (project riêng, cùng schema)
2. **Export function** để lấy data từ Supabase Backtest DB ra CSV/SQL
3. Sau khi validate → user import thủ công vào Supabase Production DB của bot

### Config cần thêm (backend/settings.py)

```python
class Settings(BaseSettings):
    # ... existing fields ...
    
    # Phase 2: Supabase Backtest DB (project riêng, KHÔNG phải production bot DB)
    supabase_url: str = ""           # Supabase Backtest project URL
    supabase_key: str = ""           # anon key cho signal_comparisons (RLS off)
    supabase_service_key: str = ""   # service role key cho signal_cases (RLS on)
    supabase_enabled: bool = False   # flag bật tắt Supabase integration
```

### API endpoints cần thêm (Phase 2)

```
POST /api/backtest/export-to-supabase
  - Body: { session_id, include_signal_cases: bool }
  - Ghi toàn bộ trades của session vào Supabase Backtest DB
  - Return: { rows_written, supabase_url_to_review }

GET /api/backtest/export-csv
  - Query: ?session_id=xxx
  - Export session trades ra CSV (format tương thích signal_comparisons schema)
  - Dùng để import thủ công vào production DB
```

### Unique key strategy cho backtest data

Để tránh collision khi import vào production DB:

```
signal_id format: "backtest_{yyyymmdd}_{strategy_name}_{bar_index}"
Ví dụ: "backtest_20240315_breakout_4h_00042"
```

Bot production sẽ nhận ra prefix `"backtest_"` để:
- Filter riêng khi cần phân tích backtest vs live signals
- Không bao giờ conflict với live signal IDs

---

## 8. ADRs quan trọng (tóm tắt)

| ADR | Quyết định | Lý do |
|---|---|---|
| ADR-01 | Event-driven với Custom EventBus | Tránh global CustomEvent, typed payloads |
| ADR-02 | Parquet local cache | Offline-capable, zero cloud cost Phase 1 |
| ADR-03 | Schema contract: timestamp int64 Unix ms | Tương thích Supabase bigint của bot |
| ADR-04 | TypeScript + esbuild | Type safety cho event system, compile-time errors |
| ADR-05 | Async Binance fetch + SSE progress | Non-blocking, 5-phút fetch không block server |
| ADR-06 | Y-axis only coordinate system (MVP) | Horizontal lines only, scope tập trung |
| ADR-07 | pandas built-in indicators (slice-first) | Zero extra deps, look-ahead prevention |
| ADR-08 | uv thay vì pip+venv | Faster, reproducible |
| ADR-09 | main.py = app factory only | Tránh monolith, navigable |
| ADR-10 | pytest + pytest-asyncio | Backend unit tests critical paths |
| ADR-11 | Pydantic Settings centralized | Single source config, fail-fast startup |
| ADR-12 | Replay Engine ở Frontend TS | Real-time per-bar animation |
| ADR-13 | LRU-1 frontend data cache | Memory pressure (5m = ~100MB) |
| ADR-14 | `tickComplete` + `tradeAdded` events | Minimal event surface |
| ADR-15 | overmind + Procfile | Quản lý 2 processes dev (backend + esbuild watch) |
| ADR-20 | LocalStorage persist timeframe+dateRange only | Không persist drawings |

---

## 9. Các gaps kỹ thuật đã xác định (phải implement)

| Gap | Mức độ | Mô tả |
|---|---|---|
| Gap-1 | Critical | Slice DataFrame trước khi compute indicators (`df.iloc[:end_idx]`) |
| Gap-2 | Critical | Atomic Parquet write: write `.tmp` → rename |
| Gap-3 | High | Replay timing: delta-time accumulation với `requestAnimationFrame` |
| Gap-4 | High | Drawing coordinate bridge: re-render khi chart zoom/pan |
| Gap-5 | High | Async Binance fetch + SSE progress stream |
| Gap-9 | High | SSE heartbeat 15s + fallback polling nếu SSE mất |
| Gap-10 | High | Job lock per (symbol, timeframe) — 409 nếu fetch đang chạy |
| Gap-11 | High | Cancellable asyncio.Task dict, cleanup CancelledError |

---

## 10. Quy tắc implement (không được vi phạm)

1. **Look-ahead bias:** `df.iloc[:date_end_index]` TRƯỚC KHI gọi bất kỳ indicator nào
2. **Float comparison:** `Math.round(price * 100) / 100` tại mọi price hit detection
3. **Line snapshot:** Freeze giá entry/TP/SL tại thời điểm nhấn Play — không đọc lại DOM
4. **Atomic write:** Parquet write phải dùng `.tmp` → rename pattern
5. **Timezone:** UTC trong tất cả storage/calculation, chỉ convert UTC+7 tại display layer
6. **Commission:** 0.1% per side, hardcoded, bắt buộc included trong P&L
7. **Sample size warning:** Hiển thị warning khi số lệnh < 10
8. **main.py:** Chỉ chứa app factory + route registration — zero business logic
9. **Supabase (Phase 2):** Luôn dùng Supabase Backtest DB riêng, KHÔNG bao giờ ghi thẳng vào production bot DB
10. **signal_id prefix:** Mọi data từ backtest phải có prefix `"backtest_"` trong signal_id

---

## 11. Lịch sử quyết định quan trọng

- **2026-04-23:** Khởi tạo PRD, Architecture, UX Design
- **2026-04-23:** Loại bỏ pandas-ta, dùng pandas built-in indicators (ADR-07 revised)
- **2026-04-23:** TypeScript thay Vanilla JS (Gap-6, ADR-04)
- **2026-04-26:** Xác định yêu cầu tích hợp Supabase: backtest tool generate data theo schema bot, dùng Supabase project riêng để tránh ô nhiễm production data, export thủ công sau khi validate
