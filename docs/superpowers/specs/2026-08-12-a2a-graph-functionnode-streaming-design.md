# A2A Graph FunctionNode Streaming Sample

## Goal

Add a standalone sample (no Django) that demonstrates end-to-end streaming:

```
[Client Graph]
  A2AAgent (node)
       │  A2A protocol (stream)
       ▼
[A2AServer]
  thin Agent adapter
       │
       ▼
[Server Graph]
  FunctionNode "counter" → FunctionNode "transformer"
```

Each FunctionNode loops (`for i in range(N)`) and yields one chunk at a time so the client sees incremental output.

Stack: **strands-agents** only (already in `pyproject.toml`).

## Non-goals

- Django UI / `single_round` integration
- Domain (catalog/factory) logic
- Production A2A deployment (auth, multi-tenant factory, push notifications)

## Architecture

### Server (`samples/a2a_graph_stream/`)

| Piece | Role |
|---|---|
| `FunctionNode` | Custom `MultiAgentBase`. Override `stream_async` to yield `{"data": ...}` per iteration (with `asyncio.sleep`), then a final `{"result": MultiAgentResult(...)}`. Default `MultiAgentBase.stream_async` only runs `invoke_async` once — not enough for item-by-item streaming. |
| Server Graph | Sequential: `counter` → `transformer`. Counter yields `counter[i]=0..N-1`. Transformer runs its own loop `0..N-1` and yields `transformer[i]=...` (independent of parsing upstream text — keeps the streaming demo obvious). |
| Agent adapter | Subclass of Strands `Agent` that overrides `stream_async`: run `server_graph.stream_async`, map nested `data` / `multiagent_node_stream` events into A2A-friendly `{"data": text}` chunks, then emit a final `{"result": AgentResult(...)}`. Required because `A2AServer` accepts `Agent`, not `Graph`. Use a cheap/local model id only if the base `Agent` constructor requires one; the override must not call the model. |
| `A2AServer` | Serves the adapter on `127.0.0.1:9000` with `enable_a2a_compliant_streaming=True`. |

### Client

| Piece | Role |
|---|---|
| `A2AAgent` | Points at `http://127.0.0.1:9000`. |
| Client Graph | One node: `A2AAgent` as entry. Observe streaming via `client_graph.stream_async` → `multiagent_node_stream`. |
| `client.py` | Prints streamed text chunks as they arrive (flush), then prints final status. |

### Defaults

- `N = 5`
- ~0.3s sleep per FunctionNode item
- Host/port: `127.0.0.1:9000`

## File layout

```
samples/a2a_graph_stream/
  nodes.py       # FunctionNode + counter / transformer helpers
  server_graph.py  # build server Graph
  adapter.py     # Agent adapter: Graph stream → {"data"} chunks
  server.py      # start A2AServer
  client.py      # Client Graph + A2AAgent, print stream
  README.md      # run instructions (two terminals)
```

Prefer the split above for clarity. Collapsing `server_graph.py` into `server.py` is allowed if the sample stays under ~150 lines total for those two.

## Data flow (happy path)

1. User runs `server.py` (blocks on uvicorn).
2. User runs `client.py` with a short prompt (e.g. `"stream demo"`).
3. Client Graph invokes `A2AAgent` node → A2A `sendMessageStream`.
4. `A2AServer` / `StrandsA2AExecutor` calls adapter `stream_async`.
5. Adapter runs Server Graph:
   - `counter` yields N data chunks, then result
   - `transformer` runs next, yields N data chunks, then result
6. Adapter re-emits text chunks as `{"data": ...}` for A2A artifact/status updates.
7. Client Graph forwards remote stream events; `client.py` prints them one by one.

## Error handling

- If server is down: client fails fast with a clear connection error (no retry loop in the sample).
- FunctionNode exceptions: surface as failed node / A2A task failure; sample does not add custom recovery.
- Adapter must always emit a final `result` event so Graph/A2A executors do not hang waiting for completion.

## Testing / verification

Manual (primary for this sample):

1. Start server.
2. Start client.
3. Confirm console shows incremental lines from counter, then transformer, not one blob at the end.
4. Confirm process exits cleanly after the final result.

Optional smoke: a small async unit test that runs `FunctionNode.stream_async` alone and asserts N `data` events before `result` (no network). Nice-to-have, not required for v1.

## Constraints (from strands-agents)

- `A2AServer` wraps `Agent` only → adapter is mandatory for Graph-behind-A2A.
- Graph forwards nested `stream_async` events; FunctionNodes must implement real streaming themselves.
- Client `A2AAgent.stream_async` yields A2A protocol events (`type: a2a_stream`) plus a final `result`; the client Graph wrapper presents these as `multiagent_node_stream`. Sample code should handle both shapes defensively when printing.

## Success criteria

- Sample runs with two terminals using strands-agents only.
- Architecture matches: Client Graph → A2AAgent → A2AServer → Server Graph → 2 FunctionNodes.
- Streaming is visibly incremental (sleep + print per item).
- README documents how to run.
