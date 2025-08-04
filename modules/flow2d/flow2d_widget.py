"""Widget principal para el módulo Flow 2D en la interfaz de My Friend TGI."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel #pylint: disable=no-name-in-module
class Flow2DWidget(QWidget):
    """Interfaz gráfica para el módulo Flow 2D de My Friend TGI."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Este es el módulo Flow 2D. Aquí irá tu lógica."))
        self.setLayout(layout)
