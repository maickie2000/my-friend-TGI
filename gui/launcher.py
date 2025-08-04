"""Base principal donde se ensamblan los módulos"""
from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QFileDialog, QMessageBox )#pylint: disable=no-name-in-module
#Importacion de modulos
from modules.excel.excel_widget import ExcelWidget
from modules.flow2d.flow2d_widget import Flow2DWidget
class Launcher(QMainWindow):
    """Ventana principal del programa My Friend TGI, organizada con pestañas para módulos."""
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

        #Agregando barra de menú
        self.init_menu_bar()

    def init_menu_bar(self):
        """Barra de menu"""
        menu_bar = self.menuBar()
        # Menú Archivo
        archivo_menu = menu_bar.addMenu("Archivo")

        abrir_action = archivo_menu.addAction("Abrir...")
        abrir_action.triggered.connect(self.abrir_archivo)

        salir_action = archivo_menu.addAction("Salir")
        salir_action.triggered.connect(self.close)

        # Menú Ayuda
        ayuda_menu = menu_bar.addMenu("Ayuda")

        acerca_action = ayuda_menu.addAction("Acerca de...")
        acerca_action.triggered.connect(self.mostrar_acerca_de)

    def abrir_archivo(self):
        """Generacion de la opción abrir archivo"""
        archivo, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo", "", "Todos los archivos (*.*)"
        )
        if archivo:
            QMessageBox.information(self, "Archivo seleccionado", archivo)

    def mostrar_acerca_de(self):
        """Generacion de información"""
        QMessageBox.information(
            self,
            "Acerca de",
            "My Friend TGI v1.1\n\nPrograma modular para procesamiento de datos técnicos\nDesarrollado por MM \nSupervisado por: JB" # pylint: disable=line-too-long
        )
