from django.conf import settings
from strands import Agent, tool

from chat.flow_log import FLOW_LOG_HOOKS
from chat.tools.factory import fetch_factory_status
from chat.tools.inventory import fetch_inventory_status
from chat.tools.sales import fetch_past_sales_data


@tool
def sales_forecast_assistant(query: str) -> str:
    """Forecast future sales using historical sales data.

    Args:
        query: A sales forecasting question, optionally naming a product or time horizon.

    Returns:
        A sales forecast based on past sales records.
    """
    agent = Agent(
        model=settings.CHAT_MODEL_ID,
        name="sales_forecast",
        system_prompt=(
            "You are a sales forecasting specialist. "
            "Always call fetch_past_sales_data before answering. "
            "Use the returned historical data to estimate future sales, "
            "explain trends, and note assumptions clearly."
        ),
        tools=[fetch_past_sales_data],
        hooks=[FLOW_LOG_HOOKS],
        callback_handler=None,
    )
    return str(agent(query))


@tool
def production_schedule_assistant(query: str) -> str:
    """Read the current factory schedule and production order status.

    Args:
        query: A question about current factory lines and scheduled production orders.

    Returns:
        An explanation of factory status and expected production timing.
    """
    agent = Agent(
        model=settings.CHAT_MODEL_ID,
        name="production_schedule",
        system_prompt=(
            "You are a factory production specialist. "
            "Always call fetch_factory_status before answering. "
            "Use line status and production orders to explain when a product "
            "will be produced and what is currently running."
        ),
        tools=[fetch_factory_status],
        hooks=[FLOW_LOG_HOOKS],
        callback_handler=None,
    )
    return str(agent(query))


@tool
def inventory_assistant(query: str) -> str:
    """Answer inventory questions such as stock levels, availability, and reorder status.

    Args:
        query: An inventory question, optionally naming a product.

    Returns:
        An explanation of current stock levels and projected availability.
    """
    agent = Agent(
        model=settings.CHAT_MODEL_ID,
        name="inventory",
        system_prompt=(
            "You are an inventory management specialist. "
            "Always call fetch_inventory_status before answering. "
            "Use on-hand quantities, reservations, reorder points, and incoming "
            "production to explain stock health and projected availability."
        ),
        tools=[fetch_inventory_status],
        hooks=[FLOW_LOG_HOOKS],
        callback_handler=None,
    )
    return str(agent(query))
