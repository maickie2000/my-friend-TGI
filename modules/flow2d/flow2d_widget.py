# modules/flow2d/flow2d_widget.py
"""Flow 2D: tabs XSECS, XSECI, XSECH (modo fantasma con prints)."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QToolBar, QFileDialog,
    QPlainTextEdit, QMessageBox, QToolButton, QMenu,
    QHBoxLayout, QLabel, QComboBox, QTableWidget, QTableWidgetItem
)  # type: ignore
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QPushButton, QSplitter  # type: ignore
from PyQt6.QtCore import Qt

# matplotlib embebido
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas  # type: ignore
from matplotlib.figure import Figure  # type: ignore


from PyQt6.QtGui import QAction  # type: ignore
import os

from .flow2d_factory import get_parser
from .flow2d_parsers import ParseResult
from .flow2d_pipeline import compute_variables, Flow2DState
from .flow2d_exporters import CSVAllLinesExporter, JSONSummaryExporter

class PlotCanvas(FigureCanvas):
    """Canvas de Matplotlib embebido en PyQt para dibujar polilíneas X-Y."""
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self._setup()

    def _setup(self):
        self.ax.set_title("Plano X-Y (XSECS)")
        self.ax.set_xlabel("X")
        self.ax.set_ylabel("Y")
        self.ax.grid(True, linestyle=":", alpha=0.6)

    def clear(self):
        self.ax.clear()
        self._setup()
        self.draw_idle()

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
        self.canvas = PlotCanvas(self)  # (clase que agregaste en el paso 2)

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

     

class Flow2DWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        # 🔽 Reemplaza la pestaña XSECS por la versión con combo+tabla
        tabs.addTab(XSECSSectionTab(), "XSECS")
        tabs.addTab(_BaseSectionTab("XSECI", "XSECI"), "XSECI")
        tabs.addTab(_BaseSectionTab("XSECH", "XSECH"), "XSECH")

        layout.addWidget(tabs)
        self.setLayout(layout)
