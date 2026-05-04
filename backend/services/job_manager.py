import asyncio
import time
import uuid

_active_tasks: dict[tuple[str, str], asyncio.Task] = {}
_job_progress: dict[str, dict] = {}
_job_key_map: dict[str, tuple[str, str]] = {}
_job_completed_at: dict[str, float] = {}

_JOB_TTL = 300  # 5 phút


def _cleanup_expired_jobs() -> None:
    now = time.time()
    expired = [jid for jid, ts in _job_completed_at.items() if now - ts > _JOB_TTL]
    for jid in expired:
        _job_progress.pop(jid, None)
        _job_completed_at.pop(jid, None)


def start_job(symbol: str, timeframe: str) -> str:
    """Trả về job_id. Raise ValueError nếu job đang chạy (caller map sang 409)."""
    _cleanup_expired_jobs()
    key = (symbol, timeframe)
    if key in _active_tasks and not _active_tasks[key].done():
        raise ValueError("FETCH_IN_PROGRESS")
    job_id = str(uuid.uuid4())
    _job_key_map[job_id] = key
    _job_progress[job_id] = {
        "status": "running",
        "percent": 0,
        "status_text": "Starting...",
        "error": None,
        "rows": None,
    }
    return job_id


def register_task(job_id: str, task: asyncio.Task) -> None:
    key = _job_key_map[job_id]
    _active_tasks[key] = task


def update_progress(job_id: str, percent: int, status_text: str) -> None:
    if job_id in _job_progress:
        _job_progress[job_id]["percent"] = percent
        _job_progress[job_id]["status_text"] = status_text


def complete_job(job_id: str, rows: int) -> None:
    _cleanup_expired_jobs()
    if job_id in _job_progress:
        _job_progress[job_id]["status"] = "done"
        _job_progress[job_id]["percent"] = 100
        _job_progress[job_id]["rows"] = rows
    _job_completed_at[job_id] = time.time()
    key = _job_key_map.pop(job_id, None)
    if key:
        _active_tasks.pop(key, None)


def fail_job(job_id: str, message: str) -> None:
    _cleanup_expired_jobs()
    if job_id in _job_progress:
        _job_progress[job_id]["status"] = "error"
        _job_progress[job_id]["error"] = message
    _job_completed_at[job_id] = time.time()
    key = _job_key_map.pop(job_id, None)
    if key:
        _active_tasks.pop(key, None)


def cancel_job(job_id: str) -> bool:
    """Cancel task và cleanup. Trả về True nếu job tồn tại."""
    key = _job_key_map.get(job_id)
    if not key:
        return False
    task = _active_tasks.get(key)
    if task and not task.done():
        task.cancel()
    # F4: cleanup progress/key_map TRƯỚC khi task thực sự dừng — task's fail_job
    # call sẽ thấy job_id không còn và skip (no-op), đây là intended behavior.
    _job_progress.pop(job_id, None)
    _job_key_map.pop(job_id, None)
    _active_tasks.pop(key, None)
    _job_completed_at.pop(job_id, None)
    return True


def get_progress(job_id: str) -> dict | None:
    _cleanup_expired_jobs()
    return _job_progress.get(job_id)
