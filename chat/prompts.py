from chat.tools.catalog import fetch_product_catalog

ORCHESTRATOR_PROMPT_TEMPLATE = """
You are the main assistant for a manufacturing company chat.

## Available products (live from database)
{catalog_section}

## Routing rules
Use tools for all company data requests. Never invent product names or figures.

- User asks what products or items you have, what you can help with, or what data exists
  -> call list_available_products, then summarize the tool result
- User asks about sales forecasts, demand planning, or past sales trends
  -> call sales_forecast_assistant with the user's full question as query
- User asks about factory status, production schedules, or when a product will be produced
  -> call production_schedule_assistant with the user's full question as query
- User asks about inventory, stock levels, availability, reorder status, or warehouse quantities
  -> call inventory_assistant with the user's full question as query
- User asks for the current date or time
  -> call current_time
- General conversation that does not need company data
  -> answer directly

Keep final answers concise and conversational.
""".strip()


def format_catalog_section(products: list[dict]) -> str:
    if not products:
        return "No products are in the database yet."

    lines = []
    for product in products:
        data_types = []
        if product["has_sales_data"]:
            data_types.append("sales history")
        if product["has_production_data"]:
            data_types.append("production schedule")
        if product["has_inventory_data"]:
            data_types.append("inventory levels")
        detail = ", ".join(data_types) if data_types else "no data"
        lines.append(f"- {product['name']} (SKU: {product['sku']}): {detail}")
    return "\n".join(lines)


def build_orchestrator_system_prompt() -> str:
    catalog_section = format_catalog_section(fetch_product_catalog())
    return ORCHESTRATOR_PROMPT_TEMPLATE.format(catalog_section=catalog_section)
