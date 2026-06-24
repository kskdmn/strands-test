import json
from datetime import UTC, date, datetime, timedelta

from django.db.models import Sum
from strands import tool

from chat.models import FactoryLine, InventoryRecord, ProductionOrder, Product, SalesForecast


def _parse_month(month: str) -> date:
    year, month_num = month.strip().split("-", 1)
    return date(int(year), int(month_num), 1)


def _month_end(month_start: date) -> date:
    if month_start.month == 12:
        return date(month_start.year + 1, 1, 1) - timedelta(days=1)
    return date(month_start.year, month_start.month + 1, 1) - timedelta(days=1)


def _incoming_production(product_id: int, through: date) -> int:
    through_dt = datetime.combine(through, datetime.max.time(), tzinfo=UTC)
    return (
        ProductionOrder.objects.filter(
            product_id=product_id,
            status__in=[
                ProductionOrder.Status.PLANNED,
                ProductionOrder.Status.IN_PROGRESS,
            ],
            estimated_completion__lte=through_dt,
        ).aggregate(total=Sum("quantity"))["total"]
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
    product_name: str,
    month: str,
    forecast_units: int,
    notes: str = "",
) -> str:
    """Save or update a sales forecast for a product and month.

    Args:
        product_name: Product name to update the forecast for.
        month: Target month in YYYY-MM format.
        forecast_units: Forecasted unit sales for that month.
        notes: Optional context for why the forecast changed.

    Returns:
        JSON string confirming the saved forecast.
    """
    product_name = product_name.strip()
    if forecast_units < 0:
        return json.dumps({"error": "forecast_units must be zero or positive."})

    try:
        month_start = _parse_month(month)
    except (ValueError, AttributeError):
        return json.dumps({"error": "month must be in YYYY-MM format."})

    product = Product.objects.filter(name__iexact=product_name).first()
    if product is None:
        product = Product.objects.filter(name__icontains=product_name).first()
    if product is None:
        return json.dumps({"error": f"No product found matching '{product_name}'."})

    forecast, created = SalesForecast.objects.update_or_create(
        product=product,
        month=month_start,
        defaults={
            "forecast_units": forecast_units,
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
                "forecast_units": forecast.forecast_units,
                "notes": forecast.notes,
                "updated_at": forecast.updated_at.isoformat(),
            },
        },
        indent=2,
    )


@tool
def suggest_production_plan(product_name: str | None = None, months: int = 1) -> str:
    """Suggest production changes based on saved sales forecasts and current supply.

    Compares forecast demand against available inventory and incoming production,
    then recommends additional or reduced production where needed.

    Args:
        product_name: Optional product name filter. Returns all products when omitted.
        months: Number of upcoming forecast months to plan for, up to 6.

    Returns:
        JSON string with supply gaps and recommended production actions.
    """
    months = max(1, min(months, 6))
    today = date.today()

    forecasts = (
        SalesForecast.objects.select_related("product")
        .filter(month__gte=date(today.year, today.month, 1))
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

    grouped: dict[str, list[SalesForecast]] = {}
    for forecast in forecasts:
        product_forecasts = grouped.setdefault(forecast.product.name, [])
        if len(product_forecasts) >= months:
            continue
        product_forecasts.append(forecast)

    recommendations = []
    for name, product_forecasts in grouped.items():
        product = product_forecasts[0].product
        inventory = InventoryRecord.objects.filter(product=product).first()
        available = 0
        if inventory is not None:
            available = max(inventory.quantity_on_hand - inventory.reserved_quantity, 0)

        forecast_demand = sum(forecast.forecast_units for forecast in product_forecasts)
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
