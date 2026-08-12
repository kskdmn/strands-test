# A2A Graph FunctionNode Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a standalone sample under `samples/a2a_graph_stream/` where a client Graph with an `A2AAgent` node streams incremental chunks from a remote `A2AServer` that runs a Graph of two streaming `FunctionNode`s.

**Architecture:** Server-side custom `FunctionNode`s override `stream_async` to yield `{"data": ...}` per loop item. A sequential server Graph (`counter` → `transformer`) is driven by a thin `Agent` subclass adapter that re-emits those chunks for A2A. The client Graph has a single `A2AAgent` entry node and prints streamed text as it arrives.

**Tech Stack:** Python 3.14+, strands-agents (`Agent`, `A2AAgent`, `A2AServer`, `GraphBuilder`, `MultiAgentBase`), asyncio, unittest/pytest-style async tests via `asyncio.run`.

## Global Constraints

- Standalone sample only — no Django / `single_round` changes.
- Use strands-agents already in `pyproject.toml` (no new dependency unless A2A extras are already pulled in transitively).
- Defaults: `N=5`, sleep `0.3` seconds per item, host `127.0.0.1`, port `9000`.
- `A2AServer(..., enable_a2a_compliant_streaming=True)`.
- Adapter must always emit a final `{"result": AgentResult(...)}` so A2A/Graph executors complete.
- Comments in English; one trailing newline per file; no trailing whitespace.
- Spec: `docs/superpowers/specs/2026-08-12-a2a-graph-functionnode-streaming-design.md`.

---

## File Structure

- Create: `samples/__init__.py` — package marker so `python -m samples.a2a_graph_stream.*` works
- Create: `samples/a2a_graph_stream/__init__.py` — empty package marker
- Create: `samples/a2a_graph_stream/nodes.py` — `FunctionNode`, `DEFAULT_N`, `DEFAULT_SLEEP_S`, factory helpers
- Create: `samples/a2a_graph_stream/server_graph.py` — `build_server_graph()`
- Create: `samples/a2a_graph_stream/adapter.py` — `GraphStreamingAgent(Agent)`
- Create: `samples/a2a_graph_stream/server.py` — start `A2AServer`
- Create: `samples/a2a_graph_stream/client.py` — client Graph + print stream
- Create: `samples/a2a_graph_stream/README.md` — two-terminal run instructions
- Create: `samples/a2a_graph_stream/test_nodes.py` — unit test for FunctionNode streaming (no network)

### Task 1: Streaming FunctionNode + unit test

**Files:**
- Create: `samples/__init__.py`
- Create: `samples/a2a_graph_stream/__init__.py`
- Create: `samples/a2a_graph_stream/nodes.py`
- Create: `samples/a2a_graph_stream/test_nodes.py`
- Test: `samples/a2a_graph_stream/test_nodes.py`

**Interfaces:**
- Consumes: strands `MultiAgentBase`, `MultiAgentResult`, `NodeResult`, `Status`, `AgentResult`, `EventLoopMetrics`
- Produces:
  - `DEFAULT_N: int = 5`
  - `DEFAULT_SLEEP_S: float = 0.3`
  - `class FunctionNode(MultiAgentBase)` with `__init__(self, func, name: str, *, count: int = DEFAULT_N, sleep_s: float = DEFAULT_SLEEP_S)`, `async def stream_async(...)`, `async def invoke_async(...)`
  - `def make_counter_node(*, count: int = DEFAULT_N, sleep_s: float = DEFAULT_SLEEP_S) -> FunctionNode`
  - `def make_transformer_node(*, count: int = DEFAULT_N, sleep_s: float = DEFAULT_SLEEP_S) -> FunctionNode`

- [ ] **Step 1: Create package init and failing test**

Create `samples/__init__.py` and `samples/a2a_graph_stream/__init__.py` (each empty with one trailing newline).

Create `samples/a2a_graph_stream/test_nodes.py`:

