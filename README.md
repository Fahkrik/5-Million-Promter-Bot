# 5 Million Promter / Dasturchi — Telegram Certificate Ordering Bot

Production-oriented Telegram bot for automating certificate orders, collecting customer data, receiving payment screenshots, notifying an administrator, and supporting manual payment approval/rejection.

> **Termux (Android) uchun muhim:** `bot_offline.py` — faqat Python standart kutubxonasi bilan ishlaydigan to'liq versiya. Unga **pip, internet, aiogram yoki SQLAlchemy kerak emas**. Telefonda faqat `bash termux_bg.sh` yoki `python bot_offline.py` yozasiz. Asl `bot.py` (aiogram + SQLAlchemy) kompyuter/VPS uchun saqlanib qolindi.

## Features

- `/start` flow with certificate selection (1-tur 5 000 so'm, 2-tur 10 000 so'm)
- FSM-based registration: role, full name, passport/metrika, phone (contact or manual), date of birth, confirmation summary
- Payment flow: configurable bank card details, "To'lov qildim", screenshot upload (photo or image document)
- Admin notification with order details, payment screenshot, and inline approval/rejection buttons
- Manual payment approval and rejection with customer notifications
- `/admin` private panel: statistics, all/pending/approved/rejected orders, recent customers, order search, runtime card update
- SQLite by default with SQLAlchemy 2.x sync sessions executed safely in worker threads (PostgreSQL-ready URL conversion; no `greenlet`/`aiosqlite` needed, Termux-friendly)
- Input validation, error handling, logging, persistent order storage, restart-safe data
- Basic privacy/security safeguards: admin authorization checks, secrets via `.env`, no hardcoded credentials, sensitive-data logging avoided

## Tech Stack

- Python 3.11+
- Aiogram 3.x
- SQLite (default) / PostgreSQL-ready
- SQLAlchemy 2.x (sync session + `asyncio.to_thread` adapter)
- FSM (aiogram)
- python-dotenv
- Logging

## Project Structure

```text
5_million_promter/
├── bot.py
├── config.py
├── database/
│   ├── __init__.py
│   ├── database.py
│   ├── models.py
│   └── operations.py
├── handlers/
│   ├── __init__.py
│   ├── start.py
│   ├── registration.py
│   ├── payment.py
│   └── admin.py
├── keyboards/
│   ├── __init__.py
│   ├── user_keyboards.py
│   └── admin_keyboards.py
├── states/
│   ├── __init__.py
│   └── order_states.py
├── services/
│   ├── __init__.py
│   ├── order_service.py
│   └── notification_service.py
├── middlewares/
│   ├── __init__.py
│   └── admin_middleware.py
├── utils/
│   ├── __init__.py
│   ├── validators.py
│   └── logger.py
├── assets/
│   ├── certificate_type_1.jpg
│   └── certificate_type_2.jpg
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Prerequisites

- Python 3.11 or newer
- Telegram account
- A bot token from [@BotFather](https://t.me/BotFather)
- Your Telegram numeric user ID (admin). You can get it from bots like [@userinfobot](https://t.me/userinfobot)

## 1. Create a Telegram bot with BotFather

1. Open Telegram and start chat with **@BotFather**.
2. Send `/newbot`.
3. Enter bot name, e.g. `5 Million Promter / Dasturchi`.
4. Enter a unique username ending with `bot`.
5. BotFather will give you a **HTTP API token** (BOT_TOKEN). Keep it secret.

## 2. Configure environment variables

1. Copy `.env.example` to `.env`:
   - **Windows (PowerShell):** `Copy-Item .env.example .env`
   - **Linux/macOS:** `cp .env.example .env`
2. Open `.env` and fill in values:

```env
BOT_TOKEN=123456789:AA...your_token...
ADMIN_TELEGRAM_ID=123456789
BANK_CARD_NUMBER=8600 1234 5678 9012
BANK_CARDHOLDER=ISM FAMILIYA
DATABASE_URL=sqlite:///bot.db
LOG_LEVEL=INFO
DATA_RETENTION_DAYS=365
```

- `BOT_TOKEN`: token from BotFather
- `ADMIN_TELEGRAM_ID`: your personal Telegram numeric ID (only this user can access `/admin` and approve/reject)
- `BANK_CARD_NUMBER` / `BANK_CARDHOLDER`: shown to customers at payment step
- `DATABASE_URL`: default SQLite file `bot.db` in project root (path is resolved absolutely automatically). For PostgreSQL later, use e.g. `postgresql://user:pass@host:5432/dbname` and install `psycopg2-binary` (sync driver) separately
- `DATA_RETENTION_DAYS`: configurable policy value for your operational processes (automatic purge job not included; use for manual/admin policy)

