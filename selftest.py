# -*- coding: utf-8 -*-
"""Офлайн-прогон экранов бота: сетевые вызовы подменяются захватом текста."""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="21day_test_"))

import bot  # noqa: E402

CAPTURED = []


def fake_call(method, params):
    CAPTURED.append((method, params.get("text", params.get("caption", ""))))
    return {"ok": True, "result": {"message_id": 1}}


def fake_photo(chat_id, path, caption, keyboard=None):
    CAPTURED.append(("sendPhoto", caption))
    assert os.path.exists(path), path
    return {"ok": True}


bot._call = fake_call
bot._call_photo = fake_photo
bot.edit = lambda chat_id, mid, text, kb=None: CAPTURED.append(("edit", text)) or {"ok": True}
bot.answer_cb = lambda cid, t="": {"ok": True}

CHAT = 555

# 1. Первый вход — выбор системы кнопкой.
bot.on_message({"chat": {"id": CHAT}, "from": {"first_name": "Юра",
               "username": "jura"}, "text": "/start"})
assert any("Выбери" in t or "21day_system" in t for _, t in CAPTURED), CAPTURED[-1]

# 2. Выбор системы кнопкой.
for sid in ("skills", "discipline", "sleep"):
    CAPTURED.clear()
    bot.on_callback({"id": "1", "data": f"sys:{sid}",
                     "message": {"chat": {"id": CHAT}, "message_id": 1},
                     "from": {"first_name": "Юра"}})
    user = bot.DB.get_user(CHAT)
    assert user.system_id == sid, user
    assert any("День 1" in t for _, t in CAPTURED), CAPTURED

# 3. Проходим всю систему 'skills' день за днём.
bot.on_callback({"id": "1", "data": "sys:skills",
                 "message": {"chat": {"id": CHAT}, "message_id": 1}, "from": {}})
CAPTURED.clear()
for day in range(1, 22):
    bot.on_callback({"id": "1", "data": f"mark:{day}",
                     "message": {"chat": {"id": CHAT}, "message_id": 1},
                     "from": {}})
st = bot.DB.stats(CHAT, "skills")
assert st["done"] == 21, st
assert st["pct"] == 100, st
assert st["minutes"] > 0

# 4. Заметка.
bot.on_callback({"id": "1", "data": "note:5",
                 "message": {"chat": {"id": CHAT}, "message_id": 1}, "from": {}})
bot.on_message({"chat": {"id": CHAT}, "from": {}, "text": "мысль дня"})
assert bot.DB.get_progress(CHAT, "skills")[5]["note"] == "мысль дня"

# 5. Экраны прогресса, недель, меню.
for data in ("progress", "week:1", "week:2", "week:3", "menu", "today",
             "users", "board", "board:skills", "board:all", "profile"):
    CAPTURED.clear()
    bot.on_callback({"id": "1", "data": data,
                     "message": {"chat": {"id": CHAT}, "message_id": 1}, "from": {}})
    assert CAPTURED, data

# 5b. Профиль: по умолчанию приватный -> в лидерах "Private User"; затем публичный.
u = bot.DB.get_user(CHAT)
assert u.is_public is False, u
bot.on_callback({"id": "1", "data": "privacy:1",
                 "message": {"chat": {"id": CHAT}, "message_id": 1}, "from": {}})
assert bot.DB.get_user(CHAT).is_public is True
boards = bot.DB.leaderboard("skills", limit=5)
assert boards and boards[0]["public"] is True, boards
assert boards[0]["name"] == "Юра", boards
bot.on_callback({"id": "1", "data": "privacy:0",
                 "message": {"chat": {"id": CHAT}, "message_id": 1}, "from": {}})
boards = bot.DB.leaderboard("skills", limit=5)
assert boards and boards[0]["name"] == "Private User", boards

