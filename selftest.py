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
for data in ("progress", "week:1", "week:2", "week:3", "menu", "today"):
    CAPTURED.clear()
    bot.on_callback({"id": "1", "data": data,
                     "message": {"chat": {"id": CHAT}, "message_id": 1}, "from": {}})
    assert CAPTURED, data

# 6. Команды.
for txt in ("/today", "/progress", "/help", "/systems", "/cancel", "/menu"):
    bot.on_message({"chat": {"id": CHAT}, "from": {}, "text": txt})

# 7. График (трейдерский/стилизованный) — файл создан.
for style in ("trader", "styled"):
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

print("БД:", bot.DB.path)
print("Все офлайн-тесты экранов прошли.")
print("Пример индикаторов:\n")
from indicators import indicator_block  # noqa: E402
print(indicator_block(bot.DB.stats(CHAT, "skills")))
