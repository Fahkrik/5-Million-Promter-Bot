import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _get_env(name: str, required: bool = False, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if required and (value is None or value.strip() == ""):
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_telegram_id: int
    bank_card_number: str
    bank_cardholder: str
    database_url: str
    log_level: str
    data_retention_days: int

    @property
    def assets_dir(self) -> Path:
        return BASE_DIR / "assets"

    def _resolve_asset(self, base_name: str) -> Path:
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            path = self.assets_dir / f"{base_name}{ext}"
            if path.exists():
                return path
        # default path (may be replaced later)
        return self.assets_dir / f"{base_name}.png"

    @property
    def cert_image_1(self) -> Path:
        return self._resolve_asset("certificate_type_1")

    @property
    def cert_image_2(self) -> Path:
        return self._resolve_asset("certificate_type_2")


def load_settings() -> Settings:
    bot_token = _get_env("BOT_TOKEN", required=True)
    admin_raw = _get_env("ADMIN_TELEGRAM_ID", required=True)
    try:
        admin_telegram_id = int(admin_raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("ADMIN_TELEGRAM_ID must be an integer") from exc

    bank_card_number = _get_env("BANK_CARD_NUMBER", default="KARTA_RAQAMI_KIRITILMAGAN") or ""
    bank_cardholder = _get_env("BANK_CARDHOLDER", default="KARTA_EGASI_KIRITILMAGAN") or ""
    database_url = _get_env("DATABASE_URL", default="sqlite:///bot.db") or "sqlite:///bot.db"
    log_level = (_get_env("LOG_LEVEL", default="INFO") or "INFO").upper()
    try:
        data_retention_days = int(_get_env("DATA_RETENTION_DAYS", default="365") or "365")
    except ValueError:
        data_retention_days = 365

    return Settings(
        bot_token=bot_token,
        admin_telegram_id=admin_telegram_id,
        bank_card_number=bank_card_number,
        bank_cardholder=bank_cardholder,
        database_url=database_url,
        log_level=log_level,
        data_retention_days=data_retention_days,
    )
