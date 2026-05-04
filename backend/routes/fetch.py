import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.models import FetchJobResponse, FetchRequest, FetchStatusResponse
from backend.services import binance, cache, job_manager
from backend.settings import Settings, get_settings

router = APIRouter()

# F10: derive from TIMEFRAME_MAP to keep in sync
_VALID_TIMEFRAMES: set[str] = set(binance.TIMEFRAME_MAP.keys())

_HEARTBEAT_INTERVAL = 15.0   # seconds
_POLL_INTERVAL = 0.5          # seconds


async def _run_fetch_job(
    job_id: str,
    symbol: str,
    timeframe: str,
    date_start: str,
    date_end: str,
    cache_dir,
    mode: str = "full",
) -> None:
    try:
        def on_progress(percent: int, status_text: str) -> None:
            job_manager.update_progress(job_id, percent, status_text)

        if mode == "refresh":
            max_ts = binance.get_cached_max_timestamp(symbol, timeframe, cache_dir)
            if max_ts is not None:
                interval_ms = binance._INTERVAL_MS[timeframe]
                from datetime import datetime, timezone
                new_start_ms = max_ts + interval_ms
                date_start_refresh = datetime.fromtimestamp(
                    new_start_ms / 1000, tz=timezone.utc
                ).strftime("%Y-%m-%d")
                date_end_refresh = date_end or datetime.now(timezone.utc).strftime("%Y-%m-%d")

                new_df = await binance.fetch_ohlcv(
                    symbol, timeframe, date_start_refresh, date_end_refresh, on_progress
                )
                cached_df = cache.read_ohlcv(symbol, timeframe, cache_dir)
                if cached_df is not None:
                    import pandas as pd
                    merged = pd.concat([cached_df, new_df], ignore_index=True)
                    merged = merged.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
                    cache.write_ohlcv(merged, symbol, timeframe, cache_dir)
                else:
                    cache.write_ohlcv(new_df, symbol, timeframe, cache_dir)
                job_manager.complete_job(job_id, rows=len(new_df))
                return
            # Fallback to full fetch if cache is empty

        df = await binance.fetch_ohlcv(symbol, timeframe, date_start, date_end, on_progress)
        cache.write_ohlcv(df, symbol, timeframe, cache_dir)
        job_manager.complete_job(job_id, rows=len(df))

    except asyncio.CancelledError:
        job_manager.fail_job(job_id, "Cancelled")
        raise  # MUST re-raise — do not swallow CancelledError

    except Exception as e:
        job_manager.fail_job(job_id, str(e))


async def _sse_generator(job_id: str):
    """SSE generator với heartbeat mỗi 15s khi không có progress event."""
    loop = asyncio.get_running_loop()  # F3: không dùng get_event_loop() deprecated
    last_event_time = loop.time()

    while True:
        progress = job_manager.get_progress(job_id)
        if progress is None:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
            return

        status = progress["status"]

        if status == "done":
            yield f"data: {json.dumps({'type': 'done', 'rows': progress.get('rows', 0)})}\n\n"
            return
        elif status == "error":
            yield f"data: {json.dumps({'type': 'error', 'message': progress.get('error', 'Unknown error')})}\n\n"
            return
        else:
            yield f"data: {json.dumps({'type': 'progress', 'percent': progress['percent'], 'status': progress['status_text']})}\n\n"
            last_event_time = loop.time()  # F2: reset timer sau mỗi progress event

        # F2: heartbeat chỉ gửi khi không có progress event trong 15s
        now = loop.time()
        if now - last_event_time >= _HEARTBEAT_INTERVAL:
            yield f"data: {json.dumps({'type': 'ping'})}\n\n"
            last_event_time = now

        await asyncio.sleep(_POLL_INTERVAL)


@router.post("/api/fetch", status_code=202)
async def start_fetch(
    req: FetchRequest,
    settings: Settings = Depends(get_settings),
) -> FetchJobResponse:
    symbol = req.symbol.upper().replace("/", "")

    if req.timeframe not in _VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=422,
            detail={"message": f"Invalid timeframe '{req.timeframe}'", "code": "INVALID_TIMEFRAME", "retryable": False},
        )

    # F18: validate symbol — _cache_path raises ValueError for invalid symbols
    try:
        job_id = job_manager.start_job(symbol, req.timeframe)
    except ValueError as e:
        err_str = str(e)
        if "FETCH_IN_PROGRESS" in err_str:
            raise HTTPException(
                status_code=409,
                detail={"message": "Fetch already in progress", "code": "FETCH_IN_PROGRESS", "retryable": False},
            )
        raise HTTPException(
            status_code=422,
            detail={"message": err_str, "code": "INVALID_SYMBOL", "retryable": False},
        )

    # Validate symbol via cache path before scheduling task
    from backend.services.cache import _cache_path
    try:
        _cache_path(symbol, req.timeframe, settings.cache_dir)
    except ValueError as exc:
        job_manager.cancel_job(job_id)
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "code": "INVALID_SYMBOL", "retryable": False},
        )

    task = asyncio.create_task(
        _run_fetch_job(job_id, symbol, req.timeframe, req.date_start, req.date_end, settings.cache_dir, mode=req.mode)
    )
    job_manager.register_task(job_id, task)

    return FetchJobResponse(job_id=job_id)


@router.get("/api/fetch-stream/{job_id}")
async def fetch_stream(job_id: str):
    if job_manager.get_progress(job_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Job not found", "code": "JOB_NOT_FOUND", "retryable": False},
        )

    return StreamingResponse(
        _sse_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/fetch-status/{job_id}")
async def fetch_status(job_id: str) -> FetchStatusResponse:
    progress = job_manager.get_progress(job_id)
    if progress is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Job not found", "code": "JOB_NOT_FOUND", "retryable": False},
        )

    return FetchStatusResponse(
        job_id=job_id,
        status=progress["status"],
        percent=progress["percent"],
        status_text=progress["status_text"],
        error=progress.get("error"),
        rows=progress.get("rows"),
    )


@router.delete("/api/fetch/{job_id}", status_code=204)
async def cancel_fetch(job_id: str):
    if not job_manager.cancel_job(job_id):
        raise HTTPException(
            status_code=404,
            detail={"message": "Job not found", "code": "JOB_NOT_FOUND", "retryable": False},
        )
