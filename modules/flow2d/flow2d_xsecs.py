from pathlib import Path
from typing import Dict, Any
import pandas as pd

def parse_xsecs(path: str | Path) -> Dict[str, Dict[str, Any]]:
    """
    Lee un archivo .XSECS y devuelve un diccionario:
      {
        "XSEC_1": {
          "n_vertices_ctrl": int,
          "n_vertices_xsec": int,
          "coords": pd.DataFrame(columns=["x","y"])  # una fila por vértice
        },
        ...
      }
    Acceso individual: sections["XSEC_ID"]["coords"]
    """
    path = Path(path)
    sections: Dict[str, Dict[str, Any]] = {}

    # Utilidad: leer siguiente línea "no vacía"
    def _next_line(lines_iter) -> str:
        for line in lines_iter:
            s = line.strip()
            if s:  # salta líneas vacías
                return s
        raise EOFError("Fin de archivo inesperado.")

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        lines = iter(f.readlines())

        # 1) número total de secciones (lo usamos como referencia; no es obligatorio para el bucle)
        total_declared = int(_next_line(lines))

        # 2) leer bloques de secciones
        count = 0
        while True:
            try:
                section_id = _next_line(lines)                # p.ej. "XSEC_1"
                nums_line = _next_line(lines)                 # p.ej. "2  100"
                n_ctrl, n_xsec = map(int, nums_line.split())

                # 3) leer coordenadas
                xs, ys = [], []
                for _ in range(n_ctrl):
                    xy = _next_line(lines).replace(",", " ")  # por si hay comas sueltas
                    x_str, y_str = xy.split()
                    xs.append(float(x_str))
                    ys.append(float(y_str))

                coords_df = pd.DataFrame({"x": xs, "y": ys})
                coords_df.index = range(1, n_ctrl + 1)        # índice 1..n_ctrl (útil para referenciar vértices)

                # 4) guardar sección (acceso individual por ID)
                if section_id in sections:
                    raise ValueError(f"ID duplicado de sección: {section_id}")
                sections[section_id] = {
                    "n_vertices_ctrl": n_ctrl,
                    "n_vertices_xsec": n_xsec,
                    "coords": coords_df,
                }

                count += 1
            except EOFError:
                break  # llegamos al final

        # (Opcional) validación suave con el declarado
        if count != total_declared:
            # No detenemos: solo avisamos para que puedas revisarlo si te interesa
            print(f"[Aviso] Se declararon {total_declared} secciones, pero se leyeron {count}.")

    return sections
