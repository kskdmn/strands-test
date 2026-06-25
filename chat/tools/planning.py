import json
from datetime import date, timedelta

from django.db.models import Sum
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


def _month_end(month_start: date) -> date:
    if month_start.month == 12:
        return date(month_start.year + 1, 1, 1) - timedelta(days=1)
    return date(month_start.year, month_start.month + 1, 1) - timedelta(days=1)


def _latest_inventory_quantity(product: Product) -> int:
    record = (
        InventoryMonthlyData.objects.filter(product=product, month__lt=current_month_start())
        .order_by("-month")
        .first()
    )
    if record is not None and record.actual_quantity is not None:
        return record.actual_quantity
    return 0


def _incoming_production(product_id: int, through: date) -> int:
    return (
        ProductionMonthlyData.objects.filter(
            product_id=product_id,
            month__gte=current_month_start(),
            month__lte=date(through.year, through.month, 1),
        ).aggregate(total=Sum("plan_quantity"))["total"]
        or 0
    )


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


@tool
def suggest_production_plan(
    product_name: str | None = None,
    months: int = 1,
    start_month: str | None = None,
) -> str:
    """Suggest production changes based on saved sales forecasts and current supply.

    Compares forecast demand against available inventory and incoming production,
    then recommends additional or reduced production where needed.

    Args:
        product_name: Optional product name filter. Returns all products when omitted.
        months: Number of upcoming forecast months to plan for, up to 6.
        start_month: Optional first forecast month to include in YYYY-MM format.

    Returns:
        JSON string with supply gaps and recommended production actions.
    """
    months = max(1, min(months, 6))
    first_month = current_month_start()
    if start_month:
        try:
            first_month = _parse_month(start_month)
        except (ValueError, AttributeError):
            return json.dumps({"error": "start_month must be in YYYY-MM format."})

    forecasts = (
        SalesMonthlyData.objects.select_related("product")
        .filter(month__gte=first_month, plan_units__isnull=False)
        .order_by("product__name", "month")
    )
    if product_name:
        forecasts = forecasts.filter(product__name__icontains=product_name.strip())

    if not forecasts.exists():
        return json.dumps(
            {
                "recommendations": [],
                "message": (
                    "No sales forecasts found for the requested period. "
                    "Use update_sales_forecast first."
                ),
            }
        )

    grouped: dict[str, list[SalesMonthlyData]] = {}
    for forecast in forecasts:
        product_forecasts = grouped.setdefault(forecast.product.name, [])
        if len(product_forecasts) >= months:
            continue
        product_forecasts.append(forecast)

    recommendations = []
    for name, product_forecasts in grouped.items():
        product = product_forecasts[0].product
        on_hand = _latest_inventory_quantity(product)
        available = max(on_hand - product.reserved_quantity, 0)

        forecast_demand = sum(forecast.plan_units or 0 for forecast in product_forecasts)
        last_month = product_forecasts[-1].month
        incoming = _incoming_production(product.id, _month_end(last_month))
        projected_supply = available + incoming
        gap = forecast_demand - projected_supply

        if gap > 0:
            action = "increase_production"
            detail = f"Schedule {gap} additional units to cover forecast demand."
        elif gap < 0:
            action = "reduce_or_delay_production"
            detail = (
                f"Supply exceeds forecast by {abs(gap)} units. "
                "Consider delaying or reducing planned production."
            )
        else:
            action = "maintain_current_plan"
            detail = "Current inventory and incoming production match forecast demand."

        line = _pick_production_line()
        recommendations.append(
            {
                "product": name,
                "sku": product.sku,
                "forecast_months": [forecast.month.isoformat() for forecast in product_forecasts],
                "forecast_demand": forecast_demand,
                "available_inventory": available,
                "incoming_production": incoming,
                "projected_supply": projected_supply,
                "supply_gap": gap,
                "recommended_action": action,
                "recommendation": detail,
                "suggested_line": line.name if line and gap > 0 else None,
            }
        )

    return json.dumps({"recommendations": recommendations}, indent=2)
