"""Tests cho backend/settings.py — Story 1.1 AC#1, #2, #3."""

import pytest
from pydantic import ValidationError

from settings import Settings


class TestSettingsWithSupabaseDisabled:
    """AC#1, AC#2: SUPABASE_ENABLED=false không raise error, Phase 1 hoạt động bình thường."""

    def test_supabase_disabled_no_supabase_vars(self, tmp_path, monkeypatch):
        """SUPABASE_ENABLED=false, không có Supabase vars → Settings load thành công."""
        monkeypatch.setenv("SUPABASE_ENABLED", "false")
        monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
        # Không set SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY
        s = Settings()
        assert s.supabase_enabled is False
        assert s.supabase_url == ""
        assert s.supabase_key == ""
        assert s.supabase_service_key == ""

    def test_supabase_disabled_is_default(self, tmp_path, monkeypatch):
        """Không set SUPABASE_ENABLED → default là False."""
        monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
        s = Settings()
        assert s.supabase_enabled is False

    def test_all_four_fields_present(self, tmp_path, monkeypatch):
        """AC#1: Tất cả 4 fields mới tồn tại trên Settings object."""
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_KEY", "anon-key-abc")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-key-xyz")
        monkeypatch.setenv("SUPABASE_ENABLED", "false")
        monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))

        s = Settings()
        assert s.supabase_url == "https://test.supabase.co"
        assert s.supabase_key == "anon-key-abc"
        assert s.supabase_service_key == "service-key-xyz"
        assert s.supabase_enabled is False

    def test_all_four_fields_load_correctly(self, tmp_path, monkeypatch):
        """AC#1: 4 env vars load đúng giá trị."""
        monkeypatch.setenv("SUPABASE_URL", "https://myproject.supabase.co")
        monkeypatch.setenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiJ9.anon")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiJ9.service")
        monkeypatch.setenv("SUPABASE_ENABLED", "true")
        monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))

        s = Settings()
        assert s.supabase_url == "https://myproject.supabase.co"
        assert s.supabase_key == "eyJhbGciOiJIUzI1NiJ9.anon"
        assert s.supabase_service_key == "eyJhbGciOiJIUzI1NiJ9.service"
        assert s.supabase_enabled is True


class TestSettingsValidationError:
    """AC#3: SUPABASE_ENABLED=true nhưng SUPABASE_URL bị bỏ trống → raise ValidationError."""

    def test_supabase_enabled_true_empty_url_raises(self, tmp_path, monkeypatch):
        """AC#3: SUPABASE_ENABLED=true + SUPABASE_URL="" → ValidationError."""
        monkeypatch.setenv("SUPABASE_ENABLED", "true")
        monkeypatch.setenv("SUPABASE_URL", "")
        monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        # Kiểm tra có error liên quan Supabase URL
        error_messages = [str(e) for e in errors]
        assert any("SUPABASE_URL" in msg for msg in error_messages)

    def test_supabase_enabled_true_missing_url_raises(self, tmp_path, monkeypatch):
        """AC#3: SUPABASE_ENABLED=true và không set SUPABASE_URL → ValidationError."""
        monkeypatch.setenv("SUPABASE_ENABLED", "true")
        # Không set SUPABASE_URL — default là ""
        monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        # Verify error message rõ ràng
        error_str = str(exc_info.value)
        assert "SUPABASE_URL" in error_str

    def test_supabase_enabled_true_with_url_succeeds(self, tmp_path, monkeypatch):
        """SUPABASE_ENABLED=true + SUPABASE_URL có giá trị → không raise error."""
        monkeypatch.setenv("SUPABASE_ENABLED", "true")
        monkeypatch.setenv("SUPABASE_URL", "https://valid.supabase.co")
        monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))

        s = Settings()  # Không raise
        assert s.supabase_enabled is True
        assert s.supabase_url == "https://valid.supabase.co"


class TestSettingsCacheDirCreation:
    """Settings tạo cache_dir khi khởi tạo."""

    def test_cache_dir_created_on_init(self, tmp_path, monkeypatch):
        """model_post_init tạo cache_dir nếu chưa tồn tại."""
        cache_path = tmp_path / "new_cache_dir"
        assert not cache_path.exists()
        monkeypatch.setenv("CACHE_DIR", str(cache_path))

        Settings()
        assert cache_path.exists()
        assert cache_path.is_dir()


# ---------------------------------------------------------------------------
# URL format validation — Story 4.3 (AC: #5)
# ---------------------------------------------------------------------------

class TestSupabaseUrlValidation:
    def test_url_http_raises_validation_error(self, tmp_path, monkeypatch):
        """http:// URL → ValidationError (must be https://)"""
        monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                supabase_url="http://wrong.supabase.co",
                supabase_enabled=False,
            )
        assert "https://" in str(exc_info.value)

    def test_url_missing_protocol_raises_error(self, tmp_path, monkeypatch):
        """URL without protocol → ValidationError"""
        monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
        with pytest.raises(ValidationError):
            Settings(
                supabase_url="wrong.supabase.co",
                supabase_enabled=False,
            )

    def test_url_https_valid(self, tmp_path, monkeypatch):
        """https:// URL → valid"""
        monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
        s = Settings(
            supabase_url="https://correct.supabase.co",
            supabase_key="test-key",
            supabase_service_key="test-service-key",
            supabase_enabled=False,
        )
        assert s.supabase_url == "https://correct.supabase.co"

    def test_url_empty_with_disabled_valid(self, tmp_path, monkeypatch):
        """Empty URL with supabase_enabled=False → valid (no https:// check for empty)"""
        monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
        s = Settings(
            supabase_url="",
            supabase_enabled=False,
        )
        assert s.supabase_url == ""

    def test_url_empty_with_enabled_raises(self, tmp_path, monkeypatch):
        """Empty URL with supabase_enabled=True → ValidationError"""
        monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                supabase_url="",
                supabase_enabled=True,
            )
        assert "SUPABASE_URL" in str(exc_info.value)
