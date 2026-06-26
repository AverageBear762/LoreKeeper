"""
LoreKeeper — Interactive Location Travel Map.

Uses Qt Graphics View Framework (QGraphicsView / QGraphicsScene) to create
an interactive canvas where users can:
- Place, drag, and label location nodes (linked to wiki articles)
- Create, edit, and remove travel connections between nodes
- Import a background map image
- Hover for article previews, click to navigate, double-click to edit
- Search/filter nodes
- Save/load layouts to/from SQLite
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import (
    Qt,
    QLineF,
    QPointF,
    QRectF,
    Signal,
    Slot,
    QTimer,
)
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QIcon,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QTransform,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsSimpleTextItem,
    QGraphicsTextItem,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from database import crud
from database.manager import DatabaseManager
from database.models import Article, MapConnection, MapNode


# ======================================================================
#  Custom QGraphicsItem for a map node
# ======================================================================

class MapNodeItem(QGraphicsEllipseItem):
    """A draggable location node on the travel map.
    
    Uses callbacks instead of Qt Signals because QGraphicsEllipseItem
    does not inherit from QObject.
    """

    NODE_RADIUS = 18
    DEFAULT_COLOR = QColor(13, 110, 253)
    HOVER_COLOR = QColor(255, 193, 7)
    SELECTED_COLOR = QColor(220, 53, 69)

    def __init__(
        self,
        node_data: MapNode,
        article_title: str = "Untitled",
        article_type: str = "Location",
        on_moved: Optional[callable] = None,
        on_clicked: Optional[callable] = None,
        on_double_clicked: Optional[callable] = None,
        parent=None,
    ) -> None:
        super().__init__(
            -self.NODE_RADIUS, -self.NODE_RADIUS,
            self.NODE_RADIUS * 2, self.NODE_RADIUS * 2,
            parent=parent,
        )
        self._node_data = node_data
        self._article_title = article_title
        self._article_type = article_type
        self._on_moved = on_moved
        self._on_clicked = on_clicked
        self._on_double_clicked = on_double_clicked

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setZValue(10)

        # Default appearance
        self._base_color = self.DEFAULT_COLOR
        self._is_hovered = False
        self._update_appearance()

        # Label
        self._label = QGraphicsSimpleTextItem(article_title, self)
        self._label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._label.setBrush(QColor(33, 37, 41))
        self._label.setPos(self.NODE_RADIUS + 4, -8)
        self._label.setZValue(11)
        self._update_label_visibility(node_data.label_visible)

        # Sync position from DB
        self.setPos(node_data.x, node_data.y)

    def _update_appearance(self) -> None:
        """Update the node's visual style."""
        if self.isSelected():
            color = self.SELECTED_COLOR
        elif self._is_hovered:
            color = self.HOVER_COLOR
        else:
            color = self._base_color

        self.setBrush(QBrush(color))
        pen = QPen(QColor(255, 255, 255), 2)
        pen.setCosmetic(True)
        self.setPen(pen)

    def _update_label_visibility(self, visible: bool) -> None:
        self._label.setVisible(visible)

    # ----------------------------------------------------------------
    # Overrides
    # ----------------------------------------------------------------

    def hoverEnterEvent(self, event) -> None:
        self._is_hovered = True
        self._update_appearance()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._is_hovered = False
        self._update_appearance()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._on_clicked:
            self._on_clicked(self._node_data.id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._on_double_clicked:
            self._on_double_clicked(self._node_data.id)
        super().mouseDoubleClickEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self._on_moved:
                self._node_data.x = self.pos().x()
                self._node_data.y = self.pos().y()
                self._on_moved(self._node_data.id, self.pos().x(), self.pos().y())
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None) -> None:
        """Draw the node circle with a subtle gradient."""
        rect = self.rect()
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        base = self.brush().color()
        grad.setColorAt(0, base.lighter(130))
        grad.setColorAt(1, base)
        painter.setBrush(QBrush(grad))
        painter.setPen(self.pen())
        painter.drawEllipse(rect)

        # Draw type icon letter in center
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.setPen(QColor(255, 255, 255))
        icon = self._type_icon_letter(self._article_type)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, icon)

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    @property
    def node_id(self) -> str:
        return self._node_data.id

    @property
    def article_id(self) -> str:
        return self._node_data.article_id

    @property
    def article_title(self) -> str:
        return self._article_title

    @property
    def article_type(self) -> str:
        return self._article_type

    @property
    def map_node(self) -> MapNode:
        return self._node_data

    def set_title(self, title: str) -> None:
        self._article_title = title
        self._label.setText(title)

    def set_label_visible(self, visible: bool) -> None:
        self._node_data.label_visible = visible
        self._label.setVisible(visible)

    def toggle_label(self) -> None:
        self.set_label_visible(not self._node_data.label_visible)

    @staticmethod
    def _type_icon_letter(article_type: str) -> str:
        mapping = {
            "Location": "L", "City": "C", "Town": "T", "Village": "V",
            "Dungeon": "D", "Castle": "C", "Settlement": "S",
            "Nation": "N", "Tavern": "T", "Temple": "T",
            "Character": "🧑", "Faction": "⚜",
        }
        return mapping.get(article_type, "📍")

    @staticmethod
    def bounding_rect_for_pos(x: float, y: float) -> QRectF:
        r = MapNodeItem.NODE_RADIUS
        return QRectF(x - r, y - r, r * 2, r * 2)


