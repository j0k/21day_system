"""Конфигурация бота.

Читает переменные окружения и (если есть) файл ``.env`` рядом с ``bot.py``.

* ``TELEGRAM_BOT_TOKEN`` — обязателен для запуска бота.
* ``OPENAI_API_KEY`` и компания — необязательны: без ключа бот работает
  в офлайн-режиме (советы по правилам, без обращений к сети).
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """Минимальный парсер .env (KEY=VALUE), без внешних зависимостей."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(),
                             value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")

# --- Telegram -------------------------------------------------------------
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
POLL_TIMEOUT: int = int(os.environ.get("POLL_TIMEOUT", "30"))

# --- LLM (OpenAI-совместимый API) — необязательно --------------------------
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL: str = os.environ.get(
    "OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()

# --- Хранилище ------------------------------------------------------------
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data")))
STATE_FILE = DATA_DIR / "state.json"
LOG_FILE = DATA_DIR / "progress.log"

# Бот умеет работать и без API-ключа.
LLM_ENABLED: bool = bool(OPENAI_API_KEY)
