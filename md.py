# -*- coding: utf-8 -*-
"""Мини-конвертер Markdown → HTML для Telegram.

Telegram принимает ограниченный HTML: <b> <i> <u> <s> <a> <code> <pre>
<blockquote>. LLM отвечает в Markdown, поэтому перед отправкой превращаем
его в этот HTML — иначе пользователь видит сырые **звёздочки** и `бэктики`.

Поддерживается: **жирный**, *курсив*, ~~зачёркнутый~~, `код`,
```блоки кода```, [ссылки](url), заголовки # и списки - / *.
Работает без сторонних библиотек.
"""
from __future__ import annotations

import html
import re

_FENCE = re.compile(r"```([^\n`]*)\n(.*?)```", re.S)
_FENCE_TILDE = re.compile(r"~~~([^\n`]*)\n(.*?)~~~", re.S)
_INLINE = re.compile(r"`([^`\n]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_HEADING = re.compile(r"(?m)^\s{0,3}#{1,6}\s*(.+?)\s*#*\s*$")
_BULLET = re.compile(r"(?m)^\s{0,3}[-*+]\s+")
_BOLD_STAR = re.compile(r"\*\*(.+?)\*\*", re.S)
_BOLD_UNDER = re.compile(r"(?<!\w)__(.+?)__(?!\w)", re.S)
_ITALIC_STAR = re.compile(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", re.S)
_ITALIC_UNDER = re.compile(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", re.S)
_STRIKE = re.compile(r"~~(.+?)~~", re.S)


def to_html(text: str) -> str:
    """Преобразовать Markdown-строку в Telegram-HTML (безопасно экранируя)."""
    if not text:
        return ""
    placeholders: dict[str, str] = {}

    def stash(fragment: str) -> str:
        key = f"\x00{len(placeholders)}\x00"
        placeholders[key] = fragment
        return key

    def block(match: re.Match) -> str:
        lang = match.group(1).strip()
        code = html.escape(match.group(2).strip("\n"), quote=False)
        cls = f' class="language-{html.escape(lang)}"' if lang else ""
        return stash(f"<pre><code{cls}>{code}</code></pre>")

    text = _FENCE.sub(block, text)
    text = _FENCE_TILDE.sub(block, text)
    text = _INLINE.sub(lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"),
                       text)
    # Всё, что осталось — обычный текст: экранируем.
    text = html.escape(text, quote=False)
    text = _LINK.sub(r'<a href="\2">\1</a>', text)
    text = _BULLET.sub("• ", text)
    text = _HEADING.sub(r"<b>\1</b>", text)
    text = _BOLD_STAR.sub(r"<b>\1</b>", text)
    text = _BOLD_UNDER.sub(r"<b>\1</b>", text)
    text = _STRIKE.sub(r"<s>\1</s>", text)
    text = _ITALIC_STAR.sub(r"<i>\1</i>", text)
    text = _ITALIC_UNDER.sub(r"<i>\1</i>", text)
    for key, fragment in placeholders.items():
        text = text.replace(key, fragment)
    return text