# ======================================================================
#  Custom QGraphicsItem for a connection (path) between two nodes
# ======================================================================

class MapConnectionItem(QGraphicsLineItem):
    """A travel path/connection between two map nodes."""

    def __init__(
        self,
        conn_data: MapConnection,
        node_a: MapNodeItem,
        node_b: MapNodeItem,
        on_clicked: Optional[callable] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._conn_data = conn_data
        self._node_a = node_a
        self._node_b = node_b
        self._on_clicked = on_clicked
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setZValue(5)

        # Style based on danger
        self._update_pen()

        # Label (distance / travel time)
        label_text = self._build_label_text()
        self._label = QGraphicsSimpleTextItem(label_text, self)
        self._label.setFont(QFont("Segoe UI", 8))
        self._label.setBrush(QColor(100, 100, 100))
        self._label.setZValue(6)

        # Position the label at midpoint
        self._update_position()

    def _build_label_text(self) -> str:
        parts = []
        if self._conn_data.distance > 0:
            parts.append(f"{self._conn_data.distance:.0f}km")
        if self._conn_data.travel_time:
            parts.append(self._conn_data.travel_time)
        return " | ".join(parts) if parts else ""

    def _update_pen(self) -> None:
        danger = self._conn_data.danger.lower()
        colors = {
            "low": QColor(40, 167, 69),      # green
            "medium": QColor(255, 193, 7),   # amber
            "high": QColor(220, 53, 69),     # red
            "extreme": QColor(128, 0, 128),  # purple
        }
        color = colors.get(danger, QColor(108, 117, 125))

        pen = QPen(color, 2.5)
        pen.setCosmetic(True)
        if danger in ("high", "extreme"):
            pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(pen)

    def _update_position(self) -> None:
        """Update the line endpoints and label position."""
        p1 = self._node_a.pos()
        p2 = self._node_b.pos()
        self.setLine(QLineF(p1, p2))

        mid = (p1 + p2) / 2
        self._label.setPos(mid.x() - self._label.boundingRect().width() / 2,
                           mid.y() - 20)

    def sync_position(self) -> None:
        """Called when a connected node moves."""
        self._update_position()

    # ----------------------------------------------------------------
    # Hover
    # ----------------------------------------------------------------

    def hoverEnterEvent(self, event) -> None:
        pen = self.pen()
        pen.setWidth(4)
        self.setPen(pen)
        self._label.setBrush(QColor(0, 0, 0))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._update_pen()
        self._label.setBrush(QColor(100, 100, 100))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._on_clicked:
            self._on_clicked(self._conn_data.id)
        super().mousePressEvent(event)

    def paint(self, painter, option, widget=None) -> None:
        super().paint(painter, option, widget)
        # Draw arrowhead at midpoint
        line = self.line()
        if line.length() < 20:
            return
        mid = line.center()
        angle = math.atan2(-line.dy(), line.dx())
        arrow_size = 8
        p1 = mid + QPointF(
            math.cos(angle + math.pi / 6) * arrow_size,
            -math.sin(angle + math.pi / 6) * arrow_size,
        )
        p2 = mid + QPointF(
            math.cos(angle - math.pi / 6) * arrow_size,
            -math.sin(angle - math.pi / 6) * arrow_size,
        )
        painter.setBrush(self.pen().color())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([mid, p1, p2]))

    @property
    def connection_id(self) -> str:
        return self._conn_data.id

    @property
    def connection_data(self) -> MapConnection:
        return self._conn_data

    @property
    def node_a_id(self) -> str:
        return self._conn_data.node_a_id

    @property
    def node_b_id(self) -> str:
        return self._conn_data.node_b_id


