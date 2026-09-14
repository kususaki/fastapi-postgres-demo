"""PostgreSQL access and repository operations."""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

import psycopg

from app.schemas import (
    Bento,
    BentoAllergenInfo,
    Company,
    CompanyContact,
    OrderDraft,
    OrderItem,
    OrderSummary,
)

DATABASE_URL = os.getenv("DATABASE_URL", "dbname=demo_db")

_NO_RETURNING_ROW = "INSERT ... RETURNING id returned no row"


def get_connection() -> psycopg.Connection:
    """Create a new database connection."""
    return psycopg.connect(DATABASE_URL)


def _normalize_date(value: object) -> str:
    """Convert a PostgreSQL date/datetime value to the string used by the UI."""
    if isinstance(value, date | datetime):
        return value.isoformat()
    return str(value)


def _company_from_row(row: tuple[Any, ...]) -> Company:
    return Company(id=row[0], name=row[1])


def _company_contact_from_row(row: tuple[Any, ...]) -> CompanyContact:
    return CompanyContact(
        id=row[0],
        name=row[1],
        contact_name=row[2],
        email=row[3],
        phone=row[4],
        order_count=int(row[5]),
        last_order_date=None if row[6] is None else _normalize_date(row[6]),
        total_price=int(row[7]),
    )


def _bento_from_row(row: tuple[Any, ...]) -> Bento:
    return Bento(id=row[0], name=row[1], price=int(row[2]))


def _order_summary_from_row(row: tuple[Any, ...]) -> OrderSummary:
    return OrderSummary(
        id=row[0],
        order_date=_normalize_date(row[1]),
        company_name=row[2],
        total_price=int(row[3]),
    )


def _order_item_from_row(row: tuple[Any, ...]) -> OrderItem:
    return OrderItem(
        name=row[0],
        quantity=int(row[1]),
        price=int(row[2]),
        subtotal=int(row[3]),
    )


_ORDER_SUMMARY_SQL = """
    SELECT
        o.id,
        o.order_date,
        c.name AS company_name,
        COALESCE(SUM(b.price * oi.quantity), 0) AS total_price
    FROM orders o
    JOIN companies c
        ON c.id = o.company_id
    LEFT JOIN order_items oi
        ON oi.order_id = o.id
    LEFT JOIN bento b
        ON b.id = oi.bento_id
"""


def fetch_companies() -> list[Company]:
    """Return companies ordered by name."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name
            FROM companies
            ORDER BY name
            """
        )
        rows = cur.fetchall()

    return [_company_from_row(row) for row in rows]


def fetch_company_contacts() -> list[CompanyContact]:
    """Return companies with their contact details and order statistics."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                c.id,
                c.name,
                c.contact_name,
                c.email,
                c.phone,
                COUNT(DISTINCT o.id) AS order_count,
                MAX(o.order_date) AS last_order_date,
                COALESCE(SUM(b.price * oi.quantity), 0) AS total_price
            FROM companies c
            LEFT JOIN orders o
                ON o.company_id = c.id
            LEFT JOIN order_items oi
                ON oi.order_id = o.id
            LEFT JOIN bento b
                ON b.id = oi.bento_id
            GROUP BY c.id, c.name, c.contact_name, c.email, c.phone
            ORDER BY c.name
            """
        )
        rows = cur.fetchall()

    return [_company_contact_from_row(row) for row in rows]


def fetch_bentos() -> list[Bento]:
    """Return available bentos ordered by id."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, price
            FROM bento
            ORDER BY id
            """
        )
        rows = cur.fetchall()

    return [_bento_from_row(row) for row in rows]


def fetch_bento_allergens() -> list[BentoAllergenInfo]:
    """Return every bento with its associated allergens."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                b.name,
                a.name
            FROM bento b
            LEFT JOIN bento_allergens ba
                ON ba.bento_id = b.id
            LEFT JOIN allergens a
                ON a.id = ba.allergen_id
            ORDER BY b.id, a.name
            """
        )
        rows = cur.fetchall()

    grouped: dict[str, list[str]] = {}
    for bento_name, allergen_name in rows:
        grouped.setdefault(bento_name, [])
        if allergen_name is not None:
            grouped[bento_name].append(allergen_name)

    return [
        BentoAllergenInfo(bento_name=name, allergens=tuple(allergens))
        for name, allergens in grouped.items()
    ]


def fetch_orders() -> list[OrderSummary]:
    """Return order history."""
    sql = f"""
        {_ORDER_SUMMARY_SQL}
        GROUP BY o.id, o.order_date, c.name
        ORDER BY o.order_date DESC, o.id DESC
    """

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    return [_order_summary_from_row(row) for row in rows]


def fetch_order(order_id: int) -> tuple[OrderSummary | None, list[OrderItem]]:
    """Return an order and its line items."""
    summary_sql = f"""
        {_ORDER_SUMMARY_SQL}
        WHERE o.id = %s
        GROUP BY o.id, o.order_date, c.name
    """

    items_sql = """
        SELECT
            b.name,
            oi.quantity,
            b.price,
            b.price * oi.quantity AS subtotal
        FROM order_items oi
        JOIN bento b
            ON b.id = oi.bento_id
        WHERE oi.order_id = %s
        ORDER BY b.id
    """

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(summary_sql, (order_id,))
        order_row = cur.fetchone()

        if order_row is None:
            return None, []

        cur.execute(items_sql, (order_id,))
        item_rows = cur.fetchall()

    return (
        _order_summary_from_row(order_row),
        [_order_item_from_row(row) for row in item_rows],
    )


def insert_order(draft: OrderDraft) -> int:
    """Persist an order and all of its items atomically."""
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO orders (
                company_id,
                order_date,
                created_at
            )
            VALUES (%s, %s, NOW())
            RETURNING id
            """,
            (draft.company_id, draft.order_date),
        )
        order_row = cur.fetchone()
        if order_row is None:
            raise RuntimeError(_NO_RETURNING_ROW)
        order_id = order_row[0]

        cur.executemany(
            """
            INSERT INTO order_items (
                order_id,
                bento_id,
                quantity
            )
            VALUES (%s, %s, %s)
            """,
            [(order_id, *item.as_db_tuple) for item in draft.quantities],
        )

    return int(order_id)
