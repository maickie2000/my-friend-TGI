"""Base principal donde se ensamblan los módulos"""
from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QFileDialog, QMessageBox ) # type: ignore
#Importacion de modulos
from modules.excel.excel_widget import ExcelWidget
from modules.flow2d.flow2d_widget import Flow2DWidget
from modules.HidrogramasCv.HidrogramasCv_widget import HidrogramasCvWidget
from utils.i18n_loader import cargar_traducciones

class Launcher(QMainWindow):
    """Ventana principal del programa My Friend TGI, organizada con pestañas para módulos."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My Friend TGI")
        self.setGeometry(100, 100, 1200, 700)

        # Idioma actual
        self.idioma_actual = "es"
        self.traducciones = cargar_traducciones(self.idioma_actual)
        self.statusBar().showMessage(self.traducciones.get("status_bar_message", "Bienvenido a My Friend TGI"))

        # Configuración de la ventana
        # Crear contenedor de pestañas
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Agregar pestaña de Excel
        self.excel_tab = ExcelWidget()
        self.tabs.addTab(self.excel_tab, "Excel")

        # Agregar pestaña de Flow 2D
        self.flow2d_tab = Flow2DWidget()
        self.tabs.addTab(self.flow2d_tab, "Flow 2D")

        # Agregar pestaña de Hidrogramas Cv
        self.flow2d_tab = HidrogramasCvWidget()
        self.tabs.addTab(self.flow2d_tab, "Hidrogramas Cv")

        #Agregando barra de menú
        #self.init_menu_bar()

        # Menú inicial
        self.build_menu()

    def build_menu(self):
        tr = self.traducciones
        """Barra de menu"""
        menu_bar = self.menuBar()
        menu_bar.clear()

        # Menú Archivo
        archivo_menu = menu_bar.addMenu(tr["file"])

        abrir_action = archivo_menu.addAction(tr["open"])
        abrir_action.triggered.connect(self.abrir_archivo)

        salir_action = archivo_menu.addAction(tr["exit"])
        salir_action.triggered.connect(self.close)
        
        #Menú Preferencias
        preferencias_menu = menu_bar.addMenu(tr["preferences"])

        # Submenú Tema
        tema_menu = preferencias_menu.addMenu("Tema")
        tema_menu.addAction("Claro", self.set_tema_claro)
        tema_menu.addAction("Cálido", self.set_tema_calido)
        tema_menu.addAction("Oscuro", self.set_tema_oscuro)
        tema_menu.addAction("Sistema", self.set_tema_sistema)

        # Submenú Idioma
        idioma_menu = preferencias_menu.addMenu(tr["language"])
        idioma_menu.addAction("Español", lambda: self.cambiar_idioma("es"))
        idioma_menu.addAction("English", lambda: self.cambiar_idioma("en"))

        # Menú Ayuda
        ayuda_menu = menu_bar.addMenu(tr["help"])

        acerca_action = ayuda_menu.addAction(tr["about"])
        acerca_action.triggered.connect(self.mostrar_acerca_de)

    def cambiar_idioma(self, idioma):
        self.idioma_actual = idioma
        self.traducciones = cargar_traducciones(idioma)
        self.build_menu()
        self.statusBar().showMessage(self.traducciones["language_changed"], 3000)

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
            "My Friend TGI v1.1\n" \
            "\nPrograma modular para procesamiento de datos técnicos" \
            "\nDesarrollado por: MM " \
            "\nSupervisado por: JB"
        )

    def set_tema_oscuro(self):
        with open("assets/styles/dark.qss", "r") as f:
            self.setStyleSheet(f.read())
        self.statusBar().showMessage("Tema oscuro activado", 3000)

    def set_tema_claro(self):
        with open("assets/styles/light.qss", "r") as f:
            self.setStyleSheet(f.read())
        self.statusBar().showMessage("Tema claro activado", 3000)
                
    def set_tema_sistema(self):
        self.setStyleSheet("")
        self.statusBar().showMessage("Tema del sistema activado")
    
    def set_tema_calido(self):
        with open("assets/styles/warm.qss", "r") as f:
            self.setStyleSheet(f.read())
        self.statusBar().showMessage("Tema cálido activado", 3000)
