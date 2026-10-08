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
# Имя ключа может быть провайдер-специфичным: OPENAI_API_KEY, ROUTERAI_API_KEY,
# LLM_API_KEY (берётся первое заданное). Работает и через .env, и через
# переменные окружения Windows. Если задан ROUTERAI_API_KEY, Base URL по
# умолчанию — RouterAI.
def _first_env(*names: str, default: str = "") -> str:
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return default


OPENAI_API_KEY: str = _first_env("OPENAI_API_KEY", "ROUTERAI_API_KEY",
                                 "LLM_API_KEY")
# Имя ключа, которое сработало (для понятного сообщения при запуске).
LLM_KEY_NAME: str = next(
    (n for n in ("OPENAI_API_KEY", "ROUTERAI_API_KEY", "LLM_API_KEY")
     if os.environ.get(n, "").strip()), "")

# Базовый URL: явное переопределение, иначе — по имени ключа.
_default_base = {
    "OPENAI_API_KEY": "https://api.openai.com/v1",
    "ROUTERAI_API_KEY": "https://routerai.ru/api/v1",
}.get(LLM_KEY_NAME, "https://api.openai.com/v1")
OPENAI_BASE_URL: str = _first_env(
    "OPENAI_BASE_URL", "ROUTERAI_BASE_URL", "LLM_BASE_URL",
    default=_default_base).rstrip("/")

# Модель по умолчанию: для RouterAI нужен префикс провайдера.
_default_model = ("openai/gpt-4o-mini" if LLM_KEY_NAME == "ROUTERAI_API_KEY"
                  else "gpt-4o-mini")
OPENAI_MODEL: str = _first_env("OPENAI_MODEL", "ROUTERAI_MODEL", "LLM_MODEL",
                               default=_default_model)

# --- Хранилище ------------------------------------------------------------
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data")))
# Все результаты — в одном файле SQLite.
DB_FILE = DATA_DIR / "21day.sqlite3"

# --- Администраторы -------------------------------------------------------
# Список Telegram user_id через запятую (env ADMIN_IDS). Админам доступна
# команда /admin. По умолчанию — владелец проекта.
ADMIN_IDS: set[int] = {
    int(x) for x in _first_env("ADMIN_IDS",
                               default="52160369")
    .replace(";", ",").split(",") if x.strip().isdigit()
}


# Бот умеет работать и без API-ключа.
LLM_ENABLED: bool = bool(OPENAI_API_KEY)
