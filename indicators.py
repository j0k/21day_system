# -*- coding: utf-8 -*-
"""Прогресс-индикаторы по мотивам J. Welles Wilder Jr.

Wilder известен RSI, ATR и ADX. Здесь те же идеи применены к прогрессу
21-дневной практики:

* **RSI-прогресс** — импульс: насколько «бычий» ритм отметок (успехи против
  пропусков) со сглаживанием Уайлдера.
* **ADX-прогресс** — сила тренда: насколько устойчива серия выполнения.
* **ATR-прогресс** — волатильность темпа: насколько рвано идут отметки.
* **Пейс** — доля выполнения за последние 7 дней.
* **Проекция** — прогноз дня финиша по среднему темпу.
"""
from __future__ import annotations


def wilder_smooth(values: list[float], period: int) -> list[float]:
    """Сглаживание Уайлдера: первое — среднее, далее prev + (x-prev)/n."""
    if not values:
        return []
    out: list[float] = []
    if len(values) < period:
        return [sum(values) / len(values)] * len(values)
    first = sum(values[:period]) / period
    out = [sum(values[:i + 1]) / (i + 1) for i in range(period - 1)]
    out.append(first)
    prev = first
    for x in values[period:]:
        prev = prev + (x - prev) / period
        out.append(prev)
    return out


def rsi(values: list[float], period: int = 14) -> float:
    """RSI Уайлдера по ряду значений (0..100)."""
    if len(values) < 2:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(values)):
        d = values[i] - values[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = wilder_smooth(gains, period)[-1]
    al = wilder_smooth(losses, period)[-1]
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    rs = ag / al
    return 100.0 - 100.0 / (1.0 + rs)


def _dm(series: list[float]) -> tuple[list[float], list[float], list[float]]:
    plus, minus, tr = [], [], []
    for i in range(1, len(series)):
        up = series[i] - series[i - 1]
        plus.append(max(up, 0.0))
        minus.append(max(-up, 0.0))
        tr.append(abs(up))
    return plus, minus, tr


def atr(series: list[float], period: int = 14) -> float:
    """ATR-подобная волатильность темпа."""
    _, _, tr = _dm(series)
    if not tr:
        return 0.0
    return wilder_smooth(tr, period)[-1]


def adx(series: list[float], period: int = 14) -> float:
    """ADX-подобная сила тренда (0..100)."""
    plus, minus, tr = _dm(series)
    if len(tr) < 2:
        return 0.0
    sp = wilder_smooth(plus, period)
    sm = wilder_smooth(minus, period)
    st = wilder_smooth(tr, period)
    dx = []
    for p, m, t in zip(sp, sm, st):
        if t == 0:
            dx.append(0.0)
            continue
        pdi = 100.0 * p / t
        mdi = 100.0 * m / t
        denom = pdi + mdi
        dx.append(100.0 * abs(pdi - mdi) / denom if denom else 0.0)
    return wilder_smooth(dx, period)[-1]


def compute(series: list[int], period: int = 7) -> dict:
    """Полный набор индикаторов по ряду 0/1 (дни 1..21).

    Индикаторы считаются по САМОМУ РЯДУ отметок (0/1), а не по накопленному
    «эквити»: эквити только растёт, поэтому RSI/ADX по нему всегда давали 100.
    На ряде 0/1 пропуск дня — это «убыток», серия отметок — «рост», и
    индикаторы становятся осмысленными.
    """
    marks = [float(v) for v in series]

    # «Эквити»: накопленное число выполненных дней (для графика/наглядности).
    equity: list[float] = []
    acc = 0.0
    for v in series:
        acc += float(v)
        equity.append(acc)
    done = int(sum(series))
    total = len(series)

    r = rsi(marks, period)
    a = adx(marks, period)
    v = atr(marks, period)

    recent = series[-7:] if series else []
    pace = (sum(recent) / len(recent)) if recent else 0.0

    # Устойчивость серии (для текстовой интерпретации ADX).
    if a >= 50:
        trend_txt = "сильный тренд"
    elif a >= 25:
        trend_txt = "тренд формируется"
    else:
        trend_txt = "боковик / нет тренда"

    # Проекция финиша по среднему темпу.
    last_day = max([i + 1 for i, x in enumerate(series) if x], default=0)
    if done > 0 and last_day > 0:
        rate = done / last_day
        remaining = total - done
        days_left = int(round(remaining / rate)) if rate > 0 else total
        projected = last_day + days_left
    else:
        projected = total

    swing = "перегрет" if r >= 70 else "перепродан" if r <= 30 else "нейтрально"

    return {
        "done": done, "total": total,
        "pct": round(100 * done / total) if total else 0,
        "rsi": round(r, 1), "adx": round(a, 1), "atr": round(v, 2),
        "pace": round(pace * 100), "trend": trend_txt, "swing": swing,
        "projected": projected, "equity": equity,
    }


def bars_10(value: float, width: int = 10) -> str:
    """Простой полосовой индикатор 0..100."""
    filled = int(round(max(0.0, min(100.0, value)) / 100.0 * width))
    return "█" * filled + "░" * (width - filled)


def indicator_block(st: dict) -> str:
    """Текстовый блок индикаторов для сообщения."""
    rsi_mark = "🔴" if st["rsi"] >= 70 else "🟢" if st["rsi"] <= 30 else "🟡"
    return (
        f"📈 <b>Индикаторы прогресса</b> (стиль Welles Wilder)\n"
        f"выполнено <b>{st['done']}/{st['total']}</b> · {st['pct']}%\n"
        f"RSI-прогресс  {rsi_mark} {st['rsi']:>5}  {bars_10(st['rsi'])}\n"
        f"ADX-тренд      {st['adx']:>5}  {bars_10(st['adx'])}  ({st['trend']})\n"
        f"ATR-темп       {st['atr']:>5}  (волатильность){''}\n"
        f"пейс 7 дней    {st['pace']:>4}%  {bars_10(st['pace'])}\n"
        f"прогноз финиша: день ~{st['projected']}"
    )
