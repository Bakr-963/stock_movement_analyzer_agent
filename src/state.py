"""Define graph state and shared stock-analysis types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypedDict

Direction = Literal["UP", "DOWN", "FLAT"]


class StockMovement(TypedDict, total=False):
    """Describe a single stock's recent price movement."""

    ticker: str
    current_price: float
    prev_price: float
    change_pct: float
    direction: Direction
    period_high: float
    period_low: float
    volume_avg: int
    lookback_days: int
    sector: str
    error: str


@dataclass(kw_only=True)
class StockAnalysisState:
    """Track a multi-ticker stock analysis workflow."""

    # User inputs
    tickers: list[str] = field(default_factory=list)
    lookback_days: int = field(default=5)
    max_research_loops: int = field(default=3)
    confidence_threshold: int = field(default=80)

    # Price data
    stock_movements: list[StockMovement] = field(default_factory=list)

    # Per-ticker loop state
    current_ticker_index: int = field(default=0)
    search_query: str | None = field(default=None)
    web_research_results: list[str] = field(default_factory=list)
    sources_gathered: list[str] = field(default_factory=list)
    research_loop_count: int = field(default=0)
    running_summary: str | None = field(default=None)
    confidence_pct: int = field(default=0)
    best_source_tier: int = field(default=4)

    # Final outputs
    ticker_reports: dict[str, str] = field(default_factory=dict)
    ticker_confidences: dict[str, int] = field(default_factory=dict)
    final_report: str | None = field(default=None)
