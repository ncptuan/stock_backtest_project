# Deferred Work

## Deferred from: code review of p1-6-2-last-used-settings-persistence-localstorage (2026-05-03)

- save() race on page unload — 500ms debounce via setTimeout; if user changes settings and closes tab within 500ms, pending save lost because setTimeout callbacks don't fire reliably during page teardown — defer, would need `beforeunload` flush handler
- Debounce race: drawing save vs doLoad save — both use same 500ms debounce in SettingsManager.save(); if drawing:lineChanged fires during async doLoad, whichever call schedules last wins — mitigated by handleLoad fix preserving drawings, defer
- No runtime validation of `drawings` shape on load — `as Partial<PersistedSettings>` cast only checks timeframe/dateStart/dateEnd truthiness; corrupt localStorage with `drawings: { entry: "abc" }` passes through to `drawingManager.setLine()` creating NaN-price line — setLine handles NaN gracefully, defer
- Multi-tab write conflict — no `storage` event listener on `btcReplay_lastSettings`; two tabs silently overwrite each other's settings on every debounce tick — explicit per scope ("Multiple tabs: no sync"), defer

## Deferred from: code review of p1-6-1-empty-state-va-getting-started-guide (2026-05-03)

- Zero bars success feedback — API returns 0 bars via chart:dataLoaded → blank chart with no empty state message; hideEmptyState removes ghost overlay, user sees nothing — rare edge case (most fetches return bars), defer
- Ghost hidden on programmatic `setLine` during settings restore — `drawing:lineChanged` fires from `restoreDrawings()`, hiding ghost drawings prematurely — no visual impact: settings restore runs after `chart:dataLoaded` which already removes the ghost overlay, defer
- `_showEmptyState` calls `setData([])` destroying existing chart data — intentional design for error state (shows "no data" message on blank chart), acceptable, defer
- `chart:loadError` event has no `chart:loadRecovered` counterpart — ghost overlay stays hidden after error even if subsequent load succeeds — mitigated by `chart:dataLoaded` removing ghost overlay entirely, defer
- ChartController error overlay uses inline `style.cssText` instead of CSS class — hardcoded z-index:15, positioning — cosmetic inconsistency with ghost overlay using CSS class, defer

## Deferred from: code review of p1-5-5-session-summary-va-sample-size-warnings (2026-05-03)

- reset() summary flash — showSummary fires before clearTradeList in same synchronous tick, zero-frame DOM batch, not visible to user, defer
- LONG-only win/loss heuristic in auto-close (reset/advanceBar/stepForward) — checkHits always passes LONG, SHORT entry path doesn't exist, dormant, defer to SHORT support scope
- .summary-warning--info CSS class unused in TypeScript source — was used in stale compiled output, harmless orphan, defer
- showEmptyMessage() targets #results-empty-msg while showSummary() targets #results-summary — different DOM elements, both exist in HTML, visual placement acceptable, defer
- Rounding asymmetry near zero P&L — Math.round(-0.004*100)/100 = 0 not -0.01, displays as "+0.00%", JS standard behavior, cosmetic, defer

## Deferred from: code review of p1-5-4-per-trade-results-panel-realtime-update (2026-05-03)

- Forced-close during reset: trade row added via tradeCompleted then immediately cleared via session:reset — single-threaded JS, no visible flash to user, defer
- innerHTML with unvalidated string fields (direction, exitType) — all data from type-safe TradeCompletedPayload, no user-controlled input, defer
- DOM listener leak on row removal — anonymous mouseenter/mouseleave closures not detached, modern GC collects when node removed, defer
- UTC+7 hardcoded timezone with no label on main time column — single-user app in VN, consistent, defer
- Entry time shown in Time column (not exit time) — audit trail hover shows exit bar OHLC, design choice, defer

## Deferred from: code review of p1-5-3-visual-trade-markers-tren-chart (2026-05-03)

