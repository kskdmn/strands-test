import json
from datetime import date

from strands import tool

from chat.models import FactoryLine, InventoryMonthlyData, ProductionMonthlyData, Product, SalesMonthlyData
from chat.monthly_data import current_month_start, is_plan_month


MONTH_ALIASES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _parse_month_number(month: str | int | None) -> int | None:
    if month is None:
        return None
    if isinstance(month, int):
        return month if 1 <= month <= 12 else None

    text = str(month).strip()
    if not text:
        return None

    if text.isdigit():
        number = int(text)
        return number if 1 <= number <= 12 else None

    key = text.lower()
    if key in MONTH_ALIASES:
        return MONTH_ALIASES[key]

    prefix = key[:3]
    if prefix in MONTH_ALIASES:
        return MONTH_ALIASES[prefix]

    return None


def _parse_year_value(year: int | str | None) -> int | None:
    if year is None:
        return None
    if isinstance(year, int):
        return year

    text = str(year).strip()
    if text.isdigit():
        return int(text)
    return None


def _resolve_month_start(year: int | str | None, month: str | int | None) -> date | None:
    month_text = "" if month is None else str(month).strip()

    if year is None and "-" in month_text:
        parts = month_text.split("-", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            year = int(parts[0])
            month = int(parts[1])

    year_number = _parse_year_value(year)
    month_number = _parse_month_number(month)
    if year_number is None or month_number is None:
        return None

    return date(year_number, month_number, 1)


def _parse_month(month: str) -> date:
    month_start = _resolve_month_start(None, month)
    if month_start is None:
        raise ValueError("invalid month")
    return month_start


def _latest_inventory_quantity(product: Product) -> int:
    record = (
        InventoryMonthlyData.objects.filter(product=product, month__lt=current_month_start())
        .order_by("-month")
        .first()
    )
    if record is not None and record.actual_quantity is not None:
        return record.actual_quantity
    return 0


def _pick_production_line() -> FactoryLine | None:
    return (
        FactoryLine.objects.filter(status=FactoryLine.Status.RUNNING)
        .order_by("name")
        .first()
        or FactoryLine.objects.filter(status=FactoryLine.Status.IDLE)
        .order_by("name")
        .first()
    )


@tool
def update_sales_forecast(
    product_name: str = "",
    year: int | str | None = None,
    month: str | int | None = None,
    forecast_units: int = 0,
    product_id: str = "",
    forecast_quantity: int | None = None,
    notes: str = "",
) -> str:
    """Save or update a sales forecast for a product and month.

    Args:
        product_name: Product name to update the forecast for.
        year: Four-digit calendar year (for example 2026).
        month: Month as 1, 01, Jan, or January.
        forecast_units: Forecasted unit sales for that month.
        product_id: Alias for product_name when the model uses product_id.
        forecast_quantity: Alias for forecast_units.
        notes: Optional context for why the forecast changed.

    Returns:
        JSON string confirming the saved forecast.
    """
    resolved_name = (product_name or product_id or "").strip()
    units = forecast_quantity if forecast_quantity is not None else forecast_units
    if units < 0:
        return json.dumps({"error": "forecast_units must be zero or positive."})

    month_start = _resolve_month_start(year, month)
    if month_start is None:
        return json.dumps(
            {
                "error": (
                    "year and month are required; month accepts 1, 01, Jan, or January."
                ),
            }
        )

    if not resolved_name:
        return json.dumps({"error": "product_name is required."})

    if not is_plan_month(month_start):
        return json.dumps({"error": "Forecasts can only be set for the current month and future months."})

    product = Product.objects.filter(name__iexact=resolved_name).first()
    if product is None:
        product = Product.objects.filter(name__icontains=resolved_name).first()
    if product is None:
        return json.dumps({"error": f"No product found matching '{resolved_name}'."})

    forecast, created = SalesMonthlyData.objects.update_or_create(
        product=product,
        month=month_start,
        defaults={
            "plan_units": units,
            "notes": notes.strip(),
        },
    )

    return json.dumps(
        {
            "action": "created" if created else "updated",
            "forecast": {
                "product": product.name,
                "sku": product.sku,
                "month": forecast.month.isoformat(),
                "data_kind": "plan",
                "forecast_units": forecast.plan_units,
                "notes": forecast.notes,
                "updated_at": forecast.updated_at.isoformat(),
            },
        },
        indent=2,
    )


def _sales_units_for_month(product: Product, month: date) -> int | None:
    record = SalesMonthlyData.objects.filter(product=product, month=month).first()
    if record is None:
        return None
    if is_plan_month(month):
        return record.plan_units
    return record.actual_units


def _production_units_for_month(product: Product, month: date) -> int:
    record = ProductionMonthlyData.objects.filter(product=product, month=month).first()
    if record is None:
        return 0
    if is_plan_month(month):
        return record.plan_quantity or 0
    return record.actual_quantity or 0


def _inventory_units_for_month(product: Product, month: date) -> int | None:
    record = InventoryMonthlyData.objects.filter(product=product, month=month).first()
    if record is None:
        return None
    if is_plan_month(month):
        return record.plan_quantity
    return record.actual_quantity


def _next_month(month: date) -> date:
    if month.month == 12:
        return date(month.year + 1, 1, 1)
    return date(month.year, month.month + 1, 1)


def _project_inventory(
    product: Product,
    month: date,
    *,
    starting_inventory: int,
    previous_production: int,
) -> int:
    sales = _sales_units_for_month(product, month) or 0
    return starting_inventory - sales + previous_production


@tool
def suggest_production_plan(
    product_name: str | None = None,
    months: int = 6,
    start_month: str | None = None,
) -> str:
    """Suggest production changes using PSI rules (suggestions only).

    For each month, projects inventory with:
    current month inventory = previous month inventory − current month sales
    + previous month production.

    Recommends production when projected inventory is below three times the next month's sales.

    Args:
        product_name: Optional product name filter. Returns all products when omitted.
        months: Number of months to analyze, up to 12.
        start_month: Optional first month in YYYY-MM format. Defaults to current month.

    Returns:
        JSON string with monthly PSI projections and production suggestions.
    """
    months = max(1, min(months, 12))
    first_month = current_month_start()
    if start_month:
        try:
            first_month = _parse_month(start_month)
        except (ValueError, AttributeError):
            return json.dumps({"error": "start_month must be in YYYY-MM format."})

    products = Product.objects.order_by("name")
    if product_name:
        products = products.filter(name__icontains=product_name.strip())

    if not products.exists():
        return json.dumps(
            {
                "recommendations": [],
                "message": "No products found for the requested filter.",
            }
        )

    recommendations = []
    for product in products:
        month_cursor = first_month
        prev_inventory = _latest_inventory_quantity(product)
        if month_cursor.month == 1:
            prev_month = date(month_cursor.year - 1, 12, 1)
        else:
            prev_month = date(month_cursor.year, month_cursor.month - 1, 1)
        prev_production = _production_units_for_month(product, prev_month)

        monthly_rows = []
        for _ in range(months):
            recorded_inventory = _inventory_units_for_month(product, month_cursor)
            sales = _sales_units_for_month(product, month_cursor)
            next_month = _next_month(month_cursor)
            next_month_sales = _sales_units_for_month(product, next_month)
            projected_inventory = _project_inventory(
                product,
                month_cursor,
                starting_inventory=prev_inventory,
                previous_production=prev_production,
            )
            inventory_value = recorded_inventory if recorded_inventory is not None else projected_inventory
            threshold = 3 * next_month_sales if next_month_sales is not None else None
            shortfall = (threshold - inventory_value) if threshold is not None else None

            if next_month_sales is None:
                action = "no_sales_data"
                detail = (
                    f"No sales data for {next_month.isoformat()}; "
                    "cannot evaluate the 3× next-month sales rule."
                )
            elif inventory_value < threshold:
                action = "increase_production"
                detail = (
                    f"Inventory ({inventory_value}) is below 3× next month's sales ({threshold}). "
                    f"Suggest producing at least {shortfall} additional units."
                )
            else:
                action = "maintain_current_plan"
                detail = (
                    f"Inventory ({inventory_value}) meets the 3× next-month sales threshold ({threshold})."
                )

            line = _pick_production_line()
            monthly_rows.append(
                {
                    "month": month_cursor.isoformat(),
                    "sales": sales,
                    "next_month": next_month.isoformat(),
                    "next_month_sales": next_month_sales,
                    "previous_production": prev_production,
                    "projected_inventory": projected_inventory,
                    "recorded_inventory": recorded_inventory,
                    "inventory_used": inventory_value,
                    "inventory_threshold": threshold,
                    "shortfall": max(shortfall, 0) if shortfall is not None else None,
                    "recommended_action": action,
                    "recommendation": detail,
                    "suggested_line": line.name if line and action == "increase_production" else None,
                }
            )

            prev_production = _production_units_for_month(product, month_cursor)
            prev_inventory = inventory_value
            if month_cursor.month == 12:
                month_cursor = date(month_cursor.year + 1, 1, 1)
            else:
                month_cursor = date(month_cursor.year, month_cursor.month + 1, 1)

        recommendations.append(
            {
                "product": product.name,
                "sku": product.sku,
                "months": monthly_rows,
            }
        )

    return json.dumps({"recommendations": recommendations}, indent=2)
