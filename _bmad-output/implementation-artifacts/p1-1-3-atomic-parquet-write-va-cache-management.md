# Story P1-1.3: Atomic Parquet write + cache management

Status: done

## Story

As a trader,
I want the cache to never be corrupted even if the server crashes mid-write,
so that I can trust the data is always complete and valid after any interruption.

## Acceptance Criteria

1. **Given** fetch hoàn thành và data sẵn sàng ghi
   **When** backend gọi `write_ohlcv()`
   **Then** backend write vào `{symbol}_{timeframe}.parquet.tmp` trước
   **And** rename thành `{symbol}_{timeframe}.parquet` chỉ khi write hoàn tất thành công
   **And** nếu `df.to_parquet()` raise exception (ví dụ: disk full), file `.tmp` bị xóa và exception được re-raise

2. **Given** server khởi động lại sau khi bị kill giữa chừng khi đang write
   **When** `lifespan` startup event chạy
   **Then** tất cả file `*.parquet.tmp` trong `cache_dir` bị xóa tự động
   **And** log message được emit cho mỗi file `.tmp` bị xóa (ví dụ: `"Cleaned up stale temp file: BTCUSDT_1h.parquet.tmp"`)
   **And** server khởi động thành công ngay cả khi không có file `.tmp` nào

3. **Given** Parquet file bị corrupt (không parse được bởi pyarrow)
   **When** backend gọi `read_ohlcv()` (via GET /api/ohlcv)
   **Then** backend tự động xóa file corrupt bằng `path.unlink(missing_ok=True)`
   **And** raise `CacheCorruptError` → route trả về 404 với `{code: "cache_corrupted", retryable: true}`
   **And** file `.parquet` bị xóa — không còn tồn tại sau request

   *(Note: AC3 đã được implement trong Story 1.1 — dev chỉ cần viết unit test cho logic này trong `test_cache.py`)*

4. **Given** cache file tồn tại và hợp lệ
   **When** backend load và validate trong `read_ohlcv()`
   **Then** duplicate timestamps bị dedup, data được sort ascending theo timestamp
   **And** OHLCV columns được validate: timestamp int64, OHLCV float64

   *(Note: AC4 đã được implement trong Story 1.1 — dev chỉ cần viết unit test trong `test_cache.py`)*

5. **Given** `write_ohlcv()` chạy từ Story 1.2 để lưu Binance data
   **When** Story 1.3 upgrade atomic write
   **Then** GET /api/ohlcv sau đó vẫn serve đúng data (regression: atomic write không break read path)

## Tasks / Subtasks

