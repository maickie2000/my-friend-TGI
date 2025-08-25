# modules/flow2d/flow2d_parsers.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
import os

# Import real del lector XSECS (ya actualizado por ti)
from .flow2d_xsecs import parse_xsecs  # debe estar en el PYTHONPATH del proyecto

from .flow2d_xseci import parse_xseci, ParseCancelled  # ⬅️ NUEVO

@dataclass
class ParseResult:
    """Resultado normalizado del parseo."""
    meta: Dict[str, Any]
    data: Any  # p.ej., dict[str, dict[str, Any]] con "coords" (DataFrame), etc.


class BaseParser:
    """Interfaz base simple para parsers de Flow2D."""
    tipo = "BASE"

    def parse(self, path: str) -> ParseResult:
        raise NotImplementedError(f"{self.__class__.__name__}.parse() no implementado")


class XSECIParser(BaseParser):
    """Parser para .XSECI."""
    tipo = "XSECI"

    def parse(self, path: str, progress_cb=None, cancel_cb=None) -> ParseResult:
        print(f"[{self.tipo}] Iniciando parseo: {path}")
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"[{self.tipo}] Ruta inválida: {path!r}")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"[{self.tipo}] No existe el archivo: {path}")

        data = parse_xseci(path, progress_cb=progress_cb, cancel_cb=cancel_cb)
        times = list(data.keys())
        ids = sorted({sid for t in times for sid in data[t].keys()})
        meta = {"type": self.tipo, "source": path, "times": times, "ids": ids}
        print(f"[{self.tipo}] OK: tiempos={len(times)}, secciones únicas={len(ids)}")
        return ParseResult(meta=meta, data=data)

class XSECSParser(BaseParser):
    """Parser para archivos .XSECS (secciones transversales)."""
    tipo = "XSECS"

    def parse(self, path: str) -> ParseResult:
        print(f"[{self.tipo}] Iniciando parseo: {path}")

        # Validaciones previas de seguridad
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"[{self.tipo}] Ruta inválida: {path!r}")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"[{self.tipo}] No existe el archivo: {path}")

        try:
            sections = parse_xsecs(path)  # ← tu implementación real
            if not isinstance(sections, dict):
                raise TypeError(f"[{self.tipo}] El parser devolvió un tipo inesperado: {type(sections)!r}")

            ids = sorted(sections.keys())
            n_sections = len(ids)
            #print(f"[{self.tipo}] OK: {n_sections} secciones. Preview IDs: {ids[:5]}{'...' if n_sections > 5 else ''}")

            meta = {
                "type": self.tipo,
                "source": path,
                "n_sections": n_sections,
                "ids": ids,
            }
            return ParseResult(meta=meta, data=sections)

        except (ValueError, EOFError, FileNotFoundError) as e:
            # Errores esperables del parser/IO: re-lanzar con contexto
            print(f"[{self.tipo}] Error controlado: {e}")
            raise
        except Exception as e:
            # Cualquier otra excepción inesperada
            print(f"[{self.tipo}] Error inesperado: {e}")
            raise



class XSECHParser(BaseParser):
    """Parser para .XSECH (stub por ahora)."""
    tipo = "XSECH"

    def parse(self, path: str) -> ParseResult:
        print(f"[{self.tipo}] (stub) parseo no implementado aún: {path}")
        raise NotImplementedError(f"[{self.tipo}] Parser pendiente de implementación")
