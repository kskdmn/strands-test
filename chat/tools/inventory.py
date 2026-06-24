import json

from django.db.models import Sum
from strands import tool

from chat.models import InventoryRecord, ProductionOrder


def _stock_status(available: int, reorder_point: int) -> str:
    if available <= 0:
        return "out_of_stock"
    if available <= reorder_point:
        return "low_stock"
    if available > reorder_point * 3:
        return "overstocked"
    return "healthy"


@tool
def fetch_inventory_status(product_name: str | None = None) -> str:
    """Fetch current inventory levels and stock status from the database.

    Args:
        product_name: Optional product name filter. Returns all products when omitted.

    Returns:
        JSON string describing on-hand stock, reservations, and incoming production.
    """
    records = InventoryRecord.objects.select_related("product").order_by("product__name")
    if product_name:
        records = records.filter(product__name__icontains=product_name.strip())

    incoming_by_product: dict[int, int] = {}
    incoming_orders = (
        ProductionOrder.objects.filter(
            status__in=[
                ProductionOrder.Status.PLANNED,
                ProductionOrder.Status.IN_PROGRESS,
            ]
        )
        .values("product_id")
        .annotate(total=Sum("quantity"))
    )
    for row in incoming_orders:
        incoming_by_product[row["product_id"]] = row["total"]

    rows = []
    for record in records:
        available = max(record.quantity_on_hand - record.reserved_quantity, 0)
        incoming = incoming_by_product.get(record.product_id, 0)
        rows.append(
            {
                "product": record.product.name,
                "sku": record.product.sku,
                "warehouse": record.warehouse,
                "quantity_on_hand": record.quantity_on_hand,
                "reserved_quantity": record.reserved_quantity,
                "available_quantity": available,
                "reorder_point": record.reorder_point,
                "incoming_from_production": incoming,
                "projected_available": available + incoming,
                "stock_status": _stock_status(available, record.reorder_point),
                "last_updated": record.last_updated.isoformat(),
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
