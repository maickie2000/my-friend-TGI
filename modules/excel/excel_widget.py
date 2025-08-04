"""Módulo que contiene la interfaz de usuario para el procesamiento de archivos Excel."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox #pylint: disable=no-name-in-module

class ExcelWidget(QWidget):
    """Interfaz gráfica para el módulo Excel de My Friend TGI."""
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """Interfaz gráfica para el módulo Excel de My Friend TGI."""
        layout = QVBoxLayout()

        self.label = QLabel("Módulo de procesamiento Excel")
        layout.addWidget(self.label)

        self.load_button = QPushButton("Cargar archivo Excel")
        self.load_button.clicked.connect(self.cargar_excel)
        layout.addWidget(self.load_button)

        self.setLayout(layout)

    def cargar_excel(self):
        """Funcion para cargar la data y ruta de un archivo excel"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo Excel", "", "Excel Files (*.xlsx *.xls)") # pylint: disable=line-too-long
        if file_path:
            # Aquí iría tu lógica de procesamiento real
            QMessageBox.information(self, "Archivo cargado", f"Se ha cargado:\n{file_path}")
        else:
            QMessageBox.warning(self, "Sin selección", "No se seleccionó ningún archivo.")