- [x] Task 1: Upgrade `backend/services/cache.py` — `write_ohlcv` thành atomic (AC: #1)
  - [x] Thêm `_tmp_path()` helper: `return cache_dir / f"{symbol}_{timeframe}.parquet.tmp"`
  - [x] Trong `write_ohlcv`: write sang `.tmp` trước (`df.to_parquet(tmp_path, index=False)`)
  - [x] Rename `.tmp` → `.parquet` bằng `os.replace(tmp, final_path)` (atomic + cross-platform)
  - [x] Trong except block: `tmp_path.unlink(missing_ok=True)` rồi re-raise exception
  - [x] Đảm bảo `cache_dir.mkdir(parents=True, exist_ok=True)` vẫn còn trước khi write

- [x] Task 2: Thêm `.tmp` cleanup vào `backend/main.py` lifespan startup (AC: #2)
  - [x] Trong `lifespan()` — phần `# Startup` — scan `settings.cache_dir.glob("*.parquet.tmp")`
  - [x] Xóa từng file `.tmp` bằng `path.unlink(missing_ok=True)`
  - [x] Dùng `_logger.warning("Cleaned up stale temp file: %s", tmp_file.name)` để log
  - [x] Bao trong `try/except` để không crash server nếu `cache_dir` chưa tồn tại khi startup

- [x] Task 3: Tạo `tests/test_cache.py` — unit tests cho cache module (AC: #1–#5)
  - [x] Test atomic write happy path: file `.parquet` tồn tại sau write, file `.tmp` KHÔNG tồn tại
  - [x] Test atomic write failure: mock `df.to_parquet` raise `OSError` → `.tmp` bị xóa, `.parquet` không được tạo
  - [x] Test `.tmp` cleanup khi write succeed: intermediate `.tmp` không còn sau rename
  - [x] Test corrupt detection: tạo file `.parquet` với nội dung rác → `read_ohlcv` raise `CacheCorruptError` + file bị xóa
  - [x] Test missing columns: DataFrame thiếu column "volume" → `CacheCorruptError`
  - [x] Test dedup + sort: DataFrame có duplicate timestamps → output sorted và deduped
  - [x] Test no_cache: file không tồn tại → trả về `None`
  - [x] Test regression: `write_ohlcv()` rồi `read_ohlcv()` → data match

## Dev Notes

### Context brownfield quan trọng

Story 1.1 đã implement `read_ohlcv` với corrupt detection, dedup, sort, và dtype validation hoàn chỉnh. Story 1.2 đã thêm `write_ohlcv` dạng **plain write** vào cuối `cache.py` với comment rõ ràng:

```python
def write_ohlcv(df: pd.DataFrame, symbol: str, timeframe: str, cache_dir: Path) -> None:
    """Plain write — Story 1.3 sẽ upgrade sang atomic write (temp → rename)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(symbol, timeframe, cache_dir)
    df.to_parquet(path, index=False)
```

**Story 1.3 thay thế implementation này** bằng atomic write pattern. Đây là upgrade tại chỗ, không phải viết mới.

### Atomic write pattern (Gap 2)

```python
# backend/services/cache.py

def _tmp_path(symbol: str, timeframe: str, cache_dir: Path) -> Path:
    symbol = symbol.replace("/", "")
    return cache_dir / f"{symbol}_{timeframe}.parquet.tmp"


def write_ohlcv(df: pd.DataFrame, symbol: str, timeframe: str, cache_dir: Path) -> None:
    """Atomic write: write-to-temp then rename. Tránh partial write corruption (Gap 2)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    final_path = _cache_path(symbol, timeframe, cache_dir)
    tmp = _tmp_path(symbol, timeframe, cache_dir)
    try:
        df.to_parquet(tmp, index=False)
    except Exception:
        tmp.unlink(missing_ok=True)  # cleanup nếu write bị ngắt
        raise
    tmp.rename(final_path)  # atomic trên cùng filesystem (POSIX rename)
```

**Tại sao `rename` là atomic:** Trên POSIX filesystem (macOS, Linux), `os.rename()` — và do đó `Path.rename()` — là atomic khi source và destination cùng một filesystem. Đây là đảm bảo OS-level: process kill sau rename thành công = file hoàn chỉnh; process kill trước rename = chỉ có file `.tmp` (bị cleanup khi restart).

**Windows note:** `Path.rename()` trên Windows không atomic nếu destination tồn tại. Dùng `os.replace()` thay thế cho cross-platform. MVP target là macOS/Linux, nhưng an toàn hơn dùng `os.replace()` từ đầu.

```python
import os

# Thay tmp.rename(final_path) bằng:
os.replace(tmp, final_path)  # atomic trên POSIX, cross-platform safe
```

### `.tmp` cleanup trong lifespan

```python
# backend/main.py
import logging

_logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: cleanup stale temp files từ crash/kill trước đó
    try:
        for tmp_file in settings.cache_dir.glob("*.parquet.tmp"):
            tmp_file.unlink(missing_ok=True)
            _logger.warning("Cleaned up stale temp file: %s", tmp_file.name)
    except (OSError, FileNotFoundError):
        pass  # cache_dir chưa tồn tại — không sao
    yield
    # Shutdown: nothing to clean up yet
```

**Pattern hiện tại của `lifespan`:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: cache_dir đã được tạo bởi settings.model_post_init
    yield
    # Shutdown: nothing to clean up yet
```
→ Dev cần **thêm cleanup block** vào trước `yield`, giữ nguyên comment `# Shutdown`.

### File thực tế cần chỉnh sửa

**File `backend/main.py` hiện có:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: cache_dir đã được tạo bởi settings.model_post_init
    yield
    # Shutdown: nothing to clean up yet
```

**Sau khi sửa:**
```python
import logging

_logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: cleanup stale .tmp files từ crash/kill trước đó (Gap 2)
    try:
        for tmp_file in settings.cache_dir.glob("*.parquet.tmp"):
            tmp_file.unlink(missing_ok=True)
            _logger.warning("Cleaned up stale temp file: %s", tmp_file.name)
    except (OSError, FileNotFoundError):
        pass
    yield
    # Shutdown: nothing to clean up yet
```

**File `backend/services/cache.py` hiện có `write_ohlcv` tại dòng ~43:**
```python
def write_ohlcv(df: pd.DataFrame, symbol: str, timeframe: str, cache_dir: Path) -> None:
    """Plain write — Story 1.3 sẽ upgrade sang atomic write (temp → rename)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(symbol, timeframe, cache_dir)
    df.to_parquet(path, index=False)
```
→ Replace hoàn toàn bằng atomic version (xem pattern ở trên).

### Files cần modify

| File | Thay đổi |
|------|---------|
| `backend/services/cache.py` | Replace `write_ohlcv` với atomic version, thêm `_tmp_path()` helper, thêm `import os` |
| `backend/main.py` | Thêm `.tmp` cleanup trong lifespan startup, thêm `import logging` và `_logger` |

### Files cần tạo mới

| File | Nội dung |
|------|---------|
| `tests/test_cache.py` | Unit tests cho `write_ohlcv` (atomic), `read_ohlcv` (corrupt, dedup, sort), cleanup |

### Files KHÔNG được touch

- `backend/routes/fetch.py` — scope của Story 1.2 (đang `ready-for-dev`)
- `backend/routes/ohlcv.py` — Story 1.1 đã done
- `backend/services/binance.py` — Story 1.2
- `backend/services/job_manager.py` — Story 1.2
- `backend/models.py` — không có model nào cần thêm cho story này
- Bất kỳ Phase 2 file nào

### Testing pattern (ADR-10)

```python
# tests/test_cache.py
"""Unit tests cho backend/services/cache.py — Story P1-1-3."""
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from backend.services.cache import (
    CacheCorruptError,
    read_ohlcv,
    write_ohlcv,
)

BASE_TS = 1_704_067_200_000  # 2024-01-01 00:00:00 UTC ms
INTERVAL_1H = 3_600_000


def _make_df(n: int = 10) -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": [BASE_TS + i * INTERVAL_1H for i in range(n)],
        "open": [42000.0] * n,
        "high": [42100.0] * n,
        "low": [41900.0] * n,
        "close": [42050.0] * n,
        "volume": [100.0] * n,
    })


def test_atomic_write_happy_path(tmp_path):
    """Sau write: .parquet tồn tại, .tmp KHÔNG tồn tại."""
    df = _make_df()
    write_ohlcv(df, "BTCUSDT", "1h", tmp_path)
    assert (tmp_path / "BTCUSDT_1h.parquet").exists()
    assert not (tmp_path / "BTCUSDT_1h.parquet.tmp").exists()


def test_atomic_write_failure_cleanup(tmp_path):
    """.tmp bị xóa nếu to_parquet raise exception."""
    df = _make_df()
    with patch("pandas.DataFrame.to_parquet", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            write_ohlcv(df, "BTCUSDT", "1h", tmp_path)
    assert not (tmp_path / "BTCUSDT_1h.parquet.tmp").exists()
    assert not (tmp_path / "BTCUSDT_1h.parquet").exists()


def test_read_write_roundtrip(tmp_path):
    """write rồi read → data khớp."""
    df = _make_df(n=5)
    write_ohlcv(df, "BTCUSDT", "1h", tmp_path)
    result = read_ohlcv("BTCUSDT", "1h", tmp_path)
    assert result is not None
    assert list(result["timestamp"]) == list(df["timestamp"])


def test_corrupt_detection(tmp_path):
    """File rác → CacheCorruptError + file bị xóa."""
    path = tmp_path / "BTCUSDT_1h.parquet"
    path.write_bytes(b"this is not a parquet file")
    with pytest.raises(CacheCorruptError):
        read_ohlcv("BTCUSDT", "1h", tmp_path)
    assert not path.exists()


def test_missing_columns(tmp_path):
    """DataFrame thiếu column 'volume' → CacheCorruptError."""
    df = _make_df().drop(columns=["volume"])
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)
    with pytest.raises(CacheCorruptError):
        read_ohlcv("BTCUSDT", "1h", tmp_path)


def test_dedup_and_sort(tmp_path):
    """Duplicate timestamps bị dedup, output sort ascending."""
    df = pd.DataFrame({
        "timestamp": [BASE_TS + 2 * INTERVAL_1H, BASE_TS, BASE_TS + INTERVAL_1H, BASE_TS],
        "open": [1.0, 2.0, 3.0, 4.0],
        "high": [1.0, 2.0, 3.0, 4.0],
        "low": [1.0, 2.0, 3.0, 4.0],
        "close": [1.0, 2.0, 3.0, 4.0],
        "volume": [1.0, 2.0, 3.0, 4.0],
    })
    df.to_parquet(tmp_path / "BTCUSDT_1h.parquet", index=False)
    result = read_ohlcv("BTCUSDT", "1h", tmp_path)
    assert result is not None
    assert len(result) == 3  # 1 duplicate bị xóa
    assert list(result["timestamp"]) == sorted(result["timestamp"].tolist())


def test_no_cache_returns_none(tmp_path):
    """Cache không tồn tại → None."""
    result = read_ohlcv("BTCUSDT", "1h", tmp_path)
    assert result is None
```

### Scope boundary — Story 1.3 vs kế tiếp

| Feature | Story 1.3 (này) | Story kế tiếp |
|---------|----------------|--------------|
| Atomic write (temp→rename) | ✓ | |
| `.tmp` cleanup at startup | ✓ | |
| `test_cache.py` unit tests | ✓ | |
| Corrupt detection (read path) | đã done (Story 1.1) | |
| Dedup + sort + dtype validate | đã done (Story 1.1) | |
| **Full pagination** Binance | | Story 1.4 |
| **Rate-limit + auto-retry** | | Story 1.4 |
| **Partial batch validation** | | Story 1.4 |
| **Data gap detection** | | Story 1.5 |

Story này đơn giản nhưng critical về data integrity. Dev không cần viết nhiều code mới — chủ yếu là replace `write_ohlcv` và thêm startup cleanup + test coverage.

### Verify atomic write sau khi implement

```python
# Quick manual verification trong Python REPL:
import pandas as pd
from pathlib import Path
from backend.services.cache import write_ohlcv, read_ohlcv

tmp = Path("/tmp/test_cache")
tmp.mkdir(exist_ok=True)
df = pd.DataFrame({"timestamp": [1000], "open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0]})

write_ohlcv(df, "TEST", "1h", tmp)
assert (tmp / "TEST_1h.parquet").exists()
assert not (tmp / "TEST_1h.parquet.tmp").exists()
print("Atomic write OK")
```

### References

- Architecture Gap 2 (Atomic Parquet Write): `_bmad-output/planning-artifacts/architecture.md#Gap-2`
- Architecture ADR-09 (module structure): `_bmad-output/planning-artifacts/architecture.md#ADR-09`
- Architecture ADR-10 (testing strategy): `_bmad-output/planning-artifacts/architecture.md#ADR-10`
- Epic story definition: `_bmad-output/planning-artifacts/epics-phase1.md#Story-1.3`
- Previous story P1-1.2: `_bmad-output/implementation-artifacts/p1-1-2-post-api-fetch-async-binance-fetch-voi-sse-progress.md`
- Story P1-1.1 (cache.py read_ohlcv impl): `_bmad-output/implementation-artifacts/p1-1-1-get-api-ohlcv-serve-ohlcv-tu-parquet-cache.md`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6 (2026-04-29)

### Debug Log References

- `cache.py` đã bị thay đổi trước bởi external process — có `CacheSchemaError` và `_SYMBOL_RE` thêm vào. Khi rewrite `cache.py`, `ohlcv.py` import `CacheSchemaError` bị broken. Giải pháp: thêm `CacheSchemaError = CacheCorruptError` alias để backward-compatible mà không cần touch `ohlcv.py`.

### Completion Notes List

- ✅ `backend/services/cache.py`: `write_ohlcv` upgraded sang atomic pattern (`write .tmp` → `os.replace` → final). Thêm `_tmp_path()` helper. Thêm `CacheSchemaError` alias để backward-compatible.
- ✅ `backend/main.py`: Lifespan startup cleanup `.parquet.tmp` files với logging. Bao trong `try/except OSError`.
- ✅ `tests/test_cache.py`: 10 unit tests bao phủ ACs #1–#5 — 10/10 pass, 123/123 total pass.

### Change Log

- 2026-04-29: Implement Story P1-1-3 — Atomic Parquet write + cache management. Upgrade write_ohlcv, thêm lifespan cleanup, viết 10 unit tests.

### File List

- `backend/services/cache.py` — MODIFIED (atomic write, _tmp_path, CacheSchemaError alias)
- `backend/main.py` — MODIFIED (lifespan .tmp cleanup + logging)
- `tests/test_cache.py` — NEW
