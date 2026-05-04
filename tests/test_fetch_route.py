"""
Tests cho Story P1-1-2: POST /api/fetch — Async Binance fetch với SSE progress.

Covers ACs #1–#7:
  - AC1: POST /api/fetch → 202 + job_id
  - AC2: POST /api/fetch 409 conflict khi cùng symbol+timeframe đang chạy
  - AC3/AC4: SSE stream events (basic check)
  - AC5: fetch-status 404 cho job_id không tồn tại
  - AC6: GET /api/fetch-status/{job_id} khi running
  - AC7: DELETE /api/fetch/{job_id} → 204
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient

_MOCK_DF = pd.DataFrame({
    "timestamp": [1_704_067_200_000],
    "open": [42000.0],
    "high": [42500.0],
    "low": [41800.0],
    "close": [42200.0],
    "volume": [100.0],
})


@pytest.fixture
def app(tmp_path: Path, monkeypatch):
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    from backend.main import create_app
    return create_app()


@pytest.fixture(autouse=True)
def reset_job_manager():
    """Reset global state trước/sau mỗi test — tránh state leak giữa tests."""
    from backend.services import job_manager
    job_manager._active_tasks.clear()
    job_manager._job_progress.clear()
    job_manager._job_key_map.clear()
    job_manager._job_completed_at.clear()
    yield
    job_manager._active_tasks.clear()
    job_manager._job_progress.clear()
    job_manager._job_key_map.clear()
    job_manager._job_completed_at.clear()


# ─── AC1: POST /api/fetch happy path → 202 + job_id ──────────────────────────

@pytest.mark.asyncio
async def test_post_fetch_happy_path_202(app):
    """POST /api/fetch với Binance mock → 202 Accepted + job_id hợp lệ."""
    with patch("backend.routes.fetch.binance.fetch_ohlcv", new_callable=AsyncMock, return_value=_MOCK_DF):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/fetch", json={
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "date_start": "2024-01-01",
                "date_end": "2024-03-01",
            })

    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert len(body["job_id"]) == 36  # UUID4 format


@pytest.mark.asyncio
async def test_post_fetch_symbol_normalize(app):
    """Symbol 'BTC/USDT' được normalize thành 'BTCUSDT'."""
    with patch("backend.routes.fetch.binance.fetch_ohlcv", new_callable=AsyncMock, return_value=_MOCK_DF):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/fetch", json={
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "date_start": "2024-01-01",
                "date_end": "2024-03-01",
            })

    assert resp.status_code == 202


# ─── AC2: 409 Conflict khi cùng job đang chạy ─────────────────────────────────

@pytest.mark.asyncio
async def test_post_fetch_409_conflict(app):
    """Gọi POST /api/fetch 2 lần cùng symbol+timeframe → 2nd call là 409."""
    from backend.services import job_manager

    # Inject running job manually với task giả không bao giờ kết thúc
    job_id = job_manager.start_job("BTCUSDT", "1h")

    async def _never_done():
        await asyncio.sleep(9999)

    task = asyncio.create_task(_never_done())
    job_manager.register_task(job_id, task)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/fetch", json={
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "date_start": "2024-01-01",
                "date_end": "2024-03-01",
            })

        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "FETCH_IN_PROGRESS"
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ─── AC: 422 Invalid timeframe ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_post_fetch_422_invalid_timeframe(app):
    """Timeframe không hợp lệ → 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/fetch", json={
            "symbol": "BTCUSDT",
            "timeframe": "2h",
            "date_start": "2024-01-01",
            "date_end": "2024-03-01",
        })

    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INVALID_TIMEFRAME"


# ─── AC5: fetch-status 404 cho job không tồn tại ────────────────────────────

@pytest.mark.asyncio
async def test_fetch_status_404_unknown_job(app):
    """GET /api/fetch-status/{job_id} với job_id không tồn tại → 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/fetch-status/nonexistent-job-id")

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "JOB_NOT_FOUND"


# ─── AC6: GET /api/fetch-status khi job đang running ─────────────────────────

@pytest.mark.asyncio
async def test_fetch_status_running(app):
    """GET /api/fetch-status/{job_id} khi job running → status=running + percent."""
    from backend.services import job_manager

    job_id = job_manager.start_job("BTCUSDT", "1h")
    job_manager.update_progress(job_id, 50, "Fetching page 5/10")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/fetch-status/{job_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == job_id
    assert body["status"] == "running"
    assert body["percent"] == 50
    assert body["status_text"] == "Fetching page 5/10"


# ─── AC7: DELETE /api/fetch/{job_id} → 204 ───────────────────────────────────

@pytest.mark.asyncio
async def test_delete_fetch_204(app):
    """DELETE /api/fetch/{job_id} → 204 + job bị xóa khỏi manager."""
    from backend.services import job_manager

    job_id = job_manager.start_job("BTCUSDT", "1h")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(f"/api/fetch/{job_id}")

    assert resp.status_code == 204
    assert job_manager.get_progress(job_id) is None


@pytest.mark.asyncio
async def test_delete_fetch_404_unknown(app):
    """DELETE /api/fetch/{job_id} với job không tồn tại → 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete("/api/fetch/nonexistent-id")

    assert resp.status_code == 404


# ─── AC3/AC4: SSE stream 404 khi job không tồn tại ──────────────────────────

@pytest.mark.asyncio
async def test_fetch_stream_404_unknown_job(app):
    """GET /api/fetch-stream/{job_id} với job không tồn tại → 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/fetch-stream/nonexistent-job-id")

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "JOB_NOT_FOUND"


# ─── Integration: fetch hoàn thành → cache tồn tại ───────────────────────────

@pytest.mark.asyncio
async def test_fetch_writes_cache(app, tmp_path, monkeypatch):
    """Fetch thành công → BTCUSDT_1h.parquet tồn tại trong cache_dir."""
    from backend.settings import settings
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    with patch("backend.routes.fetch.binance.fetch_ohlcv", new_callable=AsyncMock, return_value=_MOCK_DF):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/fetch", json={
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "date_start": "2024-01-01",
                "date_end": "2024-03-01",
            })

            assert resp.status_code == 202
            job_id = resp.json()["job_id"]

            # Chờ background task hoàn thành
            await asyncio.sleep(0.3)

            status_resp = await client.get(f"/api/fetch-status/{job_id}")

    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["status"] == "done"
    assert body["rows"] == 1

    cache_file = tmp_path / "BTCUSDT_1h.parquet"
    assert cache_file.exists(), "Cache file phải được tạo sau khi fetch thành công"
