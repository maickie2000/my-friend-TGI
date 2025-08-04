"""Punto de entrada principal de My Friend TGI."""

import sys  # 1. Módulos estándar
from PyQt6.QtWidgets import QApplication  # 2. Librerías externas / pylint: disable=no-name-in-module
from gui.launcher import Launcher  # 3. Módulos internos del proyecto

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Launcher()
    window.show()
    sys.exit(app.exec())
