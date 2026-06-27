import logging

from telegram.ext import Application

from config import Config
from handlers import (
    start_handler,
    menu_handler,
    menu_registrar_handler,
    ayuda_handler,
    reportar_conv,
    buscar_handler,
    buscar_callback_handler,
    foto_handler,
    texto_libre_handler,
    error_handler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger(__name__)


def build_app() -> Application:
    Config.validate()
    Config.ensure_dirs()

    app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # Orden critico: ConversationHandler primero, foto despues
    app.add_handler(start_handler)
    app.add_handler(menu_handler)
    app.add_handler(menu_registrar_handler)
    app.add_handler(ayuda_handler)
    app.add_handler(reportar_conv)
    app.add_handler(buscar_handler)
    app.add_handler(buscar_callback_handler)
    app.add_handler(foto_handler)
    app.add_handler(texto_libre_handler)
    app.add_error_handler(error_handler)

    return app


def main():
    app = build_app()

    if Config.PUBLIC_BASE_URL:
        logger.info(f"Starting webhook on port {Config.PORT}")
        app.run_webhook(
            listen="0.0.0.0",
            port=Config.PORT,
            url_path=Config.TELEGRAM_BOT_TOKEN,
            secret_token=Config.TELEGRAM_WEBHOOK_SECRET,
            webhook_url=f"{Config.PUBLIC_BASE_URL}/{Config.TELEGRAM_BOT_TOKEN}",
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
    else:
        logger.info("Starting polling mode (no PUBLIC_BASE_URL set)")
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )


if __name__ == "__main__":
    main()
