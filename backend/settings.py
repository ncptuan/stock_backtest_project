from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Cache
    cache_dir: Path = Path("./cache")

    # Auth
    app_password: str = ""  # empty = no auth

    # Phase 2: Supabase Backtest DB (KHÔNG phải production bot DB)
    supabase_url: str = ""
    supabase_key: str = ""           # anon key — signal_comparisons (RLS disabled)
    supabase_service_key: str = ""   # service role key — signal_cases (RLS enabled)
    supabase_enabled: bool = False

    @model_validator(mode="after")
    def validate_supabase_config(self) -> "Settings":
        if self.supabase_enabled and not self.supabase_url.strip():
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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def model_post_init(self, __context: object) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()


def get_settings() -> Settings:
    """FastAPI dependency — returns singleton Settings instance."""
    return settings
