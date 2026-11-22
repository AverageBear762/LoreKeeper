"""
World Garden — Regression tests: hover preview respects disabled sections.

Covers:
- A saved/custom ``_preview_fields_<type>`` configuration that names a field
  which has since been switched off in the template no longer renders it.
- The preview image is taken from ``portrait`` / ``image`` / ``map_image``
  only when that section is enabled in the template.

Run with:  QT_QPA_PLATFORM=offscreen python -m pytest \
               test_hover_preview_sections.py -v
"""

from __future__ import annotations

import base64
import os
import pathlib
import sys
import types

import pytest

# Widgets are exercised headless.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

# `ui/__init__.py` pulls in MainWindow, which imports the calendar dialogs. If a
# calendar module is temporarily unparsable (calendar work is owned elsewhere),
# load the ui submodules directly instead of failing the whole module.
try:
    import ui  # noqa: F401
except SyntaxError:  # pragma: no cover - only while a calendar module is broken
    _ui_pkg = types.ModuleType("ui")
    _ui_pkg.__path__ = [str(pathlib.Path(__file__).resolve().parent / "ui")]
    sys.modules["ui"] = _ui_pkg

from database import crud  # noqa: E402
from database.manager import DatabaseManager  # noqa: E402
from database.models import Article, ArticleTemplate, FieldDefinition  # noqa: E402
from ui.hover_preview import HoverPreviewWidget  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def db():
    """Fresh in-memory database for each test."""
    DatabaseManager._instance = None
    manager = DatabaseManager()
    manager.open(":memory:")
    yield manager
    manager.close()
    DatabaseManager._instance = None


def _starship_template(secret_enabled: bool = False,
                       portrait_enabled: bool = True) -> ArticleTemplate:
    return ArticleTemplate(
        type_name="Starship",
        field_definitions=[
            FieldDefinition(name="class", label="Class"),
            FieldDefinition(name="secret", label="Secret",
                            enabled=secret_enabled),
            FieldDefinition(name="portrait", label="Portrait",
                            field_type="image", enabled=portrait_enabled),
        ],
    )


def _preview(qapp, template: ArticleTemplate,
             article: Article) -> HoverPreviewWidget:
    """Build a preview widget populated for *article* under *template*."""
    widget = HoverPreviewWidget()
    widget._template = template
    widget._populate(article)
    return widget


def _rendered_field_labels(widget: HoverPreviewWidget) -> list[str]:
    """Collect the field-name labels currently laid out in the preview."""
    labels: list[str] = []
    layout = widget.fields_container
    for i in range(layout.count()):
        row = layout.itemAt(i)
        if row is None or row.layout() is None:
            continue
        name_item = row.layout().itemAt(0)
        if name_item is not None and name_item.widget() is not None:
            labels.append(name_item.widget().text().rstrip(":"))
    return labels


# A 2x2 solid PNG — enough for QPixmap to load without needing Pillow.
_PNG_1X1 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8"
    "z8DAwMDAxMDAwMDAAAANHQEDasKb6QAAAABJRU5ErkJggg=="
)


def _png(tmp_path: pathlib.Path) -> str:
    """Write a tiny real PNG so the preview's os.path.isfile check passes."""
    path = tmp_path / "portrait.png"
    path.write_bytes(base64.b64decode(_PNG_1X1))
    return str(path)


# ---------------------------------------------------------------------------
# 1. Saved preview-field configuration vs. disabled sections
# ---------------------------------------------------------------------------

def test_saved_preview_fields_drop_now_disabled_section(db, qapp):
    """A saved `_preview_fields_Starship` list is filtered by enabled fields."""
    template = _starship_template(secret_enabled=False)
    article = Article(
        title="ISS Horizon",
        article_type="Starship",
        template_fields={"class": "Frigate", "secret": "hidden"},
    )

    widget = HoverPreviewWidget()
    # Saved before the user switched the "Secret" section off.
    widget.configure_preview_fields("Starship", ["class", "secret"])
    widget._template = template
    widget._populate(article)

    assert widget._get_visible_fields("Starship") == ["class"]
    assert _rendered_field_labels(widget) == ["Class"]
    widget.deleteLater()


def test_saved_preview_fields_keep_enabled_sections(db, qapp):
    """Filtering does not remove sections that are still enabled."""
    template = _starship_template(secret_enabled=True)
    article = Article(
        title="ISS Horizon",
        article_type="Starship",
        template_fields={"class": "Frigate", "secret": "revealed"},
    )

    widget = HoverPreviewWidget()
    widget.configure_preview_fields("Starship", ["class", "secret"])
    widget._template = template
    widget._populate(article)

    assert widget._get_visible_fields("Starship") == ["class", "secret"]
    assert _rendered_field_labels(widget) == ["Class", "Secret"]
    widget.deleteLater()


def test_saved_preview_fields_unfiltered_without_template(db, qapp):
    """Types with no template have no sections, so the saved list stands."""
    article = Article(
        title="Aldric",
        article_type="Character",
        template_fields={"role": "King"},
    )

    widget = HoverPreviewWidget()
    widget.configure_preview_fields("Character", ["role"])
    widget._template = None
    widget._populate(article)

    assert widget._get_visible_fields("Character") == ["role"]
    widget.deleteLater()


# ---------------------------------------------------------------------------
# 2. Preview image vs. a disabled image section
# ---------------------------------------------------------------------------

def test_disabled_portrait_section_hides_image(db, qapp, tmp_path):
    """A portrait stored for a switched-off section is not shown."""
    template = _starship_template(portrait_enabled=False)
    article = Article(
        title="ISS Horizon",
        article_type="Starship",
        template_fields={"class": "Frigate", "portrait": _png(tmp_path)},
    )

    widget = _preview(qapp, template, article)

    assert widget.portrait_label.pixmap().isNull()
    assert widget.portrait_label.text() != ""
    widget.deleteLater()



def test_enabled_portrait_section_shows_image(db, qapp, tmp_path):
    """The same stored portrait is shown while its section is enabled."""
    template = _starship_template(portrait_enabled=True)
    article = Article(
        title="ISS Horizon",
        article_type="Starship",
        template_fields={"class": "Frigate", "portrait": _png(tmp_path)},
    )

    widget = _preview(qapp, template, article)

    assert not widget.portrait_label.pixmap().isNull()
    widget.deleteLater()