```python
import asyncio
import unittest

from samples.a2a_graph_stream.nodes import make_counter_node


class FunctionNodeStreamTests(unittest.TestCase):
    def test_counter_streams_n_data_events_then_result(self):
        node = make_counter_node(count=3, sleep_s=0)

        async def collect():
            data_events = []
            result_events = []
            async for event in node.stream_async("stream demo"):
                if "data" in event:
                    data_events.append(event["data"])
                if "result" in event:
                    result_events.append(event["result"])
            return data_events, result_events

        data_events, result_events = asyncio.run(collect())

        self.assertEqual(data_events, ["counter[0]", "counter[1]", "counter[2]"])
        self.assertEqual(len(result_events), 1)
        self.assertEqual(result_events[0].status.value, "completed")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/keisukedaimon/git/strands-test && .venv/bin/python -m unittest samples.a2a_graph_stream.test_nodes -v
```

Expected: FAIL / ERROR — `ModuleNotFoundError` or import error for `nodes`.

- [ ] **Step 3: Implement `nodes.py`**

Create `samples/a2a_graph_stream/nodes.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/keisukedaimon/git/strands-test && .venv/bin/python -m unittest samples.a2a_graph_stream.test_nodes -v
```

Expected: `OK` — `test_counter_streams_n_data_events_then_result` PASS.

- [ ] **Step 5: Commit**

```bash
git add samples/__init__.py samples/a2a_graph_stream/__init__.py samples/a2a_graph_stream/nodes.py samples/a2a_graph_stream/test_nodes.py
git commit -m "$(cat <<'EOF'
Add streaming FunctionNode sample with unit test.

EOF
)"
```

### Task 2: Server Graph builder

**Files:**
- Create: `samples/a2a_graph_stream/server_graph.py`

**Interfaces:**
- Consumes: `make_counter_node`, `make_transformer_node` from `nodes.py`
- Produces: `def build_server_graph(*, count: int = DEFAULT_N, sleep_s: float = DEFAULT_SLEEP_S) -> Graph`

- [ ] **Step 1: Implement `server_graph.py`**

```python
from strands.multiagent import GraphBuilder
from strands.multiagent.graph import Graph

from samples.a2a_graph_stream.nodes import DEFAULT_N, DEFAULT_SLEEP_S, make_counter_node, make_transformer_node


def build_server_graph(*, count: int = DEFAULT_N, sleep_s: float = DEFAULT_SLEEP_S) -> Graph:
    counter = make_counter_node(count=count, sleep_s=sleep_s)
    transformer = make_transformer_node(count=count, sleep_s=sleep_s)

    builder = GraphBuilder()
    builder.add_node(counter, "counter")
    builder.add_node(transformer, "transformer")
    builder.add_edge("counter", "transformer")
    builder.set_entry_point("counter")
    return builder.build()
```

- [ ] **Step 2: Smoke-run server graph streaming locally**

Run:

```bash
cd /Users/keisukedaimon/git/strands-test && .venv/bin/python - <<'PY'
import asyncio
from samples.a2a_graph_stream.server_graph import build_server_graph

async def main():
    graph = build_server_graph(count=2, sleep_s=0)
    data = []
    async for event in graph.stream_async("stream demo"):
        if event.get("type") == "multiagent_node_stream":
            inner = event.get("event") or {}
            if "data" in inner:
                data.append((event.get("node_id"), inner["data"]))
        elif "result" in event or event.get("type") == "multiagent_result":
            print("final", event.get("type") or "result")
    print(data)

asyncio.run(main())
PY
```

Expected: printed pairs include `('counter', 'counter[0]')`, `('counter', 'counter[1]')`, then transformer lines; process exits 0.

- [ ] **Step 3: Commit**

```bash
git add samples/a2a_graph_stream/server_graph.py
git commit -m "$(cat <<'EOF'
Add sequential server graph for FunctionNode streaming sample.

EOF
)"
```

### Task 3: GraphStreamingAgent adapter

**Files:**
- Create: `samples/a2a_graph_stream/adapter.py`

**Interfaces:**
- Consumes: `build_server_graph()` → `Graph`
- Produces: `class GraphStreamingAgent(Agent)` with overridden `async def stream_async(...)` that yields `{"data": str}` then `{"result": AgentResult}`

- [ ] **Step 1: Implement `adapter.py`**

```python
from collections.abc import AsyncIterator
from typing import Any

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
        async for event in self._graph.stream_async(prompt if prompt is not None else ""):
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
```

