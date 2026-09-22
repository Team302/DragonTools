import os
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QLabel,
    QLineEdit,
    QFormLayout,
    QMessageBox,
    QInputDialog,
    QFileDialog,
    QMenuBar,
    QMenu,
    QScrollArea,
    QFrame,
    QCheckBox,
    QComboBox,
    QDialog, 
    QDialogButtonBox, 
    QSpinBox,
    QSplitter,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator, QAction
from generation import DragonCodeGenerator
from .model import ProjectModel
from .constants import VERSION, ENUM_FIELDS, UNIT_OPTIONS


class AddRobotDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Robot Configuration")
        self.setStyleSheet("QDialog { background-color: #2D2D30; color: white; } QLabel { color: white; font-weight: bold; }")
        
        layout = QFormLayout(self)
        
        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("e.g., Comp Bot or CompBot")
        self.name_input.setStyleSheet("background-color: #1E1E1E; border: 1px solid #555; color: white; padding: 5px; border-radius: 3px;")
        
        self.team_input = QSpinBox(self)
        self.team_input.setRange(1, 9999)
        self.team_input.setValue(302) 
        self.team_input.setStyleSheet("background-color: #1E1E1E; border: 1px solid #555; color: white; padding: 5px; border-radius: 3px;")
        
        layout.addRow("Robot Name:", self.name_input)
        layout.addRow("Team Number:", self.team_input)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.setStyleSheet("QPushButton { background-color: #005A9C; color: white; padding: 5px 15px; border-radius: 3px; font-weight: bold; }")
        
        layout.addWidget(self.buttons)

    def get_robot_id(self):
        name = self.name_input.text().strip()
        team = self.team_input.value()
        if not name:
            return None
        
        formatted_name = name.replace(" ", "_").upper()
        return f"{formatted_name}_{team}"

    def get_robot_data(self):
        """Return (robot_id, name, team_number) from the dialog inputs, or None if invalid."""
        name = self.name_input.text().strip()
        team = self.team_input.value()
        if not name:
            return None
        return self.get_robot_id(), name, team


class MechanismEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dragon Code Generator V2 " f"- {VERSION}") 
        self.resize(1200, 800)

        # Qt-free data layer: owns project_data, settings, and all mutations.
        self.model = ProjectModel()
        self.current_selection = None
        self.current_mech_data = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- LEFT PANE (Tree & Actions) ---
        left_pane = QVBoxLayout()

        btn_layout = QHBoxLayout()
        self.btn_add_robot = QPushButton("+ Add Robot")
        self.btn_add_robot.clicked.connect(self.add_robot)
        self.btn_add_mech = QPushButton("+ Add Mechanism")
        self.btn_add_mech.clicked.connect(self.add_mechanism)
        btn_layout.addWidget(self.btn_add_robot)
        btn_layout.addWidget(self.btn_add_mech)
        left_pane.addLayout(btn_layout)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Project Explorer")
        self.tree.itemClicked.connect(self.on_tree_click)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)
        left_pane.addWidget(self.tree)

        self.btn_generate = QPushButton("Generate C++ Code")
        self.btn_generate.setStyleSheet(
            "background-color: #005A9C; color: white; font-weight: bold; padding: 12px; font-size: 14px; border-radius: 4px;"
        )
        self.btn_generate.clicked.connect(self.trigger_generation)
        left_pane.addWidget(self.btn_generate)

        left_widget = QWidget()
        left_widget.setLayout(left_pane)

        # --- RIGHT PANE (Contextual Editor) ---
        self.right_pane_scroll = QScrollArea()
        self.right_pane_scroll.setWidgetResizable(True)
        self.right_pane_scroll.setStyleSheet("QScrollArea { border: none; }")

        self.right_pane = QWidget()
        self.editor_layout = QVBoxLayout(self.right_pane)
        self.lbl_editor_title = QLabel("Select an item from the tree...")
        self.lbl_editor_title.setStyleSheet(
            "font-size: 18px; font-weight: bold; border-bottom: 2px solid #555; padding-bottom: 5px; color: #E0E0E0;"
        )
        self.editor_layout.addWidget(self.lbl_editor_title)
        self.editor_layout.addStretch()

        self.right_pane_scroll.setWidget(self.right_pane)

        # --- RESIZABLE SPLITTER (drag the divider to resize the panes) ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(self.right_pane_scroll)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([400, 800])
        splitter.setChildrenCollapsible(False)
        main_layout.addWidget(splitter)

        # Startup File Loading Logic
        self.model.load_app_settings()
        last_path = self.model.app_settings.get("last_project_path", "")

        if last_path and os.path.exists(last_path):
            try:
                self.model.load_project(last_path)
                self.setWindowTitle(f"Team 302 Mechanism Builder - {os.path.basename(last_path)}")
            except Exception as e:
                print(f"Failed to load last project: {e}")
                self.model.new_project()

        self.populate_tree()

    # --- DATA MODEL PROXIES ---
    @property
    def project_data(self):
        return self.model.project_data

    @property
    def app_settings(self):
        return self.model.app_settings

    @property
    def current_project_path(self):
        return self.model.current_project_path

    # --- SETTINGS / FILE I/O ---
    def new_project(self):
        self.model.new_project()
        self.setWindowTitle("Team 302 Mechanism Builder - Unsaved Project")
        self.populate_tree()
        self.clear_editor()
        self.lbl_editor_title.setText("New Project Created.")

    def load_project(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "JSON Files (*.json)"
        )
        if fname:
            self.load_project_from_path(fname)

    def load_project_from_path(self, path):
        """Load a project JSON from ``path`` and refresh the tree/editor.

        Shared by this window's File > Load and the suite shell's Load action so
        the Mechanism Generator view always refreshes after a load.
        """
        self.model.load_project(path)
        self.model.update_app_settings(path)
        self.setWindowTitle(f"Team 302 Mechanism Builder - {os.path.basename(path)}")
        self.populate_tree()
        self.clear_editor()
        self.lbl_editor_title.setText(f"Loaded: {os.path.basename(path)}")

    def save_project(self):
        if self.current_project_path and os.path.exists(self.current_project_path):
            # Overwrite silently if we already have a path
            self.model.save_project(self.current_project_path)
            self.statusBar().showMessage(f"Saved: {os.path.basename(self.current_project_path)}", 3000)
        else:
            # If no path is established, act like "Save As"
            self.save_project_as()

    def save_project_as(self):
        fname, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "FRC_Project.json", "JSON Files (*.json)"
        )
        if fname:
            self.model.save_project(fname)
            self.model.update_app_settings(fname)
            self.setWindowTitle(f"Team 302 Mechanism Builder - {os.path.basename(fname)}")
            self.statusBar().showMessage("Project saved successfully!", 3000)

    # --- TREE MANAGEMENT ---
    def add_robot(self):
        dialog = AddRobotDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.get_robot_data()

            if result:
                robot_id, name, team_number = result
                if self.model.add_robot(robot_id, name, team_number):
                    self.populate_tree(select_data={"type": "robot", "robot": robot_id})
                else:
                    QMessageBox.warning(self, "Warning", f"Configuration for {robot_id} already exists!")
            else:
                QMessageBox.warning(self, "Warning", "Robot Name cannot be empty!")

    def add_mechanism(self):
        if not self.project_data["robots"]:
            return
        robot_id, ok1 = QInputDialog.getItem(
            self,
            "Select Robot",
            "Add mechanism to:",
            list(self.project_data["robots"].keys()),
            0,
            False,
        )
        if ok1 and robot_id:
            mech_name, ok2 = QInputDialog.getText(
                self, "Add Mechanism", "Mechanism Name:"
            )
            if ok2 and mech_name:
                self.model.add_mechanism(robot_id, mech_name.strip())
                self.populate_tree(select_data={"type": "mechanism", "robot": robot_id, "name": mech_name.strip()})

    def populate_tree(self, select_data=None):
        self.tree.clear()
        item_to_select = None

        for robot_id, robot_data in self.project_data["robots"].items():
            robot_node = QTreeWidgetItem(self.tree, [robot_id])
            robot_node_data = {"type": "robot", "robot": robot_id}
            robot_node.setData(0, 256, robot_node_data)
            if select_data and robot_node_data == select_data:
                item_to_select = robot_node

            for mech_name, mech_data in robot_data.get("mechanisms", {}).items():
                mech_node = QTreeWidgetItem(robot_node, [mech_name])
                mech_node_data = {"type": "mechanism", "robot": robot_id, "name": mech_name}
                mech_node.setData(0, 256, mech_node_data)
                if select_data and mech_node_data == select_data:
                    item_to_select = mech_node

                # --- The Deep Hierarchy Folders ---
                hw_folder = QTreeWidgetItem(mech_node, ["Hardware"])
                hw_folder.setData(
                    0,
                    256,
                    {"type": "folder_hardware", "robot": robot_id, "mech": mech_name},
                )
                for i, hw in enumerate(mech_data.get("hardware", [])):
                    item_node = QTreeWidgetItem(
                        hw_folder, [f"{hw['name']} ({hw['type']})"]
                    )
                    hw_item_data = {
                        "type": "item_hardware",
                        "robot": robot_id,
                        "mech": mech_name,
                        "index": i,
                    }
                    item_node.setData(0, 256, hw_item_data)
                    if select_data and hw_item_data == select_data:
                        item_to_select = item_node

                cd_folder = QTreeWidgetItem(mech_node, ["Control Data"])
                cd_folder.setData(
                    0, 256, {"type": "folder_cd", "robot": robot_id, "mech": mech_name}
                )
                for i, cd in enumerate(mech_data.get("control_data", [])):
                    item_node = QTreeWidgetItem(
                        cd_folder, [cd.get("name", "Unnamed CD")]
                    )
                    cd_item_data = {
                        "type": "item_cd",
                        "robot": robot_id,
                        "mech": mech_name,
                        "index": i,
                    }
                    item_node.setData(0, 256, cd_item_data)
                    if select_data and cd_item_data == select_data:
                        item_to_select = item_node

                st_folder = QTreeWidgetItem(mech_node, ["States / Commands"])
                st_folder.setData(
                    0,
                    256,
                    {"type": "folder_state", "robot": robot_id, "mech": mech_name},
                )
                for i, st in enumerate(mech_data.get("states", [])):
                    state_label = st["name"] if isinstance(st, dict) else st
                    item_node = QTreeWidgetItem(st_folder, [state_label])
                    st_item_data = {
                        "type": "item_state",
                        "robot": robot_id,
                        "mech": mech_name,
                        "index": i,
                    }
                    item_node.setData(0, 256, st_item_data)
                    if select_data and st_item_data == select_data:
                        item_to_select = item_node

        self.tree.expandAll()

        if item_to_select:
            self.tree.setCurrentItem(item_to_select)
            self.tree.scrollToItem(item_to_select)
            self.on_tree_click(item_to_select, 0)

    def open_context_menu(self, position):
        item = self.tree.itemAt(position)
        if item:
            data = item.data(0, 256)
            menu = QMenu()
            delete_action = menu.addAction("Delete Selected Node")
            action = menu.exec(self.tree.viewport().mapToGlobal(position))

            if action == delete_action:
                self.handle_deletion(data)

    def handle_deletion(self, data):
        self.model.delete_node(data)
        self.populate_tree()
        self.clear_editor()

    # --- EDITOR RENDERING ---
    def clear_editor(self):
        for i in reversed(range(self.editor_layout.count())):
            widget = self.editor_layout.itemAt(i).widget()
            layout = self.editor_layout.itemAt(i).layout()
            if widget and widget != self.lbl_editor_title:
                widget.setParent(None)
            elif layout:
                self.clear_layout(layout)

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
            elif item.layout():
                self.clear_layout(item.layout())

    def on_tree_click(self, item, column):
        data = item.data(0, 256)
        if not data:
            return
        self.current_selection = data
        self.render_editor()

    def render_editor(self):
        self.clear_editor()
        data = self.current_selection
        if not data:
            return

        node_type = data["type"]

        if "folder" in node_type:
            r, m = data["robot"], data["mech"]
            mech_data = self.project_data["robots"][r]["mechanisms"][m]
            self.current_mech_data = mech_data

            if node_type == "folder_hardware":
                folder_name = "Hardware"
            elif node_type == "folder_cd":
                folder_name = "Control Data"
            else:
                folder_name = "States / Commands"

            self.lbl_editor_title.setText(f"{m} > {folder_name}")

            # Dedicated section for the add buttons, then every existing item below.
            self._add_section_header("Add New")
            if node_type == "folder_hardware":
                self.render_add_hardware_menu(mech_data)
                self.render_all_hardware(mech_data)
            elif node_type == "folder_cd":
                self.render_add_control_data_menu(mech_data)
                self.render_all_control_data(mech_data)
            elif node_type == "folder_state":
                self.render_add_state_menu(mech_data)
                self.render_all_states(mech_data)

        elif "item" in node_type:
            r, m, idx = data["robot"], data["mech"], data["index"]
            mech_data = self.project_data["robots"][r]["mechanisms"][m]

            if node_type == "item_hardware":
                item_data = mech_data["hardware"][idx]
                self.lbl_editor_title.setText(f"Hardware > {item_data['name']}")
                self._current_hw_type = item_data.get("type")
                self.render_dictionary_editor(item_data)

            elif node_type == "item_cd":
                item_data = mech_data["control_data"][idx]
                self.lbl_editor_title.setText(
                    f"Control Data > {item_data.get('name', 'Unnamed')}"
                )
                self.render_dictionary_editor(item_data)

            elif node_type == "item_state":
                self.current_mech_data = mech_data
                state_data = mech_data["states"][idx]
                state_name = state_data["name"] if isinstance(state_data, dict) else state_data
                self.lbl_editor_title.setText(f"State > {state_name}")
                if isinstance(state_data, dict):
                    self.render_state_editor(state_data, mech_data)
                else:
                    txt = QLineEdit(state_name)
                    txt.setStyleSheet(
                        "background-color: #1E1E1E; border: 1px solid #555; color: white; padding: 5px;"
                    )
                    txt.textChanged.connect(
                        lambda text, d=mech_data["states"], i=idx: self.update_list_string(
                            d, i, text
                        )
                    )
                    self.editor_layout.addWidget(txt)

        self.editor_layout.addStretch()

    # --- SUB-MENUS ---
    def render_add_hardware_menu(self, mech_data):
        hw_btns = QHBoxLayout()
        btn_talon_fx = QPushButton("+ TalonFX")
        btn_talon_fxs = QPushButton("+ TalonFXS")
        btn_coder = QPushButton("+ CANCoder")
        btn_candi = QPushButton("+ CANdi")
        btn_solenoid = QPushButton("+ Solenoid")
        btn_dio = QPushButton("+ Digital Input")

        btn_talon_fx.clicked.connect(lambda: self.add_hardware(mech_data, "TalonFX"))
        btn_talon_fxs.clicked.connect(lambda: self.add_hardware(mech_data, "TalonFXS"))
        btn_coder.clicked.connect(lambda: self.add_hardware(mech_data, "CANCoder"))
        btn_candi.clicked.connect(lambda: self.add_hardware(mech_data, "CANdi"))
        btn_solenoid.clicked.connect(lambda: self.add_hardware(mech_data, "Solenoid"))
        btn_dio.clicked.connect(lambda: self.add_hardware(mech_data, "DigitalInput"))

        hw_btns.addWidget(btn_talon_fx)
        hw_btns.addWidget(btn_talon_fxs)
        hw_btns.addWidget(btn_coder)
        hw_btns.addWidget(btn_candi)
        hw_btns.addWidget(btn_solenoid)
        hw_btns.addWidget(btn_dio)
        self.editor_layout.addLayout(hw_btns)

    def render_add_control_data_menu(self, mech_data):
        btn_cd = QPushButton("+ Add Control Data Block")
        btn_cd.clicked.connect(lambda: self.add_control_data(mech_data))
        self.editor_layout.addWidget(btn_cd)

    def render_add_state_menu(self, mech_data):
        btn_st = QPushButton("+ Add State")
        btn_st.clicked.connect(lambda: self.add_state(mech_data))
        self.editor_layout.addWidget(btn_st)

    # --- FOLDER SECTION HELPERS ---
    def _add_section_header(self, text):
        """Add a bold section heading (e.g. "Add New") to the editor pane."""
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #E0E0E0; font-weight: bold; font-size: 15px; margin-top: 8px;"
        )
        self.editor_layout.addWidget(lbl)

    def _add_item_header(self, text):
        """Add an accented heading naming a single item shown in a folder view."""
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #4FC3F7; font-weight: bold; font-size: 14px; "
            "border-bottom: 1px solid #444; padding: 6px 0 2px 0; margin-top: 12px;"
        )
        self.editor_layout.addWidget(lbl)

    def render_all_hardware(self, mech_data):
        """Render every hardware item's editor inline under the Hardware folder."""
        hardware = mech_data.get("hardware", [])
        if hardware:
            self._add_section_header("Hardware")
        for hw in hardware:
            self._add_item_header(f"{hw.get('name', '')} ({hw.get('type', '')})")
            self._current_hw_type = hw.get("type")
            self.render_dictionary_editor(hw)

    def render_all_control_data(self, mech_data):
        """Render every control-data block's editor inline under the Control Data folder."""
        control_data = mech_data.get("control_data", [])
        if control_data:
            self._add_section_header("Control Data")
        for cd in control_data:
            self._add_item_header(cd.get("name", "Unnamed"))
            self.render_dictionary_editor(cd)

    def render_all_states(self, mech_data):
        """Render every state's editor inline under the States / Commands folder."""
        states = mech_data.get("states", [])
        if states:
            self._add_section_header("States / Commands")
        for idx, st in enumerate(states):
            if isinstance(st, dict):
                self._add_item_header(st.get("name", ""))
                self.render_state_editor(st, mech_data)
            else:
                self._add_item_header(st)
                txt = QLineEdit(st)
                txt.setStyleSheet(
                    "background-color: #1E1E1E; border: 1px solid #555; color: white; padding: 5px;"
                )
                txt.textChanged.connect(
                    lambda text, d=states, i=idx: self.update_list_string(d, i, text)
                )
                self.editor_layout.addWidget(txt)

    # --- STATE EDITOR ---
    def _on_motor_control_data_changed(self, motor_target, cd_name, mech_data):
        """Store the chosen control data on the motor target and copy its unit."""
        motor_target["ControlData"] = cd_name
        motor_target["Unit"] = self.model.control_data_unit(mech_data, cd_name)

    def render_state_editor(self, state_data, mech_data):
        self.model.sync_state_targets(state_data, mech_data)
        cd_names = [cd.get("name", "") for cd in mech_data.get("control_data", [])]

        # --- State name ---
        name_frame = QFrame()
        name_frame.setStyleSheet(
            "QFrame { background-color: #2D2D30; border: 1px solid #444; border-radius: 5px; padding: 10px; }"
        )
        name_form = QFormLayout(name_frame)
        name_edit = QLineEdit(state_data.get("name", ""))
        name_edit.setStyleSheet(
            "background-color: #1E1E1E; border: 1px solid #555; color: white; padding: 3px; border-radius: 2px;"
        )
        name_edit.textChanged.connect(
            lambda text, d=state_data: self.update_dict_and_tree(d, "name", text)
        )
        name_form.addRow("Name:", name_edit)

        # Whether this state is exposed to the Auton Builder (DTD + primitive /
        # zone / snippet dropdowns). Defaults to checked; unchecking excludes it.
        auton_cb = QCheckBox("Auton State (available in Auton Builder)")
        auton_cb.setStyleSheet("color: #E0E0E0;")
        auton_cb.setChecked(state_data.get("auton_state", True))
        auton_cb.toggled.connect(
            lambda checked, d=state_data: d.__setitem__("auton_state", checked)
        )
        name_form.addRow("", auton_cb)
        self.editor_layout.addWidget(name_frame)

        # --- Motor targets (fixed, one per motor) ---
        motor_targets = state_data.get("motor_targets", [])
        if motor_targets:
            motor_frame = QFrame()
            motor_frame.setStyleSheet(
                "QFrame { background-color: #2D2D30; border: 1px solid #444; border-radius: 5px; padding: 10px; }"
            )
            motor_box = QVBoxLayout(motor_frame)
            motor_header = QLabel("Motor Targets")
            motor_header.setStyleSheet("color: #E0E0E0; font-weight: bold; font-size: 14px;")
            motor_box.addWidget(motor_header)

            for mt in motor_targets:
                row_frame = QFrame()
                row_frame.setStyleSheet(
                    "QFrame { background-color: #1F1F22; border: 1px solid #444; border-radius: 4px; padding: 6px; }"
                )
                row = QHBoxLayout(row_frame)

                hw_label = QLabel(mt.get("HardwareName", ""))
                hw_label.setStyleSheet("color: #E0E0E0; font-weight: bold;")
                hw_label.setFixedWidth(140)

                enabled_cb = QCheckBox("Enabled")
                enabled_cb.setChecked(bool(mt.get("Enabled", False)))
                enabled_cb.stateChanged.connect(
                    lambda s, it=mt: it.__setitem__("Enabled", bool(s))
                )

                target_edit = QLineEdit(str(mt.get("TargetValue", 0.0)))
                target_edit.setValidator(QDoubleValidator())
                target_edit.setFixedWidth(100)
                target_edit.setStyleSheet(
                    "background-color: #1E1E1E; border: 1px solid #555; color: white; padding: 3px; border-radius: 2px;"
                )
                target_edit.textChanged.connect(
                    lambda text, it=mt: it.__setitem__(
                        "TargetValue", float(text) if text not in ["", "-", "."] else 0.0
                    )
                )

                cd_combo = QComboBox()
                cd_combo.addItems([""] + cd_names)
                cd_combo.setCurrentText(mt.get("ControlData", ""))
                cd_combo.setStyleSheet(
                    "QComboBox { background-color: #1E1E1E; border: 1px solid #555; color: white; padding: 3px; border-radius: 2px; }"
                )
                cd_combo.currentTextChanged.connect(
                    lambda text, it=mt, md=mech_data: self._on_motor_control_data_changed(it, text, md)
                )

                row.addWidget(hw_label)
                row.addWidget(enabled_cb)
                row.addWidget(QLabel("Value"))
                row.addWidget(target_edit)
                row.addWidget(QLabel("Control Data"))
                row.addWidget(cd_combo)
                row.addStretch()

                motor_box.addWidget(row_frame)

            self.editor_layout.addWidget(motor_frame)

        # --- Solenoid targets (fixed, one per solenoid) ---
        solenoid_targets = state_data.get("solenoid_targets", [])
        if solenoid_targets:
            sol_frame = QFrame()
            sol_frame.setStyleSheet(
                "QFrame { background-color: #2D2D30; border: 1px solid #444; border-radius: 5px; padding: 10px; }"
            )
            sol_box = QVBoxLayout(sol_frame)
            sol_header = QLabel("Solenoid Targets")
            sol_header.setStyleSheet("color: #E0E0E0; font-weight: bold; font-size: 14px;")
            sol_box.addWidget(sol_header)

            for st in solenoid_targets:
                row_frame = QFrame()
                row_frame.setStyleSheet(
                    "QFrame { background-color: #1F1F22; border: 1px solid #444; border-radius: 4px; padding: 6px; }"
                )
                row = QHBoxLayout(row_frame)

                sol_label = QLabel(st.get("SolenoidName", ""))
                sol_label.setStyleSheet("color: #E0E0E0; font-weight: bold;")
                sol_label.setFixedWidth(140)

                enabled_cb = QCheckBox("Enabled")
                enabled_cb.setChecked(bool(st.get("Enabled", False)))
                enabled_cb.stateChanged.connect(
                    lambda s, it=st: it.__setitem__("Enabled", bool(s))
                )

                state_combo = QComboBox()
                state_combo.addItems(["False", "True"])
                state_combo.setCurrentText(str(st.get("State", False)))
                state_combo.setStyleSheet(
                    "QComboBox { background-color: #1E1E1E; border: 1px solid #555; color: white; padding: 3px; border-radius: 2px; }"
                )
                state_combo.currentTextChanged.connect(
                    lambda text, it=st: it.__setitem__("State", text == "True")
                )

                row.addWidget(sol_label)
                row.addWidget(enabled_cb)
                row.addWidget(QLabel("State"))
                row.addWidget(state_combo)

                sol_box.addWidget(row_frame)

            self.editor_layout.addWidget(sol_frame)

    # --- DYNAMIC DICTIONARY RENDERER ---
    def render_dictionary_editor(self, dict_ref):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: #2D2D30; border: 1px solid #444; border-radius: 5px; padding: 10px; }"
        )
        form = QFormLayout(frame)
        self.render_dictionary_fields(form, dict_ref)
        self.editor_layout.addWidget(frame)

    @staticmethod
    def prettify_label(key):
        """Human-readable label for a data key.

        - snake_case is spaced and title-cased: "supply_current_limit" -> "Supply Current Limit"
        - a single lowercase word is capitalized:  "p" -> "P"
        - UpperCamelCase keys are left untouched:   "S1CloseStateValue" -> "S1CloseStateValue"
        """
        text = str(key)
        if "_" in text:
            return " ".join(word[:1].upper() + word[1:] for word in text.split("_"))
        if text.islower():
            return text[:1].upper() + text[1:]
        return text

    def _field_disabled(self, dict_ref, key):
        """Return True when a config field won't be generated, so the GUI can gray it out.

        Feedback / External Feedback: FeedbackRemoteSensorID and RotorToSensorRatio
        only apply when a remote (non-rotor) sensor source is selected.
        Follower: FollowerID only applies when the follower is enabled.
        """
        source = dict_ref.get(
            "FeedbackSensorSourceValue", dict_ref.get("ExternalFeedbackSensorSource")
        )
        if source is not None and key in ("FeedbackRemoteSensorID", "RotorToSensorRatio"):
            return source == "RotorSensor"
        if "FollowerID" in dict_ref and key == "FollowerID":
            return not dict_ref.get("Enabled", False)
        return False

    def _field_controls_graying(self, dict_ref, key):
        """Return True when changing this field toggles graying of sibling fields,
        so its editor should re-render the detail panel live."""
        if key in ("FeedbackSensorSourceValue", "ExternalFeedbackSensorSource"):
            return True
        if key == "Enabled" and "FollowerID" in dict_ref:
            return True
        return False

    def render_dictionary_fields(self, form, dict_ref):
        for key, value in dict_ref.items():
            if key == "type":
                continue

            # Feedback is a TalonFX concept; External Feedback is TalonFXS-only.
            # Show only the block that matches the current hardware type.
            hw_type = getattr(self, "_current_hw_type", None)
            if key == "Feedback" and hw_type == "TalonFXS":
                continue
            if key == "External Feedback" and hw_type == "TalonFX":
                continue

            label_text = self.prettify_label(key) + ":"

            if isinstance(value, dict):
                nested_frame = QFrame()
                nested_frame.setStyleSheet(
                    "QFrame { background-color: #232326; border: 1px solid #555; border-radius: 4px; padding: 8px; }"
                )
                nested_form = QFormLayout(nested_frame)
                self.render_dictionary_fields(nested_form, value)
                form.addRow(label_text, nested_frame)

            elif isinstance(value, list):
                if key == "motor_targets" and not self.model.has_hardware_type(
                    self.current_mech_data, ["TalonFX", "TalonFXS"]
                ):
                    continue
                if key == "solenoid_targets" and not self.model.has_hardware_type(
                    self.current_mech_data, ["Solenoid"]
                ):
                    continue

                list_frame = QFrame()
                list_frame.setStyleSheet(
                    "QFrame { background-color: #232326; border: 1px solid #555; border-radius: 4px; padding: 8px; }"
                )
                vbox = QVBoxLayout(list_frame)
                for idx, item in enumerate(value):
                    item_frame = QFrame()
                    item_frame.setStyleSheet(
                        "QFrame { background-color: #1F1F22; border: 1px solid #444; border-radius: 4px; padding: 6px; }"
                    )
                    item_layout = QVBoxLayout(item_frame)

                    header_layout = QHBoxLayout()
                    header_label = QLabel(f"{self.prettify_label(key)} {idx + 1}")
                    header_label.setStyleSheet("color: #E0E0E0; font-weight: bold;")
                    remove_btn = QPushButton("Remove")
                    remove_btn.setFixedWidth(80)
                    remove_btn.clicked.connect(
                        lambda _, l=value, i=idx: self.remove_list_item(l, i)
                    )
                    header_layout.addWidget(header_label)
                    header_layout.addStretch()
                    header_layout.addWidget(remove_btn)
                    item_layout.addLayout(header_layout)

                    if isinstance(item, dict):
                        if key == "motor_targets":
                            hw_options = [
                                hw["name"]
                                for hw in (self.current_mech_data or {}).get("hardware", [])
                                if hw.get("type") in ["TalonFX", "TalonFXS"]
                            ]

                            fields = QHBoxLayout()

                            hw_combo = QComboBox()
                            hw_combo.addItems(hw_options)
                            current_hw = item.get("HardwareName", "")
                            if current_hw in hw_options:
                                hw_combo.setCurrentText(current_hw)
                            elif hw_options:
                                hw_combo.setCurrentText(hw_options[0])
                                item["HardwareName"] = hw_options[0]

                            hw_combo.currentTextChanged.connect(
                                lambda text, it=item: (it.__setitem__("HardwareName", text), self.populate_tree())
                            )

                            enabled_cb = QCheckBox("Enabled")
                            enabled_cb.setChecked(bool(item.get("Enabled", False)))
                            enabled_cb.stateChanged.connect(
                                lambda s, it=item: (it.__setitem__("Enabled", bool(s)), self.populate_tree())
                            )

                            target_edit = QLineEdit(str(item.get("TargetValue", 0.0)))
                            target_edit.setValidator(QDoubleValidator())
                            target_edit.textChanged.connect(
                                lambda text, it=item: (it.__setitem__("TargetValue", float(text) if text not in ["", "-", "."] else 0.0), self.populate_tree())
                            )

                            unit_combo = QComboBox()
                            unit_combo.addItems(UNIT_OPTIONS)
                            unit_combo.setCurrentText(item.get("Unit", UNIT_OPTIONS[0]))
                            unit_combo.currentTextChanged.connect(
                                lambda text, it=item: (it.__setitem__("Unit", text), self.populate_tree())
                            )

                            fields.addWidget(hw_combo)
                            fields.addWidget(enabled_cb)
                            fields.addWidget(QLabel("Value"))
                            fields.addWidget(target_edit)
                            fields.addWidget(QLabel("Unit"))
                            fields.addWidget(unit_combo)

                            item_layout.addLayout(fields)

                        elif key == "solenoid_targets":
                            hw_options = [
                                hw["name"]
                                for hw in (self.current_mech_data or {}).get("hardware", [])
                                if hw.get("type") == "Solenoid"
                            ]

                            fields = QHBoxLayout()

                            sol_combo = QComboBox()
                            sol_combo.addItems(hw_options)
                            current_sol = item.get("SolenoidName", "")
                            if current_sol in hw_options:
                                sol_combo.setCurrentText(current_sol)
                            elif hw_options:
                                sol_combo.setCurrentText(hw_options[0])
                                item["SolenoidName"] = hw_options[0]

                            sol_combo.currentTextChanged.connect(
                                lambda text, it=item: (it.__setitem__("SolenoidName", text), self.populate_tree())
                            )

                            enabled_cb = QCheckBox("Enabled")
                            enabled_cb.setChecked(bool(item.get("Enabled", False)))
                            enabled_cb.stateChanged.connect(
                                lambda s, it=item: (it.__setitem__("Enabled", bool(s)), self.populate_tree())
                            )

                            state_combo = QComboBox()
                            state_combo.addItems(["False", "True"])
                            state_combo.setCurrentText(str(item.get("State", False)))
                            state_combo.currentTextChanged.connect(
                                lambda text, it=item: (it.__setitem__("State", text == "True"), self.populate_tree())
                            )

                            fields.addWidget(sol_combo)
                            fields.addWidget(enabled_cb)
                            fields.addWidget(QLabel("State"))
                            fields.addWidget(state_combo)

                            item_layout.addLayout(fields)

                        else:
                            item_form = QFormLayout()
                            self.render_dictionary_fields(item_form, item)
                            item_layout.addLayout(item_form)
                    else:
                        value_edit = QLineEdit(str(item))
                        value_edit.setStyleSheet(
                            "background-color: #1E1E1E; border: 1px solid #555; color: white; padding: 3px; border-radius: 2px;"
                        )
                        value_edit.textChanged.connect(
                            lambda text, l=value, i=idx: self.update_list_item(l, i, text)
                        )
                        item_layout.addWidget(value_edit)

                    vbox.addWidget(item_frame)

                add_btn = QPushButton(f"Add {self.prettify_label(key).rstrip('s')}")
                add_btn.clicked.connect(lambda _, l=value, k=key: self.add_list_item(l, k, self.current_mech_data))
                vbox.addWidget(add_btn)
                form.addRow(label_text, list_frame)

            elif isinstance(value, bool):
                cb = QCheckBox()
                cb.setChecked(value)
                if self._field_controls_graying(dict_ref, key):
                    cb.stateChanged.connect(
                        lambda state, k=key, d=dict_ref: (
                            d.__setitem__(k, bool(state)),
                            self.render_editor(),
                        )
                    )
                else:
                    cb.stateChanged.connect(
                        lambda state, k=key, d=dict_ref: self.update_dict_and_tree(
                            d, k, bool(state)
                        )
                    )
                cb.setEnabled(not self._field_disabled(dict_ref, key))
                form.addRow(label_text, cb)

            elif key in ENUM_FIELDS:
                combo = QComboBox()
                options = ENUM_FIELDS[key]
                combo.addItems(options)
                combo.setCurrentText(str(value))
                combo.setStyleSheet(
                    "QComboBox { background-color: #1E1E1E; border: 1px solid #555; color: white; padding: 3px; border-radius: 2px; }"
                )
                if self._field_controls_graying(dict_ref, key):
                    combo.currentTextChanged.connect(
                        lambda text, k=key, d=dict_ref: (
                            d.__setitem__(k, text),
                            self.render_editor(),
                        )
                    )
                else:
                    combo.currentTextChanged.connect(
                        lambda text, k=key, d=dict_ref: self.update_dict_and_tree(d, k, text)
                    )
                combo.setEnabled(not self._field_disabled(dict_ref, key))
                form.addRow(label_text, combo)

            elif isinstance(value, (int, float)):
                txt = QLineEdit(str(value))
                disabled = self._field_disabled(dict_ref, key)
                if disabled:
                    txt.setStyleSheet(
                        "background-color: #2A2A2A; border: 1px dashed #3A3A3A; color: #6A6A6A; padding: 3px; border-radius: 2px;"
                    )
                    txt.setToolTip("Not generated with the current selection")
                else:
                    txt.setStyleSheet(
                        "background-color: #1E1E1E; border: 1px solid #555; color: white; padding: 3px; border-radius: 2px;"
                    )
                txt.textChanged.connect(
                    lambda text, k=key, d=dict_ref, t=type(value): self.update_number(
                        d, k, text, t
                    )
                )
                txt.setEnabled(not disabled)
                form.addRow(label_text, txt)

            else:
                txt = QLineEdit(str(value))
                txt.setStyleSheet(
                    "background-color: #1E1E1E; border: 1px solid #555; color: white; padding: 3px; border-radius: 2px;"
                )
                txt.textChanged.connect(
                    lambda text, k=key, d=dict_ref: self.update_dict_and_tree(
                        d, k, text
                    )
                )
                form.addRow(label_text, txt)

    def update_list_item(self, lst, index, value):
        if 0 <= index < len(lst):
            lst[index] = value
            self.populate_tree()

    def add_list_item(self, lst, key, mech_data=None):
        default_item = self.model.default_list_item(key, mech_data)
        lst.append(default_item)
        self.populate_tree()

    def remove_list_item(self, lst, index):
        if 0 <= index < len(lst):
            lst.pop(index)
            self.populate_tree()

    # --- DATA UPDATERS ---
    def update_dict_and_tree(self, dictionary, key, val):
        dictionary[key] = val
        if key == "name":
            self.populate_tree()

    def update_list_string(self, lst, idx, val):
        lst[idx] = val
        self.populate_tree()

    def update_number(self, dictionary, key, text, val_type):
        try:
            if text.strip() in ["", "-", "."]:
                return
            dictionary[key] = val_type(text)
        except ValueError:
            pass

    # --- ITEM INJECTORS ---
    def add_hardware(self, mech_data, hw_type):
        index = self.model.add_hardware(mech_data, hw_type)
        robot_id, mech_name = self.model.find_mech_location(mech_data)
        select_data = {"type": "item_hardware", "robot": robot_id, "mech": mech_name, "index": index} if robot_id else None
        self.populate_tree(select_data=select_data)

    def add_control_data(self, mech_data):
        index = self.model.add_control_data(mech_data)
        robot_id, mech_name = self.model.find_mech_location(mech_data)
        select_data = {"type": "item_cd", "robot": robot_id, "mech": mech_name, "index": index} if robot_id else None
        self.populate_tree(select_data=select_data)

    def add_state(self, mech_data):
        index = self.model.add_state(mech_data)
        robot_id, mech_name = self.model.find_mech_location(mech_data)
        select_data = {"type": "item_state", "robot": robot_id, "mech": mech_name, "index": index} if robot_id else None
        self.populate_tree(select_data=select_data)

    def trigger_generation(self):
            try:
                print("Starting code generation...") 
                generator = DragonCodeGenerator(version=VERSION) 
                generator.generate(self.project_data)

                # If an auton files folder is selected and contains the DTDs,
                # copy them into deploy/auton/ with the mechanism states injected.
                auton_dir = self.model.app_settings.get("auton_source_path", "")
                dtds = generator.generate_auton_dtds(self.project_data, auton_dir)

                message = "Code generated successfully!"
                if dtds:
                    message += (
                        f"\n\nGenerated {len(dtds)} auton DTD(s) with mechanism "
                        "states into deploy/auton/.\n DON'T FORGET TO UPDATE CyclePrimitives"
                    )
                QMessageBox.information(self, "Success", message)
            except Exception as e:
                print(f"Error: {e}") 
                QMessageBox.critical(self, "Error", f"Failed to generate code:\n{str(e)}")