from chat.tools.catalog import fetch_product_catalog

ORCHESTRATOR_PROMPT_TEMPLATE = """
You are the main assistant for a manufacturing company chat.

## Available products (live from database)
{catalog_section}

## Routing rules
Use tools for all company data requests. Never invent product names or figures.
Never print tool calls as code blocks — always invoke tools through the tool interface.

### PSI (Production-Sales-Inventory)
Call psi_planning when the user asks about sales, production, or inventory — including:
- Reading past sales, production schedules, or stock levels
- Changing or what-if adjusting sales plans, production schedules, or inventory
- How a sales plan change affects production
- Correcting inventory discrepancies and what to produce instead

psi_planning returns suggestions only; nothing is saved to the database.

### Other tools
- User asks what products or items you have, what you can help with, or what data exists
  -> call list_available_products, then summarize the tool result
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
        if product.get("has_forecast_data"):
            data_types.append("sales forecast")
        detail = ", ".join(data_types) if data_types else "no data"
        lines.append(f"- {product['name']} (SKU: {product['sku']}): {detail}")
    return "\n".join(lines)


def build_orchestrator_system_prompt() -> str:
    catalog_section = format_catalog_section(fetch_product_catalog())
    return ORCHESTRATOR_PROMPT_TEMPLATE.format(catalog_section=catalog_section)
