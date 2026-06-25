import json
import logging
import threading
from contextvars import ContextVar
from typing import Any
from uuid import UUID

from django.conf import settings
from strands.hooks import (
    AfterInvocationEvent,
    AfterModelCallEvent,
    AfterToolCallEvent,
    BeforeInvocationEvent,
    BeforeModelCallEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)

logger = logging.getLogger("chat.flow")

_conversation_id: ContextVar[str | None] = ContextVar("conversation_id", default=None)
_depth = threading.local()


def set_flow_context(conversation_id: UUID | str | None) -> None:
    _conversation_id.set(str(conversation_id) if conversation_id else None)


def _conv_prefix() -> str:
    conversation_id = _conversation_id.get()
    if not conversation_id:
        return ""
    return f"[conv={conversation_id[:8]}] "


def _indent() -> str:
    depth = getattr(_depth, "value", 0)
    return "  " * depth


def _agent_name(agent: Any) -> str:
    return getattr(agent, "name", None) or "agent"


def _truncate(text: str, limit: int = 200) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _log_limit(setting_name: str, default: int) -> int:
    return int(getattr(settings, setting_name, default))


def _format_json_payload(payload: Any) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except TypeError:
        return str(payload)


def _format_text_payload(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return _format_json_payload(json.loads(stripped))
        except json.JSONDecodeError:
            pass
    return text


def _format_tool_input(tool_use: dict[str, Any] | None) -> str:
    if not tool_use:
        return ""
    try:
        payload = json.dumps(tool_use.get("input", {}), ensure_ascii=False, indent=2)
    except TypeError:
        payload = str(tool_use.get("input", {}))
    return _truncate(payload, _log_limit("FLOW_LOG_TOOL_INPUT_LIMIT", 1000))


def _format_tool_result(result: dict[str, Any] | None) -> str:
    if not result:
        return "no result"

    status = result.get("status", "unknown")
    chunks: list[str] = []
    for block in result.get("content", []):
        if "text" in block:
            chunks.append(_format_text_payload(block["text"]))
        elif "json" in block:
            chunks.append(_format_json_payload(block["json"]))

    summary = "\n".join(chunks) if chunks else "(empty)"
    limit = _log_limit("FLOW_LOG_TOOL_RESULT_LIMIT", 4000)
    return f"status={status}\n{_truncate(summary, limit)}"


def log_request_start(conversation_id: UUID, content: str) -> None:
    set_flow_context(conversation_id)
    logger.info("%sREQUEST user: %s", _conv_prefix(), _truncate(content, 120))


def log_request_end() -> None:
    logger.info("%sREQUEST done", _conv_prefix())
    set_flow_context(None)


def log_agent_cache_reset(conversation_id: UUID) -> None:
    logger.info("%sCACHE orchestrator agent reset", _conv_prefix() or f"[conv={conversation_id}] ")


class FlowLogHooks(HookProvider):
    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self.on_before_invocation)
        registry.add_callback(AfterInvocationEvent, self.on_after_invocation)
        registry.add_callback(BeforeModelCallEvent, self.on_before_model)
        registry.add_callback(AfterModelCallEvent, self.on_after_model)
        registry.add_callback(BeforeToolCallEvent, self.on_before_tool)
        registry.add_callback(AfterToolCallEvent, self.on_after_tool)

    def on_before_invocation(self, event: BeforeInvocationEvent) -> None:
        _depth.value = getattr(_depth, "value", 0) + 1
        logger.info(
            "%s%sAGENT %s START",
            _conv_prefix(),
            _indent(),
            _agent_name(event.agent),
        )

    def on_after_invocation(self, event: AfterInvocationEvent) -> None:
        logger.info(
            "%s%sAGENT %s END",
            _conv_prefix(),
            _indent(),
            _agent_name(event.agent),
        )
        _depth.value = max(0, getattr(_depth, "value", 0) - 1)

    def on_before_model(self, event: BeforeModelCallEvent) -> None:
        tokens = event.projected_input_tokens
        token_note = f" (~{tokens} input tokens)" if tokens is not None else ""
        logger.info(
            "%s%sMODEL CALL %s%s",
            _conv_prefix(),
            _indent(),
            _agent_name(event.agent),
            token_note,
        )

    def on_after_model(self, event: AfterModelCallEvent) -> None:
        stop_reason = getattr(event, "stop_reason", None)
        suffix = f" stop={stop_reason}" if stop_reason else ""
        logger.info(
            "%s%sMODEL DONE %s%s",
            _conv_prefix(),
            _indent(),
            _agent_name(event.agent),
            suffix,
        )

    def on_before_tool(self, event: BeforeToolCallEvent) -> None:
        tool_name = event.tool_use.get("name", "unknown") if event.tool_use else "unknown"
        tool_input = _format_tool_input(event.tool_use)
        logger.info(
            "%s%sTOOL CALL %s(%s)",
            _conv_prefix(),
            _indent(),
            tool_name,
            tool_input,
        )

    def on_after_tool(self, event: AfterToolCallEvent) -> None:
        tool_name = event.tool_use.get("name", "unknown") if event.tool_use else "unknown"
        if event.exception is not None:
            logger.info(
                "%s%sTOOL ERROR %s: %s",
                _conv_prefix(),
                _indent(),
                tool_name,
                event.exception,
            )
            return

        logger.info(
            "%s%sTOOL DONE %s -> %s",
            _conv_prefix(),
            _indent(),
            tool_name,
            _format_tool_result(event.result),
        )


FLOW_LOG_HOOKS = FlowLogHooks()
