# GitHub Pages — лендинг проекта

В этой папке лежит статичный лендинг **21day_system** (тёмная/светлая тема,
RU/EN, живое превью бота, индикаторы Wilder, страница-просмотрщик README).
Публикуется через **GitHub Pages** из ветки `main`, папка **`/docs`**.

- Живой адрес: **https://juri-konoplev.pro/21day_system/**
- Резервный адрес GitHub: `https://j0k.github.io/21day_system/`

## Включить (один раз)

1. Репозиторий → **Settings** → **Pages**.
2. **Source:** *Deploy from a branch* → Branch **`main`**, Folder **`/docs`**.
3. Сохранить. Через минуту страница появится по адресу выше.

> ⚠️ Важно: папка должна быть **`/docs`**, а **не `/(root)`**. Если выбрать
> корень, GitHub отдаёт Jekyll-рендер `README.md`, и по адресу
> `/21day_system/README_RU.md` будет виден «сырой» Markdown, а страницы
> `indicators.html` / `readme.html` — 404.

### Свой домен `juri-konoplev.pro/21day_system/`

Домен задаётся **на уровне аккаунта GitHub Pages**, а не этого репозитория:

- Если у пользовательского сайта (`j0k.github.io`) уже прописан custom domain
  `juri-konoplev.pro`, то **все** проектные страницы аккаунта автоматически
  отдаются под ним: `https://juri-konoplev.pro/21day_system/`. Отдельный
  `CNAME` в этом репозитории **не нужен** (и вреден — перехватит домен).
- Если своего домена ещё нет: Settings пользовательского репозитория
  `j0k.github.io` → Pages → Custom domain → `juri-konoplev.pro` и DNS:
  `A`-записи на IP GitHub Pages (`185.199.108.153`, `.109.153`, `.110.153`,
  `.111.153`) либо `CNAME` для поддомена.

## Страницы

| Файл | Адрес | Назначение |
|---|---|---|
| `index.html` | `/21day_system/` | лендинг: 5 экранов бота листаются, RU/EN, тёмная/светлая тема |
| `indicators.html` | `/21day_system/indicators.html` | подробно про пять индикаторов |
| `readme.html` | `/21day_system/readme.html` | README как читаемая страница (не «сырой» Markdown) |
| `README.md`, `README_RU.md` | рядом с лендингом | копии для `readme.html` (и фолбэк) |

## Файлы

| Файл | Назначение |
|---|---|
| `index.html` | лендинг |
| `indicators.html` | страница индикаторов |
| `readme.html` | просмотрщик README (marked + локальные копии) |
| `icon.png`, `icon.svg` | иконка проекта (копия из корня) |
| `version.json` | версия для бейджа на странице |
| `vendor/marked.min.js` | локальный Markdown-рендер для `readme.html` |
| `build_assets.py` | пересобирает ассеты из `version.py`, корня и README |
| `.nojekyll` | отключить обработку Jekyll (быстрее, без сюрпризов) |

```bat
python docs\build_assets.py
```

## Тема и язык

Тумблеры в шапке (`☀/🌙` и `RU/EN`) работают на всех страницах, хранятся в
`localStorage` и переносятся между страницами. `readme.html` дополнительно
принимает `?theme=light|dark` и `?lang=en|ru`.
