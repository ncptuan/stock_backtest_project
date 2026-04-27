---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'domain'
research_topic: 'Hệ thống Backtest Trading Strategy cho BTC/USDT bằng Python'
research_goals: 'Học và luyện tập kiến thức về trading — technical analysis thông qua một tool tự xây dựng'
user_name: 'Narron'
date: '2026-04-23'
web_research_enabled: true
source_verification: true
---

# Research Report: Domain - Crypto Backtest System

**Date:** 2026-04-23
**Author:** Narron
**Research Type:** Domain

---

## Research Overview

Nghiên cứu domain về xây dựng hệ thống backtest trading strategy cho BTC/USDT bằng Python, phục vụ mục tiêu học tập và luyện tập kiến thức technical analysis.

---

## Domain Research Scope Confirmation

**Research Topic:** Xây dựng hệ thống backtest Trading Strategy cho BTC/USDT bằng Python
**Research Goals:** Học và luyện tập kiến thức về trading — technical analysis (MA, RSI, MACD...) thông qua một tool tự xây dựng

**Domain Research Scope:**

- Ecosystem & Tools — Các framework Python phổ biến cho backtest
- Data Sources — Nguồn lấy dữ liệu BTC/USDT
- Core Concepts — Các khái niệm cơ bản cần nắm
- Architecture Patterns — Cấu trúc code cho hệ thống backtest cá nhân
- Strategy mẫu — Các chiến lược phổ biến để luyện tập

**Research Methodology:**

- All claims verified against current public sources
- Multi-source validation for critical domain claims
- Confidence level framework for uncertain information
- Comprehensive domain coverage with industry-specific insights

**Scope Confirmed:** 2026-04-23

---

<!-- Content will be appended sequentially through research workflow steps -->

---

## Industry Analysis

### Market Size và Tăng Trưởng

Thị trường Algorithmic Trading toàn cầu đang tăng trưởng mạnh, trực tiếp thúc đẩy nhu cầu về công cụ backtest:

- **Quy mô thị trường 2026:** ~$20–27 tỷ USD (tùy theo phương pháp đo lường của từng hãng nghiên cứu)
- **CAGR dự báo:** 9.3%–14.4% đến 2030
- **Thị trường Automated Algo Trading:** $27.17B (2026) → $44.55B (2030), CAGR 13.2%
- **Crypto là động lực tăng trưởng chính:** Bitcoin với khối lượng giao dịch khổng lồ và biến động cao tạo ra nhiều cơ hội cho algorithmic strategy

