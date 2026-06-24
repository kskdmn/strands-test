import json

from django.db.models import Exists, OuterRef
from strands import tool

from chat.models import InventoryRecord, Product


def fetch_product_catalog() -> list[dict]:
    inventory_exists = InventoryRecord.objects.filter(product=OuterRef("pk"))
    products = (
        Product.objects.annotate(has_inventory_data=Exists(inventory_exists))
        .prefetch_related("sales_records", "production_orders")
        .order_by("name")
    )
    return [
        {
            "name": product.name,
            "sku": product.sku,
            "has_sales_data": product.sales_records.exists(),
            "has_production_data": product.production_orders.exists(),
            "has_inventory_data": product.has_inventory_data,
        }
        for product in products
    ]


def format_product_catalog(products: list[dict]) -> str:
    if not products:
        return "I don't have any product data available yet."

    lines = ["Here are the products I have information about:", ""]
    for product in products:
        data_types = []
        if product["has_sales_data"]:
            data_types.append("sales history")
        if product["has_production_data"]:
            data_types.append("production schedule")
        if product["has_inventory_data"]:
            data_types.append("inventory levels")
        detail = ", ".join(data_types) if data_types else "no data"
        lines.append(f"- {product['name']} (SKU: {product['sku']}) — {detail}")

    return "\n".join(lines)


@tool
def list_available_products() -> str:
    """List every product in the database and what data is available for each.

    Call this when the user asks what products or items you have information about,
    what you can help with, or what company data exists. Always use this tool for
    catalog or capability questions instead of guessing product names.

    Returns:
        JSON string listing each product, its SKU, and what data is available.
    """
    rows = fetch_product_catalog()
    if not rows:
        return json.dumps(
            {
                "products": [],
                "message": "No product data is available yet.",
            }
        )

    return json.dumps({"products": rows}, indent=2)
