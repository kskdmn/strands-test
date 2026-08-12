from collections.abc import AsyncIterator
from typing import Any, cast

from strands import Agent
from strands.agent.agent_result import AgentResult
from strands.multiagent.graph import Graph
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from samples.a2a_graph_stream.server_graph import build_server_graph


def _extract_data_chunks(event: dict[str, Any]) -> list[str]:
    chunks: list[str] = []
    if "data" in event and event["data"]:
        chunks.append(str(event["data"]))
    if event.get("type") == "multiagent_node_stream":
        inner = event.get("event") or {}
        chunks.extend(_extract_data_chunks(inner))
    return chunks


class GraphStreamingAgent(Agent):
    """Agent that streams a server Graph's FunctionNode chunks over A2A."""

    def __init__(self, graph: Graph | None = None, **kwargs: Any) -> None:
        kwargs.setdefault("name", "graph-stream-agent")
        kwargs.setdefault(
            "description",
            "Streams counter then transformer FunctionNode output from a server Graph.",
        )
        kwargs.setdefault("callback_handler", None)
        super().__init__(**kwargs)
        self._graph = graph or build_server_graph()

    async def stream_async(self, prompt: Any = None, **kwargs: Any) -> AsyncIterator[Any]:
        collected: list[str] = []
        async for event in self._graph.stream_async(
            prompt if prompt is not None else "",
            **kwargs,
        ):
            for chunk in _extract_data_chunks(event):
                collected.append(chunk)
                yield {"data": f"{chunk}\n"}

        text = "".join(f"{line}\n" for line in collected) or "Graph completed with no streamed chunks.\n"
        yield {
            "result": AgentResult(
                stop_reason="end_turn",
                message=Message(role="assistant", content=[ContentBlock(text=text)]),
                metrics=EventLoopMetrics(),
                state={},
            )
        }

    async def invoke_async(self, prompt: Any = None, **kwargs: Any) -> AgentResult:
        events = self.stream_async(prompt, **kwargs)
        async for event in events:
            _ = event

        return cast(AgentResult, event["result"])
