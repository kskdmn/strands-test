from datetime import date
from decimal import Decimal

DATA_RANGE_START = date(2025, 3, 1)
DATA_RANGE_END = date(2027, 8, 1)


def current_month_start(reference: date | None = None) -> date:
    today = reference or date.today()
    return date(today.year, today.month, 1)


def is_past_month(month: date, reference: date | None = None) -> bool:
    return month < current_month_start(reference)


def is_plan_month(month: date, reference: date | None = None) -> bool:
    return month >= current_month_start(reference)


def iter_months(start: date = DATA_RANGE_START, end: date = DATA_RANGE_END) -> list[date]:
    months: list[date] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(date(year, month, 1))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def effective_sales_units(actual_units: int | None, plan_units: int | None, month: date) -> int | None:
    if is_past_month(month):
        return actual_units
    return plan_units


def effective_inventory_quantity(
    actual_quantity: int | None,
    plan_quantity: int | None,
    month: date,
) -> int | None:
    if is_past_month(month):
        return actual_quantity
    return plan_quantity


def effective_production_quantity(
    actual_quantity: int | None,
    plan_quantity: int | None,
    month: date,
) -> int | None:
    if is_past_month(month):
        return actual_quantity
    return plan_quantity


def sales_revenue_for_month(
    actual_revenue: Decimal | None,
    actual_units: int | None,
    plan_units: int | None,
    unit_price: Decimal,
    month: date,
) -> Decimal | None:
    if is_past_month(month):
        return actual_revenue
    if plan_units is None:
        return None
    return unit_price * plan_units
