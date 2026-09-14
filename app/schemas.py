"""Immutable application data models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Company(BaseModel):
    """A company that places bento orders."""

    model_config = ConfigDict(frozen=True)

    id: int
    name: str


class CompanyContact(BaseModel):
    """A company with its contact details and order statistics."""

    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    order_count: int = Field(ge=0)
    last_order_date: str | None = None
    total_price: int = Field(ge=0)


class Bento(BaseModel):
    """A bento available on the menu."""

    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    price: int = Field(ge=0)


class BentoAllergenInfo(BaseModel):
    """The allergens associated with a single bento."""

    model_config = ConfigDict(frozen=True)

    bento_name: str
    allergens: tuple[str, ...]


class OrderSummary(BaseModel):
    """Header information and total price of a single order."""

    model_config = ConfigDict(frozen=True)

    id: int
    order_date: str
    company_name: str
    total_price: int = Field(ge=0)


class OrderItem(BaseModel):
    """One line item of an order."""

    model_config = ConfigDict(frozen=True)

    name: str
    quantity: int = Field(gt=0)
    price: int = Field(ge=0)
    subtotal: int = Field(ge=0)


class QuantitySelection(BaseModel):
    """A bento and quantity picked on the order screen."""

    model_config = ConfigDict(frozen=True)

    bento_id: int = Field(gt=0)
    quantity: int = Field(gt=0)

    @property
    def as_db_tuple(self) -> tuple[int, int]:
        """Return the tuple layout used by the order_items INSERT."""
        return self.bento_id, self.quantity


class OrderDraft(BaseModel):
    """An order that has not been persisted yet."""

    model_config = ConfigDict(frozen=True)

    company_id: int = Field(gt=0)
    order_date: str
    quantities: tuple[QuantitySelection, ...] = Field(min_length=1)
