"""Parser registry: detect() tries each registered bank parser."""
from __future__ import annotations

from . import sbi

PARSERS = [sbi]


def parse_pdf(path: str):
    """Auto-detect bank and parse. Returns ParsedStatement."""
    for mod in PARSERS:
        if mod.detect(path):
            return mod.parse(path)
    raise ValueError(f"No parser recognized {path}")
