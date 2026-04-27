import logging
import re
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.models import APIResponse, ErrorResponse, PreviewRequest, PreviewResponse, SessionItem
from backend.services import preview as preview_service
from backend.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

SESSION_FILENAME_PATTERN = re.compile(
    r"^([A-Z0-9]+)_([A-Za-z0-9]+)_(\d{8})\.parquet$"
)


def _parse_session_filename(filename: str) -> SessionItem | None:
    """Parse session metadata từ filename. Return None nếu không match pattern."""
    match = SESSION_FILENAME_PATTERN.match(filename)
    if not match:
        return None

    symbol, timeframe, date_raw = match.groups()
    # "20260420" → "2026-04-20"
    date_formatted = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}"

    return SessionItem(
        filename=filename,
        symbol=symbol,
        timeframe=timeframe,
        date=date_formatted,
        exported=False,  # Story 3.3 sẽ implement tracking
    )


@router.get("/sessions", response_model=APIResponse[list[SessionItem]])
async def list_sessions() -> APIResponse[list[SessionItem]]:
    """
    Trả về danh sách Parquet session files trong cache directory.
    Chỉ parse filename — không đọc nội dung file.
    """
    cache_dir: Path = settings.cache_dir

    # P2: check is_dir(), not just exists() — handles case where cache_dir is a file
    if not cache_dir.is_dir():
        return APIResponse(data=[], error=None)

    sessions: list[SessionItem] = []
    resolved_cache = cache_dir.resolve()
    # P5: sort by filename only (not full path) for consistent ordering
    for path in sorted(cache_dir.glob("*.parquet"), key=lambda p: p.name):
        # P3: skip symlinks that escape the cache directory
        if not path.resolve().is_relative_to(resolved_cache):
            continue
        session = _parse_session_filename(path.name)
        if session is not None:
            sessions.append(session)

    return APIResponse(data=sessions, error=None)


@router.post("/sessions/{filename}/preview", response_model=APIResponse[PreviewResponse])
async def preview_session(
    filename: str,
    request: PreviewRequest,
) -> APIResponse[PreviewResponse]:
    """
    POST thay vì GET vì request body required (trade list từ frontend).
    Đọc Parquet, compute EMA indicators (slice-first, Gap-1), trả về trade list + reasoning templates.
    """
    cache_dir = settings.cache_dir
    parquet_path = (cache_dir / filename).resolve()

    # P1: containment check — prevent path traversal
    if not parquet_path.is_relative_to(cache_dir.resolve()):
        return JSONResponse(  # type: ignore[return-value]
            status_code=400,
            content=APIResponse(
                error=ErrorResponse(
                    message="Invalid filename",
                    code="INVALID_FILENAME",
                    retryable=False,
                )
            ).model_dump(),
        )

    if not parquet_path.exists():
        return JSONResponse(  # type: ignore[return-value]
            status_code=404,
            content=APIResponse(
                error=ErrorResponse(
                    message="Session file không tồn tại — có thể đã bị xóa",
                    code="SESSION_NOT_FOUND",
                    retryable=False,
                )
            ).model_dump(),
        )

    try:
        result = await preview_service.build_preview(parquet_path, filename, request.trades)
        return APIResponse(data=result)
    except ValueError:
        logger.exception("Preview validation error for %s", filename)
        return JSONResponse(  # type: ignore[return-value]
            status_code=422,
            content=APIResponse(
                error=ErrorResponse(
                    message="Invalid session data or filename.",
                    code="INVALID_FILENAME",
                    retryable=False,
                )
            ).model_dump(),
        )
    except Exception as e:
        # P4: log full detail server-side, return static message to client
        logger.exception("Preview computation failed for %s", filename)
        return JSONResponse(  # type: ignore[return-value]
            status_code=500,
            content=APIResponse(
                error=ErrorResponse(
                    message="Preview computation failed. Please try again.",
                    code="PREVIEW_FAILED",
                    retryable=True,
                )
            ).model_dump(),
        )
