from django.conf import settings
from strands import Agent, tool

from chat.flow_log import FLOW_LOG_HOOKS
from chat.planning_workflow import run_planning_workflow
from chat.tools.factory import fetch_factory_status
from chat.tools.inventory import fetch_inventory_status
from chat.tools.planning import suggest_production_plan, update_sales_forecast
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

    Use for questions about what is running now, existing orders, and completion dates.
    Do NOT use for forecast-driven production planning — use planning_assistant instead.

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


@tool
def planning_assistant(query: str) -> str:
    """Update sales forecasts and suggest a revised production plan to meet demand.

    Use when the user changes forecast numbers or asks what production is needed
    to meet updated demand. Handles both forecast updates and plan recommendations.

    Args:
        query: The user's planning request, including any forecast numbers and products.

    Returns:
        Confirmation of forecast updates and recommended production actions.
    """
    workflow_result = run_planning_workflow(query)
    if workflow_result is not None:
        return workflow_result

    agent = Agent(
        model=settings.CHAT_MODEL_ID,
        name="planning",
        system_prompt=(
            "You are a demand and production planning specialist. "
            "Always call the provided tools. Never write Python code, pseudocode, or simulated classes. "
            "When the user provides new forecast numbers, call update_sales_forecast "
            "for each product and month they mention. "
            "After forecasts are saved, call suggest_production_plan to compare demand "
            "against inventory and incoming production. "
            "Use fetch_inventory_status or fetch_factory_status only when extra detail is needed. "
            "Recommendations are advisory only. Do not create or update production orders. "
            "Summarize the recommended production changes clearly in plain language, including quantities "
            "and which line to use when a gap exists."
        ),
        tools=[update_sales_forecast, suggest_production_plan, fetch_inventory_status, fetch_factory_status],
        hooks=[FLOW_LOG_HOOKS],
        callback_handler=None,
    )
    from chat.tool_fallback import resolve_leaked_tool_response

    return resolve_leaked_tool_response(str(agent(query)))
