"""LoreKeeper — Desktop user interface (PySide6)."""

from ui.main_window import MainWindow
from ui.theme import ThemeManager
from ui.template_editor import TemplateEditorDialog, TemplateManagementDialog
from ui.form_builder import DynamicForm, FormFieldWidget
from ui.default_templates import seed_default_templates, ensure_default_templates
from ui.wiki_links import WikiTextBrowser, parse_wiki_links, find_backlinks, render_wiki_content
from ui.hover_preview import HoverPreviewWidget, HoverTracker
from ui.travel_map import TravelMapWidget, MapNodeItem, MapConnectionItem, MapScene

__all__ = [
    "MainWindow",
    "ThemeManager",
    "TemplateEditorDialog",
    "TemplateManagementDialog",
    "DynamicForm",
    "FormFieldWidget",
    "seed_default_templates",
    "ensure_default_templates",
    "WikiTextBrowser",
    "parse_wiki_links",
    "find_backlinks",
    "render_wiki_content",
    "HoverPreviewWidget",
    "HoverTracker",
    "TravelMapWidget",
    "MapNodeItem",
    "MapConnectionItem",
    "MapScene",
]