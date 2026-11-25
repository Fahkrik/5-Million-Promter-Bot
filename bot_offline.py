#!/usr/bin/env python3
# 5 Million Promter / Dasturchi — OFFLINE (stdlib-only) Telegram bot
# Termux uchun: pip/aiogram/SQLAlchemy kerak emas. Faqat: python bot_offline.py
from __future__ import annotations

import json
import logging
import socket
import sqlite3
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, date
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
LOG = logging.getLogger("promter")


# ----------------------------- config -------------------------------------
def load_env() -> dict[str, str]:
    path = BASE_DIR / ".env"
    if not path.exists():
        raise SystemExit("Xatolik: .env fayli topilmadi. Loyiha papkasida ekanligingizni tekshiring.")
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


class Settings:
    def __init__(self, env: dict[str, str]):
        self.bot_token = env.get("BOT_TOKEN", "")
        if not self.bot_token:
            raise SystemExit("Xatolik: .env ichida BOT_TOKEN bo'sh.")
        self.admin_id = int(env.get("ADMIN_TELEGRAM_ID", "0") or 0)
        if not self.admin_id:
            raise SystemExit("Xatolik: .env ichida ADMIN_TELEGRAM_ID bo'sh.")
        self.card_number = env.get("BANK_CARD_NUMBER", "-")
        self.card_holder = env.get("BANK_CARDHOLDER", "-")

        url = env.get("DATABASE_URL", "sqlite:///bot.db")
        if url.startswith("sqlite:///"):
            raw = url[len("sqlite:///") :]
            p = Path(raw)
            self.db_path = p if p.is_absolute() else BASE_DIR / raw
        else:
            self.db_path = BASE_DIR / "bot.db"

        self.assets_dir = BASE_DIR / "assets"

    def image(self, base: str) -> Path:
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            p = self.assets_dir / f"{base}{ext}"
            if p.exists():
                return p
        return self.assets_dir / f"{base}.png"


ENV = load_env()
S = Settings(ENV)


