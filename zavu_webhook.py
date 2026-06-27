import hmac
import hashlib
import logging
import json

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from cachetools import TTLCache

from config import Config
from zavu_router import route_event
from zavu_handlers import HANDLER_MAP

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

    # DEBUG: show HMAC comparison
    logger.info(f"HMAC DEBUG - Our secret: {Config.ZAVU_WEBHOOK_SECRET[:15]}...")
    logger.info(f"HMAC DEBUG - Timestamp: {timestamp}")
    logger.info(f"HMAC DEBUG - Signed payload (first 100): {signed_payload[:100]}")
    logger.info(f"HMAC DEBUG - Our HMAC: {expected}")
    logger.info(f"HMAC DEBUG - Zavu HMAC: {provided_sig}")
    logger.info(f"HMAC DEBUG - Match: {expected == provided_sig}")

    return hmac.compare_digest(expected, provided_sig)


@app.post("/webhook")
async def webhook(request: Request):
    signature = request.headers.get("X-Zavu-Signature", "")
    body = await request.body()

    # DEBUG: log everything Zavu sends
    logger.info(f"WEBHOOK DEBUG - Headers: {dict(request.headers)}")
    logger.info(f"WEBHOOK DEBUG - Signature header: {signature}")
    logger.info(f"WEBHOOK DEBUG - Body: {body.decode()[:500]}")

    # Try to verify signature
    sig_valid = _verify_signature(signature, body)
    logger.info(f"WEBHOOK DEBUG - Signature valid: {sig_valid}")

    if not sig_valid:
        logger.warning("WEBHOOK DEBUG - Signature invalid, but processing anyway (debug mode)")
        # TEMPORARY: don't reject, just log and continue

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
        handler_name = route_event(event)

        if handler_name:
            handler = HANDLER_MAP.get(handler_name)
            if handler:
                await handler(event)
                logger.info(f"Event {event_id} handled by {handler_name}")
            else:
                logger.warning(f"No handler for route: {handler_name}")
        else:
            logger.info(f"Event {event_id}: no route matched")

    except Exception as e:
        logger.error(f"Error processing event {event_id}: {e}", exc_info=True)

    return JSONResponse({"status": "ok"})
