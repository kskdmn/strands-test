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
    # A2A streaming often yields (Task, TaskArtifactUpdateEvent | TaskStatusUpdateEvent | None)
    if isinstance(payload, tuple) and len(payload) == 2:
        _, update_event = payload
        if update_event is not None:
            return _coerce_a2a_text(update_event)
        return ""
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
