# modules/flow2d/flow2d_xseci.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import re
import pandas as pd

_TIME_RE = re.compile(
    r"TIME:\s*(\d+)\s*days,\s*(\d+)\s*hours,\s*(\d+)\s*min\.,\s*(\d+)\s*secs\.", re.IGNORECASE
)
_SECT_RE = re.compile(
    r"CROSS\s+SECTION\s+NO\.\s*:\s*(\d+)\s+CROSS\s+SECTION\s+ID\s*:\s*(\S+)", re.IGNORECASE
)
_Q_RE = re.compile(r"Q\s*=\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*([A-Za-z0-9^/]+)?", re.IGNORECASE)

WANTED = ["ELEM", "STATION", "BEDEL", "DEPTH", "WSEL",
          "VEL_NORM", "FROUDE", "QS_NORM"]

def _next_nonempty(it) -> str:
    for line in it:
        s = line.strip()
        if s:
            return s
    raise EOFError("Fin de archivo inesperado.")

def _parse_time_label(line: str) -> str:
    m = _TIME_RE.search(line)
    if not m:
        raise ValueError(f"Formato TIME no reconocido: {line!r}")
    d, h, m_, s = map(int, m.groups())
    return f"{d:04d}d {h:02d}h {m_:02d}m {s:02d}s"

def _split_ws(s: str) -> List[str]:
    return re.split(r"\s+", s.strip())

def _build_df_from_rows(header_line: str, units_line: str, data_rows: List[str]) -> tuple[pd.DataFrame, dict]:
    """
    Usa SOLO los encabezados de la 1ª fila (sin unidades) para titular columnas.
    Devuelve (df, units_dict) donde units_dict mapea header->unidad (por si cambia a futuro).
    Más tolerante: normaliza nombres y acepta alias (VELNORM→VEL_NORM, QSNORM→QS_NORM).
    """
    import re

    # Helpers
    def split_ws(s: str) -> List[str]:
        return re.split(r"\s+", s.strip())

    def clean_unit(tok: str) -> str:
        tok = tok.strip()
        if tok.startswith("(") and tok.endswith(")"):
            return tok[1:-1].strip()
        return tok or ""

    def norm_name(s: str) -> str:
        # quita todo menos letras/números/_ y pasa a upper
        return re.sub(r"[^A-Za-z0-9_]+", "", s).upper()

    # 1) Tokenizar encabezados y unidades
    headers = split_ws(header_line)         # p.ej. ["ELEM","STATION","BEDEL",...]
    units_tokens = split_ws(units_line)     # p.ej. ["(m)","(m)","(m)",...]
    n = max(len(headers), len(units_tokens))
    if len(headers) < n: headers += [""] * (n - len(headers))
    if len(units_tokens) < n: units_tokens += [""] * (n - len(units_tokens))

    # 2) Armar units_dict limpio (sin paréntesis)
    units_dict = {}
    for h, u in zip(headers, units_tokens):
        if h:
            units_dict[h] = clean_unit(u)

    # 3) Mapa normalizado -> nombre original
    #    y alias conocidos (sin unidades)
    wanted = ["ELEM", "STATION", "BEDEL", "DEPTH", "WSEL", "VEL_NORM", "FROUDE", "QS_NORM"]
    aliases = {
        "VELNORM": "VEL_NORM",
        "QSNORM": "QS_NORM",
        # por si llegan nombres con puntos o guiones raros
        "VELN": "VEL_NORM",
        "VEL": "VEL_NORM",
    }
    wanted_norm = {norm_name(w): w for w in wanted}
    for k, v in aliases.items():
        wanted_norm[norm_name(k)] = v  # VELNORM -> VEL_NORM

    # Posición -> nombre final (WANTED) usando normalización + alias
    pos_to_final: dict[int, str] = {}
    for i, h in enumerate(headers):
        if not h:
            continue
        nh = norm_name(h)
        if nh in wanted_norm:
            pos_to_final[i] = wanted_norm[nh]

    # 4) Construir en orden WANTED, rellenando faltantes con None
    out = {w: [] for w in wanted}
    numre = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")
    for row in data_rows:
        parts = split_ws(row)
        # Para cada col objetivo, toma el valor en su posición si está mapeada
        for w in wanted:
            # buscar qué posición corresponde a esta col en el archivo
            idx = None
            # encuentra la primera posición cuyos final == w
            for p, final in pos_to_final.items():
                if final == w:
                    idx = p
                    break
            val = parts[idx] if (idx is not None and idx < len(parts)) else None
            if val is None:
                out[w].append(None)
            else:
                out[w].append(float(val) if numre.match(val) else val)

    df = pd.DataFrame(out)
    return df, units_dict



