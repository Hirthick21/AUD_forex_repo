"""
Shared risk tracker for multiple alert bots trading the same funded
account (FundingPips #20084818, EUR 8,000, daily loss limit 3%).

Both the GBPUSD bot and this AUDUSD bot should import this module and
point SHARED_RISK_STATE_PATH at the SAME file on the same machine.
Each bot registers its active signal's allocated risk; before sending
a new alert, a bot checks combined exposure across both bots and adds
a warning to the Telegram message if the daily loss budget would be
exceeded.

This does NOT block trades or place orders - both bots remain
"Paper Alert Only". It only adds a visible warning so you can decide
whether to act on both signals or just one.

Required setup on BOTH bot repos:
  - Add this file (risk_tracker.py) to each repo
  - Set SHARED_RISK_STATE_PATH to the same absolute path in both .env
    files (same machine/server)
  - Set BOT_NAME to something distinct per bot, e.g. "GBPUSD_BOT" and
    "AUDUSD_BOT"
"""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

STATE_FILE = os.getenv("SHARED_RISK_STATE_PATH", "shared_risk_state.json")

ACCOUNT_SIZE = float(os.getenv("ACCOUNT_SIZE", "8000"))
DAILY_LOSS_LIMIT_PCT = float(os.getenv("DAILY_LOSS_LIMIT_PCT", "3.0"))
RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "0.5"))
SIGNAL_EXPIRY_SECONDS = float(os.getenv("SIGNAL_EXPIRY_SECONDS", "14400"))  # 4h


def _today():
    return datetime.now(NY_TZ).strftime("%Y-%m-%d")


def _load():
    state = {}

    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
        except Exception:
            state = {}

    if state.get("date") != _today():
        state = {"date": _today(), "signals": {}}

    # Drop expired signals (older than SIGNAL_EXPIRY_SECONDS)
    now = datetime.now(NY_TZ)
    valid = {}

    for key, sig in state.get("signals", {}).items():
        try:
            sig_time = datetime.fromisoformat(sig["time"])
            if (now - sig_time).total_seconds() < SIGNAL_EXPIRY_SECONDS:
                valid[key] = sig
        except Exception:
            continue

    state["signals"] = valid
    return state


def _save(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print("Risk tracker save error:", e)


def risk_per_trade_eur():
    return round(ACCOUNT_SIZE * RISK_PER_TRADE_PCT / 100, 2)


def daily_loss_limit_eur():
    return round(ACCOUNT_SIZE * DAILY_LOSS_LIMIT_PCT / 100, 2)


def combined_exposure(exclude_key=None):
    state = _load()
    total = 0.0

    for key, sig in state["signals"].items():
        if key == exclude_key:
            continue
        total += sig.get("risk_eur", 0)

    return round(total, 2)


def exposure_warning(bot_name, pair, side, this_trade_risk_eur):
    """
    Returns a warning string if this signal's risk, combined with any
    other currently-active signal from either bot, would exceed the
    shared daily loss limit. Returns None if within budget.
    """
    key = f"{bot_name}:{pair}:{side}"
    other_exposure = combined_exposure(exclude_key=key)
    total = round(other_exposure + this_trade_risk_eur, 2)
    limit = daily_loss_limit_eur()

    if total > limit:
        return (
            f"Combined risk across active signals would be EUR {total:.2f}, "
            f"exceeding the EUR {limit:.2f} daily loss limit "
            f"(other active signal risk: EUR {other_exposure:.2f})."
        )

    return None


def register_signal(bot_name, pair, side, risk_eur):
    """Call after sending a signal alert to record its allocated risk."""
    state = _load()
    state["signals"][f"{bot_name}:{pair}:{side}"] = {
        "pair": pair,
        "side": side,
        "risk_eur": risk_eur,
        "time": datetime.now(NY_TZ).isoformat(),
    }
    _save(state)


def clear_signal(bot_name, pair, side):
    """Optional: call if a signal is manually closed/invalidated early."""
    state = _load()
    key = f"{bot_name}:{pair}:{side}"

    if key in state["signals"]:
        del state["signals"][key]
        _save(state)
