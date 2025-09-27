# test.py
# Interactive checker for parse_xseci with file dialog + console menu (ASCII-safe).

from __future__ import annotations
import sys
from pathlib import Path
import traceback

# --- Imports base ---
import pandas as pd

# Try to import from project layout
try:
    from modules.flow2d.flow2d_xseci import parse_xseci, ParseCancelled
except Exception:
    # If run from another folder, add repo root to sys.path
    repo_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(repo_root))
    from modules.flow2d.flow2d_xseci import parse_xseci, ParseCancelled

# --- GUI for file dialogs (Windows-friendly) ---
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    _HAS_TK = True
except Exception:
    _HAS_TK = False

# ------------------ Helpers ------------------

def _progress(done: int, total: int):
    if total:
        pct = 100.0 * done / total
        print(f"[INFO] Reading... {pct:5.1f}%", end="\r")

def open_xseci_dialog() -> Path | None:
    if not _HAS_TK:
        print("[ERR] Tkinter not available. Please install tkinter or run from Python with Tk support.")
        return None
    root = tk.Tk()
    root.withdraw()
    root.update()
    path = filedialog.askopenfilename(
        title="Select XSECI results file",
        filetypes=[
            ("Text files", "*.out *.txt *.dat *.lst"),
            ("All files", "*.*"),
        ]
    )
    root.destroy()
    return Path(path) if path else None

def save_output_dialog(default_name: str) -> Path | None:
    if not _HAS_TK:
        return None
    root = tk.Tk(); root.withdraw(); root.update()
    path = filedialog.asksaveasfilename(
        title="Save output (CSV or Excel)",
        initialfile=default_name,
        defaultextension=".csv",
        filetypes=[("CSV", "*.csv"), ("Excel", "*.xlsx")]
    )
    root.destroy()
    return Path(path) if path else None

def flatten_data(data: dict) -> pd.DataFrame:
    rows = []
    for time_label, sections in data.items():
        for sect_id, payload in sections.items():
            Q_rep = payload.get("Q", None)
            Q_units = payload.get("Q_units", None)
            Flow_Width    = payload.get("Flow_Width", None)
            Depth_Ave     = payload.get("Depth_Ave", None)
            Flow_Elev_Ave = payload.get("Flow_Elev_Ave", None)
            Velocity_Ave  = payload.get("Velocity_Ave", None)
            Q_Flow        = payload.get("Q_Flow", None)

            err_pct = None
            try:
                if Q_rep is not None and Q_Flow is not None and abs(Q_rep) > 0:
                    err_pct = 100.0 * (Q_Flow - Q_rep) / Q_rep
            except Exception:
                err_pct = None

            rows.append({
                "time": time_label,
                "section": sect_id,
                "Q_reported": Q_rep,
                "Q_units": Q_units,
                "Q_Flow": Q_Flow,
                "err_pct_QFlow_vs_Q": err_pct,
                "Flow_Width": Flow_Width,
                "Depth_Ave": Depth_Ave,
                "Flow_Elev_Ave": Flow_Elev_Ave,
                "Velocity_Ave": Velocity_Ave,
            })
    if not rows:
        return pd.DataFrame(columns=[
            "time","section","Q_reported","Q_units","Q_Flow","err_pct_QFlow_vs_Q",
            "Flow_Width","Depth_Ave","Flow_Elev_Ave","Velocity_Ave"
        ])
    df = pd.DataFrame(rows)
    df = df.sort_values(["time", "section"], kind="stable").reset_index(drop=True)
    return df

def build_time_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    grp = df.groupby("time", as_index=False).agg(
        sections=("section", "count"),
        Q_rep_sum=("Q_reported", "sum"),
        Q_flow_sum=("Q_Flow", "sum"),
    )
    with pd.option_context("mode.use_inf_as_na", True):
        grp["err_pct_sum"] = (grp["Q_flow_sum"] - grp["Q_rep_sum"]) / grp["Q_rep_sum"].replace(0, pd.NA) * 100.0
    return grp

def list_times(data: dict) -> list[str]:
    return list(data.keys())

