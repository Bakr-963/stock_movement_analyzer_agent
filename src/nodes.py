"""Implement LangGraph nodes for stock movement analysis."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from .config import RuntimeDependencies
from .credibility import filter_and_score_results
from .market_data import get_portfolio_movements
from .prompts import (
    ANALYSIS_PROMPT,
    FINAL_REPORT_PROMPT,
    QUERY_GEN_PROMPT,
    REFLECTION_PROMPT,
)
from .search import deduplicate_and_format_sources, format_sources, search_web
from .state import StockAnalysisState, StockMovement

logger = logging.getLogger(__name__)
JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _coerce_content(content: Any) -> str:
    """Convert model content payloads into plain text."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
            elif item is not None:
                parts.append(str(item))
        return "\n".join(parts)

    return str(content)


def _parse_json_payload(content: str) -> dict[str, Any]:
    """Parse a JSON object from raw model output."""
    normalized = content.strip()
    match = JSON_BLOCK_PATTERN.search(normalized)
    if match:
        normalized = match.group(1).strip()
    return json.loads(normalized)


def _fallback_query(movement: StockMovement) -> str:
    """Build a safe follow-up query for a ticker."""
    ticker = movement.get("ticker", "UNKNOWN")
    return f"{ticker} stock earnings SEC filing analyst price target news"


