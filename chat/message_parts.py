from typing import Any

from strands.agent.agent_result import AgentResult


def _block_text(block: dict[str, Any]) -> str:
    if "text" in block and block["text"]:
        return str(block["text"])
    if "reasoningContent" in block:
        reasoning = block["reasoningContent"]
        if isinstance(reasoning, dict):
            text = reasoning.get("text") or reasoning.get("reasoningText")
            if text:
                return str(text)
    return ""


def _format_tool_use(block: dict[str, Any]) -> str:
    tool_use = block.get("toolUse") or {}
    name = tool_use.get("name", "unknown")
    tool_input = tool_use.get("input", {})
    return f"Tool call: {name}({tool_input})"


def _format_tool_result(block: dict[str, Any]) -> str:
    tool_result = block.get("toolResult") or {}
    status = tool_result.get("status", "unknown")
    chunks: list[str] = []
    for item in tool_result.get("content", []):
        if isinstance(item, dict) and "text" in item:
            chunks.append(str(item["text"]))
        elif isinstance(item, dict) and "json" in item:
            chunks.append(str(item["json"]))
    body = " ".join(chunks) if chunks else "(empty)"
    return f"Tool result ({status}): {body}"


def _message_text(message: dict[str, Any]) -> str:
    parts: list[str] = []
    for block in message.get("content", []):
        if not isinstance(block, dict):
            continue
        if "toolUse" in block:
            parts.append(_format_tool_use(block))
            continue
        if "toolResult" in block:
            parts.append(_format_tool_result(block))
            continue
        text = _block_text(block)
        if text:
            parts.append(text)
    return "\n\n".join(parts).strip()


def _has_tool_use(message: dict[str, Any]) -> bool:
    return any(
        isinstance(block, dict) and "toolUse" in block
        for block in message.get("content", [])
    )


def _has_tool_result(message: dict[str, Any]) -> bool:
    return any(
        isinstance(block, dict) and "toolResult" in block
        for block in message.get("content", [])
    )


def _result_text(result: AgentResult) -> str:
    message = result.message
    if isinstance(message, dict):
        return _message_text(message)
    return str(message)


def split_turn_messages(new_messages: list[dict[str, Any]]) -> tuple[str, str]:
    thinking_parts: list[str] = []
    final_answer = ""

    last_plain_assistant_idx = None
    for index, message in enumerate(new_messages):
        if message.get("role") == "assistant" and not _has_tool_use(message):
            last_plain_assistant_idx = index

    for index, message in enumerate(new_messages):
        role = message.get("role")
        text = _message_text(message)
        if not text:
            continue

        if role == "assistant":
            if _has_tool_use(message) or index != last_plain_assistant_idx:
                thinking_parts.append(text)
            else:
                final_answer = text
            continue

        if role == "user" and _has_tool_result(message):
            thinking_parts.append(text)

    thinking = "\n\n".join(thinking_parts).strip()
    return thinking, final_answer


def build_assistant_parts(
    agent: Any,
    messages_before: int,
    result: AgentResult,
    raw_text: str,
) -> tuple[str, str]:
    new_messages = agent.messages[messages_before:]
    thinking, final_answer = split_turn_messages(new_messages)

    if not final_answer:
        final_answer = _result_text(result).strip() or raw_text.strip()

    if thinking and final_answer and thinking == final_answer:
        return "", final_answer

    return thinking, final_answer
