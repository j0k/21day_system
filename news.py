# -*- coding: utf-8 -*-
"""/news — что изменилось в версии. Источник истины — git-лог.

Соглашение о коммитах (как в Codellake): тема заканчивается ``; vX.Y.Z.W`` и
несёт id тикета плюс человеческую суть. Значит, git-лог и есть changelog.

Транспорт-нейтрально (чистое форматирование + один вызов git), чтобы бот,
лендинг и десктоп-трей делили одну реализацию.
"""
from __future__ import annotations

import re
import subprocess
from collections import OrderedDict
from pathlib import Path

__all__ = ["parse_commit", "git_subjects", "collect", "news_text"]

# Хвост "; vA.B.C.D", закрывающий тему коммита (см. version.py).
_VER_RE = re.compile(r";\s*v(\d+\.\d+\.\d+\.\d+)\s*$")


def parse_commit(subject: str) -> tuple[str, str] | None:
    """(версия, суть) из темы, оканчивающейся ``; vX.Y.Z.W``; иначе None."""
    s = subject.strip()
    m = _VER_RE.search(s)
    if not m:
        return None
    return m.group(1), s[: m.start()].strip().rstrip(";").strip()


def git_subjects(limit: int = 2000, root: Path | None = None) -> list[str]:
    """Свежие темы коммитов, новые сверху (пусто при любой ошибке git)."""
    root = root or Path(__file__).resolve().parent
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", f"-{limit}", "--format=%s"],
            capture_output=True, timeout=5)
        # Кодировку задаём ЯВНО: git пишет темы в UTF-8, а text=True декодировал
        # бы локалью (на Windows это cp1251) — и русский changelog превращался
        # бы в «Р І Рє...». Декодируем байты вручную.
        if out.returncode == 0:
            text = (out.stdout or b"").decode("utf-8", "replace")
            return [ln for ln in text.splitlines() if ln.strip()]
    except Exception:  # noqa: BLE001 — нет git / не репозиторий → нет новостей
        pass
    return []


def collect(subjects) -> "OrderedDict[str, list[str]]":
    """версия -> [сути], новые сверху, порядок лога внутри версии сохранён."""
    groups: "OrderedDict[str, list[str]]" = OrderedDict()
    for s in subjects:
        pv = parse_commit(s)
        if pv is None:
            continue
        version, summary = pv
        groups.setdefault(version, []).append(summary)
    return groups


def _match(groups, query: str) -> list[str]:
    """Точная версия, иначе ключи, начинающиеся с запроса."""
    q = query.strip().lstrip("v")
    if q in groups:
        return [q]
    return [v for v in groups if v.startswith(q)]


def _format_version(version: str, summaries, note: str = "") -> str:
    head = f"📦 v{version}" + (f"  {note}" if note else "")
    return "\n".join([head] + [f" • {s}" for s in summaries])


def _format_list(groups, limit: int = 15) -> str:
    lines = ["Версии (свежие сверху):"]
    for v, summaries in list(groups.items())[:limit]:
        lines.append(f" v{v} — {summaries[0]}")
    lines.append("/news <version> — подробнее по версии.")
    return "\n".join(lines)


def news_text(arg: str = "", *, subjects=None, current: str = "") -> str:
    """Отрендерить /news.

    ``arg``: '' → текущая/последняя версия · 'list' → список версий ·
    иначе точная или префиксная версия. ``current`` — запущенная VERSION
    (чтобы голый /news показал, что работает). ``subjects`` можно подменить
    в тестах."""
    groups = collect(subjects if subjects is not None else git_subjects())
    if not groups:
        return ("История версий недоступна (нет git-лога с '; vX.Y.Z.W'). "
                "Текущая версия: 1.0-Beta.")
    a = (arg or "").strip()
    if a.lower() in ("list", "-l", "--list", "версии", "all"):
        return _format_list(groups)
    if not a:
        if current and current in groups:
            return _format_version(current, groups[current])
        latest = next(iter(groups))
        note = (f"(текущая v{current} ещё не в git-логе — показываю последнюю)"
                if current else "")
        return _format_version(latest, groups[latest], note=note)
    matches = _match(groups, a)
    if not matches:
        return f"Версия {a} не найдена. /news list — список версий."
    if len(matches) > 1:
        return (f"Неоднозначно «{a}»: "
                + ", ".join("v" + m for m in matches[:8]) + " — уточни.")
    return _format_version(matches[0], groups[matches[0]])
