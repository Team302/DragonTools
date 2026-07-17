"""Entry point for the Dragon Code Generator V2 GUI."""

import sys
from PyQt6.QtWidgets import QApplication
from gui.window import MechanismEditorWindow


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MechanismEditorWindow()
    window.show()
    sys.exit(app.exec())
