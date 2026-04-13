"""Public package exports for the stock movement analyzer."""

from __future__ import annotations

from typing import Any

from .config import Settings
from .state import StockAnalysisState

__all__ = ["Settings", "StockAnalysisState", "build_graph", "graph"]
__version__ = "0.1.0"


def build_graph(*, settings: Any = None, dependencies: Any = None):
    """Build the compiled LangGraph analyzer lazily."""
    from .graph import build_graph as _build_graph

    return _build_graph(settings=settings, dependencies=dependencies)


def __getattr__(name: str) -> Any:
    """Load the compiled graph lazily when requested."""
    if name == "graph":
        from .graph import graph as compiled_graph

        return compiled_graph
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
