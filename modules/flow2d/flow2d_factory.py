# modules/flow2d/flow2d_factory.py
from .flow2d_parsers import XSECSParser, XSECIParser, XSECHParser, BaseParser

def get_parser(ext: str) -> BaseParser:
    e = ext.upper().lstrip(".")
    print(f"[FACTORY] parser para: {e}")
    if e == "XSECS":
        return XSECSParser()
    if e == "XSECI":
        return XSECIParser()
    if e == "XSECH":
        return XSECHParser()
    raise ValueError(f"Extensión no soportada: {ext}")