# 6. Команды.
for txt in ("/today", "/progress", "/help", "/systems", "/cancel", "/menu"):
    bot.on_message({"chat": {"id": CHAT}, "from": {}, "text": txt})

# 7. График (трейдерский/стилизованный/радар) — файл создан.
for style in ("trader", "styled", "radar"):
    CAPTURED.clear()
    bot.on_callback({"id": "1", "data": f"chart:{style}",
                     "message": {"chat": {"id": CHAT}, "message_id": 1}, "from": {}})
    assert any(m == "sendPhoto" for m, _ in CAPTURED), style

# 8. Совет: работает в любом режиме (LLM при ключе, иначе — офлайн).
CAPTURED.clear()
bot.on_callback({"id": "1", "data": "advise",
                 "message": {"chat": {"id": CHAT}, "message_id": 1}, "from": {}})
tag = "LLM" if bot.config.LLM_ENABLED else "офлайн"
assert any(tag in t for _, t in CAPTURED), (tag, CAPTURED[-1])
print("Режим советника:", "LLM" if bot.config.LLM_ENABLED else "офлайн")

# 9. Админка и диалог с LLM (доступно только администратору).
ADMIN = min(bot.config.ADMIN_IDS)
OUTSIDER = 777001
if OUTSIDER in bot.config.ADMIN_IDS:
    OUTSIDER = 777002
bot.DB.touch(ADMIN, ADMIN, "Admin", "admin")
bot.DB.set_system(ADMIN, "skills")

# 9a. Не-админу админка запрещена.
CAPTURED.clear()
bot.on_message({"chat": {"id": OUTSIDER}, "from": {"id": OUTSIDER},
                "text": "/admin"})
assert any("только для администратор" in t for _, t in CAPTURED), CAPTURED[-1]

# 9b. Админ открывает панель, разделы.
CAPTURED.clear()
bot.on_message({"chat": {"id": ADMIN}, "from": {"id": ADMIN}, "text": "/admin"})
assert any("Админ-панель" in t for _, t in CAPTURED), CAPTURED[-1]
for data in ("admin", "admin:users:0", "admin:log", "admin:find"):
    CAPTURED.clear()
    bot.on_callback({"id": "1", "data": data,
                     "message": {"chat": {"id": ADMIN}, "message_id": 1},
                     "from": {"id": ADMIN}})
    assert CAPTURED, data

# 9c. Поиск пользователя по имени.
bot.on_message({"chat": {"id": ADMIN}, "from": {"id": ADMIN}, "text": "Юра"})
found = bot.DB.get_user_by_name("Юра")
assert found, "поиск по имени не сработал"

# 9d. Сводка хранилища.
over = bot.DB.overview()
assert over["users"] >= 1 and "marks" in over

# 9e. Диалог с LLM: /dev включает режим, обычный текст уходит в чат.
CAPTURED.clear()
bot.on_message({"chat": {"id": ADMIN}, "from": {"id": ADMIN}, "text": "/dev"})
assert any("Чат с LLM" in t for _, t in CAPTURED), CAPTURED[-1]
CAPTURED.clear()
bot.on_message({"chat": {"id": ADMIN}, "from": {"id": ADMIN},
                "text": "Предложи, что улучшить в боте"})
assert any("🤖" in t for _, t in CAPTURED), CAPTURED[-1]
assert bot.CHAT_HISTORY.get(ADMIN), "история чата пуста"
# очистка истории
bot.on_callback({"id": "1", "data": "dev:clear",
                 "message": {"chat": {"id": ADMIN}, "message_id": 1},
                 "from": {"id": ADMIN}})
assert not bot.CHAT_HISTORY.get(ADMIN)
print("Админка и чат с LLM: ок")

print("БД:", bot.DB.path)
print("Все офлайн-тесты экранов прошли.")
print("Пример индикаторов:\n")
from indicators import indicator_block  # noqa: E402
print(indicator_block(bot.DB.stats(CHAT, "skills")))
