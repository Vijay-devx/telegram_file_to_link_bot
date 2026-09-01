#!/bin/bash
# Start the Telegram bot in the background
python bot.py &
# Start the FastAPI web server in the foreground
uvicorn web:app --host 0.0.0.0 --port $PORT
