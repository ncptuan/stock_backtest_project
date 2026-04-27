"""
Tests cho Story 2.1: POST /api/sessions/{filename}/preview

Covers ACs #1–#7:
  - AC1: file tồn tại, valid trades → 200, đúng shape
  - AC2: slice-first EMA enforcement (Gap-1)
  - AC3: file không tồn tại → 404 + error message
  - AC4: 7 trades, 71% WR → fail (trade count)
  - AC5: 25 trades, 48% WR (12/25) → fail (win rate)
  - AC6: 31 trades, 67% WR → pass
  - AC7: empty trades → fail (0 trades)
"""
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.settings import settings

client = TestClient(app)

BASE_TS = 1_745_625_600_000   # 2026-04-20 00:00:00 UTC ms
INTERVAL_4H = 4 * 60 * 60 * 1_000


def _make_parquet(tmp_path: Path, n: int = 60) -> Path:
    """
    Tạo BTCUSDT_4h_20260420.parquet với n bars.
    Close price = 40000 + i*100 (tăng dần → EMA slice < EMA full df).
    Volume = 1000 (constant, vol_ratio ≈ 1.0x).
    """
    data = {
        "timestamp": [BASE_TS + i * INTERVAL_4H for i in range(n)],
        "open": [40000.0 + i * 100 for i in range(n)],
        "high": [40100.0 + i * 100 for i in range(n)],
        "low": [39900.0 + i * 100 for i in range(n)],
        "close": [40050.0 + i * 100 for i in range(n)],
        "volume": [1000.0] * n,
    }
    df = pd.DataFrame(data)
    path = tmp_path / "BTCUSDT_4h_20260420.parquet"
    df.to_parquet(path, index=False)
    return path


def _trade(bar_index: int, result: str = "win", entry_price: float | None = None) -> dict:
    ep = entry_price if entry_price is not None else (40050.0 + bar_index * 100)
    return {
        "bar_index": bar_index,
        "entry_timestamp_ms": BASE_TS + bar_index * INTERVAL_4H,
        "direction": "LONG",
        "entry_price": ep,
        "tp_price": ep + 500,
        "sl_price": ep - 500,
        "result": result,
        "bars_to_exit": 3,
    }


def _sample_trades_31() -> list[dict]:
    """31 trades: 21 wins + 10 losses → 67.7% WR → quality_gate pass."""
    trades = []
    for i in range(31):
        result = "win" if i < 21 else "loss"
        trades.append(_trade(bar_index=i + 5, result=result))
    return trades


# ──────────────────────────────────────────────────────────────────────────────
# AC #6 + AC #1 + AC #2 — 31 trades, pass + template format + slice-first
# ──────────────────────────────────────────────────────────────────────────────