def list_sections_for_time(data: dict, time_label: str) -> list[str]:
    return list(data.get(time_label, {}).keys())

def show_df_head(df: pd.DataFrame, limit: int = 50):
    if df.empty:
        print("[WARN] No data to show.")
        return
    with pd.option_context("display.max_rows", limit, "display.max_columns", None, "display.width", 140):
        print(df.head(limit).to_string(index=False))

def safe_input(prompt: str) -> str:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""

# ------------------ Main Menu ------------------

def main():
    print("[INFO] Select XSECI results file using Windows dialog.")
    path = open_xseci_dialog()
    if not path:
        print("[WARN] No file selected. Exiting.")
        return
    if not path.exists():
        print(f"[ERR] File not found: {path}")
        return

    print(f"[INFO] File: {path}")

    # Parse
    try:
        data = parse_xseci(path, progress_cb=_progress, cancel_cb=None)
    except ParseCancelled:
        print("\n[WARN] Parse cancelled.")
        return
    except Exception as e:
        print("\n[ERR] Parser failed.")
        print(str(e))
        print("[DBG] Traceback:")
        traceback.print_exc()
        return

    print("\n[OK] Parse completed.")

    # Precompute flat table and summary (can rebuild on demand if needed)
    flat_df = flatten_data(data)
    time_summary = build_time_summary(flat_df)
    preview_limit = 50

    # Menu loop
    while True:
        print("\n===== MENU =====")
        print("1) Preview sections table (flat)")
        print("2) Show time summary (sum Q)")
        print("3) Inspect one section (show metrics and DF head)")
        print("4) Export table (CSV/Excel) with optional time filter")
        print("5) Change preview limit (current =", preview_limit, ")")
        print("6) List times and sections quickly")
        print("0) Exit")
        choice = safe_input("Select option: ").strip()

        if choice == "1":
            if flat_df.empty:
                print("[WARN] Empty table.")
            else:
                print("[INFO] Preview (limited):")
                show_df_head(flat_df, preview_limit)

        elif choice == "2":
            if time_summary.empty:
                print("[WARN] No summary available.")
            else:
                print("[INFO] Time summary (sum by time):")
                with pd.option_context("display.max_rows", None, "display.width", 120):
                    print(time_summary.to_string(index=False))

        elif choice == "3":
            # Pick time
            times = list_times(data)
            if not times:
                print("[WARN] No times found.")
                continue
            print("[INFO] Available times:")
            for i, t in enumerate(times):
                print(f"  [{i}] {t}")
            t_idx = safe_input("Pick time index: ").strip()
            if not t_idx.isdigit() or int(t_idx) < 0 or int(t_idx) >= len(times):
                print("[ERR] Invalid selection.")
                continue
            t_sel = times[int(t_idx)]

            # Pick section
            secs = list_sections_for_time(data, t_sel)
            if not secs:
                print("[WARN] No sections for the selected time.")
                continue
            print(f"[INFO] Sections at time {t_sel}:")
            for i, s in enumerate(secs):
                print(f"  [{i}] {s}")
            s_idx = safe_input("Pick section index: ").strip()
            if not s_idx.isdigit() or int(s_idx) < 0 or int(s_idx) >= len(secs):
                print("[ERR] Invalid selection.")
                continue
            s_sel = secs[int(s_idx)]

            payload = data[t_sel][s_sel]
            # Metrics
            Q_rep = payload.get("Q")
            Q_units = payload.get("Q_units")
            Flow_Width    = payload.get("Flow_Width")
            Depth_Ave     = payload.get("Depth_Ave")
            Flow_Elev_Ave = payload.get("Flow_Elev_Ave")
            Velocity_Ave  = payload.get("Velocity_Ave")
            Q_Flow        = payload.get("Q_Flow")

            err_pct = None
            try:
                if Q_rep is not None and Q_Flow is not None and abs(Q_rep) > 0:
                    err_pct = 100.0 * (Q_Flow - Q_rep) / Q_rep
            except Exception:
                err_pct = None

            print("\n[INFO] Section metrics:")
            print(f"  time            : {t_sel}")
            print(f"  section         : {s_sel}")
            print(f"  Q_reported      : {Q_rep} [{Q_units}]")
            print(f"  Q_Flow          : {Q_Flow}")
            print(f"  err_pct(QFlow-Q): {err_pct}")
            print(f"  Flow_Width      : {Flow_Width}")
            print(f"  Depth_Ave       : {Depth_Ave}")
            print(f"  Flow_Elev_Ave   : {Flow_Elev_Ave}")
            print(f"  Velocity_Ave    : {Velocity_Ave}")

            # Show DF head (from parser payload)
            df = payload.get("df")
            if isinstance(df, pd.DataFrame) and not df.empty:
                print("\n[INFO] DF head (WANTED columns):")
                show_df_head(df, preview_limit)
            else:
                print("[WARN] No DF for this section.")

        elif choice == "4":
            # Optional filter by time
            do_filter = safe_input("Filter by one time? (y/n): ").strip().lower()
            if do_filter == "y":
                times = list_times(data)
                if not times:
                    print("[WARN] No times found.")
                    continue
                print("[INFO] Available times:")
                for i, t in enumerate(times):
                    print(f"  [{i}] {t}")
                t_idx = safe_input("Pick time index: ").strip()
                if not t_idx.isdigit() or int(t_idx) < 0 or int(t_idx) >= len(times):
                    print("[ERR] Invalid selection.")
                    continue
                t_sel = times[int(t_idx)]
                df_to_save = flat_df[flat_df["time"] == t_sel].copy()
                summary_to_save = build_time_summary(df_to_save)
                default_name = f"xseci_metrics_{t_sel.replace(' ','_').replace(':','-')}.csv"
            else:
                df_to_save = flat_df.copy()
                summary_to_save = time_summary.copy()
                default_name = "xseci_metrics.csv"

            out_path = save_output_dialog(default_name) if _HAS_TK else None
            if out_path is None:
                # fallback ask in console
                p = safe_input("Output path (leave empty to cancel): ").strip()
                if not p:
                    print("[WARN] Cancelled.")
                    continue
                out_path = Path(p)

            try:
                if out_path.suffix.lower() in (".xlsx", ".xls"):
                    with pd.ExcelWriter(out_path, engine="xlsxwriter") as w:
                        df_to_save.to_excel(w, sheet_name="xseci_sections", index=False)
                        if not summary_to_save.empty:
                            summary_to_save.to_excel(w, sheet_name="time_summary", index=False)
                    print(f"[OK] Excel saved: {out_path}")
                else:
                    df_to_save.to_csv(out_path, index=False)
                    print(f"[OK] CSV saved: {out_path}")
            except Exception as e:
                print(f"[ERR] Could not save output: {e}")

        elif choice == "5":
            new_lim = safe_input("New preview limit (int): ").strip()
            if new_lim.isdigit() and int(new_lim) > 0:
                preview_limit = int(new_lim)
                print(f"[OK] Preview limit set to {preview_limit}")
            else:
                print("[ERR] Invalid number.")

        elif choice == "6":
            times = list_times(data)
            if not times:
                print("[WARN] No times found.")
                continue
            print("[INFO] Times:")
            for i, t in enumerate(times):
                print(f"  [{i}] {t}")
            # Optional show sections for one time
            do_sec = safe_input("Show sections for one time? (y/n): ").strip().lower()
            if do_sec == "y":
                idx = safe_input("Pick time index: ").strip()
                if idx.isdigit() and 0 <= int(idx) < len(times):
                    t_sel = times[int(idx)]
                    secs = list_sections_for_time(data, t_sel)
                    print(f"[INFO] Sections at {t_sel}:")
                    for j, s in enumerate(secs):
                        print(f"  [{j}] {s}")
                else:
                    print("[ERR] Invalid index.")

        elif choice == "0":
            print("[INFO] Bye.")
            break
        else:
            print("[ERR] Unknown option.")

if __name__ == "__main__":
    main()




