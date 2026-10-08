# -*- coding: utf-8 -*-
"""Хранилище прогресса в файле SQLite.

Таблицы:
* ``users``    — кто пишет боту и какую систему выбрал;
* ``progress`` — результат по каждому дню каждой системы;
* ``log``      — журнал событий (кто что нажал).

Все результаты лежат в одном файле (по умолчанию ``data/21day.sqlite3``).
"""
from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from systems import SYSTEMS, TOTAL_DAYS

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    chat_id     INTEGER,
    first_name  TEXT,
    username    TEXT,
    system_id   TEXT,
    started_at  TEXT,
    last_seen   TEXT
);
CREATE TABLE IF NOT EXISTS progress (
    user_id     INTEGER NOT NULL,
    system_id   TEXT    NOT NULL,
    day         INTEGER NOT NULL,
    done        INTEGER NOT NULL DEFAULT 0,
    minutes     INTEGER NOT NULL DEFAULT 0,
    note        TEXT    NOT NULL DEFAULT '',
    updated_at  TEXT,
    PRIMARY KEY (user_id, system_id, day)
);
CREATE TABLE IF NOT EXISTS log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT,
    user_id  INTEGER,
    event    TEXT,
    detail   TEXT
);
"""


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class User:
    user_id: int
    chat_id: int
    first_name: str
    username: str
    system_id: str | None
    started_at: str | None


class Storage:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            # WAL ускоряет запись примерно втрое и позволяет читать во время
            # записи; busy_timeout спасает от «database is locked».
            try:
                self._db.execute("PRAGMA journal_mode=WAL")
                self._db.execute("PRAGMA synchronous=NORMAL")
                self._db.execute("PRAGMA busy_timeout=5000")
            except sqlite3.DatabaseError:
                pass
            self._db.executescript(_SCHEMA)
            self._db.commit()

    # ------------------------------------------------------------- users
    def touch(self, user_id: int, chat_id: int, first_name: str = "",
              username: str = "") -> User:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            if row is None:
                self._db.execute(
                    "INSERT INTO users(user_id, chat_id, first_name, username,"
                    " system_id, started_at, last_seen)"
                    " VALUES(?,?,?,?,NULL,?,?)",
                    (user_id, chat_id, first_name, username, _now(), _now()))
                self._db.commit()
            else:
                self._db.execute(
                    "UPDATE users SET chat_id=?, first_name=?, username=?,"
                    " last_seen=? WHERE user_id=?",
                    (chat_id, first_name, username, _now(), user_id))
                self._db.commit()
        return self.get_user(user_id)

    def get_user(self, user_id: int) -> User | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            return None
        return User(row["user_id"], row["chat_id"], row["first_name"] or "",
                    row["username"] or "", row["system_id"], row["started_at"])

    def set_system(self, user_id: int, system_id: str) -> None:
        if system_id not in SYSTEMS:
            raise KeyError(system_id)
        with self._lock:
            self._db.execute(
                "UPDATE users SET system_id=?, started_at=? WHERE user_id=?",
                (system_id, _now(), user_id))
            self._db.commit()
        self.log(user_id, "select_system", system_id)

    # ---------------------------------------------------------- progress
    def set_done(self, user_id: int, system_id: str, day: int,
                 done: bool, note: str | None = None) -> None:
        minutes = SYSTEMS[system_id].day(day).minutes
        with self._lock:
            self._db.execute(
                "INSERT INTO progress(user_id, system_id, day, done, minutes,"
                " note, updated_at) VALUES(?,?,?,?,?,?,?)"
                " ON CONFLICT(user_id, system_id, day) DO UPDATE SET"
                " done=excluded.done, minutes=excluded.minutes,"
                " note=COALESCE(?, progress.note),"
                " updated_at=excluded.updated_at",
                (user_id, system_id, day, int(done), minutes, note or "",
                 _now(), note))
            self._db.commit()
        self.log(user_id, "mark", f"{system_id} day={day} done={int(done)}")

    def get_progress(self, user_id: int, system_id: str) -> dict[int, dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM progress WHERE user_id=? AND system_id=?",
                (user_id, system_id)).fetchall()
        return {r["day"]: {"done": bool(r["done"]),
                           "minutes": r["minutes"],
                           "note": r["note"],
                           "updated_at": r["updated_at"]} for r in rows}

    def completion_series(self, user_id: int, system_id: str) -> list[int]:
        """0/1 по дням 1..21 — выполнено или нет."""
        prog = self.get_progress(user_id, system_id)
        return [1 if prog.get(d, {}).get("done") else 0
                for d in range(1, TOTAL_DAYS + 1)]

    def stats(self, user_id: int, system_id: str) -> dict:
        series = self.completion_series(user_id, system_id)
        done = sum(series)
        # текущая серия подряд
        streak = 0
        for v in series:
            streak = streak + 1 if v else 0
        best = cur = 0
        for v in series:
            cur = cur + 1 if v else 0
            best = max(best, cur)
        minutes = sum(SYSTEMS[system_id].day(d).minutes
                      for d in range(1, TOTAL_DAYS + 1) if series[d - 1])
        # сколько дней открыто (до последнего дня с отметкой или сегодня)
        considered = [d for d in range(1, TOTAL_DAYS + 1) if series[d - 1]]
        last_day = max(considered) if considered else 0
        out = {"done": done, "total": TOTAL_DAYS,
               "pct": round(100 * done / TOTAL_DAYS),
               "streak": streak, "best_streak": best,
               "minutes": minutes, "last_day": last_day,
               "series": series}
        # индикаторы в стиле Welles Wilder добавляются здесь, чтобы были
        # доступны в любом экране бота («видны в каждый момент»).
        try:
            from indicators import compute
            out.update(compute(series))
        except Exception:  # noqa: BLE001
            pass
        return out

    # --------------------------------------------------------------- log
    def log(self, user_id: int, event: str, detail: str = "") -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO log(ts, user_id, event, detail) VALUES(?,?,?,?)",
                (_now(), user_id, event, detail))
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()
