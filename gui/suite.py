"""Top-level Dragon Tool Suite shell.

`DragonSuiteWindow` is the application's main window. It hosts each individual
tool in its own tab so the suite can grow over time (Mechanism Generator, Auton
Builder, and future tools) without any one tool needing to know about the others.

Each tool is a self-contained widget. The Mechanism Generator keeps its own menu
bar and status bar (it is a `QMainWindow`), so embedding it as a tab preserves all
of its existing behavior. New tools can follow the same pattern.
"""

from PyQt6.QtGui import QActionGroup
from PyQt6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QWidget,
)

from .mechanism_builder import MechanismEditorWindow
from .auton_builder import AutonBuilderWidget
from .constants import VERSION


class DragonSuiteWindow(QMainWindow):
    """The suite shell: a tabbed container holding every Dragon tool."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Dragon Tool Suite - {VERSION}")
        self.resize(1200, 800)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.setCentralWidget(self.tabs)

        # --- Tab 1: Mechanism Generator (the existing tool) ---
        self.mechanism_generator = MechanismEditorWindow()
        self.tabs.addTab(self.mechanism_generator, "Mechanism Generator")

        # --- Tab 2: Auton Builder ---
        self.auton_builder = AutonBuilderWidget(self.mechanism_generator.model)
        self.tabs.addTab(self.auton_builder, "Auton Builder")
        self._setup_suite_menu()

        # Restore the tab the user was last on, then persist future changes.
        # Settings live in the Mechanism Generator's model (tool_settings.json),
        # which is already loaded by the time its window is constructed.
        self._settings = self.mechanism_generator.model
        last_tab = self._settings.app_settings.get("last_tab", 0)
        if 0 <= last_tab < self.tabs.count():
            self.tabs.setCurrentIndex(last_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _setup_suite_menu(self):
        file_menu = self.menuBar().addMenu("File")
        new_action = file_menu.addAction("New Project")
        new_action.triggered.connect(self._new_project)
        load_action = file_menu.addAction("Load Project (JSON)")
        load_action.triggered.connect(self._load_project)
        file_menu.addSeparator()
        save_action = file_menu.addAction("Save Project")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_project)
        save_as_action = file_menu.addAction("Save Project As...")
        save_as_action.triggered.connect(self._save_project_as)

        options_menu = self.menuBar().addMenu("Options")
        select_auton_action = options_menu.addAction("Select Auton Files Folder...")
        select_auton_action.triggered.connect(self.auton_builder.select_auton_folder)
        select_path_action = options_menu.addAction("Select Choreo Path Folder...")
        select_path_action.triggered.connect(self.auton_builder.select_choreo_folder)
        update_field_action = options_menu.addAction("Update Field Drawing")
        update_field_action.triggered.connect(self.auton_builder.refresh_field)

        options_menu.addSeparator()
        view_menu = options_menu.addMenu("Auton Editor View")
        view_group = QActionGroup(self)
        view_group.setExclusive(True)
        inline_action = view_menu.addAction("Inline (full editors)")
        inline_action.setCheckable(True)
        inline_action.triggered.connect(lambda: self.auton_builder.set_view_mode("inline"))
        list_action = view_menu.addAction("List (navigable)")
        list_action.setCheckable(True)
        list_action.triggered.connect(lambda: self.auton_builder.set_view_mode("list"))
        view_group.addAction(inline_action)
        view_group.addAction(list_action)
        inline_action.setChecked(self.auton_builder.view_mode == "inline")
        list_action.setChecked(self.auton_builder.view_mode == "list")

    def _new_project(self):
        self.mechanism_generator.new_project()
        # Auton data is folder-based, independent of the mechanism project, so a
        # new mechanism project just re-reads the current auton files folder.
        self.auton_builder._load_from_source_folder()
        self.auton_builder.refresh_tree()
        self.auton_builder.refresh_field()

    def _load_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "JSON Files (*.json)"
        )
        if not path:
            return
        self.mechanism_generator.model.load_project(path)
        self.mechanism_generator.model.update_app_settings(path)
        self.auton_builder._load_saved_data()
        self.auton_builder.refresh_tree()
        self.auton_builder.refresh_field()

    def _save_project(self):
        if self.auton_builder.save_to_project():
            return
        self.auton_builder.save_to_project_as()

    def _save_project_as(self):
        self.auton_builder.save_to_project_as()

    def _on_tab_changed(self, index):
        """Remember the active tab so the suite reopens to it next launch."""
        self._settings.set_app_setting("last_tab", index)
