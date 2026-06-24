import ast
import re
from collections.abc import Callable
from datetime import datetime

from chat.agents.subagents import (
    inventory_assistant,
    planning_assistant,
    production_schedule_assistant,
    sales_forecast_assistant,
)
from chat.flow_log import log_direct_tool, log_tool_fallback
from chat.tools.catalog import fetch_product_catalog, format_product_catalog
from chat.tools.planning import suggest_production_plan, update_sales_forecast
from chat.tools.time import current_time

TOOL_CODE_BLOCK = re.compile(
    r"```(?:tool_code|python)\s*\n\s*(\w+)\(([^)]*)\)\s*\n\s*```",
    re.IGNORECASE | re.DOTALL,
)

PLANNING_QUERY_KEYWORDS = (
    "forecast",
    "production plan",
    "meet demand",
    "demand",
    "revise production",
    "suggest production",
)

KEYWORD_ARG = re.compile(
    r"(\w+)\s*=\s*"
    r'(?:"([^"]*)"|\'([^\']*)\'|([^,\s)]+))',
)


def format_local_time(iso_timestamp: str) -> str:
    moment = datetime.fromisoformat(iso_timestamp)
    timezone_label = moment.tzname() or "local time"
    return f"The current local time is {moment.strftime('%Y-%m-%d %H:%M:%S')} ({timezone_label})."


def _parse_keyword_args(args_str: str) -> dict:
    args: dict = {}
    for match in KEYWORD_ARG.finditer(args_str):
        key = match.group(1)
        value = match.group(2) or match.group(3) or match.group(4)
        try:
            args[key] = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            args[key] = value
    return args


def _should_redirect_to_planning(query: str) -> bool:
    lowered = query.lower()
    return any(keyword in lowered for keyword in PLANNING_QUERY_KEYWORDS)


def _run_assistant(tool_name: str, tool: Callable[..., str], args: dict) -> str:
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        return ""
    log_tool_fallback(tool_name)
    log_direct_tool(tool_name)
    return tool(query=query)


def resolve_leaked_tool_response(text: str) -> str:
    """Run a tool locally when the model prints a tool call as plain text."""
    match = TOOL_CODE_BLOCK.search(text.strip())
    if not match:
        return text

    tool_name = match.group(1)
    args = _parse_keyword_args(match.group(2))

    if tool_name == "production_schedule_assistant":
        query = args.get("query", "")
        if isinstance(query, str) and _should_redirect_to_planning(query):
            tool_name = "planning_assistant"

    assistant_tools = {
        "sales_forecast_assistant": sales_forecast_assistant,
        "production_schedule_assistant": production_schedule_assistant,
        "inventory_assistant": inventory_assistant,
        "planning_assistant": planning_assistant,
    }
    if tool_name in assistant_tools:
        result = _run_assistant(tool_name, assistant_tools[tool_name], args)
        if result:
            return result

    if tool_name == "current_time":
        log_tool_fallback(tool_name)
        log_direct_tool(tool_name)
        return format_local_time(current_time(timezone=None))

    if tool_name == "list_available_products":
        log_tool_fallback(tool_name)
        log_direct_tool(tool_name)
        return format_product_catalog(fetch_product_catalog())

    if tool_name == "update_sales_forecast":
        log_tool_fallback(tool_name)
        log_direct_tool(tool_name)
        return update_sales_forecast(
            product_name=args.get("product_name", ""),
            month=args.get("month", ""),
            forecast_units=int(args.get("forecast_units", 0)),
            notes=args.get("notes", ""),
        )

    if tool_name == "suggest_production_plan":
        log_tool_fallback(tool_name)
        log_direct_tool(tool_name)
        return suggest_production_plan(
            product_name=args.get("product_name"),
            months=int(args.get("months", 1)),
        )

    return text
