import asyncio
import time
from collections.abc import AsyncIterator, Callable
from typing import Any

from strands.agent.agent_result import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message
from strands.types.multiagent import MultiAgentInput

DEFAULT_N = 5
DEFAULT_SLEEP_S = 0.3


def _agent_result(text: str) -> AgentResult:
    return AgentResult(
        stop_reason="end_turn",
        message=Message(role="assistant", content=[ContentBlock(text=text)]),
        metrics=EventLoopMetrics(),
        state={},
    )


class FunctionNode(MultiAgentBase):
    """Deterministic graph node that can stream one chunk per loop iteration."""

    def __init__(
        self,
        func: Callable[[MultiAgentInput, int], str],
        name: str,
        *,
        count: int = DEFAULT_N,
        sleep_s: float = DEFAULT_SLEEP_S,
    ) -> None:
        super().__init__()
        self.func = func
        self.name = name
        self.id = name
        self.count = count
        self.sleep_s = sleep_s

    async def invoke_async(
        self,
        task: MultiAgentInput,
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> MultiAgentResult:
        result = None
        async for event in self.stream_async(task, invocation_state, **kwargs):
            if "result" in event:
                result = event["result"]
        if result is None:
            raise RuntimeError(f"FunctionNode '{self.name}' produced no result")
        return result

    async def stream_async(
        self,
        task: MultiAgentInput,
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        started = time.time()
        chunks: list[str] = []
        for index in range(self.count):
            if self.sleep_s > 0:
                await asyncio.sleep(self.sleep_s)
            chunk = self.func(task, index)
            chunks.append(chunk)
            yield {"data": chunk}

        text = "\n".join(chunks)
        agent_result = _agent_result(text)
        node_result = NodeResult(
            result=agent_result,
            execution_time=round((time.time() - started) * 1000),
            status=Status.COMPLETED,
            execution_count=1,
        )
        yield {
            "result": MultiAgentResult(
                status=Status.COMPLETED,
                results={self.name: node_result},
                execution_time=node_result.execution_time,
                execution_count=1,
            )
        }


def make_counter_node(*, count: int = DEFAULT_N, sleep_s: float = DEFAULT_SLEEP_S) -> FunctionNode:
    def _counter(_task: MultiAgentInput, index: int) -> str:
        return f"counter[{index}]"

    return FunctionNode(_counter, "counter", count=count, sleep_s=sleep_s)


def make_transformer_node(*, count: int = DEFAULT_N, sleep_s: float = DEFAULT_SLEEP_S) -> FunctionNode:
    def _transformer(_task: MultiAgentInput, index: int) -> str:
        return f"transformer[{index}]=item-{index}"

    return FunctionNode(_transformer, "transformer", count=count, sleep_s=sleep_s)
