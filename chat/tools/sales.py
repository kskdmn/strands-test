import json

from strands import tool

from chat.models import SalesMonthlyData
from chat.monthly_data import current_month_start, is_past_month


@tool
def fetch_past_sales_data(product_name: str | None = None, months: int = 12) -> str:
    """Fetch past sales data from the database.

    Args:
        product_name: Optional product name filter. Returns all products when omitted.
        months: Number of recent months to include, up to 24.

    Returns:
        JSON string of historical sales records.
    """
    months = max(1, min(months, 24))
    records = (
        SalesMonthlyData.objects.select_related("product")
        .filter(month__lt=current_month_start())
        .order_by("-month")
    )
    if product_name:
        records = records.filter(product__name__icontains=product_name.strip())

    grouped: dict[str, list[dict]] = {}
    for record in records:
        if record.actual_units is None:
            continue
        product_records = grouped.setdefault(record.product.name, [])
        if len(product_records) >= months:
            continue
        product_records.append(
            {
                "month": record.month.isoformat(),
                "data_kind": "actual",
                "units_sold": record.actual_units,
                "revenue": float(record.actual_revenue) if record.actual_revenue is not None else None,
                "sku": record.product.sku,
            }
        )

    if not grouped:
        return json.dumps(
            {
                "records": [],
                "message": "No sales data found for the requested product.",
            }
        )

    return json.dumps({"records": grouped}, indent=2)


@tool
def fetch_sales_monthly_data(product_name: str | None = None, months: int = 12) -> str:
    """Fetch monthly sales data including actual and plan values.

    Past months return actual data; current and future months return plan data.

    Args:
        product_name: Optional product name filter. Returns all products when omitted.
        months: Number of recent months to include, up to 30.

    Returns:
        JSON string of monthly sales records with data_kind indicating actual or plan.
    """
    months = max(1, min(months, 30))
    records = SalesMonthlyData.objects.select_related("product").order_by("-month")
    if product_name:
        records = records.filter(product__name__icontains=product_name.strip())

    grouped: dict[str, list[dict]] = {}
    for record in records:
        product_records = grouped.setdefault(record.product.name, [])
        if len(product_records) >= months:
            continue
        data_kind = "actual" if is_past_month(record.month) else "plan"
        units = record.effective_units
        if units is None:
            continue
        row = {
            "month": record.month.isoformat(),
            "data_kind": data_kind,
            "units": units,
            "sku": record.product.sku,
        }
        if data_kind == "actual" and record.actual_revenue is not None:
            row["revenue"] = float(record.actual_revenue)
        if data_kind == "plan" and record.notes:
            row["notes"] = record.notes
        product_records.append(row)

    if not grouped:
        return json.dumps(
            {
                "records": [],
                "message": "No sales data found for the requested product.",
            }
        )

    return json.dumps({"records": grouped}, indent=2)
