# Deferred Work

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
