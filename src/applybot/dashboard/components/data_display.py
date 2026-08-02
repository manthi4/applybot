"""Data display components for the ApplyBot dashboard (stat cards, tables, badges)."""

from __future__ import annotations

from fasthtml.common import (
    H3,
    Article,
    P,
    Progress,
    Span,
    Table,
    Tbody,
    Td,
    Th,
    Thead,
    Tr,
)
from fasthtml.pico import Card


def stat_card(value: str, label: str) -> Card:
    """A centered stat card for the overview page."""
    return Card(H3(value), P(label), cls="stat-card")


def progress_table(
    title: str, rows: list[tuple[str, int]], max_val: int | None = None
) -> Article | str:
    """A table with label, count, and progress bar for each row."""
    if not rows:
        return ""
    if max_val is None:
        max_val = max((c for _, c in rows), default=1) or 1
    table_rows = [
        Tr(Td(label), Td(str(count)), Td(Progress(value=str(count), max=str(max_val))))
        for label, count in rows
    ]
    return Article(
        H3(title),
        Table(
            Thead(Tr(Th("Stage"), Th("Count"), Th("", style="width:60%"))),
            Tbody(*table_rows),
        ),
    )


def status_badge(status_str: str) -> Span:
    """Render a colored status badge."""
    badge_map = {
        "approved": "badge-approved",
        "new": "badge-new",
        "skipped": "badge-skipped",
        "applied": "badge-applied",
        "interview": "badge-interview",
        "rejected": "badge-rejected",
    }
    key = status_str.lower().replace(" ", "_")
    cls = badge_map.get(key, "badge-default")
    return Span(status_str.replace("_", " ").capitalize(), cls=f"badge {cls}")
