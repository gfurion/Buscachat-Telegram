import logging
import hashlib
import hmac

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BuscaChat Telegram Webhook")


@app.get("/health")
async def health():
    return {"status": "ok"}


def _verify_telegram_secret(secret_header: str) -> bool:
    if not Config.TELEGRAM_WEBHOOK_SECRET or Config.TELEGRAM_WEBHOOK_SECRET == "change-me":
        return True
    return hmac.compare_digest(secret_header, Config.TELEGRAM_WEBHOOK_SECRET)


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not _verify_telegram_secret(secret):
        logger.warning("Invalid Telegram webhook secret")
        return JSONResponse({"status": "error"}, status_code=403)

    update = await request.json()

    message = update.get("message") or update.get("callback_query")
    if not message:
        return JSONResponse({"status": "ignored"})

    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = str(cb["message"]["chat"]["id"])
        text = cb.get("data", "")
        callback_query_id = cb["id"]
    else:
        chat_id = str(message["chat"]["id"])
        text = message.get("text", "")
        callback_query_id = None

    if not text and message.get("photo"):
        text = ""

    logger.info(f"Telegram update: chat_id={chat_id} text={text[:50]}")

    from zavu_handlers import HANDLER_MAP, get_search_results_route
    from zavu_state import ReportStateMachine

    try:
        active_route = ReportStateMachine.get_route(chat_id)

        if active_route:
            handler = HANDLER_MAP.get("reportar:step:text")
            if handler:
                await handler(chat_id, text)
                logger.info(f"Telegram: state machine step for chat_id={chat_id}")
        else:
            handler_name = _route_telegram(text) or get_search_results_route(chat_id, text)

            if handler_name:
                handler = HANDLER_MAP.get(handler_name)
                if handler:
                    await handler(chat_id, text)
                    logger.info(f"Telegram: {handler_name} for chat_id={chat_id}")
                else:
                    logger.warning(f"No handler for route: {handler_name}")
            else:
                logger.info(f"Telegram: no route for chat_id={chat_id} text={text[:30]}")

        if callback_query_id:
            from telegram_client import answer_callback
            answer_callback(callback_query_id)

    except Exception as e:
        logger.error(f"Error processing Telegram update: {e}", exc_info=True)

    return JSONResponse({"status": "ok"})


def _route_telegram(text: str) -> str | None:
    text = text.strip()

    if text.startswith("/start"):
        return "start"
    if text.startswith("/buscar"):
        return "buscar"
    if text.startswith("/ayuda"):
        return "ayuda"
    if text.startswith("/info"):
        return "info"
    if text.startswith("/registrar"):
        return "registrar_cmd"
    if text.startswith("/emergencia") or text.startswith("/telefonos"):
        return "emergencia"
    if text.startswith("/refugios") or text.startswith("/centros"):
        return "refugios"
    if text.startswith("/"):
        return None

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
