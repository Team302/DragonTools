"""Entry point for the Dragon Code Generator V2 GUI."""

import sys
from PyQt6.QtWidgets import QApplication
from gui.suite import DragonSuiteWindow


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DragonSuiteWindow()
    window.show()
    sys.exit(app.exec())
