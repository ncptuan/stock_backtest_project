"""
backend/routes/export.py
Story 3.1 + 4.2 + 4.3: POST /api/export — write to Supabase signal_comparisons + signal_cases.

Flow:
  1. Guard: 503 if supabase_enabled=False
  2. Quality gate: 422 if trades < 10 or win_rate < 55% (fast fail, no network)
  3. Credential validation: 401 if API keys invalid
  4. Duplicate check: 409 if session already exported
  5. write_signal_comparisons → 504/500 on fail (no rollback needed)
  6. write_signal_cases → on fail, rollback signal_comparisons → 504/500
  7. 200 success with counts and first_signal_id
"""
import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException

from backend.models import APIResponse, ExportRequest, ExportResponse
from backend.services.supabase import (
    _parse_session_date,
    check_duplicate,
    generate_signal_id,
    rollback_signal_comparisons,
    validate_credentials,
    write_signal_cases,
    write_signal_comparisons,
)
from backend.settings import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/export", response_model=APIResponse[ExportResponse])
async def export_session(
    request: ExportRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> APIResponse[ExportResponse]:
    # 1. Guard: Supabase disabled
    if not settings.supabase_enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "disabled",
                "message": "Supabase integration chưa được bật — set SUPABASE_ENABLED=true trong .env",
            },
        )

    # 2. Quality gate — fast fail, no network (FR10, FR11)
    trade_count = len(request.trades)
    win_rate = request.session_win_rate
    qg_reasons: list[str] = []
    if trade_count < 10:
        qg_reasons.append(f"{trade_count} trades — cần tối thiểu 10")
    if win_rate < 0.55:
        pct = int(round(win_rate * 100))
        qg_reasons.append(f"{pct}% win rate — cần tối thiểu 55%")
    if qg_reasons:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "quality_gate",
                "message": "; ".join(qg_reasons),
            },
        )

    # 3. Credential validation — before any write operation
    try:
        await validate_credentials(settings)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_credentials",
                "message": str(exc),
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

    # 4. Parse session date + duplicate check
    session_date = _parse_session_date(request.session_filename)

    try:
        is_dup = await check_duplicate(session_date, request.strategy_name, settings)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={
                "error": "timeout",
                "message": "Supabase đang wake up — thử lại sau 30 giây",
            },
        )

    if is_dup:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "duplicate",
                "message": (
                    f"Session {request.session_filename} đã export — "
                    "xóa rows trên Supabase trước nếu muốn re-export"
                ),
            },
        )

    # 5. Write signal_comparisons (anon key)
    sc_count = 0
    try:
        sc_count = await write_signal_comparisons(request.trades, request, settings)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={
                "error": "timeout",
                "message": "Supabase đang wake up — thử lại sau 30 giây",
            },
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": "write_failed", "message": str(exc)},
        )

    # 6. Write signal_cases (service role key) — rollback on failure
    try:
        cases_count = await write_signal_cases(request.trades, request, settings)
    except (httpx.TimeoutException, ValueError) as exc:
        rolled_back = 0
        try:
            rolled_back = await rollback_signal_comparisons(
                session_date, request.strategy_name, settings
            )
        except Exception as rollback_err:
            logger.error(
                "Rollback also failed after signal_cases error: %s", rollback_err
            )

        error_msg = str(exc)
        is_timeout = isinstance(exc, httpx.TimeoutException)
        logger.error(
            "Export failed, rolled back %d signal_comparisons rows. Error: %s",
            rolled_back,
            error_msg,
        )
        raise HTTPException(
            status_code=504 if is_timeout else 500,
            detail={
                "error": "timeout" if is_timeout else "partial_write_rolled_back",
                "message": (
                    "Supabase đang wake up — thử lại sau 30 giây"
                    if is_timeout
                    else (
                        "Authentication failed cho signal_cases (RLS enabled) — "
                        "Kiểm tra SUPABASE_SERVICE_KEY trong .env. "
                        "Đã rollback signal_comparisons."
                    )
                ),
            },
        )

    # 5. Success
    first_signal_id = ""
    if request.trades:
        first_signal_id = generate_signal_id(
            session_date, request.strategy_name, request.trades[0].bar_index
        )
    supabase_url = (
        f"{settings.supabase_url}/rest/v1/signal_cases"
        f"?order=signal_id.desc&limit=50"
    )

    logger.info(
        "Exported session %s: %d signal_comparisons + %d signal_cases",
        request.session_filename,
        sc_count,
        cases_count,
    )

    return APIResponse(
        data=ExportResponse(
            signal_comparisons_count=sc_count,
            signal_cases_count=cases_count,
            first_signal_id=first_signal_id,
            supabase_url=supabase_url,
        ),
        error=None,
    )
