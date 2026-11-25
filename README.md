# 5-Million-Promter-Bot

A minimal Telegram bot built with aiogram 3. It runs in long-polling mode as a worker, so it has no HTTP port or healthcheck.

## Setup

1. Create a bot with @BotFather in Telegram and copy the token.
2. In the Railway service, open Variables and set `BOT_TOKEN` to that token.
3. Deploy. Railway builds the app with Railpack and starts it with `python main.py`.

Never commit the token to the repository.

## Local development

```
pip install -r requirements.txt
BOT_TOKEN=your-token python main.py
```
