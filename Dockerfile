# =========================
# Telegram Bot Dockerfile
# =========================

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY bot.py README.md ./

# Copy replies.json if present (to preserve saved replies)
COPY replies.json ./ || true

# Install dependencies
RUN pip install --no-cache-dir python-telegram-bot==20.8

# Environment variables
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["python", "bot.py"]
