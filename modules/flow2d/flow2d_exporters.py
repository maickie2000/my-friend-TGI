# modules/flow2d/flow2d_exporters.py
from typing import Protocol
from .flow2d_parsers import ParseResult
from .flow2d_pipeline import Flow2DState

class Exporter(Protocol):
    name: str
    def export(self, result: ParseResult, state: Flow2DState, out_path: str) -> None: ...

class CSVAllLinesExporter:
    name = "CSV (todo)"
    def export(self, result: ParseResult, state: Flow2DState, out_path: str) -> None:
        print(f"[EXPORT] {self.name} -> {out_path}")
        print(f"[EXPORT] meta={result.meta}")
        print(f"[EXPORT] (stub) escribiría CSV con todas las líneas/filas pertinentes")

class JSONSummaryExporter:
    name = "JSON (resumen)"
    def export(self, result: ParseResult, state: Flow2DState, out_path: str) -> None:
        print(f"[EXPORT] {self.name} -> {out_path}")
        print(f"[EXPORT] variables={state.variables}")
        print(f"[EXPORT] (stub) escribiría un JSON con resumen/variables")
