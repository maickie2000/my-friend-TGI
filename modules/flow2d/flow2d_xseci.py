# modules/flow2d/flow2d_xseci.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import re
import numpy as np
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

class ParseCancelled(Exception):
    """Señal interna para cortar parsing por cancelación del usuario."""
    pass

## Nuevas funciones opcionales? 20250927
def _normalize_header_name(name: str) -> str:
    """Quita espacios y paréntesis para comparar encabezados con/ sin unidades."""
    return name.replace(" ", "").replace("(", "").replace(")", "").upper()
def _best_match_column(df: pd.DataFrame, candidates: List[str]) -> str | None:
    """
    Devuelve el nombre real de columna en df que coincide con alguno de los 'candidates'
    (tolerando variantes con/ sin unidades). Si no hay match, None.
    """
    norm_cols = { _normalize_header_name(c): c for c in df.columns }

    for cand in candidates:
        norm_cand = _normalize_header_name(cand)
        # 1) match exacto normalizado
        if norm_cand in norm_cols:
            return norm_cols[norm_cand]
        # 2) match por prefijo razonable (por si hay "STATION" vs "STATIONm")
        for ncol, orig in norm_cols.items():
            if ncol.startswith(norm_cand):
                return orig
    return None
def _get_series(df: pd.DataFrame, candidates: List[str]) -> np.ndarray | None:
    """
    Intenta extraer una columna (como float) probando nombres con y sin unidades.
    Devuelve np.ndarray o None si no la encuentra.
    """
    col = _best_match_column(df, candidates)
    if col is None:
        return None
    # tolera strings con espacios, etc.
    try:
        return pd.to_numeric(df[col], errors="coerce").to_numpy()
    except Exception:
        return None
#Nuevas funcione de calculo:
def Calc_Flow_Width(df: pd.DataFrame) -> float | None:
    """
    Ancho de inundación (valor de prueba):
    máx(STATION) - mín(STATION) considerando solo filas con DEPTH > 0.
    """
    st = _get_series(df, ["STATION(m)", "STATION"])
    dep = _get_series(df, ["DEPTH(m)", "DEPTH"])
    if st is None or dep is None:
        return None
    mask = (dep > 0) & np.isfinite(st)
    if not np.any(mask):
        return 0.0
    return float(np.nanmax(st[mask]) - np.nanmin(st[mask]))

def Calc_Depth_Ave(df: pd.DataFrame) -> float | None:
    """
    Tirante promedio (valor de prueba):
    promedio(DEPTH) sobre filas con VEL_NORM > 0.
    """
    dep = _get_series(df, ["DEPTH(m)", "DEPTH"])
    vel = _get_series(df, ["VEL_NORM(m/s)", "VEL_NORM"])
    if dep is None or vel is None:
        return None
    mask = (vel > 0)
    vals = dep[mask]
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return 0.0
    return float(np.nanmean(vals))

def Calc_Flow_Elev_Ave(df: pd.DataFrame) -> float | None:
    """
    Cota de agua promedio (valor de prueba):
    promedio(WSEL) sobre filas con VEL_NORM > 0.
    """
    wsl = _get_series(df, ["WSEL(m)", "WSEL"])
    vel = _get_series(df, ["VEL_NORM(m/s)", "VEL_NORM"])
    if wsl is None or vel is None:
        return None
    mask = (vel > 0)
    vals = wsl[mask]
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return 0.0
    return float(np.nanmean(vals))

def Calc_Velocity_Ave(df: pd.DataFrame) -> float | None:
    """
    Velocidad promedio (valor de prueba):
    promedio(VEL_NORM) sobre filas con VEL_NORM > 0.
    """
    vel = _get_series(df, ["VEL_NORM(m/s)", "VEL_NORM"])
    if vel is None:
        return None
    vals = vel[vel > 0]
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return 0.0
    return float(np.nanmean(vals))

def Calc_Q_Flow(df: pd.DataFrame) -> float | None:
    """
    Caudal (valor de prueba):
    Q = sum(vel * depth * Δx), con Δx = diff(STATION).
    Usa filas donde DEPTH>0 y VEL_NORM>0.
    """
    st  = _get_series(df, ["STATION(m)", "STATION"])
    dep = _get_series(df, ["DEPTH(m)", "DEPTH"])
    vel = _get_series(df, ["VEL_NORM(m/s)", "VEL_NORM"])
    if st is None or dep is None or vel is None:
        return None

    # Δx (alínea última con 0 para igualar tamaños)
    dx = np.diff(st, prepend=st[0])
    dx[dx < 0] = 0  # por si hay ruido/orden no monótono

    mask = (dep > 0) & (vel > 0) & np.isfinite(dx)
    if not np.any(mask):
        return 0.0

    return float(np.nansum(vel[mask] * dep[mask] * dx[mask]))




#############################

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


"""
def parse_xseci(path: str | Path) -> Dict[str, Dict[str, Any]]:
    
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

"""

# parse_xseci(path, progress_cb=None, cancel_cb=None)
# - progress_cb(done_bytes:int, total_bytes:int) -> None
# - cancel_cb() -> bool  # True si hay que cancelar

