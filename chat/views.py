import json
from uuid import UUID

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from chat.models import Conversation, Message
from chat.services import chat_service


def chat_page(request: HttpRequest):
    return render(request, "chat/index.html")


@require_POST
def create_conversation(request: HttpRequest) -> JsonResponse:
    conversation = chat_service.create_conversation()
    return JsonResponse({"conversation_id": str(conversation.id)})


@require_GET
def list_messages(request: HttpRequest, conversation_id: UUID) -> JsonResponse:
    if not Conversation.objects.filter(id=conversation_id).exists():
        return JsonResponse({"error": "Conversation not found."}, status=404)

    messages = chat_service.get_messages(conversation_id)
    return JsonResponse(
        {
            "messages": [
                {
                    "id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "created_at": message.created_at.isoformat(),
                }
                for message in messages
            ]
        }
    )


@require_POST
def send_message(request: HttpRequest, conversation_id: UUID) -> JsonResponse:
    if not Conversation.objects.filter(id=conversation_id).exists():
        return JsonResponse({"error": "Conversation not found."}, status=404)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    content = payload.get("content", "").strip()
    if not content:
        return JsonResponse({"error": "Message content is required."}, status=400)

    try:
        user_message, assistant_message = chat_service.send_message(conversation_id, content)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse(
        {
            "conversation_id": str(conversation_id),
            "messages": [
                {
                    "id": user_message.id,
                    "role": user_message.role,
                    "content": user_message.content,
                    "created_at": user_message.created_at.isoformat(),
                },
                {
                    "id": assistant_message.id,
                    "role": assistant_message.role,
                    "content": assistant_message.content,
                    "created_at": assistant_message.created_at.isoformat(),
                },
            ],
        }
    )
