import json

from strands import tool

from chat.models import SalesRecord


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
    records = SalesRecord.objects.select_related("product").order_by("-month")
    if product_name:
        records = records.filter(product__name__icontains=product_name.strip())

    grouped: dict[str, list[dict]] = {}
    for record in records:
        product_records = grouped.setdefault(record.product.name, [])
        if len(product_records) >= months:
            continue
        product_records.append(
            {
                "month": record.month.isoformat(),
                "units_sold": record.units_sold,
                "revenue": float(record.revenue),
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