# ----------------------------- database -----------------------------------
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(S.db_path, timeout=30, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    c = conn()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id INTEGER NOT NULL,
            telegram_username TEXT,
            certificate_type INTEGER,
            certificate_price INTEGER,
            customer_role TEXT,
            first_name TEXT,
            last_name TEXT,
            middle_name TEXT,
            document_type TEXT,
            document_number TEXT,
            phone_number TEXT,
            date_of_birth TEXT,
            payment_screenshot_file_id TEXT,
            payment_status TEXT NOT NULL DEFAULT 'NOT_PAID',
            order_status TEXT NOT NULL DEFAULT 'DRAFT',
            consent_given_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            approved_at TEXT,
            approved_by INTEGER
        )
        """
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(telegram_user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_payment ON orders(payment_status)")
    c.commit()
    c.close()


ACTIVE = ("DRAFT", "AWAITING_CONFIRMATION", "AWAITING_PAYMENT", "AWAITING_SCREENSHOT", "PAYMENT_REJECTED")


def row(c: sqlite3.Connection, oid: int) -> sqlite3.Row | None:
    return c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()


def get_active(c: sqlite3.Connection, uid: int, username: str | None) -> sqlite3.Row:
    o = c.execute(
        "SELECT * FROM orders WHERE telegram_user_id=? AND order_status IN (%s) "
        "AND payment_status!='PAYMENT_APPROVED' ORDER BY id DESC LIMIT 1"
        % ",".join("?" for _ in ACTIVE),
        (uid, *ACTIVE),
    ).fetchone()
    if o:
        if username and o["telegram_username"] != username:
            c.execute("UPDATE orders SET telegram_username=? WHERE id=?", (username, o["id"]))
            c.commit()
            o = row(c, o["id"])
        return o
    c.execute(
        "INSERT INTO orders(telegram_user_id, telegram_username, order_status, payment_status, consent_given_at) "
        "VALUES(?,?,?,?,?)",
        (uid, username, "DRAFT", "NOT_PAID", datetime.now().isoformat(timespec="seconds")),
    )
    c.commit()
    return c.execute("SELECT * FROM orders WHERE id=last_insert_rowid()").fetchone()


def update_fields(c: sqlite3.Connection, oid: int, **fields: Any) -> sqlite3.Row:
    allowed = {
        "certificate_type", "certificate_price", "customer_role", "first_name", "last_name",
        "middle_name", "document_type", "document_number", "phone_number", "date_of_birth",
        "payment_screenshot_file_id", "payment_status", "order_status", "approved_at", "approved_by",
    }
    sets, values = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            values.append(v)
    if sets:
        values.append(oid)
        c.execute(f"UPDATE orders SET {', '.join(sets)}, updated_at=CURRENT_TIMESTAMP WHERE id=?", values)
        c.commit()
    return row(c, oid)


def set_status(c: sqlite3.Connection, oid: int, status: str, payment: str | None = None) -> None:
    if payment:
        c.execute(
            "UPDATE orders SET order_status=?, payment_status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, payment, oid),
        )
    else:
        c.execute("UPDATE orders SET order_status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, oid))
    c.commit()


def approve(c: sqlite3.Connection, oid: int, admin_id: int) -> tuple[sqlite3.Row | None, bool]:
    o = row(c, oid)
    if not o or o["payment_status"] == "PAYMENT_APPROVED":
        return o, False
    c.execute(
        "UPDATE orders SET payment_status='PAYMENT_APPROVED', order_status='PAYMENT_APPROVED', "
        "approved_at=?, approved_by=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (datetime.now().isoformat(timespec="seconds"), admin_id, oid),
    )
    c.commit()
    return row(c, oid), True


def reject(c: sqlite3.Connection, oid: int) -> None:
    c.execute(
        "UPDATE orders SET payment_status='PAYMENT_REJECTED', order_status='PAYMENT_REJECTED', "
        "approved_at=NULL, approved_by=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (oid,),
    )
    c.commit()


def stats(c: sqlite3.Connection) -> dict[str, int]:
    out = {}
    for key, where in (
        ("total", ""), ("pending", "WHERE payment_status='PAYMENT_PENDING'"),
        ("approved", "WHERE payment_status='PAYMENT_APPROVED'"),
        ("rejected", "WHERE payment_status='PAYMENT_REJECTED'"),
        ("not_paid", "WHERE payment_status='NOT_PAID'"),
    ):
        out[key] = c.execute(f"SELECT COUNT(*) FROM orders {where}").fetchone()[0]
    return out


# ----------------------------- validators ---------------------------------
def parse_full_name(text: str) -> tuple[str, str, str] | None:
    parts = [p for p in (text or "").split() if p]
    if len(parts) < 2:
        return None
    for p in parts:
        if len(p) < 2 or len(p) > 50:
            return None
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return parts[0], parts[1], " ".join(parts[2:])


def normalize_phone(text: str) -> str | None:
    import re
    digits = re.sub(r"\D", "", text or "")
    if digits.startswith("998") and len(digits) == 12:
        return "+" + digits
    if len(digits) == 9:
        return "+998" + digits
    if 9 <= len(digits) <= 15:
        return "+" + digits
    return None


def validate_passport(text: str) -> str | None:
    import re
    v = (text or "").strip().upper().replace(" ", "")
    if re.fullmatch(r"[A-Z]{2}\d{4,9}", v):
        return v
    return None


def validate_metrika(text: str) -> str | None:
    import re
    v = re.sub(r"\s+", " ", (text or "").strip().upper())
    if len(v) < 3 or len(v) > 30:
        return None
    if not re.fullmatch(r"[A-Z0-9\- ]+", v):
        return None
    return v


def validate_dob(text: str) -> date | None:
    try:
        d = datetime.strptime((text or "").strip(), "%d.%m.%Y").date()
    except ValueError:
        return None
    today = date.today()
    age = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    if d > today or age > 120:
        return None
    return d


# ----------------------------- formatting ---------------------------------
def money(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value:,} so'm".replace(",", " ")


def cert_label(o: sqlite3.Row) -> str:
    prices = {1: 5000, 2: 10000}
    t = o["certificate_type"]
    if t not in prices:
        return "-"
    return f"{t}-tur sertifikat — {money(prices[t])}"


def full_name(o: sqlite3.Row) -> str:
    return " ".join(x for x in (o["last_name"], o["first_name"], o["middle_name"]) if x).strip()


def role_label(o: sqlite3.Row) -> str:
    return "O'quvchi" if o["customer_role"] == "student" else "O'qituvchi" if o["customer_role"] == "teacher" else "-"


def doc_label(o: sqlite3.Row) -> str:
    return "Pasport" if o["document_type"] == "passport" else "Metrika" if o["document_type"] == "metrika" else "-"


def fmt_dob(o: sqlite3.Row) -> str:
    v = o["date_of_birth"]
    if not v:
        return "-"
    try:
        return datetime.strptime(v, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return v


def summary(o: sqlite3.Row) -> str:
    return (
        "📋 BUYURTMA MA'LUMOTLARI\n\n"
        f"Sertifikat turi: {cert_label(o)}\n"
        f"Narxi: {money(o['certificate_price'])}\n"
        f"Rol: {role_label(o)}\n"
        f"F.I.Sh: {full_name(o) or '-'}\n"
        f"Hujjat turi: {doc_label(o)}\n"
        f"Hujjat raqami: {o['document_number'] or '-'}\n"
        f"Telefon: {o['phone_number'] or '-'}\n"
        f"Tug'ilgan sana: {fmt_dob(o)}\n\n"
        "Ma'lumotlaringiz to'g'rimi? To'lovga o'tishingiz mumkin."
    )


def admin_order_text(o: sqlite3.Row) -> str:
    return (
        "🔔 YANGI TO'LOV KELDI!\n\n"
        f"👤 Mijoz: {full_name(o) or '-'}\n"
        f"🎓 Rol: {role_label(o)}\n"
        f"📄 Sertifikat turi: {cert_label(o)}\n"
        f"💰 To'lov summasi: {money(o['certificate_price'])}\n"
        f"🪪 Hujjat turi: {doc_label(o)}\n"
        f"🔢 Hujjat raqami: {o['document_number'] or '-'}\n"
        f"📱 Telefon: {o['phone_number'] or '-'}\n"
        f"🎂 Tug'ilgan sana: {fmt_dob(o)}\n"
        f"🆔 Buyurtma ID: {o['id']}\n"
        f"🕒 Yaratilgan: {o['created_at']}\n\n"
        "📸 To'lov cheki quyida."
    )


def full_order_text(o: sqlite3.Row) -> str:
    return (
        f"🆔 Buyurtma ID: {o['id']}\n"
        f"👤 Telegram: {o['telegram_user_id']} (@{o['telegram_username'] or '-'})\n"
        f"F.I.Sh: {full_name(o) or '-'}\n"
        f"Rol: {role_label(o)}\n"
        f"Sertifikat: {cert_label(o)}\n"
        f"Narxi: {money(o['certificate_price'])}\n"
        f"Hujjat: {doc_label(o)} - {o['document_number'] or '-'}\n"
        f"Telefon: {o['phone_number'] or '-'}\n"
        f"Tug'ilgan sana: {fmt_dob(o)}\n"
        f"To'lov holati: {o['payment_status']}\n"
        f"Buyurtma holati: {o['order_status']}\n"
        f"Yaratilgan: {o['created_at']}\n"
        f"Tasdiqlangan: {o['approved_at'] or '-'}\n"
        f"Tasdiqlagan admin: {o['approved_by'] or '-'}"
    )


# ----------------------------- keyboards ----------------------------------
def IKB(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]}


def cert_kb():
    return IKB([
        [("1️⃣ 1-tur — 5 000 so'm", "cert:1")],
        [("2️⃣ 2-tur — 10 000 so'm", "cert:2")],
    ])


def role_kb():
    return IKB([[("👨‍🎓 O'quvchi", "role:student")], [("👨‍🏫 O'qituvchi", "role:teacher")]])


def doc_kb():
    return IKB([[("🪪 Pasport", "doctype:passport")], [("📄 Metrika", "doctype:metrika")]])


def contact_kb():
    return {
        "keyboard": [[{"text": "📱 Telefon raqamni yuborish", "request_contact": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
        "input_field_placeholder": "Telefon raqamingizni kiriting",
    }


NO_KB = {"remove_keyboard": True}


def confirm_kb():
    return IKB([[("✅ Tasdiqlash", "confirm:yes")], [("✏️ Ma'lumotlarni qayta kiritish", "confirm:edit")]])


def pay_kb():
    return IKB([[("💳 To'lov qilish", "pay:show")]])


def paid_kb():
    return IKB([[("✅ To'lov qildim", "pay:done")]])


def restart_kb():
    return IKB([[("🔄 Qayta boshlash", "restart:order")]])


def admin_kb():
    return IKB([
        [("📊 Umumiy statistika", "admin:stats")],
        [("📦 Barcha buyurtmalar", "admin:all")],
        [("⏳ Kutilayotgan to'lovlar", "admin:pending")],
        [("✅ Tasdiqlangan to'lovlar", "admin:approved")],
        [("❌ Rad etilgan to'lovlar", "admin:rejected")],
        [("💳 Karta raqamini o'zgartirish", "admin:set_card")],
        [("👤 Mijoz ma'lumotlari (so'nggi)", "admin:customers")],
        [("🔎 Buyurtma qidirish", "admin:search")],
    ])


def back_kb():
    return IKB([[("⬅️ Admin panel", "admin:menu")]])


def approval_kb(oid: int):
    return IKB([[
        ("✅ TO'LOV TASDIQLANDI", f"admin:approve:{oid}"),
        ("❌ Rad etish", f"admin:reject:{oid}"),
    ]])


# ----------------------------- telegram api -------------------------------
class TelegramAPI:
    TELEGRAM_IPS = ["149.154.166.110", "149.154.167.51", "149.154.167.220"]

    def __init__(self, token: str):
        self.host = "api.telegram.org"
        self.token = token
        try:
            socket.gethostbyname(self.host)
            self.targets = [self.host]
        except OSError:
            # DNS is broken in Termux in some networks: use Telegram IPs directly.
            self.targets = list(self.TELEGRAM_IPS)

    @staticmethod
    def _form_value(v: Any) -> str:
        if isinstance(v, (dict, list)):
            return json.dumps(v, ensure_ascii=False)
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v)

    @staticmethod
    def _part(field: str, filename: str, data: bytes, content_type: str):
        return field, (filename, data, content_type)

    def call(self, method: str, payload: dict | None = None, files: dict | None = None) -> Any:
        payload = payload or {}
        if files:
            boundary = "----PromterBoundary7d1f"
            chunks: list[bytes] = []
            for key, value in payload.items():
                chunks.append(
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
                    + self._form_value(value).encode("utf-8") + b"\r\n"
                )
            for field, (filename, data, content_type) in files.items():
                chunks.append(
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
                    f"Content-Type: {content_type}\r\n\r\n".encode()
                    + data + b"\r\n"
                )
            chunks.append(f"--{boundary}--\r\n".encode())
            body = b"".join(chunks)
            headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        else:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers = {"Content-Type": "application/json"}

        headers["Host"] = self.host
        last_exc: Exception | None = None
        for target in self.targets:
            url = f"https://{target}/bot{self.token}/{method}"
            context = None if target == self.host else ssl._create_unverified_context()
            try:
                req = urllib.request.Request(url, data=body, headers=headers)
                with urllib.request.urlopen(req, timeout=45, context=context) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                if not result.get("ok"):
                    raise RuntimeError(f"Telegram {method}: {result}")
                # remember the working target
                self.targets = [target]
                return result.get("result")
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:500]
                last_exc = RuntimeError(f"Telegram {method} HTTP {exc.code}: {detail}")
                if exc.code in (400, 401, 404):
                    break
            except Exception as exc:
                last_exc = exc
        raise RuntimeError(f"Telegram {method} failed: {last_exc}")

    def get_updates(self, offset: int, timeout: int = 25) -> list[dict]:
        return self.call("getUpdates", {"offset": offset, "timeout": timeout, "allowed_updates": ["message", "callback_query"]})

    def send_message(self, chat_id: int, text: str, markup: dict | None = None, parse_mode: str | None = None):
        p: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if markup:
            p["reply_markup"] = markup
        if parse_mode:
            p["parse_mode"] = parse_mode
        return self.call("sendMessage", p)

    def send_photo_id(self, chat_id: int, file_id: str, caption: str | None = None, markup: dict | None = None):
        p: dict[str, Any] = {"chat_id": chat_id, "photo": file_id}
        if caption:
            p["caption"] = caption
        if markup:
            p["reply_markup"] = markup
        return self.call("sendPhoto", p)

    def send_photo_file(self, chat_id: int, path: Path, caption: str | None = None, markup: dict | None = None):
        suffix = path.suffix.lower()
        ct = "image/png" if suffix == ".png" else "image/webp" if suffix == ".webp" else "image/jpeg"
        files = {"photo": self._part("photo", path.name, path.read_bytes(), ct)}
        p: dict[str, Any] = {"chat_id": chat_id}
        if caption:
            p["caption"] = caption
        if markup:
            p["reply_markup"] = markup
        return self.call("sendPhoto", p, files)

    def send_two_images(self, chat_id: int) -> None:
        paths = [S.image("certificate_type_1"), S.image("certificate_type_2")]
        paths = [p for p in paths if p.exists()]
        if not paths:
            return
        if len(paths) == 1:
            self.send_photo_file(chat_id, paths[0])
            return
        media, files = [], {}
        for i, p in enumerate(paths):
            ct = "image/png" if p.suffix.lower() == ".png" else "image/webp" if p.suffix.lower() == ".webp" else "image/jpeg"
            media.append({"type": "photo", "media": f"attach://file{i}"})
            files[f"file{i}"] = (p.name, p.read_bytes(), ct)
        self.call("sendMediaGroup", {"chat_id": chat_id, "media": json.dumps(media, ensure_ascii=False)}, files)

    def answer_cb(self, cb_id: str, text: str | None = None, alert: bool = False):
        p: dict[str, Any] = {"callback_query_id": cb_id}
        if text:
            p["text"] = text
        if alert:
            p["show_alert"] = True
        return self.call("answerCallbackQuery", p)

    def edit_markup(self, chat_id: int, message_id: int, markup: dict):
        return self.call("editMessageReplyMarkup", {
            "chat_id": chat_id, "message_id": message_id, "reply_markup": markup
        })

    def edit_text(self, chat_id: int, message_id: int, text: str, markup: dict | None = None):
        p: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if markup:
            p["reply_markup"] = markup
        return self.call("editMessageText", p)

    def edit_caption(self, chat_id: int, message_id: int, caption: str, markup: dict | None = None):
        p: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "caption": caption}
        if markup:
            p["reply_markup"] = markup
        return self.call("editMessageCaption", p)

    def edit_smart(self, chat_id: int, message_id: int, text: str, had_caption: bool = False):
        if had_caption:
            try:
                return self.edit_caption(chat_id, message_id, text, IKB([]))
            except Exception:
                pass
        try:
            return self.edit_text(chat_id, message_id, text, IKB([]))
        except Exception:
            return self.edit_caption(chat_id, message_id, text, IKB([]))


API = TelegramAPI(S.bot_token)


# ----------------------------- fsm ----------------------------------------
FSM: dict[int, dict[str, Any]] = {}


def fsm_of(uid: int) -> dict[str, Any]:
    return FSM.setdefault(uid, {"state": None, "data": {}})


def set_state(uid: int, state: str | None, **data: Any) -> None:
    f = fsm_of(uid)
    f["state"] = state
    if data:
        f["data"].update(data)


def clear_state(uid: int) -> None:
    FSM[uid] = {"state": None, "data": {}}


def current_state(uid: int) -> str | None:
    return fsm_of(uid).get("state")


# ----------------------------- messages -----------------------------------
START_TEXT = (
    "Assalomu alaykum! 👋\n\n"
    "Sizda ikkita tanlov bor:\n\n"
    "🥇 1-tur sertifikatlarimiz narxi: 5 000 so'm\n\n"
    "🥈 2-tur sertifikatlarimiz narxi: 10 000 so'm\n\n"
    "Iltimos, sertifikat turini tanlang."
)


# ----------------------------- helpers ------------------------------------
def send_start(chat_id: int, uid: int, username: str | None) -> None:
    clear_state(uid)
    c = conn()
    get_active(c, uid, username)
    c.close()
    try:
        API.send_two_images(chat_id)
    except Exception:
        LOG.exception("Rasmlar yuborilmadi")
        API.send_message(chat_id, "⚠️ Sertifikat namunalari yuborilmadi. Davom etishingiz mumkin.")
    API.send_message(chat_id, START_TEXT, markup=cert_kb())
    set_state(uid, "choosing_certificate")


def is_admin(uid: int) -> bool:
    return uid == S.admin_id


def notify_admin(text: str, file_id: str | None = None, markup: dict | None = None) -> None:
    try:
        if file_id:
            API.send_photo_id(S.admin_id, file_id, caption=text, markup=markup)
        else:
            API.send_message(S.admin_id, text, markup=markup)
    except Exception:
        LOG.exception("Admin ga xabar yuborilmadi")


# ----------------------------- message handlers ---------------------------
def handle_message(msg: dict) -> None:
    uid = msg["from"]["id"]
    chat_id = msg["chat"]["id"]
    username = msg["from"].get("username")
    text = (msg.get("text") or "").strip()
    state = current_state(uid)

    if text.startswith("/start"):
        send_start(chat_id, uid, username)
        return
    if text.startswith("/cancel"):
        clear_state(uid)
        c = conn()
        o = c.execute("SELECT * FROM orders WHERE telegram_user_id=? ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
        if o and o["payment_status"] != "PAYMENT_APPROVED":
            set_status(c, o["id"], "CANCELLED")
        c.close()
        API.send_message(chat_id, "❎ Buyurtma jarayoni bekor qilindi. Yangi buyurtma boshlash uchun /start buyrug'ini yuboring.", markup=restart_kb())
        return
    if text.startswith("/admin"):
        admin_panel(chat_id, uid)
        return

    # Admin FSM
    if is_admin(uid) and state in ("admin_search", "admin_card_number", "admin_card_holder"):
        if state == "admin_search":
            do_search(chat_id, text)
        elif state == "admin_card_number":
            if len(text) < 8:
                API.send_message(chat_id, "Karta raqami juda qisqa. Qayta kiriting.")
                return
            fsm_of(uid)["data"]["new_card"] = text
            set_state(uid, "admin_card_holder")
            API.send_message(chat_id, "Karta egasining ismini kiriting:")
        elif state == "admin_card_holder":
            if len(text) < 3:
                API.send_message(chat_id, "Ma'lumot noto'g'ri. /admin orqali qayta urinib ko'ring.")
                clear_state(uid)
                return
            S.card_number = fsm_of(uid)["data"].get("new_card", S.card_number)
            S.card_holder = text
            clear_state(uid)
            API.send_message(chat_id, "✅ Karta ma'lumotlari yangilandi (runtime). Doimiy saqlash uchun .env faylini ham yangilang.", markup=admin_kb())
        return

    if state == "entering_full_name":
        parsed = parse_full_name(text)
        if not parsed:
            API.send_message(chat_id, "❗ F.I.Sh noto'g'ri kiritildi. Kamida ism va familiyangizni kiriting.")
            return
        first, last, middle = parsed
        c = conn(); o = get_active(c, uid, username)
        update_fields(c, o["id"], first_name=first, last_name=last, middle_name=middle)
        c.close()
        API.send_message(chat_id, "Pasport yoki metrika ma'lumotlaringizni kiriting.\n\nPasport bo'lsa: AE****\n\nMetrika bo'lsa: I-FR ***", markup=doc_kb())
        set_state(uid, "choosing_document_type")
        return

    if state == "entering_document_number":
        dtype = fsm_of(uid)["data"].get("document_type")
        value = validate_passport(text) if dtype == "passport" else validate_metrika(text)
        if not value:
            example = "AE1234567" if dtype == "passport" else "I-FR 123456"
            API.send_message(chat_id, f"❗ Hujjat raqami noto'g'ri formatda. Masalan: {example}. Qayta kiriting.")
            return
        c = conn(); o = get_active(c, uid, username)
        update_fields(c, o["id"], document_number=value)
        c.close()
        API.send_message(chat_id, "Telefon raqamingizni kiriting.", markup=contact_kb())
        set_state(uid, "entering_phone")
        return

    if state == "entering_phone":
        contact = msg.get("contact")
        raw = contact.get("phone_number") if contact else text
        phone = normalize_phone(raw or "")
        if not phone:
            API.send_message(chat_id, "❗ Telefon raqami noto'g'ri. Masalan: +998901234567 yoki 901234567. Qayta kiriting.")
            return
        c = conn(); o = get_active(c, uid, username)
        update_fields(c, o["id"], phone_number=phone)
        c.close()
        API.send_message(chat_id, "Tug'ilgan kuningizni kiriting.\n\nFormat: DD.MM.YYYY", markup=NO_KB)
        set_state(uid, "entering_dob")
        return

    if state == "entering_dob":
        dob = validate_dob(text)
        if not dob:
            API.send_message(chat_id, "❗ Sana noto'g'ri. DD.MM.YYYY formatida kiriting (masalan: 01.01.2005).")
            return
        c = conn(); o = get_active(c, uid, username)
        update_fields(c, o["id"], date_of_birth=dob.isoformat())
        set_status(c, o["id"], "AWAITING_CONFIRMATION")
        o = row(c, o["id"])
        c.close()
        API.send_message(chat_id, summary(o), markup=confirm_kb())
        set_state(uid, "confirming")
        return

    if state == "awaiting_screenshot":
        photo = msg.get("photo")
        doc = msg.get("document")
        file_id = None
        if photo:
            file_id = photo[-1]["file_id"]
        elif doc and (doc.get("mime_type") or "").lower().startswith("image/"):
            file_id = doc["file_id"]
        if not file_id:
            API.send_message(chat_id, "📸 Iltimos, to'lov chekini rasm (screenshot) ko'rinishida yuboring.")
            return
        handle_screenshot(uid, chat_id, username, file_id)
        return

    if state in ("choosing_role", "choosing_document_type", "confirming"):
        API.send_message(chat_id, "Iltimos, yuqoridagi tugmalardan birini tanlang.")
        return
    if state == "awaiting_payment_click":
        API.send_message(chat_id, "Iltimos, avval \"💳 To'lov qilish\" tugmasidan foydalaning.", markup=pay_kb())
        return

    API.send_message(chat_id, "Kechirasiz, xabar tushunilmadi. Buyurtmani boshlash uchun /start, bekor qilish uchun /cancel yuboring.")


def handle_screenshot(uid: int, chat_id: int, username: str | None, file_id: str) -> None:
    c = conn(); o = get_active(c, uid, username)
    if not o["certificate_type"] or not o["phone_number"] or not o["document_number"]:
        API.send_message(chat_id, "Buyurtma ma'lumotlari to'liq emas. /start bilan qayta boshlang.")
        c.close(); return
    if o["payment_status"] == "PAYMENT_APPROVED":
        API.send_message(chat_id, "Bu buyurtma uchun to'lov allaqachon tasdiqlangan.")
        c.close(); return
    update_fields(c, o["id"], payment_screenshot_file_id=file_id)
    set_status(c, o["id"], "PAYMENT_PENDING", "PAYMENT_PENDING")
    o = row(c, o["id"])
    c.close()
    API.send_message(chat_id, "✅ To'lov cheki qabul qilindi. Administrator tekshiruvdan so'ng tasdiqlaydi. Iltimos, kuting.")
    notify_admin(admin_order_text(o), file_id, approval_kb(o["id"]))
    clear_state(uid)


# ----------------------------- callback handlers --------------------------
def handle_callback(cb: dict) -> None:
    cb_id = cb["id"]
    uid = cb["from"]["id"]
    data = cb.get("data") or ""
    msg = cb.get("message") or {}
    chat_id = msg.get("chat", {}).get("id", uid)
    message_id = msg.get("message_id")
    had_caption = "caption" in msg
    username = cb["from"].get("username")

    try:
        API.answer_cb(cb_id)
    except Exception:
        pass

    if data == "restart:order":
        send_start(chat_id, uid, username)
        return

    if data.startswith("cert:"):
        cert = int(data.split(":")[1])
        if cert not in (1, 2):
            return
        price = 5000 if cert == 1 else 10000
        c = conn(); o = get_active(c, uid, username)
        if o["certificate_type"] is not None and o["order_status"] not in ("DRAFT", "PAYMENT_REJECTED"):
            c.close()
            try: API.answer_cb(cb_id, "Sertifikat turi allaqachon tanlangan. /start yuboring.", True)
            except Exception: pass
            return
        update_fields(c, o["id"], certificate_type=cert, certificate_price=price)
        set_status(c, o["id"], "DRAFT")
        c.close()
        remove_markup(chat_id, message_id)
        API.send_message(chat_id, "Siz kim bo'lib faoliyat yuritasiz?", markup=role_kb())
        set_state(uid, "choosing_role")
        return

    if data.startswith("role:"):
        role = data.split(":")[1]
        if role not in ("student", "teacher"):
            return
        c = conn(); o = get_active(c, uid, username)
        update_fields(c, o["id"], customer_role=role)
        c.close()
        remove_markup(chat_id, message_id)
        API.send_message(chat_id, "Iltimos, Ism, Familiya va Sharifingizni kiriting.", markup=NO_KB)
        set_state(uid, "entering_full_name")
        return

    if data.startswith("doctype:"):
        dtype = data.split(":")[1]
        if dtype not in ("passport", "metrika"):
            return
        c = conn(); o = get_active(c, uid, username)
        update_fields(c, o["id"], document_type=dtype, document_number=None)
        c.close()
        prompt = "Iltimos, pasport raqamingizni kiriting (masalan: AE1234567)." if dtype == "passport" else "Iltimos, metrika raqamingizni kiriting (masalan: I-FR 123456)."
        remove_markup(chat_id, message_id)
        API.send_message(chat_id, prompt)
        fsm_of(uid)["data"]["document_type"] = dtype
        set_state(uid, "entering_document_number")
        return

    if data == "confirm:edit":
        c = conn(); o = get_active(c, uid, username)
        update_fields(c, o["id"], customer_role=None, first_name=None, last_name=None, middle_name=None,
                      document_type=None, document_number=None, phone_number=None, date_of_birth=None)
        c.close()
        remove_markup(chat_id, message_id)
        API.send_message(chat_id, "Siz kim bo'lib faoliyat yuritasiz?", markup=role_kb())
        set_state(uid, "choosing_role")
        return

    if data == "confirm:yes":
        c = conn(); o = get_active(c, uid, username)
        needed = ["certificate_type", "certificate_price", "customer_role", "first_name", "last_name",
                  "document_type", "document_number", "phone_number", "date_of_birth"]
        if any(o[k] is None or o[k] == "" for k in needed):
            c.close()
            API.send_message(chat_id, "Ma'lumotlar to'liq emas. Iltimos, qayta kiriting.", markup=role_kb())
            set_state(uid, "choosing_role")
            return
        set_status(c, o["id"], "AWAITING_PAYMENT")
        c.close()
        remove_markup(chat_id, message_id)
        API.send_message(
            chat_id,
            "💳 To'lovni amalga oshirish uchun quyidagi tugmani bosing.\n\nTo'lovni amalga oshirgach, to'lov chekini (screenshot) botga yuboring.",
            markup=pay_kb(),
        )
        set_state(uid, "awaiting_payment_click")
        return

    if data == "pay:show":
        c = conn(); o = get_active(c, uid, username)
        if not o["certificate_price"]:
            c.close(); return
        set_status(c, o["id"], "AWAITING_PAYMENT")
        c.close()
        API.send_message(
            chat_id,
            "💳 TO'LOV MA'LUMOTLARI\n\n"
            f"Karta raqami: <code>{S.card_number}</code>\n\n"
            f"Karta egasi: {S.card_holder}\n\n"
            f"To'lov summasi: {money(o['certificate_price'])}\n\n"
            "To'lovni amalga oshirgach, quyidagi tugmani bosing.",
            markup=paid_kb(),
            parse_mode="HTML",
        )
        set_state(uid, "awaiting_payment_click")
        return

    if data == "pay:done":
        c = conn(); o = get_active(c, uid, username)
        c.close()
        remove_markup(chat_id, message_id)
        API.send_message(chat_id, "📸 Iltimos, to'lov amalga oshirilganligini tasdiqlovchi screenshot yuboring.")
        set_state(uid, "awaiting_screenshot")
        return

    # admin actions
    if data.startswith("admin:"):
        handle_admin_callback(cb, uid, chat_id, message_id, data, had_caption)
        return


def remove_markup(chat_id: int, message_id: int) -> None:
    try:
        API.edit_markup(chat_id, message_id, IKB([]))
    except Exception:
        pass


# ----------------------------- admin --------------------------------------
def admin_panel(chat_id: int, uid: int) -> None:
    if not is_admin(uid):
        API.send_message(chat_id, "⛔ Sizda administrator huquqi yo'q.")
        return
    clear_state(uid)
    API.send_message(chat_id, "🛠 Admin panel", markup=admin_kb())


def do_search(chat_id: int, query: str) -> None:
    q = query.strip()
    c = conn()
    if q.isdigit():
        rows = c.execute("SELECT * FROM orders WHERE id=? OR phone_number LIKE ? ORDER BY id DESC LIMIT 10", (int(q), f"%{q}%")).fetchall()
    else:
        like = f"%{q}%"
        rows = c.execute(
            "SELECT * FROM orders WHERE phone_number LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR document_number LIKE ? ORDER BY id DESC LIMIT 10",
            (like, like, like, like),
        ).fetchall()
    c.close()
    if not rows:
        API.send_message(chat_id, "Natija topilmadi.", markup=admin_kb())
        return
    for o in rows:
        API.send_message(chat_id, full_order_text(o))
        if o["payment_screenshot_file_id"]:
            try:
                API.send_photo_id(chat_id, o["payment_screenshot_file_id"], caption=f"📸 Chek (Buyurtma #{o['id']})")
            except Exception:
                LOG.exception("Chek yuborilmadi")
    API.send_message(chat_id, "Qidiruv yakunlandi.", markup=admin_kb())


def send_order_list(chat_id: int, title: str, where: str = "") -> None:
    c = conn()
    rows = c.execute(f"SELECT * FROM orders {where} ORDER BY id DESC LIMIT 20").fetchall()
    c.close()
    if not rows:
        API.send_message(chat_id, f"{title}\n\nBuyurtmalar topilmadi.", markup=back_kb())
        return
    lines = [title, ""]
    for o in rows:
        lines.append(f"🆔 #{o['id']} | {full_name(o) or '-'} | {cert_label(o)} | {money(o['certificate_price'])} | {o['payment_status']}")
    lines.append("\nBatafsil: 🔎 Buyurtma qidirish")
    API.send_message(chat_id, "\n".join(lines), markup=back_kb())


def handle_admin_callback(cb: dict, uid: int, chat_id: int, message_id: int, data: str, had_caption: bool) -> None:
    if not is_admin(uid):
        try: API.answer_cb(cb["id"], "Ruxsat yo'q", True)
        except Exception: pass
        return

    if data == "admin:menu":
        clear_state(uid)
        try: API.edit_text(chat_id, message_id, "🛠 Admin panel", admin_kb())
        except Exception: API.send_message(chat_id, "🛠 Admin panel", markup=admin_kb())
        return

    if data == "admin:stats":
        c = conn(); st = stats(c); c.close()
        API.send_message(
            chat_id,
            "📊 Umumiy statistika\n\n"
            f"Jami buyurtmalar: {st['total']}\n"
            f"⏳ Kutilayotgan: {st['pending']}\n"
            f"✅ Tasdiqlangan: {st['approved']}\n"
            f"❌ Rad etilgan: {st['rejected']}\n"
            f"💤 To'lanmagan: {st['not_paid']}",
            markup=back_kb(),
        )
        return

    lists = {
        "admin:all": ("📦 Barcha buyurtmalar (so'nggi 20):", ""),
        "admin:pending": ("⏳ Kutilayotgan to'lovlar:", "WHERE payment_status='PAYMENT_PENDING'"),
        "admin:approved": ("✅ Tasdiqlangan to'lovlar:", "WHERE payment_status='PAYMENT_APPROVED'"),
        "admin:rejected": ("❌ Rad etilgan to'lovlar:", "WHERE payment_status='PAYMENT_REJECTED'"),
    }
    if data in lists:
        send_order_list(chat_id, *lists[data])
        return

    if data == "admin:customers":
        c = conn(); rows = c.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 10").fetchall(); c.close()
        if not rows:
            API.send_message(chat_id, "👤 Mijoz ma'lumotlari topilmadi.", markup=back_kb())
            return
        text = "\n\n".join(full_order_text(o) for o in rows)
        if len(text) > 3500:
            text = text[:3500] + "\n..."
        API.send_message(chat_id, text, markup=back_kb())
        return

    if data == "admin:search":
        set_state(uid, "admin_search")
        API.send_message(chat_id, "🔎 Qidirish uchun buyurtma ID yoki telefon raqamini kiriting:", markup=back_kb())
        return

    if data == "admin:set_card":
        set_state(uid, "admin_card_number")
        API.send_message(chat_id, "💳 Yangi karta raqamini kiriting:", markup=back_kb())
        return

    if data.startswith("admin:approve:"):
        oid = int(data.split(":")[-1])
        c = conn(); o, changed = approve(c, oid, uid); c.close()
        if not o:
            try: API.answer_cb(cb["id"], "Buyurtma topilmadi", True)
            except Exception: pass
            return
        if not changed:
            try: API.answer_cb(cb["id"], "⚠️ Ushbu to'lov avval tasdiqlangan.", True)
            except Exception: pass
            remove_markup(chat_id, message_id)
            return
        API.send_message(
            o["telegram_user_id"],
            "✅ TO'LOVINGIZ TASDIQLANDI!\n\n"
            "Hurmatli mijoz, to'lovingiz muvaffaqiyatli tasdiqlandi.\n\n"
            "🎓 Sertifikatingiz adminlar tomonidan 48 soat ichida tayyorlanib, sizga yuboriladi.\n\n"
            "Sertifikatingizni olish uchun hoziroq @Aisertificate adminga yozing.\n\n"
            "Bizning xizmatimizdan foydalanganingiz uchun rahmat! ❤️",
        )
        base = msg_caption_or_text(cb)
        try:
            API.edit_smart(chat_id, message_id, base + f"\n\n✅ TO'LOV TASDIQLANGAN\nTasdiqlagan admin: {uid}", had_caption)
        except Exception:
            LOG.exception("Admin xabari tahrirlanmadi")
            remove_markup(chat_id, message_id)
        return

    if data.startswith("admin:reject:"):
        oid = int(data.split(":")[-1])
        c = conn(); o = row(c, oid)
        if not o or o["payment_status"] == "PAYMENT_APPROVED":
            c.close()
            try: API.answer_cb(cb["id"], "Bu to'lov allaqachon tasdiqlangan.", True)
            except Exception: pass
            return
        reject(c, oid); c.close()
        API.send_message(
            o["telegram_user_id"],
            "❌ To'lovingiz tasdiqlanmadi.\n\nIltimos, to'lov chekini tekshirib, yangi screenshotni qayta yuboring.",
            markup=restart_kb(),
        )
        base = msg_caption_or_text(cb)
        try:
            API.edit_smart(chat_id, message_id, base + f"\n\n❌ TO'LOV RAD ETILDI\nAdmin ID: {uid}", had_caption)
        except Exception:
            LOG.exception("Admin xabari tahrirlanmadi")
            remove_markup(chat_id, message_id)
        return


def msg_caption_or_text(cb: dict) -> str:
    msg = cb.get("message") or {}
    return msg.get("caption") or msg.get("text") or ""


# ----------------------------- main loop ----------------------------------
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    init_db()
    LOG.info("DB tayyor: %s", S.db_path)
    LOG.info("Bot ishga tushdi (stdlib offline mode)")
    offset = 0
    while True:
        try:
            updates = API.get_updates(offset, timeout=25)
            for upd in updates:
                offset = max(offset, upd["update_id"] + 1)
                try:
                    if "callback_query" in upd:
                        handle_callback(upd["callback_query"])
                    elif "message" in upd:
                        handle_message(upd["message"])
                except Exception:
                    LOG.exception("Update ishlashda xatolik")
        except KeyboardInterrupt:
            LOG.info("To'xtatildi")
            break
        except Exception:
            LOG.exception("Polling xatoligi; 3 soniyadan keyin qayta urinaman")
            time.sleep(3)


if __name__ == "__main__":
    main()
