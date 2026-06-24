import re
from datetime import datetime

from chat.flow_log import log_direct_tool, log_tool_fallback
from chat.tools.catalog import fetch_product_catalog, format_product_catalog
from chat.tools.time import current_time

TOOL_CODE_BLOCK = re.compile(
    r"```(?:tool_code|python)\s*\n\s*(\w+)\(([^)]*)\)\s*\n\s*```",
    re.IGNORECASE | re.DOTALL,
)


def format_local_time(iso_timestamp: str) -> str:
    moment = datetime.fromisoformat(iso_timestamp)
    timezone_label = moment.tzname() or "local time"
    return f"The current local time is {moment.strftime('%Y-%m-%d %H:%M:%S')} ({timezone_label})."


def resolve_leaked_tool_response(text: str) -> str:
    """Run a tool locally when the model prints a tool call as plain text."""
    match = TOOL_CODE_BLOCK.search(text.strip())
    if not match:
        return text

    tool_name = match.group(1)
    if tool_name == "current_time":
        log_tool_fallback(tool_name)
        log_direct_tool(tool_name)
        return format_local_time(current_time(timezone=None))
    if tool_name == "list_available_products":
        log_tool_fallback(tool_name)
        log_direct_tool(tool_name)
        return format_product_catalog(fetch_product_catalog())

    return text
