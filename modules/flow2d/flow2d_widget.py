# modules/flow2d/flow2d_widget.py
"""Flow 2D: tabs XSECS, XSECI, XSECH (modo fantasma con prints)."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QToolBar, QFileDialog, QSplitter,
    QPlainTextEdit, QMessageBox, QToolButton, QPushButton, QMenu, QSpinBox,
    QHBoxLayout, QLabel, QComboBox, QTableWidget, QTableWidgetItem, QProgressDialog, QApplication )  # type: ignore
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QStyle   # type: ignore

from PyQt6.QtWidgets import QDialog, QCheckBox

from PyQt6.QtCore import QSize, Qt, QSettings , QObject, QThread, pyqtSignal
from PyQt6.QtGui import QAction  # type: ignore
from PyQt6.QtGui import QKeySequence, QShortcut # type: ignore
from PyQt6.QtGui import QImage, QPixmap, QGuiApplication # type: ignore
# matplotlib embebido
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas  # type: ignore
from matplotlib.figure import Figure  # type: ignore
from matplotlib.colorbar import Colorbar  # type: ignore
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.colorbar import Colorbar
from mpl_toolkits.axes_grid1 import make_axes_locatable

import numpy as np
# modules/flow2d/flow2d_widget.py (añadir)
from PyQt6.QtCore import Qt  # si no lo tenías
from matplotlib.collections import LineCollection  # para “cortina” de velocidad
import matplotlib.ticker as mticker
import time

import os, re, io

from .flow2d_factory import get_parser
from .flow2d_parsers import ParseResult
from .flow2d_pipeline import compute_variables, Flow2DState
from .flow2d_exporters import CSVAllLinesExporter, JSONSummaryExporter
from .flow2d_parsers import XSECIParser, ParseCancelled

# FUNCIONES AUXILIARES
def time_label_to_hours(label: str) -> float:
    """
    Asume formato consistente (lo generó tu _parse_time_label)
     "dddd d hh h mm m ss s
    """
    parts = label.replace("d", " ").replace("h", " ").replace("m", " ").replace("s", " ").split()
    d, h, m, s = map(int, parts)
    return d * 24.0 + h + m / 60.0 + s / 3600.0


## CLASES AUXILIARES

class PlotCanvas(FigureCanvas):
    """
    Lienzo único configurable.
    - use_colorbar=False: layout automático (XSECS).
    - use_colorbar=True : eje de colorbar fijo a la derecha (XSECI).
    """
    def __init__(self, parent=None, use_colorbar: bool = False):
        self.use_colorbar = use_colorbar

        self.fig = Figure(figsize=(5, 4), dpi=100)
        # Layout según necesidad
        if self.use_colorbar:
            self.fig.set_constrained_layout(False)   # lo controlamos manualmente
        else:
            self.fig.set_constrained_layout(True)    # bonito por defecto

        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)

        # Colorbar solo si aplica (XSECI)
        self.cax = None
        self._cbar: Colorbar | None = None
        if self.use_colorbar:
            divider = make_axes_locatable(self.ax)
            self.cax = divider.append_axes("right", size="5%", pad=0.12)
            # ✅ márgenes razonables (no los vuelvas a tocar en otro lado)
            # left/right: deja sitio a colorbar fija; bottom: para xlabel + leyenda
            self.fig.subplots_adjust(left=0.08, right=0.86, top=0.92, bottom=0.34)



    def clear(self):
        """Limpia el eje principal y gestiona el colorbar sin romper la geometría."""
        if self.use_colorbar:
            # colorbar
            if self._cbar is not None:
                try:
                    self._cbar.remove()
                except Exception:
                    pass
                finally:
                    self._cbar = None

            # cax: recrea si fue eliminado, o límpialo si existe
            if self.cax is None or self.cax not in self.fig.axes:
                divider = make_axes_locatable(self.ax)
                self.cax = divider.append_axes("right", size="5%", pad=0.12)
            else:
                try:
                    self.cax.cla()
                except Exception:
                    pass

        # eje principal
        self.ax.clear()
        self.draw_idle()

    def get_or_update_colorbar(self, mappable, label: str | None = None) -> Colorbar | None:
        """Crea/actualiza el colorbar en cax fijo (si use_colorbar=True)."""
        if not self.use_colorbar:
            return None

        # garantiza cax
        if self.cax is None or self.cax not in self.fig.axes:
            divider = make_axes_locatable(self.ax)
            self.cax = divider.append_axes("right", size="5%", pad=0.12)

        if self._cbar is None:
            self._cbar = self.fig.colorbar(mappable, cax=self.cax)
        else:
            self._cbar.update_normal(mappable)

        if label:
            self._cbar.set_label(label)
        return self._cbar
    
         
    def plot_polyline(self, xs, ys, label=None):
        self.ax.plot(xs, ys, linewidth=1.6, alpha=0.95, label=label)

    def finalize(self, show_legend=True):
        try:
            self.ax.set_aspect("equal", adjustable="datalim")
        except Exception:
            pass
        if show_legend:
            self.ax.legend(loc="best", fontsize=8)
        self.draw_idle()

class _BaseSectionTab(QWidget):
    def __init__(self, titulo: str, extension: str):
        super().__init__()
        self.titulo = titulo
        self.extension = extension.upper().lstrip(".")
        self.archivo_actual: str | None = None
        self.result: ParseResult | None = None
        self.state: Flow2DState | None = None
        self.parser = get_parser(self.extension)

        lay = QVBoxLayout(self)
        self.setWindowTitle(f"Flow 2D - {self.titulo}")

        # Toolbar con acciones
        self.toolbar = QToolBar(f"{self.titulo}")
        self.toolbar.setMovable(False)
        self.act_abrir = QAction("Abrir", self)
        self.act_limpiar = QAction("Limpiar", self)

        # Botón de exportación
        self.btn_exportar = QToolButton(self)
        self.btn_exportar.setText("Exportar")
        self.btn_exportar.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.menu_export = QMenu(self)
        self.btn_exportar.setMenu(self.menu_export)

        self.exporters = [CSVAllLinesExporter(), JSONSummaryExporter()]
        for exp in self.exporters:
            act = self.menu_export.addAction(exp.name)
            act.triggered.connect(lambda _, e=exp: self._run_exporter(e))

        self.toolbar.addAction(self.act_abrir)
        self.toolbar.addAction(self.act_limpiar)
        self.toolbar.addWidget(self.btn_exportar)

        # Visor por defecto (texto)
        self.viewer = QPlainTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setPlaceholderText(f"[{self.titulo}] Vista previa (stub)")

        lay.addWidget(self.toolbar)
        lay.addWidget(self.viewer)
        self.setLayout(lay)

        # señales de estado
        self.act_abrir.triggered.connect(self._abrir_archivo)
        self.act_limpiar.triggered.connect(self._limpiar)

    # ---- Acciones de la UI ----
    def _abrir_archivo(self):
        filtro = f"{self.titulo} (*.{self.extension});;Todos (*.*)"
        ruta, _ = QFileDialog.getOpenFileName(self, f"Abrir {self.titulo}", "", filtro)
        if not ruta:
            return
        try:
            print(f"[UI] Abrir {self.titulo}: {ruta}")
            self._cargar_y_mostrar(ruta)
            self.archivo_actual = ruta
            self._status(f"{self.titulo}: cargado {os.path.basename(ruta)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir:\n{e}")

    def _limpiar(self):
        print(f"[UI] Limpiar {self.titulo}")
        self.viewer.clear()
        self.archivo_actual = None
        self.result = None
        self.state = None
        self._status(f"{self.titulo}: limpiado")

    def _run_exporter(self, exporter):
        if not (self.result and self.state):
            QMessageBox.information(self, "Exportar", "No hay datos cargados.")
            return
        ruta, _ = QFileDialog.getSaveFileName(self, f"Guardar {exporter.name}", "", "Todos (*.*)")
        if not ruta:
            return
        print(f"[UI] Exportar {self.titulo} usando {exporter.name} -> {ruta}")
        exporter.export(self.result, self.state, ruta)
        self._status(f"{self.titulo}: exportado ({exporter.name})")

    # ---- Para sobreescribir en tabs concretas si hace falta ----
    def _cargar_y_mostrar(self, ruta: str):
        self.result = self.parser.parse(ruta)               # ← aquí entra tu parse_xsecs real
        self.state = compute_variables(self.result)         # ← variables derivadas
        meta = self.result.meta
        ids = meta.get("ids", [])
        texto = f"[{self.titulo}] META: {meta}\n\nIDs: {ids[:10]}{'...' if len(ids)>10 else ''}"
        self.viewer.setPlainText(texto)

    # ---- Util ----
    def _status(self, msg: str):
        w = self.parent()
        while w is not None:
            if hasattr(w, "statusBar") and callable(w.statusBar):
                try: w.statusBar().showMessage(msg, 3000)
                except Exception: pass
                break
            w = w.parent()


class XSECSSectionTab(_BaseSectionTab):
    """XSECS: añade combo de IDs y tabla de coords por sección."""
    def __init__(self):
        super().__init__("XSECS", "XSECS")

        # Panel superior: label + combo
        top = QWidget(self)
        hl = QHBoxLayout(top)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(QLabel("Sección:"))
        self.cbo_ids = QComboBox()
        self.cbo_ids.currentIndexChanged.connect(self._on_select_id)
        hl.addWidget(self.cbo_ids)
        top.setLayout(hl)

        # Tabla de coordenadas
        self.table = QTableWidget(self)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["x", "y"])

        # Insertar panel y reemplazar el viewer por la tabla
        lay: QVBoxLayout = self.layout()  # type: ignore
        lay.insertWidget(1, top)          # debajo de la toolbar
        lay.replaceWidget(self.viewer, self.table)
        self.viewer.hide()

        # --- Panel lateral con filtros ---
        side = QWidget(self)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(0, 0, 0, 0)

        self.lst_ids = QListWidget()
        self.lst_ids.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        side_lay.addWidget(QLabel("Filtrar secciones (multi-selección):"))
        side_lay.addWidget(self.lst_ids)

        # Botones de acción
        btns = QWidget(self)
        btns_lay = QHBoxLayout(btns); btns_lay.setContentsMargins(0,0,0,0)
        self.btn_plot_selected = QPushButton("Graficar seleccionadas")
        self.btn_plot_all = QPushButton("Ver todo")
        self.btn_plot_clear = QPushButton("Limpiar gráfico")
        btns_lay.addWidget(self.btn_plot_selected)
        btns_lay.addWidget(self.btn_plot_all)
        btns_lay.addWidget(self.btn_plot_clear)
        side_lay.addWidget(btns)

        # --- Área principal: gráfico + tabla ---
        self.canvas = PlotCanvas(self, use_colorbar=False) # (clase que agregaste en el paso 2)

        # Splitter vertical (gráfico arriba, tabla abajo)
        plot_and_table = QSplitter(self)
        plot_and_table.setOrientation(Qt.Orientation.Vertical)
        plot_and_table.addWidget(self.canvas)
        plot_and_table.addWidget(self.table)
        plot_and_table.setStretchFactor(0, 3)  # gráfico más grande
        plot_and_table.setStretchFactor(1, 2)

        # Splitter principal (lateral + área principal)
        main_split = QSplitter(self)
        main_split.addWidget(side)
        main_split.addWidget(plot_and_table)
        main_split.setStretchFactor(0, 1)
        main_split.setStretchFactor(1, 3)

        # Inserta el splitter en el layout central
        lay: QVBoxLayout = self.layout()  # type: ignore
        try:
            self.viewer.hide()  # si existía el viewer de texto, lo ocultamos
        except Exception:
            pass
        lay.addWidget(main_split)

        # Conexiones de botones del panel lateral
        self.btn_plot_selected.clicked.connect(self._plot_selected)
        self.btn_plot_all.clicked.connect(self._plot_all)
        self.btn_plot_clear.clicked.connect(lambda: self.canvas.clear())


    def _cargar_y_mostrar(self, ruta: str):
        # Parseo real + variables
        self.result = self.parser.parse(ruta)
        self.state = compute_variables(self.result)

        # Poblar combo con IDs
        ids = self.result.meta.get("ids", [])
        self.cbo_ids.blockSignals(True)
        self.cbo_ids.clear()
        self.cbo_ids.addItems(ids)
        self.cbo_ids.blockSignals(False)

        # Cargar primera sección si existe
        if ids:
            self._load_section(ids[0])
            self.cbo_ids.setCurrentIndex(0)
        else:
            # Si no hay IDs, limpiar tabla
            self.table.clearContents()
            self.table.setRowCount(0)
        # Poblar lista lateral con IDs
        # Poblar lista multiselección con todos los IDs
        self.lst_ids.clear()
        ids = self.result.meta.get("ids", [])
        for sec_id in ids:
            self.lst_ids.addItem(QListWidgetItem(sec_id))

        # Dibuja la primera sección como referencia (si existe)
        if ids:
            self._plot_single(ids[0])  # no borra otras curvas, solo añade
        self._status(f"XSECS: cargado {os.path.basename(ruta)} ({len(ids)} secciones)")


    def _on_select_id(self, idx: int):
        if idx < 0 or not self.result:
            return
        sec_id = self.cbo_ids.currentText()
        self._load_section(sec_id)

    def _load_section(self, sec_id: str):
        """Llena la tabla con coords de la sección seleccionada."""
        if not self.result or not isinstance(self.result.data, dict):
            return
        info = self.result.data.get(sec_id)
        if not info:
            return

        df = info.get("coords")
        # Soporta DataFrame o listas simples
        try:
            # pandas DataFrame esperado: columnas ["x","y"]
            cols = list(df.columns)  # puede fallar si no es DataFrame
            if not {"x", "y"}.issubset(set(cols)):
                raise ValueError("DataFrame sin columnas x/y")
            n = len(df)
            self.table.setRowCount(n)
            self.table.setColumnCount(2)
            self.table.setHorizontalHeaderLabels(["x", "y"])
            for r, (_, row) in enumerate(df.iterrows()):
                self.table.setItem(r, 0, QTableWidgetItem(str(row["x"])))
                self.table.setItem(r, 1, QTableWidgetItem(str(row["y"])))
        except Exception:
            # Fallback: si coords es lista de pares/tuplas o lista de dicts
            data = df
            rows = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "x" in item and "y" in item:
                        rows.append((item["x"], item["y"]))
                    elif isinstance(item, (tuple, list)) and len(item) >= 2:
                        rows.append((item[0], item[1]))
            # pintar
            self.table.setRowCount(len(rows))
            self.table.setColumnCount(2)
            self.table.setHorizontalHeaderLabels(["x", "y"])
            for r, (x, y) in enumerate(rows):
                self.table.setItem(r, 0, QTableWidgetItem(str(x)))
                self.table.setItem(r, 1, QTableWidgetItem(str(y)))

        self._status(f"XSECS: sección {sec_id} cargada ({self.table.rowCount()} vértices)")
        # Dibuja solo esta sección (sin limpiar el resto del gráfico)
        self._plot_single(sec_id, clear=False)
    
    def _extract_xy(self, df_or_list):
        """Devuelve (xs, ys) desde DataFrame x/y o lista de pares/dicts."""
        xs, ys = [], []
        # Intento DataFrame (pandas)
        try:
            cols = list(df_or_list.columns)  # falla si no es DF
            if {"x", "y"}.issubset(set(cols)):
                for _, row in df_or_list.iterrows():
                    xs.append(float(row["x"]))
                    ys.append(float(row["y"]))
                return xs, ys
        except Exception:
            pass
        # Fallback: lista de dicts o tuplas
        if isinstance(df_or_list, list):
            for item in df_or_list:
                if isinstance(item, dict) and "x" in item and "y" in item:
                    xs.append(float(item["x"])); ys.append(float(item["y"]))
                elif isinstance(item, (tuple, list)) and len(item) >= 2:
                    xs.append(float(item[0])); ys.append(float(item[1]))
        return xs, ys

    def _plot_single(self, sec_id: str, clear: bool = False):
        """Plotea una sola sección por ID."""
        if not self.result or not isinstance(self.result.data, dict):
            return
        info = self.result.data.get(sec_id)
        if not info:
            return
        xs, ys = self._extract_xy(info.get("coords"))
        if not xs:
            return
        if clear:
            self.canvas.clear()
        self.canvas.plot_polyline(xs, ys, label=sec_id)
        self.canvas.finalize(show_legend=True)

    def _plot_selected(self):
        """Plotea todas las seleccionadas en la lista lateral."""
        if not self.result:
            return
        selected = [it.text() for it in self.lst_ids.selectedItems()]
        if not selected:
            QMessageBox.information(self, "Graficar", "Selecciona una o más secciones en la lista.")
            return
        self.canvas.clear()
        for sec_id in selected:
            self._plot_single(sec_id, clear=False)
        self.canvas.finalize(show_legend=True)

    def _plot_all(self):
        """Plotea todas las secciones del archivo."""
        if not self.result:
            return
        ids = self.result.meta.get("ids", [])
        if not ids:
            return
        # (Opcional) aviso si son muchas
        if len(ids) > 500:
            ok = QMessageBox.question(self, "Ver todo", f"Se graficarán {len(ids)} secciones. ¿Continuar?")
            if ok.name != "Yes":
                return
        self.canvas.clear()
        for sec_id in ids:
            self._plot_single(sec_id, clear=False)
        self.canvas.finalize(show_legend=True)

#CLASS XSECITab
class XSECITab(_BaseSectionTab):
    """XSECI: selector de tiempo + ID, tabla y gráfico perfil (terreno/agua + velocidad)."""
    # ⬅️ nueva señal: manda el ParseResult (o None si vacías)
    dataLoaded = pyqtSignal(object)  # ParseResult
    # bandera de cancelación a nivel de instancia
    

    def __init__(self):
        super().__init__("XSECI", "XSECI")
        self._cancel_flag = False #opcional?
        self.result = None   # asegúrate de tener este atributo

        # Panel de selección (tiempo + id)
        sel = QWidget(self)
        sel_lay = QHBoxLayout(sel); 
        sel_lay.setContentsMargins(0,0,0,0)
        
        # --- Botón retroceder tiempo ---
        btn_prev = QToolButton()
        btn_prev.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        btn_prev.setToolTip("Tiempo anterior (Ctrl+←)")
        btn_prev.setFixedSize(28, 28)
        btn_prev.setIconSize(QSize(18, 18))
        btn_prev.setAutoRepeat(True)
        btn_prev.setAutoRepeatDelay(250)
        btn_prev.setAutoRepeatInterval(120)
        btn_prev.clicked.connect(self._time_prev)
        sel_lay.addWidget(btn_prev)

        # --- Combo tiempos ---
        sel_lay.addWidget(QLabel("Tiempo:"))
        self.cbo_time = QComboBox()
        self.cbo_time.setMinimumWidth(180) # Ajustar al ancho del texto
        sel_lay.addWidget(self.cbo_time)
        #sel_lay.addSpacing(12)


        # --- Botón avanzar tiempo ---
        btn_next = QToolButton()
        btn_next.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward))
        btn_next.setToolTip("Tiempo siguiente (Ctrl+→)")
        btn_next.setFixedSize(28, 28)
        btn_next.setIconSize(QSize(18, 18))
        btn_next.setAutoRepeat(True)
        btn_next.setAutoRepeatDelay(250)
        btn_next.setAutoRepeatInterval(120)
        btn_next.clicked.connect(self._time_next)
        sel_lay.addWidget(btn_next)

        sel_lay.addSpacing(12)

        # --- Sección ---
        sel_lay.addWidget(QLabel("Sección:"))
        self.cbo_id = QComboBox()
        self.cbo_id.setMinimumWidth(140)
        sel_lay.addWidget(self.cbo_id)

        
        # auto-repeat (mantener pulsado avanza/retrocede)
        for b in (btn_prev, btn_next):
            b.setAutoRepeat(True)
            b.setAutoRepeatDelay(250)     # ms antes de repetir
            b.setAutoRepeatInterval(120)  # ms entre repeticiones

        sel_lay.addSpacing(8)

        # Secciones con Ctrl + flechas
        QShortcut(QKeySequence("Ctrl+Left"),  self, activated=self._section_prev)
        QShortcut(QKeySequence("Ctrl+Right"), self, activated=self._section_next)

        
        # Canvas + tabla
        self.canvas = PlotCanvas(self, use_colorbar=True)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.table = QTableWidget(self)
        self.table.setColumnCount(0)

        self.aspect_mode = "pretty"  # "pretty" | "equal"
        
        # --- toggle 1:1 ---
        self.btn_aspect = QPushButton("Escala 1:1")
        self.btn_aspect.setCheckable(True)
        self.btn_aspect.setToolTip("Alternar entre vista estética y 1:1,  Atajo: 1")
        self.btn_aspect.toggled.connect(self._toggle_aspect_mode)
        sel_lay.addSpacing(12)
        sel_lay.addWidget(self.btn_aspect)     # <— usa sel_lay, no top_controls_layout

        # --- exportaciones ---
        btn_png = QPushButton("Exportar PNG")
        btn_png.clicked.connect(self._export_png)
        btn_csv = QPushButton("Exportar CSV")
        btn_csv.clicked.connect(self._export_csv)
        sel_lay.addSpacing(12)
        sel_lay.addWidget(btn_png)  
        sel_lay.addWidget(btn_csv)

        btn_xlsx = QPushButton("Exportar Excel")
        btn_xlsx.clicked.connect(self._export_xlsx)
        sel_lay.addWidget(btn_xlsx)

        # DPI
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(72, 600)
        self.spin_dpi.setSingleStep(30)
        self.spin_dpi.setValue(180)
        self.spin_dpi.setPrefix("DPI ")
        self.spin_dpi.setToolTip("Resolución al exportar")

        # Copiar al portapapeles (icono estándar)
        btn_copy = QToolButton()
        btn_copy.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton))
        btn_copy.setIconSize(QSize(18, 18))
        btn_copy.setToolTip("Copiar imagen al portapapeles")
        btn_copy.clicked.connect(self._copy_to_clipboard)
        

        # Exportar lote
        btn_batch = QToolButton()
        btn_batch.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        btn_batch.setIconSize(QSize(18, 18))
        btn_batch.setToolTip("Exportar lote (tiempos/secciones múltiples)")
        btn_batch.clicked.connect(self._export_batch)

        # Añádelos a tu layout de selección, por ejemplo después de btn_png / btn_csv:
        sel_lay.addSpacing(12)
        sel_lay.addWidget(self.spin_dpi)
        sel_lay.addWidget(btn_copy)
        sel_lay.addWidget(btn_batch)

        # Disposición (gráfico sobre tabla)
        split = QSplitter(self)
        split.setOrientation(Qt.Orientation.Vertical)
        split.addWidget(self.canvas)
        split.addWidget(self.table)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)

        # Montaje
        lay: QVBoxLayout = self.layout()  # type: ignore
        try: self.viewer.hide()
        except Exception: pass
        lay.insertWidget(1, sel)          # debajo de la toolbar superior propia del tab
        lay.insertWidget(2, self.toolbar) # << nueva línea: barra de herramientas de Matplotlib
        lay.addWidget(split)

        # Señales
        self.cbo_time.currentIndexChanged.connect(self._on_time_changed)
        self.cbo_id.currentIndexChanged.connect(self._on_id_changed)
        
        # --- bookmarks (favoritos) ---
        self.bookmarks: list[tuple[str, str]] = []  # [(time_label, sec_id)]
        self.cbo_bookmarks = QComboBox()
        self.cbo_bookmarks.setMinimumWidth(160)
        btn_add_bmk = QPushButton("★ Guardar vista")
        btn_go_bmk  = QPushButton("Ir")
        btn_add_bmk.clicked.connect(self._add_bookmark)
        btn_go_bmk.clicked.connect(self._goto_bookmark)

        sel_lay.addSpacing(12)
        sel_lay.addWidget(QLabel("Favoritos:"))
        sel_lay.addWidget(self.cbo_bookmarks)
        sel_lay.addWidget(btn_add_bmk)
        sel_lay.addWidget(btn_go_bmk)

        # --- atajos de teclado ---
        QShortcut(QKeySequence(Qt.Key.Key_Left),  self, activated=self._time_prev)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, activated=self._time_next)
        QShortcut(QKeySequence("1"),          self, activated=self._shortcut_toggle_aspect)
        QShortcut(QKeySequence("0"),          self, activated=self._reset_view)
        QShortcut(QKeySequence("Ctrl+S"),     self, activated=self._export_png)
        QShortcut(QKeySequence("Ctrl+E"),     self, activated=self._export_csv)


### Modificacion para lectura de proceso de abrir XSECI.
    def _abrir_xseci(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir XSECI", self._last_dir(), "XSECI (*.XSECI *.xseci)")
        if not path:
            return
        self._save_last_dir(os.path.dirname(path) + os.sep)
        self._cargar_xseci_async(path)

    def _cargar_xseci_async(self, path: str):
        # UI: diálogo de progreso
        self._prog = QProgressDialog("Cargando XSECI...", "Cancelar", 0, 100, self)
        self._prog.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._prog.setAutoClose(False)
        self._prog.setAutoReset(False)
        self._prog.setMinimumDuration(300)  # ms

        # Hilo + worker
        self._thr = QThread(self)
        self._wk  = XSECIWorker(path)
        self._wk.moveToThread(self._thr)

        # Conexiones
        self._thr.started.connect(self._wk.run)
        self._wk.progress.connect(self._on_load_progress)
        self._wk.finished.connect(self._on_load_finished)
        self._wk.failed.connect(self._on_load_failed)
        self._wk.cancelled.connect(self._on_load_cancelled)

        # Cancelación desde el diálogo
        self._prog.canceled.connect(self._wk.request_cancel)

        # Limpieza
        self._wk.finished.connect(self._cleanup_worker)
        self._wk.failed.connect(self._cleanup_worker)
        self._wk.cancelled.connect(self._cleanup_worker)

        self._thr.start()

    def _on_load_progress(self, done: int, total: int):
        # actualiza barra (si total=0, pon modo “indeterminado”)
        if total <= 0:
            self._prog.setRange(0, 0)
        else:
            self._prog.setRange(0, total)
            self._prog.setValue(done)

    def _on_load_finished(self, result):
        self._prog.close()
        self.result = result
        # opcional: computar variables derivadas
        self.state = compute_variables(self.result)
        # poblar combos
        times = self.result.meta.get("times", []) if isinstance(self.result, ParseResult) else sorted(self.result.keys())
        self.cbo_time.blockSignals(True)
        self.cbo_time.clear()
        self.cbo_time.addItems(times)
        self.cbo_time.blockSignals(False)
        if times:
            self.cbo_time.setCurrentIndex(0)
            self._populate_ids_for_time(times[0])

    def _on_load_failed(self, msg: str):
        self._prog.close()
        QMessageBox.critical(self, "Error", f"No se pudo cargar el XSECI:\n{msg}")

    def _on_load_cancelled(self):
        self._prog.close()
        QMessageBox.information(self, "Cargar XSECI", "Operación cancelada por el usuario.")

    def _cleanup_worker(self):
        try:
            self._thr.quit()
            self._thr.wait(1500)
        except Exception:
            pass
        self._wk = None
        self._thr = None
        self._prog = None




### Fin de modificación


    def _time_prev(self):
        i = self.cbo_time.currentIndex()
        if i > 0:
            self.cbo_time.setCurrentIndex(i - 1)

    def _time_next(self):
        i = self.cbo_time.currentIndex()
        if i < self.cbo_time.count() - 1:
            self.cbo_time.setCurrentIndex(i + 1)

    def _section_prev(self):
        i = self.cbo_id.currentIndex()
        if i > 0:
            self.cbo_id.setCurrentIndex(i - 1)

    def _section_next(self):
        i = self.cbo_id.currentIndex()
        if i < self.cbo_id.count() - 1:
            self.cbo_id.setCurrentIndex(i + 1)



    def _current_df(self):
        """Devuelve el DataFrame de la selección actual o None."""
        if not self.result:
            return None
        t = self.cbo_time.currentText()
        s = self.cbo_id.currentText()
        sec = self.result.data.get(t, {}).get(s) if (t and s) else None
        return None if not sec else sec.get("df")


    def _export_csv(self):
        """Exporta la tabla actual a CSV."""
        t = self.cbo_time.currentText()
        s = self.cbo_id.currentText()
        if not t or not s or not self.result:
            return
        sec = self.result.data.get(t, {}).get(s)
        if not sec or sec.get("df") is None:
            QMessageBox.information(self, "Exportar CSV", "No hay datos para exportar.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar CSV",
                                            f"{s}_{t}.csv".replace(" ", "_").replace(":", "-"),
                                            "CSV (*.csv)")
        if not path:
            return
        try:
            sec["df"].to_csv(path, index=False)
            QMessageBox.information(self, "Exportar CSV", "Archivo guardado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")


    def _export_xlsx(self):
        import pandas as pd
        df = self._current_df()
        if df is None or df.empty:
            QMessageBox.warning(self, "Exportar", "No hay datos para exportar.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar tabla Excel", f"{self.cbo_id.currentText()}_{self.cbo_time.currentText()}.xlsx",
            "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
                df.to_excel(writer, sheet_name="XSECI", index=False)
            QMessageBox.information(self, "Exportar", "Excel guardado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")

# --- Exportar PNG del perfil actual ---    
    def _export_png(self):
        # nombre y carpeta por defecto
        default_name = self._default_image_filename("png")
        default_path = os.path.join(self._last_dir(), default_name)

        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar imagen",
            default_path,
            "PNG (*.png);;SVG (*.svg);;PDF (*.pdf)"
        )
        if not path:
            return

        # si el usuario eligió filtro pero no puso extensión, añade una
        if not os.path.splitext(path)[1]:
            path += ".png"

        try:
            self._save_current_figure(path, dpi=self.spin_dpi.value())
            self._save_last_dir(path)
            QMessageBox.information(self, "Exportar", f"Imagen guardada:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")


    def _save_current_figure(self, path: str, dpi: int = 180, transparent: bool = False):
        """Guarda la figura actual (respeta leyenda/cbar) con DPI elegidos."""
        fig = self.canvas.fig
        ax  = self.canvas.ax
        # asegura layout actualizado
        fig.canvas.draw()
        face = fig.get_facecolor()
        edge = fig.get_edgecolor()
        fig.savefig(
            path,
            dpi=dpi,
            bbox_inches="tight",
            facecolor=face,
            edgecolor=edge,
            transparent=transparent,
            metadata={
                "Title": ax.get_title(),
                "Creator": "My Friend TGI",
                "Subject": "Perfil XSECI",
            },
        )

    def _copy_to_clipboard(self):
        try:
            buf = io.BytesIO()
            fig = self.canvas.fig
            fig.canvas.draw()  # actualiza layout
            fig.savefig(buf, format="png", dpi=self.spin_dpi.value(), bbox_inches="tight")
            buf.seek(0)
            data = buf.getvalue()
            img = QImage.fromData(data, "PNG")
            if img.isNull():
                # fallback: captura visual del canvas (DPI de pantalla)
                pix = self.canvas.grab()
                QGuiApplication.clipboard().setPixmap(pix)
            else:
                QGuiApplication.clipboard().setImage(img)
            QMessageBox.information(self, "Portapapeles", "Imagen copiada al portapapeles.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo copiar:\n{e}")


    def _shortcut_toggle_aspect(self):
        # invierte el check del botón (sin emitir doble señal)
        self.btn_aspect.setChecked(not self.btn_aspect.isChecked())

    def _toggle_aspect_mode(self, checked: bool):
        self.aspect_mode = "equal" if checked else "pretty"
        # Redibuja con el modo elegido para la selección actual
        t = self.cbo_time.currentText()
        s = self.cbo_id.currentText()
        if not t or not s or not self.result:
            return
        sec = self.result.data.get(t, {}).get(s)
        if not sec:
            return
        df = sec.get("df")
        title = f"{s} @ {t}  (Q={sec.get('Q')} {sec.get('Q_units') or ''})"
        self._plot_profile(df, title=title)


    def _ensure_unique_path(self, path: str) -> str:
        """Si path existe, añade _1, _2, ... hasta que sea único."""
        base, ext = os.path.splitext(path)
        i = 1
        out = path
        while os.path.exists(out):
            out = f"{base}_{i}{ext}"
            i += 1
        return out

    def _export_batch(self):
        if not self.result:
            QMessageBox.information(self, "Exportar lote", "No hay datos cargados.")
            return

        # Conjuntos disponibles
        times = self.result.meta.get("times", [])
        all_ids = sorted({sid for t in self.result.data for sid in self.result.data[t].keys()})

        dlg = BatchExportDialog(self, times, all_ids)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        sel_times, sel_ids, cartes = dlg.selections()
        if not sel_times or not sel_ids:
            QMessageBox.information(self, "Exportar lote", "Debes seleccionar al menos un tiempo y una sección.")
            return

        # Carpeta destino
        out_dir = QFileDialog.getExistingDirectory(self, "Selecciona carpeta de destino", self._last_dir())
        if not out_dir:
            return

        dpi = self.spin_dpi.value()
        count = 0

        try:
            # Recorremos SIEMPRE por (t, s) y exportamos si existe
            for t in sel_times:
                for s in sel_ids:
                    sec = (self.result.data.get(t) or {}).get(s)
                    if not sec:
                        continue

                    df = sec.get("df")
                    title = f"{s} @ {t}  (Q={sec.get('Q')} {sec.get('Q_units') or ''})"

                    # Renderizamos la vista (NO tocamos combos)
                    self._plot_profile(df, title=title)

                    # Nombre rico por cada (t, s)
                    fname = self._default_image_filename("png", time_label=t, section_id=s, info=sec)
                    out_path = os.path.join(out_dir, fname)
                    out_path = self._ensure_unique_path(out_path)

                    self._save_current_figure(out_path, dpi=dpi)
                    count += 1

            self._save_last_dir(out_dir + os.sep)
            QMessageBox.information(self, "Exportar lote", f"Exportadas {count} imágenes en:\n{out_dir}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo en exportación masiva:\n{e}")


    

    def _cargar_y_mostrar(self, ruta: str):
        self.result = self.parser.parse(ruta)
               
        
        parser = XSECIParser()

        # 1) Diálogo de progreso
        dlg = QProgressDialog("Leyendo XSECI…", "Cancelar", 0, 100, self)
        dlg.setWindowTitle("Cargando")
        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        dlg.setMinimumDuration(0)  # muéstralo enseguida
        dlg.setValue(0)
        dlg.show()
        QApplication.processEvents()         # <- DALE AIRE A LA GUI

        # 2) Estado cancelado (cerrado sobre mutable)
        cancelled = {"val": False}

        def cancel_cb() -> bool:
            # si el usuario pulsó “Cancelar”
            val = dlg.wasCanceled()
            cancelled["val"] = cancelled["val"] or val
            return cancelled["val"]

        def progress_cb(done: int, total: int):
            # actualizar barra (0..100)
            pct = int(done / total * 100) if total else 0
            dlg.setValue(pct)
            QApplication.processEvents()  # permite refrescar y procesar clicks

        try:
            # 3) Llamar al parser con callbacks
            self.result = parser.parse(ruta, progress_cb=progress_cb, cancel_cb=cancel_cb)

        except ParseCancelled:
            dlg.close()
            QMessageBox.information(self, "Cancelado", "Lectura cancelada por el usuario.")
            return
        except Exception as e:
            dlg.close()
            QMessageBox.critical(self, "Error", f"No se pudo leer el archivo:\n{e}")
            return
        finally:
            dlg.close()

        # 4) Si todo OK, continuar como antes
        self.state = compute_variables(self.result)
        times = self.result.meta.get("times", [])
        self.cbo_time.blockSignals(True)
        self.cbo_time.clear()
        self.cbo_time.addItems(times)
        self.cbo_time.blockSignals(False)
        if times:
            self.cbo_time.setCurrentIndex(0)
            self._populate_ids_for_time(times[0])

        # 🔔 avisa a quien le interese (Flow2DWidget/XSECH)
        self.dataLoaded.emit(self.result)

    def _populate_ids_for_time(self, time_label: str, preferred_id: str | None = None) -> str | None:
        """Llena el combo de IDs para el tiempo seleccionado y carga una sola vez."""
        if not self.result:
            return None

        # estado previo y memoria por tiempo
        prev_id = self.cbo_id.currentText()
        if not hasattr(self, "_last_id_for_time"):
            self._last_id_for_time: dict[str, str] = {}

        ids = sorted((self.result.data.get(time_label) or {}).keys())
        # Relleno del combo sin señales
        self.cbo_id.blockSignals(True)
        self.cbo_id.clear()
        if ids:
            self.cbo_id.addItems(ids)

        # Decide el target de forma robusta
        target = None
        if preferred_id and preferred_id in ids:
            target = preferred_id
        elif time_label in self._last_id_for_time and self._last_id_for_time[time_label] in ids:
            target = self._last_id_for_time[time_label]
        elif prev_id in ids:
            target = prev_id
        elif ids:
            target = ids[0]

        if target:
            self.cbo_id.setCurrentText(target)

        self.cbo_id.blockSignals(False)

        # Cargar y recordar una sola vez
        if target:
            self._last_id_for_time[time_label] = target
            self._load_current(time_label, target)
            return target

        # Si no hay IDs, limpia tabla/gráfico si quieres:
        self.table.clearContents()
        self.table.setRowCount(0)
        self.canvas.clear()
        self.canvas.ax.set_title(f"{time_label}: sin secciones")
        self.canvas.draw_idle()
        return None


    def _on_time_changed(self, _idx: int):
        t = self.cbo_time.currentText()
        current_id = self.cbo_id.currentText()
        if t:
            self._populate_ids_for_time(t, preferred_id=current_id)  # <— mantiene la misma sección

    def _on_id_changed(self, _idx: int):
        t = self.cbo_time.currentText()
        s = self.cbo_id.currentText()
        if t and s:
            self._load_current(t, s)

    # --- Cargar tabla + gráfico para (tiempo, id) ---
    def _load_current(self, time_label: str, sec_id: str):
        if not self.result:
            return
        sec = self.result.data.get(time_label, {}).get(sec_id)
        if not sec:
            return
        df = sec.get("df")

        # Tabla
        self._populate_table(df)

        # Perfil
        self._plot_profile(df, title=f"{sec_id} @ {time_label}  (Q={sec.get('Q')} {sec.get('Q_units') or ''})")

    def _populate_table(self, df):
        # Siempre mostrar todas las columnas de interés
        col_order = ["ELEM", "STATION", "BEDEL", "DEPTH", "WSEL",
                     "VEL_NORM", "FROUDE", "QS_NORM"]

        if df is None or df.empty:
            self.table.clearContents()
            self.table.setRowCount(0)
            self.table.setColumnCount(len(col_order))
            self.table.setHorizontalHeaderLabels(col_order)
            return

        # Agregar columnas faltantes con NaN/None para completar el orden
        for col in col_order:
            if col not in df.columns:
                df[col] = None

        # Reordenar DataFrame según col_order
        df = df[col_order]

        # Configurar tabla
        self.table.setColumnCount(len(col_order))
        self.table.setHorizontalHeaderLabels(col_order)
        self.table.setRowCount(len(df))

        # Llenar tabla
        for r, (_, row) in enumerate(df.iterrows()):
            for c, name in enumerate(col_order):
                val = row[name]
                self.table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))
    def _get_col(self, df, *candidates):
        for name in candidates:
            if name in df.columns:
                return df[name].astype(float).to_numpy()
        # heurística: buscar por prefijo
        for cand in candidates:
            for col in df.columns:
                if col.replace(" ", "").startswith(cand.replace(" ", "")):
                    try: return df[col].astype(float).to_numpy()
                    except Exception: pass
        return None

    def _plot_profile(self, df, title: str = ""):
        """Dibuja Terreno (STATION vs BEDEL), Agua (STATION vs WSEL) y cortina coloreada por VEL_NORM."""
        # 1) Limpiar el lienzo y validar datos
        self.canvas.clear()
        ax = self.canvas.ax
        if (df is None) or df.empty: 
            ax.set_title(title or "Sin datos")
            self.canvas.draw_idle()
            return

        # 2) Obtener columnas de forma robusta (acepta variantes de encabezado)
        #_get_col intenta con varios candidatos y fallback por prefijo
        # Obtén columnas (robusto ante nombres ligeramente distintos)
        st = self._get_col(df, "STATION(m)", "STATION")
        bed = self._get_col(df, "BEDEL(m)", "BEDEL")
        wsl = self._get_col(df, "WSEL(m)", "WSEL")
        vel = self._get_col(df, "VEL_NORM(m/s)", "VEL_NORM")

        # Terreno y estación son imprescindibles para dibujar el perfil
        if (st is None) or (bed is None):
            self.canvas.ax.set_title("Faltan columnas STATION/BEDEL")
            self.canvas.draw_idle()
            return

        # 3) Asegurar que las series sean arreglos NumPy y queden alineadas
        # (evita errores si alguna serie es más larga)
        st  = np.asarray(st,  dtype=float)
        bed = np.asarray(bed, dtype=float)
        n_common = min(len(st), len(bed))
        st, bed = st[:n_common], bed[:n_common]
        
        if (wsl is not None):
            wsl = np.asarray(wsl, dtype=float)[:n_common]
        if (vel is not None):
            vel = np.asarray(vel, dtype=float)[:n_common]

        # 4) Trazos base: primero agua (debajo), luego terreno (encima)
        #    — Colores definidos: WSEL celeste, BEDEL marrón
        ax = self.canvas.ax
        # Asegura que las longitudes coincidan
        if (wsl is not None):
            ax.plot(st, wsl, linewidth=2, color="#00AEEF", label="Nivel (WSEL)", zorder=2)   # celeste cielo
        ax.plot(st, bed, linewidth=2.5, color="#8B5A2B", label="Terreno (BEDEL)", zorder=3)   # marrón tierra

        # 5) Cortina coloreada por velocidad (si hay wsl y vel)
        if (wsl is not None) and (vel is not None):
            # Asegura longitudes compatibles
            segs = np.stack([
                np.column_stack([st, bed]),
                np.column_stack([st, wsl])], 
                axis=1
            )

            lc = LineCollection(segs, cmap="viridis", array=vel, linewidths=2, alpha=0.85, zorder=1)
            ax.add_collection(lc)

            # ✅ UNA sola línea: crea/actualiza el colorbar en el cax fijo, sin cambiar layout
            self.canvas.get_or_update_colorbar(lc, label="Velocidad (m/s)")
        else:
            # Si no hay velocidad, asegúrate de no dejar colorbar “huérfano”
            if getattr(self.canvas, "_cbar", None):
                try:
                    self.canvas._cbar.remove()
                except Exception:
                    pass
                self.canvas._cbar = None

        # 6) Títulos y etiquetas de ejes
        ax.set_title(title or "Perfil XSECI")
        ax.set_xlabel("Distancia (m)", labelpad=10)  # un poco más de espacio
        ax.set_ylabel("Elevación (m)")


        # 7) Altura mínima visible (por si el perfil es muy "plano")

        y_vals = [*bed.tolist()]
        if bed is not None: 
            y_vals.extend(bed.tolist())
        if wsl is not None: 
            y_vals.extend(wsl.tolist())
        if y_vals:
            y_min, y_max = float(np.nanmin(y_vals)), float(np.nanmax(y_vals))
            span = y_max - y_min
            min_span = 1.0  # mínimo en unidades de elevación (m). Ajusta según tus datos
            if span < min_span:
                pad = (min_span - span) / 2 or 0.5
                ax.set_ylim(y_min - pad, y_max + pad)

        # 8) Aspecto (proporción). Modo 1:1 vs “pretty”
        if getattr(self, "aspect_mode", "pretty") == "equal":
            # 1:1 y límites coherentes sin aplastar
            (xl, xu), (yl, yu) = self._apply_equal_aspect_custom(ax, st, bed, wsl)
            ax.set_autoscale_on(False)
            ax.set_autoscalex_on(False)
            ax.set_autoscaley_on(False)
        else:
            # Vista “bonita”: relación caja estable y márgenes suaves
            self._apply_pretty_aspect(ax)
            try:
                ax.set_aspect("auto")
                ax.set_box_aspect(0.6)  # alto ≈ 60% del ancho (ajústalo si quieres)
            except Exception:
                pass
            ax.autoscale(enable=True, tight=True)
            ax.margins(0.05)

        # Mostrar leyenda solo si hay al menos 1 línea con label
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            # Asegura que la leyenda no se superponga al gráfico
            ax.legend(
                loc="upper center",
                bbox_to_anchor=(0.5, -0.25),
                bbox_transform=ax.transAxes,        # << CLAVE: coordenadas de figura
                ncol=2,
                fontsize=8,
                frameon=True,
                borderaxespad=0.3,
            )


        # 9) Cuadrícula y render final
        ax.grid(True, linestyle=":", alpha=0.6)
        self.canvas.draw_idle()


  
    def _apply_pretty_aspect(self, ax):
        """Vista estética: rectangular estable."""
        try:
            ax.set_aspect("auto")
            ax.set_box_aspect(0.6)   # 0.5..0.8 a gusto
        except Exception:
            pass

    def _apply_equal_aspect_expand_y(self, ax, x, y1, y2=None):
        """
        Fuerza 1:1 sin aplastar: si falta altura, expande Y simétricamente.
        x: array estaciones; y1: terreno; y2: agua (opcional).
        """
        import numpy as np
        x = np.asarray(x, float)
        ys = np.asarray(y1, float)
        if y2 is not None:
            ys = np.concatenate([ys, np.asarray(y2, float)])
        # spans actuales
        xmin, xmax = np.nanmin(x), np.nanmax(x)
        ymin, ymax = np.nanmin(ys), np.nanmax(ys)
        xspan = max(xmax - xmin, 1e-9)
        yspan = max(ymax - ymin, 1e-9)

        # Queremos yspan == xspan; si yspan < xspan, expandimos Y
        if yspan < xspan:
            extra = (xspan - yspan) / 2.0
            ymin -= extra
            ymax += extra

        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        try:
            ax.set_aspect("equal", adjustable="box")  # 1:1 con caja
        except Exception:
            pass

    def _apply_equal_aspect_custom(self, ax, x, y1, y2=None):
        """
        Escala 1:1 sin aplastar:
        - X: [0, Xmax]
        - Altura mínima en Y = 0.25 * Xmax (si los datos son más planos).
        - Y centrado alrededor del centro de los datos.
        """
        import numpy as np

        # --- saneo de datos ---
        x = np.asarray(x, float)
        y1 = np.asarray(y1, float)
        if y2 is not None:
            y2 = np.asarray(y2, float)

        x = x[np.isfinite(x)]
        yvals = y1[np.isfinite(y1)]
        if y2 is not None:
            yvals = np.concatenate([yvals, y2[np.isfinite(y2)]])

        if x.size == 0 or yvals.size == 0:
            # fallback amable
            ax.autoscale(enable=True, tight=True)
            try: ax.set_aspect("equal", adjustable="box")
            except Exception: pass
            return ax.get_xlim(), ax.get_ylim()

        # --- eje X ---
        xmin = 0.0
        xmax = float(np.nanmax(x))
        if not np.isfinite(xmax) or xmax <= 0:
            xmax = 1.0  # evita rango 0 en X

        # --- eje Y ---
        y_min = float(np.nanmin(yvals))
        y_max = float(np.nanmax(yvals))
        y_mid = 0.5 * (y_min + y_max)
        y_span_data = max(y_max - y_min, 0.0)

        y_span_target = max(0.25 * xmax, y_span_data)  # ≥ 25% de Xmax
        # si quedara 0 por algún caso extremo, abre un epsilon
        if y_span_target <= 0:
            y_span_target = 1.0

        y_lower = y_mid - y_span_target / 2.0
        y_upper = y_mid + y_span_target / 2.0
        if y_lower == y_upper:
            y_lower -= 0.5
            y_upper += 0.5

        ax.set_xlim(xmin, xmax)
        ax.set_ylim(y_lower, y_upper)
        try:
            ax.set_aspect("equal", adjustable="box")
        except Exception:
            pass
        # Devuelve límites para uso posterior
        return (xmin, xmax), (y_lower, y_upper)

    def _reset_view(self):
        """Replotea la selección actual en modo 'pretty' (reset zoom/vista)."""
        self.aspect_mode = "pretty"
        # sincroniza botón si hace falta
        if getattr(self, "btn_aspect", None) and self.btn_aspect.isChecked():
            self.btn_aspect.blockSignals(True)
            self.btn_aspect.setChecked(False)
            self.btn_aspect.blockSignals(False)
        # replotea
        t = self.cbo_time.currentText()
        s = self.cbo_id.currentText()
        if not t or not s or not self.result:
            return
        sec = self.result.data.get(t, {}).get(s)
        if not sec:
            return
        df = sec.get("df")
        title = f"{s} @ {t}  (Q={sec.get('Q')} {sec.get('Q_units') or ''})"
        self._plot_profile(df, title=title)

    # --- Bookmarks ---
    def _add_bookmark(self):
        t = self.cbo_time.currentText()
        s = self.cbo_id.currentText()
        if not t or not s:
            return
        pair = (t, s)
        if pair not in self.bookmarks:
            self.bookmarks.append(pair)
            self.cbo_bookmarks.addItem(f"{t} | {s}", userData=pair)

    def _goto_bookmark(self):
        idx = self.cbo_bookmarks.currentIndex()
        if idx < 0:
            return
        t, s = self.cbo_bookmarks.currentData()
        # cambiar tiempo SIN perder sección (ya lo controlas en _on_time_changed)
        # pero como queremos ir directo a (t,s), lo forzamos:
        self.cbo_time.blockSignals(True)
        self.cbo_time.setCurrentText(t)
        self.cbo_time.blockSignals(False)
        # poblar ids para ese tiempo y seleccionar s
        self._populate_ids_for_time(t)
        # si existe s para ese tiempo, selecciona
        i = self.cbo_id.findText(s)
        if i >= 0:
            self.cbo_id.setCurrentIndex(i)
        else:
            # si no existe, al menos dejamos el primero
            pass

    def _slug(self, s: str) -> str:
        # Seguro para nombres de archivo
        s = s.replace(" ", "_")
        return re.sub(r"[^A-Za-z0-9._-]+", "_", s)

    def _default_image_filename(
        self,
        ext: str = "png",
        time_label: str | None = None,
        section_id: str | None = None,
        info: dict | None = None,
    ) -> str:
        # Si no te pasan, usa los actuales (para exportación simple)
        t = (time_label or self.cbo_time.currentText().strip() or "time")
        s = (section_id or self.cbo_id.currentText().strip() or "section")

        if info is None:
            info = self.result.data.get(t, {}).get(s, {})

        q = info.get("Q")
        qu = info.get("Q_units") or "m3s"

        def _slug(s: str) -> str:
            import re
            s = s.replace(" ", "_")
            return re.sub(r"[^A-Za-z0-9._-]+", "_", s)

        t_norm = _slug(t.replace(" ", "").replace(":", "").replace(",", "_"))
        base = f"{_slug(s)}__{t_norm}"
        if q is not None:
            base += f"__Q={float(q):.3f}_{_slug(qu)}"
        return f"{base}.{ext}"

    def _last_dir(self) -> str:
        s = QSettings("MyFriendTGI", "Flow2D")
        return s.value("export_dir", os.path.expanduser("~"))

    def _save_last_dir(self, path: str):
        s = QSettings("MyFriendTGI", "Flow2D")
        s.setValue("export_dir", os.path.dirname(path))

class BatchExportDialog(QDialog):
    """Selector multi para tiempos/secciones. Permite cruzar ambos conjuntos."""
    def __init__(self, parent, times: list[str], ids: list[str]):
        super().__init__(parent)
        self.setWindowTitle("Exportar lote")
        self.resize(500, 360)

        lay = QVBoxLayout(self)

        lay.addWidget(QLabel("Selecciona tiempos:"))
        self.lst_times = QListWidget()
        self.lst_times.setSelectionMode(self.lst_times.SelectionMode.MultiSelection)
        for t in times:
            QListWidgetItem(t, self.lst_times)
        lay.addWidget(self.lst_times)

        lay.addWidget(QLabel("Selecciona secciones:"))
        self.lst_ids = QListWidget()
        self.lst_ids.setSelectionMode(self.lst_ids.SelectionMode.MultiSelection)
        for s in ids:
            QListWidgetItem(s, self.lst_ids)
        lay.addWidget(self.lst_ids)

        self.chk_cartesian = QCheckBox("Cruzar tiempos × secciones (cartesiano)")
        self.chk_cartesian.setChecked(True)
        lay.addWidget(self.chk_cartesian)

        row = QHBoxLayout()
        btn_ok = QPushButton("Exportar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)
        row.addWidget(btn_ok)
        lay.addLayout(row)

    def selections(self):
        ts = [i.text() for i in self.lst_times.selectedItems()]
        ss = [i.text() for i in self.lst_ids.selectedItems()]
        return ts, ss, self.chk_cartesian.isChecked()
class XSECIWorker(QObject):
    progress = pyqtSignal(int, int)   # done, total
    finished = pyqtSignal(object)     # result
    failed   = pyqtSignal(str)
    cancelled= pyqtSignal()

    def __init__(self, path: str):
        super().__init__()
        self._path = path
        self._cancel = False

    def request_cancel(self):
        self._cancel = True

    def _cancel_cb(self) -> bool:
        return self._cancel

    def _progress_cb(self, done: int, total: int):
        self.progress.emit(done, total)

    def run(self):
        try:
            from .flow2d_parsers import parse_xseci, ParseCancelled
            result = parse_xseci(self._path,
                                 progress_cb=self._progress_cb,
                                 cancel_cb=self._cancel_cb)
            if self._cancel:
                self.cancelled.emit()
            else:
                self.finished.emit(result)
        except ParseCancelled:
            self.cancelled.emit()
        except Exception as e:
            self.failed.emit(str(e))

#CLASS XSECH
class XSECHidrogramaTab(QWidget):
    """
    Hidrogramas por sección:
      - Arriba: gráfico (horas vs Q)
      - Abajo: tabla (tiempo vs columnas de secciones)
      - Fuente de caudal: 'XSECI' o 'Ajustados'
      - Multi-selección de secciones a graficar
    """
    
    

    def __init__(self):
        super().__init__()

        # --- Estado interno (se llena al recibir datos) ---
        self._times_labels: list[str] = []
        self._times_hours: np.ndarray | None = None   # shape (T,)
        self._sections: list[str] = []                # ids ordenados
        self._Q_xseci: np.ndarray | None = None       # shape (T, S)
        self._Q_adj:   np.ndarray | None = None       # shape (T, S)

        # Matrices T×S por métrica
        # claves: "Q_XSECI", "Q_AJUST", "Flow_Width", "Depth_Ave", "Flow_Elev_Ave", "Velocity_Ave", "Q_Flow"
        self._matrices: dict[str, np.ndarray] = {}

        # --- UI raíz ---
        root = QVBoxLayout(self)

        # 1) Toolbar superior (fuente de caudales + acciones propias)
        tb = QToolBar("Hidrograma", self)
        tb.setIconSize(QSize(18, 18))
        root.addWidget(tb)
        self._topbar = tb          # <-- alias para compatibilidad con código previo

        # Fuente de series a graficar
        tb.addWidget(QLabel("Fuente:"))
        self.cbo_source = QComboBox()
        # claves de usuario (texto visible) → claves internas
        self._source_items = [
            ("Caudales XSECI",    "Q_XSECI"),
            ("Caudales ajustados","Q_AJUST"),
            ("Ancho de flujo",    "Flow_Width"),
            ("Tirante promedio",  "Depth_Ave"),
            ("Cota agua prom.",   "Flow_Elev_Ave"),
            ("Velocidad prom.",   "Velocity_Ave"),
            ("Q calculado (test)","Q_Flow"),
        ]
        self.cbo_source.addItems([t for (t, _) in self._source_items])
        tb.addWidget(self.cbo_source)
        tb.addSeparator()
        self.cbo_source.currentIndexChanged.connect(self._on_source_changed)

        # Acción eje Y secundario (espejo)
        self.ax2 = None                # eje Y secundario (twinx)
        self._cid_ylim = None          # id del callback para sincronizar límites/ticks
        self.act_y2 = QAction("Eje Y2", self, checkable=True)
        self.act_y2.setToolTip("Activar eje vertical secundario (espejo)")
        self.act_y2.toggled.connect(self._toggle_y2)
        tb.addAction(self.act_y2)

        # 2) Barra de navegación de Matplotlib (como widget debajo del toolbar)
        self.canvas = PlotCanvas(self, use_colorbar=False)
        self.nav = NavigationToolbar(self.canvas, self)
        self.nav.setIconSize(QSize(18, 18))
        root.addWidget(self.nav)   # <- opción simple y limpia
        # Si la quisieras dentro de la toolbar superior, sería:
        # tb.addWidget(self.nav)

        # 3) Lista de secciones a graficar (multi-selección)
        list_row = QWidget(self)
        list_lay = QHBoxLayout(list_row); list_lay.setContentsMargins(0, 0, 0, 0)
        list_lay.addWidget(QLabel("Secciones:"))
        self.lst_sections = QListWidget()
        self.lst_sections.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.lst_sections.setMaximumHeight(90)
        list_lay.addWidget(self.lst_sections, 1)
        root.addWidget(list_row)

        # 4) Splitter con gráfico arriba y tabla abajo
        split = QSplitter(self)
        split.setOrientation(Qt.Orientation.Vertical)
        split.addWidget(self.canvas)

        self.table = QTableWidget(self)
        split.addWidget(self.table)

        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        root.addWidget(split)

        # Señales mínimas
        self.cbo_source.currentIndexChanged.connect(self._refresh_plot)
        self.lst_sections.itemSelectionChanged.connect(self._refresh_plot)

        # Eje espejo (se creará on‑demand)
        self.ax2 = None

    # ------------ Helpers para grafica -----------------
    def _ensure_ax2(self):
        """Crea el eje Y secundario si no existe."""
        if getattr(self, "ax2", None) is None:
            self.ax2 = self.canvas.ax.twinx()
            self.ax2.grid(False)
            self.ax2.set_ylabel("Caudal (m³/s) [Y2]")
            # pequeño detalle de estilo para diferenciar
            self.ax2.tick_params(axis='y', labelcolor="#5a7")
            # si usas colorbar en este tab, no afecta

    def _remove_ax2(self):
        """Elimina el eje Y2 si existe."""
        if getattr(self, "ax2", None) is not None:
            try:
                self.ax2.remove()
            except Exception:
                pass
            self.ax2 = None

    def _toggle_y2(self, on: bool):
        """existe."""# ✅ ahora `on` está definido como argumento
        if on:
            if self.ax2 is None or not self.ax2.figure:
                self.ax2 = self.canvas.ax.twinx()
                self.ax2.grid(False)
            # engancha sincronización de límites y ticks
            self._attach_y2_sync()
            self._sync_y2()  # sincroniza ahora mismo
        else:
            # suelta el callback y elimina el eje espejo
            if self._cid_ylim is not None:
                try:
                    self.canvas.ax.callbacks.disconnect(self._cid_ylim)
                except Exception:
                    pass
                self._cid_ylim = None
            if self.ax2 is not None:
                try:
                    self.ax2.remove()
                except Exception:
                    pass
                self.ax2 = None
        self.canvas.draw_idle()

    def _attach_y2_sync(self):
        """Conecta un callback para mantener Y2 idéntico a Y1 tras zoom/pan/redraw."""
        if self._cid_ylim is not None:
            return
        self._cid_ylim = self.canvas.ax.callbacks.connect(
            "ylim_changed", lambda ax: self._sync_y2()
        )

    def _sync_y2(self):
        """Copia límites, posiciones de ticks y etiquetas del eje principal a Y2."""
        if self.ax2 is None:
            return
        ax1 = self.canvas.ax
        ax2 = self.ax2

        # 1) mismos límites
        y0, y1 = ax1.get_ylim()
        ax2.set_ylim(y0, y1)

        # 2) mismas posiciones de ticks (FixedLocator)
        ticks = ax1.get_yticks()
        ax2.yaxis.set_major_locator(mticker.FixedLocator(ticks))

        # 3) mismas etiquetas (FixedFormatter) — respeta formato local
        labels = [t.get_text() for t in ax1.get_yticklabels()]
        # Si estuvieran vacías (aún sin render), formatea numéricamente:
        if not any(labels):
            labels = [ax1.yaxis.get_major_formatter().format_data(t) for t in ticks]
        ax2.yaxis.set_major_formatter(mticker.FixedFormatter(labels))

        # 4) mismo texto del eje y sin grid
        ax2.set_ylabel(ax1.get_ylabel())
        ax2.grid(False)

    def _to_hours_array(self, time_labels: list[str]) -> np.ndarray:
        """Convierte ['0000d 00h 06m 00s', ...] a np.array([horas,...])."""
        out = []
        for tl in time_labels:
            # tolerante: busca d,h,m,s en el string
            m = re.search(r"(\d+)d\s+(\d+)h\s+(\d+)m\s+(\d+)s", tl)
            if not m:
                out.append(np.nan)
                continue
            d, h, mi, s = map(int, m.groups())
            hours = d*24 + h + mi/60 + s/3600
            out.append(hours)
        return np.asarray(out, dtype=float)



    # ------------------- API pública -------------------
    def set_xseci_result(self, res):
        """Recibe el resultado de XSECI (dict meta+data) y arma tiempos, secciones y matrices."""
        if not res or not getattr(res, "data", None):
            # deja la pestaña vacía
            self._times_labels = []
            self._times_hours  = None
            self._sections     = []
            self._matrices     = {}
            self._populate_sections_list()
            self._populate_table()
            self._refresh_plot()
            return

        # 1) tiempos (ordenados)
        times = sorted(res.data.keys())                   # p.ej. ["0000d 00h 06m 00s", ...]
        self._times_labels = times
        # convierte etiqueta → horas (float)
        self._times_hours = self._to_hours_array(times)

        # 2) secciones (unión ordenada)
        sections = sorted({sid for t in times for sid in res.data[t].keys()})
        self._sections = sections

        T, S = len(times), len(sections)
        def _empty(): return np.full((T, S), np.nan, dtype=float)

        # 3) construir matrices por clave interna
        mats: dict[str, np.ndarray] = {
            "Q_XSECI":     _empty(),
            "Q_AJUST":     _empty(),
            "Flow_Width":  _empty(),
            "Depth_Ave":   _empty(),
            "Flow_Elev_Ave": _empty(),
            "Velocity_Ave":  _empty(),
            "Q_Flow":        _empty(),
        }

        # 4) llenar matrices recorriendo (t, s)
        sec_idx = {sid: i for i, sid in enumerate(sections)}
        for it, t in enumerate(times):
            sec_map = res.data.get(t, {})
            for sid, info in sec_map.items():
                js = sec_idx.get(sid)
                if js is None: 
                    continue
                # Q del archivo (puede ser None)
                q_file = info.get("Q")
                if q_file is not None:
                    mats["Q_XSECI"][it, js] = float(q_file)
                # Q ajustado actual (placeholder): usa el tuyo si ya lo tienes
                # Por ahora dejamos 0.0 para mostrar la idea
                mats["Q_AJUST"][it, js] = 0.0

                # Métricas nuevas que ya calcula el parser
                for k in ("Flow_Width", "Depth_Ave", "Flow_Elev_Ave", "Velocity_Ave", "Q_Flow"):
                    val = info.get(k)
                    if val is not None:
                        mats[k][it, js] = float(val)

        self._matrices = mats

        # 5) UI
        self._populate_sections_list()  # refresca lista multi-selección
        self._populate_table()          # tabla con tiempo y columnas por sección, según fuente actual
        self._refresh_plot()            # plotea según fuente actual



    # ----------------- CConstrucción de modelo a partir del resultado XSECI -----------------
    def _build_from_result(self, res):
        """
        Construye:
        - _times_labels: lista de etiquetas "0000d 00h 06m 00s" (ordenada)
        - _times_hours : ndarray float con horas
        - _sections    : lista ids ordenados globalmente
        - _Q_xseci     : matriz T x S con Q leídos (None->NaN)
        - _Q_adj       : matriz T x S (por ahora 0.0 en todos)
        """
        # 1) Tiempos
        times = list(res.meta.get("times", []))
        if not times:
            # Si no estaban en meta, tómalos de las keys para robustez
            times = sorted(res.data.keys())
        self._times_labels = times
        self._times_hours  = np.array([self._time_label_to_hours(t) for t in times], dtype=float)

        # 2) Secciones (unión global)
        all_ids = sorted({sid for t in res.data for sid in res.data[t].keys()})
        self._sections = all_ids

        # 3) Matriz Q_xseci (T,S)
        T, S = len(times), len(all_ids)
        Q = np.full((T, S), np.nan, dtype=float)
        for it, t in enumerate(times):
            sec_map = res.data.get(t, {})
            for is_, sid in enumerate(all_ids):
                sec = sec_map.get(sid)
                if sec is None:
                    continue
                val = sec.get("Q")
                try:
                    Q[it, is_] = float(val) if val is not None else np.nan
                except Exception:
                    Q[it, is_] = np.nan
        self._Q_xseci = Q

        # 4) Matriz Q ajustados (placeholder = 0.0)
        self._Q_adj = np.zeros_like(Q)

    def _current_matrix_key(self) -> str | None:
        """Devuelve la clave interna de la métrica en función del combo 'Fuente'."""
        idx = self.cbo_source.currentIndex()
        if idx < 0:
            return None
        return self._source_items[idx][1]  # p.ej. "Q_XSECI"

    def _current_matrix(self) -> np.ndarray | None:
        key = self._current_matrix_key()
        if not key:
            return None
        return self._matrices.get(key)

    def _ylabel_for_key(self, key: str) -> str:
        return {
            "Q_XSECI":       "Caudal (m³/s)",
            "Q_AJUST":       "Caudal (m³/s)",
            "Flow_Width":    "Ancho (m)",
            "Depth_Ave":     "Tirante (m)",
            "Flow_Elev_Ave": "Cota (m s.n.m.)",
            "Velocity_Ave":  "Velocidad (m/s)",
            "Q_Flow":        "Caudal (m³/s)",
        }.get(key, "Valor")

    def _on_source_changed(self, _i: int):
        self._populate_table()
        self._refresh_plot()
    # ------------------- UI helpers -------------------

    def _populate_sections_list(self):
        """Llena la lista de secciones y las marca todas seleccionadas por defecto."""
        self.lst_sections.blockSignals(True)
        self.lst_sections.clear()
        for sid in self._sections:
            item = QListWidgetItem(sid)
            item.setSelected(True)  # seleccionadas por defecto
            self.lst_sections.addItem(item)
        self.lst_sections.blockSignals(False)

    def _populate_table(self):
        """Rellena la tabla con: tiempo(h) + columnas por sección, usando la fuente actual."""
        M = self._current_matrix()
        if M is None or self._times_hours is None or not self._sections:
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        times = self._times_hours
        sections = self._sections

        self.table.setRowCount(len(times))
        self.table.setColumnCount(len(sections) + 1)
        headers = ["Tiempo (h)"] + sections
        self.table.setHorizontalHeaderLabels(headers)

        for i, t in enumerate(times):
            self.table.setItem(i, 0, QTableWidgetItem(f"{t:.3f}"))
            for j, s in enumerate(sections, start=1):
                val = M[i, j-1]
                self.table.setItem(i, j, QTableWidgetItem("" if np.isnan(val) else f"{val:.6g}"))


    # ----------------- Plot -----------------
    def _refresh_all(self):
        """Cambio de fuente de caudales → actualizar todo."""
        self._populate_table()
        self._refresh_plot()


    def _refresh_plot(self):
        """Grafica la serie seleccionada (fuente) para las secciones seleccionadas."""
        self.canvas.clear()

        if self._times_hours is None or not self._sections:
            self.canvas.ax.set_title("Sin datos")
            self.canvas.draw_idle()
            return

        M = self._current_matrix()
        if M is None:
            self.canvas.ax.set_title("No hay datos para la fuente seleccionada")
            self.canvas.draw_idle()
            return

        times_h = self._times_hours

        # Secciones seleccionadas
        selected = [i.text() for i in self.lst_sections.selectedItems()]
        if not selected:
            self.canvas.ax.set_title("Seleccione al menos una sección")
            self.canvas.draw_idle()
            return

        idx = {sid: i for i, sid in enumerate(self._sections)}

        # plot
        for sid in selected:
            j = idx.get(sid)
            if j is None:
                continue
            y = M[:, j]
            self.canvas.ax.plot(times_h, y, label=sid, linewidth=1.8)

        key = self._current_matrix_key() or ""
        self.canvas.ax.set_title("Serie: " + dict(self._source_items)[self.cbo_source.currentText()]
                                if hasattr(self.cbo_source, "currentText") else "Serie")
        self.canvas.ax.set_xlabel("Tiempo (h)")
        self.canvas.ax.set_ylabel(self._ylabel_for_key(key))
        self.canvas.ax.grid(True, linestyle=":", alpha=0.6)

        handles, _ = self.canvas.ax.get_legend_handles_labels()
        if handles:
            self.canvas.ax.legend(loc="upper right", fontsize=9, frameon=False)

        self.canvas.draw_idle()



    def _current_Q_matrix(self) -> np.ndarray:
        """Devuelve la matriz Q según la fuente seleccionada."""
        if self.cbo_source.currentIndex() == 0:
            return self._Q_xseci if self._Q_xseci is not None else np.empty((0,0))
        return self._Q_adj   if self._Q_adj   is not None else np.empty((0,0))

    def _time_label_to_hours(self, s: str) -> float:
        """
        Convierte '0000d 00h 06m 00s' → horas (float).
        Si tus labels vinieran como '0000 days, 00 hours, 06 min.,00 secs.' 
        adapta el regex según corresponda.
        """
        import re
        m = re.search(r"(\d+)d\s+(\d+)h\s+(\d+)m\s+(\d+)s", s)
        if not m:
            # fallback: 0.0 h si formato inesperado
            return 0.0
        d, h, mm, ss = map(int, m.groups())
        return d*24.0 + h + mm/60.0 + ss/3600.0
    
    def _clear_all_ui(self, title: str):
        self._times_labels = []
        self._times_hours  = None
        self._sections     = []
        self._Q_xseci = None
        self._Q_adj   = None
        self.lst_sections.clear()
        self.table.clear()
        self.table.setRowCount(0); self.table.setColumnCount(0)
        self.canvas.clear(); self.canvas.ax.set_title(title); self.canvas.draw_idle()

# --- WIDGET RAÍZ CON TABS ---

class Flow2DWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        xsecs_tab  = XSECSSectionTab()
        xseci_tab  = XSECITab()
        xsech_tab  = XSECHidrogramaTab()

        tabs.addTab(xsecs_tab, "XSECS")
        tabs.addTab(xseci_tab, "XSECI")
        tabs.addTab(xsech_tab, "XSECH")

        # 🔗 CONEXIÓN CLAVE: cuando XSECI cargue, XSECH recibe el ParseResult
        xseci_tab.dataLoaded.connect(xsech_tab.set_xseci_result)
        
        # (opcional) si al crear el widget XSECI ya tenía algo (p.ej. restaurado),
        # pásalo inmediatamente:
        if getattr(xseci_tab, "result", None):
            xsech_tab.set_xseci_result(xseci_tab.result)
        
        layout.addWidget(tabs)
        self.setLayout(layout)
