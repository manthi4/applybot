"""Form components for the ApplyBot dashboard (filter forms)."""

from __future__ import annotations

from typing import Any

from fasthtml.common import (
    Button,
    Div,
    Form,
    Input,
    Label,
    NotStr,
    Option,
    Select,
)
from fasthtml.pico import Grid


def filter_form(
    action: str, filters: list[dict[str, Any]], form_id: str | None = None
) -> Form:
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
    form_kwargs: dict[str, Any] = {"method": "get", "action": action}
    if form_id:
        form_kwargs["id"] = form_id
    return Form(Grid(*fields), **form_kwargs)
