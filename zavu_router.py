import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

Handler = Callable[[dict], Awaitable[None]]


def route_event(event: dict) -> str | None:
    data = event.get("data", {})
    msg_type = data.get("messageType", "")
    text = data.get("text", "").strip()
    interactive = data.get("content", {}).get("interactiveReply")

    if interactive:
        button_id = interactive.get("id", "")
        if button_id:
            return f"button:{button_id}"

    if msg_type == "image":
        return "photo"

    if msg_type != "text":
        return None

    if text.startswith("/start"):
        return "start"
    if text.startswith("/buscar"):
        return "buscar"
    if text.startswith("/ayuda"):
        return "ayuda"
    if text.startswith("/"):
        return None

    if len(text) >= 2:
        return "free_text"

    return None


def get_chat_id(event: dict) -> str:
    return event["data"]["from"]
