import hmac
import hashlib
import logging
import json

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from cachetools import TTLCache

from config import Config
from zavu_router import route_event, get_chat_id
from zavu_handlers import HANDLER_MAP
from zavu_state import ReportStateMachine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_seen_events = TTLCache(maxsize=10000, ttl=600)

app = FastAPI(title="BuscaChat Zavu Webhook")


@app.get("/health")
async def health():
    return {"status": "ok"}


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
            "Secret on Railway: %s...",
            Config.ZAVU_WEBHOOK_SECRET[:12] if Config.ZAVU_WEBHOOK_SECRET else "unset"
        )
        # FIXME: Zavu Telegram channel signs with its own secret,
        # separate from the sender's webhook secret. The sender's
        # regenerate_webhook_secret() does not affect the Telegram
        # channel signing secret. Until we find the correct secret
        # via Zavu support/dashboard, we process all webhooks.

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
        active_route = ReportStateMachine.get_route(chat_id)
        msg_type = event.get("data", {}).get("messageType", "")

        if active_route:
            # During FOTO step: route images to photo handler, text to text handler
            if active_route == "reportar:step:foto" and msg_type == "image":
                handler = HANDLER_MAP.get("reportar:step:foto")
            else:
                handler = HANDLER_MAP.get("reportar:step:text")

            if handler:
                await handler(event)
                logger.info(f"Event {event_id}: state machine step {active_route} (chat_id={chat_id}, msg_type={msg_type})")
            else:
                logger.warning(f"No handler for state route: {active_route}")
        else:
            handler_name = route_event(event)

            if handler_name:
                handler = HANDLER_MAP.get(handler_name)
                if handler:
                    await handler(event)
                    logger.info(f"Event {event_id} handled by {handler_name} (chat_id={chat_id})")
                else:
                    logger.warning(f"No handler for route: {handler_name}")
            else:
                logger.info(f"Event {event_id}: no route matched (chat_id={chat_id})")

    except Exception as e:
        logger.error(f"Error processing event {event_id}: {e}", exc_info=True)

    return JSONResponse({"status": "ok"})
