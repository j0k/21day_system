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
    is_public   INTEGER NOT NULL DEFAULT 0,
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


def _streaks(series: list[int]) -> tuple[int, int]:
    """(текущая серия, лучшая серия) по ряду 0/1."""
    cur = best = 0
    for v in series:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return cur, best


def _trailing_streak(series: list[int]) -> int:
    """Дней подряд до последнего отмеченного дня (будущие пропуски не в счёт).

    В лидерборде важно, держит ли человек ритм сейчас: пустые дни впереди
    не должны обнулять серию.
    """
    considered = [i for i, v in enumerate(series) if v]
    if not considered:
        return 0
    last = max(considered)
    n = 0
    for v in reversed(series[:last + 1]):
        if v:
            n += 1
        else:
            break
    return n



@dataclass
class User:
    user_id: int
    chat_id: int
    first_name: str
    username: str
    system_id: str | None
    started_at: str | None
    is_public: bool = False
    last_seen: str | None = None


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
            # миграция: колонка is_public появилась позже — добавим при нужде
            cols = {r["name"] for r in
                    self._db.execute("PRAGMA table_info(users)").fetchall()}
            if "is_public" not in cols:
                self._db.execute(
                    "ALTER TABLE users ADD COLUMN is_public INTEGER"
                    " NOT NULL DEFAULT 0")
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
                # не затираем сохранённое имя/username пустыми значениями
                self._db.execute(
                    "UPDATE users SET chat_id=?,"
                    " first_name=CASE WHEN ?<>'' THEN ? ELSE first_name END,"
                    " username=CASE WHEN ?<>'' THEN ? ELSE username END,"
                    " last_seen=? WHERE user_id=?",
                    (chat_id, first_name, first_name, username, username,
                     _now(), user_id))
                self._db.commit()
        return self.get_user(user_id)

    def get_user(self, user_id: int) -> User | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            return None
        return User(row["user_id"], row["chat_id"], row["first_name"] or "",
                    row["username"] or "", row["system_id"], row["started_at"],
                    bool(row["is_public"]), row["last_seen"])

    def set_system(self, user_id: int, system_id: str) -> None:
        if system_id not in SYSTEMS:
            raise KeyError(system_id)
        with self._lock:
            self._db.execute(
                "UPDATE users SET system_id=?, started_at=? WHERE user_id=?",
                (system_id, _now(), user_id))
            self._db.commit()
        self.log(user_id, "select_system", system_id)

    def set_public(self, user_id: int, is_public: bool) -> None:
        """Публичный профиль: показывать имя в таблице лидеров."""
        with self._lock:
            self._db.execute(
                "UPDATE users SET is_public=? WHERE user_id=?",
                (int(is_public), user_id))
            self._db.commit()
        self.log(user_id, "set_public", "1" if is_public else "0")

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

    # ------------------------------------------------------------ лидеры
    def participants(self) -> int:
        """Сколько всего человек писали боту."""
        with self._lock:
            return self._db.execute(
                "SELECT COUNT(*) AS n FROM users").fetchone()["n"]

    def leaderboard(self, system_id: str | None = None, limit: int = 10
                    ) -> list[dict]:
        """Таблица лидеров.

        Ранжируем по числу выполненных дней выбранной системы (или лучшей из
        трёх, если система не задана), затем по текущей серии и по сумме
        минут. Возвращаем ``[{name, username, user_id, system_id, done, pct,
        streak, minutes, rank}]``.
        """
        with self._lock:
            users = self._db.execute(
                "SELECT user_id, first_name, username, system_id, is_public"
                " FROM users").fetchall()
            rows = self._db.execute(
                "SELECT user_id, system_id, COUNT(*) AS n,"
                " COALESCE(SUM(minutes),0) AS mins FROM progress"
                " WHERE done=1 GROUP BY user_id, system_id").fetchall()
            series_rows = self._db.execute(
                "SELECT user_id, system_id, day, done FROM progress"
                " ORDER BY user_id, system_id, day").fetchall()

        # серии: собрать ряды 0/1 по каждому (пользователь, система)
        marks: dict[tuple[int, str], dict[int, int]] = {}
        for r in series_rows:
            marks.setdefault((r["user_id"], r["system_id"]), {})[r["day"]] = \
                1 if r["done"] else 0

        agg: dict[tuple[int, str], dict] = {}
        for r in rows:
            agg[(r["user_id"], r["system_id"])] = {
                "done": r["n"], "minutes": r["mins"]}

        out = []
        for u in users:
            best = None
            candidates = ([system_id] if system_id in SYSTEMS
                          else list(SYSTEMS.keys()))
            for sid in candidates:
                key = (u["user_id"], sid)
                info = agg.get(key)
                if not info:
                    continue
                series = [marks.get(key, {}).get(d, 0)
                          for d in range(1, TOTAL_DAYS + 1)]
                _cur, best_streak = _streaks(series)
                streak = _trailing_streak(series)
                cand = {"system_id": sid, "done": info["done"],
                        "minutes": info["minutes"], "streak": streak,
                        "best_streak": best_streak,
                        "pct": round(100 * info["done"] / TOTAL_DAYS)}
                if best is None or (cand["done"], cand["streak"],
                                    cand["minutes"]) > (
                                    best["done"], best["streak"],
                                    best["minutes"]):
                    best = cand
            if best is None:
                continue
            public = bool(u["is_public"])
            if public:
                name = (u["first_name"] or (u["username"] and "@" + u["username"])
                        or f"id{u['user_id']}")
            else:
                name = "Private User"
            out.append({"user_id": u["user_id"], "name": name,
                        "username": u["username"] or "", "public": public,
                        **best})
        out.sort(key=lambda x: (-x["done"], -x["streak"], -x["minutes"],
                                x["name"].lower()))
        for i, row in enumerate(out, 1):
            row["rank"] = i
        return out[:limit]

    # ----------------------------------------------------------- админка
    def overview(self) -> dict:
        """Сводка по всей базе для админ-панели."""
        with self._lock:
            users = self._db.execute(
                "SELECT COUNT(*) AS n FROM users").fetchone()["n"]
            public = self._db.execute(
                "SELECT COUNT(*) AS n FROM users WHERE is_public=1"
            ).fetchone()["n"]
            marks = self._db.execute(
                "SELECT COUNT(*) AS n FROM progress WHERE done=1"
            ).fetchone()["n"]
            logs = self._db.execute(
                "SELECT COUNT(*) AS n FROM log").fetchone()["n"]
            by_system = {r["system_id"]: r["n"] for r in self._db.execute(
                "SELECT system_id, COUNT(*) AS n FROM progress WHERE done=1"
                " GROUP BY system_id")}
            selected = {r["system_id"]: r["n"] for r in self._db.execute(
                "SELECT system_id, COUNT(*) AS n FROM users"
                " WHERE system_id IS NOT NULL GROUP BY system_id")}
        return {"users": users, "public": public, "marks": marks,
                "logs": logs, "by_system": by_system, "selected": selected}

    def all_users(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Список пользователей с прогрессом по выбранной системе."""
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM users ORDER BY last_seen DESC LIMIT ? OFFSET ?",
                (limit, offset)).fetchall()
        out = []
        for r in rows:
            sid = r["system_id"]
            done = 0
            if sid in SYSTEMS:
                series = self.completion_series(r["user_id"], sid)
                done = sum(series)
            out.append({
                "user_id": r["user_id"], "chat_id": r["chat_id"],
                "first_name": r["first_name"] or "", "username": r["username"] or "",
                "system_id": sid, "is_public": bool(r["is_public"]),
                "started_at": r["started_at"] or "",
                "last_seen": r["last_seen"] or "", "done": done,
            })
        return out

    def get_user_by_name(self, query: str) -> list[User]:
        """Найти пользователя по username, имени или id."""
        q = query.strip().lstrip("@")
        with self._lock:
            if q.isdigit():
                rows = self._db.execute(
                    "SELECT * FROM users WHERE user_id=? OR chat_id=?",
                    (int(q), int(q))).fetchall()
            else:
                rows = self._db.execute(
                    "SELECT * FROM users WHERE username LIKE ?"
                    " OR first_name LIKE ? ORDER BY last_seen DESC LIMIT 10",
                    (q, f"%{q}%")).fetchall()
        return [User(r["user_id"], r["chat_id"], r["first_name"] or "",
                     r["username"] or "", r["system_id"], r["started_at"],
                     bool(r["is_public"]), r["last_seen"]) for r in rows]

    def delete_user(self, user_id: int) -> None:
        with self._lock:
            self._db.execute("DELETE FROM progress WHERE user_id=?", (user_id,))
            self._db.execute("DELETE FROM users WHERE user_id=?", (user_id,))
            self._db.commit()
        self.log(user_id, "admin_delete_user", "")

    def reset_progress(self, user_id: int, system_id: str | None = None) -> int:
        with self._lock:
            if system_id:
                cur = self._db.execute(
                    "DELETE FROM progress WHERE user_id=? AND system_id=?",
                    (user_id, system_id))
            else:
                cur = self._db.execute(
                    "DELETE FROM progress WHERE user_id=?", (user_id,))
            self._db.commit()
        n = cur.rowcount
        self.log(user_id, "admin_reset", system_id or "*")
        return n

    def recent_log(self, limit: int = 20) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT ts, user_id, event, detail FROM log"
                " ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

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
