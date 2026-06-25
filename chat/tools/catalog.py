import json

from django.db.models import Exists, OuterRef
from strands import tool

from chat.models import InventoryMonthlyData, Product, ProductionMonthlyData, SalesMonthlyData
from chat.monthly_data import current_month_start


def fetch_product_catalog() -> list[dict]:
    sales_exists = SalesMonthlyData.objects.filter(product=OuterRef("pk"))
    inventory_exists = InventoryMonthlyData.objects.filter(product=OuterRef("pk"))
    production_exists = ProductionMonthlyData.objects.filter(product=OuterRef("pk"))
    forecast_exists = SalesMonthlyData.objects.filter(
        product=OuterRef("pk"),
        month__gte=current_month_start(),
        plan_units__isnull=False,
    )
    products = (
        Product.objects.annotate(
            has_sales_data=Exists(sales_exists),
            has_inventory_data=Exists(inventory_exists),
            has_production_data=Exists(production_exists),
            has_forecast_data=Exists(forecast_exists),
        )
        .order_by("name")
    )
    return [
        {
            "name": product.name,
            "sku": product.sku,
            "has_sales_data": product.has_sales_data,
            "has_production_data": product.has_production_data,
            "has_inventory_data": product.has_inventory_data,
            "has_forecast_data": product.has_forecast_data,
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
        if product["has_forecast_data"]:
            data_types.append("sales forecast")
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
