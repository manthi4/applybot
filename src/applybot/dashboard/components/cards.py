"""Card components for the ApplyBot dashboard (detail cards, action buttons, collapsible text)."""

from __future__ import annotations

from fasthtml.common import (
    Article,
    Button,
    Details,
    Div,
    Group,
    P,
    Pre,
    Small,
    Strong,
    Summary,
)


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
