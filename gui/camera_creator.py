"""Camera Creator: per-robot camera editing, visualization and C++ export."""

import os

from jinja2 import TemplateError
from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton,
    QScrollArea, QSplitter, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt

from generation import DragonCodeGenerator
from generation.cameras import (
    ANGLE_FIELDS, ANGLE_UNITS, DECIMAL_PLACES, DIMENSION_FIELDS, LENGTH_UNITS,
    LIMELIGHT_OPTIONS, POSE_FIELDS, UNIT_FACTORS, default_camera_config,
    field_unit, new_camera, validate_camera_config,
)
from .camera_preview import CameraPreview
from .constants import VERSION


class CameraCreatorWidget(QWidget):
    def __init__(self, mechanism_model, parent=None):
        super().__init__(parent)
        self.model = mechanism_model
        self.config = None
        self._loading = False
        self._valid_config = True
        layout = QVBoxLayout(self)

        robot_row = QHBoxLayout()
        robot_row.addWidget(QLabel("Robot:"))
        self.robot_combo = QComboBox()
        robot_row.addWidget(self.robot_combo, 1)
        layout.addLayout(robot_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.controls = QWidget()
        controls_layout = QVBoxLayout(self.controls)
        scroll.setWidget(self.controls)
        splitter.addWidget(scroll)

        robot_box = QGroupBox("Robot dimensions")
        robot_form = QFormLayout(robot_box)
        self.robot_length = self._spin()
        self.robot_width = self._spin()
        self.dimension_widgets = {"robot_length_in": self.robot_length, "robot_width_in": self.robot_width}
        self.dimension_unit_widgets = {}
        for field, label in (("robot_length_in", "Length (front to back):"), ("robot_width_in", "Width (left to right):")):
            combo = self._unit_combo(field)
            combo.currentIndexChanged.connect(lambda _index, key=field: self._dimension_unit_changed(key))
            self.dimension_unit_widgets[field] = combo
            robot_form.addRow(label, self._with_unit(self.dimension_widgets[field], combo))
        controls_layout.addWidget(robot_box)

        buttons = QHBoxLayout()
        self.add_limelight_button = QPushButton("+ Add Limelight")
        self.add_quest_button = QPushButton("+ Add Quest")
        buttons.addWidget(self.add_limelight_button)
        buttons.addWidget(self.add_quest_button)
        controls_layout.addLayout(buttons)
        self.camera_list = QListWidget()
        self.camera_list.setMaximumHeight(155)
        controls_layout.addWidget(self.camera_list)
        self.remove_button = QPushButton("Remove Selected Camera")
        controls_layout.addWidget(self.remove_button)

        self.camera_box = QGroupBox("Selected camera")
        camera_form = QFormLayout(self.camera_box)
        self.camera_form = camera_form
        self.name_edit = QLineEdit()
        self.name_edit.setToolTip("NetworkTables name for Limelight; descriptive label for Quest. Use a-z, 0-9 and hyphens.")
        camera_form.addRow("Name / NT name:", self.name_edit)
        self.option_widgets = {}
        for key, options in LIMELIGHT_OPTIONS.items():
            combo = QComboBox()
            combo.addItems(options)
            camera_form.addRow(key.replace("_", " ").title() + ":", combo)
            combo.currentTextChanged.connect(lambda value, field=key: self._set_camera_value(field, value))
            self.option_widgets[key] = combo
        self.pose_widgets = {}
        self.pose_unit_widgets = {}
        for field, label in zip(
            POSE_FIELDS, ("X (forward +)", "Y (left +)", "Z (up +)", "Pitch (about Y)", "Yaw (about Z)", "Roll (about X)")
        ):
            spin = self._spin()
            combo = self._unit_combo(field)
            camera_form.addRow(label + ":", self._with_unit(spin, combo))
            spin.valueChanged.connect(lambda value, key=field: self._pose_changed(key, value))
            combo.currentIndexChanged.connect(lambda _index, key=field: self._pose_unit_changed(key))
            self.pose_widgets[field] = spin
            self.pose_unit_widgets[field] = combo
        controls_layout.addWidget(self.camera_box)
        convention = QLabel(
            "Robot space: +X forward, +Y left, +Z up.\n"
            "Positive yaw turns left. Positive pitch tilts up for Limelight and down for Quest.\n"
            "Roll rotates about the camera's forward axis.\n"
            "If a Limelight UI labels an offset Right, use -Y."
        )
        convention.setWordWrap(True)
        controls_layout.addWidget(convention)
        docs = QLabel(
            '<a href="https://docs.limelightvision.io/docs/docs-limelight/pipeline-apriltag/'
            'apriltag-robot-localization-megatag2#configuring-your-limelights-robot-space-pose">'
            "Limelight robot-space pose documentation</a>"
        )
        docs.setOpenExternalLinks(True)
        controls_layout.addWidget(docs)
        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        self.validation_label.setStyleSheet("color: #e5a34a;")
        controls_layout.addWidget(self.validation_label)
        self.generate_button = QPushButton("Generate Camera C++")
        controls_layout.addWidget(self.generate_button)
        controls_layout.addStretch()

        preview_pane = QWidget()
        preview_layout = QVBoxLayout(preview_pane)
        view_buttons = QHBoxLayout()
        for label, azimuth, elevation in (
            ("Reset 3D", -55.0, 28.0), ("Top", 0.0, 89.9),
            ("Front", 0.0, 0.0), ("Left", 90.0, 0.0),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, a=azimuth, e=elevation: self.preview.set_view(a, e))
            view_buttons.addWidget(button)
        preview_layout.addLayout(view_buttons)
        self.preview = CameraPreview()
        preview_layout.addWidget(self.preview, 1)
        splitter.addWidget(preview_pane)
        splitter.setSizes([380, 750])
        splitter.setChildrenCollapsible(False)

        self.robot_combo.currentIndexChanged.connect(self._robot_changed)
        self.robot_length.valueChanged.connect(lambda value: self._dimension_changed("robot_length_in", value))
        self.robot_width.valueChanged.connect(lambda value: self._dimension_changed("robot_width_in", value))
        self.add_limelight_button.clicked.connect(lambda: self.add_camera("Limelight"))
        self.add_quest_button.clicked.connect(lambda: self.add_camera("Quest"))
        self.remove_button.clicked.connect(self.remove_camera)
        self.camera_list.currentRowChanged.connect(self._camera_changed)
        self.name_edit.textChanged.connect(lambda value: self._set_camera_value("name", value))
        self.generate_button.clicked.connect(self.generate_cameras)
        self.refresh_robots()

    @staticmethod
    def _spin():
        spin = QDoubleSpinBox()
        spin.setKeyboardTracking(False)
        spin.setDecimals(DECIMAL_PLACES)
        spin.setRange(-10000, 10000)
        return spin

    @staticmethod
    def _unit_combo(field):
        combo = QComboBox()
        if field in ANGLE_FIELDS:
            for unit, label in zip(ANGLE_UNITS, ("deg", "rad")):
                combo.addItem(label, unit)
        else:
            for unit, label in zip(LENGTH_UNITS, ("in", "m")):
                combo.addItem(label, unit)
        combo.setToolTip("Unit used for display and for the generated C++ literal.")
        return combo

    @staticmethod
    def _with_unit(spin, combo):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(spin, 1)
        layout.addWidget(combo)
        return row

    @staticmethod
    def _show_value(spin, combo, unit, stored, minimum, maximum):
        factor = UNIT_FACTORS[unit]
        combo.setCurrentIndex(combo.findData(unit))
        spin.setRange(minimum * factor, maximum * factor)
        spin.setSingleStep(factor)
        spin.setValue(stored * factor)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_robots()

    def refresh_robots(self):
        selected = self.robot_combo.currentData()
        self.robot_combo.blockSignals(True)
        self.robot_combo.clear()
        for robot_id, robot in self.model.project_data.get("robots", {}).items():
            self.robot_combo.addItem(f"{robot.get('name', robot_id)} ({robot_id})", robot_id)
        index = self.robot_combo.findData(selected)
        self.robot_combo.setCurrentIndex(max(0, index) if self.robot_combo.count() else -1)
        self.robot_combo.blockSignals(False)
        self._robot_changed()

    def _robot_changed(self):
        robot = self.model.project_data.get("robots", {}).get(self.robot_combo.currentData())
        self.config = robot.get("camera_config", default_camera_config()) if robot is not None else None
        self._valid_config = True
        if robot is not None:
            try:
                validate_camera_config(self.config, structural_only=True)
            except ValueError as error:
                self._valid_config = False
                self.validation_label.setText(f"Invalid saved camera configuration: {error}\nCorrect the project JSON and reload.")
        self.controls.setEnabled(robot is not None and self._valid_config)
        self._loading = True
        self.camera_list.clear()
        if self.config is not None and self._valid_config:
            for camera in self.config["cameras"]:
                self.camera_list.addItem(f"{camera['name']} ({camera['type']})")
            self._load_dimensions()
        self._loading = False
        self.camera_list.setCurrentRow(0 if self.camera_list.count() else -1)
        self._camera_changed()
        if self._valid_config:
            self._validate()
        self.preview.set_config(self.config if self._valid_config else None, self.camera_list.currentRow())

    def _commit(self):
        if self.config is not None:
            robot = self.model.project_data["robots"][self.robot_combo.currentData()]
            robot["camera_config"] = self.config
            self._validate()
            self.preview.set_config(self.config, self.camera_list.currentRow())

    def _validate(self):
        if self.config is None:
            self.validation_label.setText("Add a robot in Mechanism Generator to configure its cameras.")
            return
        try:
            validate_camera_config(self.config)
        except ValueError as error:
            self.validation_label.setText(str(error))
            self.generate_button.setEnabled(False)
        else:
            self.validation_label.setText("")
            self.generate_button.setEnabled(True)
        cameras = self.config["cameras"]
        self.add_quest_button.setEnabled(not any(c["type"] == "Quest" for c in cameras))
        self.add_limelight_button.setEnabled(sum(c["type"] == "Limelight" for c in cameras) < 4)

    def _load_dimensions(self):
        for field in DIMENSION_FIELDS:
            self._show_value(
                self.dimension_widgets[field], self.dimension_unit_widgets[field],
                field_unit(self.config, field), self.config[field], 0.001, 10000,
            )

    def _dimension_unit_changed(self, field):
        if self._loading or self.config is None:
            return
        self.config.setdefault("dimension_units", {})[field] = self.dimension_unit_widgets[field].currentData()
        self._loading = True
        self._load_dimensions()
        self._loading = False
        self._commit()

    def _dimension_changed(self, field, value):
        if not self._loading and self.config is not None:
            self.config[field] = value / UNIT_FACTORS[field_unit(self.config, field)]
            self._commit()

    def selected_camera(self):
        index = self.camera_list.currentRow()
        if self._valid_config and self.config is not None and 0 <= index < len(self.config["cameras"]):
            return self.config["cameras"][index]
        return None

    def _camera_changed(self):
        if self._loading:
            return
        camera = self.selected_camera()
        self.camera_box.setEnabled(camera is not None)
        self.remove_button.setEnabled(camera is not None)
        self._loading = True
        self.name_edit.setText(camera["name"] if camera else "")
        is_limelight = camera is not None and camera["type"] == "Limelight"
        for field, combo in self.option_widgets.items():
            combo.setVisible(is_limelight)
            self.camera_form.labelForField(combo).setVisible(is_limelight)
            if is_limelight:
                combo.setCurrentIndex(combo.findText(camera[field]))
        for field, spin in self.pose_widgets.items():
            limit = 36000 if field in ANGLE_FIELDS else 10000
            unit = field_unit(self.config, field, camera) if camera else self.pose_unit_widgets[field].currentData()
            self._show_value(spin, self.pose_unit_widgets[field], unit, camera[field] if camera else 0.0, -limit, limit)
        self._loading = False
        self.preview.set_config(self.config if self._valid_config else None, self.camera_list.currentRow())

    def _set_camera_value(self, field, value):
        camera = self.selected_camera()
        if self._loading or camera is None:
            return
        camera[field] = value
        if field == "name":
            self.camera_list.currentItem().setText(f"{value} ({camera['type']})")
        self._commit()

    def _pose_changed(self, field, value):
        camera = self.selected_camera()
        if self._loading or camera is None:
            return
        self._set_camera_value(field, value / UNIT_FACTORS[field_unit(self.config, field, camera)])

    def _pose_unit_changed(self, field):
        camera = self.selected_camera()
        if self._loading or camera is None:
            return
        camera.setdefault("units", {})[field] = self.pose_unit_widgets[field].currentData()
        self._camera_changed()
        self._commit()

    def add_camera(self, kind):
        if self.config is None:
            return
        try:
            camera = new_camera(kind, self.config["cameras"])
        except ValueError as error:
            QMessageBox.warning(self, "Cannot add camera", str(error))
            return
        self.config["cameras"].append(camera)
        self.camera_list.addItem(f"{camera['name']} ({kind})")
        self.camera_list.setCurrentRow(len(self.config["cameras"]) - 1)
        self._commit()

    def remove_camera(self):
        index = self.camera_list.currentRow()
        if self.selected_camera() is None:
            return
        del self.config["cameras"][index]
        self._loading = True
        self.camera_list.takeItem(index)
        self._loading = False
        self._camera_changed()
        self._commit()

    def generate_cameras(self):
        self.commit_edits()
        if self.config is None:
            QMessageBox.warning(self, "Camera Creator", "Select a robot first.")
            return
        self._commit()
        try:
            generator = DragonCodeGenerator(version=VERSION)
            written = generator.generate_camera_configs(self.model.project_data)
        except (ValueError, OSError, TemplateError) as error:
            QMessageBox.critical(self, "Camera generation failed", str(error))
            return
        QMessageBox.information(
            self, "Camera C++ generated",
            f"Generated {len(written)} camera files in:\n"
            f"{os.path.abspath(generator.output_dir)}\n\n"
            "Use the Mechanism Generator to generate the matching RobotIdentifier.h.\n"
            "Copy the generated vision definitions into your robot project. "
            "The generated CameraConfigMgr replaces its robot-to-camera mappings.\n"
            "Save Project to retain these settings."
        )

    def commit_edits(self):
        if self.config is not None and self._valid_config:
            for spin in (self.robot_length, self.robot_width, *self.pose_widgets.values()):
                spin.interpretText()
