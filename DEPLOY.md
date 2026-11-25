# Serverga joylash (Ubuntu / Debian)

Bot uzoq so'rov (long polling) bilan ishga tushadi, shuning uchun **doimiy ishlaydigan VM** kerak.
`bot_offline.py` faqat Python standart kutubxonasi bilan ishlaydi — `pip`, `venv`, `aiogram` kerak emas.

## 1. Server talablari

- Ubuntu 22.04 yoki 24.04 (Python 3.10+)
- 1 GB RAM ham yetarli (bot ~30-50 MB ishlatadi)
- 10 GB disk (asosan `bot.db` va log uchun)
- Chiqish (outbound) internet — Telegram API ga
- Kirish porti ochish shart emas (webhook yo'q)

## 2. Fayllarni yuklash

```bash
sudo mkdir -p /opt/promter
cd /opt/promter
# fayllarni bu yerga yuklang: bot_offline.py, .env, assets/
sudo nano .env   # tekshiring: BOT_TOKEN, ADMIN_TELEGRAM_ID, BANK_*
```

Tezkor sinov:

```bash
python3 bot_offline.py
```

`DB tayyor: /opt/promter/bot.db` va `Bot ishga tushdi` chiqishi kerak. `Ctrl+C` bilan to'xtating.

## 3. systemd xizmati (24/7 avtomatik qayta ishga tushadi)

```bash
sudo tee /etc/systemd/system/promter.service > /dev/null <<'EOF'
[Unit]
Description=5 Million Promter Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/promter
ExecStart=/usr/bin/python3 /opt/promter/bot_offline.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now promter
```

Tekshirish:

```bash
sudo systemctl status promter
sudo journalctl -u promter -f
```

Boshqarish:

```bash
sudo systemctl restart promter
sudo systemctl stop promter
```

## 4. Ma'lumotlar bazasini zaxiralash (kunlik)

```bash
sudo crontab -e
```

Qo'shing (har kuni soat 03:00 da, 14 kun saqlanadi):

```cron
0 3 * * * cp /opt/promter/bot.db /opt/promter/backups/bot_$(date +\%Y\%m\%d).db && find /opt/promter/backups -name 'bot_*.db' -mtime +14 -delete
```

Oldin papka yaratish:

```bash
sudo mkdir -p /opt/promter/backups
```

## 5. Eslatma

- Proxy/firewall bo'lsa, `api.telegram.org:443` ga chiqishga ruxsat bering.
- Agar serverda DNS ishlamasa, bot avtomatik Telegram IP lariga o'tadi.
- `.env` ichidagi token — maxfiy, uni git yoki ochiq joyga yuklamang.
