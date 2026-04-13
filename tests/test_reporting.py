import unittest
from types import SimpleNamespace

from stock_movement_analyzer.config import RuntimeDependencies, Settings
from stock_movement_analyzer.nodes import GraphNodes
from stock_movement_analyzer.state import StockAnalysisState


class StubModel:
    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = list(responses or [])

    def invoke(self, _messages):
        response = self.responses.pop(0) if self.responses else ""
        return SimpleNamespace(content=response)


class ReportingTests(unittest.TestCase):
    def _make_nodes(
        self,
        *,
        llm_responses: list[str] | None = None,
        json_responses: list[str] | None = None,
    ) -> GraphNodes:
        settings = Settings(tavily_api_key="test-key")
        dependencies = RuntimeDependencies(
            settings=settings,
            llm=StubModel(llm_responses),
            json_llm=StubModel(json_responses),
            tavily_client=None,
        )
        return GraphNodes(dependencies)

    def test_save_ticker_report_places_confidence_after_summary(self) -> None:
        nodes = self._make_nodes()
        state = StockAnalysisState(
            stock_movements=[
                {
                    "ticker": "NVDA",
                    "direction": "UP",
                    "change_pct": 4.2,
                    "lookback_days": 5,
                    "prev_price": 104.23,
                    "current_price": 108.52,
                }
            ],
            current_ticker_index=0,
            running_summary="NVIDIA moved on strong earnings and AI demand.",
            confidence_pct=88,
            sources_gathered=["* [PRIMARY 95/100] Reuters : https://reuters.com/test"],
        )

        result = nodes.save_ticker_report(state)
        report = result["ticker_reports"]["NVDA"]

        self.assertIn("### NVDA", report)
        self.assertLess(
            report.index("NVIDIA moved on strong earnings and AI demand."),
            report.index("**Confidence:**"),
        )

    def test_save_ticker_report_resets_transient_state_for_next_ticker(self) -> None:
        nodes = self._make_nodes()
        state = StockAnalysisState(
            stock_movements=[
                {
                    "ticker": "NVDA",
                    "direction": "UP",
                    "change_pct": 4.2,
                    "lookback_days": 5,
                    "prev_price": 104.23,
                    "current_price": 108.52,
                },
                {
                    "ticker": "AAPL",
                    "direction": "UP",
                    "change_pct": 1.1,
                    "lookback_days": 5,
                    "prev_price": 207.82,
                    "current_price": 210.10,
                },
            ],
            current_ticker_index=0,
            running_summary="NVIDIA moved on strong earnings and AI demand.",
            confidence_pct=88,
            search_query="NVDA Reuters earnings",
            research_loop_count=2,
            web_research_results=["Sources:\n\nNVDA result"],
            sources_gathered=["* [PRIMARY 95/100] Reuters : https://reuters.com/test"],
            best_source_tier=1,
        )

        result = nodes.save_ticker_report(state)

        self.assertEqual(result["current_ticker_index"], 1)
        self.assertEqual(result["research_loop_count"], 0)
        self.assertIsNone(result["running_summary"])
        self.assertEqual(result["web_research_results"], [])
        self.assertEqual(result["sources_gathered"], [])
        self.assertIsNone(result["search_query"])
        self.assertEqual(result["confidence_pct"], 0)
        self.assertEqual(result["best_source_tier"], 4)

    def test_compile_final_report_omits_confidence_snapshot(self) -> None:
        nodes = self._make_nodes(
            llm_responses=[
                "## Market Overview\n\nAI infrastructure outperformed while defensives held up well."
            ]
        )
        state = StockAnalysisState(
            stock_movements=[{"ticker": "NVDA"}, {"ticker": "AAPL"}],
            ticker_reports={
                "NVDA": "### NVDA\n\nReport one",
                "AAPL": "### AAPL\n\nReport two",
            },
            ticker_confidences={"NVDA": 92, "AAPL": 76},
        )

        result = nodes.compile_final_report(state)
        final_report = result["final_report"]

        self.assertIn("## Detailed Per-Ticker Reports", final_report)
        self.assertNotIn("## Confidence Snapshot", final_report)
