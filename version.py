# -*- coding: utf-8 -*-
"""Единый источник версии приложения — как в Codellake.

Числовое ядро ``CORE`` — четыре сегмента **A.B.C.D**, привязанные к уровням
дерева целей (Trac/Agent's Tower):

    L0 (миссия)    -> A   +1.0.0.0
    L1 (эпик)      -> B   +0.1.0.0
    L2 (задача)    -> C   +0.0.1.0
    L3 (подзадача) -> D   +0.0.0.1

Аддитивно: закрытие тикета увеличивает только свой сегмент, нижние НЕ
сбрасываются (например, ``1.0.3.0`` --L1--> ``1.1.3.0``). Закрытие L0 —
это релиз: номер пересобирается в чистый (путь ``0.x.y.z`` -> ``1.0.0.0``).

Текущий релиз — первый стабильный: **1.0-Beta** (публичная бета).
Числовое ядро — ``1.0.0.0``, канал — ``Beta``. Дальнейшая работа растёт от
``1.0``; предрелизные сборки помечаются каналом (Beta / RC).

Единственное место, куда вписывается версия. Всё остальное (бот, лендинг,
документация, git-теги) берёт её отсюда — см. ``news.py`` для changelog.
"""
from __future__ import annotations

# --- единственный источник -------------------------------------------------
VERSION = "1.0-Beta"        # человекочитаемая версия: <ядро>-<канал>
CORE = "1.0.0.0"            # числовое ядро A.B.C.D (bump и сравнения)
CHANNEL = "Beta"           # канал релиза: Beta | RC | Stable
VERSION_DATE = "2026-10-08"  # дата релиза, ISO (менять вместе с VERSION)

_LEVEL_INDEX = {"l0": 0, "l1": 1, "l2": 2, "l3": 3}
_BUILD_TIME_CACHE: str | None = None


def build_time() -> str:
    """Время сборки/коммита загруженного кода, до секунды.

    Сначала берём время git-коммита HEAD (настоящее время сборки); если git
    недоступен (установленный пакет, скачанный zip) — mtime этого файла.
    Кэшируется после первого вызова (дёшево для баннеров)."""
    global _BUILD_TIME_CACHE
    if _BUILD_TIME_CACHE is not None:
        return _BUILD_TIME_CACHE
    import datetime
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent
    ts = ""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "-1",
             "--date=format:%Y-%m-%d %H:%M:%S", "--format=%cd"],
            capture_output=True, timeout=2)
        if out.returncode == 0:
            ts = (out.stdout or b"").decode("utf-8", "replace").strip()
    except Exception:  # noqa: BLE001 — нет git / не репозиторий → фолбэк
        ts = ""
    if not ts:
        try:
            mtime = Path(__file__).stat().st_mtime
            ts = datetime.datetime.fromtimestamp(mtime).strftime(
                "%Y-%m-%d %H:%M:%S")
        except OSError:
            ts = VERSION_DATE
    _BUILD_TIME_CACHE = ts
    return ts


def version_str() -> str:
    """Короткая версия для подписей и бейджей («1.0-Beta»)."""
    return VERSION


def version_line() -> str:
    """Одна строка для баннера и команды /version: номер, дата, сборка."""
    return f"21day_system {VERSION} ({VERSION_DATE}) · сборка {build_time()}"


def core_of(version: str | None = None) -> str:
    """Числовое ядро A.B.C.D из версии (``1.0-Beta`` -> ``1.0.0.0``).

    Если передано уже числовое ядро — возвращает его же, дополнив нулями."""
    base = (version or CORE).split("-", 1)[0]
    parts = [int(x) for x in base.split(".")]
    while len(parts) < 4:
        parts.append(0)
    return ".".join(str(p) for p in parts[:4])


def bump(version: str, level: str) -> str:
    """Вернуть ядро A.B.C.D с увеличенным сегментом уровня ``l0..l3``.

    Аддитивно: нижние сегменты сохраняются. Принимает и «1.0-Beta», и
    «1.0.0.0» — канал отбрасывается."""
    idx = _LEVEL_INDEX.get(str(level).lower())
    if idx is None:
        raise ValueError(f"unknown level: {level!r} (use l0/l1/l2/l3)")
    parts = [int(x) for x in core_of(version).split(".")]
    parts[idx] += 1
    return ".".join(str(p) for p in parts)


if __name__ == "__main__":
    print(version_line())
    print("ядро:", core_of(), "| канал:", CHANNEL)
