#Importacion de librerias
import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QTabWidget
from PyQt6 import uic
#Importacion de modulos
from modules.excel.excel_widget import ExcelWidget
from modules.flow2d.flow2d_widget import Flow2DWidget
class Launcher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My Friend TGI")
        self.setGeometry(100, 100, 1200, 700)

        # Crear contenedor de pestañas
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Agregar pestaña de Excel
        self.excel_tab = ExcelWidget()
        self.tabs.addTab(self.excel_tab, "Excel")

        # Agregar pestaña de Flow 2D
        self.flow2d_tab = Flow2DWidget()
        self.tabs.addTab(self.flow2d_tab, "Flow 2D")