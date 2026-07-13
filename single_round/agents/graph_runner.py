from strands.agent.agent_result import AgentResult
from strands.multiagent.graph import GraphResult

from single_round.flow_log import FLOW_LOG_HOOKS


def format_graph_result(result: GraphResult) -> str:
    if result.execution_order:
        last_node = result.execution_order[-1]
        node_result = result.results.get(last_node.node_id)
        if node_result is not None:
            agent_results = node_result.get_agent_results()
            if agent_results:
                text = _agent_result_text(agent_results[-1])
                if text:
                    return text
                return str(agent_results[-1])

    chunks: list[str] = []
    for node_result in result.results.values():
        for agent_result in node_result.get_agent_results():
            text = _agent_result_text(agent_result)
            if text:
                chunks.append(text)

    if chunks:
        return "\n\n".join(chunks)

    return f"Graph finished with status={result.status.value}"


def _agent_result_text(result: AgentResult) -> str:
    message = result.message
    if not isinstance(message, dict):
        return str(message).strip()

    parts: list[str] = []
    for block in message.get("content", []):
        if isinstance(block, dict) and "text" in block and block["text"]:
            parts.append(str(block["text"]))
    return "\n\n".join(parts).strip()


def run_graph(builder, query: str) -> str:
    graph = builder.set_hook_providers([FLOW_LOG_HOOKS]).build()
    result = graph(query)
    return format_graph_result(result)
