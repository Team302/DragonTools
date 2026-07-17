"""Top-level Dragon Tool Suite shell.

`DragonSuiteWindow` is the application's main window. It hosts each individual
tool in its own tab so the suite can grow over time (Mechanism Generator, Auton
Builder, and future tools) without any one tool needing to know about the others.

Each tool is a self-contained widget. The Mechanism Generator keeps its own menu
bar and status bar (it is a `QMainWindow`), so embedding it as a tab preserves all
of its existing behavior. New tools can follow the same pattern.
"""

from PyQt6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
)

from .window import MechanismEditorWindow
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

        # --- Tab 2: Auton Builder (blank placeholder for the next tool) ---
        self.auton_builder = QWidget()
        self.tabs.addTab(self.auton_builder, "Auton Builder")

        # Restore the tab the user was last on, then persist future changes.
        # Settings live in the Mechanism Generator's model (tool_settings.json),
        # which is already loaded by the time its window is constructed.
        self._settings = self.mechanism_generator.model
        last_tab = self._settings.app_settings.get("last_tab", 0)
        if 0 <= last_tab < self.tabs.count():
            self.tabs.setCurrentIndex(last_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index):
        """Remember the active tab so the suite reopens to it next launch."""
        self._settings.set_app_setting("last_tab", index)

