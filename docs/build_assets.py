# -*- coding: utf-8 -*-
"""Собрать ассеты для GitHub Pages из единственного источника версии.

Кладёт рядом с лендингом:
  * ``icon.png`` / ``icon.svg``    — из корня проекта;
  * ``version.json``               — из ``version.py`` (для бейджа на странице);
  * ``README.md`` / ``README_RU.md`` — копии для страницы-просмотрщика
    ``docs/readme.html`` (чтобы Markdown читался как страница, а не как raw-текст).

Идемпотентно; запускать после смены версии/иконки/README:

    python docs/build_assets.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import version  # noqa: E402

# 1) иконки из корня проекта
for name in ("icon.png", "icon.svg"):
    src = ROOT / name
    if src.exists():
        shutil.copy2(src, DOCS / name)
        print("assets:", name)
    else:
        print("assets: пропущено (нет)", name)

# 2) version.json для бейджа на лендинге
data = {
    "version": version.VERSION,
    "core": version.CORE,
    "channel": version.CHANNEL,
    "date": version.VERSION_DATE,
    "repo": "https://github.com/j0k/21day_system",
    "page": "https://juri-konoplev.pro/21day_system/",
}
(DOCS / "version.json").write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("assets: version.json ->", data["version"])

# 3) README-копии для docs/readme.html
for name in ("README.md", "README_RU.md"):
    src = ROOT / name
    if src.exists():
        shutil.copy2(src, DOCS / name)
        print("assets:", name)
    else:
        print("assets: пропущено (нет)", name)
