# -*- coding: utf-8 -*-
"""Прогон всех трёх систем: отметки через день, индикаторы, оба графика."""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="21day_all_")

from graph import render            # noqa: E402
from indicators import compute      # noqa: E402
from storage import Storage         # noqa: E402
from systems import SYSTEMS, SYSTEM_ORDER, TOTAL_DAYS  # noqa: E402

db = Storage(os.path.join(os.environ["DATA_DIR"], "x.sqlite3"))
db.touch(9, 9, "T", "t")
ok = True
for sid in SYSTEM_ORDER:
    db.set_system(9, sid)
    for d in range(1, TOTAL_DAYS + 1, 2):      # каждый второй день
        db.set_done(9, sid, d, True)
    st = db.stats(9, sid)
    ind = compute(st["series"])
    render(SYSTEMS[sid], st["series"],
           os.path.join(os.environ["DATA_DIR"], f"g_{sid}.png"), "trader")
    render(SYSTEMS[sid], st["series"],
           os.path.join(os.environ["DATA_DIR"], f"g_{sid}s.png"), "styled")
    days = len(SYSTEMS[sid].days)
    assert days == 21, (sid, days)
    ok = ok and days == 21 and st["done"] == 11
    print(f"{sid:11} days={days} done={st['done']:2} pct={st['pct']:3}% "
          f"rsi={ind['rsi']:5} adx={ind['adx']:5} pace={ind['pace']:3} "
          f"proj={ind['projected']}")

assert ok
print("ALL SYSTEMS OK (3 systems x 21 days, indicators + both charts).")
