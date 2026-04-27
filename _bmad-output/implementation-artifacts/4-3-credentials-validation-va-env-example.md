# Story 4.3: Credentials validation và .env.example

Status: done

## Story

As a developer,
I want Supabase credentials được validate khi bắt đầu export và .env.example document đầy đủ,
So that Narron nhận error ngay lập tức với hướng dẫn rõ ràng nếu config sai — không phải sau khi 30 rows đã được ghi.

## Acceptance Criteria

1. **Given** `POST /api/export` nhận request với `SUPABASE_ENABLED=true` — **When** request được xử lý — **Then** backend validate credentials TRƯỚC khi ghi bất kỳ row nào: test `GET` đơn giản đến Supabase để verify URL + key hợp lệ.

2. **Given** anon key sai (cho signal_comparisons) — **When** credential validation — **Then** HTTP 401 với message cụ thể: `"SUPABASE_KEY không hợp lệ — Kiểm tra anon key trong .env (dùng cho signal_comparisons)"` — không row nào được ghi.

3. **Given** service key sai (cho signal_cases) — **When** credential validation — **Then** HTTP 401 với message cụ thể: `"SUPABASE_SERVICE_KEY không hợp lệ — Kiểm tra service role key trong .env (dùng cho signal_cases, RLS enabled)"` — không row nào được ghi.

4. **Given** `.env.example` trong root directory — **When** developer mở file — **Then** thấy đủ 4 vars với exact comments:
   ```
   SUPABASE_URL=https://your-project.supabase.co  # URL của Supabase Backtest project (KHÔNG phải production bot)
   SUPABASE_KEY=your-anon-key                      # Anon key — dùng cho signal_comparisons (RLS disabled)
   SUPABASE_SERVICE_KEY=your-service-role-key      # Service role key — dùng cho signal_cases (RLS enabled)
   SUPABASE_ENABLED=false                          # Set true để bật Supabase integration
   ```

5. **Given** `SUPABASE_URL=http://wrong-format.supabase.co` (thiếu `https://`) — **When** FastAPI khởi động và Pydantic Settings validate — **Then** server raise `ValidationError` với message rõ chỉ ra URL sai format — server KHÔNG khởi động.

6. **Given** credential validation pass — **When** export proceeds — **Then** không có thêm validation overhead — duplicate check và write functions hoạt động bình thường.

7. **Given** tests/test_settings.py và tests/test_export.py — **When** `pytest tests/` chạy — **Then** credential validation tests pass — không cần Supabase connection thật.

## Tasks / Subtasks