# ======================================================================
#  MapScene — manages all graphics items
# ======================================================================

class MapScene(QGraphicsScene):
    """QGraphicsScene for the travel map, managing nodes and connections."""

    node_added = Signal(str)             # node_id
    node_selected = Signal(str)          # node_id — for article navigation
    node_double_clicked = Signal(str)    # node_id — for edit
    node_moved = Signal(str, float, float)  # node_id, x, y
    connection_added = Signal(str)       # connection_id
    connection_selected = Signal(str)    # connection_id

    NODE_COLORS = {
        "Location": QColor(13, 110, 253),
        "City": QColor(13, 110, 253),
        "Town": QColor(23, 162, 184),
        "Village": QColor(40, 167, 69),
        "Dungeon": QColor(220, 53, 69),
        "Castle": QColor(108, 117, 125),
        "Settlement": QColor(111, 66, 193),
        "Nation": QColor(253, 126, 20),
        "Character": QColor(0, 123, 255),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._nodes: dict[str, MapNodeItem] = {}
        self._connections: dict[str, MapConnectionItem] = {}
        self._bg_image: Optional[QGraphicsPixmapItem] = None
        self._bg_pixmap: Optional[QPixmap] = None
        self._drawing_connection_nodes: list[MapNodeItem] = []
        self._temp_line: Optional[QGraphicsLineItem] = None

        self.setSceneRect(-2000, -2000, 4000, 4000)

    # ----------------------------------------------------------------
    # Background image
    # ----------------------------------------------------------------

    def set_background_image(self, path: str) -> bool:
        """Load and display a background map image."""
        if not os.path.isfile(path):
            return False

        pix = QPixmap(path)
        if pix.isNull():
            return False

        # Remove old background
        if self._bg_image:
            self.removeItem(self._bg_image)

        self._bg_pixmap = pix
        self._bg_image = QGraphicsPixmapItem(pix)
        self._bg_image.setZValue(-100)
        self._bg_image.setOpacity(0.8)
        self.addItem(self._bg_image)

        # Resize scene to fit
        self.setSceneRect(
            -pix.width() / 2 - 200, -pix.height() / 2 - 200,
            pix.width() + 400, pix.height() + 400,
        )
        return True

    def remove_background(self) -> None:
        if self._bg_image:
            self.removeItem(self._bg_image)
            self._bg_image = None
            self._bg_pixmap = None

    # ----------------------------------------------------------------
    # Node management
    # ----------------------------------------------------------------

    def add_node(
        self,
        node_data: MapNode,
        article_title: str = "Untitled",
        article_type: str = "Location",
    ) -> MapNodeItem:
        """Add a node to the scene (from DB data)."""
        item = MapNodeItem(
            node_data, article_title, article_type,
            on_moved=self._on_node_moved,
            on_clicked=lambda nid: self.node_selected.emit(nid),
            on_double_clicked=lambda nid: self.node_double_clicked.emit(nid),
        )
        color = self.NODE_COLORS.get(article_type, MapNodeItem.DEFAULT_COLOR)
        item._base_color = color
        item._update_appearance()

        self.addItem(item)
        self._nodes[node_data.id] = item

        return item

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and its connections."""
        if node_id not in self._nodes:
            return False

        # Remove all connections for this node
        to_remove = [
            cid for cid, conn in self._connections.items()
            if conn.node_a_id == node_id or conn.node_b_id == node_id
        ]
        for cid in to_remove:
            self.remove_connection(cid)

        # Remove node from DB
        crud.delete_map_node(node_id)

        # Remove from scene
        item = self._nodes.pop(node_id)
        self.removeItem(item)
        return True

    def create_new_node(
        self,
        article_id: str,
        article_title: str,
        article_type: str,
        x: float,
        y: float,
    ) -> MapNodeItem:
        """Create a new node (DB + scene)."""
        node_data = MapNode(
            article_id=article_id,
            x=x,
            y=y,
            label_visible=True,
        )
        crud.create_map_node(node_data)
        item = self.add_node(node_data, article_title, article_type)
        self.node_added.emit(node_data.id)
        return item

    def find_node_by_article(self, article_id: str) -> Optional[MapNodeItem]:
        for item in self._nodes.values():
            if item.article_id == article_id:
                return item
        return None

    def get_all_nodes(self) -> list[MapNodeItem]:
        return list(self._nodes.values())

    # ----------------------------------------------------------------
    # Connection management
    # ----------------------------------------------------------------

    def add_connection(self, conn_data: MapConnection) -> Optional[MapConnectionItem]:
        """Add a connection (from DB data) between two existing nodes."""
        if conn_data.node_a_id not in self._nodes:
            return None
        if conn_data.node_b_id not in self._nodes:
            return None

        item = MapConnectionItem(
            conn_data,
            self._nodes[conn_data.node_a_id],
            self._nodes[conn_data.node_b_id],
            on_clicked=lambda cid: self.connection_selected.emit(cid),
        )
        self.addItem(item)
        self._connections[conn_data.id] = item
        return item

    def remove_connection(self, connection_id: str) -> bool:
        if connection_id not in self._connections:
            return False
        crud.delete_map_connection(connection_id)
        item = self._connections.pop(connection_id)
        self.removeItem(item)
        return True

    def create_new_connection(
        self, node_a_id: str, node_b_id: str
    ) -> Optional[MapConnectionItem]:
        """Create a new connection between two nodes."""
        # Check if already connected
        for conn in self._connections.values():
            if (conn.node_a_id == node_a_id and conn.node_b_id == node_b_id) or \
               (conn.node_a_id == node_b_id and conn.node_b_id == node_a_id):
                return None  # Already connected

        conn_data = MapConnection(
            node_a_id=node_a_id,
            node_b_id=node_b_id,
            distance=0,
            travel_time="",
            terrain="",
            danger="low",
            notes="",
        )
        crud.create_map_connection(conn_data)
        item = self.add_connection(conn_data)
        if item:
            self.connection_added.emit(conn_data.id)
        return item

    def get_all_connections(self) -> list[MapConnectionItem]:
        return list(self._connections.values())

    # ----------------------------------------------------------------
    # Syncing
    # ----------------------------------------------------------------

    def sync_all_positions(self) -> None:
        """Update connection line positions after node drags."""
        for conn in self._connections.values():
            conn.sync_position()

    def _on_node_moved(self, node_id: str, x: float, y: float) -> None:
        """Node was dragged — update DB and connection lines."""
        crud.update_node_position(node_id, x, y)
        self.sync_all_positions()
        self.node_moved.emit(node_id, x, y)

    # ----------------------------------------------------------------
    # Interaction helpers
    # ----------------------------------------------------------------

    def start_drawing_connection(self, node: MapNodeItem) -> None:
        """Begin drawing a connection from *node*."""
        self._drawing_connection_nodes = [node]
        pos = node.pos()
        self._temp_line = QGraphicsLineItem(
            QLineF(pos, pos + QPointF(1, 0))
        )
        pen = QPen(QColor(108, 117, 125), 2, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self._temp_line.setPen(pen)
        self._temp_line.setZValue(20)
        self.addItem(self._temp_line)

    def update_drawing_connection(self, scene_pos: QPointF) -> None:
        """Update the temporary line endpoint as the mouse moves."""
        if self._temp_line and self._drawing_connection_nodes:
            p1 = self._drawing_connection_nodes[0].pos()
            self._temp_line.setLine(QLineF(p1, scene_pos))

    def finish_drawing_connection(self, target_node: MapNodeItem) -> bool:
        """Finish drawing — create connection if valid."""
        if not self._drawing_connection_nodes:
            return False

        source = self._drawing_connection_nodes[0]
        # Clean up temp line
        if self._temp_line:
            self.removeItem(self._temp_line)
            self._temp_line = None

        self._drawing_connection_nodes = []

        if source.node_id == target_node.node_id:
            return False  # Can't connect to self

        item = self.create_new_connection(source.node_id, target_node.node_id)
        return item is not None

    def cancel_drawing_connection(self) -> None:
        """Cancel an in-progress connection draw."""
        if self._temp_line:
            self.removeItem(self._temp_line)
            self._temp_line = None
        self._drawing_connection_nodes = []

    @property
    def is_drawing_connection(self) -> bool:
        return bool(self._drawing_connection_nodes)


# ======================================================================
#  TravelMapWidget — main widget containing the map view + toolbar
# ======================================================================

class TravelMapWidget(QWidget):
    """Main travel map widget — wraps the QGraphicsView and toolbar."""

    article_navigated = Signal(str)        # article_id
    article_edit_requested = Signal(str)   # article_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = MapScene(self)
        self._hover_tooltip: Optional[Any] = None  # HoverPreviewWidget
        self._hover_timer = QTimer()
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(200)
        self._hover_timer.timeout.connect(self._on_hover_timeout)
        self._hovered_node: Optional[MapNodeItem] = None

        self._build_ui()
        self._load_from_db()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Top toolbar ---
        toolbar = QToolBar("Map Toolbar")
        toolbar.setMovable(False)

        self.act_bg_image = QAction("🗺 Load Background", self)
        self.act_bg_image.triggered.connect(self._on_load_background)
        toolbar.addAction(self.act_bg_image)

        self.act_remove_bg = QAction("✕ Clear BG", self)
        self.act_remove_bg.triggered.connect(self._scene.remove_background)
        toolbar.addAction(self.act_remove_bg)

        toolbar.addSeparator()

        # Connect nodes toggle
        self.act_connect = QAction("🔗 Connect", self)
        self.act_connect.setCheckable(True)
        self.act_connect.setToolTip("Toggle connection-drawing mode")
        self.act_connect.triggered.connect(self._on_toggle_connect_mode)
        toolbar.addAction(self.act_connect)

        toolbar.addSeparator()

        self.act_zoom_in = QAction("🔍+ Zoom In", self)
        self.act_zoom_in.setShortcut(QKeySequence("Ctrl++"))
        self.act_zoom_in.triggered.connect(self._zoom_in)
        toolbar.addAction(self.act_zoom_in)

        self.act_zoom_out = QAction("🔍− Zoom Out", self)
        self.act_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        self.act_zoom_out.triggered.connect(self._zoom_out)
        toolbar.addAction(self.act_zoom_out)

        self.act_fit = QAction("⊞ Fit All", self)
        self.act_fit.triggered.connect(self._fit_all)
        toolbar.addAction(self.act_fit)

        toolbar.addSeparator()

        self.node_search = QLineEdit()
        self.node_search.setPlaceholderText("🔍 Search nodes...")
        self.node_search.setMaximumWidth(200)
        self.node_search.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.node_search)

        # Connection mode status label
        self._connect_status = QLabel("")
        self._connect_status.setStyleSheet("color: #dc3545; font-weight: bold; padding: 0 8px;")
        toolbar.addWidget(self._connect_status)

        layout.addWidget(toolbar)

        # --- Graphics View ---
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._view.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.SmartViewportUpdate
        )
        self._view.setMouseTracking(True)
        self._view.setMinimumSize(400, 300)
        self._view.viewport().installEventFilter(self)
        layout.addWidget(self._view, 1)

        # --- Connection viewer sidebar (collapsed) ---
        self._sidebar = QWidget()
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(4, 4, 4, 4)
        self._conn_info = QLabel("Click a connection to see details")
        self._conn_info.setWordWrap(True)
        self._conn_info.setStyleSheet("font-size: 11px; color: #6c757d; padding: 4px;")
        sidebar_layout.addWidget(self._conn_info)
        sidebar_layout.addStretch(1)

        # --- Connect scene signals ---
        self._scene.node_selected.connect(self._on_node_selected)
        self._scene.node_double_clicked.connect(self._on_node_double_clicked)
        self._scene.connection_selected.connect(self._on_connection_selected)

    # ----------------------------------------------------------------
    # Loading from DB
    # ----------------------------------------------------------------

    def _load_from_db(self) -> None:
        """Load all map nodes and connections from the database."""
        nodes, connections = crud.get_full_map_data()

        for nd in nodes:
            article = crud.get_article(nd.article_id)
            title = article.title if article else "Unknown"
            atype = article.article_type if article else "Location"
            self._scene.add_node(nd, title, atype)

        for conn in connections:
            self._scene.add_connection(conn)

    def reload(self) -> None:
        """Reload all map data from the database."""
        self._scene._nodes.clear()
        self._scene._connections.clear()
        self._scene.clear()
        self._load_from_db()

    def save_to_db(self) -> None:
        """Save current node positions to the DB (connections already saved)."""
        for node_item in self._scene.get_all_nodes():
            crud.update_map_node(node_item.map_node)

    # ----------------------------------------------------------------
    # View controls
    # ----------------------------------------------------------------

    def _zoom_in(self) -> None:
        self._view.scale(1.25, 1.25)

    def _zoom_out(self) -> None:
        self._view.scale(0.8, 0.8)

    def _fit_all(self) -> None:
        self._view.fitInView(
            self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
        )

    # ----------------------------------------------------------------
    # Background
    # ----------------------------------------------------------------

    def _on_load_background(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Background Map Image", "",
            "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp);;All Files (*)",
        )
        if path and self._scene.set_background_image(path):
            self._fit_all()

    # ----------------------------------------------------------------
    # Search / filter
    # ----------------------------------------------------------------

    def _on_toggle_connect_mode(self, checked: bool) -> None:
        """Toggle connection-drawing mode on/off."""
        if checked:
            self.act_connect.setText("🔗 Connecting...")
            self._connect_status.setText("Click a node to start")
            self._view.setCursor(Qt.CursorShape.CrossCursor)
            self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        else:
            self.act_connect.setText("🔗 Connect")
            self._connect_status.setText("")
            self._view.setCursor(Qt.CursorShape.ArrowCursor)
            self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self._scene.cancel_drawing_connection()

    def _on_search_changed(self, text: str) -> None:
        """Filter visible nodes based on search text."""
        text = text.lower()
        for node_item in self._scene.get_all_nodes():
            match = text in node_item.article_title.lower()
            node_item.setVisible(match or not text)
            if match or not text:
                node_item.setOpacity(1.0)
            else:
                node_item.setOpacity(0.15)

    # ----------------------------------------------------------------
    # Node interaction
    # ----------------------------------------------------------------

    def _on_node_selected(self, node_id: str) -> None:
        """Single click — navigate to the article."""
        node_item = self._scene._nodes.get(node_id)
        if node_item:
            self.article_navigated.emit(node_item.article_id)

    def _on_node_double_clicked(self, node_id: str) -> None:
        """Double click — open edit overlay."""
        node_item = self._scene._nodes.get(node_id)
        if node_item:
            self.article_edit_requested.emit(node_item.article_id)

    def _on_connection_selected(self, connection_id: str) -> None:
        """Show connection details in the sidebar."""
        conn_item = self._scene._connections.get(connection_id)
        if not conn_item:
            return
        cd = conn_item.connection_data
        info = (
            f"<b>Connection Details</b><br>"
            f"Distance: {cd.distance} km<br>"
            f"Travel Time: {cd.travel_time or 'N/A'}<br>"
            f"Terrain: {cd.terrain or 'N/A'}<br>"
            f"Danger: {cd.danger}<br>"
            f"Notes: {cd.notes or 'None'}"
        )
        self._conn_info.setText(info)

        # Show a quick edit dialog
        self._show_connection_edit_dialog(cd)

    def _show_connection_edit_dialog(self, conn_data: MapConnection) -> None:
        """Dialog to edit connection metadata."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Travel Path")
        dialog.setMinimumWidth(350)

        layout = QFormLayout(dialog)

        distance = QSpinBox()
        distance.setRange(0, 99999)
        distance.setValue(int(conn_data.distance))
        layout.addRow("Distance (km):", distance)

        travel_time = QLineEdit(conn_data.travel_time)
        travel_time.setPlaceholderText("e.g. 3 days")
        layout.addRow("Travel Time:", travel_time)

        terrain = QLineEdit(conn_data.terrain)
        terrain.setPlaceholderText("e.g. mountain, forest")
        layout.addRow("Terrain:", terrain)

        danger = QComboBox()
        danger.addItems(["low", "medium", "high", "extreme"])
        idx = danger.findText(conn_data.danger)
        if idx >= 0:
            danger.setCurrentIndex(idx)
        layout.addRow("Danger:", danger)

        notes = QLineEdit(conn_data.notes)
        layout.addRow("Notes:", notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        delete_btn = QPushButton("Delete Connection")
        delete_btn.setStyleSheet("QPushButton { color: #dc3545; }")
        delete_btn.clicked.connect(lambda: self._delete_connection(conn_data.id, dialog))
        layout.addRow(delete_btn)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            conn_data.distance = distance.value()
            conn_data.travel_time = travel_time.text().strip()
            conn_data.terrain = terrain.text().strip()
            conn_data.danger = danger.currentText().lower()
            conn_data.notes = notes.text().strip()
            crud.update_map_connection(conn_data)
            if conn_data.id in self._scene._connections:
                self._scene._connections[conn_data.id]._update_pen()
                self._scene._connections[conn_data.id]._update_position()

    def _delete_connection(self, connection_id: str, dialog: QDialog) -> None:
        self._scene.remove_connection(connection_id)
        dialog.accept()

    # ----------------------------------------------------------------
    # Context menu
    # ----------------------------------------------------------------

    def contextMenuEvent(self, event) -> None:
        """Right-click context menu on the map."""
        scene_pos = self._view.mapToScene(self._view.viewport().mapFromGlobal(event.globalPos()))
        item = self._scene.itemAt(scene_pos, self._view.transform())

        menu = QWidget()

        if isinstance(item, MapNodeItem):
            self._show_node_context_menu(item, scene_pos)
        elif isinstance(item, MapConnectionItem):
            self._show_connection_context_menu(item)
        else:
            self._show_canvas_context_menu(scene_pos)

        event.accept()

    def _show_node_context_menu(self, node: MapNodeItem, scene_pos: QPointF) -> None:
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)

        act_open = menu.addAction("📄 Open Article")
        act_edit = menu.addAction("✏ Quick Edit")
        menu.addSeparator()
        act_toggle_label = menu.addAction("👁 Toggle Label")
        act_connect = menu.addAction("🔗 Start Connection")
        menu.addSeparator()
        act_create_link = menu.addAction("🔗 Create Linked Article Here")
        act_delete = menu.addAction("🗑 Delete Node")

        action = menu.exec(QCursor.pos())

        if action == act_open:
            self.article_navigated.emit(node.article_id)
        elif action == act_edit:
            self.article_edit_requested.emit(node.article_id)
        elif action == act_toggle_label:
            node.toggle_label()
            crud.update_map_node(node.map_node)
        elif action == act_connect:
            self._scene.start_drawing_connection(node)
        elif action == act_create_link:
            self._create_article_at_node(node, scene_pos)
        elif action == act_delete:
            result = QMessageBox.question(
                self, "Delete Node",
                f'Delete node "{node.article_title}"?\nThis removes the node from the map but does NOT delete the article.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if result == QMessageBox.StandardButton.Yes:
                self._scene.remove_node(node.node_id)

    def _create_article_at_node(self, existing_node: MapNodeItem, pos: QPointF) -> None:
        """Create a new article + map node at the given position."""
        from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QVBoxLayout, QLabel

        dialog = QDialog(self)
        dialog.setWindowTitle("New Article on Map")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Article Title:"))
        title_edit = QLineEdit()
        title_edit.setPlaceholderText("e.g., Darkwood Forest")
        layout.addWidget(title_edit)
        layout.addWidget(QLabel("Type:"))
        combo = QComboBox()
        combo.addItems(crud.list_all_article_types())
        layout.addWidget(combo)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            title = title_edit.text().strip()
            if not title:
                return
            atype = combo.currentText()
            article = Article(title=title, content="", article_type=atype)
            crud.create_article(article)
            self._scene.create_new_node(article.id, title, atype, pos.x(), pos.y())

    def _show_connection_context_menu(self, conn: MapConnectionItem) -> None:
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        act_edit = menu.addAction("✏ Edit Connection")
        act_delete = menu.addAction("🗑 Delete")

        action = menu.exec(QCursor.pos())

        if action == act_edit:
            self._show_connection_edit_dialog(conn.connection_data)
        elif action == act_delete:
            self._scene.remove_connection(conn.connection_id)

    def _show_canvas_context_menu(self, scene_pos: QPointF) -> None:
        """Right-click on empty canvas — create a new node from existing article."""
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        act_new = menu.addAction("📄 New Article Here")
        act_place = menu.addAction("📍 Place Existing Article Here...")
        menu.addSeparator()
        act_fit = menu.addAction("⊞ Fit All")

        action = menu.exec(QCursor.pos())

        if action == act_new:
            self._create_article_at_node(None, scene_pos)
        elif action == act_place:
            self._show_place_existing_dialog(scene_pos)
        elif action == act_fit:
            self._fit_all()

    def _show_place_existing_dialog(self, scene_pos: QPointF) -> None:
        """Dialog to select an existing Location-type article to place on the map."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Place Existing Article")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Select an article to place on the map:"))

        list_widget = QListWidget()
        # Show Location-type articles that don't already have a map node
        locations = crud.list_articles(article_type="Location", limit=200)
        existing_node_articles = {
            item.article_id for item in self._scene.get_all_nodes()
        }
        for loc in locations:
            if loc.id not in existing_node_articles:
                item = QListWidgetItem(f"{loc.title} ({loc.id[:8]}...)")
                item.setData(Qt.ItemDataRole.UserRole, loc.id)
                list_widget.addItem(item)

        layout.addWidget(list_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = list_widget.currentItem()
            if selected:
                article_id = selected.data(Qt.ItemDataRole.UserRole)
                article = crud.get_article(article_id)
                if article:
                    self._scene.create_new_node(
                        article_id, article.title, article.article_type,
                        scene_pos.x(), scene_pos.y(),
                    )

    # ----------------------------------------------------------------
    # Hover tooltip (uses HoverPreviewWidget)
    # ----------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        if obj is self._view.viewport():
            if event.type() == event.Type.MouseMove:
                self._on_view_mouse_move(event)
                if self._scene.is_drawing_connection:
                    scene_pos = self._view.mapToScene(event.position().toPoint())
                    self._scene.update_drawing_connection(scene_pos)
            elif event.type() == event.Type.MouseButtonPress:
                if self.act_connect.isChecked() or self._scene.is_drawing_connection:
                    self._on_connect_click(event)
                    return True
            elif event.type() == event.Type.Leave:
                self._hide_tooltip()
        return super().eventFilter(obj, event)

    def _on_view_mouse_move(self, event) -> None:
        """Track mouse over map nodes for hover tooltips."""
        scene_pos = self._view.mapToScene(event.position().toPoint())
        item = self._scene.itemAt(scene_pos, self._view.transform())

        node_item = None
        while item and not isinstance(item, MapNodeItem):
            item = item.parentItem()
        if isinstance(item, MapNodeItem):
            node_item = item

        if node_item and node_item != self._hovered_node:
            self._hovered_node = node_item
            self._hover_timer.start()
        elif not node_item:
            self._hide_tooltip()
            self._hovered_node = None

    def _on_connect_click(self, event) -> None:
        """Handle mouse clicks in connection-drawing mode."""
        scene_pos = self._view.mapToScene(event.position().toPoint())
        item = self._scene.itemAt(scene_pos, self._view.transform())

        # Find the MapNodeItem that was clicked
        node_item = None
        while item and not isinstance(item, MapNodeItem):
            item = item.parentItem()
        if isinstance(item, MapNodeItem):
            node_item = item

        if node_item:
            if not self._scene.is_drawing_connection:
                # First click — start drawing from this node
                self._scene.start_drawing_connection(node_item)
                self._connect_status.setText("Now click another node to connect")
                self.act_connect.setChecked(True)
            else:
                # Second click — finish connection
                if self._scene.finish_drawing_connection(node_item):
                    self._connect_status.setText("Connection created!")
                    self.act_connect.setChecked(False)
                    self._on_toggle_connect_mode(False)
                else:
                    self._connect_status.setText("Already connected or invalid")
        else:
            # Clicked empty space — cancel
            self._scene.cancel_drawing_connection()
            self._connect_status.setText("")
            self.act_connect.setChecked(False)
            self._on_toggle_connect_mode(False)

    def _on_hover_timeout(self) -> None:
        """Show the hover tooltip for the currently hovered node."""
        if not self._hovered_node:
            return
        article = crud.get_article(self._hovered_node.article_id)
        if not article:
            return

        if self._hover_tooltip is None:
            from ui.hover_preview import HoverPreviewWidget
            self._hover_tooltip = HoverPreviewWidget(self)

        from ui.wiki_links import article_exists
        self._hover_tooltip.show_for_article(
            article.title,
            (QCursor.pos().x(), QCursor.pos().y()),
        )

    def _hide_tooltip(self) -> None:
        self._hover_timer.stop()
        if self._hover_tooltip:
            self._hover_tooltip.hide()

    # ----------------------------------------------------------------
    # Keyboard shortcuts
    # ----------------------------------------------------------------

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self._scene.is_drawing_connection:
                self._scene.cancel_drawing_connection()
            else:
                self.node_search.clearFocus()
        elif event.key() == Qt.Key.Key_Delete:
            selected = self._scene.selectedItems()
            for item in selected:
                if isinstance(item, MapNodeItem):
                    self._scene.remove_node(item.node_id)
                elif isinstance(item, MapConnectionItem):
                    self._scene.remove_connection(item.connection_id)
        super().keyPressEvent(event)