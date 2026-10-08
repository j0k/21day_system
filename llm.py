# -*- coding: utf-8 -*-
"""Необязательный LLM-советник (OpenAI-совместимый API).

Если ключа нет — работает офлайн: возвращает заранее заготовленный совет,
подобранный по текущему дню системы. Сетевые вызовы делаются только при
наличии ключа.
"""
from __future__ import annotations

import json
import urllib.request

import config

_PERSONA = (
    "Ты — доброжелательный наставник по 21-дневным микро-практикам. "
    "Отвечай кратко (3–5 предложений), по-русски, без воды и мотивационного шума. "
    "Опирайся на принцип: маленькое ежедневное действие важнее рывка; "
    "навык растёт косвенно. Если просят совет — дай один конкретный шаг."
)


def _offline_advice(system, day_text: str) -> str:
    return (
        "Сделай только это действие и не расширяй его — весь смысл в дозе. "
        "После — короткая отметка (1–3 строки). Пропустишь день — не догоняй, "
        "просто вернись завтра. Так навык держится сам."
    )


def ask(system, question: str, day_text: str = "") -> tuple[str, bool]:
    """Вернуть (ответ, использован_ли_API)."""
    if not config.LLM_ENABLED:
        return _offline_advice(system, day_text), False

    payload = {
        "model": config.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": _PERSONA},
            {"role": "user", "content":
                f"Система: {system.title}\nКонтекст дня: {day_text}\n"
                f"Вопрос: {question}"},
        ],
        "temperature": 0.6,
        "max_tokens": 400,
    }
    return _chat(payload, _offline_advice(system, day_text))


_DEV_PERSONA = (
    "Ты — технический со-пилот проекта 21day_system (Telegram-бот трёх "
    "21-дневных микро-практик на Python). Пользователь — автор проекта. "
    "Обсуждай функционал, предлагай решения, оценивай идеи, пиши короткие "
    "фрагменты кода при необходимости. Отвечай по-русски, конкретно, без воды. "
    "ВАЖНО: в проекте только стандартная библиотека Python и matplotlib — "
    "не предлагай сторонние пакеты (schedule, apscheduler, requests и т.п.); "
    "если нужна фоновая задача — используй threading стандартной библиотеки. "
    "Если предлагаешь изменение — укажи, какой файл трогать (bot.py, "
    "storage.py, systems.py, indicators.py, graph.py, radar.py, llm.py, "
    "config.py). Можешь задавать уточняющие вопросы. "
    "Оформляй ответ в Markdown: заголовки, списки, **жирный**, `код` и блоки "
    "кода в ``` — бот отрендерит их в Telegram."
)


def chat_dev(history: list[dict], question: str, context: str = ""
            ) -> tuple[str, bool]:
    """Свободный диалог про функционал проекта (для админа).

    ``history`` — прошлые сообщения [{"role", "content"}] без system.
    """
    if not config.LLM_ENABLED:
        return ("LLM недоступен: не задан API-ключ. Задай OPENAI_API_KEY / "
                "ROUTERAI_API_KEY / LLM_API_KEY и перезапусти бота.", False)
    msgs = [{"role": "system", "content": _DEV_PERSONA}]
    if context:
        msgs.append({"role": "system", "content": "Текущее состояние:\n" + context})
    msgs.extend(history[-12:])
    msgs.append({"role": "user", "content": question})
    return _chat({"model": config.OPENAI_MODEL, "messages": msgs,
                  "temperature": 0.5, "max_tokens": 900}, "")


def _chat(payload: dict, offline: str) -> tuple[str, bool]:
    req = urllib.request.Request(
        config.OPENAI_BASE_URL + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip()
        return text, True
    except Exception as exc:  # noqa: BLE001
        return ((f"(LLM недоступен: {exc})\n\n" + offline) if offline
                else f"(LLM недоступен: {exc})", False)
