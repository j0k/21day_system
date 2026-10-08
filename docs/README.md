<h1 align="center">21day_system</h1>

<p align="center">
  <img src="icon.png" width="150" alt="21day_system icon">
</p>

<p align="center">
  <b>Three 21-day micro-practices in one Telegram bot</b><br>
  skills · daily routine &amp; discipline · sleep
</p>

<p align="center">
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/version-1.0--Beta-2ea043" alt="version 1.0-Beta"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="https://matplotlib.org/"><img src="https://img.shields.io/badge/deps-stdlib%20%2B%20matplotlib-2f8f4e" alt="deps"></a>
  <a href="https://www.sqlite.org/"><img src="https://img.shields.io/badge/storage-SQLite-003B57?logo=sqlite&logoColor=white" alt="SQLite"></a>
  <a href="https://core.telegram.org/bots"><img src="https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white" alt="Telegram Bot"></a>
  <a href="SETUP.md"><img src="https://img.shields.io/badge/docs-readme%20%2B%20setup-1f8f8a" alt="docs"></a>
</p>

<p align="center">
  🌐 Language: <b>English</b> · <a href="README_RU.md">Русский</a>
</p>

> A Telegram bot that runs three 21-day micro-practice systems: **skills**, **daily routine** and **sleep**.

---

**21day_system** helps you complete a short 21-day program: 3–7 minutes a day, from easy to harder. The point is not the quality of a single action but **repetition** — a skill compounds indirectly, like capital in an account.

The bot keeps score, shows progress with **indicators in the spirit of Welles Wilder**, draws charts and a radar, ranks participants on a leaderboard, and runs **fully offline** — no API key required.

