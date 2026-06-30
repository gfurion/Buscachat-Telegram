import logging
import asyncio
import concurrent.futures

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from config import Config

logger = logging.getLogger(__name__)

_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
    return _bot


def send_text(chat_id: int, text: str) -> None:
    async def _send():
        bot = get_bot()
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info(f"Message sent to {chat_id}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())


def send_photo(chat_id: int, photo: str, caption: str = "") -> None:
    async def _send():
        bot = get_bot()
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info(f"Photo sent to {chat_id}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())


def answer_callback(callback_query_id: str, text: str = "") -> None:
    async def _send():
        bot = get_bot()
        await bot.answer_callback_query(
            callback_query_id=callback_query_id,
            text=text,
        )
        logger.info(f"Callback answered: {callback_query_id}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())


def edit_message_text(chat_id: int, message_id: int, text: str,
                      buttons: list[list[dict]] | None = None) -> None:
    async def _send():
        bot = get_bot()
        kwargs = {
            "chat_id": int(chat_id),
            "message_id": message_id,
            "text": text,
            "parse_mode": ParseMode.MARKDOWN,
        }
        if buttons:
            keyboard = [
                [InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"])
                 for btn in row]
                for row in buttons
            ]
            kwargs["reply_markup"] = InlineKeyboardMarkup(keyboard)
        await bot.edit_message_text(**kwargs)
        logger.info(f"Message edited for chat_id={chat_id}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())


def edit_message_reply_markup(chat_id: int, message_id: int,
                               buttons: list[list[dict]] | None = None) -> None:
    async def _send():
        bot = get_bot()
        if buttons:
            keyboard = [
                [InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"])
                 for btn in row]
                for row in buttons
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            reply_markup = ""
        await bot.edit_message_reply_markup(
            chat_id=int(chat_id),
            message_id=message_id,
            reply_markup=reply_markup,
        )
        logger.info(f"Reply markup edited for chat_id={chat_id}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())


def send_image(chat_id: int, image_url: str, caption: str = "") -> None:
    send_photo(chat_id, image_url, caption)


def send_menu_with_buttons(chat_id: int, text: str, buttons: list[list[dict]]) -> None:
    async def _send():
        bot = get_bot()
        keyboard = [
            [InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"])
             for btn in row]
            for row in buttons
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
        )
        logger.info(f"Menu with buttons sent to {chat_id}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())