- [x] Task 1: Thêm URL format validator vào `backend/settings.py` (AC: #5)
  - [x] Tìm `@model_validator` hiện có trong Settings (từ Story 1.1) — **MODIFY**, không tạo validator mới
  - [x] Thêm URL format check vào validator đã có: nếu `supabase_url` không rỗng VÀ không bắt đầu `https://` → raise `ValueError`
  - [x] Message cụ thể: `f"SUPABASE_URL phải bắt đầu bằng 'https://' — Nhận được: '{self.supabase_url}'"`
  - [x] Format check apply ALWAYS (kể cả khi `supabase_enabled=false`) để catch config errors sớm
  - [x] Empty string `""` vẫn valid (disabled mode) — chỉ fail khi có giá trị nhưng format sai

- [x] Task 2: Tạo `validate_credentials()` trong `backend/services/supabase.py` (AC: #1, #2, #3)
  - [x] File đã tồn tại từ Story 3.1 — **ADD** function mới, không tạo lại file
  - [x] Implement `async def validate_credentials(settings: Settings) -> None`
  - [x] Test anon key: `GET {supabase_url}/rest/v1/signal_comparisons?limit=1` với anon key header
  - [x] Nếu response `401` → raise `ValueError("SUPABASE_KEY không hợp lệ — Kiểm tra anon key trong .env (dùng cho signal_comparisons)")`
  - [x] Test service key: `GET {supabase_url}/rest/v1/signal_cases?limit=1` với service key header
  - [x] Nếu response `401` → raise `ValueError("SUPABASE_SERVICE_KEY không hợp lệ — Kiểm tra service role key trong .env (dùng cho signal_cases, RLS enabled)")`
  - [x] Non-401 errors (404, 500) → KHÔNG raise ValueError — chỉ 401 chỉ rõ credential fail; các lỗi khác sẽ được phát hiện khi write
  - [x] Dùng `httpx.AsyncClient(timeout=10.0)` — ngắn hơn write timeout (10s vs 30s) vì đây là test nhẹ

- [x] Task 3: Thêm credential validation vào `backend/routes/export.py` (AC: #1, #2, #3, #6)
  - [x] File đã tồn tại từ Story 3.1 (có quality gate từ Story 4.2) — **MODIFY**
  - [x] Thêm step mới: sau quality gate check, TRƯỚC duplicate check
  - [x] Gọi `await validate_credentials(settings)` và wrap trong try/except:
    - `ValueError` → `HTTPException(401, detail={"error": "invalid_credentials", "message": str(e)})`
    - `httpx.TimeoutException` → `HTTPException(504, detail={"error": "timeout", ...})`
  - [x] Import `validate_credentials` từ `backend.services.supabase` (cùng import block với các functions khác)

- [x] Task 4: Update `.env.example` (AC: #4)
  - [x] File đã tồn tại từ Story 1.1 — **MODIFY** comment của `SUPABASE_URL`
  - [x] Thêm "(KHÔNG phải production bot)" vào cuối comment `SUPABASE_URL`
  - [x] Kết quả exact: `SUPABASE_URL=https://your-project.supabase.co  # URL của Supabase Backtest project (KHÔNG phải production bot)`
  - [x] Giữ nguyên tất cả các vars khác

- [x] Task 5: Extend `tests/test_settings.py` và `tests/test_export.py` (AC: #7)
  - [x] **`tests/test_settings.py`** (file đã có từ Story 1.1) — ADD tests:
    - Test: `SUPABASE_URL="http://wrong.supabase.co"` → raise `ValidationError` với message chứa "https://"
    - Test: `SUPABASE_URL="https://correct.supabase.co"` → không raise error
    - Test: `SUPABASE_URL=""` khi `SUPABASE_ENABLED=false` → vẫn valid (không force https:// khi empty)
  - [x] **`tests/test_export.py`** (file đã có từ Story 3.1, extended bởi Story 4.2) — ADD tests:
    - Test: valid payload, mock anon key returns 401 → export returns HTTP 401 với "SUPABASE_KEY" message
    - Test: valid payload, mock service key returns 401 → export returns HTTP 401 với "SUPABASE_SERVICE_KEY" message
    - Test: credential validation timeout → HTTP 504
    - Test: credential pass (200) → export proceeds (no 401)
    - Test: credential validation xảy ra TRƯỚC duplicate check (mock verify call order)

### Review Findings

- [x] [Review][Patch] Dead code + orphaned Mock import trong test_credential_invalid_anon_key_401 [tests/test_export.py:511-513] — fixed: xóa inline import và mock_resp_401 unused variable

## Dev Notes

### ⚠️ CRITICAL: Story 1.1 Đã Tạo `backend/settings.py` và `.env.example`

Story 1.1 (done) đã implement:
- `backend/settings.py` với `class Settings(BaseSettings)` có đủ 4 Supabase fields
- `@model_validator` validate `supabase_enabled=true` + `supabase_url=""` → ValidationError
- `.env.example` với 4 Phase 2 vars (comments có thể khác 1 chút — xem Task 4)

**Story 4.3 MODIFIES, không tạo lại:**
1. `backend/settings.py` — thêm URL format check vào `@model_validator` hiện có
2. `.env.example` — update comment của `SUPABASE_URL` thêm "(KHÔNG phải production bot)"
3. `backend/services/supabase.py` — ADD `validate_credentials()` function
4. `backend/routes/export.py` — ADD credential validation step

> **⚠️ Kiểm tra trước khi edit**: Đọc `backend/settings.py` hiện tại — validator đã có check gì? Tránh duplicate validation logic. Chỉ ADD URL format check, không rewrite validator.

---

### Execution Order trong `POST /api/export`

Sau Story 4.2 và Story 4.3, route có 6 steps theo thứ tự:

```
1. Guard SUPABASE_ENABLED (503)
   ↓
2. Quality gate check (422) — fast fail, no network [Story 4.2]
   ↓
3. Credential validation (401) — network call ~100ms [Story 4.3]
   ↓
4. Duplicate check (409) — uses anon key
   ↓
5. Write signal_comparisons (uses anon key)
   ↓
6. Write signal_cases / rollback (uses service key)
```

**Lý do quality gate TRƯỚC credential validation:**
- Quality gate là pure logic, không cần network
- Fast fail: nếu win_rate < 55% → fail ngay, không waste network call
- Credential check chỉ xảy ra khi trade data đã hợp lệ

**Lý do credential validation TRƯỚC duplicate check:**
- Credential fail = cả anon key lẫn duplicate check sẽ cùng fail
- Better UX: actionable "key sai" message thay vì confusing "duplicate check failed"

---

### `backend/settings.py` — Exact Validator Modification

Story 1.1's existing validator:
```python
@model_validator(mode="after")
def validate_supabase_config(self) -> "Settings":
    if self.supabase_enabled and not self.supabase_url:
        raise ValueError(
            "SUPABASE_URL is required when SUPABASE_ENABLED=true. "
            "Set SUPABASE_URL in .env to your Supabase Backtest project URL."
        )
    return self
```

Story 4.3 — ADD URL format check trong cùng validator:
```python
@model_validator(mode="after")
def validate_supabase_config(self) -> "Settings":
    if self.supabase_enabled and not self.supabase_url:
        raise ValueError(
            "SUPABASE_URL is required when SUPABASE_ENABLED=true. "
            "Set SUPABASE_URL in .env to your Supabase Backtest project URL."
        )
    # URL format check — apply always (even when disabled) to catch config errors early
    if self.supabase_url and not self.supabase_url.startswith("https://"):
        raise ValueError(
            f"SUPABASE_URL phải bắt đầu bằng 'https://' — "
            f"Nhận được: '{self.supabase_url}'"
        )
    return self
```

**Không** thêm `@field_validator` riêng — dùng `@model_validator` đã có để tránh hai validators làm cùng việc.

---

### `validate_credentials()` — Implementation

```python
async def validate_credentials(settings: Settings) -> None:
    """
    Validate Supabase credentials before any write operation.
    Makes lightweight GET request to test API key validity.
    
    Raises ValueError with actionable message if 401 (invalid credentials).
    Non-401 errors (404, 500, network) are NOT raised here — they will be
    caught during the actual write operations.
    """
    base_url = f"{settings.supabase_url}/rest/v1"

    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Validate anon key (signal_comparisons access)
        resp_anon = await client.get(
            f"{base_url}/signal_comparisons",
            headers={
                "apikey": settings.supabase_key,
                "Authorization": f"Bearer {settings.supabase_key}",
            },
            params={"limit": "1"},
        )
        if resp_anon.status_code == 401:
            raise ValueError(
                "SUPABASE_KEY không hợp lệ — Kiểm tra anon key trong .env "
                "(dùng cho signal_comparisons)"
            )

        # 2. Validate service role key (signal_cases access)
        resp_service = await client.get(
            f"{base_url}/signal_cases",
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
            },
            params={"limit": "1"},
        )
        if resp_service.status_code == 401:
            raise ValueError(
                "SUPABASE_SERVICE_KEY không hợp lệ — Kiểm tra service role key trong .env "
                "(dùng cho signal_cases, RLS enabled)"
            )
```

**Tại sao chỉ check 401:**
- 401 = credentials invalid → actionable, rõ ràng nguyên nhân
- 403 = credentials valid nhưng permission denied (RLS issue) → khác với key invalid, catch ở write time
- 404 = table không tồn tại (schema issue) → Story 4.1 / _parse_supabase_error() scope
- 500, 502 = Supabase server error → không phải credential issue, sẽ fail ở write time với proper message

---

### `backend/routes/export.py` — Credential Validation Step

Tìm vị trí sau quality gate check và TRƯỚC duplicate check. Add:

```python
    # 3b. Credential validation (before any Supabase operation)
    from backend.services.supabase import (
        _parse_session_date, check_duplicate,
        validate_credentials,
        write_signal_comparisons, write_signal_cases,
        rollback_signal_comparisons, generate_signal_id,
    )
    try:
        await validate_credentials(settings)
    except ValueError as e:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_credentials",
                "message": str(e),
            },
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={
                "error": "timeout",
                "message": "Supabase đang wake up — thử lại sau 30 giây",
            },
        )
```

> **Import consolidation note**: Story 3.1 dùng lazy imports (`from backend.services.supabase import ...`) bên trong các blocks. Story 4.3 nên consolidate tất cả supabase imports lên một chỗ nếu có thể, hoặc add `validate_credentials` vào lazy import block gần duplicate check.

---

### `.env.example` — Exact Update Required

Tìm dòng `SUPABASE_URL` hiện tại và update comment:

**Trước:**
```
SUPABASE_URL=https://your-project.supabase.co   # URL của Supabase Backtest project
```

**Sau:**
```
SUPABASE_URL=https://your-project.supabase.co  # URL của Supabase Backtest project (KHÔNG phải production bot)
```

Chú ý: Giữ nguyên tất cả vars khác, chỉ update comment của `SUPABASE_URL`.

---

### Test Pattern — Mock Credential Validation

```python
# tests/test_export.py — ADD sau quality gate tests (Story 4.2)

class TestCredentialValidation:
    def test_invalid_anon_key_returns_401(self, client, mock_settings_enabled):
        """Mock anon key returns 401 → export returns 401 với 'SUPABASE_KEY' message"""
        payload = _make_export_request(n_trades=15, win_rate=0.60)

        with patch("httpx.AsyncClient") as mock_httpx:
            # First GET (anon key validation) → 401
            mock_resp_401 = Mock()
            mock_resp_401.status_code = 401
            mock_httpx.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_resp_401
            )

            resp = client.post("/api/export", json=payload)

        assert resp.status_code == 401
        detail = resp.json()["detail"]
        assert detail["error"] == "invalid_credentials"
        assert "SUPABASE_KEY" in detail["message"]
        assert "signal_comparisons" in detail["message"]

    def test_invalid_service_key_returns_401(self, client, mock_settings_enabled):
        """Anon key OK, service key returns 401 → 401 với 'SUPABASE_SERVICE_KEY' message"""
        payload = _make_export_request(n_trades=15, win_rate=0.60)

        with patch("httpx.AsyncClient") as mock_httpx:
            # First GET (anon key) → 200 OK
            # Second GET (service key) → 401
            mock_ok = Mock(); mock_ok.status_code = 200
            mock_401 = Mock(); mock_401.status_code = 401
            mock_httpx.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=[mock_ok, mock_401]
            )

            resp = client.post("/api/export", json=payload)

        assert resp.status_code == 401
        detail = resp.json()["detail"]
        assert "SUPABASE_SERVICE_KEY" in detail["message"]
        assert "signal_cases" in detail["message"]

    def test_credential_validation_timeout(self, client, mock_settings_enabled):
        """Credential validation timeout → 504"""
        payload = _make_export_request(n_trades=15, win_rate=0.60)

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )

            resp = client.post("/api/export", json=payload)

        assert resp.status_code == 504

    def test_credential_valid_proceeds_to_write(self, client, mock_settings_enabled):
        """Both credentials valid → export proceeds past credential check"""
        payload = _make_export_request(n_trades=15, win_rate=0.60)

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ok = Mock(); mock_ok.status_code = 200
            mock_ok.json.return_value = []
            mock_ok.headers = {}
            # credential GET × 2, then duplicate check GET × 1, then write POSTs × 2
            mock_httpx.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_ok
            )
            mock_httpx.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_ok
            )

            resp = client.post("/api/export", json=payload)

        # Should not be 401 (credentials passed)
        assert resp.status_code != 401

    def test_credential_check_before_quality_gate_fail(self, client, mock_settings_enabled):
        """Quality gate fail (< 10 trades) → credential NOT called (quality gate is fast fail first)"""
        payload = _make_export_request(n_trades=7, win_rate=0.71)

        with patch(
            "backend.services.supabase.validate_credentials"
        ) as mock_validate:
            resp = client.post("/api/export", json=payload)

        assert resp.status_code == 422  # quality gate fail
        mock_validate.assert_not_called()  # credential check NOT called

    def test_credential_check_before_duplicate_check(self, client, mock_settings_enabled):
        """Credentials fail → duplicate check NOT called (credential check first)"""
        payload = _make_export_request(n_trades=15, win_rate=0.60)

        with patch("backend.services.supabase.validate_credentials") as mock_validate, \
             patch("backend.services.supabase.check_duplicate") as mock_dup:
            mock_validate.side_effect = ValueError("SUPABASE_KEY không hợp lệ ...")
            resp = client.post("/api/export", json=payload)

        assert resp.status_code == 401
        mock_dup.assert_not_called()  # duplicate check NOT called
```

### Settings Validation Tests

```python
# tests/test_settings.py — ADD

import pytest
from pydantic import ValidationError
from backend.settings import Settings


class TestSupabaseUrlValidation:
    def test_url_http_raises_validation_error(self):
        """http:// URL → ValidationError (must be https://)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                supabase_url="http://wrong.supabase.co",
                supabase_enabled=False,
            )
        assert "https://" in str(exc_info.value)

    def test_url_missing_protocol_raises_error(self):
        """URL without protocol → ValidationError"""
        with pytest.raises(ValidationError):
            Settings(
                supabase_url="wrong.supabase.co",
                supabase_enabled=False,
            )

    def test_url_https_valid(self):
        """https:// URL → valid"""
        s = Settings(
            supabase_url="https://correct.supabase.co",
            supabase_key="test-key",
            supabase_service_key="test-service-key",
            supabase_enabled=False,
        )
        assert s.supabase_url == "https://correct.supabase.co"

    def test_url_empty_with_disabled_valid(self):
        """Empty URL with supabase_enabled=False → valid (no https:// check for empty)"""
        s = Settings(
            supabase_url="",
            supabase_enabled=False,
        )
        assert s.supabase_url == ""

    def test_url_empty_with_enabled_raises(self):
        """Empty URL with supabase_enabled=True → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                supabase_url="",
                supabase_enabled=True,
            )
        assert "SUPABASE_URL" in str(exc_info.value)
```

> **Note trên test isolation**: Settings singleton `settings = Settings()` được tạo tại module level. Trong tests, dùng `Settings(...)` trực tiếp (không phải singleton) để test validation. Đây là pattern từ Story 1.1's `tests/test_settings.py`.

---

### NFR Compliance

- **NFR5 (Critical):** Supabase credentials chỉ load từ env vars — `.env.example` guide developer đúng cách ✓
- **NFR6 (Medium):** SUPABASE_SERVICE_KEY comment rõ: chỉ dùng cho signal_cases (RLS) ✓
- **NFR11 (Critical):** `.env.example` comment "(KHÔNG phải production bot)" nhắc nhở tường minh về hai Supabase projects ✓
- **NFR18 (Low):** `.env.example` document đủ tất cả Supabase env vars ✓
- **FR29 (High):** Credentials validate khi khởi động export, lỗi rõ nếu sai ✓

---

### Security: Credential Exposure Prevention

- Credentials (keys) **không bao giờ** được log ra: `logger.error(str(e))` — ValueError message chỉ chứa field name (`SUPABASE_KEY`), không chứa giá trị key thật
- `_parse_supabase_error()` (từ Story 4.1) truncates response body: `resp.text[:200]` — giới hạn thông tin leak trong error messages
- `.env` được gitignore (Story 1.1's `.gitignore` đã thêm)

---

### Cross-Story Dependencies

- **Story 1.1** (done): `backend/settings.py` với `@model_validator` và `.env.example` — Story 4.3 MODIFIES cả hai
- **Story 3.1** (review): `backend/services/supabase.py` — Story 4.3 ADDS `validate_credentials()` function
- **Story 3.1** (review) + **Story 4.2** (ready-for-dev): `backend/routes/export.py` — Story 4.3 ADDS credential validation step. Nếu Story 4.2 chưa merge, Story 4.3 cũng add quality gate check (order: 4.2 first, then 4.3)
- **Story 4.2** (ready-for-dev): `tests/test_export.py` — Story 4.3 EXTENDS với credential tests. Merge order: Story 4.2's quality gate tests TRƯỚC, Story 4.3 adds credentials tests SAU.

> **⚠️ Merge conflict risk HIGH với Stories 4.1, 4.2, 4.3**: Cả 3 stories đều modify `backend/services/supabase.py` và `backend/routes/export.py`. Dev agent nên:
> 1. Complete Story 4.1 trước (merge `services/supabase.py` changes)
> 2. Complete Story 4.2 (merge quality gate in `routes/export.py`)
> 3. Complete Story 4.3 (merge credential validation in both files)
> Sequential implementation tránh merge conflicts.

### References

- [epics.md - Story 4.3 Acceptance Criteria](_bmad-output/planning-artifacts/epics.md#story-43-credentials-validation-và-envexample)
- [prd-phase2-supabase.md - FR29, NFR5, NFR6, NFR11, NFR18](_bmad-output/planning-artifacts/prd-phase2-supabase.md)
- [1-1-them-supabase-config-vao-backend-settings.md - settings.py implementation + .env.example format](_bmad-output/implementation-artifacts/1-1-them-supabase-config-vao-backend-settings.md)
- [3-1-post-api-export-write-signal-comparisons-va-signal-cases.md - export.py route structure](_bmad-output/implementation-artifacts/3-1-post-api-export-write-signal-comparisons-va-signal-cases.md)
- [4-1-services-supabase-py-write-functions-va-schema-mapping.md - supabase.py additions context](_bmad-output/implementation-artifacts/4-1-services-supabase-py-write-functions-va-schema-mapping.md)
- [4-2-pytest-unit-tests-cho-critical-paths.md - export.py quality gate + test_export.py extensions](_bmad-output/implementation-artifacts/4-2-pytest-unit-tests-cho-critical-paths.md)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Completion Notes

- Task 1: Thêm URL format check vào `@model_validator` hiện có trong `backend/settings.py`. Apply khi `supabase_url` có giá trị nhưng không bắt đầu `https://`. Empty string vẫn valid.
- Task 2: Thêm `validate_credentials()` vào `backend/services/supabase.py`. Dùng `httpx.AsyncClient(timeout=10.0)`, chỉ raise ValueError khi nhận 401 (explicit credential failure). Non-401 không raise.
- Task 3: Restructure `backend/routes/export.py` — reorder steps: Guard → Quality gate → Credential validation → Duplicate check → Write. Updated `validate_credentials` import. Updated docstring để phản ánh flow mới.
- Task 4: Updated `.env.example` — thêm "(KHÔNG phải production bot)" vào comment SUPABASE_URL.
- Task 5: Added `TestSupabaseUrlValidation` class (5 tests) vào `tests/test_settings.py`. Added 6 credential validation tests vào `tests/test_export.py`. Updated 6 existing tests để mock `validate_credentials`.
- Tổng tests: 93 → 104 (thêm 11 tests mới). Tất cả pass.

### File List

- `backend/settings.py` — thêm URL format check vào validator
- `backend/services/supabase.py` — thêm `validate_credentials()` function
- `backend/routes/export.py` — reorder steps, add credential validation step, add import
- `.env.example` — update SUPABASE_URL comment
- `tests/test_settings.py` — thêm `TestSupabaseUrlValidation` class (5 tests)
- `tests/test_export.py` — thêm 6 credential validation tests, update 6 existing tests với `validate_credentials` mock

### Change Log

- Added URL format validation to `Settings.validate_supabase_config` (Story 4.3 AC#5) — 2026-04-27
- Added `validate_credentials()` to `backend/services/supabase.py` (Story 4.3 AC#1-3) — 2026-04-27
- Restructured `POST /api/export` route flow: Guard → Quality gate → Credential validation → Duplicate check → Write (Story 4.3 AC#6) — 2026-04-27
- Updated `.env.example` SUPABASE_URL comment (Story 4.3 AC#4) — 2026-04-27
- Extended tests/test_settings.py and tests/test_export.py (Story 4.3 AC#7) — 2026-04-27

### Debug Log References

### Completion Notes List

### File List
