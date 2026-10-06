# -*- coding: utf-8 -*-
"""21day_system — Telegram-бот трёх 21-дневных микро-практик.

Запуск:
    set TELEGRAM_BOT_TOKEN=123:ABC        (Windows)
    python bot.py

* Первый, кто написал боту, выбирает одну из трёх систем кнопкой.
* Прогресс пишется в файл SQLite (data/21day.sqlite3).
* Индикаторы прогресса (RSI/ADX/ATR по мотивам Welles Wilder) видны всегда.
* График прогресса: /chart — «трейдерский» или стилизованный.
* API-ключ (OpenAI-совместимый) необязателен: без него — офлайн-совет.

Проект: https://github.com/j0k/21day_system
"""
from __future__ import annotations

import html
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import config
from graph import render as render_chart
from indicators import compute, indicator_block
from llm import ask as llm_ask
from storage import Storage
from systems import SYSTEMS, SYSTEM_ORDER, TOTAL_DAYS

API = "https://api.telegram.org/bot{token}/{method}"
DB = Storage(config.DB_FILE)
PENDING: dict[int, dict] = {}   # chat_id -> {"action": ..., "day": ...}


# ------------------------------------------------------------------ Telegram
def _call(method: str, params: dict) -> dict:
    url = API.format(token=config.TELEGRAM_BOT_TOKEN, method=method)
    data = urllib.parse.urlencode(params).encode("utf-8")
    try:
        with urllib.request.urlopen(url, data=data, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": exc.read().decode("utf-8", "replace")}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _call_photo(chat_id: int, path: str, caption: str, keyboard=None) -> dict:
    """multipart/form-data для sendPhoto."""
    url = API.format(token=config.TELEGRAM_BOT_TOKEN, method="sendPhoto")
    boundary = "----21day" + str(int(time.time()))
    with open(path, "rb") as fh:
        blob = fh.read()
    parts: list[bytes] = []

    def field(name: str, value: str):
        parts.append(
            (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n"
             f"{value}\r\n").encode("utf-8"))

    def file_field(name: str, filename: str, content: bytes):
        parts.append(
            (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\";"
             f" filename=\"{filename}\"\r\nContent-Type: image/png\r\n\r\n"
             ).encode("utf-8"))
        parts.append(content)
        parts.append(b"\r\n")

    field("chat_id", str(chat_id))
    field("caption", caption)
    field("parse_mode", "HTML")
    if keyboard is not None:
        field("reply_markup", json.dumps(keyboard, ensure_ascii=False))
    file_field("photo", Path(path).name, blob)
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def send(chat_id: int, text: str, keyboard=None):
    params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
              "disable_web_page_preview": "true"}
    if keyboard is not None:
        params["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)
    return _call("sendMessage", params)


def edit(chat_id: int, message_id: int, text: str, keyboard=None):
    params = {"chat_id": chat_id, "message_id": message_id, "text": text,
              "parse_mode": "HTML", "disable_web_page_preview": "true"}
    if keyboard is not None:
        params["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)
    return _call("editMessageText", params)


def answer_cb(cb_id: str, text: str = ""):
    return _call("answerCallbackQuery", {"callback_query_id": cb_id, "text": text})


# ---------------------------------------------------------------- клавиатуры
def kb_systems():
    rows = []
    for sid in SYSTEM_ORDER:
        s = SYSTEMS[sid]
        rows.append([{"text": f"{s.emoji}  {s.title}", "callback_data": f"sys:{sid}"}])
    return {"inline_keyboard": rows}


def kb_main(system):
    return {"inline_keyboard": [
        [{"text": "▶️ Мой день", "callback_data": "today"},
         {"text": "📊 Прогресс", "callback_data": "progress"}],
        [{"text": "🗓 Неделя 1", "callback_data": "week:1"},
         {"text": "🗓 Неделя 2", "callback_data": "week:2"},
         {"text": "🗓 Неделя 3", "callback_data": "week:3"}],
        [{"text": "📈 График", "callback_data": "chart:trader"},
         {"text": "🎨 Стиль", "callback_data": "chart:styled"}],
        [{"text": "💡 Совет", "callback_data": "advise"},
         {"text": "🔀 Сменить систему", "callback_data": "systems"}],
    ]}


def kb_day(day, done):
    mark = ({"text": "✅ Выполнено — отменить", "callback_data": f"unmark:{day}"}
            if done else
            {"text": "✅ Отметить выполненным", "callback_data": f"mark:{day}"})
    return {"inline_keyboard": [
        [mark],
        [{"text": "📝 Заметка", "callback_data": f"note:{day}"},
         {"text": "📊 Прогресс", "callback_data": "progress"}],
        [{"text": "▶️ Мой день", "callback_data": "today"},
         {"text": "🏠 Меню", "callback_data": "menu"}],
    ]}


def kb_back_menu():
    return {"inline_keyboard": [[{"text": "🏠 Меню", "callback_data": "menu"},
                                 {"text": "📊 Прогресс", "callback_data": "progress"}]]}


# ------------------------------------------------------------------- тексты
def _esc(s: str) -> str:
    return html.escape(str(s), quote=False)


def _compact(st: dict) -> str:
    """Мини-строка индикаторов — видна в каждом экране."""
    return (f"📈 {st['done']}/{st['total']} ({st['pct']}%) · "
            f"RSI {st['rsi']} · ADX {st['adx']} · темп {st['pace']}%")


def _user_and_system(chat_id: int):
    user = DB.get_user(chat_id)
    if not user or not user.system_id:
        return None, None
    return user, SYSTEMS[user.system_id]


def screen_systems(chat_id: int, message_id: int | None = None):
    text = ("<b>21day_system</b> — три системы микро-практики.\n"
            "Выбери ту, которую хочешь пройти. Выбор можно сменить в любой момент.\n\n"
            + "\n".join(f"{SYSTEMS[s].emoji} <b>{_esc(SYSTEMS[s].title)}</b>\n"
                        f"    <i>{_esc(SYSTEMS[s].subtitle)}</i>"
                        for s in SYSTEM_ORDER))
    if message_id:
        edit(chat_id, message_id, text, kb_systems())
    else:
        send(chat_id, text, kb_systems())


def screen_menu(chat_id: int, message_id: int | None = None):
    user, system = _user_and_system(chat_id)
    if not system:
        return screen_systems(chat_id, message_id)
    st = DB.stats(chat_id, system.id)
    series = st["series"]
    next_day = next((d for d in range(1, TOTAL_DAYS + 1) if not series[d - 1]),
                    TOTAL_DAYS)
    text = (f"{system.emoji} <b>{_esc(system.title)}</b>\n"
            f"<i>{_esc(system.subtitle)}</i>\n\n"
            f"Следующий день: <b>{next_day}</b>\n\n{_compact(st)}")
    if message_id:
        edit(chat_id, message_id, text, kb_main(system))
    else:
        send(chat_id, text, kb_main(system))


def screen_today(chat_id: int, message_id: int | None = None):
    user, system = _user_and_system(chat_id)
    if not system:
        return screen_systems(chat_id, message_id)
    st = DB.stats(chat_id, system.id)
    series = st["series"]
    d = next((x for x in range(1, TOTAL_DAYS + 1) if not series[x - 1]), None)
    finished = d is None
    if finished:
        d = TOTAL_DAYS
    day = system.day(d)
    week = system.week_of(d)
    done = bool(series[d - 1])

    head = (f"{system.emoji} <b>День {d} / {TOTAL_DAYS}</b>"
            + ("  ✅" if done else ""))
    body = (f"<i>{_esc(week.title)}</i>\n"
            f"⏱ <b>{day.minutes} мин</b>\n\n"
            f"{_esc(day.action)}\n\n"
            f"🎯 <i>{_esc(day.skill)}</i>")
    tail = ("\n\n🏁 Все 21 день отмечены — поздравляю! Смотри /progress и /chart."
            if finished else "")
    text = f"{head}\n{body}{tail}\n\n{_compact(st)}"
    kb = kb_back_menu() if finished else kb_day(d, done)
    if message_id:
        edit(chat_id, message_id, text, kb)
    else:
        send(chat_id, text, kb)


def screen_progress(chat_id: int, message_id: int | None = None):
    user, system = _user_and_system(chat_id)
    if not system:
        return screen_systems(chat_id, message_id)
    st = DB.stats(chat_id, system.id)
    series = st["series"]
    marks = "".join("🟩" if v else "⬜" for v in series)
    text = (f"{system.emoji} <b>{_esc(system.title)}</b>\n\n"
            f"{marks}\n\n"
            f"выполнено <b>{st['done']}/{st['total']}</b> · {st['pct']}%\n"
            f"текущая серия: <b>{st['streak']}</b> · лучшая: <b>{st['best_streak']}</b>\n"
            f"суммарно: <b>{st['minutes']} мин</b>\n\n"
            f"{indicator_block(st)}")
    if message_id:
        edit(chat_id, message_id, text, kb_main(system))
    else:
        send(chat_id, text, kb_main(system))


def screen_week(chat_id: int, n: int, message_id: int | None = None):
    user, system = _user_and_system(chat_id)
    if not system:
        return screen_systems(chat_id, message_id)
    week = system.weeks[n - 1]
    st = DB.stats(chat_id, system.id)
    lines = [f"{system.emoji} <b>{_esc(week.title)}</b>\n"]
    for day in week.days:
        mark = "✅" if st["series"][day.n - 1] else "▫️"
        lines.append(f"{mark} <b>{day.n}</b>. {_esc(day.action)}  "
                     f"<i>({day.minutes} мин)</i>")
    text = "\n".join(lines) + f"\n\n{_compact(st)}"
    if message_id:
        edit(chat_id, message_id, text, kb_main(system))
    else:
        send(chat_id, text, kb_main(system))


def send_chart(chat_id: int, style: str):
    user, system = _user_and_system(chat_id)
    if not system:
        return screen_systems(chat_id)
    st = DB.stats(chat_id, system.id)
    out = config.DATA_DIR / f"chart_{chat_id}_{system.id}.png"
    render_chart(system, st["series"], out, style=style)
    caption = (f"{system.emoji} <b>{_esc(system.title)}</b>\n"
               f"<i>{'трейдерский вид' if style == 'trader' else 'стилизованный вид'}"
               f" · индикаторы Welles Wilder</i>")
    _call_photo(chat_id, str(out), caption, kb_main(system))


# ------------------------------------------------------------------ callbacks
def on_callback(cb: dict):
    data = cb.get("data", "")
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")
    user = cb.get("from", {})
    DB.touch(chat_id, chat_id, user.get("first_name", ""),
             user.get("username", ""))
    answer_cb(cb["id"])

    if data == "systems" or data == "menu_choice":
        return screen_systems(chat_id, message_id)
    if data.startswith("sys:"):
        sid = data.split(":", 1)[1]
        if sid not in SYSTEMS:
            return
        DB.set_system(chat_id, sid)
        s = SYSTEMS[sid]
        send(chat_id, f"Выбрана система: {s.emoji} <b>{_esc(s.title)}</b>\n"
                      f"<i>{_esc(s.subtitle)}</i>\n\nНачинаем! День 1 ниже.")
        return screen_today(chat_id)
    if data == "menu":
        return screen_menu(chat_id, message_id)
    if data == "today":
        return screen_today(chat_id, message_id)
    if data == "progress":
        return screen_progress(chat_id, message_id)
    if data.startswith("week:"):
        return screen_week(chat_id, int(data.split(":", 1)[1]), message_id)
    if data.startswith("chart:"):
        return send_chart(chat_id, data.split(":", 1)[1])
    if data.startswith("mark:"):
        d = int(data.split(":", 1)[1])
        user_obj, system = _user_and_system(chat_id)
        DB.set_done(chat_id, system.id, d, True)
        return screen_today(chat_id, message_id)
    if data.startswith("unmark:"):
        d = int(data.split(":", 1)[1])
        user_obj, system = _user_and_system(chat_id)
        DB.set_done(chat_id, system.id, d, False)
        return screen_today(chat_id, message_id)
    if data.startswith("note:"):
        d = int(data.split(":", 1)[1])
        PENDING[chat_id] = {"action": "note", "day": d}
        edit(chat_id, message_id,
             f"✍️ Напиши короткую заметку по дню {d} (1–3 строки) и отправь "
             f"сообщением. Или /cancel.",
             {"inline_keyboard": [[{"text": "Отмена", "callback_data": "today"}]]})
        return
    if data == "advise":
        user_obj, system = _user_and_system(chat_id)
        st = DB.stats(chat_id, system.id)
        d = next((x for x in range(1, TOTAL_DAYS + 1) if not st["series"][x - 1]), 1)
        day = system.day(d)
        advice, used = llm_ask(system, "Как не сорваться и выполнить сегодняшний день?",
                               f"День {d}: {day.action}")
        tag = "LLM" if used else "офлайн-режим (без API-ключа)"
        return send(chat_id, f"💡 <b>Совет</b> <i>({tag})</i>\n\n{_esc(advice)}",
                    kb_back_menu())


# -------------------------------------------------------------------- message
def on_message(msg: dict):
    chat_id = msg.get("chat", {}).get("id")
    user = msg.get("from", {})
    text = (msg.get("text") or "").strip()
    DB.touch(chat_id, chat_id, user.get("first_name", ""),
             user.get("username", ""))

    if chat_id in PENDING and not text.startswith("/"):
        pend = PENDING.pop(chat_id)
        user_obj, system = _user_and_system(chat_id)
        DB.set_done(chat_id, system.id, pend["day"], True, note=text)
        send(chat_id, f"📝 Заметка к дню {pend['day']} сохранена.")
        return screen_today(chat_id)

    if text.startswith("/start"):
        return screen_systems(chat_id)
    if text.startswith("/menu"):
        return screen_menu(chat_id)
    if text.startswith("/today"):
        return screen_today(chat_id)
    if text.startswith("/progress"):
        return screen_progress(chat_id)
    if text.startswith("/chart"):
        parts = text.split()
        style = "styled" if len(parts) > 1 and parts[1] in ("styled", "style",
                                                             "стиль") else "trader"
        return send_chart(chat_id, style)
    if text.startswith("/systems"):
        return screen_systems(chat_id)
    if text.startswith("/cancel"):
        PENDING.pop(chat_id, None)
        return send(chat_id, "Ок, отменено.", kb_back_menu())
    if text.startswith("/help"):
        return send(chat_id,
                    "<b>Команды</b>\n"
                    "/start — выбрать систему\n"
                    "/today — текущий день\n"
                    "/progress — прогресс и индикаторы\n"
                    "/chart [styled] — график прогресса\n"
                    "/systems — сменить систему\n"
                    "/cancel — отменить ввод\n\n"
                    "Днём можно отметить выполнение кнопкой и добавить заметку.\n"
                    "Проект: https://github.com/j0k/21day_system",
                    kb_back_menu())
    user_obj, system = _user_and_system(chat_id)
    if not system:
        return screen_systems(chat_id)
    return send(chat_id, "Не понял. Открой /menu или /help.", kb_main(system))


# ----------------------------------------------------------------------- loop
def main():
    if not config.TELEGRAM_BOT_TOKEN:
        print("Нет TELEGRAM_BOT_TOKEN. Создай .env по образцу .env.example "
              "или задай переменную окружения.")
        return
    print("21day_system бот запущен. Проект: https://github.com/j0k/21day_system")
    print("БД:", config.DB_FILE,
          "| LLM:", "вкл" if config.LLM_ENABLED else "выкл")
    offset = None
    while True:
        params = {"timeout": config.POLL_TIMEOUT}
        if offset is not None:
            params["offset"] = offset
        resp = _call("getUpdates", params)
        if not resp.get("ok"):
            print("getUpdates:", resp.get("error"))
            time.sleep(3)
            continue
        for upd in resp.get("result", []):
            offset = upd["update_id"] + 1
            try:
                if "callback_query" in upd:
                    on_callback(upd["callback_query"])
                elif "message" in upd:
                    on_message(upd["message"])
            except Exception as exc:  # noqa: BLE001
                print("handler error:", exc)


if __name__ == "__main__":
    main()
