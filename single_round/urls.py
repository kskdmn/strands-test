from django.urls import path

from single_round import views

urlpatterns = [
    path("single-round/", views.chat_page, name="single-round-page"),
    path("api/single-round/chat/", views.chat, name="single-round-chat"),
]
