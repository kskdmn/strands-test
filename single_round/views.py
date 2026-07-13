import json

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from single_round.services import single_round_service


def chat_page(request: HttpRequest):
    return render(request, "single_round/index.html")


@require_POST
def chat(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    message = payload.get("message", "").strip()
    if not message:
        return JsonResponse({"error": "Message content is required."}, status=400)

    try:
        result = single_round_service.chat(message)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse(result)