> 📄 Project page: **[juri-konoplev.pro/21day_system](https://juri-konoplev.pro/21day_system/)**

---

## Contents

- [Three systems](#three-systems)
- [Features](#features)
- [Indicators](#welles-wilder-style-indicators)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Commands](#commands)
- [Versioning](#versioning)
- [Admin panel and LLM chat](#admin-panel-and-llm-chat)
- [Project layout](#project-layout)
- [Tests](#tests)
- [Credits](#credits)

---

## Three systems

On first launch you pick one of three with a button. You can switch at any time.

| System | What it builds | Key themes |
|---|---|---|
| 🧠 **21 days · micro-practice** | indirect skill growth | Prolog thinking, robotics, RSI, edge, Welles Wilder |
| 🗓 **21 days · daily routine & discipline** | steady rhythm and focus | environment, anchors, priorities, recovery |
| 🌙 **Night rhythm · 21 days of sleep** | sleep quality | light, bedroom environment, rituals, relaxation |

Each system is split into three weeks: **notice → keep the rhythm → reinforce**.

---

## Features

- **Pick a system with a button** in Telegram, switch anytime.
- **Daily check-offs** — done / missed, plus short notes.
- **Progress indicators always visible** — RSI / ADX / ATR in the spirit of Welles Wilder, 7-day pace and finish projection.
- **Three charts** with one command `/chart`:
  - `📈` trader style — dark theme, progress line + RSI/ADX/pace panels;
  - `🎨` styled — light pastel theme;
  - `📡` **progress radar** — target markers converge toward the center as you approach the goal.
- **Participants and leaderboard** — a participant counter and top‑3 right on the system-select screen; dedicated "👥 Participants" and "🏆 Leaders" screens with a per-system filter.
- **Profile and privacy** — go **public** (name shown in the leaderboard) or stay **private** (`Private User`).
- **Admin panel** — overview, user list, user card, event log, broadcast.
- **LLM chat about the project** — free-form dialogue with the model about bot features.
- **Markdown rendering** of LLM answers: bold, italic, `code`, code blocks, lists, links.
- **Works without an API key** — a rule-based offline advisor, no network calls.
- **Versioning** — a single version source and a changelog built from git history (`/version`, `/news`).

---

## Welles Wilder-style indicators

J. Welles Wilder Jr. invented RSI, ATR and ADX. The same ideas are applied here to the **0/1 check-off series** (not to accumulated progress — otherwise the indicators would always read "100").

| Indicator | What it shows |
|---|---|
| `RSI progress` | momentum: wins vs misses |
| `ADX trend` | strength and persistence of the streak |
| `ATR pace` | pace volatility (how jumpy the check-offs are) |
| `7-day pace` | completion rate over the last week |
| `finish projection` | expected completion day from the average pace |

Example block shown on every screen:

```text
📈 Progress indicators (Welles Wilder style)
done 14/21 · 67%
RSI progress  🟡  58.0  ██████░░░░
ADX trend        41.2  ████░░░░░░  (trend forming)
ATR pace         0.31  (volatility)
7-day pace       71%   ███████░░░
finish projection: day ~21
```

---

## Quick start

```bat
git clone https://github.com/j0k/21day_system.git
cd 21day_system
copy .env.example .env
rem put your TELEGRAM_BOT_TOKEN from @BotFather into .env
python bot.py
```

Done — open the bot in Telegram and press **Start**.

> 📖 Full install guide (venv, token, LLM key, autostart, server, troubleshooting) — see **[SETUP.md](SETUP.md)**.
>
> 🧩 Want to build **your own** 21-day system (including via an LLM chat) — see **[HOWTO_MAKE_SELF_21_SYS.md](HOWTO_MAKE_SELF_21_SYS.md)**.

---

## Configuration

All settings are read from the environment or an **`.env`** file next to `bot.py`.

| Variable | Required | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | token from [@BotFather](https://t.me/BotFather) |
| `OPENAI_API_KEY` | — | OpenAI key directly |
| `ROUTERAI_API_KEY` | — | RouterAI key (base URL auto-filled) |
| `LLM_API_KEY` | — | key for any OpenAI-compatible service |
| `OPENAI_BASE_URL` | — | explicit base URL override |
| `OPENAI_MODEL` | — | model (default `gpt-4o-mini`) |
| `ADMIN_IDS` | — | comma-separated Telegram user_ids of admins |
| `DATA_DIR` | — | database folder (default `./data`) |
| `POLL_TIMEOUT` | — | long-polling timeout, sec (default `30`) |

The bot uses the **first non-empty** key from `OPENAI_API_KEY` / `ROUTERAI_API_KEY` / `LLM_API_KEY`. If `ROUTERAI_API_KEY` is set, the base URL and model prefix are filled in automatically.

```powershell
# you can also use Windows environment variables
[Environment]::SetEnvironmentVariable("ROUTERAI_API_KEY", "your_key", "User")
```

**Without an API key the bot is fully functional** — the advisor answers offline.

---

## Commands

| Command | Action |
|---|---|
| `/start` | pick a system (with a button) |
| `/today` | current day |
| `/progress` | progress and indicators |
| `/chart [styled\|radar]` | progress chart |
| `/systems` | switch system |
| `/users` | participants |
| `/board` | leaderboard |
| `/profile` | profile and visibility (public/private) |
| `/admin` | admin panel *(admin only)* |
| `/dev` | LLM chat about the project *(admin only)* |
| `/version` | bot version |
| `/news [list]` | what's new across versions |
| `/cancel` | cancel note input |
| `/help` | help |

---

## Versioning

The version lives in one place — **`version.py`** — following the Codellake scheme:
a numeric core **A.B.C.D** tied to the goal-tree levels.

| Level | Segment | On close |
|---|---|---|
| L0 — mission | **A** | +1.0.0.0 (release) |
| L1 — epic | **B** | +0.1.0.0 |
| L2 — task | **C** | +0.0.1.0 |
| L3 — subtask | **D** | +0.0.1.0 |

Additive: lower segments are **not reset**. The current release is **1.0-Beta**
(core `1.0.0.0`, channel `Beta`, date `2026-10-08`).

```python
from version import VERSION, bump, version_line
VERSION          # "1.0-Beta"
bump("1.0.3.0", "l1")   # "1.1.3.0"
version_line()   # "21day_system 1.0-Beta (2026-10-08) · build ..."
```

The changelog is built from git history: every commit subject ends with
`; vX.Y.Z.W`, so `/news` shows the gist per version and `/version` shows what is
running. See **[CHANGELOG.md](CHANGELOG.md)** for the version history.

---

## Admin panel and LLM chat

Access is controlled by the `ADMIN_IDS` list (env) or the default value.

### 🛠 Admin panel (`/admin`)

| Section | What it does |
|---|---|
| 📊 Overview | users, public accounts, check-offs, events, per-system breakdown |
| 👥 Users | paginated list: visibility, system, progress |
| 👤 User card | a person's progress + **reset / visibility / delete** |
| 🕓 Log | last 20 events |
| 📣 Broadcast | message to all users |
| 🔎 Find | by username, name or id |

### 💬 LLM chat (`/dev`)

Free-form dialogue with the model about the project: ideas, decisions, code snippets. The bot injects a **brief project context** and remembers the last **12 turns**. The persona is tuned to the project stack: Python standard library and matplotlib only.

---

## Project layout

```text
21day_system/
├── bot.py            # entry point: screens, keyboards, handlers, long-polling
├── config.py         # configuration and a minimal .env parser
├── version.py        # single version source (1.0-Beta) and per-level bump
├── news.py           # changelog from git history (/news)
├── systems.py        # data for the three systems (21 days × 3 weeks)
├── storage.py        # SQLite storage (users, progress, log) + migrations
├── indicators.py     # RSI / ADX / ATR in the spirit of Welles Wilder
├── graph.py          # charts: trader and styled
├── radar.py          # progress radar (goal markers converging to the center)
├── llm.py            # optional LLM advisor and project chat
├── md.py             # Markdown → Telegram HTML
├── data/             # 21day.sqlite3 (gitignored)
├── docs/             # GitHub Pages: juri-konoplev.pro/21day_system landing
├── selftest.py           # offline run of the screens
├── selftest_all.py       # three systems + charts
├── selftest_config.py    # config under different keys
├── selftest_version.py   # version, /news, /version
├── demo_progress.py      # demo of the progress output
├── .env.example
└── README.md / README_RU.md / SETUP.md
```

### Storage

Everything lives in a single `data/21day.sqlite3` file:

| Table | Purpose |
|---|---|
| `users` | who writes to the bot, chosen system, privacy, `started_at`, `last_seen` |
| `progress` | result per day: `done`, `minutes`, `note` |
| `log` | event journal (who pressed what) |

---

## Tests

Offline runs, no token or network required:

```bat
python selftest.py          # bot screens, profile, admin panel, Markdown
python selftest_all.py      # three systems + all charts
python selftest_config.py   # config under different keys
python selftest_version.py  # version, /news, /version
python demo_progress.py     # what the bot sends on progress
```

---

## Credits

- Indicator ideas — **J. Welles Wilder Jr.** (RSI, ATR, ADX).
- Versioning scheme — inspired by **Codellake**.
- Project and design: [juri-konoplev.pro](https://juri-konoplev.pro/).