class GraphNodes:
    """Bind graph node functions to runtime dependencies."""

    def __init__(self, dependencies: RuntimeDependencies) -> None:
        """Initialize a node bundle with external dependencies."""
        self.dependencies = dependencies
        self.settings = dependencies.settings

    def _invoke_json(self, system_prompt: str, human_prompt: str) -> dict[str, Any]:
        """Invoke the JSON-oriented model and parse the response."""
        result = self.dependencies.json_llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt),
            ]
        )
        content = _coerce_content(result.content)
        return _parse_json_payload(content)

    def _reset_ticker_research_state(self, *, next_ticker_index: int) -> dict[str, Any]:
        """Clear transient research fields before the next ticker starts."""
        return {
            "current_ticker_index": next_ticker_index,
            "research_loop_count": 0,
            "running_summary": None,
            "web_research_results": [],
            "sources_gathered": [],
            "search_query": None,
            "confidence_pct": 0,
            "best_source_tier": 4,
        }

    def fetch_prices(self, state: StockAnalysisState) -> dict[str, Any]:
        """Pull price data for every ticker in the request."""
        movements = get_portfolio_movements(state.tickers, state.lookback_days)
        logger.info("Fetched price data for %s tickers.", len(movements))

        for movement in movements:
            if "error" in movement:
                logger.warning(
                    "[%s] %s",
                    movement.get("ticker", "UNKNOWN"),
                    movement["error"],
                )
                continue

            logger.info(
                "[%s] $%s -> $%s (%s %s%%)",
                movement.get("ticker", "UNKNOWN"),
                movement.get("prev_price", "?"),
                movement.get("current_price", "?"),
                movement.get("direction", "?"),
                movement.get("change_pct", "?"),
            )

        return {"stock_movements": movements}

    def generate_stock_query(self, state: StockAnalysisState) -> dict[str, Any]:
        """Create an authoritative search query for the current ticker."""
        movement = state.stock_movements[state.current_ticker_index]
        if "error" in movement:
            return {"search_query": _fallback_query(movement)}

        prompt = QUERY_GEN_PROMPT.format(
            ticker=movement["ticker"],
            direction=movement["direction"],
            change_pct=movement["change_pct"],
            current_price=movement["current_price"],
            prev_price=movement["prev_price"],
            lookback_days=movement["lookback_days"],
            today=datetime.now().strftime("%B %d, %Y"),
        )
        query_data = self._invoke_json(prompt, "Generate the search query now.")

        query = query_data.get("query") or _fallback_query(movement)
        logger.info("[%s] Search query: %s", movement["ticker"], query)
        target_source = query_data.get("target_source_type", "N/A")
        hypothesis = query_data.get("hypothesis", "N/A")
        logger.info("[%s] Target source: %s", movement["ticker"], target_source)
        logger.info("[%s] Hypothesis: %s", movement["ticker"], hypothesis)

        return {"search_query": query}

    def search_and_filter_news(self, state: StockAnalysisState) -> dict[str, Any]:
        """Search the web and keep the most credible sources."""
        raw_results = search_web(
            self.dependencies.tavily_client,
            state.search_query or "",
            include_raw_content=True,
            max_results=self.settings.search_max_results,
        )
        filtered_results = filter_and_score_results(raw_results, min_score=30)
        credibility_summary = filtered_results.get("credibility_summary", {})
        search_text = deduplicate_and_format_sources(
            filtered_results,
            max_tokens_per_source=self.settings.max_tokens_per_source,
        )
        formatted_sources = format_sources(filtered_results)

        ticker = state.stock_movements[state.current_ticker_index].get("ticker", "UNKNOWN")
        kept = credibility_summary.get("kept", 0)
        dropped = credibility_summary.get("dropped", 0)
        best_tier = credibility_summary.get("best_tier", 4)
        logger.info(
            "[%s] Sources kept: %s, dropped: %s (loop %s).",
            ticker,
            kept,
            dropped,
            state.research_loop_count + 1,
        )

        for dropped_source in credibility_summary.get("dropped_sources", []):
            logger.debug(
                "[%s] Dropped %s (%s)",
                ticker,
                dropped_source.get("url", "unknown"),
                dropped_source.get("reason", "no reason provided"),
            )

        new_best = min(state.best_source_tier, best_tier)
        return {
            "sources_gathered": state.sources_gathered + [formatted_sources],
            "research_loop_count": state.research_loop_count + 1,
            "web_research_results": state.web_research_results + [search_text],
            "best_source_tier": new_best,
        }

    def analyze_movement(self, state: StockAnalysisState) -> dict[str, Any]:
        """Explain the stock move using the gathered research."""
        movement = state.stock_movements[state.current_ticker_index]
        most_recent_research = state.web_research_results[-1]
        existing_summary = state.running_summary

        analysis_prompt = ANALYSIS_PROMPT.format(
            ticker=movement.get("ticker", "???"),
            direction=movement.get("direction", "???"),
            change_pct=movement.get("change_pct", "???"),
            lookback_days=movement.get("lookback_days", "???"),
            prev_price=movement.get("prev_price", "???"),
            current_price=movement.get("current_price", "???"),
        )

        if existing_summary:
            human_prompt = (
                f"Extend the existing analysis:\n{existing_summary}\n\n"
                "New search results (with credibility scores):\n"
                f"{most_recent_research}"
            )
        else:
            human_prompt = (
                "Analyze these search results and explain the price movement:\n"
                f"{most_recent_research}"
            )

        result = self.dependencies.llm.invoke(
            [
                SystemMessage(content=analysis_prompt),
                HumanMessage(content=human_prompt),
            ]
        )
        return {"running_summary": _coerce_content(result.content)}

    def reflect_and_deepen(self, state: StockAnalysisState) -> dict[str, Any]:
        """Assign confidence, identify gaps, and propose the next query."""
        movement = state.stock_movements[state.current_ticker_index]
        prompt = REFLECTION_PROMPT.format(
            ticker=movement.get("ticker", "???"),
            direction=movement.get("direction", "???"),
            change_pct=movement.get("change_pct", "???"),
            running_summary=state.running_summary,
            best_source_tier=state.best_source_tier,
            sector=movement.get("sector", "the company's sector"),
        )
        reflection = self._invoke_json(
            prompt,
            "Assess the analysis and assign a confidence percentage.",
        )

        try:
            confidence = int(float(reflection.get("confidence_pct", 0)))
        except (TypeError, ValueError):
            confidence = 0
        confidence = max(0, min(100, confidence))

        ticker = movement.get("ticker", "UNKNOWN")
        logger.info(
            "[%s] Confidence: %s%% | Gap: %s",
            ticker,
            confidence,
            reflection.get("gap", "N/A"),
        )
        logger.info(
            "[%s] Rationale: %s",
            ticker,
            reflection.get("confidence_rationale", "N/A"),
        )

        follow_up_query = reflection.get("follow_up_query") or _fallback_query(movement)
        return {
            "search_query": follow_up_query,
            "confidence_pct": confidence,
        }

    def save_ticker_report(self, state: StockAnalysisState) -> dict[str, Any]:
        """Save the completed report for the current ticker."""
        movement = state.stock_movements[state.current_ticker_index]
        ticker = movement.get("ticker", "UNKNOWN")
        confidence = state.confidence_pct

        if confidence >= 80:
            badge = "HIGH CONFIDENCE"
        elif confidence >= 50:
            badge = "MODERATE CONFIDENCE"
        else:
            badge = "LOW CONFIDENCE -- treat with skepticism"

        move_line = (
            f"Moved {movement.get('direction', '?')} {movement.get('change_pct', '?')}% "
            f"over {movement.get('lookback_days', '?')} days "
            f"(${movement.get('prev_price', '?')} -> ${movement.get('current_price', '?')})"
        )
        all_sources = "\n".join(state.sources_gathered)
        report = "\n".join(
            [
                f"### {ticker}",
                f"*{move_line}*",
                "",
                state.running_summary or "No summary was generated.",
                "",
                f"**Confidence:** {confidence}% ({badge})",
                "",
                "**Sources (credibility-scored):**",
                all_sources,
            ]
        ).strip()

        updated_reports = dict(state.ticker_reports)
        updated_reports[ticker] = report

        updated_confidences = dict(state.ticker_confidences)
        updated_confidences[ticker] = confidence

        logger.info("[%s] Analysis complete at %s%% confidence.", ticker, confidence)
        return {
            "ticker_reports": updated_reports,
            "ticker_confidences": updated_confidences,
            **self._reset_ticker_research_state(
                next_ticker_index=state.current_ticker_index + 1
            ),
        }

    def compile_final_report(self, state: StockAnalysisState) -> dict[str, Any]:
        """Compile the final portfolio report."""
        all_analyses = "\n\n---\n\n".join(
            state.ticker_reports[movement["ticker"]]
            for movement in state.stock_movements
            if movement.get("ticker") in state.ticker_reports
        )

        if len(state.ticker_reports) <= 1:
            return {"final_report": all_analyses}

        result = self.dependencies.llm.invoke(
            [
                SystemMessage(content=FINAL_REPORT_PROMPT),
                HumanMessage(content=f"Individual stock analyses:\n\n{all_analyses}"),
            ]
        )
        overview = _coerce_content(result.content).strip()

        final_sections = [
            overview,
            f"## Detailed Per-Ticker Reports\n\n{all_analyses}",
        ]

        final = "\n\n---\n\n".join(section for section in final_sections if section)
        return {"final_report": final}