- reset() forced-close misclassifies exit marker — compares closePrice vs entryPrice to determine TP/SL marker, but price between entry and TP shows TP marker at wrong price — semantic issue (forced-close = win/loss, not literal TP/SL hit), defer
- Pulse animation stays at fixed pixel position during chart zoom/pan — 0.6s window, cosmetic, low user impact, defer
- No pulse feedback for off-screen markers — LW markers still render at correct position, just no DOM pulse animation, defer
- 1-frame marker flicker on trade hit — addTradeMarker runs between revealBar calls, marker briefly invisible until next re-render, defer
- `TradeMarker.price` stored but never used in LW markers rendering — `belowBar`/`aboveBar` positions ignore price field — dead data, cosmetic, defer
- Duplicate type definition `TradeMarkerType` vs EventMap inline union — can drift if one updated without other — low risk, defer

## Deferred from: code review of p1-5-2-pnl-calculation-va-commission (2026-05-03)

- SHORT direction P&L formula inverted — `(exit-entry)/entry*100` produces negative for SHORT wins — dormant (checkHits hardcodes LONG), defer to SHORT support scope
- Negative P&L rounding asymmetry — JS `Math.round` rounds .5 toward +Infinity — `-1.665` → `-1.66` not `-1.67` — consistent JS behavior, cosmetic, defer
- Division by zero if entryPrice = 0 — `normalize()` rounds prices < 0.005 to 0.00 — unreachable with real BTC data, defer

## Deferred from: code review of p1-5-1-hit-detection-engine-entry-tp-sl-logic (2026-05-03)

- SHORT direction dead code — `openTrade` accepts `'SHORT'` but `checkHits` always passes `'LONG'`, TP/SL logic is LONG-only (high >= tp, low <= sl) — needs full SHORT path (low <= entry, reversed TP/SL), design scope, defer
- Doji candle (close === open) defaults to SL on same-bar TP+SL — `isBullish = close > open` is false for doji, arbitrary tiebreak, rare on BTC/USDT, defer
- TP/SL === 0 always hits — `high >= 0` is always true, no guard — pre-flight checklist validation should prevent, defer
- Entry === TP degenerate setup — zero-profit trade minus commission — validation scope, defer
- `openTrade` signature change (now accepts fillPrice, tpPrice, slPrice instead of LineSnapshot) — no external callers found, internal only, defer

## Deferred from: code review of p1-4-5-keyboard-shortcuts (2026-05-03)

- `e.preventDefault()` on arrow keys runs unconditionally — blocks native scroll/page navigation in setup mode when no replay active — defer to UX polish sprint
- Focus guard misses `[contenteditable]` elements — no contenteditable exists in app today — defer
- Missing `e.preventDefault()` on letter-key shortcuts (1/2/3/E/T/S/R/?) — no contenteditable today, defensive — defer
- `?` key layout dependency — `e.key === '?'` may differ on non-US keyboard layouts (AZERTY, QWERTZ) — single-user app, defer

## Deferred from: code review of p1-4-4-pre-flight-checklist (2026-05-03)

- innerHTML reflows on every `drawing:lineChanged` — no child event listeners on checklist items today, perf sprint if drag becomes laggy, defer
- Button disabled state + click handler guard redundancy — cosmetic duplication, both correct, defer
- Fingerprint not hidden on replay engine error — defensive cleanup, no current error path triggers this, defer
- `toLocaleString('en-US')` output inconsistency across non-US browser environments — cosmetic, single-user app, defer

## Deferred from: code review of p1-4-3-reset-giu-drawings (2026-05-03)

- Summary flash on reset — `replayStateChanged:stopped` fires before `session:reset`, `showSummary()` renders empty-state message briefly then cleared — event ordering design tradeoff, defer
- Zoom preservation drops range when zero-width `savedRange` (`{from:5, to:5}`) — fails `to > from` guard, chart auto-fits — edge case on uninitialized chart, defer
- `revealBar(0)` renders full dataset then narrows viewport — perf spike for 100k+ bars — defer to perf sprint
- Visual flash between IndicatorOverlay/VolumeOverlay restore and main chart restore on reset — single-frame inconsistency on slow renders, defer

## Deferred from: code review of p1-4-2-3-toc-do-slow-normal-fast (2026-05-03)

- `revealBar(0)` renders full data for timeScale calibration — brief flash before viewport snaps to bar 0 — design tradeoff, LW Charts needs full range for scale, defer
- HoverTooltip double O(n) scan per crosshair event — `getBarByTime()` + `findIndex()` on full cache — perf optimization sprint with Map<number, number> index, defer
- Bar index 0 never emits `replay:barAdvanced` from `advanceBar()` — increments before emit, fixed by initial emit in `start()` — by design, defer

