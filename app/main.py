"""FastAPI web layer for the bento ordering application."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import db
from app.schemas import OrderDraft, QuantitySelection

if TYPE_CHECKING:
    from collections.abc import Mapping

app = FastAPI()

templates = Jinja2Templates(directory="app/templates")


def format_yen(value: int) -> str:
    """Format an integer as Japanese yen."""
    return f"{int(value):,}円"


templates.env.filters["yen"] = format_yen


def _required_int(value: object, *, field_name: str) -> int:
    if value is None:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} is required",
        )

    try:
        return int(str(value))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be an integer",
        ) from exc


def _required_str(value: object, *, field_name: str) -> str:
    if value is None:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} is required",
        )
    return str(value)


def parse_quantities(form: Mapping[str, object]) -> tuple[QuantitySelection, ...]:
    """Extract positive quantity_* fields from a submitted form."""
    quantities = tuple(
        selection
        for key, value in form.items()
        if key.startswith("quantity_")
        for selection in (_try_parse_quantity(key, value),)
        if selection is not None
    )

    if not quantities:
        raise HTTPException(
            status_code=400,
            detail="At least one bento quantity must be greater than zero",
        )

    return quantities


def _try_parse_quantity(
    key: str,
    value: object,
) -> QuantitySelection | None:
    try:
        bento_id = int(key.removeprefix("quantity_"))
        quantity = int(str(value))
    except ValueError:
        return None

    return (
        QuantitySelection(bento_id=bento_id, quantity=quantity)
        if quantity > 0
        else None
    )


def _parse_order_draft(form: Mapping[str, object]) -> OrderDraft:
    return OrderDraft(
        company_id=_required_int(form.get("company_id"), field_name="company_id"),
        order_date=_required_str(form.get("order_date"), field_name="order_date"),
        quantities=parse_quantities(form),
    )


@app.get("/")
def index(request: Request) -> HTMLResponse:
    """Render the order form with the company list and today's menu."""
    context = {
        "companies": db.fetch_companies(),
        "bentos": db.fetch_bentos(),
        "bento_allergens": db.fetch_bento_allergens(),
    }
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/companies")
def company_directory(request: Request) -> HTMLResponse:
    """Render the company directory with contact details and order stats."""
    return templates.TemplateResponse(
        request,
        "companies.html",
        {"companies": db.fetch_company_contacts()},
    )


@app.post("/orders")
async def create_order(request: Request) -> RedirectResponse:
    """Store the submitted order and redirect to its completion page."""
    form = await request.form()
    draft = _parse_order_draft(form)
    order_id = db.insert_order(draft)

    return RedirectResponse(
        url=f"/orders/complete?order_id={order_id}",
        status_code=303,
    )


@app.get("/orders")
def order_history(request: Request) -> HTMLResponse:
    """Render every past order, newest first."""
    return templates.TemplateResponse(
        request,
        "order_history.html",
        {"orders": db.fetch_orders()},
    )


@app.get("/orders/complete")
def order_complete(request: Request, order_id: int) -> HTMLResponse:
    """Render the receipt of a single order."""
    order, items = db.fetch_order(order_id)

    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return templates.TemplateResponse(
        request,
        "order_complete.html",
        {
            "order": order,
            "items": items,
        },
    )
