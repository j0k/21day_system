# -*- coding: utf-8 -*-
"""Демонстрация: что именно бот присылает по прогрессу (текст + график)."""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="21day_demo_")

import bot  # noqa: E402

SENT = []
bot._call = lambda m, p: SENT.append(("msg", p.get("text", ""))) or {"ok": True}
bot.edit = lambda c, mid, t, kb=None: SENT.append(("edit", t)) or {"ok": True}
bot.answer_cb = lambda c, t="": {"ok": True}


def photo(chat_id, path, caption, keyboard=None):
    SENT.append(("photo", caption + "  [файл: " + os.path.basename(path) + ", "
                 + str(os.path.getsize(path)) + " байт]"))
    return {"ok": True}


bot._call_photo = photo
CHAT = 777

bot.on_message({"chat": {"id": CHAT}, "from": {"first_name": "Юра"},
                "text": "/start"})
bot.on_callback({"id": "1", "data": "sys:discipline",
                 "message": {"chat": {"id": CHAT}, "message_id": 1}, "from": {}})
for d in (1, 2, 3, 5, 6, 8):
    bot.on_callback({"id": "1", "data": f"mark:{d}",
                     "message": {"chat": {"id": CHAT}, "message_id": 1}, "from": {}})

SENT.clear()
print("=" * 70)
print("ЧТО ПРИХОДИТ ПО КОМАНДЕ /progress")
print("=" * 70)
bot.on_message({"chat": {"id": CHAT}, "from": {}, "text": "/progress"})
for kind, text in SENT:
    print(text)

for style in ("trader", "styled"):
    SENT.clear()
    print("\n" + "=" * 70)
    print(f"ЧТО ПРИХОДИТ ПО ГРАФИКУ ({style})")
    print("=" * 70)
    bot.on_message({"chat": {"id": CHAT}, "from": {},
                    "text": f"/chart {style}" if style == "styled" else "/chart"})
    for kind, text in SENT:
        print(f"[{kind}] {text}")
