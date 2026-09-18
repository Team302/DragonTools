"""Auton Builder tab for DragonTools.

The Auton Builder lets a user assemble FRC autonomous routines from the objects
defined by the project's DTD schemas:

* ``AutonExample/auton.dtd``      - autons, primitives and snippet/zone references
* ``AutonExample/Zone/zone.dtd``  - zone geometry (rectangle / circle) + metadata

The editor is **DTD driven**: the allowed attributes and their enumerated values
are parsed from the DTDs at startup, so the UI only ever offers values the schema
allows. Mechanism state names (launcher / intake) are pulled from the reused
Mechanism Generator project data, and a sync action writes those states back into
the DTD metadata.

Layout (mirrors the Mechanism Generator style):

    +--------------------------------------------------------------+
    | File bar: Choreo folder | Auton v | Zone v | Update | Sync   |
    +----------------+---------------------------------------------+
    | Tree           | Field visualization (top of creator panel)  |
    | (Autons/       +---------------------------------------------+
    |  Zones/        | Contextual editor (DTD-driven properties)   |
    |  Snippets)     |                                             |
    +----------------+---------------------------------------------+
"""

import os
import re
import json
import math
import bisect
import xml.etree.ElementTree as ET

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:  # The generator is Qt-free and safe to import from the GUI layer.
    from generation.naming import state_enum, camel_case
except Exception:  # pragma: no cover - fallback if generation is unavailable
    def state_enum(name):
        cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", str(name)).strip("_").upper()
        return f"STATE_{cleaned}" if cleaned else "STATE_OFF"

    def camel_case(name):
        parts = [p for p in re.split(r"[^0-9a-zA-Z]+", str(name)) if p]
        if not parts:
            return ""
        return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])


# FRC field geometry (metres). Matches the Choreo field JSON and the values the
# choreo ``.traj`` files reference, so paths, zones and the field image line up.
FIELD_WIDTH = 16.541   # field length along X
FIELD_HEIGHT = 8.0692  # field width along Y

# Attributes that should be edited as numbers regardless of the DTD's CDATA type.
NUMERIC_ATTRS = {
    "time", "heading",
    "x1_rect", "y1_rect", "x2_rect", "y2_rect",
    "circlex", "circley", "radius",
}

RECT_KEYS = ["x1_rect", "y1_rect", "x2_rect", "y2_rect"]
CIRCLE_KEYS = ["circlex", "circley", "radius"]

HANDLE_SIZE = 0.28  # metres
ZONE_LABEL_SCALE = 0.02  # shrink pixel-sized text into field metres

# Distinct colours cycled per trajectory path so an auton's order reads at a glance.
PATH_PALETTE = [
    (80, 190, 255), (120, 230, 120), (255, 180, 70), (240, 120, 200),
    (255, 235, 90), (150, 150, 255), (90, 230, 220), (240, 130, 90),
]


def _make_zone_label(text, parent):
    """Create a centred, non-interactive name label as a child of a zone item.

    Being a child means it moves and is deleted together with the zone item, so
    dragging the zone drags its name too.
    """
    label = QGraphicsTextItem(text, parent)
    label.setDefaultTextColor(QColor(255, 255, 255))
    label.setScale(ZONE_LABEL_SCALE)
    label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)  # clicks fall through
    label.setZValue(16)
    return label


# --------------------------------------------------------------------------- #
# DTD parsing (the schema is the source of truth for supported values)
# --------------------------------------------------------------------------- #
def parse_dtd_attlists(dtd_text):
    """Parse ``<!ATTLIST ...>`` blocks into ``{element: [attr_def, ...]}``.

    Each ``attr_def`` is ``{"name", "kind" (enum|cdata), "options", "default"}``.
    """
    result = {}
    attr_re = re.compile(
        r"(\w+)\s+(\([^)]*\)|CDATA|NMTOKEN|NMTOKENS|ID|IDREF|IDREFS)\s*"
        r'(#REQUIRED|#IMPLIED|#FIXED\s+"[^"]*"|"[^"]*")?',
        re.DOTALL,
    )
    for block in re.finditer(r"<!ATTLIST\s+(\w+)(.*?)>", dtd_text, re.DOTALL):
        element = block.group(1)
        body = block.group(2)
        attrs = []
        for m in attr_re.finditer(body):
            name, type_token, default_token = m.group(1), m.group(2), m.group(3) or ""
            if type_token.startswith("("):
                options = [o.strip() for o in type_token[1:-1].split("|") if o.strip()]
                kind = "enum"
            else:
                options = []
                kind = "cdata"
            default = ""
            match = re.search(r'"([^"]*)"', default_token)
            if match:
                default = match.group(1)
            attrs.append({"name": name, "kind": kind, "options": options, "default": default})
        result[element] = attrs
    return result


# --------------------------------------------------------------------------- #
# Field coordinate helpers (metres -> scene, with Y flipped so up is up)
# --------------------------------------------------------------------------- #
def world_to_scene(x, y):
    return x, FIELD_HEIGHT - y


def scene_to_world(x, y):
    return x, FIELD_HEIGHT - y


class NoScrollComboBox(QComboBox):
    """A combo box that ignores mouse-wheel scrolling.

    Prevents accidentally changing a selection while scrolling the editor panel.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        event.ignore()


class NoScrollDoubleSpinBox(QDoubleSpinBox):
    """A spin box that ignores mouse-wheel scrolling."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        event.ignore()


class FieldView(QGraphicsView):
    """A graphics view that always fits the whole field into the widget."""

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(220)
        self.setBackgroundBrush(QColor(18, 26, 20))

    def _fit(self):
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    def showEvent(self, event):
        super().showEvent(event)
        self._fit()