_Source: [Coherent Market Insights](https://www.coherentmarketinsights.com/market-insight/algorithmic-trading-market-2476), [Yahoo Finance](https://finance.yahoo.com/news/algorithmic-trading-analysis-report-2026-090900902.html)_

### Python Backtesting Framework Landscape

Ecosystem Python cho backtest crypto hiện tại (2026) khá trưởng thành, với các framework nổi bật:

| Framework | Ưu điểm | Nhược điểm | Phù hợp với |
|-----------|---------|-----------|------------|
| **VectorBT** | Cực nhanh (Numba), xử lý 1M orders ~70-100ms, test hàng nghìn strategy song song | Đường cong học tập dốc, abstraction phức tạp | Optimization, research |
| **Backtrader** | OOP thân thiện, mirror cách trader suy nghĩ, tài liệu phong phú | Đã ngừng phát triển chính từ 2018, chậm hơn | Học cơ bản, prototype |
| **Freqtrade** | Open-source hoàn chỉnh: backtest + optimization + live trading, community lớn | Phức tạp hơn để setup | Muốn tiến tới live trading |
| **Zipline** | Từ Quantopian, battle-tested | Khó maintain, ít hỗ trợ crypto | Stock market |

**Khuyến nghị cho mục tiêu học tập:** Bắt đầu với **Backtrader** (dễ học concept) hoặc **tự xây** engine đơn giản (hiểu sâu hơn), sau đó chuyển sang VectorBT khi cần performance.

_Source: [python.financial](https://python.financial/), [Backtrader vs VectorBT - Greyhound Analytics](https://greyhoundanalytics.com/blog/vectorbt-vs-backtrader/), [DEV Community](https://dev.to/linou518/backtrader-vs-vnpy-vs-qlib-a-deep-comparison-of-python-quant-backtesting-frameworks-2026-3gjl)_

### Data Sources cho BTC/USDT

Các nguồn dữ liệu lịch sử miễn phí, ổn định:

| Nguồn | Loại | Đặc điểm | Python Support |
|-------|------|---------|---------------|
| **Binance API** | REST API | OHLCV theo timeframe, miễn phí, không cần tài khoản với gói public | `python-binance`, `binance-historical-data` |
| **CCXT** | Thư viện tổng hợp | Hỗ trợ 100+ exchange, chuẩn hóa format dữ liệu | `ccxt` (pip) |
| **CryptoDataDownload** | CSV download | 1100+ assets, daily/hourly/minute, free | Đọc trực tiếp bằng pandas |
| **CoinGecko API** | REST API | Free tier: 30 calls/min, 10k calls/month | `pycoingecko` |

**Lựa chọn tối ưu cho học tập:** `ccxt` + Binance — một dòng code lấy được OHLCV bất kỳ timeframe nào, chuẩn hóa format cho mọi exchange.

_Source: [CCXT GitHub](https://github.com/ccxt/ccxt), [CryptoDataDownload](https://www.cryptodatadownload.com/), [CoinGecko API](https://www.coingecko.com/en/api)_

### Core Concepts Cần Nắm (Học Từ Backtest)

Những khái niệm quan trọng mà việc tự xây hệ thống sẽ giúp bạn hiểu sâu:

**Về Bias và Lỗi Phổ Biến:**
- **Overfitting/Curve-fitting:** Tối ưu quá nhiều parameters → chạy tốt trên data cũ, thất bại live. Dấu hiệu: return hàng nghìn %, Sharpe ratio > 3.0 → nghi ngờ ngay
- **Look-ahead bias:** Vô tình dùng thông tin tương lai (ví dụ: dùng giá close của nến hiện tại để vào lệnh ngay lúc nến đó)
- **Slippage & Commission:** Một strategy 20% return thực tế chỉ còn 8% sau phí 0.5% slippage + 0.1% commission mỗi lệnh

**Về Phương pháp Kiểm Tra Robust:**
- **Out-of-sample testing:** Dùng 70% data train, 30% còn lại test — không được chỉnh gì sau khi thấy kết quả 30%
- **Walk-forward analysis:** Chuẩn vàng — train period 1 → test period 2 → train period 1+2 → test period 3...
- **Monte Carlo simulation:** Xáo ngẫu nhiên thứ tự 1000 lần để kiểm tra edge có thật hay do may mắn

**Metrics cần theo dõi:** Win rate, Profit Factor (>1.5 tốt, >2.0 xuất sắc), Max Drawdown, Sharpe Ratio, Expectancy

_Source: [TradeZella Complete Guide](https://www.tradezella.com/blog/backtesting-trading-strategies), [LuxAlgo Backtesting Traps](https://www.luxalgo.com/blog/backtesting-traps-common-errors-to-avoid/), [Coin Bureau Crypto Backtest Guide](https://coinbureau.com/guides/how-to-backtest-your-crypto-trading-strategy)_

### Competitive Dynamics trong Crypto Backtest Tools

- **Open-source dominates:** Hầu hết trader cá nhân dùng open-source (Backtrader, Freqtrade, VectorBT)
- **Rào cản gia nhập thấp:** Python + free data API = bắt đầu được ngay
- **Tự xây là lựa chọn giáo dục tốt nhất:** Nhiều trader kinh nghiệm khuyên nên tự viết engine cơ bản trước khi dùng framework — hiểu sâu hơn về cách backtest hoạt động
- **Community mạnh:** r/algotrading, QuantConnect community, Freqtrade Discord

---

## Competitive Landscape

### Key Players và Positioning

Hệ sinh thái công cụ backtest crypto chia thành 4 nhóm chính:

**Nhóm 1: Open-source Python Libraries (phù hợp nhất để học)**

| Tool | Stars GitHub | Điểm mạnh | Điểm yếu |
|------|-------------|-----------|---------|
| **Freqtrade** | ~35k | Backtest + optimization + live trading trong một, community lớn, docs tốt | Setup phức tạp hơn cho người mới |
| **VectorBT** | ~4k | Tốc độ cực nhanh, parameter optimization hàng loạt | Learning curve dốc, abstraction khó hiểu |
| **Backtrader** | ~15k | OOP thân thiện, nhiều ví dụ tutorial | Ngừng active development từ 2018 |
| **Jesse** | ~6k | Thiết kế cho crypto, dễ đọc code | Ít phổ biến hơn |

**Nhóm 2: Cloud Platforms (institutional grade)**
- **QuantConnect (Lean Engine):** Cloud-based, data built-in, broker integration — quá phức tạp cho mục tiêu học tập
- **Backtest.io, StratBase.ai:** SaaS, không cần code — không phù hợp vì bạn muốn tự xây

**Nhóm 3: Exchange-integrated (Binance, Bybit built-in tools)**
- Hữu ích để verify kết quả nhưng không thể customize strategy logic

**Nhóm 4: Tự xây (Self-built) — Recommended cho Narron**
- Hoàn toàn kiểm soát logic
- Hiểu sâu từng bước
- Không bị ràng buộc bởi API của framework

_Source: [StratBase Best Crypto Backtesting Platforms 2026](https://stratbase.ai/en/blog/best-crypto-backtesting-platforms), [Python Backtesting Landscape 2026](https://python.financial/), [Awesome Systematic Trading](https://github.com/paperswithbacktest/awesome-systematic-trading)_

### Architecture: Event-Driven vs Vectorized

Đây là lựa chọn kiến trúc quan trọng nhất khi tự xây:

**Vectorized (pandas/NumPy-based):**
```
df['signal'] = where(df['ma_fast'] > df['ma_slow'], 1, -1)
df['returns'] = df['signal'].shift(1) * df['price_pct_change']
```
- ✅ Viết nhanh, dễ prototype
- ✅ Chạy nhanh hơn (NumPy operations)
- ❌ Dễ bị look-ahead bias nếu không cẩn thận
- ❌ Khó mô phỏng realistic: partial fills, dynamic position sizing

**Event-Driven (bar-by-bar loop):**
```
for bar in data:
    signal = strategy.on_bar(bar)
    if signal: portfolio.execute(signal)
```
- ✅ Gần với live trading hơn, không có look-ahead bias
- ✅ Dễ mở rộng: thêm slippage, commission, risk management
- ❌ Chậm hơn với dataset lớn
- ❌ Phức tạp hơn để viết ban đầu

**Khuyến nghị cho mục tiêu học:** Bắt đầu bằng **Vectorized** để hiểu flow nhanh → sau đó rebuild bằng **Event-Driven** để hiểu sâu hơn về execution reality.

_Source: [QuantStart Event-Driven Backtesting](https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-I/), [Interactive Brokers: Vector vs Event-Based](https://www.interactivebrokers.com/campus/ibkr-quant-news/a-practical-breakdown-of-vector-based-vs-event-based-backtesting/)_

### Strategy Mẫu để Luyện Tập với BTC/USDT

Các strategy phổ biến nhất để bắt đầu (từ đơn giản → phức tạp):

1. **MA Crossover (đơn giản nhất)**
   - Buy: EMA20 cắt lên trên SMA50
   - Sell: EMA20 cắt xuống dưới SMA50
   - Học được: signal generation, entry/exit logic

2. **RSI Mean Reversion**
   - Buy: RSI < 30 (oversold)
   - Sell: RSI > 70 (overbought)
   - Học được: oscillator-based signals, market regime awareness

3. **MACD + RSI Combined**
   - Kết hợp 2 indicator để lọc tín hiệu giả
   - Học được: signal filtering, reducing false positives

4. **Bollinger Bands Breakout**
   - Buy: giá breakout khỏi upper band với volume cao
   - Học được: volatility-based strategies

**Python library cho indicators:** `ta-lib` (150+ indicators) hoặc `pandas-ta` (dễ install hơn trên Mac/Windows)

_Source: [Machine Learning How To: Backtrader Crypto Strategy](https://machinelearninghowto.com/backtesting-a-strategy/), [Medium: MACD + RSI Combined Strategy](https://medium.com/@redsword_23261/a-combined-strategy-with-macd-and-rsi-971aa1ef9b38)_

### Recommended Architecture cho Hệ Thống Của Narron

Dựa trên mục tiêu học tập, đây là architecture đề xuất:

```
stock_backtest_project/
├── data/
│   ├── fetcher.py        # CCXT + Binance, lấy OHLCV
│   └── cache/            # Lưu data local để tránh gọi API lại
├── indicators/
│   └── technical.py      # MA, RSI, MACD, Bollinger...
├── strategies/
│   ├── base.py           # Abstract base class
│   ├── ma_crossover.py   # Strategy 1
│   └── rsi_strategy.py   # Strategy 2
├── backtest/
│   ├── engine.py         # Core backtest loop
│   ├── portfolio.py      # Position tracking, P&L
│   └── metrics.py        # Sharpe, drawdown, win rate...
├── reports/
│   └── visualizer.py     # Matplotlib/Plotly charts
└── main.py               # Entry point
```

**Stack đề xuất:**
- `ccxt` — lấy data
- `pandas` + `numpy` — xử lý data
- `pandas-ta` hoặc `ta-lib` — indicators
- `matplotlib` hoặc `plotly` — visualization
- `pytest` — test strategy logic

---

## Regulatory Requirements & Technical Standards

### Binance API — Giới Hạn Kỹ Thuật Cần Biết

Khi xây dựng data fetcher, cần nắm rõ các giới hạn này để tránh bị ban IP:

| Giới hạn | Giá trị | Hậu quả khi vượt |
|---------|---------|-----------------|
| **Request weight/phút** | 1200 weights | 429 (Too Many Requests) |
| **OHLCV calls** | 600 calls/phút (2 weights/call) | IP bị throttle |
| **Bulk calls** | 6200 calls/5 phút | Rate limit |
| **Candles/request** | Tối đa **1000 candles** | Phải paginate cho data dài |
| **IP ban** | Lần đầu: vài giây → tái phạm: 3 ngày | — |

**Cách xử lý trong Python (CCXT):**
```python
exchange = ccxt.binance({'enableRateLimit': True})  # Tự động handle rate limit
```

Để lấy toàn bộ lịch sử BTC/USDT (1000+ candles), cần implement **pagination** — lấy 1000 candles một lần, dịch chuyển `since` timestamp, lặp lại cho đến khi đủ data.

_Source: [CCXT Manual](https://github.com/ccxt/ccxt/wiki/manual), [Manuel Levi: CCXT >1000 rows](https://manuellevi.com/how-to-get-more-data-price-data-using-ccxt/), [DEV Community: Binance Historical Data Guide](https://dev.to/pi19404/a-technical-guide-to-downloading-and-managing-binance-historical-crypto-market-data-d82)_

### Data Quality Standards

Đây là những tiêu chuẩn kỹ thuật mà bất kỳ backtest nghiêm túc nào cũng phải đảm bảo:

**Về Data Integrity:**
- Data phải đúng field names, field order, và data types — sai một trong ba là kết quả backtest vô nghĩa
- Kiểm tra missing candles (exchange đôi khi skip candles ở timeframe thấp)
- Kiểm tra duplicate timestamps trước khi chạy backtest
- Lưu data local (CSV hoặc SQLite) sau khi tải để tránh gọi API lại

**Về Look-ahead Bias — Lỗi phổ biến nhất khi tự code:**
```python
# SAI — dùng giá close của nến hiện tại để vào lệnh ngay
signal = df['close'] > df['ma']
df['position'] = signal  # Bias!

# ĐÚNG — shift(1): chỉ biết tín hiệu sau khi nến đóng
df['position'] = signal.shift(1)
```

**Về Realistic Cost Modeling:**
- Binance Spot BTC/USDT: phí maker/taker = 0.1% mỗi chiều (0.2% round-trip)
- Slippage ước tính: 0.05–0.1% cho BTC/USDT (market order)
- Không tính phí = kết quả backtest inflated, không phản ánh thực tế

### Performance Metrics Standards (Industry Benchmarks)

| Metric | Threshold tốt | Threshold xuất sắc | Red flag |
|--------|--------------|-------------------|---------|
| **Sharpe Ratio** | > 1.0 | > 1.5 | > 3.0 (nghi overfitting) |
| **Max Drawdown** | < 20% | < 10% | > 30% |
| **Profit Factor** | > 1.5 | > 2.0 | > 5.0 (nghi overfitting) |
| **Win Rate** | > 45% | > 55% | Không đủ nếu R:R thấp |
| **Số lệnh test** | > 50 | > 100 | < 30 (không đủ statistical significance) |

_Source: [Bitsgap Crypto Backtesting Guide 2025](https://bitsgap.com/blog/crypto-backtesting-guide-2025-tools-tips-and-how-bitsgap-helps), [Blockchain Council: Backtesting AI Crypto Safely](https://www.blockchain-council.org/cryptocurrency/backtesting-ai-crypto-trading-strategies-avoiding-overfitting-lookahead-bias-data-leakage/), [Stoic.ai Backtesting Guide](https://stoic.ai/blog/backtesting-trading-strategies/)_

### Implementation Checklist cho Narron

Những việc **bắt buộc** phải làm đúng ngay từ đầu:

- [ ] **Shift tín hiệu đúng cách** — luôn dùng `signal.shift(1)` khi apply vào giá
- [ ] **Tính phí giao dịch** — ít nhất 0.1% mỗi chiều
- [ ] **Cache data local** — tránh gọi API mỗi lần chạy backtest
- [ ] **Paginate khi lấy data** — Binance giới hạn 1000 candles/request
- [ ] **Out-of-sample split** — giữ 20–30% data cuối để test sau khi optimize
- [ ] **Dùng ít parameters** — mỗi parameter thêm vào tăng nguy cơ overfitting

---

## Technical Trends và Innovation (2025–2026)

### Emerging Technologies trong Crypto Trading

**AI/ML tích hợp vào backtesting — xu hướng lớn nhất 2025–2026:**
- AI đã chiếm ~65% crypto trading volume năm 2026
- Reinforcement Learning (RL): model tự tối ưu entry/exit/position sizing rules
- ML models (LSTM, Random Forest, XGBoost) được dùng để predict price direction, sau đó backtest predictions như một strategy
- Explainable AI (XAI) nổi lên để giải thích *tại sao* model ra quyết định — quan trọng khi debug

**Với mục tiêu học tập của Narron:** AI/ML nên là phase 2. Trước tiên, làm chủ backtesting dựa trên rule-based (technical indicators) — đây là nền tảng để hiểu AI/ML sau này có ý nghĩa.

_Source: [Blockchain Council: AI Crypto Trading](https://www.blockchain-council.org/cryptocurrency/backtesting-ai-crypto-trading-strategies-avoiding-overfitting-lookahead-bias-data-leakage/), [Medium: ML Trading 2026](https://medium.com/@sandrarobinson264evsusanb989fy/machine-learning-trading-2026-top-ai-algorithms-for-crypto-profits-be30a607f12f)_

### Digital Transformation — Tools Mới Đáng Chú Ý

**Framework nổi bật cho người mới (2025–2026):**
- **Backtesting.py** — lightweight, dễ học, visualizer tích hợp sẵn, phù hợp người mới
- **Lumibot** — open-source, cover toàn bộ pipeline từ backtest → paper trade → live trading
- **Jesse** — thiết kế chuyên cho crypto, API rất clean và Pythonic

**Trend quan trọng: Paper Trading trước Live**
```
Backtest → Paper Trade (real-time, no real money) → Live (25–50% size) → Full size
```
Hầu hết platform 2026 đều tích hợp paper trading mode — chạy strategy với real-time data nhưng không dùng tiền thật.

_Source: [LearnDataSci: Algo Trading Crypto Bot Python](https://www.learndatasci.com/tutorials/algo-trading-crypto-bot-python-strategy-backtesting/), [CoinGecko: Backtesting Crypto Python](https://www.coingecko.com/learn/backtesting-crypto-trading-strategies-python)_

### Challenges và Risks Cần Lưu Ý

| Challenge | Mô tả | Cách giải quyết |
|-----------|-------|----------------|
| **Overfitting** | Optimize quá nhiều → fail live | Giữ < 5 parameters, out-of-sample test |
| **Look-ahead bias** | Dùng thông tin tương lai | Luôn `shift(1)` tín hiệu |
| **Data gaps** | Binance thiếu candles ở 1m timeframe | Dùng 1h hoặc 4h cho bắt đầu |
| **Transaction costs** | Bỏ qua phí = kết quả ảo | Tính 0.1% mỗi chiều từ đầu |
| **Market regime change** | Strategy tốt 2020 có thể fail 2024 | Test nhiều giai đoạn (bull/bear/sideways) |

_Source: [Stoic.ai Backtesting Guide](https://stoic.ai/blog/backtesting-trading-strategies/), [Zignaly: Algorithmic Crypto Trading](https://zignaly.com/crypto-trading/algorithmic-strategies/algorithmic-crypto-trading)_

---

## Recommendations

### Technology Adoption Strategy cho Narron

1. **Bắt đầu tự xây** — đừng dùng framework ngay, hiểu từ gốc
2. **Stack tối giản:** `ccxt` + `pandas` + `pandas-ta` + `matplotlib` — đủ dùng cho toàn bộ Phase 1 và 2
3. **BTC/USDT 1h timeframe** — đủ data, ít noise hơn 1m, dễ experiment
4. **Dùng Binance public API** — không cần account, không cần API key cho data lịch sử

### Innovation Roadmap

```
Tuần 1–2:  Data pipeline hoàn chỉnh (fetch → cache → load)
Tuần 3–4:  Backtest engine v1 (vectorized) + MA Crossover
Tuần 5–6:  Thêm metrics, visualizer, fix look-ahead bias
Tuần 7–8:  RSI + MACD strategies, so sánh kết quả
Tuần 9–12: Event-driven engine, out-of-sample testing
Sau đó:    Paper trading, ML integration (optional)
```

### Risk Mitigation

- **Code review bản thân:** Mỗi strategy viết xong, đọc lại từng dòng kiểm tra look-ahead bias
- **Sanity check:** Buy-and-hold BTC từ 2020–2024 cho ~500% return — nếu strategy của bạn beat quá nhiều, hãy nghi ngờ
- **Peer comparison:** Tham khảo r/algotrading để benchmark kết quả