> The admin panel also allows changing card number/holder **at runtime** for the current bot process. For permanent changes, update `.env` and restart.

## 3. Add certificate images

Replace placeholder images in `assets/` with your real certificate samples (JPG/PNG/WebP):

- `assets/certificate_type_1.png` (or `.jpg` / `.jpeg` / `.webp`)
- `assets/certificate_type_2.png` (or `.jpg` / `.jpeg` / `.webp`)

The bot auto-detects the extension. Keep the base filenames `certificate_type_1` and `certificate_type_2`.

## 4. Install dependencies

### Windows (PowerShell)

```powershell
cd "C:\path\to\5_million_promter"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If script execution is blocked, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

### Linux / VPS (Ubuntu/Debian example)

```bash
cd /path/to/5_million_promter
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4a. VS Code (Windows) — eng oson ishga tushirish

Hech qanday `pip` yoki virtual environment kerak emas. Botning asosiy versiyasi `bot_offline.py` bo'lib, u **faqat Python standart kutubxonasi** bilan ishlaydi.

1. VS Code da papkani oching: `C:\Project's\5 Million Promter`
2. `.env` fayli borligiga ishonch hosil qiling (token/admin/karta allaqachon to'ldirilgan).
3. **`F5`** bosing yoki yuqori o'ngdagi **▶ Run** tugmasini bosing.
4. Konfiguratsiya tanlash so'ralsa: **「▶ Run Bot (offline, tavsiya)」** ni tanlang.

Terminalda bunday chiqishi kerak:

```text
DB tayyor: bot.db
Bot ishga tushdi (stdlib offline mode)
```

Boshqa usullar:

```powershell
python main.py
python bot_offline.py
```

`.vscode/launch.json` ichida ikkinchi konfiguratsiya ham bor — **「Run Bot (aiogram, PC)」**. U faqat `aiogram`, `SQLAlchemy` va `python-dotenv` o'rnatilgan bo'lsa ishlaydi (`pip install -r requirements.txt`). Termux/telefon uchun faqat offline versiyadan foydalaning.

## 4b. Termux (Android) — OFFLINE o'rnatish (tavsiya etiladi)

Termux uchun `bot_offline.py` ishlatiladi. U **faqat Python standart kutubxonasi** bilan ishlaydi: na `pip`, na internet, na `aiogram`/`SQLAlchemy` kerak. Shu sabab `pypi.org` yoki Termux repository muammolari butunlay yo'q.

```bash
cd ~/5_million_promter
bash termux_setup.sh
```

Skript faqat Python borligini, `.env` va rasmlar borligini tekshiradi — hech narsa yuklamaydi.

Agar `.env` hali to'g'ri to'ldirilmagan bo'lsa:
```bash
nano .env
```

Agar skript `^M` / `\r` xatoligi bersa (Windows'dan ko'chirilganda):
```bash
sed -i 's/\r$//' termux_*.sh
bash termux_setup.sh
```

Loyihani Termuxga ko'chirish: ZIP ni telefonga olib, `unzip 5_million_promter_termux.zip` qiling.

## 5. Run the bot

### VS Code (tavsiya)
`F5` → **「▶ Run Bot (offline, tavsiya)」** yoki terminalda `python main.py`.

### Termux (oldinga chiqarib)
```bash
cd ~/5_million_promter
bash termux_start.sh
```

### Termux (fon rejimida / tavsiya etiladi)
```bash
cd ~/5_million_promter
bash termux_bg.sh
```

`termux_bg.sh` avval tmux bor-yo'qligini tekshiradi:
- **tmux bor** → `tmux new-session -d -s promter` bilan ishga tushiradi
- **tmux yo'q** → avtomatik `termux_nohup.sh` ga o'tadi (tmux umuman kerak emas)

To'g'ridan-to'g'ri tmux'siz ishga tushirish:
```bash
bash termux_nohup.sh
```

Loglarni ko'rish:
```bash
tmux attach -t promter   # tmux ishlatilgan bo'lsa
tail -f bot.log          # nohup ishlatilgan bo'lsa
```
Logdan chiqib, fon rejimda qoldirish: `Ctrl+C` (bot to'xtamaydi)

To'xtatish:
```bash
bash termux_stop.sh        # tmux uchun
bash termux_stop_nohup.sh  # nohup uchun
```

> `termux-wake-lock` batareya optimallashtirish tufayli botning to'xtab qolishining oldini oladi. Shuningdek Termux sozlamalarida **Battery optimization → Don't optimize** qiling.

### Windows

```powershell
cd "C:\path\to\5_million_promter"
.\.venv\Scripts\Activate.ps1
python bot.py
```

### Linux

```bash
cd /path/to/5_million_promter
source .venv/bin/activate
python bot.py
```

The bot uses long polling. Stop with `Ctrl+C`.

## 6. Deploy on a Linux VPS (systemd)

1. Copy project to server (e.g. `/opt/5_million_promter`) and configure `.env`.
2. Create virtualenv and install dependencies as above.
3. Create systemd service `/etc/systemd/system/5million-promter.service`:

```ini
[Unit]
Description=5 Million Promter Telegram Bot
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/opt/5_million_promter
Environment="PATH=/opt/5_million_promter/.venv/bin"
ExecStart=/opt/5_million_promter/.venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

4. Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable 5million-promter
sudo systemctl start 5million-promter
sudo systemctl status 5million-promter
```

5. View logs:

```bash
journalctl -u 5million-promter -f
```

## Usage

### User commands
- `/start` — start/restart order flow
- `/cancel` — cancel current flow (incomplete/active non-approved order)

### Admin commands
- `/admin` — open admin panel (authorized admin only)

## Database

- Tables are created automatically on startup (`init_models`).
- Default DB file: `bot.db` (SQLite). Stored in project root when using default URL.
- Order data, statuses, and screenshot `file_id` are persisted across restarts.
- For PostgreSQL migration, point `DATABASE_URL` to PostgreSQL and install `psycopg2-binary` in your environment. The DB layer uses SQLAlchemy sync sessions executed in worker threads, so no `greenlet`/`aiosqlite` is needed (important for Termux compatibility).

## Security & Privacy Notes

- Never commit `.env` (included in `.gitignore`).
- Restrict admin actions by `ADMIN_TELEGRAM_ID`; callbacks are checked server-side.
- Personal data (passport/metrika, phone, DOB) is stored for order processing; avoid sharing DB/backups.
- Logging avoids printing sensitive document/phone values.
- Payment verification is **manual** by admin; screenshots are not proof of successful transfer.
- Customers are informed about data collection purpose at start. For deletion requests, handle via admin/business process per applicable requirements.

## Testing Checklist

- `/start` shows images and certificate buttons
- Both certificate types/prices selectable
- Role selection (student/teacher)
- Full name, passport/metrika validation
- Contact share and manual phone
- DOB validation
- Confirmation summary and edit/restart
- Payment info shows configured card and amount
- Screenshot upload (photo/image document) and admin notification
- Admin approval updates DB and notifies customer
- Admin rejection updates DB and asks for new screenshot
- Unauthorized admin access blocked
- Duplicate approval prevented
- Data persists after bot restart

## Troubleshooting

- **Termuxda `pypi.org` / mirror xatoligi:** `pip` ishlatma ang — `bot_offline.py` va `termux_*.sh` skriptlari bilan ishga tushiring. Ular internet va kutubxona talab qilmaydi.
- **Bot doesn't start:** verify `BOT_TOKEN` and `ADMIN_TELEGRAM_ID` in `.env`.
- **Images not sent:** ensure `assets/certificate_type_1.jpg` and `assets/certificate_type_2.jpg` exist and are valid.
- **Admin not receiving notifications:** confirm `ADMIN_TELEGRAM_ID` is correct and admin has started chat with the bot.
- **DB errors on PostgreSQL:** install `psycopg2-binary` and verify connection string/permissions.

## License / Notes

This project is delivered as a complete implementation template for "5 Million Promter / Dasturchi". Review and adapt data-retention, legal notices, and operational policies to your business and jurisdiction requirements before production use.
