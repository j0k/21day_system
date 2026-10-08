# -*- coding: utf-8 -*-
"""21day_system — Telegram-бот трёх 21-дневных микро-практик.

Запуск:
    set TELEGRAM_BOT_TOKEN=123:ABC        (Windows)
    python bot.py

* Первый, кто написал боту, выбирает одну из трёх систем кнопкой.
* Прогресс пишется в файл SQLite (data/21day.sqlite3).
* Индикаторы прогресса (RSI/ADX/ATR по мотивам Welles Wilder) видны всегда.
* График прогресса: /chart — «трейдерский», стилизованный или радар TCAS.
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
from llm import chat_dev as llm_chat_dev
from md import to_html as md_to_html
from radar import render_radar
from storage import Storage
from systems import SYSTEMS, SYSTEM_ORDER, TOTAL_DAYS

API = "https://api.telegram.org/bot{token}/{method}"
DB = Storage(config.DB_FILE)
PENDING: dict[int, dict] = {}   # chat_id -> {"action": ..., "day": ...}
# История диалога с LLM про функционал (админ): chat_id -> [{"role","content"}]
CHAT_HISTORY: dict[int, list[dict]] = {}


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


def send_md(chat_id: int, prefix_html: str, markdown: str, keyboard=None):
    """Отправить текст LLM с рендером Markdown→HTML и безопасным откатом.

    Если Telegram не принял разметку — шлём тот же текст как есть (экранируя),
    чтобы ответ точно дошёл.
    """
    resp = send(chat_id, prefix_html + md_to_html(markdown), keyboard)
    if not resp.get("ok"):
        resp = send(chat_id, prefix_html + _esc(markdown), keyboard)
    return resp


def edit(chat_id: int, message_id: int, text: str, keyboard=None):
    params = {"chat_id": chat_id, "message_id": message_id, "text": text,
              "parse_mode": "HTML", "disable_web_page_preview": "true"}
    if keyboard is not None:
        params["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)
    return _call("editMessageText", params)


def answer_cb(cb_id: str, text: str = ""):
    return _call("answerCallbackQuery", {"callback_query_id": cb_id, "text": text})


# ---------------------------------------------------------------- клавиатуры
def kb_systems(chat_id: int | None = None):
    rows = []
    for sid in SYSTEM_ORDER:
        s = SYSTEMS[sid]
        rows.append([{"text": f"{s.emoji}  {s.title}", "callback_data": f"sys:{sid}"}])
    rows.append([{"text": "👥 Участники", "callback_data": "users"},
                 {"text": "🏆 Лидеры", "callback_data": "board"}])
    rows.append([{"text": "🙍 Профиль", "callback_data": "profile"}])
    if chat_id is not None and _is_admin(chat_id):
        rows.append([{"text": "🛠 Админка", "callback_data": "admin"},
                     {"text": "💬 Чат с LLM", "callback_data": "dev"}])
    return {"inline_keyboard": rows}


def kb_board(system_id: str | None = None):
    def tab(sid, label):
        mark = "· " if system_id == sid else ""
        return {"text": f"{mark}{label}", "callback_data": f"board:{sid}"}
    return {"inline_keyboard": [
        [tab("skills", "🧠 микро-практика"),
         tab("discipline", "📅 дисциплина"),
         tab("sleep", "🌙 сон")],
        [{"text": "🌐 Все системы", "callback_data": "board:all"},
         {"text": "⬅️ К выбору", "callback_data": "systems"}],
    ]}


def kb_profile(user) -> dict:
    label = ("🔒 Сделать приватным" if user.is_public
             else "🌐 Сделать публичным")
    return {"inline_keyboard": [
        [{"text": label,
          "callback_data": "privacy:" + ("0" if user.is_public else "1")}],
        [{"text": "👥 Участники", "callback_data": "users"},
         {"text": "🏆 Лидеры", "callback_data": "board"}],
        [{"text": "🏠 Меню", "callback_data": "menu"}],
    ]}


def kb_main(system):
    return {"inline_keyboard": [
        [{"text": "▶️ Мой день", "callback_data": "today"},
         {"text": "📊 Прогресс", "callback_data": "progress"}],
        [{"text": "🗓 Неделя 1", "callback_data": "week:1"},
         {"text": "🗓 Неделя 2", "callback_data": "week:2"},
         {"text": "🗓 Неделя 3", "callback_data": "week:3"}],
        [{"text": "📈 График", "callback_data": "chart:trader"},
         {"text": "🎨 Стиль", "callback_data": "chart:styled"}],
        [{"text": "📡 Радар TCAS", "callback_data": "chart:radar"}],
        [{"text": "💡 Совет", "callback_data": "advise"},
         {"text": "🙍 Профиль", "callback_data": "profile"}],
        [{"text": "🏆 Лидеры", "callback_data": "board"},
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
    n_users = DB.participants()
    board = DB.leaderboard(limit=3)
    text = ("<b>21day_system</b> — три системы микро-практики.\n"
            "Выбери ту, которую хочешь пройти. Выбор можно сменить в любой момент.\n\n"
            + "\n".join(f"{SYSTEMS[s].emoji} <b>{_esc(SYSTEMS[s].title)}</b>\n"
                        f"    <i>{_esc(SYSTEMS[s].subtitle)}</i>"
                        for s in SYSTEM_ORDER))
    text += f"\n\n👥 Участников: <b>{n_users}</b>"
    if board:
        text += "\n🏆 Лидеры:\n" + "\n".join(_board_line(r) for r in board)
    if message_id:
        edit(chat_id, message_id, text, kb_systems(chat_id))
    else:
        send(chat_id, text, kb_systems(chat_id))


def _board_line(r: dict) -> str:
    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(r["rank"], f"{r['rank']}.")
    sys_emoji = SYSTEMS[r["system_id"]].emoji if r["system_id"] in SYSTEMS else ""
    return (f"{medal} <b>{_esc(r['name'])}</b> — {r['done']}/{TOTAL_DAYS} "
            f"({r['pct']}%) {sys_emoji} · серия {r['streak']}")


def screen_users(chat_id: int, message_id: int | None = None):
    n = DB.participants()
    board = DB.leaderboard(limit=20)
    # сколько людей идут каждую систему
    counts = {sid: 0 for sid in SYSTEM_ORDER}
    for r in board:
        if r["system_id"] in counts:
            counts[r["system_id"]] += 1
    text = [f"👥 <b>Участники</b>\n",
            f"Всего писали боту: <b>{n}</b>",
            "Активных (есть отметки): <b>%d</b>\n" % len(DB.leaderboard(limit=999))]
    for sid in SYSTEM_ORDER:
        s = SYSTEMS[sid]
        text.append(f"{s.emoji} <b>{_esc(s.title)}</b> — {counts[sid]}")
    text.append("\n🏆 Топ:\n" + "\n".join(_board_line(r) for r in board[:10])
                if board else "\nПока никто не отметил ни одного дня.")
    body = "\n".join(text)
    if message_id:
        edit(chat_id, message_id, body, kb_systems(chat_id))
    else:
        send(chat_id, body, kb_systems(chat_id))


def screen_board(chat_id: int, system_id: str | None = None,
                 message_id: int | None = None):
    sid = system_id if system_id in SYSTEMS else None
    rows = DB.leaderboard(sid, limit=20)
    title = ("🏆 <b>Лидеры</b> — все системы" if sid is None
             else f"🏆 <b>Лидеры</b> — {SYSTEMS[sid].emoji} "
                  f"{_esc(SYSTEMS[sid].title)}")
    if not rows:
        body = f"{title}\n\nПока никто не отметил ни одного дня. Стань первым!"
    else:
        lines = [f"{r['rank']}. <b>{_esc(r['name'])}</b> — {r['done']}/{TOTAL_DAYS} "
                 f"({r['pct']}%) · серия {r['streak']} · {r['minutes']} мин"
                 for r in rows]
        body = title + "\n\n" + "\n".join(lines)
    if message_id:
        edit(chat_id, message_id, body, kb_board(sid))
    else:
        send(chat_id, body, kb_board(sid))


def _is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def kb_admin() -> dict:
    return {"inline_keyboard": [
        [{"text": "👥 Пользователи", "callback_data": "admin:users:0"},
         {"text": "🕓 Журнал", "callback_data": "admin:log"}],
        [{"text": "🔎 Найти", "callback_data": "admin:find"},
         {"text": "📣 Рассылка", "callback_data": "admin:broadcast"}],
        [{"text": "📊 Сводка", "callback_data": "admin"},
         {"text": "💬 Чат с LLM", "callback_data": "dev"}],
        [{"text": "🏠 Меню", "callback_data": "menu"}],
    ]}


def kb_dev(active: bool = True) -> dict:
    if active:
        return {"inline_keyboard": [
            [{"text": "🧹 Очистить историю", "callback_data": "dev:clear"},
             {"text": "🛠 Админка", "callback_data": "admin"}],
            [{"text": "🏠 Меню", "callback_data": "menu"}],
        ]}
    return {"inline_keyboard": [
        [{"text": "💬 Открыть чат с LLM", "callback_data": "dev"},
         {"text": "🛠 Админка", "callback_data": "admin"}],
        [{"text": "🏠 Меню", "callback_data": "menu"}],
    ]}


def _project_context() -> str:
    """Краткое состояние проекта — чтобы LLM отвечал предметно."""
    over = DB.overview()
    lines = [
        f"Системы: {', '.join(sid for sid in SYSTEM_ORDER)} "
        f"({TOTAL_DAYS} дней каждая).",
        f"Пользователей: {over['users']}, отметок: {over['marks']}.",
        "Файлы: bot.py (экраны/диалог), storage.py (SQLite), systems.py "
        "(данные 21 дня), indicators.py (RSI/ADX/ATR по Уайлдеру), "
        "graph.py (2 графика), radar.py (радар TCAS), llm.py, config.py.",
        "Есть: выбор системы кнопкой, отметки/заметки, индикаторы, графики "
        "(trader/styled/radar), участники, лидерборд, профиль "
        "(публичный/приватный), админка (пользователи, журнал, рассылка).",
        "Стек: Python stdlib + matplotlib, Telegram через urllib long-polling.",
    ]
    return "\n".join(lines)


def screen_dev(chat_id: int, message_id: int | None = None):
    hist = CHAT_HISTORY.get(chat_id, [])
    text = ("💬 <b>Чат с LLM о функционале</b>\n\n"
            "Пиши сообщением, что хочешь обсудить или добавить в бота. "
            "Я помню последние 12 реплик.\n\n"
            f"Реплик в истории: <b>{len(hist)}</b>. "
            + ("Можешь продолжать." if hist else "Начни с любого вопроса."))
    if message_id:
        edit(chat_id, message_id, text, kb_dev(active=True))
    else:
        send(chat_id, text, kb_dev(active=True))


def kb_admin_user(uid: int) -> dict:
    return {"inline_keyboard": [
        [{"text": "♻️ Сбросить прогресс", "callback_data": f"admin:reset:{uid}"},
         {"text": "🌐 Публичность", "callback_data": f"admin:pub:{uid}"}],
        [{"text": "🗑 Удалить", "callback_data": f"admin:del:{uid}"}],
        [{"text": "⬅️ К списку", "callback_data": "admin:users:0"},
         {"text": "🏠 Меню", "callback_data": "menu"}],
    ]}


def screen_admin(chat_id: int, message_id: int | None = None):
    over = DB.overview()
    lines = [f"🛠 <b>Админ-панель</b>\n",
             f"👥 Пользователей: <b>{over['users']}</b> "
             f"(публичных: {over['public']})",
             f"✅ Отметок всего: <b>{over['marks']}</b>",
             f"🕓 Событий в журнале: <b>{over['logs']}</b>\n",
             "По системам (выбрали / отметок):"]
    for sid in SYSTEM_ORDER:
        s = SYSTEMS[sid]
        lines.append(f"{s.emoji} {_esc(s.title)} — "
                     f"{over['selected'].get(sid, 0)} / "
                     f"{over['by_system'].get(sid, 0)}")
    text = "\n".join(lines)
    if message_id:
        edit(chat_id, message_id, text, kb_admin())
    else:
        send(chat_id, text, kb_admin())


def screen_admin_users(chat_id: int, offset: int = 0,
                       message_id: int | None = None):
    offset = max(0, offset)
    rows = DB.all_users(limit=10, offset=offset)
    over = DB.overview()
    head = f"👥 <b>Пользователи</b> ({offset + 1}–{offset + len(rows)} "
    head += f"из {over['users']})\n"
    if not rows:
        body = head + "\nПусто."
        kb = {"inline_keyboard": [[{"text": "⬅️ Назад",
                                   "callback_data": "admin"}]]}
    else:
        lines = []
        for u in rows:
            vis = "🌐" if u["is_public"] else "🔒"
            name = u["first_name"] or (u["username"] and "@" + u["username"]) \
                or f"id{u['user_id']}"
            sysid = u["system_id"] or "—"
            lines.append(f"{vis} <b>{_esc(name)}</b> · {sysid} · "
                         f"{u['done']}/21 · <code>{u['user_id']}</code>")
        body = head + "\n" + "\n".join(lines)
        nav = []
        if offset > 0:
            nav.append({"text": "⬅️", "callback_data": f"admin:users:{max(0, offset - 10)}"})
        nav.append({"text": "🏠 Меню", "callback_data": "menu"})
        if offset + 10 < over["users"]:
            nav.append({"text": "➡️", "callback_data": f"admin:users:{offset + 10}"})
        kb = {"inline_keyboard": [nav]}
    if message_id:
        edit(chat_id, message_id, body, kb)
    else:
        send(chat_id, body, kb)


def screen_admin_user(chat_id: int, uid: int, query: str = "",
                      message_id: int | None = None):
    user = DB.get_user(uid)
    if not user:
        return send(chat_id, "Пользователь не найден.", kb_admin())
    system = SYSTEMS[user.system_id] if user.system_id in SYSTEMS else None
    st = DB.stats(uid, user.system_id) if system else None
    name = user.first_name or (user.username and "@" + user.username) \
        or f"id{user.user_id}"
    lines = [f"👤 <b>{_esc(name)}</b>",
             f"id: <code>{user.user_id}</code> · @{_esc(user.username) or '—'}",
             f"система: {system.emoji + ' ' + _esc(system.title) if system else '—'}",
             f"видимость: {'🌐 публичный' if user.is_public else '🔒 приватный'}",
             f"начал: {_esc(user.started_at or '—')}",
             f"был(а): {_esc(user.last_seen or '—')}"]
    if st:
        lines.append(f"\nпрогресс: <b>{st['done']}/{st['total']}</b> "
                     f"({st['pct']}%) · серия {st['streak']} · "
                     f"{st['minutes']} мин")
        lines.append("".join("🟩" if v else "⬜" for v in st["series"]))
        notes = DB.get_progress(uid, user.system_id)
        with_notes = [(d, n["note"]) for d, n in sorted(notes.items())
                      if n.get("note")]
        if with_notes:
            lines.append("\n📝 последние заметки:")
            for d, n in with_notes[-3:]:
                lines.append(f"  • день {d}: {_esc(n)}")
    text = "\n".join(lines)
    if message_id:
        edit(chat_id, message_id, text, kb_admin_user(uid))
    else:
        send(chat_id, text, kb_admin_user(uid))


def screen_admin_find(chat_id: int, query: str = "",
                      message_id: int | None = None):
    if not query:
        PENDING[chat_id] = {"action": "admin_find"}
        text = ("🔎 Напиши <b>username</b>, <b>имя</b> или <b>id</b> "
                "пользователя. Или /cancel.")
        kb = {"inline_keyboard": [[{"text": "⬅️ Назад",
                                   "callback_data": "admin"}]]}
        if message_id:
            return edit(chat_id, message_id, text, kb)
        return send(chat_id, text, kb)
    found = DB.get_user_by_name(query)
    if not found:
        return send(chat_id, f"🔎 Ничего не найдено по «{_esc(query)}».",
                    kb_admin())
    if len(found) == 1:
        return screen_admin_user(chat_id, found[0].user_id, query=query,
                                 message_id=message_id)
    rows = []
    for u in found:
        name = u.first_name or (u.username and "@" + u.username) \
            or f"id{u.user_id}"
        rows.append([{"text": f"{name} · {u.user_id}",
                      "callback_data": f"admin:view:{u.user_id}"}])
    rows.append([{"text": "⬅️ Назад", "callback_data": "admin"}])
    text = f"🔎 Найдено: <b>{len(found)}</b>. Выбери:"
    if message_id:
        edit(chat_id, message_id, text, {"inline_keyboard": rows})
    else:
        send(chat_id, text, {"inline_keyboard": rows})


def screen_admin_log(chat_id: int, message_id: int | None = None):
    rows = DB.recent_log(limit=20)
    if not rows:
        body = "🕓 Журнал пуст."
    else:
        lines = ["🕓 <b>Последние события</b>\n"]
        for r in rows:
            lines.append(f"<code>{_esc(r['ts'])}</code> · "
                         f"<code>{r['user_id']}</code> · "
                         f"<b>{_esc(r['event'])}</b> {_esc(r['detail'])[:40]}")
        body = "\n".join(lines)
    kb = {"inline_keyboard": [[{"text": "⬅️ Назад", "callback_data": "admin"},
                               {"text": "🏠 Меню", "callback_data": "menu"}]]}
    if message_id:
        edit(chat_id, message_id, body, kb)
    else:
        send(chat_id, body, kb)


def screen_admin_broadcast(chat_id: int, message_id: int | None = None):
    PENDING[chat_id] = {"action": "admin_broadcast"}
    text = ("📣 Напиши текст рассылки — отправлю всем пользователям бота. "
            "Или /cancel.")
    kb = {"inline_keyboard": [[{"text": "⬅️ Назад", "callback_data": "admin"}]]}
    if message_id:
        edit(chat_id, message_id, text, kb)
    else:
        send(chat_id, text, kb)


def screen_profile(chat_id: int, message_id: int | None = None):
    user = DB.get_user(chat_id)
    if not user:
        return screen_systems(chat_id, message_id)
    system = SYSTEMS[user.system_id] if user.system_id in SYSTEMS else None
    vis = ("🌐 <b>Публичный</b> — имя видно в таблице лидеров"
           if user.is_public else
           "🔒 <b>Приватный</b> — в лидерборде показывается как "
           "<b>Private User</b>")
    shown = (user.first_name or (user.username and "@" + user.username)
             or f"id{user.user_id}")
    name_line = (f"Отображаемое имя: <b>{_esc(shown)}</b>" if user.is_public
                 else "Отображаемое имя: <b>Private User</b>")
    sys_line = (f"{system.emoji} {_esc(system.title)}" if system
                else "система не выбрана")
    rank_line = ""
    rows = DB.leaderboard()
    mine = next((r for r in rows if r["user_id"] == user.user_id), None)
    if mine:
        rank_line = (f"\n🏆 Место в лидерах: <b>#{mine['rank']}</b> "
                     f"({mine['done']}/{TOTAL_DAYS})")
    text = (f"🙍 <b>Профиль</b>\n\n"
            f"{name_line}\n"
            f"Видимость: {vis}\n"
            f"Система: {sys_line}"
            f"{rank_line}\n\n"
            f"<i>Если ты ещё не сделал профиль публичным, в таблице лидеров "
            f"ты значишься как Private User.</i>")
    if message_id:
        edit(chat_id, message_id, text, kb_profile(user))
    else:
        send(chat_id, text, kb_profile(user))


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
    out = config.DATA_DIR / f"chart_{chat_id}_{system.id}_{style}.png"
    if style == "radar":
        render_radar(system, st["series"], st, out)
        caption = (f"{system.emoji} <b>{_esc(system.title)}</b>\n"
                   f"<i>радар прогресса · приближение к целевым показателям</i>")
    else:
        render_chart(system, st["series"], out, style=style)
        caption = (f"{system.emoji} <b>{_esc(system.title)}</b>\n"
                   f"<i>{'трейдерский вид' if style == 'trader' else 'стилизованный вид'}"
                   f" · индикаторы Welles Wilder</i>")
    _call_photo(chat_id, str(out), caption, kb_main(system))


# ------------------------------------------------------------------ callbacks
def _admin_callback(chat_id: int, data: str, message_id: int | None):
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    if action == "":
        return screen_admin(chat_id, message_id)
    if action == "users":
        return screen_admin_users(chat_id,
                                  int(parts[2]) if len(parts) > 2 else 0,
                                  message_id)
    if action == "view" or action == "pub":
        uid = int(parts[2])
        if action == "pub":
            u = DB.get_user(uid)
            if u:
                DB.set_public(uid, not u.is_public)
        return screen_admin_user(chat_id, uid, message_id=message_id)
    if action == "reset":
        uid = int(parts[2])
        DB.reset_progress(uid)
        return send(chat_id, f"♻️ Прогресс пользователя <code>{uid}</code> "
                             f"сброшен.", kb_admin_user(uid))
    if action == "del":
        uid = int(parts[2])
        PENDING[chat_id] = {"action": "admin_del_confirm", "uid": uid}
        return edit(chat_id, message_id,
                    f"🗑 Удалить пользователя <code>{uid}</code> вместе с "
                    f"прогрессом? Это необратимо.\n\nНапиши <b>ДА</b> для "
                    f"подтверждения или /cancel.", 
                    {"inline_keyboard": [[{"text": "Отмена",
                                           "callback_data": f"admin:view:{uid}"}]]})
    if action == "find":
        return screen_admin_find(chat_id, message_id=message_id)
    if action == "log":
        return screen_admin_log(chat_id, message_id)
    if action == "broadcast":
        return screen_admin_broadcast(chat_id, message_id)
    return screen_admin(chat_id, message_id)


def on_callback(cb: dict):
    data = cb.get("data", "")
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")
    user = cb.get("from", {})
    uid = user.get("id", chat_id)
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
    if data == "users":
        return screen_users(chat_id, message_id)
    if data == "profile":
        return screen_profile(chat_id, message_id)
    if data == "admin" or data.startswith("admin:"):
        if not _is_admin(uid):
            return send(chat_id, "⛔️ Команда только для администратора.")
        return _admin_callback(chat_id, data, message_id)
    if data == "dev" or data.startswith("dev:"):
        if not _is_admin(uid):
            return send(chat_id, "⛔️ Чат доступен только администратору.")
        if data == "dev:clear":
            CHAT_HISTORY.pop(uid, None)
            return send(chat_id, "🧹 История чата очищена.", kb_dev())
        DEV_ON.add(uid)
        return screen_dev(chat_id, message_id)
    if data.startswith("privacy:"):
        flag = data.split(":", 1)[1] == "1"
        DB.set_public(chat_id, flag)
        return screen_profile(chat_id, message_id)
    if data.startswith("board"):
        parts = data.split(":", 1)
        sid = parts[1] if len(parts) > 1 else None
        return screen_board(chat_id, None if sid in (None, "all") else sid,
                            message_id)
    if data.startswith("week:"):
        return screen_week(chat_id, int(data.split(":", 1)[1]), message_id)
    if data.startswith("chart:"):
        return send_chart(chat_id, data.split(":", 1)[1])
    if data.startswith("mark:"):
        d = int(data.split(":", 1)[1])
        user_obj, system = _user_and_system(chat_id)
        if not system:
            return screen_systems(chat_id, message_id)
        DB.set_done(chat_id, system.id, d, True)
        return screen_today(chat_id, message_id)
    if data.startswith("unmark:"):
        d = int(data.split(":", 1)[1])
        user_obj, system = _user_and_system(chat_id)
        if not system:
            return screen_systems(chat_id, message_id)
        DB.set_done(chat_id, system.id, d, False)
        return screen_today(chat_id, message_id)
    if data.startswith("note:"):
        d = int(data.split(":", 1)[1])
        if not _user_and_system(chat_id)[1]:
            return screen_systems(chat_id, message_id)
        PENDING[chat_id] = {"action": "note", "day": d}
        edit(chat_id, message_id,
             f"✍️ Напиши короткую заметку по дню {d} (1–3 строки) и отправь "
             f"сообщением. Или /cancel.",
             {"inline_keyboard": [[{"text": "Отмена", "callback_data": "today"}]]})
        return
    if data == "advise":
        user_obj, system = _user_and_system(chat_id)
        if not system:
            return screen_systems(chat_id, message_id)
        st = DB.stats(chat_id, system.id)
        d = next((x for x in range(1, TOTAL_DAYS + 1) if not st["series"][x - 1]), 1)
        day = system.day(d)
        advice, used = llm_ask(system, "Как не сорваться и выполнить сегодняшний день?",
                               f"День {d}: {day.action}")
        tag = "LLM" if used else "офлайн-режим (без API-ключа)"
        return send_md(chat_id, f"💡 <b>Совет</b> <i>({tag})</i>\n\n", advice,
                       kb_back_menu())


DEV_ON: set[int] = set()  # админы, у кого включён чат-режим с LLM


def _handle_pending(chat_id: int, pend: dict, text: str) -> bool:
    """Обработать ожидаемый ввод. True — ввод был поглощён."""
    action = pend.get("action")
    if action == "note":
        user_obj, system = _user_and_system(chat_id)
        if system:
            DB.set_done(chat_id, system.id, pend["day"], True, note=text)
            send(chat_id, f"📝 Заметка к дню {pend['day']} сохранена.")
            screen_today(chat_id)
        return True
    if action == "admin_find":
        screen_admin_find(chat_id, text)
        return True
    if action == "admin_broadcast":
        sent = 0
        for u in DB.all_users(limit=100000):
            if send(u["chat_id"], f"📣 {_esc(text)}").get("ok"):
                sent += 1
        send(chat_id, f"📣 Отправлено: <b>{sent}</b> из "
                      f"{DB.overview()['users']}.", kb_admin())
        return True
    if action == "admin_del_confirm":
        uid = pend["uid"]
        if text.strip().lower() in ("да", "yes", "y", "д"):
            DB.delete_user(uid)
            send(chat_id, f"🗑 Пользователь <code>{uid}</code> удалён.",
                 kb_admin())
        else:
            send(chat_id, "Ок, не удаляю.", kb_admin())
        return True
    return False


# -------------------------------------------------------------------- message
def on_message(msg: dict):
    chat_id = msg.get("chat", {}).get("id")
    user = msg.get("from", {})
    text = (msg.get("text") or "").strip()
    uid = user.get("id", chat_id)
    DB.touch(chat_id, chat_id, user.get("first_name", ""),
             user.get("username", ""))

    if chat_id in PENDING and not text.startswith("/"):
        pend = PENDING.pop(chat_id)
        if _handle_pending(chat_id, pend, text):
            return

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
        style = "trader"
        if len(parts) > 1:
            arg = parts[1].lower()
            if arg in ("styled", "style", "стиль"):
                style = "styled"
            elif arg in ("radar", "радар", "tcas"):
                style = "radar"
        return send_chart(chat_id, style)
    if text.startswith("/systems"):
        return screen_systems(chat_id)
    if text.startswith("/users"):
        return screen_users(chat_id)
    if text.startswith("/board") or text.startswith("/leaders"):
        return screen_board(chat_id)
    if text.startswith("/profile"):
        return screen_profile(chat_id)
    if text.startswith("/admin"):
        if not _is_admin(uid):
            return send(chat_id, "⛔️ Команда только для администратора.")
        return screen_admin(chat_id)
    if text.startswith("/dev") or text.startswith("/llm"):
        if not _is_admin(uid):
            return send(chat_id, "⛔️ Чат доступен только администратору.")
        DEV_ON.add(uid)
        return screen_dev(chat_id)
    if text.startswith("/cancel"):
        PENDING.pop(chat_id, None)
        DEV_ON.discard(uid)
        return send(chat_id, "Ок, отменено.", kb_back_menu())
    if text.startswith("/help"):
        return send(chat_id,
                    "<b>Команды</b>\n"
                    "/start — выбрать систему\n"
                    "/today — текущий день\n"
                    "/progress — прогресс и индикаторы\n"
                    "/chart [styled|radar] — график прогресса\n"
                    "/systems — сменить систему\n"
                    "/users — участники\n"
                    "/board — таблица лидеров\n"
                    "/profile — профиль и видимость (публичный/приватный)\n"
                    "/admin — админ-панель (только для администратора)\n"
                    "/dev — чат с LLM о функционале (только админ)\n"
                    "/cancel — отменить ввод\n\n"
                    "Днём можно отметить выполнение кнопкой и добавить заметку.\n"
                    "Проект: https://github.com/j0k/21day_system",
                    kb_back_menu())
    user_obj, system = _user_and_system(chat_id)
    # Свободный чат с LLM (админ): любой текст уходит в диалог.
    if uid in DEV_ON and _is_admin(uid):
        hist = CHAT_HISTORY.setdefault(uid, [])
        hist.append({"role": "user", "content": text})
        send(chat_id, "💬 <i>думаю…</i>")
        answer, used = llm_chat_dev(hist, text, _project_context())
        hist.append({"role": "assistant", "content": answer})
        del hist[:-12]
        tag = "LLM" if used else "ошибка/офлайн"
        return send_md(chat_id, f"🤖 <i>({tag})</i>\n", answer, kb_dev())
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
    if config.LLM_ENABLED:
        print("   ключ:", config.LLM_KEY_NAME,
              "| base_url:", config.OPENAI_BASE_URL,
              "| модель:", config.OPENAI_MODEL)
    else:
        print("   LLM выключен (нет ключа) — работает офлайн-совет.")
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