- [ ] **Step 2: Smoke-run adapter stream (no A2A)**

Run:

```bash
cd /Users/keisukedaimon/git/strands-test && .venv/bin/python - <<'PY'
import asyncio
from samples.a2a_graph_stream.adapter import GraphStreamingAgent
from samples.a2a_graph_stream.server_graph import build_server_graph

async def main():
    agent = GraphStreamingAgent(graph=build_server_graph(count=2, sleep_s=0))
    async for event in agent.stream_async("stream demo"):
        if "data" in event:
            print(event["data"], end="", flush=True)
        elif "result" in event:
            print("DONE", str(event["result"]).strip().splitlines()[-1:])

asyncio.run(main())
PY
```

Expected: prints `counter[0]` … `transformer[1]=item-1` then a DONE line; exit 0.

- [ ] **Step 3: Commit**

```bash
git add samples/a2a_graph_stream/adapter.py
git commit -m "$(cat <<'EOF'
Add GraphStreamingAgent adapter for A2A FunctionNode streaming.

EOF
)"
```

### Task 4: A2AServer entrypoint

**Files:**
- Create: `samples/a2a_graph_stream/server.py`

**Interfaces:**
- Consumes: `GraphStreamingAgent`
- Produces: runnable `python -m samples.a2a_graph_stream.server` serving `http://127.0.0.1:9000`

- [ ] **Step 1: Implement `server.py`**

```python
from strands.multiagent.a2a import A2AServer

from samples.a2a_graph_stream.adapter import GraphStreamingAgent

HOST = "127.0.0.1"
PORT = 9000


def main() -> None:
    agent = GraphStreamingAgent()
    server = A2AServer(
        agent=agent,
        host=HOST,
        port=PORT,
        enable_a2a_compliant_streaming=True,
    )
    print(f"Serving A2A graph stream agent on http://{HOST}:{PORT}/", flush=True)
    server.serve()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Start server briefly to confirm bind**

Run in background (or foreground and Ctrl-C after card fetch):

```bash
cd /Users/keisukedaimon/git/strands-test && .venv/bin/python -m samples.a2a_graph_stream.server
```

In another shell:

```bash
curl -sS http://127.0.0.1:9000/.well-known/agent.json | head -c 400; echo
```

Expected: JSON agent card mentioning `graph-stream-agent` (or similar); server stays up until stopped.

Stop the server process after the check.

- [ ] **Step 3: Commit**

```bash
git add samples/a2a_graph_stream/server.py
git commit -m "$(cat <<'EOF'
Add A2AServer entrypoint for graph FunctionNode streaming sample.

EOF
)"
```

### Task 5: Client Graph with A2AAgent

**Files:**
- Create: `samples/a2a_graph_stream/client.py`

**Interfaces:**
- Consumes: remote A2A endpoint `http://127.0.0.1:9000`
- Produces: runnable client that prints incremental streamed text

- [ ] **Step 1: Implement `client.py`**

```python
import asyncio
import sys

from strands.agent.a2a_agent import A2AAgent
from strands.multiagent import GraphBuilder

ENDPOINT = "http://127.0.0.1:9000"


def _print_stream_event(event: dict) -> None:
    if event.get("type") == "multiagent_node_stream":
        inner = event.get("event") or {}
        _print_stream_event(inner)
        return

    if event.get("type") == "a2a_stream":
        # Protocol envelopes vary; dig for text when present.
        payload = event.get("event")
        text = _coerce_a2a_text(payload)
        if text:
            print(text, end="", flush=True)
        return

    if "data" in event and event["data"]:
        print(str(event["data"]), end="", flush=True)


def _coerce_a2a_text(payload: object) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    # TaskArtifactUpdateEvent / status updates often nest text parts
    root = getattr(payload, "root", payload)
    artifact = getattr(root, "artifact", None) or getattr(payload, "artifact", None)
    if artifact is not None:
        parts = getattr(artifact, "parts", None) or []
        bits: list[str] = []
        for part in parts:
            part_root = getattr(part, "root", part)
            text = getattr(part_root, "text", None)
            if text:
                bits.append(str(text))
        return "".join(bits)
    status = getattr(root, "status", None) or getattr(payload, "status", None)
    message = getattr(status, "message", None) if status is not None else None
    if message is not None:
        parts = getattr(message, "parts", None) or []
        bits = []
        for part in parts:
            part_root = getattr(part, "root", part)
            text = getattr(part_root, "text", None)
            if text:
                bits.append(str(text))
        return "".join(bits)
    return ""


async def main(prompt: str = "stream demo") -> None:
    remote = A2AAgent(endpoint=ENDPOINT, name="remote_graph_stream")
    builder = GraphBuilder()
    builder.add_node(remote, "remote")
    builder.set_entry_point("remote")
    graph = builder.build()

    async for event in graph.stream_async(prompt):
        _print_stream_event(event)
        if event.get("type") == "multiagent_result" or "result" in event:
            result = event.get("result")
            status = getattr(result, "status", None)
            print(f"\n[client] graph finished status={getattr(status, 'value', status)}", flush=True)


if __name__ == "__main__":
    user_prompt = " ".join(sys.argv[1:]).strip() or "stream demo"
    asyncio.run(main(user_prompt))
```

