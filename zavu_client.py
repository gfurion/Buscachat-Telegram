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
