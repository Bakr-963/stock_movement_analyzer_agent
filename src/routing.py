"""Route between stock-analysis graph nodes."""

from __future__ import annotations

import logging
from typing import Literal

from .state import StockAnalysisState

logger = logging.getLogger(__name__)


def route_research(
    state: StockAnalysisState,
) -> Literal["save_ticker_report", "search_and_filter_news"]:
    """Decide whether to continue researching the current ticker."""
    ticker = state.stock_movements[state.current_ticker_index]["ticker"]

    if (
        state.research_loop_count >= 1
        and state.confidence_pct >= state.confidence_threshold
    ):
        logger.info(
            "[%s] Confidence %s%% reached the %s%% threshold.",
            ticker,
            state.confidence_pct,
            state.confidence_threshold,
        )
        return "save_ticker_report"

    if state.research_loop_count >= state.max_research_loops:
        logger.info(
            "[%s] Hit max research loops (%s) at %s%% confidence.",
            ticker,
            state.max_research_loops,
            state.confidence_pct,
        )
        return "save_ticker_report"

    return "search_and_filter_news"


def route_next_ticker(
    state: StockAnalysisState,
) -> Literal["generate_stock_query", "compile_final_report"]:
    """Move to the next ticker or finish the report."""
    if state.current_ticker_index < len(state.stock_movements):
        return "generate_stock_query"
    return "compile_final_report"
