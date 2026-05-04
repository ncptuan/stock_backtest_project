from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from backend.models import ErrorResponse, OHLCVBar, OHLCVResponse
from backend.services.cache import CacheCorruptError, CacheSchemaError, detect_gaps, read_ohlcv
from backend.services.indicators import compute_indicators
from backend.settings import Settings, get_settings

router = APIRouter()

_VALID_TIMEFRAMES = {"5m", "30m", "1h", "4h", "1D"}
_INDICATOR_PERIOD = 20


def _date_to_ms(date_str: str) -> int:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str!r}. Expected YYYY-MM-DD.")
    return int(dt.timestamp() * 1000)


def _ms_to_date(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


@router.get("/api/ohlcv")
async def get_ohlcv(
    symbol: str = Query(...),
    timeframe: str = Query(...),
    date_start: str = Query(...),
    date_end: str = Query(...),
    ma: int | None = Query(default=None),
    ema: int | None = Query(default=None),
    settings: Settings = Depends(get_settings),
):
    if timeframe not in _VALID_TIMEFRAMES:
        return JSONResponse(
            status_code=422,
            content={
                "error": ErrorResponse(
                    message=f"Timeframe '{timeframe}' không hợp lệ. Hỗ trợ: {sorted(_VALID_TIMEFRAMES)}",
                    code="invalid_timeframe",
                    retryable=False,
                ).model_dump()
            },
        )

    # F7(A): only period=20 supported; reject other values
    if ma is not None and ma != _INDICATOR_PERIOD:
        return JSONResponse(
            status_code=422,
            content={
                "error": ErrorResponse(
                    message=f"ma phải là {_INDICATOR_PERIOD} (nhận được {ma})",
                    code="invalid_indicator_period",
                    retryable=False,
                ).model_dump()
            },
        )
    if ema is not None and ema != _INDICATOR_PERIOD:
        return JSONResponse(
            status_code=422,
            content={
                "error": ErrorResponse(
                    message=f"ema phải là {_INDICATOR_PERIOD} (nhận được {ema})",
                    code="invalid_indicator_period",
                    retryable=False,
                ).model_dump()
            },
        )

    # F5: reject non-positive periods (redundant after F7 check but kept for safety)
    if (ma is not None and ma < 1) or (ema is not None and ema < 1):
        return JSONResponse(
            status_code=422,
            content={
                "error": ErrorResponse(
                    message="ma/ema phải >= 1",
                    code="invalid_indicator_period",
                    retryable=False,
                ).model_dump()
            },
        )

    # F4: validate date format
    try:
        date_start_ms = _date_to_ms(date_start)
        date_end_ms = _date_to_ms(date_end)
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": ErrorResponse(
                    message=str(exc),
                    code="invalid_date",
                    retryable=False,
                ).model_dump()
            },
        )

    # F11: date_start must not be after date_end
    if date_start_ms > date_end_ms:
        return JSONResponse(
            status_code=422,
            content={
                "error": ErrorResponse(
                    message=f"date_start ({date_start}) phải <= date_end ({date_end})",
                    code="invalid_date_range",
                    retryable=False,
                ).model_dump()
            },
        )

    # F1: symbol validation happens inside read_ohlcv → _cache_path (raises ValueError)
    try:
        df = read_ohlcv(symbol, timeframe, settings.cache_dir)
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": ErrorResponse(
                    message=str(exc),
                    code="invalid_symbol",
                    retryable=False,
                ).model_dump()
            },
        )
    except CacheCorruptError:
        return JSONResponse(
            status_code=404,
            content={
                "error": ErrorResponse(
                    message="Cache bị lỗi và đã được xóa — fetch lại để tạo mới",
                    code="cache_corrupted",
                    retryable=True,
                ).model_dump()
            },
        )
    except CacheSchemaError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": ErrorResponse(
                    message=f"Cache schema không hợp lệ: {exc}",
                    code="cache_schema_invalid",
                    retryable=False,
                ).model_dump()
            },
        )

    if df is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": ErrorResponse(
                    message=f"Chưa có data cho {symbol} {timeframe} — fetch trước",
                    code="no_cache",
                    retryable=False,
                ).model_dump()
            },
        )

    actual_start_ms = int(df["timestamp"].min())
    actual_end_ms = int(df["timestamp"].max())

    # F10: track which sides are clipped independently
    start_clipped = date_start_ms < actual_start_ms
    end_clipped = date_end_ms > actual_end_ms
    clipped = start_clipped or end_clipped

    mask = (df["timestamp"] >= date_start_ms) & (df["timestamp"] <= date_end_ms)
    sliced = df[mask].copy()

    # F2(A): compute indicators on full df up to date_end (proper warm-up)
    if ma or ema:
        date_end_idx = int((df["timestamp"] <= date_end_ms).sum())
        df_with_indicators = compute_indicators(df, date_end_idx, ema, ma)
        # Extract only the rows in the requested slice
        sliced = df_with_indicators[df_with_indicators["timestamp"].isin(sliced["timestamp"])].copy()
        if ema:
            sliced = sliced.rename(columns={f"ema_{ema}": "ema_20"})
        if ma:
            sliced = sliced.rename(columns={f"ma_{ma}": "ma_20"})

    bars: list[OHLCVBar] = []
    for row in sliced.itertuples(index=False):
        bar_data = {
            "timestamp": int(row.timestamp),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
        }
        # F9: explicit None check before float conversion
        if hasattr(row, "ema_20"):
            v = row.ema_20
            bar_data["ema_20"] = None if (v is None or v != v) else float(v)
        if hasattr(row, "ma_20"):
            v = row.ma_20
            bar_data["ma_20"] = None if (v is None or v != v) else float(v)
        bars.append(OHLCVBar(**bar_data))

    gaps = detect_gaps(sliced, timeframe)

    response = OHLCVResponse(
        data=bars,
        clipped=clipped,
        actual_date_start=_ms_to_date(actual_start_ms) if start_clipped else None,
        actual_date_end=_ms_to_date(actual_end_ms) if end_clipped else None,
        has_gaps=len(gaps) > 0,
        gaps=gaps,
    )
    return response
