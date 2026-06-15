"""
LoreKeeper — Wiki Link Parser & Backlink Engine.

Parses `[[Article Name]]` syntax from markdown content, renders it as
interactive HTML links, and computes backlinks ("What links here?").
"""

from __future__ import annotations

import re
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QTextBrowser

from database import crud
from database.models import Article


# ---------------------------------------------------------------------------
# Pattern
# ---------------------------------------------------------------------------

# Matches [[Article Name]] or [[Article Name|Display Text]]
WIKI_LINK_PATTERN = re.compile(r"\[\[([^\[\]]+?)(?:\|([^\[\]]*))?\]\]")


def parse_wiki_links(text: str) -> list[tuple[str, str, int, int]]:
    """Find all wiki links in *text*.

    Returns a list of (article_name, display_text, start_pos, end_pos).
    """
    results: list[tuple[str, str, int, int]] = []
    for match in WIKI_LINK_PATTERN.finditer(text):
        article_name = match.group(1).strip()
        display_text = (match.group(2) or article_name).strip()
        results.append((article_name, display_text, match.start(), match.end()))
    return results


def resolve_wiki_link_title(article_name: str) -> Optional[str]:
    """Find the actual article title (case-insensitive) matching *article_name*.

    Returns the stored title (which may differ in casing), or None if not found.
    """
    article = crud.get_article_by_title(article_name)
    return article.title if article else None


def article_exists(article_name: str) -> bool:
    """Check if an article with this name exists (case-insensitive)."""
    return crud.get_article_by_title(article_name) is not None


# ---------------------------------------------------------------------------
# Backlinks
# ---------------------------------------------------------------------------

def find_backlinks(article_title: str, limit: int = 50) -> list[Article]:
    """Find all articles whose content contains ``[[article_title]]``.

    Searches case-insensitively.
    """
    if not article_title:
        return []

    # We search using LIKE on the content for [[Title]] patterns.
    # This isn't FTS5-based but is simple and reliable for backlinks.
    pattern = f"%[[{article_title}]]%"
    # Also match with pipe syntax: [[Title|display]]
    pattern2 = f"%[[{article_title}|%"

    rows = crud.list_articles(limit=limit)
    matches: list[Article] = []
    title_lower = article_title.lower()

    for article in rows:
        content_lower = article.content.lower()
        if f"[[{title_lower}]]" in content_lower or f"[[{title_lower}|" in content_lower:
            matches.append(article)

    return matches


# ---------------------------------------------------------------------------
# Markdown to HTML renderer (replaces wiki links with clickable HTML)
# ---------------------------------------------------------------------------

def render_wiki_content(markdown_text: str) -> str:
    """Convert markdown text (with ``[[links]]``) to rich HTML.

    Handles:
    - ``[[Article Name]]`` → clickable HTML links (or grey if not found)
    - Basic markdown: **bold**, *italic*, `code`, ## headings, --- hr
    - Line breaks → <br>
    """
    html = _escape_html_basic(markdown_text)

    # Headings
    html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html)
    html = re.sub(r'\*(.+?)\*', r'<i>\1</i>', html)

    # Inline code
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

    # Horizontal rule
    html = re.sub(r'^---+\s*$', '<hr>', html, flags=re.MULTILINE)

    # Wiki links
    def _replace_wiki_link(match: re.Match) -> str:
        article_name = match.group(1).strip()
        display_text = (match.group(2) or article_name).strip()
        exists = article_exists(article_name)
        if exists:
            title = resolve_wiki_link_title(article_name) or article_name
            return (
                f'<a href="wikilink://{title}" '
                f'style="color: #0d6efd; text-decoration: underline; '
                f'cursor: pointer;" '
                f'data-article="{title}">{_escape_html(display_text)}</a>'
            )
        else:
            return (
                f'<a href="wikicreate://{article_name}" '
                f'style="color: #dc3545; text-decoration: underline dotted; '
                f'cursor: pointer;" '
                f'data-article="{article_name}">'
                f'{_escape_html(display_text)}</a>'
                f'<sup style="color: #dc3545; font-size: 10px;">?</sup>'
            )

    html = WIKI_LINK_PATTERN.sub(_replace_wiki_link, html)

    # Line breaks (preserve double line breaks as paragraph breaks)
    html = re.sub(r'\n\s*\n', '</p><p>', html)
    html = re.sub(r'\n(?!\s*</)', '<br>', html)

    return f'<div style="line-height: 1.6;">{html}</div>'


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _escape_html_basic(text: str) -> str:
    """Escape HTML but keep wiki link syntax unescaped so we can parse it."""
    # First, protect wiki links
    def _protect(m: re.Match) -> str:
        return m.group(0).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Escape everything not inside [[...]]
    result = []
    last_end = 0
    for match in WIKI_LINK_PATTERN.finditer(text):
        # Escape text before this match
        before = text[last_end:match.start()]
        result.append(_escape_html(before))
        # Keep the wiki link unescaped (we'll process it later)
        result.append(match.group(0))
        last_end = match.end()
    # Escape remaining text after last match
    result.append(_escape_html(text[last_end:]))
    return "".join(result)


# ---------------------------------------------------------------------------
# WikiTextBrowser — displays rendered markdown + wiki links
# ---------------------------------------------------------------------------

class WikiTextBrowser(QTextBrowser):
    """QTextBrowser subclass that renders wiki content and handles link clicks."""

    link_navigated = str  # signal: article_id or article_name
    link_creation_requested = str  # signal: article_name to create

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)
        self.setReadOnly(True)
        self.anchorClicked.connect(self._on_anchor_clicked)
        self.setStyleSheet("QTextBrowser { background: transparent; border: none; }")

    def set_wiki_content(self, markdown_text: str) -> None:
        """Render markdown content with wiki links into the browser."""
        html = render_wiki_content(markdown_text)
        self.setHtml(html)

    def _on_anchor_clicked(self, url) -> None:
        href = url.toString()
        if href.startswith("wikilink://"):
            article_name = href[len("wikilink://"):]
            article = crud.get_article_by_title(article_name)
            if article:
                # Emit our own signal for the main window to handle
                self.link_navigated.emit(article.id)
        elif href.startswith("wikicreate://"):
            article_name = href[len("wikicreate://"):]
            self.link_creation_requested.emit(article_name)