class FieldWindow(QWidget):
    """A separate, movable top-level window that hosts the field view.

    Emits ``on_close`` when the user closes it so the builder can re-dock the
    field back into the tab.
    """

    def __init__(self, on_close, parent=None):
        super().__init__(parent)
        self._on_close = on_close
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowTitle("Auton Builder - Field")
        self.resize(1000, 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

    def closeEvent(self, event):
        if self._on_close is not None:
            self._on_close()
        super().closeEvent(event)


class ResizeHandle(QGraphicsRectItem):
    """A small square that resizes its owner zone item when dragged."""

    def __init__(self, owner):
        super().__init__(-HANDLE_SIZE / 2, -HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE, owner)
        self.owner = owner
        self.setBrush(QBrush(QColor(255, 255, 255)))
        self.setPen(QPen(QColor(20, 20, 20), 0))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(20)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            return self.owner.handle_moved(value)
        return super().itemChange(change, value)


class ZoneRectItem(QGraphicsRectItem):
    """A draggable / resizable rectangular zone.

    The local rect is ``(0, 0, w, h)`` and the item position is the scene
    top-left, so dragging moves the position and the corner handle resizes it.
    """

    def __init__(self, zone, builder):
        self.zone = zone
        self.builder = builder
        x1 = float(zone.get("x1_rect", 0.0) or 0.0)
        y1 = float(zone.get("y1_rect", 0.0) or 0.0)
        x2 = float(zone.get("x2_rect", x1 + 1.0) or 0.0)
        y2 = float(zone.get("y2_rect", y1 + 1.0) or 0.0)
        w = max(abs(x2 - x1), 0.1)
        h = max(abs(y2 - y1), 0.1)
        tl_x, tl_y = world_to_scene(min(x1, x2), max(y1, y2))
        super().__init__(0, 0, w, h)
        self.setPos(tl_x, tl_y)
        self.setPen(QPen(QColor(0, 255, 160), 0.05))
        self.setBrush(QBrush(QColor(0, 255, 160, 70)))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(10)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.handle = ResizeHandle(self)
        self.handle.setPos(w, h)
        self.label = _make_zone_label(zone.get("name", ""), self)
        self._center_label()

    def _center_label(self):
        rect = self.rect()
        br = self.label.boundingRect()
        self.label.setPos(
            rect.width() / 2 - br.width() * (ZONE_LABEL_SCALE / 2),
            rect.height() / 2 - br.height() * (ZONE_LABEL_SCALE / 2),
        )

    def _write_geometry(self):
        rect = self.rect()
        tl_x = self.pos().x()
        tl_y = self.pos().y()
        x_min, y_max = scene_to_world(tl_x, tl_y)
        x_max = x_min + rect.width()
        y_min = y_max - rect.height()
        self.zone["x1_rect"] = round(x_min, 3)
        self.zone["y1_rect"] = round(y_min, 3)
        self.zone["x2_rect"] = round(x_max, 3)
        self.zone["y2_rect"] = round(y_max, 3)
        self.builder.zone_geometry_changed()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            rect = self.rect()
            nx = min(max(value.x(), 0.0), FIELD_WIDTH - rect.width())
            ny = min(max(value.y(), 0.0), FIELD_HEIGHT - rect.height())
            return QPointF(nx, ny)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene():
            self._write_geometry()
        return super().itemChange(change, value)

    def handle_moved(self, value):
        w = min(max(value.x(), 0.2), FIELD_WIDTH - self.pos().x())
        h = min(max(value.y(), 0.2), FIELD_HEIGHT - self.pos().y())
        self.setRect(0, 0, w, h)
        self._center_label()
        self._write_geometry()
        return QPointF(w, h)


class ZoneCircleItem(QGraphicsEllipseItem):
    """A draggable / resizable circular zone (centred local rect)."""

    def __init__(self, zone, builder):
        self.zone = zone
        self.builder = builder
        cx = float(zone.get("circlex", 1.0) or 0.0)
        cy = float(zone.get("circley", 1.0) or 0.0)
        r = max(float(zone.get("radius", 1.0) or 0.0), 0.1)
        super().__init__(-r, -r, 2 * r, 2 * r)
        sx, sy = world_to_scene(cx, cy)
        self.setPos(sx, sy)
        self.setPen(QPen(QColor(255, 180, 70), 0.05))
        self.setBrush(QBrush(QColor(255, 180, 70, 70)))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(10)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.handle = ResizeHandle(self)
        self.handle.setPos(r, 0)
        self.label = _make_zone_label(zone.get("name", ""), self)
        self._center_label()

    def _center_label(self):
        br = self.label.boundingRect()
        # Local rect is centred on (0, 0), so centre the label there too.
        self.label.setPos(
            -br.width() * (ZONE_LABEL_SCALE / 2),
            -br.height() * (ZONE_LABEL_SCALE / 2),
        )

    def _radius(self):
        return self.rect().width() / 2.0

    def _write_geometry(self):
        cx, cy = scene_to_world(self.pos().x(), self.pos().y())
        self.zone["circlex"] = round(cx, 3)
        self.zone["circley"] = round(cy, 3)
        self.zone["radius"] = round(self._radius(), 3)
        self.builder.zone_geometry_changed()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            r = self._radius()
            nx = min(max(value.x(), r), FIELD_WIDTH - r)
            ny = min(max(value.y(), r), FIELD_HEIGHT - r)
            return QPointF(nx, ny)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene():
            self._write_geometry()
        return super().itemChange(change, value)

    def handle_moved(self, value):
        r = max(value.x(), 0.1)
        self.setRect(-r, -r, 2 * r, 2 * r)
        self._write_geometry()
        return QPointF(r, 0)


class AutonBuilderWidget(QWidget):
    """The Auton Builder tab widget."""

    def __init__(self, mechanism_model=None):
        super().__init__()
        self.mechanism_model = mechanism_model
        self.choreo_path = ""
        self.auton_source_path = ""
        self.autons = []
        self.zones = []
        self.snippets = []
        self.current_selection = None
        self._zone_spinboxes = {}
        self._to_select = None
        self.view_mode = "inline"  # "inline" (full editors) or "list" (navigable)
        self._field_asset = None   # cache: (QPixmap, meta) once loaded, or False
        self.field_window = None   # separate pop-out window, or None when docked

        # Trajectory playback state.
        self._timeline = None      # {"t","x","y","h","dur","bumper"} or None
        self._robot_item = None
        self._pb_time = 0.0
        self._pb_playing = False
        self._pb_scrubbing = False
        self._pb_timer = QTimer(self)
        self._pb_timer.setInterval(30)  # ~33 fps
        self._pb_timer.timeout.connect(self._on_pb_tick)

        self.dtd_paths = {}
        self.schema_auton = {}
        self.schema_zone = {}
        self._load_dtd_schema()

        self.field_scene = QGraphicsScene(-0.5, -0.5, FIELD_WIDTH + 1.0, FIELD_HEIGHT + 1.0)
        self.field_view = FieldView(self.field_scene)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Auton Explorer")
        self.tree.itemClicked.connect(self.on_tree_click)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)

        self.editor_scroll = QScrollArea()
        self.editor_scroll.setWidgetResizable(True)
        self.editor_scroll.setStyleSheet("QScrollArea { border: none; }")
        self.editor_panel = QWidget()
        self.editor_layout = QVBoxLayout(self.editor_panel)
        self.editor_scroll.setWidget(self.editor_panel)

        self._build_layout()
        self._restore_settings()
        self._load_from_source_folder()
        self._update_status_label()
        self.populate_tree()
        self.refresh_field()

    # ------------------------------------------------------------------ #
    # DTD schema
    # ------------------------------------------------------------------ #
    def _repo_root(self):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def _load_dtd_schema(self):
        """Parse each DTD separately.

        ``auton.dtd`` and ``zone.dtd`` both declare an element named ``zone`` but
        with different meaning: in ``auton.dtd`` it is a *reference* (``filename``)
        used inside a primitive, while in ``zone.dtd`` it is the zone *definition*
        (geometry + metadata). Keeping the schemas apart avoids collisions.
        """
        example_dir = os.path.join(self._repo_root(), "AutonExample")
        self.dtd_paths = {
            "auton": os.path.join(example_dir, "auton.dtd"),
            "zone": os.path.join(example_dir, "Zone", "zone.dtd"),
        }
        self.schema_auton = {}
        self.schema_zone = {}
        for key, path in self.dtd_paths.items():
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    parsed = parse_dtd_attlists(f.read())
            except Exception:
                parsed = {}
            if key == "auton":
                self.schema_auton = parsed
            else:
                self.schema_zone = parsed

    def _primitive_attrs(self):
        return self.schema_auton.get("primitive", [])

    def _zone_ref_attrs(self):
        return self.schema_auton.get("zone", [])

    def _snippet_ref_attrs(self):
        return self.schema_auton.get("snippet", [])

    def _zone_def_attrs(self):
        return self.schema_zone.get("zone", [])

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def _build_layout(self):
        root = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: tree + actions
        tree_wrap = QWidget()
        tree_layout = QVBoxLayout(tree_wrap)
        add_actions = QHBoxLayout()
        self.btn_new_auton = QPushButton("+ Add Auton")
        self.btn_new_auton.clicked.connect(self.add_new_auton)
        self.btn_new_zone = QPushButton("+ Add Zone")
        self.btn_new_zone.clicked.connect(self.add_new_zone)
        self.btn_new_snippet = QPushButton("+ Add Snippet")
        self.btn_new_snippet.clicked.connect(self.add_new_snippet)
        add_actions.addWidget(self.btn_new_auton)
        add_actions.addWidget(self.btn_new_zone)
        add_actions.addWidget(self.btn_new_snippet)
        tree_layout.addLayout(add_actions)
        tree_layout.addWidget(self.tree)

        bottom_actions = QHBoxLayout()
        self.btn_generate = QPushButton("Generate Auton XML")
        self.btn_generate.setStyleSheet(
            "background-color: #005A9C; color: white; font-weight: bold; "
            "padding: 10px; font-size: 13px; border-radius: 4px;"
        )
        self.btn_generate.clicked.connect(self.generate_auton)
        bottom_actions.addWidget(self.btn_generate)
        tree_layout.addLayout(bottom_actions)
        splitter.addWidget(tree_wrap)

        # Right (creator panel): field on top, editor below
        creator = QSplitter(Qt.Orientation.Vertical)
        creator.setChildrenCollapsible(False)
        self.creator_splitter = creator
        self.field_wrap = QWidget()
        field_layout = QVBoxLayout(self.field_wrap)
        header = QHBoxLayout()
        self.field_title = QLabel("Field Visualization")
        self.field_title.setStyleSheet("font-weight: bold; color: #E0E0E0; padding: 2px;")
        header.addWidget(self.field_title)
        header.addStretch()
        self.btn_popout = QPushButton("Pop Out \u2197")
        self.btn_popout.setToolTip("Show the field in a separate, movable window")
        self.btn_popout.clicked.connect(self.toggle_field_window)
        header.addWidget(self.btn_popout)
        field_layout.addLayout(header)

        # The field lives in a swappable host so it can be moved to a pop-out
        # window; when popped out this host is hidden and the editor expands.
        self.field_area = QWidget()
        self.field_area_layout = QVBoxLayout(self.field_area)
        self.field_area_layout.setContentsMargins(0, 0, 0, 0)

        # field view + playback bar travel together (into the pop-out window too).
        self.field_stack = QWidget()
        stack_layout = QVBoxLayout(self.field_stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.setSpacing(2)
        stack_layout.addWidget(self.field_view, 1)
        stack_layout.addWidget(self._build_playback_bar())
        self.field_area_layout.addWidget(self.field_stack)
        field_layout.addWidget(self.field_area, 1)

        creator.addWidget(self.field_wrap)
        creator.addWidget(self.editor_scroll)
        creator.setSizes([420, 380])
        splitter.addWidget(creator)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([320, 880])
        root.addWidget(splitter, 1)

        # Bottom status bar: a single thin line showing the choreo path folder.
        self.path_label = QLabel()
        self.path_label.setStyleSheet(
            "color: #C0C0C0; background-color: #2D2D30; border-top: 1px solid #444; "
            "padding: 1px 8px;"
        )
        self.path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.path_label.setFixedHeight(self.path_label.fontMetrics().height() + 4)
        root.addWidget(self.path_label, 0)
        self._update_status_label()

    # ------------------------------------------------------------------ #
    # Pop-out field window
    # ------------------------------------------------------------------ #
    def toggle_field_window(self):
        if self.field_window is None:
            self.pop_out_field()
        else:
            self.dock_field()

    def pop_out_field(self):
        """Move the field view into a separate window and expand the editor."""
        if self.field_window is not None:
            self.field_window.raise_()
            self.field_window.activateWindow()
            return
        # Remember the current split so we can restore it when docking back.
        self._creator_sizes_docked = self.creator_splitter.sizes()

        self.field_area_layout.removeWidget(self.field_stack)
        self.field_window = FieldWindow(self._on_field_window_closed, parent=self.window())
        self.field_window.layout().addWidget(self.field_stack)

        # Collapse the field area so the editor takes over the vertical space.
        self.field_area.hide()
        self.field_title.setText("Field Visualization (popped out)")
        total = sum(self._creator_sizes_docked) or 800
        header_h = self.field_wrap.sizeHint().height()
        self.creator_splitter.setSizes([header_h, max(total - header_h, 1)])

        self.btn_popout.setText("Dock Field \u2199")
        self.field_window.show()
        self.field_window.raise_()
        self.field_window.activateWindow()
        self.field_stack.show()
        self.refresh_field()

    def dock_field(self, _from_close=False):
        """Return the field view from the pop-out window back into the tab."""
        if self.field_window is None:
            return
        window = self.field_window
        self.field_window = None

        window.layout().removeWidget(self.field_stack)
        self.field_area_layout.addWidget(self.field_stack)
        self.field_area.show()
        self.field_stack.show()
        self.field_title.setText("Field Visualization")
        self.creator_splitter.setSizes(
            getattr(self, "_creator_sizes_docked", None) or [420, 380]
        )

        self.btn_popout.setText("Pop Out \u2197")
        if not _from_close:
            window.close()
        window.deleteLater()
        self.refresh_field()

    def _on_field_window_closed(self):
        # The user closed the pop-out window directly: re-dock the field.
        if self.field_window is not None:
            self.dock_field(_from_close=True)

    # ------------------------------------------------------------------ #
    # Trajectory playback
    # ------------------------------------------------------------------ #
    def _build_playback_bar(self):
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 0, 4, 0)
        self.btn_play = QPushButton("\u25B6 Play")
        self.btn_play.setFixedWidth(80)
        self.btn_play.clicked.connect(self._toggle_playback)
        layout.addWidget(self.btn_play)

        self.pb_slider = QSlider(Qt.Orientation.Horizontal)
        self.pb_slider.setRange(0, 1000)
        self.pb_slider.setValue(0)
        self.pb_slider.sliderPressed.connect(self._on_scrub_start)
        self.pb_slider.sliderReleased.connect(self._on_scrub_end)
        self.pb_slider.valueChanged.connect(self._on_scrub)
        layout.addWidget(self.pb_slider, 1)

        self.pb_time_label = QLabel("0.00 / 0.00 s")
        self.pb_time_label.setStyleSheet("color: #C0C0C0;")
        self.pb_time_label.setFixedWidth(110)
        layout.addWidget(self.pb_time_label)

        self.playback_bar = bar
        return bar

    def _owner_primitives(self, owner):
        """Ordered primitives of an auton/snippet body (or a single primitive)."""
        entries = owner.get("sequence")
        if entries is not None:
            return [e["data"] for e in entries if e.get("kind") == "primitive"]
        if owner.get("id"):
            return [owner]
        return []

    def _rebuild_playback(self, owner):
        """Build the pose timeline for the whole auton (chained primitives)."""
        self._timeline = None
        if owner is None:
            self._update_playback_controls()
            return
        times, xs, ys, hs = [], [], [], []
        bumper = None
        cursor = 0.0
        last = None
        for primitive in self._owner_primitives(owner):
            traj = None
            choreoname = primitive.get("choreoname")
            if choreoname:
                traj = self._load_trajectory_full(choreoname)
            if traj and len(traj["samples"]) >= 2:
                if bumper is None:
                    bumper = traj["bumper"]
                base = traj["samples"][0][0]
                for (t, x, y, h) in traj["samples"]:
                    times.append(cursor + (t - base))
                    xs.append(x); ys.append(y); hs.append(h)
                    last = (x, y, h)
                cursor = times[-1]
            else:
                # Non-drive (or unloadable) primitive: hold the last pose for `time`.
                try:
                    wait = float(primitive.get("time", 0) or 0)
                except (TypeError, ValueError):
                    wait = 0.0
                if last is not None and wait > 0:
                    times.append(cursor); xs.append(last[0]); ys.append(last[1]); hs.append(last[2])
                    cursor += wait
                    times.append(cursor); xs.append(last[0]); ys.append(last[1]); hs.append(last[2])

        if len(times) >= 2 and cursor > 0:
            self._timeline = {
                "t": times, "x": xs, "y": ys, "h": hs,
                "dur": cursor, "bumper": bumper or (0.4, 0.4, 0.4),
            }
            if self._pb_time > cursor:
                self._pb_time = 0.0
        else:
            self._pb_time = 0.0
            self._stop_playback()
        self._update_playback_controls()

    def _update_playback_controls(self):
        enabled = self._timeline is not None
        for w in (self.btn_play, self.pb_slider):
            w.setEnabled(enabled)
        if not enabled:
            self.btn_play.setText("\u25B6 Play")
            self.pb_slider.blockSignals(True)
            self.pb_slider.setValue(0)
            self.pb_slider.blockSignals(False)
            self.pb_time_label.setText("0.00 / 0.00 s")
        else:
            self._sync_playback_ui()

    def _playback_pose(self, t):
        tl = self._timeline
        times = tl["t"]
        if t <= times[0]:
            return tl["x"][0], tl["y"][0], tl["h"][0]
        if t >= times[-1]:
            return tl["x"][-1], tl["y"][-1], tl["h"][-1]
        i = bisect.bisect_right(times, t)
        i0, i1 = i - 1, i
        t0, t1 = times[i0], times[i1]
        frac = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
        x = tl["x"][i0] + (tl["x"][i1] - tl["x"][i0]) * frac
        y = tl["y"][i0] + (tl["y"][i1] - tl["y"][i0]) * frac
        h = tl["h"][i0] + (tl["h"][i1] - tl["h"][i0]) * frac
        return x, y, h

    def _create_robot_item(self):
        """Create the robot (bumper) marker for the current timeline."""
        if self._timeline is None:
            self._robot_item = None
            return
        front, side, back = self._timeline["bumper"]
        body = QGraphicsRectItem(-back, -side, front + back, 2 * side)
        body.setPen(QPen(QColor(255, 255, 255), 0.04))
        body.setBrush(QBrush(QColor(90, 150, 240, 130)))
        body.setZValue(8)
        # Front-direction arrow so orientation is obvious.
        nose = QGraphicsPolygonItem(
            QPolygonF([
                QPointF(front, 0.0),
                QPointF(front - 0.22, -min(side, 0.22)),
                QPointF(front - 0.22, min(side, 0.22)),
            ]),
            body,
        )
        nose.setPen(QPen(QColor(255, 255, 255), 0.0))
        nose.setBrush(QBrush(QColor(255, 255, 255)))
        self.field_scene.addItem(body)
        self._robot_item = body
        self._apply_robot_pose(self._pb_time)

    def _apply_robot_pose(self, t):
        if self._robot_item is None or self._timeline is None:
            return
        x, y, h = self._playback_pose(t)
        sx, sy = world_to_scene(x, y)
        self._robot_item.setPos(sx, sy)
        # Scene Y is flipped, so a CCW world heading is a negative scene rotation.
        self._robot_item.setRotation(-math.degrees(h))

    def _toggle_playback(self):
        if self._timeline is None:
            return
        if self._pb_playing:
            self._stop_playback()
        else:
            if self._pb_time >= self._timeline["dur"]:
                self._pb_time = 0.0  # restart from the beginning
            self._pb_playing = True
            self.btn_play.setText("\u275A\u275A Pause")
            self._pb_timer.start()

    def _stop_playback(self):
        self._pb_playing = False
        self._pb_timer.stop()
        if hasattr(self, "btn_play"):
            self.btn_play.setText("\u25B6 Play")

    def _on_pb_tick(self):
        if self._timeline is None:
            self._stop_playback()
            return
        self._pb_time += self._pb_timer.interval() / 1000.0
        if self._pb_time >= self._timeline["dur"]:
            self._pb_time = self._timeline["dur"]
            self._apply_robot_pose(self._pb_time)
            self._sync_playback_ui()
            self._stop_playback()
            return
        self._apply_robot_pose(self._pb_time)
        self._sync_playback_ui()

    def _sync_playback_ui(self):
        if self._timeline is None:
            return
        dur = self._timeline["dur"]
        self.pb_slider.blockSignals(True)
        self.pb_slider.setValue(int(1000 * self._pb_time / dur) if dur else 0)
        self.pb_slider.blockSignals(False)
        self.pb_time_label.setText(f"{self._pb_time:.2f} / {dur:.2f} s")

    def _on_scrub_start(self):
        self._pb_scrubbing = True
        self._stop_playback()

    def _on_scrub_end(self):
        self._pb_scrubbing = False

    def _on_scrub(self, value):
        if self._timeline is None:
            return
        self._pb_time = self._timeline["dur"] * value / 1000.0
        self._apply_robot_pose(self._pb_time)
        self.pb_time_label.setText(f"{self._pb_time:.2f} / {self._timeline['dur']:.2f} s")

    def _update_status_label(self):
        auton = self.auton_source_path or "(none - use Options -> Select Auton Files Folder)"
        choreo = self.choreo_path or "(none - use Options -> Select Choreo Path Folder)"
        self.path_label.setText(f"Auton files:  {auton}      |      Choreo path:  {choreo}")

    # ------------------------------------------------------------------ #
    # Settings / persistence
    # ------------------------------------------------------------------ #
    def _restore_settings(self):
        if self.mechanism_model is not None:
            saved_path = self.mechanism_model.app_settings.get("auton_choreo_path", "")
            if saved_path and os.path.isdir(saved_path):
                self.choreo_path = saved_path
            saved_source = self.mechanism_model.app_settings.get("auton_source_path", "")
            if saved_source and os.path.isdir(saved_source):
                self.auton_source_path = saved_source
            mode = self.mechanism_model.app_settings.get("auton_view_mode", "inline")
            if mode in ("inline", "list"):
                self.view_mode = mode

    def set_view_mode(self, mode):
        """Switch between the fully-inline editor and the navigable list view."""
        if mode not in ("inline", "list") or mode == self.view_mode:
            return
        self.view_mode = mode
        if self.mechanism_model is not None:
            self.mechanism_model.set_app_setting("auton_view_mode", mode)
        self.render_editor()

    def select_choreo_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Choreo Path Folder")
        if not folder:
            return
        self.choreo_path = folder
        if self.mechanism_model is not None:
            self.mechanism_model.set_app_setting("auton_choreo_path", folder)
        self._update_status_label()
        if self.current_selection:
            self.render_editor()
        self.refresh_field()

    def select_auton_folder(self):
        """Choose the folder to load auton / zone / snippet XMLs from."""
        folder = QFileDialog.getExistingDirectory(self, "Select Auton Files Folder")
        if not folder:
            return
        self.auton_source_path = folder
        if self.mechanism_model is not None:
            self.mechanism_model.set_app_setting("auton_source_path", folder)
        self.load_autons_from_folder(folder)
        self._update_status_label()
        self.populate_tree()
        self.refresh_field()

    def _load_from_source_folder(self):
        """Load autons/zones/snippets from the selected folder (source of truth)."""
        folder = self.auton_source_path or self._default_auton_dir()
        self.auton_source_path = folder
        self.load_autons_from_folder(folder)

    # Kept for the suite shell; auton data is folder-based, so a project
    # load/new simply re-reads the current auton files folder.
    def _load_saved_data(self):
        self._load_from_source_folder()

    def _save_data(self):
        """Auton data lives in XML files in the auton folder, not in the project JSON.

        Drop any legacy ``auton_builder`` copy so the JSON and the XMLs cannot
        drift apart. In-memory edits are written to XML via ``Generate Auton XML``.
        """
        if self.mechanism_model is not None:
            self.mechanism_model.project_data.pop("auton_builder", None)

    def save_to_project(self):
        self._save_data()
        if self.mechanism_model is None:
            return False
        if self.mechanism_model.current_project_path:
            self.mechanism_model.save_project(self.mechanism_model.current_project_path)
            return True
        return False

    def save_to_project_as(self):
        self._save_data()
        if self.mechanism_model is None:
            return False
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "FRC_Project.json", "JSON Files (*.json)"
        )
        if not path:
            return False
        self.mechanism_model.save_project(path)
        self.mechanism_model.update_app_settings(path)
        return True

    def generate_auton(self):
        ok, info = self.save_autons_to_folder()
        if ok:
            QMessageBox.information(
                self,
                "Auton XML Generated",
                f"Wrote auton, zone and snippet XML files to:\n{info}",
            )
        else:
            QMessageBox.warning(self, "Generate Auton XML", info)

    # ------------------------------------------------------------------ #
    # XML loading (the folder is the source of truth)
    # ------------------------------------------------------------------ #
    def _default_auton_dir(self):
        return os.path.join(self._repo_root(), "AutonExample")

    def load_autons_from_folder(self, folder):
        """Load autons, zones and snippets from ``folder``.

        The folder layout matches the example project: auton XMLs at the top
        level, zone XMLs under ``Zone/`` and snippet XMLs under ``Snippets/``.
        """
        if not os.path.isdir(folder):
            return
        self.autons = []
        self.zones = []
        self.snippets = []
        self.current_selection = None
        self._load_zone_examples(folder)
        self._load_snippet_examples(folder)
        self._load_auton_examples(folder)
        self._save_data()

    def _load_zone_examples(self, example_dir):
        zone_dir = os.path.join(example_dir, "Zone")
        if not os.path.isdir(zone_dir):
            return
        for name in sorted(os.listdir(zone_dir)):
            if not name.lower().endswith(".xml"):
                continue
            path = os.path.join(zone_dir, name)
            try:
                root = ET.parse(path).getroot()
            except Exception:
                continue
            zone = {"name": os.path.splitext(name)[0], "type": "zone"}
            zone_el = root.find("zone")
            if zone_el is not None:
                for key, value in zone_el.attrib.items():
                    zone[key] = value
            zone["zone_shape"] = "circle" if "circlex" in zone else "rectangle"
            self.zones.append(zone)

    def _load_snippet_examples(self, example_dir):
        snippet_dir = os.path.join(example_dir, "Snippets")
        if not os.path.isdir(snippet_dir):
            return
        for name in sorted(os.listdir(snippet_dir)):
            if not name.lower().endswith(".xml"):
                continue
            path = os.path.join(snippet_dir, name)
            try:
                root = ET.parse(path).getroot()
            except Exception:
                continue
            snippet = {
                "name": os.path.splitext(name)[0],
                "type": "snippet",
                "sequence": [],
            }
            self._load_auton_children(root, snippet)
            self.snippets.append(snippet)

    def _load_auton_examples(self, example_dir):
        for name in sorted(os.listdir(example_dir)):
            full = os.path.join(example_dir, name)
            if os.path.isdir(full) or not name.lower().endswith(".xml"):
                continue
            try:
                root = ET.parse(full).getroot()
            except Exception:
                continue
            auton = {"name": os.path.splitext(name)[0], "type": "auton", "sequence": []}
            self._load_auton_children(root, auton)
            self.autons.append(auton)

    def _load_auton_children(self, root, owner):
        """Load the ordered auton/snippet body (primitives + snippet refs)."""
        sequence = owner.setdefault("sequence", [])
        for child in list(root):
            if child.tag == "primitive":
                primitive = dict(child.attrib)
                primitive["zones"] = [dict(z.attrib) for z in child.findall("zone")]
                sequence.append({"kind": "primitive", "data": primitive})
            elif child.tag == "snippet":
                sequence.append({"kind": "snippet", "data": dict(child.attrib)})
            elif child.tag == "zone":
                # A standalone zone file body: keep its attributes on the owner.
                owner.update(dict(child.attrib))

    # ------------------------------------------------------------------ #
    # XML generation (write autons / zones / snippets back to the folder)
    # ------------------------------------------------------------------ #
    def save_autons_to_folder(self):
        """Write every auton, zone and snippet to XML in the auton folder.

        Returns ``(ok, info)`` where ``info`` is the folder on success or an
        error message on failure. The layout mirrors the loader: autons at the
        top level, zones under ``Zone/`` and snippets under ``Snippets/``.
        """
        folder = self.auton_source_path
        if not folder or not os.path.isdir(folder):
            return False, (
                "No auton files folder is selected. Use "
                "Options -> Select Auton Files Folder first."
            )
        try:
            zone_dir = os.path.join(folder, "Zone")
            snippet_dir = os.path.join(folder, "Snippets")
            os.makedirs(zone_dir, exist_ok=True)
            os.makedirs(snippet_dir, exist_ok=True)

            for auton in self.autons:
                path = os.path.join(folder, self._xml_filename(auton.get("name"), "auton"))
                self._write_xml(path, self._container_to_xml(auton), "auton.dtd")
            for snippet in self.snippets:
                path = os.path.join(snippet_dir, self._snippet_filename(snippet))
                self._write_xml(path, self._container_to_xml(snippet), "auton.dtd")
            for zone in self.zones:
                path = os.path.join(zone_dir, self._zone_filename(zone))
                self._write_xml(path, self._zone_to_xml(zone), "zone.dtd")
        except Exception as exc:  # pragma: no cover - filesystem errors
            return False, f"Failed to write XML files:\n{exc}"
        return True, folder

    @staticmethod
    def _xml_filename(name, fallback):
        base = (name or fallback).strip() or fallback
        return base if base.lower().endswith(".xml") else f"{base}.xml"

    def _snippet_filename(self, snippet):
        """A snippet's on-disk filename is derived from its name (name.xml)."""
        return self._xml_filename(snippet.get("name"), "snippet")

    def _zone_filename(self, zone):
        """A zone's on-disk filename is derived from its name (name.xml).

        This is also the value used by ``<zone filename=...>`` references.
        """
        return self._xml_filename(zone.get("name"), "zone")

    def _container_to_xml(self, container):
        """Build an ``<auton>`` element for an auton or snippet body."""
        root = ET.Element("auton")
        for entry in container.get("sequence", []):
            data = entry.get("data", {})
            if entry.get("kind") == "primitive":
                root.append(self._primitive_to_xml(data))
            else:
                ET.SubElement(root, "snippet", {"file": str(data.get("file", ""))})
        return root

    def _primitive_to_xml(self, primitive):
        el = ET.Element("primitive")
        # DTD-ordered attributes first, then any mechanism-data (*State) attrs.
        for key in ("id", "time", "choreoname"):
            value = primitive.get(key)
            if value not in (None, ""):
                el.set(key, str(value))
        for key, value in primitive.items():
            if key in ("zones", "id", "time", "choreoname") or value in (None, ""):
                continue
            el.set(key, str(value))
        for zref in primitive.get("zones", []):
            filename = zref.get("filename", "")
            if filename:
                ET.SubElement(el, "zone", {"filename": str(filename)})
        return el

    def _zone_to_xml(self, zone):
        root = ET.Element("auton")
        zel = ET.SubElement(root, "zone")
        is_circle = str(zone.get("zone_shape", "")).lower() == "circle" or (
            "circlex" in zone and "x1_rect" not in zone
        )
        geo_keys = CIRCLE_KEYS if is_circle else RECT_KEYS
        skip_keys = set(RECT_KEYS if is_circle else CIRCLE_KEYS)
        internal = {"name", "type", "filename", "zone_shape"}
        ordered = geo_keys + ["pathUpdateOption", "allianceColor"]
        for key in ordered:
            value = zone.get(key)
            if value not in (None, ""):
                zel.set(key, str(value))
        for key, value in zone.items():
            if key in internal or key in ordered or key in skip_keys or value in (None, ""):
                continue
            zel.set(key, str(value))
        return root

    def _write_xml(self, path, root, dtd_name):
        try:
            ET.indent(root, space="    ")
        except Exception:
            pass
        body = ET.tostring(root, encoding="unicode")
        text = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<!DOCTYPE auton SYSTEM "{dtd_name}">\n{body}\n'
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    # ------------------------------------------------------------------ #
    # Tree (path-descriptor based, mirroring the Mechanism Generator)
    # ------------------------------------------------------------------ #
    def _collection(self, coll):
        return self.autons if coll == "autons" else self.snippets

    def _resolve(self, desc):
        """Resolve a node descriptor to the underlying dict/entry, or None."""
        if not desc:
            return None
        kind = desc.get("type")
        try:
            if kind == "auton":
                return self.autons[desc["index"]]
            if kind == "snippet":
                return self.snippets[desc["index"]]
            if kind == "zone":
                return self.zones[desc["index"]]
            if kind == "step":
                return self._collection(desc["coll"])[desc["owner"]]["sequence"][desc["index"]]
            if kind == "zoneref":
                step = self._collection(desc["coll"])[desc["owner"]]["sequence"][desc["step"]]
                return step["data"]["zones"][desc["index"]]
        except (IndexError, KeyError, TypeError):
            return None
        return None

    def refresh_tree(self, select_data=None):
        self.populate_tree(select_data)

    def populate_tree(self, select_data=None):
        self.tree.clear()
        self._to_select = None

        autons_root = self._mk_node(self.tree, "Autons", {"type": "folder", "kind": "autons"}, select_data)
        for i, auton in enumerate(self.autons):
            node = self._mk_node(autons_root, auton.get("name", "Auton"), {"type": "auton", "index": i}, select_data)
            self._add_steps(node, "autons", i, auton, select_data)

        zones_root = self._mk_node(self.tree, "Zones", {"type": "folder", "kind": "zones"}, select_data)
        for i, zone in enumerate(self.zones):
            self._mk_node(zones_root, zone.get("name", "Zone"), {"type": "zone", "index": i}, select_data)

        snippets_root = self._mk_node(self.tree, "Snippets", {"type": "folder", "kind": "snippets"}, select_data)
        for i, snippet in enumerate(self.snippets):
            node = self._mk_node(snippets_root, snippet.get("name", "Snippet"), {"type": "snippet", "index": i}, select_data)
            self._add_steps(node, "snippets", i, snippet, select_data)

        self.tree.expandAll()

        if self._to_select is not None:
            self.tree.setCurrentItem(self._to_select)
            self.tree.scrollToItem(self._to_select)
            self.on_tree_click(self._to_select, 0)
        elif select_data is not None:
            # The requested node no longer exists: clear the editor.
            self.current_selection = None
            self._clear_editor()
            self.refresh_field()

    def _mk_node(self, parent, label, desc, select_data):
        node = QTreeWidgetItem(parent, [label])
        node.setData(0, Qt.ItemDataRole.UserRole, desc)
        if select_data is not None and desc == select_data:
            self._to_select = node
        return node

    def _add_steps(self, parent, coll, owner_index, container, select_data):
        for j, entry in enumerate(container.get("sequence", [])):
            data = entry.get("data", {})
            if entry.get("kind") == "primitive":
                label = f"{j + 1}. {data.get('id', 'DO_NOTHING')}"
                if data.get("choreoname"):
                    label += f"  [{data['choreoname']}]"
            else:
                label = f"{j + 1}. snippet: {data.get('file', '')}"
            step_desc = {"type": "step", "coll": coll, "owner": owner_index, "index": j}
            step_node = self._mk_node(parent, label, step_desc, select_data)
            if entry.get("kind") == "primitive":
                for k, zref in enumerate(data.get("zones", [])):
                    zref_desc = {
                        "type": "zoneref", "coll": coll, "owner": owner_index,
                        "step": j, "index": k,
                    }
                    self._mk_node(step_node, f"zone: {zref.get('filename', '')}", zref_desc, select_data)

    def on_tree_click(self, item, column=0):
        desc = item.data(0, Qt.ItemDataRole.UserRole)
        if not desc:
            return
        self.current_selection = desc
        self.render_editor()
        self.refresh_field()

    # ------------------------------------------------------------------ #
    # Context menu / deletion
    # ------------------------------------------------------------------ #
    def open_context_menu(self, position):
        item = self.tree.itemAt(position)
        if item is None:
            return
        desc = item.data(0, Qt.ItemDataRole.UserRole)
        if not desc or desc.get("type") == "folder":
            return
        menu = QMenu()
        delete_action = menu.addAction("Delete")
        if menu.exec(self.tree.viewport().mapToGlobal(position)) == delete_action:
            self.handle_deletion(desc)

    def handle_deletion(self, desc):
        kind = desc.get("type")
        try:
            if kind == "auton":
                del self.autons[desc["index"]]
            elif kind == "zone":
                del self.zones[desc["index"]]
            elif kind == "snippet":
                del self.snippets[desc["index"]]
            elif kind == "step":
                del self._collection(desc["coll"])[desc["owner"]]["sequence"][desc["index"]]
            elif kind == "zoneref":
                del self._collection(desc["coll"])[desc["owner"]]["sequence"][desc["step"]]["data"]["zones"][desc["index"]]
            else:
                return
        except (IndexError, KeyError, TypeError):
            return
        self._save_data()
        self.current_selection = None
        self.populate_tree(select_data=self._parent_descriptor(desc))

    def _parent_descriptor(self, desc):
        kind = desc.get("type")
        if kind == "auton":
            return {"type": "folder", "kind": "autons"}
        if kind == "zone":
            return {"type": "folder", "kind": "zones"}
        if kind == "snippet":
            return {"type": "folder", "kind": "snippets"}
        if kind == "step":
            container_type = "auton" if desc["coll"] == "autons" else "snippet"
            return {"type": container_type, "index": desc["owner"]}
        if kind == "zoneref":
            return {"type": "step", "coll": desc["coll"], "owner": desc["owner"], "index": desc["step"]}
        return None

    # ------------------------------------------------------------------ #
    # Editor helpers
    # ------------------------------------------------------------------ #
    def _clear_editor(self):
        self._clear_layout(self.editor_layout)

    def _clear_layout(self, layout):
        """Recursively remove every widget and nested layout from ``layout``.

        Widgets added via ``addLayout`` are parented to the editor panel, not to
        the sub-layout, so clearing only top-level items would leave stale rows
        (headers, Up/Down/Delete rows) on screen when switching selections.
        """
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child = item.layout()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif child is not None:
                self._clear_layout(child)
                child.deleteLater()

    def _editor_title(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 16px; font-weight: bold; border-bottom: 2px solid #555; "
            "padding-bottom: 4px; color: #E0E0E0;"
        )
        self.editor_layout.addWidget(lbl)

    def _section_header(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #E0E0E0; font-weight: bold; font-size: 14px; margin-top: 8px;")
        self.editor_layout.addWidget(lbl)

    def _item_header(self, text, desc=None, on_delete=None,
                     up=None, down=None):
        """Accent heading naming one inline child, with optional row actions."""
        row = QHBoxLayout()
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #4FC3F7; font-weight: bold; font-size: 14px; "
            "border-bottom: 1px solid #444; padding: 6px 0 2px 0; margin-top: 12px;"
        )
        if desc is not None:
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(lbl, 1)
        if up is not None:
            up_btn = QPushButton("Up")
            up_btn.setFixedWidth(40)
            up_btn.clicked.connect(up)
            row.addWidget(up_btn)
        if down is not None:
            down_btn = QPushButton("Down")
            down_btn.setFixedWidth(50)
            down_btn.clicked.connect(down)
            row.addWidget(down_btn)
        if on_delete is not None:
            del_btn = QPushButton("Delete")
            del_btn.clicked.connect(on_delete)
            row.addWidget(del_btn)
        self.editor_layout.addLayout(row)

    def render_editor(self):
        self._clear_editor()
        self._zone_spinboxes = {}
        desc = self.current_selection
        if not desc:
            return
        kind = desc["type"]
        if kind == "folder":
            self._render_folder_editor(desc["kind"])
            self.editor_layout.addStretch()
            return
        data = self._resolve(desc)
        if data is None:
            return
        if kind in ("auton", "snippet"):
            self._render_container_editor(desc, data)
        elif kind == "zone":
            self._render_zone_editor(desc, data)
        elif kind == "step":
            if data.get("kind") == "primitive":
                self._render_primitive_editor(desc, data["data"])
            else:
                self._render_snippet_ref_editor(desc, data["data"])
        elif kind == "zoneref":
            self._render_zoneref_editor(desc, data)
        self.editor_layout.addStretch()

    # ------------------------------------------------------------------ #
    # Add actions
    # ------------------------------------------------------------------ #
    def add_new_auton(self):
        name = f"NewAuton_{len(self.autons) + 1}"
        self.autons.append({"name": name, "type": "auton", "sequence": []})
        self._save_data()
        self.populate_tree(select_data={"type": "auton", "index": len(self.autons) - 1})

    def add_new_zone(self):
        name = f"NewZone_{len(self.zones) + 1}"
        self.zones.append({
            "name": name, "type": "zone",
            "zone_shape": "rectangle",
            "x1_rect": 1.0, "y1_rect": 1.0, "x2_rect": 3.0, "y2_rect": 3.0,
            "pathUpdateOption": "NOTHING", "allianceColor": "BOTH",
        })
        self._save_data()
        self.populate_tree(select_data={"type": "zone", "index": len(self.zones) - 1})

    def add_new_snippet(self):
        name = f"NewSnippet_{len(self.snippets) + 1}"
        self.snippets.append({"name": name, "type": "snippet", "sequence": []})
        self._save_data()
        self.populate_tree(select_data={"type": "snippet", "index": len(self.snippets) - 1})

    # ------------------------------------------------------------------ #
    # Editors
    # ------------------------------------------------------------------ #
    def _render_folder_editor(self, kind):
        titles = {"autons": "Autons", "zones": "Zones", "snippets": "Snippets"}
        singular = {"autons": "Auton", "zones": "Zone", "snippets": "Snippet"}
        adders = {"autons": self.add_new_auton, "zones": self.add_new_zone, "snippets": self.add_new_snippet}
        items = {"autons": self.autons, "zones": self.zones, "snippets": self.snippets}[kind]
        self._editor_title(titles[kind])

        add_box = QGroupBox("Add New")
        add_layout = QVBoxLayout(add_box)
        add_btn = QPushButton(f"+ Add {singular[kind]}")
        add_btn.clicked.connect(adders[kind])
        add_layout.addWidget(add_btn)
        self.editor_layout.addWidget(add_box)

        if not items:
            self.editor_layout.addWidget(QLabel("(none yet)"))
            return

        if self.view_mode == "list":
            list_box = QGroupBox(titles[kind])
            list_layout = QVBoxLayout(list_box)
            for i, obj in enumerate(items):
                desc = {"type": singular[kind].lower(), "index": i}
                row = QHBoxLayout()
                open_btn = QPushButton(obj.get("name", ""))
                open_btn.setStyleSheet("text-align: left;")
                open_btn.clicked.connect(lambda _=False, d=desc: self.populate_tree(select_data=d))
                row.addWidget(open_btn, 1)
                del_btn = QPushButton("Delete")
                del_btn.clicked.connect(lambda _=False, d=desc: self.handle_deletion(d))
                row.addWidget(del_btn)
                list_layout.addLayout(row)
            self.editor_layout.addWidget(list_box)
            return

        # Inline: render each child's full editor with a header + delete.
        for i, obj in enumerate(items):
            desc = {"type": singular[kind].lower(), "index": i}
            self._item_header(
                obj.get("name", ""), desc=desc,
                on_delete=lambda _=False, d=desc: self.handle_deletion(d),
            )
            if kind == "zones":
                self._render_zone_editor(desc, obj, inline=True)
            else:
                self._render_container_editor(desc, obj, inline=True)

    def _render_container_editor(self, desc, container, inline=False):
        coll = "autons" if desc["type"] == "auton" else "snippets"
        if not inline:
            self._editor_title(f"{desc['type'].title()}: {container.get('name', '')}")

        props = QGroupBox("Properties")
        form = QFormLayout(props)
        name_edit = QLineEdit(str(container.get("name", "")))
        name_edit.editingFinished.connect(
            lambda e=name_edit: self._apply_container_name(desc, container, e.text())
        )
        form.addRow("Name", name_edit)
        self.editor_layout.addWidget(props)

        self._section_header("Sequence")
        buttons = QHBoxLayout()
        add_primitive = QPushButton("+ Primitive")
        add_primitive.clicked.connect(lambda: self._add_step(desc, "primitive"))
        buttons.addWidget(add_primitive)
        add_snippet = QPushButton("+ Snippet")
        add_snippet.clicked.connect(lambda: self._add_step(desc, "snippet"))
        buttons.addWidget(add_snippet)
        self.editor_layout.addLayout(buttons)

        sequence = container.get("sequence", [])
        if not sequence:
            self.editor_layout.addWidget(QLabel("(empty sequence)"))
        for j, entry in enumerate(sequence):
            data = entry.get("data", {})
            if entry.get("kind") == "primitive":
                label = f"{j + 1}. {data.get('id', 'DO_NOTHING')}"
            else:
                label = f"{j + 1}. snippet: {data.get('file', '')}"
            step_desc = {"type": "step", "coll": coll, "owner": desc["index"], "index": j}

            if self.view_mode == "inline":
                # Header row carries reorder + delete; the full editor renders below.
                self._item_header(
                    label,
                    on_delete=lambda _=False, d=step_desc: self.handle_deletion(d),
                    up=lambda _=False, jj=j: self._move_step(coll, desc["index"], jj, -1),
                    down=lambda _=False, jj=j: self._move_step(coll, desc["index"], jj, 1),
                )
                if entry.get("kind") == "primitive":
                    self._render_primitive_editor(step_desc, data, inline=True)
                else:
                    self._render_snippet_ref_editor(step_desc, data, inline=True)
            else:
                row = QHBoxLayout()
                open_btn = QPushButton(label)
                open_btn.setStyleSheet("text-align: left;")
                open_btn.clicked.connect(lambda _=False, d=step_desc: self.populate_tree(select_data=d))
                row.addWidget(open_btn, 1)
                up_btn = QPushButton("Up")
                up_btn.setFixedWidth(40)
                up_btn.clicked.connect(lambda _=False, jj=j: self._move_step(coll, desc["index"], jj, -1))
                down_btn = QPushButton("Down")
                down_btn.setFixedWidth(50)
                down_btn.clicked.connect(lambda _=False, jj=j: self._move_step(coll, desc["index"], jj, 1))
                del_btn = QPushButton("Delete")
                del_btn.clicked.connect(lambda _=False, d=step_desc: self.handle_deletion(d))
                row.addWidget(up_btn)
                row.addWidget(down_btn)
                row.addWidget(del_btn)
                self.editor_layout.addLayout(row)

    def _render_primitive_editor(self, desc, primitive, inline=False):
        if not inline:
            self._editor_title(f"Primitive: {primitive.get('id', 'DO_NOTHING')}")
        group = QGroupBox("Primitive")
        form = QFormLayout(group)
        for attr in self._primitive_attrs():
            self._add_schema_field(
                form, primitive, attr,
                on_change=lambda k, v, d=desc, p=primitive: self._apply_primitive_field(d, p, k, v),
            )
        self.editor_layout.addWidget(group)

        mech_box = self._render_mechanism_data(primitive)
        if mech_box is not None:
            self.editor_layout.addWidget(mech_box)

        zones_box = QGroupBox("Zone References")
        zlayout = QVBoxLayout(zones_box)
        add_zone = QPushButton("+ Add Zone Reference")
        add_zone.clicked.connect(lambda: self._add_zoneref(desc))
        zlayout.addWidget(add_zone)
        for k, zref in enumerate(primitive.get("zones", [])):
            row = QHBoxLayout()
            combo = NoScrollComboBox()
            combo.addItem("")
            combo.addItems([self._zone_filename(z) for z in self.zones])
            combo.setCurrentText(str(zref.get("filename", "")))
            combo.currentTextChanged.connect(
                lambda text, d=desc, r=zref: self._apply_zoneref_filename(d, r, text)
            )
            row.addWidget(combo, 1)
            del_btn = QPushButton("Delete")
            del_btn.clicked.connect(lambda _=False, d=desc, kk=k: self._delete_zoneref(d, kk))
            row.addWidget(del_btn)
            zlayout.addLayout(row)
        self.editor_layout.addWidget(zones_box)

    def _render_zone_editor(self, desc, zone, inline=False):
        if not inline:
            self._editor_title(f"Zone: {zone.get('name', '')}")
        group = QGroupBox("Zone")
        form = QFormLayout(group)

        name_edit = QLineEdit(str(zone.get("name", "")))
        name_edit.editingFinished.connect(
            lambda e=name_edit: self._apply_zone_name(desc, zone, e.text())
        )
        form.addRow("Name", name_edit)

        shape = str(zone.get("zone_shape", "rectangle")).lower()
        if shape not in {"rectangle", "circle"}:
            shape = "circle" if "circlex" in zone else "rectangle"
        zone["zone_shape"] = shape
        shape_combo = NoScrollComboBox()
        shape_combo.addItems(["Rectangle", "Circle"])
        shape_combo.setCurrentText("Circle" if shape == "circle" else "Rectangle")
        shape_combo.currentTextChanged.connect(lambda text: self._set_zone_shape(desc, zone, text))
        form.addRow("Shape", shape_combo)

        geo_keys = CIRCLE_KEYS if shape == "circle" else RECT_KEYS
        for key in geo_keys:
            spin = self._make_numeric_spin(float(zone.get(key, 0.0) or 0.0))
            spin.valueChanged.connect(lambda value, z=zone, k=key: self._update_zone_field(z, k, value))
            # Only track spinboxes for the single selected zone (used by drag sync).
            if not inline:
                self._zone_spinboxes[key] = spin
            form.addRow(key, spin)

        handled = set(RECT_KEYS + CIRCLE_KEYS)
        for attr in self._zone_def_attrs():
            if attr["name"] in handled:
                continue
            self._add_schema_field(
                form, zone, attr,
                on_change=lambda k, v, z=zone: self._apply_field(z, k, v),
            )
        self.editor_layout.addWidget(group)

        mech_box = self._render_mechanism_data(zone)
        if mech_box is not None:
            self.editor_layout.addWidget(mech_box)

    def _render_zoneref_editor(self, desc, zref, inline=False):
        if not inline:
            self._editor_title("Zone Reference")
        group = QGroupBox("Zone Reference")
        form = QFormLayout(group)
        combo = NoScrollComboBox()
        combo.addItem("")
        combo.addItems([self._zone_filename(z) for z in self.zones])
        combo.setCurrentText(str(zref.get("filename", "")))
        combo.currentTextChanged.connect(
            lambda text: self._apply_zoneref_filename(desc, zref, text)
        )
        form.addRow("filename", combo)
        self.editor_layout.addWidget(group)

    def _render_snippet_ref_editor(self, desc, sref, inline=False):
        if not inline:
            self._editor_title("Snippet")
        group = QGroupBox("Snippet")
        form = QFormLayout(group)
        combo = self._make_choice_combo(
            [self._snippet_filename(s) for s in self.snippets], sref.get("file", "")
        )
        combo.currentTextChanged.connect(
            lambda text: self._apply_snippet_ref_file(desc, sref, text)
        )
        form.addRow("snippet", combo)
        self.editor_layout.addWidget(group)

    # -- schema-driven field widgets -- #
    def _make_numeric_spin(self, value):
        spin = NoScrollDoubleSpinBox()
        spin.setRange(-100.0, 100.0)
        spin.setDecimals(3)
        spin.setSingleStep(0.1)
        spin.setValue(value)
        return spin

    def _make_choice_combo(self, options, current, include_blank=True):
        """A select-only (non-editable) combo box.

        The current stored value is always shown, even if it isn't one of the
        standard options (e.g. a reference to an item outside the loaded folder),
        so switching to a non-editable box never silently drops a value.
        """
        combo = NoScrollComboBox()
        items = [""] if include_blank else []
        for opt in options:
            opt = str(opt)
            if opt not in items:
                items.append(opt)
        current = str(current)
        if current and current not in items:
            items.append(current)
        combo.addItems(items)
        combo.setCurrentText(current)
        return combo

    def _add_schema_field(self, form, data, attr, on_change):
        name = attr["name"]
        current = data.get(name, attr.get("default", ""))

        if name == "choreoname":
            combo = self._make_choice_combo(self._choreo_path_names(), current)
            combo.currentTextChanged.connect(lambda text, k=name: on_change(k, text))
            form.addRow(name, combo)
            return

        if attr["kind"] == "enum":
            combo = NoScrollComboBox()
            options = list(attr["options"])
            if "" not in options:
                combo.addItem("")
            combo.addItems(options)
            combo.setCurrentText(str(current))
            combo.currentTextChanged.connect(lambda text, k=name: on_change(k, text))
            form.addRow(name, combo)
            return

        if name in NUMERIC_ATTRS:
            spin = self._make_numeric_spin(float(current) if str(current).strip() else 0.0)
            spin.valueChanged.connect(lambda value, k=name: on_change(k, value))
            form.addRow(name, spin)
            return

        edit = QLineEdit(str(current))
        edit.editingFinished.connect(lambda e=edit, k=name: on_change(k, e.text()))
        form.addRow(name, edit)

    # ------------------------------------------------------------------ #
    # Editor mutations (operate on captured dicts; tree kept in sync)
    # ------------------------------------------------------------------ #
    def _apply_field(self, target, key, value):
        """Set (or clear) a plain attribute on a dict; persist without a rebuild."""
        text = str(value)
        if text == "":
            target.pop(key, None)
        else:
            target[key] = text
        self._save_data()

    def _apply_container_name(self, desc, container, name):
        name = name.strip()
        if not name:
            return
        container["name"] = name
        self._save_data()
        self.populate_tree(select_data=desc)

    def _apply_zone_name(self, desc, zone, name):
        name = name.strip()
        if not name:
            return
        zone["name"] = name
        self._save_data()
        self.populate_tree(select_data=desc)

    def _apply_primitive_field(self, desc, primitive, key, value):
        primitive[key] = str(value)
        self._save_data()
        if key == "id":
            # Label depends on id: rebuild the tree, keeping this step selected.
            self.populate_tree(select_data=desc)
        elif key == "choreoname":
            # Redraw the path but keep focus (choreoname edits fire per keystroke).
            self.refresh_field()

    def _update_zone_field(self, zone, key, value):
        zone[key] = round(float(value), 3)
        self._save_data()
        self.refresh_field()

    def _set_zone_shape(self, desc, zone, text):
        shape = "rectangle" if str(text).lower().startswith("rect") else "circle"
        zone["zone_shape"] = shape
        if shape == "rectangle":
            zone.setdefault("x1_rect", 1.0)
            zone.setdefault("y1_rect", 1.0)
            zone.setdefault("x2_rect", 3.0)
            zone.setdefault("y2_rect", 3.0)
            for key in CIRCLE_KEYS:
                zone.pop(key, None)
        else:
            zone.setdefault("circlex", FIELD_WIDTH / 2)
            zone.setdefault("circley", FIELD_HEIGHT / 2)
            zone.setdefault("radius", 1.0)
            for key in RECT_KEYS:
                zone.pop(key, None)
        self._save_data()
        self.render_editor()
        self.refresh_field()

    def zone_geometry_changed(self):
        """Called by draggable zone items: sync spinboxes + persist (no redraw)."""
        desc = self.current_selection
        if not desc or desc.get("type") != "zone":
            return
        zone = self._resolve(desc)
        if zone is None:
            return
        for key, spin in self._zone_spinboxes.items():
            spin.blockSignals(True)
            spin.setValue(float(zone.get(key, 0.0) or 0.0))
            spin.blockSignals(False)
        self._save_data()

    def _apply_snippet_ref_file(self, desc, ref, value):
        ref["file"] = str(value)
        self._save_data()
        self.populate_tree(select_data=desc)

    def _apply_zoneref_filename(self, desc, zref, value):
        zref["filename"] = str(value)
        self._save_data()
        # desc may be a primitive step (editing inline) or the zoneref node itself.
        self.populate_tree(select_data=desc)

    # -- sequence + zone-reference add/remove -- #
    def _add_step(self, container_desc, kind):
        container = self._resolve(container_desc)
        if container is None:
            return
        sequence = container.setdefault("sequence", [])
        if kind == "primitive":
            sequence.append({"kind": "primitive", "data": {"id": "DO_NOTHING", "time": "0.0", "zones": []}})
        else:
            sequence.append({"kind": "snippet", "data": {"file": ""}})
        self._save_data()
        coll = "autons" if container_desc["type"] == "auton" else "snippets"
        self.populate_tree(select_data={
            "type": "step", "coll": coll, "owner": container_desc["index"], "index": len(sequence) - 1,
        })

    def _move_step(self, coll, owner, index, delta):
        sequence = self._collection(coll)[owner]["sequence"]
        target = index + delta
        if not (0 <= target < len(sequence)):
            return
        sequence[index], sequence[target] = sequence[target], sequence[index]
        self._save_data()
        self.populate_tree(select_data={"type": "step", "coll": coll, "owner": owner, "index": target})

    def _add_zoneref(self, step_desc):
        entry = self._resolve(step_desc)
        if entry is None or entry.get("kind") != "primitive":
            return
        entry["data"].setdefault("zones", []).append({"filename": ""})
        self._save_data()
        self.populate_tree(select_data=step_desc)

    def _delete_zoneref(self, step_desc, index):
        entry = self._resolve(step_desc)
        if entry is None or entry.get("kind") != "primitive":
            return
        zones = entry["data"].get("zones", [])
        if 0 <= index < len(zones):
            del zones[index]
            self._save_data()
        self.populate_tree(select_data=step_desc)

    # ------------------------------------------------------------------ #
    # Mechanism integration (states come from the saved project data)
    # ------------------------------------------------------------------ #
    def _mechanism_state_fields(self):
        """Return ``{attributeName: [STATE_*, ...]}`` from the saved project.

        One field is produced per mechanism defined in the Mechanism Generator
        project: the attribute name is ``camelCase(mechanism) + "State"`` (e.g.
        ``Launcher`` -> ``launcherState``) and the options are that mechanism's
        state enum names. This is how autons, snippets (via their primitives) and
        zones pick up mechanism data from saved project data.
        """
        fields = {}
        if self.mechanism_model is None:
            return fields
        for robot in self.mechanism_model.project_data.get("robots", {}).values():
            for mech_name, mech in robot.get("mechanisms", {}).items():
                attr = f"{camel_case(mech_name)}State"
                options = fields.setdefault(attr, [])
                for state in mech.get("states", []):
                    if isinstance(state, dict) and state.get("name"):
                        enum_name = state_enum(state["name"])
                        if enum_name not in options:
                            options.append(enum_name)
        return fields

    def _render_mechanism_data(self, data):
        """Build the mechanism-data group box for a primitive or zone.

        The dropdown options are sourced entirely from the saved project data, so
        no mechanism metadata is added to the DTDs.
        """
        fields = self._mechanism_state_fields()
        # Preserve any *State attribute already present that has no mechanism.
        extra = {
            key: value for key, value in data.items()
            if key.endswith("State") and key not in fields
        }
        if not fields and not extra:
            return None

        box = QGroupBox("Mechanism Data")
        form = QFormLayout(box)
        for attr, options in fields.items():
            combo = self._make_choice_combo(options, data.get(attr, ""))
            combo.currentTextChanged.connect(lambda text, d=data, k=attr: self._on_mech_field(d, k, text))
            form.addRow(attr, combo)
        for attr, value in extra.items():
            combo = self._make_choice_combo([], value)
            combo.currentTextChanged.connect(lambda text, d=data, k=attr: self._on_mech_field(d, k, text))
            form.addRow(attr, combo)
        return box

    def _on_mech_field(self, data, key, value):
        text = str(value).strip()
        if text:
            data[key] = text
        else:
            data.pop(key, None)
        self._save_data()

    def _choreo_path_names(self):
        if not self.choreo_path or not os.path.isdir(self.choreo_path):
            return []
        names = set()
        for name in os.listdir(self.choreo_path):
            full = os.path.join(self.choreo_path, name)
            if os.path.isfile(full) and name.lower().endswith((".traj", ".json")):
                names.add(os.path.splitext(name)[0])
        return sorted(names)

    # ------------------------------------------------------------------ #
    # Field drawing
    # ------------------------------------------------------------------ #
    def refresh_field(self):
        self.field_scene.clear()
        self._robot_item = None
        self._draw_field()

        owner = None
        sel = self.current_selection
        if sel:
            kind = sel.get("type")
            if kind in ("auton", "snippet"):
                owner = self._resolve(sel)
            elif kind in ("step", "zoneref"):
                container = self.autons if sel["coll"] == "autons" else self.snippets
                if 0 <= sel["owner"] < len(container):
                    owner = container[sel["owner"]]

        zones_to_draw, interactive_zone = self._zones_for_selection()
        for zone in zones_to_draw:
            self._draw_zone(zone, interactive=(zone is interactive_zone))

        if owner is not None:
            self._draw_paths(owner)

        # Rebuild the playback timeline + robot marker for this selection.
        self._rebuild_playback(owner)
        self._create_robot_item()

        self.field_view._fit()

    def _zones_for_selection(self):
        """Decide which zones the field shows for the current selection.

        - Top level (a folder node or nothing selected): show every zone.
        - A single zone selected: show just that zone, editable (draggable).
        - An auton / snippet / step / zone-reference selected: show only the
          zones referenced by that auton or snippet (including via the snippets
          it calls). A selected zone-reference makes its target zone editable.
        """
        sel = self.current_selection
        if not sel or sel.get("type") == "folder":
            return list(self.zones), None

        kind = sel["type"]
        if kind == "zone":
            zone = self._resolve(sel)
            return ([zone] if zone is not None else []), zone

        if kind in ("auton", "snippet"):
            owner = self._resolve(sel)
        else:  # step / zoneref carry coll + owner index
            container = self.autons if sel.get("coll") == "autons" else self.snippets
            owner = container[sel["owner"]] if 0 <= sel.get("owner", -1) < len(container) else None
        if owner is None:
            return [], None

        filenames = self._referenced_zone_filenames(owner)
        zones = [z for z in self.zones if self._zone_filename(z) in filenames]

        interactive = None
        if kind == "zoneref":
            ref = self._resolve(sel)
            target = ref.get("filename") if ref else None
            interactive = next((z for z in zones if self._zone_filename(z) == target), None)
        return zones, interactive

    def _referenced_zone_filenames(self, container, _seen=None):
        """Collect every zone filename referenced by a container's sequence.

        Recurses into referenced snippets (guarding against cycles) so an auton
        shows the zones used by the snippets it calls as well as its own.
        """
        if _seen is None:
            _seen = set()
        names = set()
        for entry in container.get("sequence", []):
            if entry.get("kind") == "primitive":
                for zref in entry["data"].get("zones", []):
                    filename = zref.get("filename")
                    if filename:
                        names.add(filename)
            elif entry.get("kind") == "snippet":
                filename = entry["data"].get("file")
                if filename and filename not in _seen:
                    _seen.add(filename)
                    snippet = next(
                        (s for s in self.snippets if self._snippet_filename(s) == filename),
                        None,
                    )
                    if snippet is not None:
                        names |= self._referenced_zone_filenames(snippet, _seen)
        return names

    def _draw_field(self):
        if self._draw_field_image():
            # A thin outline over the real field image marks the legal rectangle.
            boundary = QGraphicsRectItem(0, 0, FIELD_WIDTH, FIELD_HEIGHT)
            boundary.setPen(QPen(QColor(255, 255, 255, 120), 0.03))
            boundary.setZValue(1)
            self.field_scene.addItem(boundary)
            return

        # Fallback (image missing): simple rectangle + centre line.
        boundary = QGraphicsRectItem(0, 0, FIELD_WIDTH, FIELD_HEIGHT)
        boundary.setPen(QPen(QColor(210, 210, 210), 0.06))
        boundary.setBrush(QBrush(QColor(24, 42, 30)))
        self.field_scene.addItem(boundary)
        mid = self.field_scene.addLine(
            FIELD_WIDTH / 2, 0, FIELD_WIDTH / 2, FIELD_HEIGHT,
            QPen(QColor(120, 120, 120), 0.04),
        )
        mid.setZValue(1)

    def _load_field_asset(self):
        """Load and cache the Choreo field image + its JSON metadata.

        Returns ``(QPixmap, meta_dict)`` or ``None`` if the asset is unavailable.
        """
        if self._field_asset is not None:
            return self._field_asset or None
        base = os.path.join(self._repo_root(), "assets", "fields")
        json_path = os.path.join(base, "field.json")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            png_path = os.path.join(base, meta.get("field-image", "field.png"))
            pixmap = QPixmap(png_path)
            if pixmap.isNull():
                raise ValueError("field image failed to load")
            self._field_asset = (pixmap, meta)
        except Exception:
            self._field_asset = False  # remember the failure; use the fallback
            return None
        return self._field_asset

    def _draw_field_image(self):
        """Draw the real FRC field PNG behind everything, in field metres.

        The field JSON maps the image's pixel corners to the field rectangle;
        we scale/position the pixmap so those corners land on (0,0)-(W,H) in the
        Y-flipped scene, exactly like Choreo's ``JSONFieldImage``.
        """
        asset = self._load_field_asset()
        if asset is None:
            return False
        pixmap, meta = asset
        try:
            corners = meta["field-corners"]
            left_px, top_px = corners["top-left"]
            right_px, _bottom_px = corners["bottom-right"]
            field_len_m = float(meta["field-size"][0])
            span_px = float(right_px - left_px)
            if span_px <= 0:
                return False
            m_per_px = field_len_m / span_px
        except (KeyError, IndexError, TypeError, ValueError):
            return False

        item = QGraphicsPixmapItem(pixmap)
        item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        item.setScale(m_per_px)
        # Place image so its field top-left pixel lands at scene (0, 0).
        item.setPos(-left_px * m_per_px, -top_px * m_per_px)
        item.setZValue(-10)
        self.field_scene.addItem(item)
        return True

    def _draw_zone(self, zone, interactive):
        shape = str(zone.get("zone_shape", "")).lower()
        is_circle = shape == "circle" or ("circlex" in zone and "x1_rect" not in zone)

        if interactive:
            item = ZoneCircleItem(zone, self) if is_circle else ZoneRectItem(zone, self)
            self.field_scene.addItem(item)
            return

        pen = QPen(QColor(90, 160, 120), 0.03)
        brush = QBrush(QColor(90, 160, 120, 45))
        if is_circle:
            r = max(float(zone.get("radius", 1.0) or 0.0), 0.05)
            cx, cy = world_to_scene(float(zone.get("circlex", 0.0) or 0.0),
                                    float(zone.get("circley", 0.0) or 0.0))
            item = QGraphicsEllipseItem(cx - r, cy - r, 2 * r, 2 * r)
        else:
            x1 = float(zone.get("x1_rect", 0.0) or 0.0)
            y1 = float(zone.get("y1_rect", 0.0) or 0.0)
            x2 = float(zone.get("x2_rect", 0.0) or 0.0)
            y2 = float(zone.get("y2_rect", 0.0) or 0.0)
            tl_x, tl_y = world_to_scene(min(x1, x2), max(y1, y2))
            item = QGraphicsRectItem(tl_x, tl_y, abs(x2 - x1), abs(y2 - y1))
        item.setPen(pen)
        item.setBrush(brush)
        self.field_scene.addItem(item)
        self._add_zone_label(zone, is_circle, highlight=False)

    def _add_zone_label(self, zone, is_circle, highlight):
        if is_circle:
            wx = float(zone.get("circlex", 0.0) or 0.0)
            wy = float(zone.get("circley", 0.0) or 0.0)
        else:
            wx = (float(zone.get("x1_rect", 0.0) or 0.0) + float(zone.get("x2_rect", 0.0) or 0.0)) / 2
            wy = (float(zone.get("y1_rect", 0.0) or 0.0) + float(zone.get("y2_rect", 0.0) or 0.0)) / 2
        sx, sy = world_to_scene(wx, wy)
        text = self.field_scene.addText(zone.get("name", ""))
        text.setDefaultTextColor(QColor(255, 255, 255) if highlight else QColor(180, 210, 190))
        text.setScale(0.02)
        rect = text.boundingRect()
        text.setPos(sx - rect.width() * 0.01, sy - rect.height() * 0.01)
        text.setZValue(15)

    def _draw_paths(self, owner):
        seg = 0
        for primitive in self._owner_primitives(owner):
            choreoname = primitive.get("choreoname")
            if not choreoname:
                continue
            points = self._load_trajectory_points(choreoname)
            if len(points) < 2:
                continue
            color = QColor(*PATH_PALETTE[seg % len(PATH_PALETTE)])
            path = QPainterPath()
            sx, sy = world_to_scene(*points[0])
            path.moveTo(sx, sy)
            for (x, y) in points[1:]:
                px, py = world_to_scene(x, y)
                path.lineTo(px, py)
            path_item = QGraphicsPathItem(path)
            path_item.setPen(QPen(color, 0.07))
            path_item.setZValue(5)
            self.field_scene.addItem(path_item)

            self._draw_marker(points[0], color.lighter(130))
            self._draw_marker(points[-1], color.darker(130))
            self._draw_path_number(points[0], seg + 1, color)
            seg += 1

    def _draw_path_number(self, point, number, color):
        """A numbered badge at a path's start so the auton order is readable."""
        sx, sy = world_to_scene(*point)
        r = 0.26
        badge = QGraphicsEllipseItem(sx - r, sy - r, 2 * r, 2 * r)
        badge.setPen(QPen(QColor(20, 20, 20), 0.03))
        badge.setBrush(QBrush(color))
        badge.setZValue(14)
        self.field_scene.addItem(badge)
        text = self.field_scene.addText(str(number))
        text.setDefaultTextColor(QColor(20, 20, 20))
        text.setScale(0.02)
        tr = text.boundingRect()
        text.setPos(sx - tr.width() * 0.01, sy - tr.height() * 0.01)
        text.setZValue(15)

    def _draw_marker(self, point, color):
        sx, sy = world_to_scene(*point)
        r = 0.12
        marker = QGraphicsEllipseItem(sx - r, sy - r, 2 * r, 2 * r)
        marker.setPen(QPen(color, 0.03))
        marker.setBrush(QBrush(color))
        marker.setZValue(6)
        self.field_scene.addItem(marker)

    def _resolve_traj_path(self, choreoname):
        if not choreoname or not self.choreo_path or not os.path.isdir(self.choreo_path):
            return None
        candidates = [
            os.path.join(self.choreo_path, choreoname + ".traj"),
            os.path.join(self.choreo_path, choreoname + ".json"),
            os.path.join(self.choreo_path, choreoname),
        ]
        return next((p for p in candidates if os.path.isfile(p)), None)

    def _load_trajectory_points(self, choreoname):
        path = self._resolve_traj_path(choreoname)
        if not path:
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []
        samples = (data.get("trajectory") or {}).get("samples") or []
        points = [(s["x"], s["y"]) for s in samples if "x" in s and "y" in s]
        if not points:
            waypoints = (data.get("snapshot") or {}).get("waypoints") or []
            points = [(w["x"], w["y"]) for w in waypoints if "x" in w and "y" in w]
        return points

    def _load_trajectory_full(self, choreoname):
        """Return ``{"samples": [(t,x,y,heading)...], "bumper": (f,s,b)}`` or None."""
        path = self._resolve_traj_path(choreoname)
        if not path:
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return None
        traj = data.get("trajectory") or {}
        raw = traj.get("samples") or []
        samples = [
            (float(s["t"]), float(s["x"]), float(s["y"]), float(s.get("heading", 0.0)))
            for s in raw
            if "t" in s and "x" in s and "y" in s
        ]
        if len(samples) < 2:
            return None
        bump = (traj.get("config") or {}).get("bumper") or {}
        bumper = (
            float(bump.get("front", 0.4)),
            float(bump.get("side", 0.4)),
            float(bump.get("back", 0.4)),
        )
        return {"samples": samples, "bumper": bumper}

