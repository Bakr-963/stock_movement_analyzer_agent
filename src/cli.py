"""Provide a CLI for the stock movement analyzer."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from .config import Settings
from .graph import build_graph
from .state import StockAnalysisState


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Analyze recent stock price movements with Yahoo Finance, Tavily, "
            "LangGraph, and a local LLM."
        )
    )
    parser.add_argument(
        "tickers",
        nargs="+",
        help="Ticker symbols to analyze, such as NVDA AAPL TSLA.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=5,
        help="Trading-day window to measure against. Default: 5.",
    )
    parser.add_argument(
        "--max-research-loops",
        type=int,
        default=None,
        help="Override the max research loop count from the environment.",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=int,
        default=None,
        help="Stop early once confidence reaches this percentage.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional markdown file path for the final report.",
    )
    return parser


def _render_confidence_scores(confidences: dict[str, int]) -> str:
    """Render ticker confidence scores as plain text."""
    lines = ["Confidence Scores", "-" * 30]
    for ticker, confidence in confidences.items():
        bar_length = max(0, min(20, confidence // 5))
        bar = "#" * bar_length + "." * (20 - bar_length)
        lines.append(f"  {ticker}: {confidence:3d}% [{bar}]")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    settings = Settings.from_env()
    if args.max_research_loops is not None:
        settings = replace(settings, max_research_loops=args.max_research_loops)
    if args.confidence_threshold is not None:
        settings = replace(
            settings,
            confidence_threshold=args.confidence_threshold,
        )

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(message)s",
    )

    graph = build_graph(settings=settings)
    initial_state = StockAnalysisState(
        tickers=[ticker.upper().strip() for ticker in args.tickers],
        lookback_days=args.lookback_days,
        max_research_loops=settings.max_research_loops,
        confidence_threshold=settings.confidence_threshold,
    )
    result = graph.invoke(initial_state)
    final_report = result["final_report"]

    if args.output is not None:
        args.output.write_text(final_report, encoding="utf-8")
        logging.getLogger(__name__).info("Saved final report to %s", args.output)

    sys.stdout.write(f"{final_report}\n")
    ticker_confidences = result.get("ticker_confidences", {})
    if ticker_confidences:
        sys.stdout.write("\n")
        sys.stdout.write(_render_confidence_scores(ticker_confidences))
        sys.stdout.write("\n")

    return 0
