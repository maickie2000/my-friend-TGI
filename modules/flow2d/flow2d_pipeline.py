# modules/flow2d/flow2d_pipeline.py
from dataclasses import dataclass
from typing import Dict, Any
from .flow2d_parsers import ParseResult

@dataclass
class Flow2DState:
    variables: Dict[str, Any]

def compute_variables(result: ParseResult) -> Flow2DState:
    #print(f"[PIPELINE] compute_variables(meta={result.meta})")
    # Fantasma: deriva variables mínimas
    vars_min = {
        "source": result.meta.get("source"),
        "type": result.meta.get("type"),
        "n_sections": result.meta.get("n_sections", 0),
        "ids": result.meta.get("ids", []),
    }
    #print(f"[PIPELINE] derivado -> {vars_min}")
    return Flow2DState(variables=vars_min)
