# A2A Graph FunctionNode Streaming

Standalone sample (strands-agents only):

```text
Client Graph (A2AAgent node)
  -> A2AServer (GraphStreamingAgent adapter)
    -> Server Graph (counter FunctionNode -> transformer FunctionNode)
```

Each FunctionNode loops `0..N-1` and yields one streamed chunk per iteration.

## Prerequisites

From the repo root, install dependencies (includes the `a2a` extra via `strands-agents[a2a]`):

```bash
uv sync
```

Activate the project venv before running the commands below.

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
