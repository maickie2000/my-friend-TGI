# utils/i18n_loader.py
import json
import os
import sys

def cargar_traducciones(idioma):
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    ruta = os.path.join(base_path, "assets", "i18n", f"{idioma}.json")
    
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)
