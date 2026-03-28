"""Reusable UI components for the ApplyBot dashboard."""

from __future__ import annotations

from typing import Any

from fasthtml.common import (
    H3,
    A,
    Article,
    Button,
    Card,
    Container,
    Details,
    Div,
    Form,
    Grid,
    Group,
    Input,
    Label,
    Li,
    Main,
    Nav,
    NotStr,
    Option,
    P,
    Pre,
    Progress,
    Select,
    Small,
    Span,
    Strong,
    Summary,
    Table,
    Tbody,
    Td,
    Th,
    Thead,
    Tr,
    Ul,
)

# ---------- Layout ----------


def nav() -> Nav:
    """Top navigation bar with approved-jobs count badge on the Jobs link."""
    approved_count = 0
    try:
        from applybot.models.job import count_jobs_by_status

        approved_count = count_jobs_by_status().get("approved", 0)
    except Exception:
        pass

    jobs_link = (
        A(
            "Jobs",
            Span(str(approved_count), cls="nav-badge"),
            href="/jobs",
        )
        if approved_count > 0
        else A("Jobs", href="/jobs")
    )

    return Nav(
        Ul(Li(Strong(A("ApplyBot", href="/")))),
        Ul(
            Li(A("Overview", href="/")),
            Li(jobs_link),
            Li(A("Applications", href="/apps")),
            Li(A("Profile", href="/profile")),
            Li(
                Form(
                    Button("Logout", type="submit", cls="secondary outline"),
                    method="post",
                    action="/logout",
                    style="margin:0",
                )
            ),
        ),
    )


def page(*content: object, title: str = "ApplyBot") -> tuple[object, ...]:
    """Wrap content in the standard page layout with nav."""
    return (
        nav(),
        Main(Container(*content), cls="container"),
    )


def alert(msg: str, kind: str = "info") -> Article:
    """Render a themed alert. kind: info, success, error."""
    role = {"info": "note", "success": "status", "error": "alert"}.get(kind, "note")
    return Article(P(msg), role=role)


# ---------- Data Display ----------


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


# ---------- Forms ----------


def filter_form(action: str, filters: list[dict[str, Any]]) -> Form:
    """Build a filter form with a grid of controls and a submit button.

    Each filter dict has keys:
        name, label, type ("select" or "number"),
        options (for select): list of (value, display) tuples,
        selected (for select): current value,
        value/min/max (for number).
    """
    fields = []
    for f in filters:
        if f["type"] == "select":
            options = [
                Option(text, value=val, selected=(val == f.get("selected", "")))
                for val, text in f["options"]
            ]
            fields.append(
                Div(
                    Label(f["label"], _for=f["name"]),
                    Select(*options, name=f["name"], id=f["name"]),
                )
            )
        elif f["type"] == "number":
            fields.append(
                Div(
                    Label(f["label"], _for=f["name"]),
                    Input(
                        type="number",
                        name=f["name"],
                        id=f["name"],
                        value=str(f.get("value", 0)),
                        min=str(f.get("min", 0)),
                        max=str(f.get("max", 100)),
                    ),
                )
            )
    fields.append(Div(Label(NotStr("&nbsp;")), Button("Filter", type="submit")))
    return Form(Grid(*fields), method="get", action=action)


# ---------- Cards ----------


def detail_card(
    id_prefix: str, id_val: str, summary_text: str, *content: object
) -> Article:
    """An expandable article card with a details/summary header."""
    return Article(
        Details(Summary(summary_text), *content),
        id=f"{id_prefix}-{id_val}",
    )


def action_buttons(*buttons: tuple[str, str, str, str]) -> Div:
    """Render a group of HTMX action buttons.

    Each tuple: (label, hx_post_url, hx_target, cls).
    cls: "" for primary, "secondary", "contrast".
    """
    btn_elements = []
    for label, url, target, cls in buttons:
        kwargs = {"hx_post": url, "hx_target": target, "hx_swap": "outerHTML"}
        if cls:
            kwargs["cls"] = cls
        btn_elements.append(Button(label, **kwargs))
    return Div(Group(*btn_elements))


def confirmed_card(
    id_prefix: str, id_val: str, title: str, status_text: str
) -> Article:
    """A compact card shown after an action (approve/skip/etc)."""
    return Article(
        P(Strong(title), " -- ", Small(status_text)),
        id=f"{id_prefix}-{id_val}",
    )


def collapsible_text(label: str, text: str) -> Details:
    """A collapsible section with preformatted text."""
    return Details(
        Summary(label),
        Pre(text, style="white-space:pre-wrap;font-size:0.85em;"),
    )
