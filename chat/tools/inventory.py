import json

from django.db.models import Sum
from strands import tool

from chat.models import InventoryMonthlyData, ProductionMonthlyData, Product
from chat.monthly_data import current_month_start, is_plan_month


def _stock_status(available: int, reorder_point: int) -> str:
    if available <= 0:
        return "out_of_stock"
    if available <= reorder_point:
        return "low_stock"
    if available > reorder_point * 3:
        return "overstocked"
    return "healthy"


def _latest_inventory_quantity(product: Product) -> int:
    record = (
        InventoryMonthlyData.objects.filter(product=product, month__lt=current_month_start())
        .order_by("-month")
        .first()
    )
    if record is not None and record.actual_quantity is not None:
        return record.actual_quantity
    record = (
        InventoryMonthlyData.objects.filter(product=product)
        .order_by("-month")
        .first()
    )
    if record is not None and record.effective_quantity is not None:
        return record.effective_quantity
    return 0


def _incoming_production(product: Product) -> int:
    return (
        ProductionMonthlyData.objects.filter(
            product=product,
            month__gte=current_month_start(),
        ).aggregate(total=Sum("plan_quantity"))["total"]
        or 0
    )


@tool
def fetch_inventory_status(product_name: str | None = None) -> str:
    """Fetch current inventory levels and stock status from the database.

    Args:
        product_name: Optional product name filter. Returns all products when omitted.

    Returns:
        JSON string describing on-hand stock, reservations, and incoming production.
    """
    products = Product.objects.order_by("name")
    if product_name:
        products = products.filter(name__icontains=product_name.strip())

    rows = []
    for product in products:
        on_hand = _latest_inventory_quantity(product)
        available = max(on_hand - product.reserved_quantity, 0)
        incoming = _incoming_production(product)
        rows.append(
            {
                "product": product.name,
                "sku": product.sku,
                "warehouse": product.warehouse,
                "quantity_on_hand": on_hand,
                "reserved_quantity": product.reserved_quantity,
                "available_quantity": available,
                "reorder_point": product.reorder_point,
                "incoming_from_production": incoming,
                "projected_available": available + incoming,
                "stock_status": _stock_status(available, product.reorder_point),
            }
        )

    if not rows:
        return json.dumps(
            {
                "inventory": [],
                "message": "No inventory data found for the requested product.",
            }
        )

    return json.dumps({"inventory": rows}, indent=2)


@tool
def fetch_inventory_monthly_data(product_name: str | None = None, months: int = 12) -> str:
    """Fetch monthly inventory data including actual and plan values.

    Past months return actual data; current and future months return plan data.

    Args:
        product_name: Optional product name filter. Returns all products when omitted.
        months: Number of recent months to include, up to 30.

    Returns:
        JSON string of monthly inventory records.
    """
    months = max(1, min(months, 30))
    records = InventoryMonthlyData.objects.select_related("product").order_by("-month")
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
                "message": "No inventory data found for the requested product.",
            }
        )

    return json.dumps({"records": grouped}, indent=2)
