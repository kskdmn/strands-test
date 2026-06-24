import json

from strands import tool

from chat.models import FactoryLine, ProductionOrder


@tool
def fetch_factory_status(product_name: str | None = None) -> str:
    """Fetch the current factory status and production schedule.

    Args:
        product_name: Optional product name filter. Returns all active orders when omitted.

    Returns:
        JSON string describing factory lines and production orders.
    """
    lines = [
        {
            "line": line.name,
            "status": line.status,
        }
        for line in FactoryLine.objects.all()
    ]

    orders = ProductionOrder.objects.select_related("product", "line").order_by("scheduled_start")
    if product_name:
        orders = orders.filter(product__name__icontains=product_name.strip())

    order_rows = [
        {
            "product": order.product.name,
            "sku": order.product.sku,
            "line": order.line.name,
            "status": order.status,
            "quantity": order.quantity,
            "scheduled_start": order.scheduled_start.isoformat(),
            "estimated_completion": order.estimated_completion.isoformat(),
        }
        for order in orders
    ]

    if not lines and not order_rows:
        return json.dumps(
            {
                "lines": [],
                "production_orders": [],
                "message": "No factory data found.",
            }
        )

    return json.dumps(
        {
            "lines": lines,
            "production_orders": order_rows,
        },
        indent=2,
    )
