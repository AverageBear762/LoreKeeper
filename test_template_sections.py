"""
World Garden — Tests for configurable template sections (enable/disable).

Covers:
- Templates saved before this feature (no "enabled" key) load fully enabled.
- Disabling a section, saving through the template editor, and reloading
  keeps it disabled.
- The article form panel renders only enabled sections.
- Backup export/import preserves the flag (no silent re-enable).
- Saving an article keeps stored values of now-disabled sections.

Run with:  python -m pytest test_template_sections.py -v
"""

from __future__ import annotations

import json
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
from database.models import (  # noqa: E402
    Article,
    ArticleTemplate,
    FieldDefinition,
)
from ui.backup_manager import BackupManager  # noqa: E402
from ui.form_builder import DynamicForm  # noqa: E402
from ui.template_editor import FieldEditorRow, TemplateEditorDialog  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
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


def _two_field_template(second_enabled: bool = False) -> ArticleTemplate:
    return ArticleTemplate(
        type_name="Starship",
        field_definitions=[
            FieldDefinition(name="class", label="Class"),
            FieldDefinition(
                name="secret", label="Secret", enabled=second_enabled
            ),
        ],
    )


# ---------------------------------------------------------------------------
# 1. Backwards compatibility
# ---------------------------------------------------------------------------

def test_missing_enabled_key_defaults_to_enabled():
    """Old-style template JSON (no 'enabled' key) loads fully enabled."""
    row = {
        "id": "legacy-1",
        "type_name": "Legacy",
        "field_definitions": json.dumps(
            [
                {"name": "a", "label": "A", "field_type": "text"},
                {"name": "b", "label": "B", "field_type": "number",
                 "required": True},
            ]
        ),
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
    }
    template = ArticleTemplate.from_row(row)

    assert [fd.enabled for fd in template.field_definitions] == [True, True]
    assert len(template.enabled_field_definitions()) == 2


def test_null_enabled_key_defaults_to_enabled():
    """A null 'enabled' value is treated as enabled, not as disabled."""
    fd = FieldDefinition.from_dict({"name": "a", "enabled": None})
    assert fd.enabled is True


def test_old_template_round_trip_keeps_everything_enabled(db):
    """A template stored without the flag reloads from SQLite fully enabled."""
    template = _two_field_template(second_enabled=True)
    crud.create_template(template)

    # Simulate a pre-feature row: strip the key from the stored JSON.
    legacy_json = json.dumps(
        [
            {"name": "class", "label": "Class", "field_type": "text",
             "required": False, "options": [], "placeholder": ""},
        ]
    )
    DatabaseManager().execute(
        "UPDATE article_templates SET field_definitions = ? WHERE id = ?",
        (legacy_json, template.id),
    )
    DatabaseManager().commit()

    reloaded = crud.get_template(template.id)
    assert len(reloaded.field_definitions) == 1
    assert reloaded.field_definitions[0].enabled is True


# ---------------------------------------------------------------------------
# 2. Persistence through the template editor
# ---------------------------------------------------------------------------

def test_editor_row_reflects_and_reports_enabled_state(qapp):
    """The row's checkbox reflects the flag and feeds it back out."""
    row_on = FieldEditorRow(FieldDefinition(name="a", label="A"))
    assert row_on.enabled_cb.isChecked() is True
    assert row_on.get_field_definition().enabled is True

    row_off = FieldEditorRow(FieldDefinition(name="b", label="B", enabled=False))
    assert row_off.enabled_cb.isChecked() is False
    assert row_off.get_field_definition().enabled is False
    # Disabled rows stay visible and can be re-enabled.
    assert row_off.enabled_cb.isEnabled() is True
    assert row_off.name_edit.isEnabled() is False

    row_off.enabled_cb.setChecked(True)
    assert row_off.name_edit.isEnabled() is True
    assert row_off.get_field_definition().enabled is True


def test_disable_save_reload_keeps_section_disabled(db, qapp):
    """Unchecking a section in the editor and saving persists the flag."""
    template = _two_field_template(second_enabled=True)
    crud.create_template(template)

    dialog = TemplateEditorDialog(crud.get_template(template.id))
    assert len(dialog._field_rows) == 2
    assert all(r.enabled_cb.isChecked() for r in dialog._field_rows)

    dialog._field_rows[1].enabled_cb.setChecked(False)
    dialog._on_save()

    reloaded = crud.get_template(template.id)
    assert [fd.name for fd in reloaded.enabled_field_definitions()] == ["class"]
    assert reloaded.field_definitions[1].enabled is False
    # The disabled section is still part of the template, not deleted.
    assert len(reloaded.field_definitions) == 2


# ---------------------------------------------------------------------------
# 3. Consumers skip disabled sections
# ---------------------------------------------------------------------------

def test_form_panel_renders_only_enabled_sections(db, qapp):
    """The article form panel builds widgets only for enabled sections."""
    template = _two_field_template(second_enabled=False)
    form = DynamicForm()
    form.load_template(template, {"class": "Frigate", "secret": "hidden"})

    assert form.field_count == 1
    assert list(form.get_values().keys()) == ["class"]
    form.deleteLater()


def test_form_panel_renders_everything_when_all_enabled(db, qapp):
    template = _two_field_template(second_enabled=True)
    form = DynamicForm()
    form.load_template(template, {})
    assert form.field_count == 2
    form.deleteLater()


# ---------------------------------------------------------------------------
# 4. Backup round-trip
# ---------------------------------------------------------------------------

def test_backup_round_trip_preserves_disabled_flag(db, tmp_path):
    """Export/import must not silently re-enable a disabled section."""
    template = _two_field_template(second_enabled=False)
    crud.create_template(template)

    snapshot = tmp_path / "snapshot.json"
    BackupManager().export_json(str(snapshot))

    crud.delete_template(template.id)
    assert crud.get_template(template.id) is None

    BackupManager().import_json(str(snapshot))

    restored = crud.get_template(template.id)
    assert restored is not None
    by_name = {fd.name: fd.enabled for fd in restored.field_definitions}
    assert by_name == {"class": True, "secret": False}


# ---------------------------------------------------------------------------
# 5. Stored values of disabled sections survive a save
# ---------------------------------------------------------------------------

def test_article_save_keeps_value_of_disabled_section(db, qapp):
    """Editing an article does not drop data held by a disabled section."""
    from ui.article_view import ArticleView

    template = _two_field_template(second_enabled=False)
    crud.create_template(template)

    article = Article(
        title="ISS Horizon",
        article_type="Starship",
        template_fields={"class": "Frigate", "secret": "keep me"},
    )
    crud.create_article(article)

    view = ArticleView()
    view.load_article(crud.get_article(article.id))
    assert view.template_fields_panel.field_count == 1
    assert view.save() is True

    saved = crud.get_article(article.id)
    assert saved.template_fields["secret"] == "keep me"
    assert saved.template_fields["class"] == "Frigate"
    view.deleteLater()