## Deferred from: code review of p1-4-1-play-pause-replay-engine (2026-05-03)

- SHORT direction dead code — `checkHits()` hardcodes `'LONG'`, no SHORT entry path exists — Epic P1-5 scope (hit detection refinement), defer
- Entry price uses `lineSnapshot.entry` instead of next-bar open price — produces incorrect P&L — Epic P1-5 scope (fill price logic), defer
- Entry at last bar silently dropped — `nextBar` is undefined, no trade opens, no user feedback — Epic P1-5 edge case, defer
- TP=Entry or SL=Entry after normalization produces degenerate trades — no validation prevents equal levels — Epic P1-5 validation, defer
- Background tab RAF still advances bars at ~1/sec — 10 min background = ~600 bars advanced — UX enhancement, could auto-pause on `visibilitychange`, defer
- `reset()` calls `handleTradeClose(currentIndex, 'loss')` with stale index — acceptable semantics (fires loss event before clearing state), defer

## Deferred from: code review of p1-3-5-toast-undo-khi-switch-timeframe (2026-05-03)

- Unhandled async promise in `onUndo` callback — doLoad is async but onUndo is () => void, promise silently dropped if data load fails — doLoad has internal error handling, single-user app, defer
- Rapid switches race — multiple `doLoad()` fire-and-forget, whichever resolves last wins regardless of user intent — needs async AbortController, defer to performance sprint
- Ctrl+Z triggers oldest undo toast not newest — `querySelector` returns first DOM match — max 1 undo toast at a time (dismiss on new switch), not a practical issue, defer

## Deferred from: code review of p1-3-4-rr-ratio-live-khi-drag (2026-05-03)

- Negative R:R format: AC8 says `"R:R = 1:-2.30"` but code renders `"⚠ R:R = 1:2.30"` (absolute value + warning) — Dev Notes explicitly design this format, spec conflict resolved in favor of Dev Notes, defer
- Short-trade R:R assumes LONG direction — negative rr = invalid setup, shown with ⚠ warning, by design per spec, defer
- `risk === 0` strict float equality — prices snap to $0.01 multiples, exact zero is correct guard, defer
- Badge clips on narrow containers — min-width 1024px in CSS prevents in practice, defer
- Badge can overlap price labels near chart bottom — cosmetic, max 3 labels, defer

## Deferred from: code review of p1-3-3-price-label-va-mau-phan-biet (2026-05-03)

- Label connector line for displaced labels — when overlap prevention shifts label far from its real line Y, user can't tell which label belongs to which line — UX enhancement, defer
- `rectX` clamping on narrow containers — very long price text on narrow panel could push label off-canvas left — `min-width: 1024px` in CSS prevents this in practice, defer
- `_formatPrice` NaN/Infinity guard — upstream data validated by backend, defer
- Sort determinism for same-price lines — add secondary sort by type for deterministic label order when two lines share exact price — cosmetic, defer
- `toLocaleString` perf on every redraw — max 3 calls per frame for 3 labels, acceptable for MVP, defer

## Deferred from: code review of p1-3-2-drag-to-move-va-delete-line (2026-05-03)

- Delete during active drag is a benign no-op (deleteSelected returns false, no selectedType) — could add UX: cancel drag instead, defer
- Rapid container resize during drag causes cosmetic handle flicker (handle recreated at new position mid-drag) — no crash, `getBoundingClientRect()` recomputes correctly, defer
- Handle mousedown listener lifecycle — confirmed correct, old listeners GC'd with removed elements, no action needed

## Deferred from: code review of p1-3-1-entry-tp-sl-line-drawing (2026-05-03)

- RR calculation assumes LONG direction — `_calcRR` computes `reward = tp - entry`, `risk = entry - sl`; for SHORT both are negative yielding positive ratio, but `_drawRRBadge` warning (`rr < 0`) never triggers for misconfigured SHORT — UX polish, defer
- Handle mousedown listeners in `_updateHandles` not cleaned up in `destroy()` — arrow function closures keep DrawingManager alive until GC — minor, defer
- `isUpdating` is public mutable field on CoordinateTranslator — any code can read/write — encapsulation concern, defer
- freeze/unfreeze only react to 'playing'/'stopped' states — 'paused' leaves handles frozen with no restore path — Epic P1-4 scope, defer

