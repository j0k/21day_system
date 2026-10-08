# GitHub Pages — лендинг проекта

В этой папке лежит статичный лендинг **21day_system** (тёмная тема, живое
превью бота, индикаторы Wilder). Публикуется через **GitHub Pages** из ветки
`main`, папка **`/docs`**.

- Живой адрес: **https://juri-konoplev.pro/21day_system/**
- Резервный адрес GitHub: `https://j0k.github.io/21day_system/`

## Включить (один раз)

1. Репозиторий → **Settings** → **Pages**.
2. **Source:** *Deploy from a branch* → Branch **`main`**, Folder **`/docs`**.
3. Сохранить. Через минуту страница появится по адресу выше.

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

## Файлы

| Файл | Назначение |
|---|---|
| `index.html` | лендинг (единственная точка правки контента) |
| `icon.png`, `icon.svg` | иконка проекта (копия из корня) |
| `version.json` | версия для бейджа на странице |
| `build_assets.py` | пересобирает ассеты из `version.py` и корня |
| `.nojekyll` | отключить обработку Jekyll (быстрее, без сюрпризов) |

```bat
python docs\build_assets.py
```
