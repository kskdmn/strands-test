import threading
from uuid import UUID

from django.conf import settings
from django.db.models import QuerySet
from strands import Agent

from chat.models import Conversation, Message


class ChatService:
    _agents: dict[str, Agent] = {}
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._system_prompt = (
            "You are a helpful assistant in a web chat. "
            "Keep responses concise and conversational."
        )

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