def parse_xseci(path: str | Path,
                progress_cb=None,
                cancel_cb=None) -> Dict[str, Dict[str, Any]]:
    """
    Retorna: data[time_label][section_id] = {
        "coords_text": str,
        "Q": float | None,         # Q reportado por el archivo (si viene la línea Q=...)
        "Q_units": str | None,
        "units": Dict[str,str],    # unidades por columna
        "df": DataFrame,
        # --- NUEVAS MÉTRICAS ---
        "Flow_Width": float | None,
        "Depth_Ave": float | None,
        "Flow_Elev_Ave": float | None,
        "Velocity_Ave": float | None,
        "Q_Flow": float | None,    # Q calculado (valor de prueba)
    }
    """
    path = Path(path)

    #BARRA DE PROCESO DE LECTURA
    total_bytes = path.stat().st_size if path.exists() else 0
    if progress_cb and total_bytes > 0:
        progress_cb(0, total_bytes)      # tick inicial (0%)

    done_bytes = 0

    def _tick_progress(new_bytes: int = 0):
        nonlocal done_bytes
        done_bytes += new_bytes
        if progress_cb and total_bytes > 0:
            progress_cb(done_bytes, total_bytes)
        if cancel_cb and cancel_cb():
            raise ParseCancelled()

    data: Dict[str, Dict[str, Any]] = {}
    current_time: str | None = None



    with path.open("r", encoding="utf-8", errors="ignore") as f:
        # leemos línea a línea para medir bytes
        def _safe_readline():
            line = f.readline()
            if not line:
                raise EOFError
            _tick_progress(len(line.encode("utf-8", errors="ignore")))
            return line

        # reimplementa tu _next_nonempty pero usando _safe_readline()
        def _next_nonempty():
            while True:
                s = _safe_readline()
                s2 = s.strip()
                if s2:
                    return s2

        # --- aquí reutiliza tu lógica actual, pero usa _next_nonempty()
        # y donde iteres líneas, llama a _safe_readline() para sumar bytes.
        # Cuando cierres un bloque de sección/tiempo, no olvides que _tick_progress
        # ya lo estás llamando por cada línea leída.

        # Saltar encabezados hasta TIME o CROSS SECTION RESULTS
        while True:
            try:
                line = _next_nonempty()
            except EOFError:
                return data
            if line.upper().startswith("TIME:") or "CROSS SECTION RESULTS" in line.upper():
                first = line
                break

        line = first
        while True:
            try:
                #Cambio de tiempo
                if line.upper().startswith("TIME:"):
                    current_time = _parse_time_label(line)  # tu función actual
                    data.setdefault(current_time, {})
                    line = _next_nonempty()
                    continue
                #Cambio de sección
                m = _SECT_RE.search(line)  # tu regex actual
                if m:
                    sect_id = m.group(2)
                    coords_line = _next_nonempty()
                    header_line = _next_nonempty()
                    units_line  = _next_nonempty()

                    rows: list[str] = []
                    while True:
                        candidate = _next_nonempty()
                        u = candidate.upper()
                        # Cierre por línea de Q (caso más común)
                        if u.startswith("Q"):
                            q_match = _Q_RE.search(candidate)
                            Q_val   = float(q_match.group(1)) if q_match else None
                            Q_units = q_match.group(2) if (q_match and q_match.group(2)) else None
                            df, units = _build_df_from_rows(header_line, units_line, rows)
                            # --- NUEVAS MÉTRICAS ---
                            Flow_Width     = Calc_Flow_Width(df)
                            Depth_Ave      = Calc_Depth_Ave(df)
                            Flow_Elev_Ave  = Calc_Flow_Elev_Ave(df)
                            Velocity_Ave   = Calc_Velocity_Ave(df)
                            Q_Flow         = Calc_Q_Flow(df)

                            if current_time is None:
                                current_time = "Unknown"
                                data.setdefault(current_time, {})
                            data[current_time][sect_id] = {
                                "coords_text": coords_line.strip(),
                                "Q": Q_val,
                                "Q_units": Q_units,
                                "units": units,
                                "df": df,
                                # nuevas
                                "Flow_Width": Flow_Width,
                                "Depth_Ave": Depth_Ave,
                                "Flow_Elev_Ave": Flow_Elev_Ave,
                                "Velocity_Ave": Velocity_Ave,
                                "Q_Flow": Q_Flow,
                            }
                            try:
                                line = _next_nonempty()
                            except EOFError:
                                line = ""
                            break
                        # Cierre por inicio de otra sección o nuevo TIME
                        if u.startswith("CROSS SECTION NO.") or u.startswith("TIME:"):
                            df, units = _build_df_from_rows(header_line, units_line, rows)
                            # --- NUEVAS MÉTRICAS ---
                            Flow_Width     = Calc_Flow_Width(df)
                            Depth_Ave      = Calc_Depth_Ave(df)
                            Flow_Elev_Ave  = Calc_Flow_Elev_Ave(df)
                            Velocity_Ave   = Calc_Velocity_Ave(df)
                            Q_Flow         = Calc_Q_Flow(df)

                            if current_time is None:
                                current_time = "Unknown"
                                data.setdefault(current_time, {})
                            data[current_time][sect_id] = {
                                "coords_text": coords_line.strip(),
                                "Q": None,
                                "Q_units": None,
                                "units": units,
                                "df": df,
                                # nuevas
                                "Flow_Width": Flow_Width,
                                "Depth_Ave": Depth_Ave,
                                "Flow_Elev_Ave": Flow_Elev_Ave,
                                "Velocity_Ave": Velocity_Ave,
                                "Q_Flow": Q_Flow,
                            }
                            line = candidate
                            break
                        # Sigue acumulando filas del bloque de tabla
                        rows.append(candidate)
                    continue

                # Nada especial → próxima línea
                line = _next_nonempty()
            except EOFError:
                break

    return data


