
import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .faq_data import find_best_match, FALLBACK_ANSWER

logger = logging.getLogger(__name__)


# Greeting shown when the chat widget first opens
GREETING = (
    "Hi! LifeLink Nepal connects blood donors with hospitals across Nepal "
    "during emergencies. Are you here to donate blood, register as a "
    "hospital, or do you have a question?"
)

# Quick-reply options shown alongside the greeting
GREETING_QUICK_REPLIES = [
    {"label": "I want to donate", "value": "I want to register as a donor"},
    {"label": "I'm a hospital", "value": "I want to register as a hospital"},
    {"label": "I have a question", "value": "I have a question"},
]


@csrf_exempt  # NOTE: see bottom of file for the recommended non-exempt version
@require_POST
def chatbot_message(request):
    """
    POST endpoint for the chatbot widget.

    Expects JSON body: {"message": "<user's text>"}
    Returns JSON: {
        "answer": "<bot's reply text>",
        "action": "route_donor" | "route_hospital" | null,
        "matched": true | false
    }
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request body"}, status=400)

    user_message = body.get("message", "")

    if not isinstance(user_message, str) or not user_message.strip():
        return JsonResponse({"error": "Message is required"}, status=400)

    # Cap message length to something reasonable - this is a FAQ matcher,
    # not a general chat endpoint, so very long input is not expected
    user_message = user_message[:500]

    # Special case: the "I have a question" quick-reply isn't itself a
    # question - it's a meta-action that should prompt the user to type
    # their actual question, not be matched against the FAQ.
    if user_message.strip().lower() == "i have a question":
        return JsonResponse({
            "answer": "Sure - go ahead and type your question below.",
            "action": None,
            "matched": True,
        })

    match = find_best_match(user_message)

    if match is not None:
        logger.info(f"Chatbot matched FAQ entry: {match['id']}")
        return JsonResponse({
            "answer": match["answer"],
            "action": match.get("action"),
            "matched": True,
        })

    logger.info(f"Chatbot found no FAQ match for message: {user_message[:80]!r}")
    return JsonResponse({
        "answer": FALLBACK_ANSWER,
        "action": None,
        "matched": False,
    })


def chatbot_greeting(request):
    """
    GET endpoint returning the initial greeting + quick-reply buttons,
    shown when the chat widget first opens.
    """
    return JsonResponse({
        "answer": GREETING,
        "quick_replies": GREETING_QUICK_REPLIES,
    })



