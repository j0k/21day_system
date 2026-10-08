# -*- coding: utf-8 -*-
"""Радар прогресса.

Дисплей-радар «приближения к цели»:
* центр снизу — «ты сейчас»;
* купол сверху — обзор;
* кольца — дистанция до цели (100% = центр, 0% = внешняя дуга);
* каждая «цель» — целевой показатель (выполнение, темп, серия, прогноз,
  устойчивость, импульс);
* чем ближе метка к центру — тем ближе показатель к цели;
* цвет — уровни состояния по смыслу прогресса:
  зелёный (цель достигнута), белый (норма), оранжевый (внимание),
  красный (отставание);
* стрелка ↑/↓ — показатель растёт или падает.
"""
from __future__ import annotations

import math

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, FancyBboxPatch, Polygon, Circle

from indicators import compute

# --- палитра радара ---------------------------------------------------------
BG = "#0a0e0c"
FRAME = "#e8eef2"
GRID = "#6f7f88"
WHITE = "#e8eef2"
GREEN = "#27b34a"
ORANGE = "#e08a00"
RED = "#e53935"
FAINT = "#8a979e"
CROSS = "#b6e21f"

# --- геометрия прибора ------------------------------------------------------
XMAX = 9.6 / 6.4            # чтобы круг был кругом, а не эллипсом
CX, CY = 0.75, 0.275        # центр (own ship)
R_OUT, R_IN = 0.470, 0.255  # внешнее и внутреннее кольцо
A0, A1 = 40.0, 140.0        # сектор обзора
R_LAB = R_OUT + 0.072       # радиус подписей снаружи купола
FR_X0, FR_Y0 = 0.06, 0.055  # левый-нижний угол рамки
FR_X1, FR_Y1 = XMAX - 0.06, 0.905


# --------------------------------------------------------------- показатели
def _streak(s: list[int]) -> int:
    cur = 0
    for v in s:
        cur = cur + 1 if v else 0
    return cur


def _pace(s: list[int]) -> float:
    w = s[-7:]
    return sum(w) / len(w) if w else 0.0


def _metrics(series: list[int]) -> list[dict]:
    """Целевые показатели: (название, достижение 0..1.2, цель, что значит)."""
    n = len(series)
    if n == 0:
        return []
    ind = compute(series)
    done = sum(series)
    completion = done / n
    pace = _pace(series)
    streak = _streak(series)
    rsi = ind["rsi"]
    adx = ind["adx"]
    projected = ind["projected"]

    def clamp(x):
        return max(0.0, min(1.2, x))

    items = [
        ("done", "ВЫПОЛНЕНО", clamp(completion / 1.0), "21/21"),
        ("pace", "ТЕМП 7 ДНЕЙ", clamp(pace / 0.7), "≥70%"),
        ("streak", "СЕРИЯ", clamp(streak / 7.0), "7 дней"),
        ("proj", "ПРОГНОЗ ФИНИША", clamp(21.0 / projected if projected else 0.0),
         "≤21 дн"),
        ("adx", "УСТОЙЧИВОСТЬ", clamp(adx / 50.0), "ADX 50"),
        ("rsi", "ИМПУЛЬС", clamp(1.0 - abs(rsi - 60.0) / 60.0), "RSI ~60"),
    ]

    def value(key, s):
        if not s:
            return 0.0
        if key == "done":
            return sum(s) / len(s)
        if key == "pace":
            return _pace(s)
        if key == "streak":
            return _streak(s)
        i = compute(s)
        if key == "proj":
            return 21.0 / i["projected"] if i["projected"] else 0.0
        if key == "adx":
            return i["adx"] / 50.0
        return 1.0 - abs(i["rsi"] - 60.0) / 60.0

    out = []
    for key, label, att, target in items:
        trend = 0
        if n > 4:
            c = value(key, series)
            p = value(key, series[:-3])
            if c - p > 0.03:
                trend = 1
            elif p - c > 0.03:
                trend = -1
        out.append({"key": key, "label": label, "att": att, "target": target,
                    "trend": trend})
    return out


def _status(att: float) -> tuple[str, str]:
    if att >= 0.99:
        return GREEN, "done"
    if att >= 0.66:
        return WHITE, "on_track"
    if att >= 0.40:
        return ORANGE, "attention"
    return RED, "lag"


def _radius(att: float) -> float:
    a = max(0.0, min(1.0, att))
    # ^0.62 растягивает верхний диапазон, чтобы метки у цели не слипались
    return R_IN + (1.0 - a) ** 0.62 * (R_OUT - R_IN)


def _xy(angle_deg: float, r: float) -> tuple[float, float]:
    a = math.radians(angle_deg)
    return CX + r * math.cos(a), CY + r * math.sin(a)


def _diamond(ax, x, y, size, color, filled, lw=1.8):
    pts = [(x, y + size), (x + size, y), (x, y - size), (x - size, y)]
    ax.add_patch(Polygon(pts, closed=True,
                         facecolor=color if filled else "none",
                         edgecolor=color, lw=lw, zorder=6))


