import pandas as pd


def compute_indicators(
    df: pd.DataFrame,
    date_end_idx: int,
    ema_period: int | None,
    ma_period: int | None,
) -> pd.DataFrame:
    # CRITICAL: slice to date_end_idx on the FULL df BEFORE computing — no look-ahead
    sliced = df.iloc[:date_end_idx].copy()

    if ema_period:
        sliced[f"ema_{ema_period}"] = sliced["close"].ewm(span=ema_period, adjust=False).mean()
    if ma_period:
        sliced[f"ma_{ma_period}"] = sliced["close"].rolling(window=ma_period).mean()

    return sliced
