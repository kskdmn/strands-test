import threading
from uuid import UUID

from django.conf import settings
from django.db.models import QuerySet
from strands import Agent

from chat.agents.subagents import production_schedule_assistant, sales_forecast_assistant
from chat.models import Conversation, Message

ORCHESTRATOR_SYSTEM_PROMPT = """
You are the main assistant for a manufacturing company chat.

Route specialized requests to the right tool:
- Sales forecasts, demand planning, or questions about past sales trends
  -> use sales_forecast_assistant
- Factory status, production schedules, or when a product will be produced
  -> use production_schedule_assistant
- General conversation that does not need company data -> answer directly

When routing, pass the user's full question to the selected tool.
Keep final answers concise and conversational.
""".strip()


class ChatService:
    _agents: dict[str, Agent] = {}
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._system_prompt = ORCHESTRATOR_SYSTEM_PROMPT
        self._tools = [sales_forecast_assistant, production_schedule_assistant]

    def create_conversation(self) -> Conversation:
        return Conversation.objects.create()

    def get_messages(self, conversation_id: UUID) -> QuerySet[Message]:
        return Message.objects.filter(conversation_id=conversation_id)

    def send_message(self, conversation_id: UUID, content: str) -> tuple[Message, Message]:
        conversation = Conversation.objects.get(id=conversation_id)
        agent = self._get_agent(conversation_id)
        response = agent(content)
        assistant_text = str(response)

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

    def _get_agent(self, conversation_id: UUID) -> Agent:
        key = str(conversation_id)
        with self._lock:
            agent = self._agents.get(key)
            if agent is not None:
                return agent

            messages = self._load_messages(conversation_id)
            agent = Agent(
                model=settings.CHAT_MODEL_ID,
                system_prompt=self._system_prompt,
                messages=messages,
                tools=self._tools,
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
