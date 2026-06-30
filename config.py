import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_SECRET: str = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "change-me")
    TELEGRAM_ENABLED: bool = os.environ.get("TELEGRAM_ENABLED", "false").lower() == "true"
    PUBLIC_BASE_URL: str = os.environ.get("PUBLIC_BASE_URL", "")
    PORT: int = int(os.environ.get("PORT", "8443"))

    FOUND_PEOPLE_API_URL: str = os.environ.get(
        "FOUND_PEOPLE_API_URL",
        "https://bot-production-ed0b.up.railway.app"
    )
    EXTERNAL_API_SECRET: str = os.environ.get("EXTERNAL_API_SECRET", "")

    DATA_DIR: Path = Path(os.environ.get("DATA_DIR", "./data"))
    FOTOS_DIR: Path = DATA_DIR / "fotos"
    DB_PATH: Path = DATA_DIR / "buscachat.db"
    PERSISTENCE_PATH: Path = DATA_DIR / "bot_data"

    FACE_MATCH_THRESHOLD: float = float(os.environ.get("FACE_MATCH_THRESHOLD", "0.40"))
    FACE_MATCH_ENABLED: bool = os.environ.get("FACE_MATCH_ENABLED", "true").lower() == "true"

    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

    @classmethod
    def ensure_dirs(cls):
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.FOTOS_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls):
        errors = []
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is required")
        if cls.TELEGRAM_ENABLED and cls.TELEGRAM_WEBHOOK_SECRET in ("", "change-me"):
            errors.append("TELEGRAM_WEBHOOK_SECRET must be set to a real secret when TELEGRAM_ENABLED=true")
        if not cls.FOUND_PEOPLE_API_URL:
            errors.append("FOUND_PEOPLE_API_URL is required")
        if errors:
            raise ValueError(f"Config errors: {', '.join(errors)}")
        return True