## Deferred from: code review of p1-2-5-volume-bars-toggle (2026-05-03)

- Scale margins always allocated (bottom 20% of chart pane) even when volume is OFF — LW Charts hides empty scales, defer
- `currentBars` shared reference (direct assignment from getCachedBars) — `_renderBars` already copies via `[...bars]`, defer
- `destroy()` doesn't reset `visible` state — inconsistent object state after destroy, defer
- Toggle event listener never removed — single-user app, no re-init pattern, defer
- Hardcoded rgba color strings bypass design token system — LW Charts JS API doesn't support CSS variables, defer
- Toggle state not persisted to localStorage — intentional per scope, no AC requires it, defer
- Timestamp rounding mismatch (raw /1000 vs Math.round) — Binance timestamps are whole-second ms multiples, defer

## Deferred from: code review of p1-2-4-ma-ema-overlay-toggle (2026-05-03)

- `destroy()` silent failure when chart already destroyed — single-user app, page unload cleans up, defer
- `currentBars` stores direct reference to cached data (shared mutation risk) — `_renderBars` already copies via `[...bars]`, defer
- `init()` silently no-ops if `getChart()` returns undefined — ordering enforced by main.ts init sequence, defer
- Hardcoded colors (#2f81f7, #d29922) in IndicatorOverlay.ts — LW Charts JS API doesn't support CSS variables, defer
- Toggle state not persisted to localStorage — intentional per scope, no AC requires it, defer
- `chart:dataLoaded` event subscription bypassed — direct call in doLoad() works correctly, defer
- `setData([])` on hide leaves series on price scale — cosmetic, series invisible with empty data, defer
- buildLineData timestamp/1000 precision mismatch with _renderBars Math.round — Binance timestamps are whole-second ms multiples, defer

## Deferred from: code review of p1-2-3-ohlcv-hover-tooltip (2026-05-03)

- `innerHTML` on every crosshair move — `formatPrice` returns numeric strings via `toLocaleString`, safe today (no XSS from numbers), defer perf optimization to throttle/requestAnimationFrame sprint
- `getBarByTime` O(n) linear scan on every hover event — should use `Map<number, OHLCVBar>` index for O(1), defer to performance optimization sprint
- `param.time as number` BusinessDay type guard — chart uses UTCTimestamp (numeric), BusinessDay impossible with candlestick data, defer
- `offsetWidth` fallback (160px) causes one-frame position jump on first show after hide — cosmetic, defer
- `formatTimestampUTC7` NaN handling for invalid timestamps — upstream data validated by backend, defer
- Small container positioning overflow (< tooltipHeight + 16) — `min-width: 1024px` in CSS prevents this, defer

## Deferred from: code review of p1-2-1-candlestick-chart (2026-05-03)

- Missing `--prim-gray-300` token trong `@layer tokens` — gray scale có gap ở 300, cosmetic, defer — FIXED (added --prim-gray-300)
- Inline `style` attribute trên `#results-panel-placeholder` trong index.html chứa literal `16px` — nên dùng CSS class, defer
- Missing `--prim-yellow-300` trong `@layer tokens` — unlayered styles dùng `var(--prim-yellow-300, #d29922)` fallback, hoạt động đúng, defer — FIXED (added --prim-yellow-300)
- `LoadDataResult` type trong types.ts được define nhưng không dùng — `loadData()` trả `Promise<void>`, dead code, defer — FIXED (loadData now returns LoadDataResult)
- `revealBar(upToIndex)` slice vào `this.cache.data` có thể khác date range hiện tại — Epic P1-4 scope, defer
- `ExportPanel` và `sessionListPanel` không có teardown — single-call usage, defer
- Không validate date input trước khi fetch — server reject invalid dates, defer
- `_renderBars` chạy `bars.map()` mỗi lần gọi, không cache mapped result — perf optimization, defer khi có performance issue — NOTE: added sort/dedup, map still uncached
- `ema_20`/`ma_20` fields trong OHLCVBar bị discard bởi `_renderBars` — P1-2-4 scope (MA/EMA overlay), defer
- CSS `@layer` browser compatibility: Safari < 15.4 không hỗ trợ — target browsers đã support, defer
- Phase 2 CSS unlayered (ngoài `@layer`) luôn override `@layer components` — intentional design, defer
- `lang="vi"` trên `<html>` — tất cả UI text là Vietnamese, correct, defer
- `loadData()` signature `Promise<LoadDataResult | null>` khác spec `Promise<void>` — enhancement, defer — FIXED (signature now matches actual usage)
- `main.ts` import Phase 2 modules (SessionListPanel, ExportPanel) cho bundling — scope concern, defer
- ChartController hardcode hex colors thay vì đọc CSS tokens — LW Charts JS API không support CSS variables, defer
- getDefaultDateRange() month boundary overflow (e.g. Mar 31 → Sep 31 → Oct 1) — 1 day edge case, defer

## Deferred from: code review of p1-2-2-timeframe-selector (2026-05-03)

- IndicatorToggleState dead code [types.ts:80-83] — cosmetic, not a bug, defer
- Month boundary overflow in getDefaultDateRange [SettingsManager.ts:7-8] — 1-day edge case, defer
- No destroy/cleanup in main.ts (HMR leak) [main.ts] — development concern only, defer
- PersistedSettings.timeframe accepts arbitrary strings [SettingsManager.ts:19-26] — server validates, defer
- Settings save no user feedback on failure [SettingsManager.ts:32-38] — acceptable UX, defer
- load() swallows parse failures silently [SettingsManager.ts:28] — minor debuggability, defer
- No input sanitization on date inputs [main.ts:185] — browser constrains format, defer
- sessionListPanel/ExportPanel opaque side effects [main.ts:10-11] — Phase 2 scope, defer
- Date string comparison fragility [main.ts:185] — safe with input type="date", defer
- IndicatorOverlay.init() silently no-ops [IndicatorOverlay.ts:27-28] — latent bug, not current, defer

## Deferred from: code review of p1-1-5-data-gap-detection (2026-05-03)

- F1 (LOW): `_INTERVAL_MS` dict duplicated giữa `cache.py` và `binance.py` — intentional per ADR-09 (separation of concerns), nhưng nếu values thay đổi cần update cả 2 — defer, maintenance risk thấp
- F2 (LOW): `gaps: list[dict]` trong `OHLCVResponse` dùng untyped dict — nên dùng `GapInfo(BaseModel)` cho schema clarity — defer sang frontend integration sprint
- F3 (LOW): `detect_gaps` không validate sorted input — contract-based, `read_ohlcv` guarantees sort — defer, no runtime risk

## Deferred from: code review of p1-1-4-post-api-fetch-refresh (2026-05-03)

- F4 (LOW): `_cleanup_expired_jobs` trong job_manager.py không cleanup stale `_job_key_map` entries — minor memory leak trên server chạy lâu dài, defer sang refactor job_manager
- F5 (LOW): `test_partial_page_retry` chỉ assert `call_count >= 3`, không verify `len(result)` hoặc partial page thực sự được replace — defer, test hiện tại đủ để detect regression lớn
- F6 (LOW): AC7 ("Cache serves when Binance unavailable") claim trong docstring nhưng không có test nào cover — cache serve path đã được test ở test_ohlcv_route.py, defer
- F7 (LOW): `test_get_cached_max_timestamp_empty_cache` identical với `no_cache` — cả 2 test path không tồn tại, nên tạo empty parquet file để test 0-row case — defer
- F8 (LOW): `Retry-After` header value không validate — negative hoặc huge values gây sleep bất thường — defer, Binance API đáng tin cậy

## Deferred from: code review of p1-1-2-post-api-fetch (2026-04-29)

- F1: Race window giữa `start_job()` và `register_task()` — safe hiện tại vì không có `await` giữa 2 lời gọi trong asyncio single-loop; sẽ trở thành real race nếu ai insert `await` giữa chúng — defer, cần refactor job_manager để insert-and-register là atomic
- F11: `complete_job`/`fail_job` không xóa stale `_active_tasks` entry khi task đã done — correctness không bị ảnh hưởng vì `start_job` kiểm tra `task.done()`, nhưng dict không bao giờ được cleanup — defer cùng với F5 memory leak refactor
- F12: Binance HTTP error body (raw Python `str(e)`) leak vào `error` field của `/api/fetch-status` response — single-user tool nên không phải security issue hiện tại, nhưng nên sanitize khi deploy ra ngoài
- F14: AC5 race: job bị cancel trong khoảnh khắc giữa 404 guard trong `fetch_stream` và first poll của `_sse_generator` → SSE `error` event thay vì HTTP 404 — window cực nhỏ trong single-loop asyncio, defer đến khi có SSE integration tests

## Deferred from: code review of p1-1-1-get-api-ohlcv (2026-04-29)

- F12: Silent auto-delete cache khi có transient I/O error — không có logging/backup trước khi xóa; nếu `pd.read_parquet` raise do OOM hoặc I/O lỗi tạm thời, file sẽ bị xóa vĩnh viễn — defer đến khi thêm logging layer
- F13: `ma`/`ema` rất lớn (vd `ma=10000` trên 100 bars) → tất cả bars trả về `null`, không warning — defer sang UX polish sprint, thêm `le=500` constraint hoặc warning field trong response
- F14: `sliced.where(sliced.notna(), other=None)` áp dụng lên toàn bộ columns kể cả base OHLCV columns — đổi dtype các integer column sang object; không crash trong thực tế vì base columns đã validate non-null, nhưng fragile — defer sang refactor indicators.py để chỉ apply `where` lên indicator columns

## Deferred from: code review of 4-1-services-supabase-py (2026-04-27)

- 4.1-D1: 4 tautology tests (`test_timestamp_is_int`, `test_telegram_sent_is_false_bool`, `test_claude_verdict_is_none`, `test_metadata_schema_version_is_string`) test hardcoded literals thay vì output thực tế từ `write_signal_comparisons` / `write_signal_cases` — không bắt được regression nếu mapping logic thay đổi; nên replace bằng integration-style tests với mock httpx

## Deferred from: code review of 3-2-exportprogressoverlay (2026-04-27)

- D1: `exportpreview:confirmed` listener trong constructor không bao giờ remove — singleton tồn tại suốt app lifetime, acceptable nhưng gây test isolation pollution nếu module được re-import trong tests
- D2: Double-write asymmetry — 409 path ghi ExportHistory trực tiếp, 200 path ghi qua `exportprogress:exportSuccess` event — correct nhưng asymmetric, cần document để tránh future double-write
- D3: `exportprogress:exportSuccess` event detail `{ filename, date }` không có type declaration trong EventMap — silent runtime breakage nếu shape thay đổi
- D4: AC2/AC3 icon size 48px và màu green-500/red-500 cần verify trong CSS (`epo-success-icon`, `epo-error-icon`) — không kiểm tra được từ TS diff

## Deferred from: code review of 2-4-trades-array-management-trong-exportpanel (2026-04-27)

- G1: EventBus `on()` return value (unsubscribe fn) bị discard trong ExportPanel constructor — handlers không remove được, gây test isolation pollution nếu ExportPanel được re-instantiate trong tests — defer đến khi có test suite cần isolation
- G4: Draft sessionStorage không clear khi `_currentFilename` là null lúc `replayStateChanged:stopped` — ExportPanel không có filename để clear nếu user chưa bao giờ trigger `sessionlist:exportSelected` trong session đó — design gap, defer sang Story 4.x cleanup
- G6: `paused→stopped` transition không broadcast `canExport(false)` — buttons có thể ở trạng thái stale nếu `pause()` được implement trong ReplayEngine — defer đến khi implement pause feature
- G11: Double `sessionlist:exportSelected` khi ExportPreview đang open → `_currentFilename` trong ExportPanel và `_draftKey` trong ExportPreview có thể diverge — complex scenario, defer sang Story 4.x UX hardening
- G14: ResultsPanel + SessionListPanel Export buttons không có initial disabled state — buttons appear enabled trước khi `canExport` event đầu tiên fire sau page load — marginal init gap, backend quality gate chặn export nếu 0 trades

## Deferred from: code review of 2-3-per-trade-reasoning-summary-textarea-voi-auto-save (2026-04-27)

- AC3 Tab/Shift+Tab navigation: native browser Tab behavior đủ cho MVP; custom focus trap + wrap-around defer sang Story 4.x UX refinement sprint — native Tab hoạt động đúng DOM order
- F8: `_checkBlankTextarea()` chỉ fire trên `blur`, không fire trên `input` — blank warning không xuất hiện nếu user xóa rồi click Confirm mà không blur qua textarea — UX advisory only, không block export
- F9: `data-min-rows`/`data-max-rows` attributes render trong DOM nhưng không được đọc trong JS — expand/collapse hardcode `rows=5`/`rows=2` — dead attributes, cosmetic cleanup
- F10: Glow `setTimeout(800ms)` trong `enableConfirm()` không được track và cancel trong `cleanup()` — fires trên detached DOM node — no-op trong browser, không gây crash; theo dõi nếu mở rộng handler
- F13: `cleanup(true)` clear draft trước khi `exportpreview:confirmed` listener có thể fail-recover — nếu Story 3.x listener throw, draft đã mất vĩnh viễn — design tradeoff phụ thuộc Story 3.x error handling
- F14: `.export-preview-toast` dùng `position:sticky; top:56px` trong flex column context của panel — nếu panel scrolls thay vì trade-list, sticky có thể không hoạt động — marginal layout risk, MVP acceptable
- F15: `_getCharCounter()` và `_checkBlankTextarea()` traversal theo sibling order cố định (textarea → blank-hint → char-counter) — sẽ trả về null silently nếu element nào đó được insert giữa chúng — fragility, không phải regression hôm nay

## Deferred from: code review of 2-2-exportpreview-component (2026-04-27)

- `window.confirm()` for close-dirty dialog suppressed in sandboxed iframes — custom DOM confirmation dialog deferred to Story 4.x (MVP runs standalone)
- `close(force)` vs `cleanup(clearDraft)` parameter naming collision — cosmetic only, no functional impact, defer
- `data.trades` null-guard omitted — backend schema guarantees array, defer if contract ever changes

## Deferred from: code review of 2-1-get-api-sessions-filename-preview (2026-04-27)

- `bar_index > len(df)` silently clamped to `len(df)` — desync between frontend bar count and Parquet row count is invisible to client — defer validation to Story 4.3
- `timestamp` column dtype not validated — string timestamps pass monotonic check silently — defer to Story 4.3
- `except ValueError` in route always maps to `INVALID_FILENAME` code regardless of actual cause (invalid filename vs. corrupt data vs. missing columns) — distinct error codes deferred to Story 4.3

## Deferred from: code review of 1-4-sessionlistpanel-ui-browse-va-chon-session (2026-04-27)

- `_onReplayStateChanged` xóa `trades[]` ngay khi replay 'stopped' kể cả khi export đang in-flight — race condition cần design decision: nên show "replay stopped, trades cleared" warning hay block stop khi đang export? Defer sang Story 2.4 review.

## Deferred from: code review of 1-3-get-api-sessions-danh-sach-parquet-sessions (2026-04-27)

- Regex `\d{8}` trong `SESSION_FILENAME_PATTERN` không validate calendar date thực — `99999999` match thành công và tạo `"9999-99-99"`. Defer sang Story 4.3 (credentials + validation layer).

## Deferred from: code review of 1-2-eventbus-replaystatechanged-va-tradecompleted-events (2026-04-27)

- `typescript: "^6.0.0"` trong `package.json` — version 6.x chưa stable, có thể resolve pre-release — defer khi TypeScript 6 ra stable
- `strict: false` trong `tsconfig.json` ẩn null/undefined bugs — defer theo ADR-16 rollout plan (enable noImplicitAny trước, strict sau)

## Deferred from: code review of 1-1-them-supabase-config-vao-backend-settings (2026-04-27)

- `supabase_key`/`supabase_service_key` nên dùng `SecretStr` thay vì `str` để tránh secrets leak trong logs và tracebacks — defer sang Story 4.3 (Credentials Validation)
- `supabase_url` không validate format URL, chỉ check not-empty — một URL sai format như `"not-a-url"` vẫn pass validation — defer sang Story 4.3
- `--reload` flag trong `Procfile` không phù hợp production deployment — defer đến khi có production deployment setup
