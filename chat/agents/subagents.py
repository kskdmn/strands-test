from django.conf import settings
from strands import Agent, tool

from chat.flow_log import FLOW_LOG_HOOKS
from chat.tools.factory import fetch_factory_status, fetch_production_monthly_data
from chat.tools.inventory import fetch_inventory_monthly_data, fetch_inventory_status
from chat.tools.planning import suggest_production_plan
from chat.tools.sales import fetch_past_sales_data, fetch_sales_monthly_data

PSI_DOMAIN_RULES = """
## PSI domain rules
- Sales: actual quantity for past months, planned quantity for current and future months.
  Sales are independent of production and inventory.
- Production: suggest ordering or producing when a month's inventory is below
  three times the next month's sales (inventory < 3 × next month's sales).
- Inventory: current month inventory = previous month inventory − current month sales
  + previous month production.

You provide suggestions only. Never claim that data was saved or updated in the database.
""".strip()


@tool
def sales_assistant(query: str) -> str:
    """Analyze sales data and suggest sales plan adjustments.

    Args:
        query: A sales-related question, optionally naming a product, month, or quantity change.

    Returns:
        Sales analysis and suggested plan changes (suggestions only, no database writes).
    """
    agent = Agent(
        model=settings.CHAT_MODEL_ID,
        name="sales",
        system_prompt=(
            "You are a sales planning specialist for PSI (Production-Sales-Inventory) planning. "
            "Always call fetch_sales_monthly_data before answering. "
            "Use fetch_past_sales_data when the user only needs historical trends. "
            "Explain actual vs planned sales clearly. "
            "When the user wants to change a sales plan, describe the suggested new values "
            "but do not write to the database.\n\n"
            f"{PSI_DOMAIN_RULES}"
        ),
        tools=[fetch_sales_monthly_data, fetch_past_sales_data],
        hooks=[FLOW_LOG_HOOKS],
        callback_handler=None,
    )
    return str(agent(query))


@tool
def production_assistant(query: str) -> str:
    """Analyze production schedules and suggest production adjustments.

    Args:
        query: A production-related question, optionally naming a product or schedule change.

    Returns:
        Production analysis and suggested schedule changes (suggestions only, no database writes).
    """
    agent = Agent(
        model=settings.CHAT_MODEL_ID,
        name="production",
        system_prompt=(
            "You are a production planning specialist for PSI planning. "
            "Always call fetch_production_monthly_data and suggest_production_plan before answering. "
            "Use fetch_factory_status when line capacity or factory status matters. "
            "Recommend production changes when inventory falls below three times next month's sales. "
            "Provide concrete unit suggestions but do not write to the database.\n\n"
            f"{PSI_DOMAIN_RULES}"
        ),
        tools=[fetch_production_monthly_data, suggest_production_plan, fetch_factory_status],
        hooks=[FLOW_LOG_HOOKS],
        callback_handler=None,
    )
    return str(agent(query))


@tool
def inventory_assistant(query: str) -> str:
    """Analyze inventory levels and suggest corrections or production impacts.

    Args:
        query: An inventory-related question, optionally naming a product or discrepancy.

    Returns:
        Inventory analysis and suggested adjustments (suggestions only, no database writes).
    """
    agent = Agent(
        model=settings.CHAT_MODEL_ID,
        name="inventory",
        system_prompt=(
            "You are an inventory planning specialist for PSI planning. "
            "Always call fetch_inventory_monthly_data before answering. "
            "Use fetch_inventory_status for current stock snapshots. "
            "Apply the inventory formula: current month inventory = previous month inventory "
            "− current month sales + previous month production. "
            "When counts look wrong, explain the discrepancy and suggest corrected values "
            "or downstream production changes. Do not write to the database.\n\n"
            f"{PSI_DOMAIN_RULES}"
        ),
        tools=[fetch_inventory_monthly_data, fetch_inventory_status],
        hooks=[FLOW_LOG_HOOKS],
        callback_handler=None,
    )
    return str(agent(query))


@tool
def psi_planning(query: str) -> str:
    """Plan or analyze PSI (Production-Sales-Inventory) data changes.

    Call this when the user asks about sales plans, production schedules, inventory levels,
    or how a change in one area affects the others. Covers both read-only PSI questions and
    what-if adjustments (suggestions only — nothing is saved to the database).

    Args:
        query: The user's full PSI question, including any proposed changes.

    Returns:
        Coordinated PSI analysis and suggestions across sales, production, and inventory.
    """
    agent = Agent(
        model=settings.CHAT_MODEL_ID,
        name="psi_planning",
        system_prompt=(
            "You are the PSI planning coordinator for a manufacturing company. "
            "Route work to the right specialist:\n"
            "- sales_assistant for sales actuals, forecasts, and planned sales changes\n"
            "- production_assistant for factory schedules and production recommendations\n"
            "- inventory_assistant for stock levels, inventory formula checks, and discrepancies\n"
            "Call one or more specialists as needed, then synthesize a clear answer. "
            "When the user adjusts a sales plan, explain the knock-on effect on production. "
            "When inventory data looks wrong, suggest corrected inventory and production changes.\n\n"
            f"{PSI_DOMAIN_RULES}"
        ),
        tools=[sales_assistant, production_assistant, inventory_assistant],
        hooks=[FLOW_LOG_HOOKS],
        callback_handler=None,
    )
    return str(agent(query))
