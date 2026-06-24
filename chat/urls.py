from django.urls import path

from chat import views

urlpatterns = [
    path("", views.chat_page, name="chat-page"),
    path("api/conversations/", views.create_conversation, name="create-conversation"),
    path(
        "api/conversations/<uuid:conversation_id>/messages/",
        views.list_messages,
        name="list-messages",
    ),
    path(
        "api/conversations/<uuid:conversation_id>/messages/send/",
        views.send_message,
        name="send-message",
    ),
]
