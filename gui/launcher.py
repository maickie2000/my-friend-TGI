import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton
from PyQt6 import uic
from modules.excel.gui_excel_tool import ExcelTool
import os

# ⚠️ Agregamos una variable global para mantener la ventana del módulo
ventana_modulo_excel = None

def iniciar_aplicacion():
    app = QApplication(sys.argv)

    ruta_ui = os.path.join(os.path.dirname(__file__), "launcher.ui")
    ventana = uic.loadUi(ruta_ui)

    ventana.setWindowTitle("My Friend TGI - Menú Principal")
    
    # Conectar botón del launcher
    ventana.btn_excel.clicked.connect(mostrar_modulo_excel)

    ventana.show()
    sys.exit(app.exec())

def mostrar_modulo_excel():
    global ventana_modulo_excel
    if ventana_modulo_excel is None or not ventana_modulo_excel.isVisible():
        ventana_modulo_excel = ExcelTool()
        ventana_modulo_excel.show()
    else:
        ventana_modulo_excel.raise_()
        ventana_modulo_excel.activateWindow()
