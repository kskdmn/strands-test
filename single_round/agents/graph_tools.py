from django.conf import settings
from strands import Agent, tool
from strands.multiagent import GraphBuilder

from chat.tools.catalog import list_available_products
from chat.tools.factory import fetch_factory_status
from chat.tools.time import current_time
from single_round.agents.graph_runner import run_graph
from single_round.flow_log import FLOW_LOG_HOOKS


def _build_product_catalog_graph() -> GraphBuilder:
    catalog_fetcher = Agent(
        model=settings.CHAT_MODEL_ID,
        name="catalog_fetcher",
        system_prompt=(
            "You fetch product catalog data for the manufacturing company. "
            "Always call list_available_products before answering. "
            "Return structured notes about which products exist and what data is available."
        ),
        tools=[list_available_products],
        hooks=[FLOW_LOG_HOOKS],
        callback_handler=None,
    )
    catalog_summarizer = Agent(
        model=settings.CHAT_MODEL_ID,
        name="catalog_summarizer",
        system_prompt=(
            "You summarize product catalog research for business users. "
            "Use the upstream fetcher's notes to answer the user's question clearly and concisely."
        ),
        hooks=[FLOW_LOG_HOOKS],
        callback_handler=None,
    )

    builder = GraphBuilder()
    builder.add_node(catalog_fetcher, "catalog_fetcher")
    builder.add_node(catalog_summarizer, "catalog_summarizer")
    builder.add_edge("catalog_fetcher", "catalog_summarizer")
    builder.set_entry_point("catalog_fetcher")
    return builder


def _build_factory_operations_graph() -> GraphBuilder:
    factory_fetcher = Agent(
        model=settings.CHAT_MODEL_ID,
        name="factory_fetcher",
        system_prompt=(
            "You gather factory and production data. "
            "Call fetch_factory_status for line and schedule information. "
            "Call current_time when the user needs timing context. "
            "Return structured notes for downstream analysis."
        ),
        tools=[fetch_factory_status, current_time],
        hooks=[FLOW_LOG_HOOKS],
        callback_handler=None,
    )
    factory_advisor = Agent(
        model=settings.CHAT_MODEL_ID,
        name="factory_advisor",
        system_prompt=(
            "You advise on factory operations based on upstream research. "
            "Explain line status, production schedules, and practical next steps clearly."
        ),
        hooks=[FLOW_LOG_HOOKS],
        callback_handler=None,
    )

    builder = GraphBuilder()
    builder.add_node(factory_fetcher, "factory_fetcher")
    builder.add_node(factory_advisor, "factory_advisor")
    builder.add_edge("factory_fetcher", "factory_advisor")
    builder.set_entry_point("factory_fetcher")
    return builder


@tool
def product_catalog_graph(query: str) -> str:
    """Answer questions about available products and catalog capabilities.

    Use this graph tool when the user asks what products exist, what data is
    available, or what the assistant can help with regarding the product catalog.

    Args:
        query: The user's product or catalog question.

    Returns:
        A synthesized answer from a two-node agent graph (fetch, then summarize).
    """
    return run_graph(_build_product_catalog_graph(), query)


@tool
def factory_operations_graph(query: str) -> str:
    """Answer questions about factory lines, production schedules, and timing.

    Use this graph tool when the user asks about factory status, production plans,
    line availability, or operational timing.

    Args:
        query: The user's factory or production question.

    Returns:
        A synthesized answer from a two-node agent graph (fetch, then advise).
    """
    return run_graph(_build_factory_operations_graph(), query)
