import logging

logger = logging.getLogger(__name__)


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
    if text.startswith("/registrar"):
        return "registrar_cmd"
    if text.startswith("/emergencia") or text.startswith("/telefonos"):
        return "emergencia"
    if text.startswith("/refugios") or text.startswith("/centros"):
        return "refugios"
    if text.startswith("/"):
        return None

    # Numeric menu selections
    if text == "1":
        return "menu:buscar"
    if text == "2":
        return "menu:registrar"
    if text == "3":
        return "menu:refugios"
    if text == "4":
        return "menu:emergencia"
    if text == "5":
        return "ayuda"

    if len(text) >= 2:
        return "free_text"

    return None


def get_chat_id(event: dict) -> str:
    data = event.get("data", {})
    chat_id = data.get("telegramChatId", "")
    if chat_id:
        return chat_id
    from_field = data.get("from", "")
    if from_field.startswith("telegram:"):
        return from_field[len("telegram:"):]
    return from_field