# ------------------------------------------------------------------- рендер
def render_radar(system, series: list[int], st: dict, path: str,
                 title: str | None = None):
    metrics = _metrics(series)
    k = len(metrics) or 1
    fig = plt.figure(figsize=(9.6, 6.4), dpi=130)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.set_xlim(0, XMAX); ax.set_ylim(0, 1); ax.set_aspect("equal")

    # --- рамка прибора ---
    ax.add_patch(FancyBboxPatch((FR_X0, FR_Y0), FR_X1 - FR_X0, FR_Y1 - FR_Y0,
                 boxstyle="round,pad=0,rounding_size=0.03", fc=BG,
                 ec=FRAME, lw=2.4, zorder=1))

    # --- дуги: внешняя сплошная + пунктирные кольца дистанции ---
    ax.add_patch(Arc((CX, CY), 2 * R_OUT, 2 * R_OUT, angle=0,
                     theta1=A0, theta2=A1, color=FRAME, lw=2.6, zorder=2))
    for frac in (0.25, 0.50, 0.75):
        r = R_IN + frac * (R_OUT - R_IN)
        ax.add_patch(Arc((CX, CY), 2 * r, 2 * r, angle=0, theta1=A0,
                         theta2=A1, color=GRID, lw=1.2, ls=(0, (6, 5)),
                         zorder=2))

    # --- центр: own ship + цель ---
    ax.plot([CX - 0.040, CX + 0.040], [CY, CY], color=CROSS, lw=2.4, zorder=5)
    ax.plot([CX, CX], [CY - 0.034, CY + 0.034], color=CROSS, lw=2.4, zorder=5)
    ax.text(CX, CY - 0.072, "СЕЙЧАС", color=CROSS, fontsize=7.4, ha="center",
            va="center", fontweight="bold", zorder=3)

    ax.text(FR_X0 + 0.02, 0.872,
            "центр — цель · дуги — 25 / 50 / 75% пути к цели", color=FAINT,
            fontsize=7.0, ha="left", va="center", zorder=3)
    for i, m in enumerate(metrics):
        ang = A0 + (A1 - A0) * (i / (k - 1)) if k > 1 else 90.0
        r = _radius(m["att"])
        x, y = _xy(ang, r)
        color, shape = _status(m["att"])
        size = 0.024
        if shape == "circle":
            ax.add_patch(Circle((x, y), size * 0.85, facecolor=color,
                                edgecolor="none", zorder=6))
        elif shape in ("done", "lag"):
            _diamond(ax, x, y, size, color, True)
        else:
            _diamond(ax, x, y, size, color, False)
        ax.add_patch(FancyBboxPatch((x - 0.040, y - 0.032), 0.080, 0.064,
                     boxstyle="round,pad=0,rounding_size=0.008", fc="none",
                     ec=color, lw=0.8, ls=(0, (2, 2)), zorder=4))

        # процент достижения — сбоку от метки, не лезет к центру и к подписям
        arrow = "↑" if m["trend"] > 0 else "↓" if m["trend"] < 0 else ""
        side = -1 if x >= CX else 1
        ax.text(x + side * 0.082, y, f"{int(round(m['att'] * 100))}%{arrow}",
                color=color, fontsize=9.0, ha="center", va="center",
                fontweight="bold", zorder=7)

        # подпись снаружи купола + соединитель
        lx, ly = _xy(ang, R_LAB)
        ax.plot([x, lx], [y, ly], color=color, lw=0.7, ls=(0, (1, 2)),
                zorder=4)
        ha = "center"
        if lx < 0.30:
            ha = "left"
        elif lx > XMAX - 0.30:
            ha = "right"
        ax.text(lx, ly + 0.015, m["label"], color=WHITE, fontsize=8.0,
                ha=ha, va="center", fontweight="bold", zorder=6)
        ax.text(lx, ly - 0.013, f"цель {m['target']}", color=FAINT,
                fontsize=6.8, ha=ha, va="center", zorder=6)

    # --- заголовок и сводка ---
    name = title or system.title
    ax.text(FR_X0 + 0.02, 0.962, "РАДАР ПРОГРЕССА", color=WHITE, fontsize=13.5,
            fontweight="bold", ha="left", va="center", zorder=6)
    ax.text(FR_X0 + 0.02, 0.932, name, color=FAINT, fontsize=8.6, ha="left",
            va="center", zorder=6)
    att_avg = round(100 * sum(min(1.0, m["att"]) for m in metrics) / k)
    ax.text(FR_X1 - 0.02, 0.962, f"{st['done']}/{st['total']}  ·  {st['pct']}%",
            color=ORANGE, fontsize=13.5, ha="right", va="center",
            fontweight="bold", zorder=6)
    ax.text(FR_X1 - 0.02, 0.932, f"среднее по цели: {att_avg}%", color=FAINT,
            fontsize=8.2, ha="right", va="center", zorder=6)

    # --- легенда уровней: один ряд внизу внутри рамки ---
    legend = [(GREEN, "цель достигнута"), (WHITE, "в норме"),
              (ORANGE, "внимание"), (RED, "отставание")]
    step = (FR_X1 - FR_X0) / len(legend)
    for idx, (col, lab) in enumerate(legend):
        lx0 = FR_X0 + step * (idx + 0.15)
        ax.add_patch(Circle((lx0, 0.082), 0.011, facecolor=col,
                            edgecolor="none", zorder=6))
        ax.text(lx0 + 0.022, 0.082, lab, color=FAINT, fontsize=8.0,
                ha="left", va="center", zorder=6)

    fig.savefig(path, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return path
