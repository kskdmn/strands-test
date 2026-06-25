import threading
from uuid import UUID

from django.conf import settings
from django.db.models import QuerySet
from strands import Agent

from chat.tools.catalog import list_available_products
from chat.tools.time import current_time

from chat.agents.subagents import (
    inventory_assistant,
    planning_assistant,
    production_schedule_assistant,
    sales_forecast_assistant,
)
from chat.flow_log import FLOW_LOG_HOOKS, log_request_end, log_request_start
from chat.models import Conversation, Message
from chat.prompts import build_orchestrator_system_prompt
from chat.tool_fallback import resolve_leaked_tool_response


class ChatService:
    _agents: dict[str, Agent] = {}
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._tools = [
            current_time,
            list_available_products,
            sales_forecast_assistant,
            production_schedule_assistant,
            inventory_assistant,
            planning_assistant,
        ]

    def create_conversation(self) -> Conversation:
        return Conversation.objects.create()

    def get_messages(self, conversation_id: UUID) -> QuerySet[Message]:
        return Message.objects.filter(conversation_id=conversation_id)

    def send_message(self, conversation_id: UUID, content: str) -> tuple[Message, Message]:
        log_request_start(conversation_id, content)
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            agent = self._get_agent(conversation_id)
            agent.system_prompt = build_orchestrator_system_prompt()
            response = agent(
                content,
                invocation_state={"conversation_id": str(conversation_id)},
            )
            assistant_text = resolve_leaked_tool_response(str(response))

            user_message = Message.objects.create(
                conversation=conversation,
                role=Message.Role.USER,
                content=content,
            )
            assistant_message = Message.objects.create(
                conversation=conversation,
                role=Message.Role.ASSISTANT,
                content=assistant_text,
            )
            return user_message, assistant_message
        finally:
            log_request_end()

    def _get_agent(self, conversation_id: UUID) -> Agent:
        key = str(conversation_id)
        with self._lock:
            agent = self._agents.get(key)
            if agent is not None:
                return agent

            messages = self._load_messages(conversation_id)
            agent = Agent(
                model=settings.CHAT_MODEL_ID,
                name="orchestrator",
                system_prompt=build_orchestrator_system_prompt(),
                messages=messages,
                tools=self._tools,
                hooks=[FLOW_LOG_HOOKS],
                callback_handler=None,
            )
            self._agents[key] = agent
            return agent

    def _load_messages(self, conversation_id: UUID) -> list[dict]:
        stored_messages = Message.objects.filter(conversation_id=conversation_id)
        return [
            {
                "role": message.role,
                "content": [{"text": message.content}],
            }
            for message in stored_messages
        ]


chat_service = ChatService()
