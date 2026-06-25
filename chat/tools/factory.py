import json

from strands import tool

from chat.models import FactoryLine, ProductionMonthlyData
from chat.monthly_data import is_past_month, is_plan_month


@tool
def fetch_factory_status(product_name: str | None = None) -> str:
    """Fetch the current factory status and production schedule.

    Args:
        product_name: Optional product name filter. Returns all products when omitted.

    Returns:
        JSON string describing factory lines and monthly production data.
    """
    lines = [
        {
            "line": line.name,
            "status": line.status,
        }
        for line in FactoryLine.objects.all()
    ]

    records = ProductionMonthlyData.objects.select_related("product").order_by("month")
    if product_name:
        records = records.filter(product__name__icontains=product_name.strip())

    production_rows = []
    for record in records:
        quantity = record.effective_quantity
        if quantity is None:
            continue
        production_rows.append(
            {
                "product": record.product.name,
                "sku": record.product.sku,
                "month": record.month.isoformat(),
                "data_kind": "actual" if is_past_month(record.month) else "plan",
                "quantity": quantity,
            }
        )

    if not lines and not production_rows:
        return json.dumps(
            {
                "lines": [],
                "production": [],
                "message": "No factory data found.",
            }
        )

    return json.dumps(
        {
            "lines": lines,
            "production": production_rows,
        },
        indent=2,
    )


@tool
def fetch_production_monthly_data(product_name: str | None = None, months: int = 12) -> str:
    """Fetch monthly production data including actual and plan values.

    Past months return actual data; current and future months return plan data.

    Args:
        product_name: Optional product name filter. Returns all products when omitted.
        months: Number of recent months to include, up to 30.

    Returns:
        JSON string of monthly production records.
    """
    months = max(1, min(months, 30))
    records = ProductionMonthlyData.objects.select_related("product").order_by("-month")
    if product_name:
        records = records.filter(product__name__icontains=product_name.strip())

    grouped: dict[str, list[dict]] = {}
    for record in records:
        product_records = grouped.setdefault(record.product.name, [])
        if len(product_records) >= months:
            continue
        quantity = record.effective_quantity
        if quantity is None:
            continue
        product_records.append(
            {
                "month": record.month.isoformat(),
                "data_kind": "actual" if not is_plan_month(record.month) else "plan",
                "quantity": quantity,
                "sku": record.product.sku,
            }
        )

    if not grouped:
        return json.dumps(
            {
                "records": [],
                "message": "No production data found for the requested product.",
            }
        )

    return json.dumps({"records": grouped}, indent=2)
