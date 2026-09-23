"""Semantic classification for rows in meal-log nutrition tables."""

from __future__ import annotations

import re


MARKER_PREFIXES = {
    "subtotal": ("subtotal",),
    "day_total": ("day total",),
    "running_total_reported": ("day so far",),
}


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def classify_meal_row(item: str) -> str:
    """Classify food rows and qualified aggregate markers consistently."""
    label = normalize_label(item)
    for kind, prefixes in MARKER_PREFIXES.items():
        if label.startswith(prefixes):
            return kind
    return "item"
