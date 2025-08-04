# modules/flow2d/flow2d_widget.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class Flow2DWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Este es el módulo Flow 2D. Aquí irá tu lógica."))
        self.setLayout(layout)
