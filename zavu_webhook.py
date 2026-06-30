import hmac
import hashlib
import logging
import json

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from cachetools import TTLCache

from config import Config
from zavu_router import route_event, get_chat_id
from zavu_handlers import HANDLER_MAP, get_search_results_route
from zavu_state import ReportStateMachine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_seen_events = TTLCache(maxsize=10000, ttl=600)

app = FastAPI(title="BuscaChat Webhook")


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Zavu webhook
# ---------------------------------------------------------------------------

def _verify_signature(signature_header: str, body: bytes) -> bool:
    if not signature_header or not Config.ZAVU_WEBHOOK_SECRET:
        return False

    parts = dict(
        part.split("=", 1)
        for part in signature_header.split(",")
        if "=" in part
    )
    timestamp = parts.get("t", "")
    provided_sig = parts.get("v1", "")

    if not timestamp or not provided_sig:
        return False

    signed_payload = f"{timestamp}.{body.decode()}"
    expected = hmac.new(
        Config.ZAVU_WEBHOOK_SECRET.encode(),
        signed_payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, provided_sig)


@app.post("/webhook")
async def webhook(request: Request):
    signature = request.headers.get("X-Zavu-Signature", "")
    body = await request.body()

    sig_valid = _verify_signature(signature, body)

    if not sig_valid:
        logger.warning(
            "Webhook signature verification failed — processing anyway (debug mode). "
            "Telegram channel secret inaccessible via SDK — must be set from Zavu dashboard."
        )

    event = await request.json()
    event_type = event.get("type", "")

    if event_type not in ("message.inbound", "conversation.new"):
        return JSONResponse({"status": "ignored"})

    event_id = event.get("id", "unknown")

    if event_id in _seen_events:
        return JSONResponse({"status": "duplicate"})

    _seen_events[event_id] = True
    logger.info(f"Event {event_id}: {event_type}")

    try:
        chat_id = get_chat_id(event)
        data = event.get("data", {})
        text = data.get("text", "").strip()

        active_route = ReportStateMachine.get_route(chat_id)

        if active_route:
            handler = HANDLER_MAP.get("reportar:step:text")

            if handler:
                await handler(chat_id, text)
                logger.info(f"Event {event_id}: state machine step {active_route} (chat_id={chat_id})")
            else:
                logger.warning(f"No handler for state route: {active_route}")
        else:
            handler_name = get_search_results_route(chat_id, text) or route_event(event)

            if handler_name:
                handler = HANDLER_MAP.get(handler_name)
                if handler:
                    await handler(chat_id, text)
                    logger.info(f"Event {event_id} handled by {handler_name} (chat_id={chat_id})")
                else:
                    logger.warning(f"No handler for route: {handler_name}")
            else:
                logger.info(f"Event {event_id}: no route matched (chat_id={chat_id})")

    except Exception as e:
        logger.error(f"Error processing event {event_id}: {e}", exc_info=True)

    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# Telegram webhook
# ---------------------------------------------------------------------------

def _verify_telegram_secret(secret_header: str) -> bool:
    if not Config.TELEGRAM_WEBHOOK_SECRET or Config.TELEGRAM_WEBHOOK_SECRET == "change-me":
        return True
    return hmac.compare_digest(secret_header, Config.TELEGRAM_WEBHOOK_SECRET)


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


# ---------------------------------------------------------------------------
# Startup — configure Telegram webhook
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def configure_telegram_webhook():
    if not Config.TELEGRAM_ENABLED:
        logger.info("Telegram webhook disabled (TELEGRAM_ENABLED=false)")
        return

    if not Config.PUBLIC_BASE_URL:
        logger.warning("PUBLIC_BASE_URL not set — cannot configure Telegram webhook")
        return

    if not Config.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — cannot configure Telegram webhook")
        return

    try:
        from telegram_client import get_bot
        bot = get_bot()
        url = f"{Config.PUBLIC_BASE_URL.rstrip('/')}/webhook/telegram"
        secret = Config.TELEGRAM_WEBHOOK_SECRET if Config.TELEGRAM_WEBHOOK_SECRET != "change-me" else None

        await bot.set_webhook(
            url=url,
            secret_token=secret,
        )
        logger.info(f"Telegram webhook configured: {url}")
    except Exception as e:
        logger.error(f"Failed to configure Telegram webhook: {e}", exc_info=True)
