import hmac
import hashlib
import logging

from zavudev import Zavudev

from config import Config

logger = logging.getLogger(__name__)

_zavu = Zavudev(api_key=Config.ZAVU_API_KEY)


def send_text(to: str, text: str) -> dict:
    result = _zavu.messages.send(
        to=to,
        text=text,
        channel="telegram",
        zavu_sender=Config.ZAVU_SENDER_ID,
    )
    logger.info(f"Message sent to {to}")
    return result


def send_buttons(to: str, text: str, buttons: list[dict]) -> dict:
    result = _zavu.messages.send(
        to=to,
        text=text,
        channel="telegram",
        zavu_sender=Config.ZAVU_SENDER_ID,
        messageType="buttons",
        content={"buttons": buttons},
    )
    logger.info(f"Buttons sent to {to}")
    return result


def verify_webhook_signature(signature: str, body: bytes) -> bool:
    if not signature or not Config.ZAVU_WEBHOOK_SECRET:
        return False

    expected = hmac.new(
        Config.ZAVU_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature, expected)
