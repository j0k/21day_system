# -*- coding: utf-8 -*-
"""Офлайн-проверка версионирования, /news и команд /version+/news в боте."""
import os
import re
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="21day_ver_"))

import version  # noqa: E402
from news import collect, news_text, parse_commit  # noqa: E402

# --- 1. Версия -------------------------------------------------------------
assert version.VERSION == "1.0-Beta", version.VERSION
assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version.CORE), version.CORE
assert version.core_of() == "1.0.0.0"
assert version.core_of("1.0-Beta") == "1.0.0.0"
assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", version.VERSION_DATE)
assert version.CHANNEL in ("Beta", "RC", "Stable")
assert version.version_str() == "1.0-Beta"
assert "1.0-Beta" in version.version_line()
assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", version.build_time())
assert version.build_time() == version.build_time()  # кэш стабилен

# --- 2. Аддитивный bump по уровням -----------------------------------------
assert version.bump("1.0.0.0", "l2") == "1.0.1.0"
assert version.bump("1.0.3.0", "l1") == "1.1.3.0"
assert version.bump("1.0.3.2", "l0") == "2.0.3.2"
assert version.bump("1.0-Beta", "l3") == "1.0.0.1"
try:
    version.bump("1.0.0.0", "l9")
    raise AssertionError("bump должен падать на неизвестном уровне")
except ValueError:
    pass

# --- 3. Changelog из git-тем -----------------------------------------------
assert parse_commit("bot: add /version; v1.0.1.0") == ("1.0.1.0",
                                                       "bot: add /version")
assert parse_commit("no version here") is None
sample = [
    "docs: split README EN/RU; v1.0.2.0",
    "feat: versioning 1.0-Beta; v1.0.0.0",
    "feat: another thing; v1.0.0.0",
    "мусорный коммит без версии",
]
groups = collect(sample)
assert list(groups) == ["1.0.2.0", "1.0.0.0"], list(groups)
assert len(groups["1.0.0.0"]) == 2
txt = news_text("", subjects=sample, current="1.0.0.0")
assert "v1.0.0.0" in txt and "another thing" in txt
assert "v1.0.2.0" in news_text("1.0.2.0", subjects=sample)
assert "Версии" in news_text("list", subjects=sample)
assert "не найдена" in news_text("9.9.9.9", subjects=sample)
assert "недоступна" in news_text(subjects=[])

# --- 4. Команды бота /version и /news --------------------------------------
import bot  # noqa: E402

CAPTURED = []


def fake_call(method, params):
    CAPTURED.append((method, params.get("text", "")))
    return {"ok": True, "result": {"message_id": 1}}


bot._call = fake_call
CHAT = 777

CAPTURED.clear()
bot.on_message({"chat": {"id": CHAT}, "from": {"first_name": "Т", "id": CHAT},
                "text": "/version"})
assert CAPTURED and "1.0-Beta" in CAPTURED[-1][1], CAPTURED[-1]

CAPTURED.clear()
bot.on_message({"chat": {"id": CHAT}, "from": {"first_name": "Т", "id": CHAT},
                "text": "/news"})
assert CAPTURED and ("v1.0" in CAPTURED[-1][1] or "недоступна"
                     in CAPTURED[-1][1]), CAPTURED[-1]

print("VERSION OK — 1.0-Beta, bump аддитивен, /news и /version отвечают.")
