"""Reusable UI components for the ApplyBot dashboard.

The package is split by category (layout, data_display, forms, cards); this
module re-exports the full public API so pages can keep importing as
``from applybot.dashboard.components import <name>``.
"""

from __future__ import annotations

from applybot.dashboard.components.cards import (
    action_buttons,
    collapsible_text,
    confirmed_card,
    detail_card,
)
from applybot.dashboard.components.data_display import (
    progress_table,
    stat_card,
    status_badge,
)
from applybot.dashboard.components.forms import filter_form
from applybot.dashboard.components.layout import alert, nav, page

__all__ = [
    "action_buttons",
    "alert",
    "collapsible_text",
    "confirmed_card",
    "detail_card",
    "filter_form",
    "nav",
    "page",
    "progress_table",
    "stat_card",
    "status_badge",
]
