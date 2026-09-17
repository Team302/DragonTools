"""Auton Builder tab for DragonTools.

This initial implementation focuses on the structure requested by the user:
- a selectable choreo path folder
- a tree for Autons, Zones, and Snippets
- visual field rendering for the selected auton and zone
- numeric editing and drag editing for zones
- a DTD sync action that can refresh mechanism state fields in the DTD
"""

import os
import xml.etree.ElementTree as ET
from typing import Any

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


FIELD_WIDTH = 16.54
FIELD_HEIGHT = 8.21


class ZoneGraphicsRect(QGraphicsRectItem):
    """A draggable zone rectangle on the field."""

    def __init__(self, zone, refresh_cb=None):
        self.zone = zone
        self.refresh_cb = refresh_cb
        x1 = float(zone.get("x1_rect", 0.0))
        y1 = float(zone.get("y1_rect", 0.0))
        x2 = float(zone.get("x2_rect", x1 + 1.0))
        y2 = float(zone.get("y2_rect", y1 + 1.0))
        super().__init__(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
        self.setPen(QPen(QColor(0, 255, 160), 2))
        self.setBrush(QBrush(QColor(0, 255, 160, 80)))
        self.setAcceptHoverEvents(True)

    def mouseMoveEvent(self, event):
        new_pos = event.scenePos()
        if new_pos.x() < 0:
            new_pos.setX(0)
        if new_pos.y() < 0:
            new_pos.setY(0)
        if new_pos.x() > FIELD_WIDTH:
            new_pos.setX(FIELD_WIDTH)
        if new_pos.y() > FIELD_HEIGHT:
            new_pos.setY(FIELD_HEIGHT)
        self.zone["x1_rect"] = round(float(new_pos.x()), 3)
        self.zone["y1_rect"] = round(float(new_pos.y()), 3)
        self.zone["x2_rect"] = round(float(new_pos.x() + max(abs(float(self.zone.get("x2_rect", 0.0)) - float(self.zone.get("x1_rect", 0.0))), 0.5)), 3)
        self.zone["y2_rect"] = round(float(new_pos.y() + max(abs(float(self.zone.get("y2_rect", 0.0)) - float(self.zone.get("y1_rect", 0.0))), 0.5)), 3)
        self.setRect(
            min(float(self.zone["x1_rect"]), float(self.zone["x2_rect"])),
            min(float(self.zone["y1_rect"]), float(self.zone["y2_rect"])),
            abs(float(self.zone["x2_rect"]) - float(self.zone["x1_rect"])),
            abs(float(self.zone["y2_rect"]) - float(self.zone["y1_rect"])),
        )
        if self.refresh_cb:
            self.refresh_cb()
        super().mouseMoveEvent(event)


class ZoneGraphicsCircle(QGraphicsEllipseItem):
    """A draggable zone circle on the field."""

    def __init__(self, zone, refresh_cb=None):
        self.zone = zone
        self.refresh_cb = refresh_cb
        cx = float(zone.get("circlex", 1.0))
        cy = float(zone.get("circley", 1.0))
        radius = float(zone.get("radius", 1.0))
        super().__init__(cx - radius, cy - radius, radius * 2, radius * 2)
        self.setPen(QPen(QColor(255, 180, 70), 2))
        self.setBrush(QBrush(QColor(255, 180, 70, 80)))

    def mouseMoveEvent(self, event):
        pos = event.scenePos()
        self.zone["circlex"] = round(float(max(0, min(FIELD_WIDTH, pos.x()))), 3)
        self.zone["circley"] = round(float(max(0, min(FIELD_HEIGHT, pos.y()))), 3)
        radius = max(float(self.zone.get("radius", 1.0)), 0.25)
        self.setRect(self.zone["circlex"] - radius, self.zone["circley"] - radius, radius * 2, radius * 2)
        if self.refresh_cb:
            self.refresh_cb()
        super().mouseMoveEvent(event)


class AutonBuilderWidget(QWidget):
    def __init__(self, mechanism_model=None):
        super().__init__()
        self.mechanism_model = mechanism_model
        self.choreo_path = ""
        self.autons = []
        self.zones = []
        self.snippets = []
        self.current_item = None
        self.field_scene = QGraphicsScene(0, 0, 760, 420)
        self.field_scene.setBackgroundBrush(QColor(21, 35, 22))
        self.field_view = QGraphicsView(self.field_scene)
        self.field_view.setRenderHint(self.field_view.renderHints())
        self.field_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.field_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Auton Builder")
        self.tree.setColumnCount(1)
        self.tree.itemClicked.connect(self.on_tree_click)

        self.editor_panel = QWidget()
        self.editor_layout = QVBoxLayout(self.editor_panel)

        self._build_layout()

        self._restore_settings()
        self._load_saved_data()
        if not self.autons and not self.zones and not self.snippets:
            self._load_example_data()
        self.refresh_tree()
        self.refresh_field()

    def _build_layout(self):
        root = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        tree_wrap = QWidget()
        tree_layout = QVBoxLayout(tree_wrap)
        tree_actions = QHBoxLayout()
        self.btn_new_auton = QPushButton("+ Add Auton")
        self.btn_new_auton.clicked.connect(self.add_new_auton)
        self.btn_new_zone = QPushButton("+ Add Zone")
        self.btn_new_zone.clicked.connect(self.add_new_zone)
        self.btn_new_snippet = QPushButton("+ Add Snippet")
        self.btn_new_snippet.clicked.connect(self.add_new_snippet)
        tree_actions.addWidget(self.btn_new_auton)
        tree_actions.addWidget(self.btn_new_zone)
        tree_actions.addWidget(self.btn_new_snippet)
        tree_layout.addLayout(tree_actions)
        tree_layout.addWidget(self.tree)

        generation_actions = QHBoxLayout()
        self.btn_generate = QPushButton("Generate Auton")
        self.btn_generate.setStyleSheet(
            "background-color: #005A9C; color: white; font-weight: bold; "
            "padding: 12px; font-size: 14px; border-radius: 4px;"
        )
        self.btn_generate.clicked.connect(self.generate_auton)
        self.btn_sync_dtd = QPushButton("Sync DTD with Mechanism")
        self.btn_sync_dtd.setStyleSheet(
            "background-color: #005A9C; color: white; font-weight: bold; "
            "padding: 12px; font-size: 14px; border-radius: 4px;"
        )
        self.btn_sync_dtd.clicked.connect(self.sync_dtd_with_mechanism)
        generation_actions.addWidget(self.btn_generate)
        generation_actions.addWidget(self.btn_sync_dtd)
        tree_layout.addLayout(generation_actions)
        splitter.addWidget(tree_wrap)

        visual_and_editor = QSplitter(Qt.Orientation.Vertical)
        visual_and_editor.setChildrenCollapsible(False)
        visual_and_editor.addWidget(self.field_view)
        visual_and_editor.addWidget(self.editor_panel)
        splitter.addWidget(visual_and_editor)

        splitter.setSizes([300, 900])
        root.addWidget(splitter)

    def _restore_settings(self):
        self.folder_label = QLabel()
        if self.mechanism_model is not None:
            saved_path = self.mechanism_model.app_settings.get("auton_choreo_path", "")
            if saved_path and os.path.exists(saved_path):
                self.choreo_path = saved_path

    def select_choreo_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Path Folder")
        if not folder:
            return
        self.choreo_path = folder
        if self.mechanism_model is not None:
            self.mechanism_model.set_app_setting("auton_choreo_path", folder)
        self.refresh_field()

    def _load_saved_data(self):
        if self.mechanism_model is None:
            return
        saved = self.mechanism_model.project_data.get("auton_builder", {})
        self.autons = saved.get("autons", [])
        self.zones = saved.get("zones", [])
        self.snippets = saved.get("snippets", [])

    def _save_data(self):
        if self.mechanism_model is not None:
            self.mechanism_model.project_data["auton_builder"] = {
                "autons": self.autons,
                "zones": self.zones,
                "snippets": self.snippets,
            }

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
        self._save_data()
        QMessageBox.information(
            self,
            "Generate Auton",
            "Auton data has been saved to the project JSON. XML generation will use this data.",
        )

    def add_new_auton(self):
        name = f"NewAuton_{len(self.autons) + 1}"
        auton = {
            "name": name,
            "type": "auton",
            "filename": os.path.join(self.choreo_path or ".", f"{name}.xml"),
            "primitives": [],
            "snippets": [],
            "zones": [],
            "launcherState": "STATE_IDLE",
            "intakeState": "STATE_OFF",
        }
        self.autons.append(auton)
        self._save_data()
        self.refresh_tree()
        self._select_payload({"type": "auton", "data": auton})

    def add_new_zone(self):
        name = f"NewZone_{len(self.zones) + 1}"
        zone = {
            "name": name,
            "type": "zone",
            "zone_shape": "rectangle",
            "x1_rect": 0.0,
            "y1_rect": 0.0,
            "x2_rect": 2.0,
            "y2_rect": 2.0,
            "circlex": 0.0,
            "circley": 0.0,
            "radius": 1.0,
            "pathUpdateOption": "NOTHING",
            "launcherState": "STATE_IDLE",
            "intakeState": "STATE_OFF",
            "allianceColor": "BOTH",
        }
        self.zones.append(zone)
        self._save_data()
        self.refresh_tree()
        self._select_payload({"type": "zone", "data": zone})

    def add_new_snippet(self):
        name = f"NewSnippet_{len(self.snippets) + 1}"
        snippet = {
            "name": name,
            "type": "snippet",
            "filename": os.path.join(self.choreo_path or ".", f"{name}.xml"),
            "file": os.path.join(self.choreo_path or ".", f"{name}.xml"),
            "primitives": [],
            "zones": [],
        }
        self.snippets.append(snippet)
        self._save_data()
        self.refresh_tree()
        self._select_payload({"type": "snippet", "data": snippet})

    def _select_payload(self, payload):
        self.current_item = payload
        self.tree.clearSelection()
        for top_index in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(top_index)
            for child_index in range(top_item.childCount()):
                child = top_item.child(child_index)
                node = child.data(0, Qt.ItemDataRole.UserRole)
                if node == payload:
                    self.tree.setCurrentItem(child)
                    self._render_editor_for_selection(payload)
                    self.refresh_field()
                    return
        self._render_editor_for_selection(payload)
        self.refresh_field()

    def _load_example_data(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        example_dir = os.path.join(repo_root, "AutonExample")
        if not os.path.isdir(example_dir):
            return

        self.autons = []
        self.zones = []
        self.snippets = []

        self._load_zone_examples(example_dir)
        self._load_snippet_examples(example_dir)
        self._load_auton_examples(example_dir)

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
                zone = {"name": os.path.splitext(name)[0], "filename": path, "type": "zone"}
                zone_el = root.find("zone")
                if zone_el is not None:
                    for key, value in zone_el.attrib.items():
                        zone[key] = value
                zone["zone_shape"] = "circle" if "circlex" in zone else "rectangle"
                self.zones.append(zone)
            except Exception:
                pass

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
                snippet = {
                    "name": os.path.splitext(name)[0],
                    "filename": path,
                    "type": "snippet",
                    "file": path,
                    "primitives": [],
                    "zones": [],
                }
                self._load_auton_children(root, snippet)
                self.snippets.append(snippet)
            except Exception:
                pass

    def _load_auton_examples(self, example_dir):
        for name in sorted(os.listdir(example_dir)):
            if not name.lower().endswith(".xml") or name.lower().endswith(".dtd"):
                continue
            if os.path.isdir(os.path.join(example_dir, name)):
                continue
            path = os.path.join(example_dir, name)
            try:
                root = ET.parse(path).getroot()
                auton = {"name": os.path.splitext(name)[0], "filename": path, "type": "auton"}
                self._load_auton_children(root, auton)
                self.autons.append(auton)
            except Exception:
                pass

    def _load_auton_children(self, root, owner):
        for child in list(root):
            if child.tag == "primitive":
                primitive = dict(child.attrib)
                primitive["zones"] = [
                    dict(zone.attrib) for zone in child.findall("zone")
                ]
                owner.setdefault("primitives", []).append(primitive)
            elif child.tag == "snippet":
                owner.setdefault("snippets", []).append(dict(child.attrib))
            elif child.tag == "zone":
                owner.setdefault("zones", []).append(dict(child.attrib))

    def refresh_tree(self):
        self.tree.clear()
        top = QTreeWidgetItem(["Autons"])
        for auton in self.autons:
            item = QTreeWidgetItem([auton["name"]])
            item.setData(0, Qt.ItemDataRole.UserRole, {"type": "auton", "data": auton})
            top.addChild(item)
            self._add_sequence_children(item, auton, allow_snippets=True)
        self.tree.addTopLevelItem(top)

        zones_root = QTreeWidgetItem(["Zones"])
        for zone in self.zones:
            item = QTreeWidgetItem([zone["name"]])
            item.setData(0, Qt.ItemDataRole.UserRole, {"type": "zone", "data": zone})
            zones_root.addChild(item)
        self.tree.addTopLevelItem(zones_root)

        snippets_root = QTreeWidgetItem(["Snippets"])
        for snippet in self.snippets:
            item = QTreeWidgetItem([snippet["name"]])
            item.setData(0, Qt.ItemDataRole.UserRole, {"type": "snippet", "data": snippet})
            snippets_root.addChild(item)
            self._add_sequence_children(item, snippet, allow_snippets=False)
        self.tree.addTopLevelItem(snippets_root)

        self.tree.expandAll()

    def _add_sequence_children(self, parent, owner, allow_snippets):
        for index, primitive in enumerate(owner.get("primitives", [])):
            child = QTreeWidgetItem([f"Primitive {index + 1}: {primitive.get('id', 'DO_NOTHING')}"])
            child.setData(0, Qt.ItemDataRole.UserRole, {
                "type": "primitive", "data": primitive, "owner": owner,
            })
            parent.addChild(child)
        for index, zone in enumerate(owner.get("zones", [])):
            child = QTreeWidgetItem([f"Zone {index + 1}: {zone.get('filename', 'Unnamed')}"])
            child.setData(0, Qt.ItemDataRole.UserRole, {
                "type": "sequence_zone", "data": zone, "owner": owner,
            })
            parent.addChild(child)
        if allow_snippets:
            for index, snippet in enumerate(owner.get("snippets", [])):
                child = QTreeWidgetItem([f"Snippet {index + 1}: {snippet.get('file', 'Unnamed')}"])
                child.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "sequence_snippet", "data": snippet, "owner": owner,
                })
                parent.addChild(child)

    def on_tree_click(self, item):
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not payload:
            return
        self.current_item = payload
        self._render_editor_for_selection(payload)
        self.refresh_field()

    def _render_editor_for_selection(self, payload):
        for idx in range(self.editor_layout.count()):
            widget = self.editor_layout.itemAt(idx).widget()
            if widget is not None:
                widget.deleteLater()
        while self.editor_layout.count():
            item = self.editor_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        item_type = payload["type"]
        data = payload["data"]

        title = QLabel(f"{item_type.title()} Editor")
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.editor_layout.addWidget(title)

        group = QGroupBox("Properties")
        form = QFormLayout(group)

        if item_type in {"auton", "snippet"}:
            name_edit = QLineEdit(str(data.get("name", "")))
            name_edit.editingFinished.connect(
                lambda edit=name_edit, selected=data: self._rename_item(selected, edit.text())
            )
            form.addRow("Name", name_edit)
            form.addRow("Primitive Count", QLabel(str(len(data.get("primitives", [])))))
            form.addRow("Zone Count", QLabel(str(len(data.get("zones", [])))))
            if item_type == "auton":
                form.addRow("Snippet Count", QLabel(str(len(data.get("snippets", [])))))

            sequence_actions = QHBoxLayout()
            add_primitive = QPushButton("Add Primitive")
            add_primitive.clicked.connect(lambda: self._add_primitive(data))
            add_zone = QPushButton("Add Zone")
            add_zone.clicked.connect(lambda: self._add_sequence_zone(data))
            sequence_actions.addWidget(add_primitive)
            sequence_actions.addWidget(add_zone)
            if item_type == "auton":
                add_snippet = QPushButton("Add Snippet")
                add_snippet.clicked.connect(lambda: self._add_sequence_snippet(data))
                sequence_actions.addWidget(add_snippet)
            form.addRow(sequence_actions)

        elif item_type == "primitive":
            self._render_primitive_editor(form, data)

        elif item_type in {"sequence_zone", "sequence_snippet"}:
            reference = QComboBox()
            if item_type == "sequence_zone":
                reference.addItems([""] + [str(zone.get("name", "")) for zone in self.zones])
                current = str(data.get("filename", ""))
                reference.setCurrentText(current)
                reference.currentTextChanged.connect(
                    lambda value: self._update_sequence_reference(data, "filename", value)
                )
            else:
                reference.addItems([""] + [str(snippet.get("name", "")) for snippet in self.snippets])
                current = str(data.get("file", ""))
                reference.setCurrentText(current)
                reference.currentTextChanged.connect(
                    lambda value: self._update_sequence_reference(data, "file", value)
                )
            form.addRow("Reference", reference)

        elif item_type == "zone":
            name_edit = QLineEdit(str(data.get("name", "")))
            name_edit.editingFinished.connect(
                lambda edit=name_edit, selected=data: self._rename_item(selected, edit.text())
            )
            form.addRow("Name", name_edit)

            zone_shape = str(data.get("zone_shape", "rectangle")).lower()
            if zone_shape not in {"rectangle", "circle"}:
                zone_shape = "rectangle"
            data["zone_shape"] = zone_shape

            shape_combo = QComboBox()
            shape_combo.addItems(["Rectangle", "Circle"])
            shape_combo.setCurrentText("Rectangle" if zone_shape == "rectangle" else "Circle")
            shape_combo.currentTextChanged.connect(
                lambda text, current_payload=payload: self._set_zone_shape(current_payload["data"], text)
            )
            form.addRow("Zone Type", shape_combo)

            if zone_shape == "rectangle":
                for key in ["x1_rect", "y1_rect", "x2_rect", "y2_rect"]:
                    value = float(data.get(key, 0.0))
                    field = QDoubleSpinBox()
                    field.setRange(-20.0, 30.0)
                    field.setSingleStep(0.1)
                    field.setValue(value)
                    field.valueChanged.connect(lambda new_value, k=key: self._update_zone_field(k, new_value))
                    form.addRow(key, field)
            else:
                for key in ["circlex", "circley", "radius"]:
                    value = float(data.get(key, 0.0))
                    field = QDoubleSpinBox()
                    field.setRange(-20.0, 30.0)
                    field.setSingleStep(0.1)
                    field.setValue(value)
                    field.valueChanged.connect(lambda new_value, k=key: self._update_zone_field(k, new_value))
                    form.addRow(key, field)

            path_update = QComboBox()
            path_update.addItems(["DRIVE_TO_HUB", "DRIVE_OVER_BUMP", "DRIVE_TO_DEPOT", "DRIVE_TO_OUTPOST", "DRIVE_TO_TOWER", "NOTHING"])
            path_update.setCurrentText(str(data.get("pathUpdateOption", "NOTHING")))
            path_update.currentTextChanged.connect(lambda text: self._update_zone_field("pathUpdateOption", text))
            form.addRow("pathUpdateOption", path_update)

        elif item_type == "snippet":
            form.addRow("Name", QLabel(data.get("name", "")))
            form.addRow("File", QLabel(data.get("filename", "")))

        self.editor_layout.addWidget(group)
        self.editor_layout.addStretch()

    def _rename_item(self, data, name):
        name = name.strip()
        if not name:
            return
        data["name"] = name
        self._save_data()
        self.refresh_tree()

    def _render_primitive_editor(self, form, primitive):
        fields = [
            ("id", ["DO_NOTHING", "HOLD_POSITION", "TRAJECTORY_DRIVE",
                    "RESET_POSITION", "RESET_POSITION_NO_VISION", "DRIVE_STOP_MECH"]),
        ]
        for key, values in fields:
            combo = QComboBox()
            combo.addItems(values)
            combo.setCurrentText(str(primitive.get(key, values[0])))
            combo.currentTextChanged.connect(lambda value, k=key: self._update_primitive(k, value))
            form.addRow(key, combo)

        time_edit = QDoubleSpinBox()
        time_edit.setRange(0.0, 999.0)
        time_edit.setDecimals(3)
        time_edit.setValue(float(primitive.get("time", 0.0)))
        time_edit.valueChanged.connect(lambda value: self._update_primitive("time", value))
        form.addRow("time", time_edit)

        if primitive.get("id", "DO_NOTHING") == "TRAJECTORY_DRIVE":
            path_names = []
            if self.choreo_path and os.path.isdir(self.choreo_path):
                path_names = sorted(
                    os.path.splitext(name)[0]
                    for name in os.listdir(self.choreo_path)
                    if os.path.isfile(os.path.join(self.choreo_path, name))
                    and name.lower().endswith((".json", ".traj", ".csv"))
                )
            if not path_names:
                path_names = [str(primitive.get("choreoname", ""))]
            path_combo = QComboBox()
            path_combo.setEditable(True)
            path_combo.addItems(path_names)
            path_combo.setCurrentText(str(primitive.get("choreoname", "")))
            path_combo.currentTextChanged.connect(
                lambda value: self._update_primitive("choreoname", value)
            )
            form.addRow("choreoname", path_combo)

    def _update_primitive(self, key, value):
        if not self.current_item or self.current_item["type"] != "primitive":
            return
        self.current_item["data"][key] = str(value)
        self._save_data()
        self.refresh_tree()
        self.refresh_field()

    def _update_sequence_reference(self, data, key, value):
        data[key] = value
        self._save_data()

    def _add_primitive(self, owner):
        owner.setdefault("primitives", []).append({
            "id": "DO_NOTHING", "time": "0.0",
            "zones": [],
        })
        self._save_data()
        self.refresh_tree()

    def _add_sequence_zone(self, owner):
        owner.setdefault("zones", []).append({"filename": ""})
        self._save_data()
        self.refresh_tree()

    def _add_sequence_snippet(self, owner):
        owner.setdefault("snippets", []).append({"file": ""})
        self._save_data()
        self.refresh_tree()

    def _set_zone_shape(self, data, text):
        shape_value = "rectangle" if str(text).lower() == "rectangle" else "circle"
        data["zone_shape"] = shape_value
        if shape_value == "rectangle":
            data.setdefault("x1_rect", 0.0)
            data.setdefault("y1_rect", 0.0)
            data.setdefault("x2_rect", 2.0)
            data.setdefault("y2_rect", 2.0)
            data.pop("circlex", None)
            data.pop("circley", None)
            data.pop("radius", None)
        else:
            data.setdefault("circlex", 1.0)
            data.setdefault("circley", 1.0)
            data.setdefault("radius", 1.0)
            data.pop("x1_rect", None)
            data.pop("y1_rect", None)
            data.pop("x2_rect", None)
            data.pop("y2_rect", None)
        self._save_data()
        self.refresh_field()
        self._render_editor_for_selection(self.current_item)

    def _update_zone_field(self, key, value):
        if not self.current_item or self.current_item["type"] != "zone":
            return
        self.current_item["data"][key] = value
        self._save_data()
        self.refresh_field()

    def _update_auton_field(self, key, value):
        if not self.current_item or self.current_item["type"] != "auton":
            return
        self.current_item["data"][key] = value
        self._save_data()
        self.refresh_field()

    def _mechanism_state_options(self):
        if self.mechanism_model is None:
            return []
        options = []
        project_data = self.mechanism_model.project_data
        for robot_id, robot_data in project_data.get("robots", {}).items():
            for mech_name, mech_data in robot_data.get("mechanisms", {}).items():
                for state in mech_data.get("states", []):
                    if isinstance(state, dict):
                        state_name = state.get("name", "")
                        if state_name:
                            options.append(state_name)
        deduped = []
        for option in options:
            if option not in deduped:
                deduped.append(option)
        return deduped

    def refresh_field(self):
        self.field_scene.clear()
        field = QGraphicsRectItem(0, 0, FIELD_WIDTH, FIELD_HEIGHT)
        field.setPen(QPen(QColor(200, 200, 200), 2))
        field.setBrush(QBrush(QColor(20, 38, 26)))
        self.field_scene.addItem(field)

        for zone in self.zones:
            if "x1_rect" in zone or "circlex" in zone:
                if "circlex" in zone:
                    zone_item = ZoneGraphicsCircle(zone, self.refresh_field)
                    self.field_scene.addItem(zone_item)
                else:
                    zone_item = ZoneGraphicsRect(zone, self.refresh_field)
                    self.field_scene.addItem(zone_item)

        if self.current_item and self.current_item["type"] == "auton":
            auton = self.current_item["data"]
            primitives = auton.get("primitives", [])
            for primitive in primitives:
                if "choreoname" in primitive:
                    path_text = self.field_scene.addText(primitive.get("choreoname", "Path"))
                    path_text.setPos(10, 10)

        self.field_scene.update()

    #fill in with mechansim based on mechanism defintion
    def sync_dtd_with_mechanism(self):
        return