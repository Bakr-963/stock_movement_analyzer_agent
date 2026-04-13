import unittest

from stock_movement_analyzer.routing import route_next_ticker, route_research
from stock_movement_analyzer.state import StockAnalysisState


class RoutingTests(unittest.TestCase):
    def test_route_research_stops_after_threshold(self) -> None:
        state = StockAnalysisState(
            stock_movements=[{"ticker": "NVDA"}],
            research_loop_count=1,
            confidence_pct=85,
            confidence_threshold=80,
        )

        self.assertEqual(route_research(state), "save_ticker_report")

    def test_route_research_continues_when_more_evidence_is_needed(self) -> None:
        state = StockAnalysisState(
            stock_movements=[{"ticker": "NVDA"}],
            research_loop_count=0,
            confidence_pct=42,
            confidence_threshold=80,
            max_research_loops=3,
        )

        self.assertEqual(route_research(state), "search_and_filter_news")

    def test_route_next_ticker_compiles_after_last_ticker(self) -> None:
        state = StockAnalysisState(
            stock_movements=[{"ticker": "NVDA"}],
            current_ticker_index=1,
        )

        self.assertEqual(route_next_ticker(state), "compile_final_report")
