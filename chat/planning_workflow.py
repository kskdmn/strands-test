import json
import re
from datetime import date

from chat.flow_log import log_direct_tool
from chat.models import Product
from chat.tools.planning import suggest_production_plan, update_sales_forecast

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

FORECAST_UNITS = re.compile(r"\b(\d[\d,]*)\s+units?\b", re.IGNORECASE)
YEAR_MONTH = re.compile(r"\b(20\d{2})-(0[1-9]|1[0-2])\b")


def _parse_requested_month(content: str) -> tuple[str, str] | None:
    match = YEAR_MONTH.search(content)
    if match:
        month_start = date(int(match.group(1)), int(match.group(2)), 1)
        return month_start.strftime("%Y-%m"), month_start.strftime("%B %Y")

    for month_name, month_number in MONTHS.items():
        match = re.search(rf"\b{month_name}\s+(20\d{{2}})\b", content, re.IGNORECASE)
        if match:
            month_start = date(int(match.group(1)), month_number, 1)
            return month_start.strftime("%Y-%m"), month_start.strftime("%B %Y")
    return None


def _find_product(content: str) -> Product | None:
    content_lower = content.lower()
    matching_products = [
        product for product in Product.objects.all() if product.name.lower() in content_lower
    ]
    return max(matching_products, key=lambda item: len(item.name), default=None)


def _requests_forecast_update(content: str) -> bool:
    lowered = content.lower()
    return "forecast" in lowered and any(keyword in lowered for keyword in ("update", "change", "set"))


def _requests_production_plan(content: str) -> bool:
    lowered = content.lower()
    return "production plan" in lowered or (
        "production" in lowered and "plan" in lowered
    )


def _format_production_plan(recommendation: dict) -> str:
    gap = recommendation["supply_gap"]
    if gap > 0:
        line = recommendation.get("suggested_line")
        if line:
            return f"Production plan: schedule {gap} additional units on {line}."
        return f"Production plan: schedule {gap} additional units."
    if gap < 0:
        return (
            f"Production plan: supply exceeds forecast by {abs(gap)} units; "
            "consider delaying or reducing planned production."
        )
    return "Production plan: current inventory and incoming production match forecast demand."


def run_planning_workflow(query: str) -> str | None:
    """Run planning tools directly when the query contains enough structure."""
    product = _find_product(query)
    if product is None:
        return None

    requested_month = _parse_requested_month(query)
    wants_forecast_update = _requests_forecast_update(query)
    wants_production_plan = _requests_production_plan(query)
    if not wants_forecast_update and not wants_production_plan:
        return None

    lines: list[str] = []

    if wants_forecast_update:
        units_match = FORECAST_UNITS.search(query)
        if units_match is None or requested_month is None:
            return None

        month, month_label = requested_month
        log_direct_tool("update_sales_forecast")
        forecast_payload = json.loads(
            update_sales_forecast(
                product_name=product.name,
                month=month,
                forecast_units=int(units_match.group(1).replace(",", "")),
            )
        )
        if "error" in forecast_payload:
            return f"Forecast update failed: {forecast_payload['error']}"

        forecast = forecast_payload["forecast"]
        lines.append(
            f"Forecast updated: {forecast['product']} for {month_label} "
            f"to {forecast['forecast_units']} units."
        )

    if wants_production_plan:
        plan_kwargs: dict = {
            "product_name": product.name,
            "months": 1,
        }
        if requested_month is not None:
            plan_kwargs["start_month"] = requested_month[0]

        log_direct_tool("suggest_production_plan")
        plan_payload = json.loads(suggest_production_plan(**plan_kwargs))
        if "error" in plan_payload:
            return f"Production plan failed: {plan_payload['error']}"

        recommendations = plan_payload.get("recommendations", [])
        if recommendations:
            lines.append(_format_production_plan(recommendations[0]))
        else:
            message = plan_payload.get("message", "No production recommendation available.")
            lines.append(f"Production plan: {message}")

    if not lines:
        return None

    return "\n".join(lines)
