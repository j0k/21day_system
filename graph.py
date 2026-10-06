# -*- coding: utf-8 -*-
"""Графики прогресса: «трейдерский» и стилизованный.

* ``trader`` — тёмная тема, линия накопленного прогресса (как цена),
  панели RSI, ADX и темпа в духе Welles Wilder.
* ``styled`` — светлая пастельная тема в оформлении PDF-конспектов.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from indicators import bars_10, compute

INK = "#1f262c"
FAINT = "#525d67"
ORANGE = "#EC6A2C"
GREEN = "#2f8f4e"
BLUE = "#2f6299"


def _equity(series: list[int]) -> list[float]:
    out, acc = [], 0.0
    for v in series:
        acc += v
        out.append(acc)
    return out


def render(system, series: list[int], path: str | Path, style: str = "trader"):
    path = str(path)
    st = compute(series)
    eq = _equity(series)
    days = list(range(1, len(series) + 1))

    if style == "styled":
        _render_styled(system, series, eq, days, st, path)
    else:
        _render_trader(system, series, eq, days, st, path)
    return path


def _render_trader(system, series, eq, days, st, path):
    bg = "#0f1419"
    fg = "#d7e0e6"
    grid = "#1d2a33"
    fig = plt.figure(figsize=(9.2, 8.0), dpi=130)
    fig.patch.set_facecolor(bg)
    gs = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.28,
                          left=0.09, right=0.96, top=0.90, bottom=0.11)

    ax0 = fig.add_subplot(gs[0]); ax1 = fig.add_subplot(gs[1], sharex=ax0)
    ax2 = fig.add_subplot(gs[2], sharex=ax0)
    for ax in (ax0, ax1, ax2):
        ax.set_facecolor(bg)
        for s in ax.spines.values():
            s.set_color(grid)
        ax.tick_params(colors=FAINT, labelsize=8)
        ax.grid(True, color=grid, lw=0.6, alpha=0.6)

    # Панель 1: накопленный прогресс (как цена) + цель 21.
    ax0.plot(days, eq, color=ORANGE, lw=2.2, label="прогресс")
    ax0.axhline(len(days), color=GREEN, lw=1.1, ls="--", alpha=0.8,
                label="цель 21")
    ax0.fill_between(days, eq, color=ORANGE, alpha=0.10)
    ax0.set_ylim(-0.5, len(days) + 1)
    ax0.set_ylabel("выполнено дней", color=fg, fontsize=9)
    ax0.legend(loc="lower right", fontsize=8, facecolor=bg,
               edgecolor=grid, labelcolor=fg)
    ax0.set_title(f"{system.title}  ·  {st['done']}/{st['total']}"
                  f"  ({st['pct']}%)", color=fg, fontsize=12, loc="left")

    # Панель 2: пометки по дням (выполнено/пропуск) и RSI-полоса.
    ax1.bar(days, [1 if x else 0.15 for x in series],
            color=[ORANGE if x else "#2a333b" for x in series], width=0.6)
    ax1.set_ylim(0, 1.2); ax1.set_yticks([])
    ax1.set_ylabel("отметки", color=fg, fontsize=8)

    # Панель 3: RSI/ADX/темп.
    ax2.plot(days, [st["rsi"]] * len(days), color="#48b0a3", lw=1.4,
             label=f"RSI {st['rsi']}")
    ax2.plot(days, [st["adx"]] * len(days), color="#c9a227", lw=1.4,
             label=f"ADX {st['adx']}")
    ax2.plot(days, [st["pace"]] * len(days), color="#7a8fd0", lw=1.2, ls=":",
             label=f"темп {st['pace']}%")
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("0..100", color=fg, fontsize=8)
    ax2.set_xlabel("день", color=fg, fontsize=9)
    ax2.legend(loc="upper left", fontsize=7.5, ncol=3, facecolor=bg,
               edgecolor=grid, labelcolor=fg)
    for ax in (ax0, ax1):
        ax.tick_params(labelbottom=False)

    fig.text(0.09, 0.955, "индикаторы Welles Wilder: RSI · ADX · ATR",
             color=FAINT, fontsize=8.5)
    fig.savefig(path, facecolor=bg, bbox_inches="tight")
    plt.close(fig)


def _render_styled(system, series, eq, days, st, path):
    bg = "#eef3f6"
    card = "#ffffff"
    fig = plt.figure(figsize=(9.2, 8.0), dpi=130)
    fig.patch.set_facecolor(bg)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    ax.add_patch(FancyBboxPatch((0.05, 0.925), 0.90, 0.055,
                 boxstyle="round,pad=0,rounding_size=0.012", fc=card,
                 ec="none", mutation_aspect=1.0))
    ax.text(0.075, 0.952, f"{system.title}", fontsize=14,
            color=INK, fontweight="bold", va="center", ha="left")
    ax.text(0.925, 0.952, f"{st['done']}/{st['total']}  ·  {st['pct']}%",
            fontsize=13, color=ORANGE, fontweight="bold", va="center",
            ha="right")

    # 21 клетка-трекер.
    x0, y0, cw, gap = 0.05, 0.775, 0.036, 0.006
    acc = 0
    for i, v in enumerate(series):
        cx = x0 + i * (cw + gap)
        fc = ORANGE if v else card
        ec = ORANGE if v else "#c6ced4"
        ax.add_patch(FancyBboxPatch((cx, y0), cw, 0.06,
                     boxstyle="round,pad=0,rounding_size=0.006", fc=fc,
                     ec=ec, lw=1.1, mutation_aspect=1.0))
        ax.text(cx + cw / 2, y0 + 0.03, str(i + 1), fontsize=8,
                color="#ffffff" if v else FAINT, ha="center", va="center",
                fontweight="bold")
    ax.text(0.05, 0.855, "21 день · отметки выполнения", fontsize=9.5,
            color=FAINT, va="center")

    # Мини-график прогресса.
    axg = fig.add_axes([0.08, 0.50, 0.86, 0.26])
    axg.set_facecolor(card)
    for s in axg.spines.values():
        s.set_color("#dde3e8")
    axg.fill_between(days, eq, color=ORANGE, alpha=0.15)
    axg.plot(days, eq, color=ORANGE, lw=2.4)
    axg.axhline(len(days), color=GREEN, lw=1.0, ls="--")
    axg.set_ylim(-0.5, len(days) + 1)
    axg.set_xlim(1, len(days))
    axg.tick_params(colors=FAINT, labelsize=8)
    axg.grid(True, color="#eef3f6", lw=0.7)

    # Карточки индикаторов.
    cards = [
        ("RSI-прогресс", f"{st['rsi']}", bars_10(st["rsi"]), "#48b0a3"),
        ("ADX-тренд", f"{st['adx']}", bars_10(st["adx"]), "#c9a227"),
        ("темп 7 дней", f"{st['pace']}%", bars_10(st["pace"]), "#7a8fd0"),
    ]
    cx = 0.05
    for title, val, bar, col in cards:
        ax.add_patch(FancyBboxPatch((cx, 0.315), 0.29, 0.135,
                     boxstyle="round,pad=0,rounding_size=0.012", fc=card,
                     ec=col, lw=1.5, mutation_aspect=1.0))
        ax.text(cx + 0.02, 0.425, title, fontsize=9, color=col,
                fontweight="bold", va="center")
        ax.text(cx + 0.02, 0.392, val, fontsize=15, color=INK,
                fontweight="bold", va="center")
        ax.text(cx + 0.02, 0.345, bar, fontsize=8, color=FAINT, va="center")
        cx += 0.30
    ax.text(0.05, 0.265, f"исход: {st['trend']} · прогноз финиша: день ~{st['projected']}"
            f" · ATR-темп {st['atr']}", fontsize=9, color=FAINT, va="center")

    fig.savefig(path, facecolor=bg, bbox_inches="tight")
    plt.close(fig)
