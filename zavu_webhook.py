import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from cachetools import TTLCache

from config import Config
from zavu_client import verify_webhook_signature
from zavu_router import route_event
from zavu_handlers import HANDLER_MAP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_seen_events = TTLCache(maxsize=10000, ttl=600)

app = FastAPI(title="BuscaChat Zavu Webhook")


@app.get("/health")
async def health():
    return {"status": "ok", "code": "message_type_v2"}


@app.post("/webhook")
async def webhook(request: Request):
    signature = request.headers.get("X-Zavu-Signature", "")
    body = await request.body()

    if not verify_webhook_signature(signature, body):
        raise HTTPException(status_code=401, detail="Invalid signature")

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