- [ ] **Step 2: End-to-end manual verification**

Terminal 1:

```bash
cd /Users/keisukedaimon/git/strands-test && .venv/bin/python -m samples.a2a_graph_stream.server
```

Terminal 2:

```bash
cd /Users/keisukedaimon/git/strands-test && .venv/bin/python -m samples.a2a_graph_stream.client
```

Expected:
- Counter lines appear one-by-one (`counter[0]` … `counter[4]`), then transformer lines.
- Not a single dump only at the end.
- Client prints a final status line and exits 0.
- If server is down, client fails fast with a connection error (no retry loop).

If A2A envelope parsing misses text, adjust `_coerce_a2a_text` / `_print_stream_event` until incremental lines appear; keep changes inside `client.py`.

- [ ] **Step 3: Commit**

```bash
git add samples/a2a_graph_stream/client.py
git commit -m "$(cat <<'EOF'
Add client Graph with A2AAgent for FunctionNode streaming sample.

EOF
)"
```

### Task 6: README

**Files:**
- Create: `samples/a2a_graph_stream/README.md`

**Interfaces:**
- Consumes: `server.py`, `client.py`, `test_nodes.py`
- Produces: operator docs for the sample

- [ ] **Step 1: Write README**

```markdown
# A2A Graph FunctionNode Streaming

Standalone sample (strands-agents only):

```text
Client Graph (A2AAgent node)
  -> A2AServer (GraphStreamingAgent adapter)
    -> Server Graph (counter FunctionNode -> transformer FunctionNode)
```

Each FunctionNode loops `0..N-1` and yields one streamed chunk per iteration.

## Run

From the repo root, with the project venv active:

Terminal 1:

```bash
python -m samples.a2a_graph_stream.server
```

Terminal 2:

```bash
python -m samples.a2a_graph_stream.client
```

Optional prompt:

```bash
python -m samples.a2a_graph_stream.client "stream demo"
```

## Unit test (no network)

```bash
python -m unittest samples.a2a_graph_stream.test_nodes -v
```

## Defaults

- N = 5
- sleep = 0.3s per item
- endpoint = http://127.0.0.1:9000
```

- [ ] **Step 2: Commit**

```bash
git add samples/a2a_graph_stream/README.md
git commit -m "$(cat <<'EOF'
Document A2A Graph FunctionNode streaming sample.

EOF
)"
```

---

## Spec Coverage Checklist

| Spec requirement | Task |
|---|---|
| Client Graph with A2AAgent node | Task 5 |
| A2AServer + Agent adapter | Tasks 3–4 |
| Server Graph counter → transformer | Task 2 |
| FunctionNode stream one-by-one | Task 1 |
| Standalone `samples/a2a_graph_stream/` | Tasks 1–6 |
| README two-terminal run | Task 6 |
| Defaults N=5 / 0.3s / :9000 | Tasks 1, 4, 5, 6 |
| `enable_a2a_compliant_streaming=True` | Task 4 |
| Adapter always emits final result | Task 3 |
| Optional FunctionNode unit test | Task 1 |
| No Django changes | (all tasks) |
