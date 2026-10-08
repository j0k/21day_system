# SETUP — установка и запуск 21day_system

Пошаговая инструкция: от нуля до работающего бота. Рассчитана на **Windows** (основной сценарий), с заметками для Linux/macOS.

> Краткая версия — в [README.md](README.md). Здесь — всё подробно: venv, токен, ключ LLM, автозапуск, сервер, диагностика.

---

## Содержание

- [Требования](#1-требования)
- [Получение файлов](#2-получение-файлов)
- [Виртуальное окружение и зависимости](#3-виртуальное-окружение-и-зависимости)
- [Токен бота](#4-токен-бота)
- [Настройка .env](#5-настройка-env)
- [Ключ LLM (необязательно)](#6-ключ-llm-необязательно)
- [Первый запуск](#7-первый-запуск)
- [Администратор](#8-администратор)
- [Автозапуск](#9-автозапуск)
- [Запуск на сервере](#10-запуск-на-сервере)
- [Обновление](#11-обновление)
- [Диагностика](#12-диагностика)
- [Шпаргалка](#шпаргалка)

---

## 1. Требования

| Компонент | Версия | Обязательно |
|---|---|---|
| Python | **3.10+** (проверено на 3.13) | да |
| pip | свежий | да |
| Git | любой | для клонирования |
| Telegram-аккаунт | — | да |
| Ключ LLM | — | нет (бот работает офлайн) |

Проверить Python:

```bat
python --version
```

Внешние зависимости почти отсутствуют: бот написан на **стандартной библиотеке Python**; `matplotlib` нужен только для графиков.

---

## 2. Получение файлов

```bat
git clone https://github.com/j0k/21day_system.git
cd 21day_system
```

Если Git недоступен — скачайте ZIP с GitHub и распакуйте, затем перейдите в папку:

```bat
cd путь\к\21day_system
```

---

## 3. Виртуальное окружение и зависимости

Рекомендуется изолированное окружение:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install matplotlib
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip matplotlib
```

> Если графика не нужна — `matplotlib` можно не ставить: всё остальное работает на стандартной библиотеке, а вызовы `/chart` и `/chart radar` просто завершатся ошибкой без него.

---

## 4. Токен бота

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram.
2. Отправьте `/newbot`.
3. Задайте имя и username (username обязан заканчиваться на `bot`).
4. Скопируйте токен вида:

   ```text
   1234567890:AAH-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

Сохраните его — он понадобится на следующем шаге.

---

## 5. Настройка .env

Создайте `.env` из шаблона и откройте его:

```bat
copy .env.example .env
notepad .env
```

Минимально нужно заполнить токен:

```dotenv
TELEGRAM_BOT_TOKEN=1234567890:AAH-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Полный список параметров:

| Переменная | По умолчанию | Описание |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | токен от @BotFather (**обязателен**) |
| `OPENAI_API_KEY` | — | ключ OpenAI |
| `ROUTERAI_API_KEY` | — | ключ RouterAI |
| `LLM_API_KEY` | — | ключ любого OpenAI-совместимого сервиса |
| `OPENAI_BASE_URL` | зависит от ключа | базовый URL API |
| `OPENAI_MODEL` | `gpt-4o-mini` | модель |
| `ADMIN_IDS` | `52160369` | Telegram user_id админов (через запятую) |
| `DATA_DIR` | `./data` | папка с SQLite |
| `POLL_TIMEOUT` | `30` | таймаут long-polling, сек |

> Файл `.env` **не коммитится** (он в `.gitignore`) — секреты не попадут в репозиторий.

---

## 6. Ключ LLM (необязательно)

Бот **полностью работает без ключа** — советник отвечает офлайн. Ключ нужен только для живых ответов модели (💡 Совет и чат `/dev`).

Поддерживаются три имени ключа (берётся первое непустое):

| Ключ | Базовый URL | Модель по умолчанию |
|---|---|---|
| `OPENAI_API_KEY` | `https://api.openai.com/v1` | `gpt-4o-mini` |
| `ROUTERAI_API_KEY` | `https://routerai.ru/api/v1` | `openai/gpt-4o-mini` |
| `LLM_API_KEY` | `https://api.openai.com/v1` | `gpt-4o-mini` |

Пример для RouterAI в `.env`:

```dotenv
ROUTERAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
# модель можно переопределить:
# ROUTERAI_MODEL=anthropic/claude-sonnet-4.6
```

Или через переменную окружения Windows:

```powershell
[Environment]::SetEnvironmentVariable("ROUTERAI_API_KEY", "ваш_ключ", "User")
# перезапустите терминал
```

Проверить, что конфигурация подхватилась:

```bat
python selftest_config.py
```

---

## 7. Первый запуск

```bat
python bot.py
```

Ожидаемый вывод:

```text
21day_system бот запущен. Проект: https://github.com/j0k/21day_system
БД: ...\21day_system\data\21day.sqlite3 | LLM: вкл
   ключ: ROUTERAI_API_KEY | base_url: https://routerai.ru/api/v1 | модель: openai/gpt-4o-mini
```

Теперь в Telegram:

1. Найдите своего бота по username.
2. Нажмите **Start** (или отправьте `/start`).
3. Выберите одну из трёх систем кнопкой.
4. Отмечайте дни, смотрите `/progress`, `/chart`, `/chart radar`.

Остановить — `Ctrl + C`.

---

## 8. Администратор

Админам доступны `/admin` и `/dev`. Список задаётся в `ADMIN_IDS`:

```dotenv
ADMIN_IDS=52160369,123456789
```

Свой Telegram user_id можно узнать:

- в боте **@userinfobot**;
- или в журнале: `/admin` → 🕓 Журнал (первая колонка — id).

---

## 9. Автозапуск

### Windows — планировщик заданий

Создайте `run_bot.bat` в папке проекта:

```bat
@echo off
cd /d D:\pm\soft\21day_system
call .venv\Scripts\activate
python -u bot.py
```

Затем: **Планировщик заданий** → *Создать задачу* → триггер *При входе в систему* → действие *Запуск программы* → укажите `run_bot.bat`, включите «Выполнять вне зависимости от регистрации».

### Windows — автозагрузка (просто)

Нажмите `Win + R` → `shell:startup` → положите туда ярлык на `run_bot.bat`.

---

## 10. Запуск на сервере

### systemd (Linux)

`/etc/systemd/system/21day.service`:

```ini
[Unit]
Description=21day_system Telegram bot
After=network-online.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/21day_system
EnvironmentFile=/opt/21day_system/.env
ExecStart=/opt/21day_system/.venv/bin/python -u bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now 21day
sudo systemctl status 21day
```

### Docker (вариант)

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir matplotlib
CMD ["python", "-u", "bot.py"]
```

```bash
docker build -t 21day .
docker run -d --name 21day --env-file .env -v $(pwd)/data:/app/data --restart unless-stopped 21day
```

> Только **один** экземпляр бота на токен: второй запуск вызовет ошибку `409 Conflict`.

---

## 11. Обновление

```bat
cd путь\к\21day_system
git pull
.venv\Scripts\activate
python bot.py
```

База `data/21day.sqlite3` сохраняется между обновления; схема мигрирует автоматически.

---

## 12. Диагностика

| Симптом | Причина | Решение |
|---|---|---|
| `Нет TELEGRAM_BOT_TOKEN` | не задан токен | заполните `.env` или задайте переменную |
| `409 Conflict` | запущено два бота | оставьте один экземпляр, перезапустите |
| бот молчит | нет сети / неверный токен | проверьте токен, доступ в интернет |
| `LLM недоступен` | нет ключа или ошибка API | проверьте ключ, `python selftest_config.py` |
| пустые графики | не установлен matplotlib | `pip install matplotlib` |
| старая схема БД | давняя база | колонка `is_public` добавляется авто-миграцией |
| кириллица в консоли «кракозябрами» | кодировка терминала | запускайте `python -u bot.py`, используйте Windows Terminal |

Быстрые проверки:

```bat
python selftest.py          rem экраны, админка, Markdown
python selftest_all.py      rem три системы + графики
python selftest_config.py   rem конфигурация
```

---

## Шпаргалка

```bat
rem установка
python -m venv .venv && .venv\Scripts\activate
pip install matplotlib
copy .env.example .env

rem запуск
python -u bot.py

rem проверки
python selftest.py
python selftest_all.py
python selftest_config.py
```

**Проект:** <https://github.com/j0k/21day_system> · **Сайт:** <https://juri-konoplev.pro/>
