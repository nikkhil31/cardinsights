"""Cashback estimation + actual-cashback detection.

Rates come from cashback.yaml (env CARDWISE_CASHBACK overrides path).
A debit's rate depends on whether the spend is online or offline (detected
from the SBI description via online_keywords). Effective rate:
    cards[last4][channel] if present else categories[category][channel] else default[channel]
cashback amount = amount * rate / 100.
"""
from __future__ import annotations

import os
import re

import yaml

_DEFAULT_YAML = os.path.join(os.path.dirname(__file__), "..", "..", "cashback.yaml")
_CASHBACK_PATH = os.environ.get("CARDWISE_CASHBACK", _DEFAULT_YAML)

_RATES: dict | None = None


def _norm_channel_rates(val, fallback_online=0.0, fallback_offline=0.0):
    """Accept either {online, offline} or a scalar (used for both)."""
    if isinstance(val, dict):
        return {
            "online": float(val.get("online", fallback_online) or 0.0),
            "offline": float(val.get("offline", fallback_offline) or 0.0),
        }
    if val is None:
        return {"online": float(fallback_online), "offline": float(fallback_offline)}
    v = float(val)
    return {"online": v, "offline": v}


def _load() -> dict:
    global _RATES
    if _RATES is not None:
        return _RATES
    try:
        with open(_CASHBACK_PATH) as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}
    default_raw = data.get("default", {})
    default = _norm_channel_rates(default_raw, 0.0, 0.0)
    cats_raw = data.get("categories") or {}
    categories = {}
    for k, v in cats_raw.items():
        categories[str(k)] = _norm_channel_rates(v, default["online"], default["offline"])
    cards_raw = data.get("cards") or {}
    cards = {}
    for k, v in cards_raw.items():
        cards[str(k)] = _norm_channel_rates(v, default["online"], default["offline"])
    _RATES = {
        "default": default,
        "categories": categories,
        "cards": cards,
        "online_keywords": [str(x).lower() for x in (data.get("online_keywords") or [])],
    }
    return _RATES


def reload_rates() -> None:
    global _RATES
    _RATES = None
    _load()


def is_online(description: str) -> bool:
    r = _load()
    low = (description or "").lower()
    return any(kw in low for kw in r["online_keywords"])


def channel_for(description: str, txn_type: str) -> str:
    if txn_type != "debit":
        return "credit"
    return "online" if is_online(description) else "offline"


def rate_for(category: str, card_last4: str | None = None, online: bool | None = None) -> float:
    r = _load()
    ch = "online" if (online if online is not None else False) else "offline"
    # card override
    if card_last4 and card_last4 in r["cards"]:
        return r["cards"][card_last4].get(ch, r["default"].get(ch, 0.0))
    cat_rates = r["categories"].get(category)
    if cat_rates:
        return cat_rates.get(ch, r["default"].get(ch, 0.0))
    return r["default"].get(ch, 0.0)


_CASHBACK_RX = re.compile(r"cash\s*back", re.IGNORECASE)


def is_cashback_credit(description: str) -> bool:
    return bool(_CASHBACK_RX.search(description or ""))


def compute_cashback(description: str, category: str, card_last4: str | None,
                     amount: float, txn_type: str) -> float:
    if txn_type == "credit":
        if is_cashback_credit(description):
            return float(amount or 0.0)
        return 0.0
    online = is_online(description)
    rate = rate_for(category, card_last4, online)
    return round(float(amount or 0.0) * rate / 100.0, 2)
