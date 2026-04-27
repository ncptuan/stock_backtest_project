"""Tests cho GET /api/sessions — Story 1.3 AC#1, #2, #3, #4, #5."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    """TestClient với cache_dir isolated trong tmp_path."""
    from backend.settings import settings

    cache_path = tmp_path / "cache"
    cache_path.mkdir(parents=True)
    monkeypatch.setattr(settings, "cache_dir", cache_path)

    from backend.main import create_app

    return TestClient(create_app())


def test_list_sessions_two_valid_files(client, tmp_path):
    """AC#1: 2 valid Parquet files → 2 SessionItems với đúng fields."""
    cache = tmp_path / "cache"
    (cache / "BTCUSDT_4h_20260420.parquet").touch()
    (cache / "ETHUSDT_1h_20260415.parquet").touch()

    response = client.get("/api/sessions")
    assert response.status_code == 200

    body = response.json()
    assert body["error"] is None
    data = body["data"]
    assert len(data) == 2

    btc = next(s for s in data if s["symbol"] == "BTCUSDT")
    assert btc["filename"] == "BTCUSDT_4h_20260420.parquet"
    assert btc["timeframe"] == "4h"
    assert btc["date"] == "2026-04-20"
    assert btc["exported"] is False

    eth = next(s for s in data if s["symbol"] == "ETHUSDT")
    assert eth["filename"] == "ETHUSDT_1h_20260415.parquet"
    assert eth["timeframe"] == "1h"
    assert eth["date"] == "2026-04-15"
    assert eth["exported"] is False


def test_list_sessions_empty_cache(client):
    """AC#2: cache dir trống → [] với HTTP 200."""
    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert response.json()["data"] == []
    assert response.json()["error"] is None


def test_list_sessions_cache_dir_missing(tmp_path, monkeypatch):
    """AC#2: cache dir không tồn tại → [] với HTTP 200, không phải 404."""
    from backend.settings import settings

    monkeypatch.setattr(settings, "cache_dir", tmp_path / "nonexistent")

    from backend.main import create_app

    c = TestClient(create_app())
    response = c.get("/api/sessions")
    assert response.status_code == 200
    assert response.json()["data"] == []
    assert response.json()["error"] is None


def test_list_sessions_skips_non_matching_files(client, tmp_path):
    """AC#3: files không match pattern bị skip — không crash, không xuất hiện."""
    cache = tmp_path / "cache"
    # Phase 1 file — KHÔNG match Phase 2 pattern
    (cache / "BTC_USDT_4h.parquet").touch()
    # Temp file — KHÔNG match
    (cache / "BTCUSDT_4h_20260420.parquet.tmp").touch()
    # Non-parquet
    (cache / "readme.txt").touch()
    # Valid Phase 2 file
    (cache / "BTCUSDT_4h_20260420.parquet").touch()

    response = client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()["data"]

    assert len(data) == 1
    assert data[0]["filename"] == "BTCUSDT_4h_20260420.parquet"


def test_list_sessions_supabase_disabled_still_works(client, tmp_path, monkeypatch):
    """AC#4: endpoint không phụ thuộc SUPABASE_ENABLED."""
    from backend.settings import settings

    monkeypatch.setattr(settings, "supabase_enabled", False)

    cache = tmp_path / "cache"
    (cache / "BTCUSDT_4h_20260420.parquet").touch()

    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_list_sessions_exported_always_false(client, tmp_path):
    """AC#5: exported field luôn là false (hardcoded cho đến Story 3.3)."""
    cache = tmp_path / "cache"
    (cache / "BTCUSDT_4h_20260420.parquet").touch()

    response = client.get("/api/sessions")
    data = response.json()["data"]
    assert all(s["exported"] is False for s in data)


def test_list_sessions_sorted_order(client, tmp_path):
    """Sessions trả về theo thứ tự alphabetical (consistent ordering)."""
    cache = tmp_path / "cache"
    (cache / "ETHUSDT_1h_20260415.parquet").touch()
    (cache / "BTCUSDT_4h_20260420.parquet").touch()
    (cache / "BTCUSDT_4h_20260401.parquet").touch()

    response = client.get("/api/sessions")
    data = response.json()["data"]
    filenames = [s["filename"] for s in data]
    assert filenames == sorted(filenames)
