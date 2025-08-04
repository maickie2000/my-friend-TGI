from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6 import uic
import os

class ExcelTool(QWidget):
    def __init__(self):
        super().__init__()
        ruta_ui = os.path.join(os.path.dirname(__file__), "gui_excel_tool.ui")
        uic.loadUi(ruta_ui, self)
        self.setWindowTitle("Módulo Excel - My Friend TGI")