def test_preview_pass_quality_gate(tmp_path: Path, monkeypatch):
    """AC #1 + #6: 31 valid trades → 200, quality_gate=pass, correct shape."""
    _make_parquet(tmp_path)
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    resp = client.post(
        "/api/sessions/BTCUSDT_4h_20260420.parquet/preview",
        json={"trades": _sample_trades_31()},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    data = body["data"]
    assert data["quality_gate"] == "pass"
    assert data["quality_gate_reason"] is None
    assert data["trade_count"] == 31
    assert data["win_rate"] == pytest.approx(21 / 31, abs=0.001)
    assert data["symbol"] == "BTCUSDT"
    assert data["timeframe"] == "4h"
    assert data["date"] == "2026-04-20"
    assert len(data["trades"]) == 31


def test_preview_reasoning_template_format(tmp_path: Path, monkeypatch):
    """AC #2 (partial): Template phải khớp format '4H | Entry $... | EMA20=... | Outcome: WIN'."""
    _make_parquet(tmp_path)
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    resp = client.post(
        "/api/sessions/BTCUSDT_4h_20260420.parquet/preview",
        json={"trades": _sample_trades_31()},
    )
    first_template = resp.json()["data"]["trades"][0]["reasoning_template"]
    assert "4H | Entry $" in first_template
    assert "EMA20=$" in first_template
    assert "EMA50=$" in first_template
    assert "Vol=" in first_template
    assert "Outcome: WIN" in first_template


# ──────────────────────────────────────────────────────────────────────────────
# AC #2 — Slice-first enforcement (Gap-1)
# ──────────────────────────────────────────────────────────────────────────────

def test_preview_slice_first_enforcement(tmp_path: Path, monkeypatch):
    """
    AC #2 CRITICAL: EMA20 tại bar_index=42 phải dùng df.iloc[:42], không phải full df.

    Fixture uses a price series that drops sharply after bar 42 so that:
      - slice[:42] EMA (correct) ≠ full-df .iloc[-1] EMA (wrong)
    The negative assertion confirms the full-df value is absent from the template.
    """
    n = 60
    # Prices rise to bar 42, then plummet — makes full-df EMA diverge from slice EMA
    close_prices = [40050.0 + i * 100 for i in range(42)] + [10000.0] * (n - 42)
    data = {
        "timestamp": [BASE_TS + i * INTERVAL_4H for i in range(n)],
        "open":  close_prices,
        "high":  close_prices,
        "low":   close_prices,
        "close": close_prices,
        "volume": [1000.0] * n,
    }
    df = pd.DataFrame(data)
    path = tmp_path / "BTCUSDT_4h_20260420.parquet"
    df.to_parquet(path, index=False)
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    sliced = df.iloc[:42]
    expected_ema20 = sliced["close"].ewm(span=20, adjust=False).mean().iloc[-1]
    expected_str = f"${expected_ema20:,.0f}"

    # Full-df .iloc[-1] EMA — much lower due to the price drop after bar 42
    wrong_ema20 = df["close"].ewm(span=20, adjust=False).mean().iloc[-1]
    wrong_str = f"${wrong_ema20:,.0f}"

    # The two values must differ for this test to be meaningful
    assert expected_str != wrong_str, (
        "Fixture did not produce diverging EMA values — test would be vacuous"
    )

    trade = _trade(bar_index=42, result="win", entry_price=df.iloc[41]["close"])
    resp = client.post(
        "/api/sessions/BTCUSDT_4h_20260420.parquet/preview",
        json={"trades": [trade]},
    )
    assert resp.status_code == 200
    template = resp.json()["data"]["trades"][0]["reasoning_template"]
    assert expected_str in template, (
        f"Expected slice EMA20 {expected_str} in template: {template}"
    )
    assert wrong_str not in template, (
        f"Template must NOT contain full-df EMA20 {wrong_str}: {template}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# AC #3 — File not found → 404
# ──────────────────────────────────────────────────────────────────────────────

def test_preview_file_not_found(tmp_path: Path, monkeypatch):
    """AC #3: File không tồn tại → 404 + error message."""
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    resp = client.post(
        "/api/sessions/NONEXISTENT_4h_20260420.parquet/preview",
        json={"trades": []},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["data"] is None
    assert "không tồn tại" in body["error"]["message"]
    assert body["error"]["code"] == "SESSION_NOT_FOUND"
    assert body["error"]["retryable"] is False


# ──────────────────────────────────────────────────────────────────────────────
# AC #4 — 7 trades, 71% WR → fail (trade count)
# ──────────────────────────────────────────────────────────────────────────────

def test_preview_quality_gate_fail_trade_count(tmp_path: Path, monkeypatch):
    """AC #4: 7 trades, 71% WR → quality_gate fail vì trade_count < 10."""
    _make_parquet(tmp_path)
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    trades = [_trade(bar_index=10 + i, result="win" if i < 5 else "loss") for i in range(7)]
    # 5/7 = 71.4% ≥ 55% — chỉ fail vì trade count
    resp = client.post(
        "/api/sessions/BTCUSDT_4h_20260420.parquet/preview",
        json={"trades": trades},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["quality_gate"] == "fail"
    assert "7 trades" in data["quality_gate_reason"]
    assert "10" in data["quality_gate_reason"]
    # Win rate check không nên xuất hiện trong reason
    assert "win rate" not in data["quality_gate_reason"].lower()


# ──────────────────────────────────────────────────────────────────────────────
# AC #5 — 15 trades, 48% WR → fail (win rate)
# ──────────────────────────────────────────────────────────────────────────────

def test_preview_quality_gate_fail_win_rate(tmp_path: Path, monkeypatch):
    """AC #5: 25 trades, 48% WR (12/25) → quality_gate fail vì win_rate < 55%."""
    _make_parquet(tmp_path)
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    # 12/25 = 48.0% exactly < 55% — trade count passes (25 >= 10)
    trades = [_trade(bar_index=5 + i, result="win" if i < 12 else "loss") for i in range(25)]
    resp = client.post(
        "/api/sessions/BTCUSDT_4h_20260420.parquet/preview",
        json={"trades": trades},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["quality_gate"] == "fail"
    reason = data["quality_gate_reason"]
    assert "48%" in reason
    assert "55" in reason
    # Trade count is sufficient (25 >= 10) — must not appear in reason
    assert "trades" not in reason


# ──────────────────────────────────────────────────────────────────────────────
# Bonus — cả hai fail cùng lúc
# ──────────────────────────────────────────────────────────────────────────────

def test_preview_quality_gate_fail_both(tmp_path: Path, monkeypatch):
    """7 trades + 48% WR → fail, reason phải nói cả hai."""
    _make_parquet(tmp_path)
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    # 3/7 = 42.9% < 55% AND 7 < 10
    trades = [_trade(bar_index=10 + i, result="win" if i < 3 else "loss") for i in range(7)]
    resp = client.post(
        "/api/sessions/BTCUSDT_4h_20260420.parquet/preview",
        json={"trades": trades},
    )
    data = resp.json()["data"]
    assert data["quality_gate"] == "fail"
    reason = data["quality_gate_reason"]
    assert "7 trades" in reason
    assert "%" in reason  # win rate reason


# ──────────────────────────────────────────────────────────────────────────────
# AC #7 — Empty trades → fail (0 trades)
# ──────────────────────────────────────────────────────────────────────────────

def test_preview_empty_trades(tmp_path: Path, monkeypatch):
    """AC #7: Empty trades [] → trade_count=0, quality_gate fail."""
    _make_parquet(tmp_path)
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    resp = client.post(
        "/api/sessions/BTCUSDT_4h_20260420.parquet/preview",
        json={"trades": []},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["trade_count"] == 0
    assert data["win_rate"] == 0.0
    assert data["quality_gate"] == "fail"
    assert data["quality_gate_reason"] == "0 trades — cần tối thiểu 10"
    assert "win rate" not in data["quality_gate_reason"]
    assert len(data["trades"]) == 0


# ──────────────────────────────────────────────────────────────────────────────
# P7 — Quality gate exact boundary: 10 trades + 11/20 WR = 55% → must pass
# ──────────────────────────────────────────────────────────────────────────────

def test_quality_gate_exact_boundary(tmp_path: Path, monkeypatch):
    """10 trades (== minimum) + 11/20 WR == 55% exactly → quality_gate pass."""
    _make_parquet(tmp_path)
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    # Need exactly 20 trades with 11 wins: 11/20 = 0.55 exactly
    trades = [_trade(bar_index=5 + i, result="win" if i < 11 else "loss") for i in range(20)]
    resp = client.post(
        "/api/sessions/BTCUSDT_4h_20260420.parquet/preview",
        json={"trades": trades},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["quality_gate"] == "pass"
    assert data["quality_gate_reason"] is None


# ──────────────────────────────────────────────────────────────────────────────
# P8 — bar_index=1 minimum boundary — no crash, valid template
# ──────────────────────────────────────────────────────────────────────────────

def test_preview_bar_index_minimum(tmp_path: Path, monkeypatch):
    """bar_index=1 → sliced_df has 1 row → no crash, valid template returned."""
    _make_parquet(tmp_path)
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    # 20 trades with bar_index starting at 1, 11 wins → quality gate passes
    trades = [_trade(bar_index=i + 1, result="win" if i < 11 else "loss") for i in range(20)]
    resp = client.post(
        "/api/sessions/BTCUSDT_4h_20260420.parquet/preview",
        json={"trades": trades},
    )
    assert resp.status_code == 200
    template = resp.json()["data"]["trades"][0]["reasoning_template"]
    assert "4H | Entry $" in template
    assert "EMA20=$" in template


def test_preview_bar_index_zero_rejected(tmp_path: Path, monkeypatch):
    """bar_index=0 → Pydantic ge=1 constraint → 422 validation error."""
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    trade = _trade(bar_index=1, result="win")
    trade["bar_index"] = 0
    resp = client.post(
        "/api/sessions/BTCUSDT_4h_20260420.parquet/preview",
        json={"trades": [trade]},
    )
    assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────────────────────
# P9 — Path traversal + malformed filename
# ──────────────────────────────────────────────────────────────────────────────

def test_preview_path_traversal_blocked(tmp_path: Path, monkeypatch):
    """Path traversal attempt must return 400, not 200."""
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    resp = client.post(
        "/api/sessions/..%2F..%2Fetc%2Fpasswd/preview",
        json={"trades": []},
    )
    assert resp.status_code in (400, 404)


def test_preview_malformed_filename_returns_422(tmp_path: Path, monkeypatch):
    """Filename not matching pattern → build_preview raises ValueError → 422.
    We must CREATE a file with that name so the exists() check passes and
    the pattern validation in build_preview is actually reached.
    """
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    # Create a real file with the malformed name so exists() passes
    bad_path = tmp_path / "bad.parquet"
    bad_path.write_bytes(b"not real parquet")
    resp = client.post("/api/sessions/bad.parquet/preview", json={"trades": []})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_FILENAME"


# ──────────────────────────────────────────────────────────────────────────────
# Backward compat — GET /api/sessions vẫn work sau khi thêm preview endpoint
# ──────────────────────────────────────────────────────────────────────────────

def test_list_sessions_still_works(tmp_path: Path, monkeypatch):
    """Backward compat: GET /api/sessions vẫn trả về đúng sau khi thêm preview endpoint."""
    _make_parquet(tmp_path)
    monkeypatch.setattr(settings, "cache_dir", tmp_path)

    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert len(body["data"]) == 1
    assert body["data"][0]["filename"] == "BTCUSDT_4h_20260420.parquet"