def parse_xseci(path: str | Path) -> Dict[str, Dict[str, Any]]:
    """
    Retorna: data[time_label][section_id] = {
        "coords_text": str,
        "Q": float | None,
        "Q_units": str | None,
        "df": DataFrame con columnas WANTED (las disponibles)
    }
    """
    path = Path(path)
    data: Dict[str, Dict[str, Any]] = {}
    current_time: str | None = None

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        it = iter(f.readlines())

        # Saltar encabezados hasta TIME o marcador de resultados
        while True:
            try:
                line = _next_nonempty(it)
            except EOFError:
                return data
            if line.upper().startswith("TIME:") or "CROSS SECTION RESULTS" in line.upper():
                first = line
                break

        line = first
        while True:
            try:
                if line.upper().startswith("TIME:"):
                    current_time = _parse_time_label(line)
                    data.setdefault(current_time, {})
                    line = _next_nonempty(it)
                    continue

                m = _SECT_RE.search(line)
                if m:
                    sect_id = m.group(2)
                    coords_line = _next_nonempty(it)
                    header_line = _next_nonempty(it)
                    units_line = _next_nonempty(it)
                    #print("[XSECI][DBG] header_line =", header_line)
                    #print("[XSECI][DBG] units_line  =", units_line)

                    rows: List[str] = []
                    while True:
                        candidate = _next_nonempty(it)
                        u = candidate.upper()
                        if u.startswith("Q"):
                            q_match = _Q_RE.search(candidate)
                            Q_val = float(q_match.group(1)) if q_match else None
                            Q_units = q_match.group(2) if (q_match and q_match.group(2)) else None
                            # DEBUG: inspección rápida (temporal)
                            #print("[XSECI][DBG] sample rows:", rows[:3])
                            df, units = _build_df_from_rows(header_line, units_line, rows)
                            # DEBUG — imprime una vez por (tiempo, id):
                            #print(f"[XSECI][DF] sec={sect_id} time={current_time}")
                            #print("[XSECI][DF] cols:", df.columns.tolist())
                            #print("[XSECI][DF] head:\n", df.head(3).to_string(index=False))

                            if current_time is None:
                                current_time = "Unknown"
                                data.setdefault(current_time, {})
                            data[current_time][sect_id] = {
                                "coords_text": coords_line.strip(),
                                "Q": Q_val,
                                "Q_units": Q_units,
                                "units": units,
                                "df": df,
                            }
                            try:
                                line = _next_nonempty(it)
                            except EOFError:
                                line = ""
                            break
                        if u.startswith("CROSS SECTION NO.") or u.startswith("TIME:"):
                            # Guarda sin Q (no apareció) y relanza el flujo con la nueva línea
                            df, units = _build_df_from_rows(header_line, units_line, rows)
                            if current_time is None:
                                current_time = "Unknown"
                                data.setdefault(current_time, {})
                            data[current_time][sect_id] = {
                                "coords_text": coords_line.strip(),
                                "Q": None,
                                "Q_units": None,
                                "units": units,
                                "df": df,
                            }
                            line = candidate
                            break
                        rows.append(candidate)
                    continue

                # Nada especial, sigue
                line = _next_nonempty(it)
            except EOFError:
                break

    return data
