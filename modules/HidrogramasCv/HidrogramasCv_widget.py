"""Widget principal para la generación de hidrogramas con Cv en la interfaz de My Friend TGI."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel # type: ignore
class HidrogramasCvWidget(QWidget):
    """Interfaz gráfica para el módulo Flow 2D de My Friend TGI."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Este es el módulo Flow 2D. Aquí irá tu lógica."))
        self.setLayout(layout)
