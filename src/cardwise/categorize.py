"""Rule-based merchant categorizer using categories.yaml."""
from __future__ import annotations

import os
import re

import yaml

_DEFAULT_YAML = os.path.join(os.path.dirname(__file__), "..", "..", "categories.yaml")
_CATEGORIES_PATH = os.environ.get("CARDWISE_CATEGORIES", _DEFAULT_YAML)

_RULES: list[tuple[re.Pattern, str]] | None = None


def _load() -> list[tuple[re.Pattern, str]]:
    global _RULES
    if _RULES is not None:
        return _RULES
    with open(_CATEGORIES_PATH) as f:
        data = yaml.safe_load(f) or {}
    rules: list[tuple[re.Pattern, str]] = []
    for category, keywords in data.items():
        for kw in keywords or []:
            rules.append((re.compile(re.escape(kw), re.IGNORECASE), category))
    # longest keywords first so specific beats generic
    rules.sort(key=lambda r: -len(r[0].pattern))
    _RULES = rules
    return rules


def categorize(description: str) -> str:
    for rx, cat in _load():
        if rx.search(description):
            return cat
    return "Other"
