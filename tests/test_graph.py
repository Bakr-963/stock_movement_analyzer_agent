import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from stock_movement_analyzer.config import RuntimeDependencies, Settings
from stock_movement_analyzer.graph import build_graph
from stock_movement_analyzer.state import StockAnalysisState


class StubModel:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)

    def invoke(self, _messages):
        response = self.responses.pop(0)
        return SimpleNamespace(content=response)


class FakeSearchClient:
    def search(self, *, query: str, max_results: int, include_raw_content: bool):
        del max_results, include_raw_content

        if "AAPL" in query:
            return {
                "results": [
                    {
                        "title": "Reuters covers Apple services growth",
                        "url": "https://www.reuters.com/technology/apple-services-test",
                        "content": "AAPL earnings revenue eps services iphone buyback",
                        "raw_content": "AAPL earnings revenue eps services iphone buyback",
                    }
                ]
            }

        return {
            "results": [
                {
                    "title": "Reuters covers NVIDIA earnings",
                    "url": "https://www.reuters.com/markets/us/nvidia-earnings-test",
                    "content": "earnings revenue eps guidance analyst price target",
                    "raw_content": "earnings revenue eps guidance analyst price target",
                }
            ]
        }


class GraphSmokeTests(unittest.TestCase):
    @patch("stock_movement_analyzer.nodes.get_portfolio_movements")
    def test_graph_invokes_with_fake_dependencies(self, mock_movements) -> None:
        mock_movements.return_value = [
            {
                "ticker": "NVDA",
                "direction": "UP",
                "change_pct": 4.2,
                "current_price": 108.52,
                "prev_price": 104.23,
                "lookback_days": 5,
                "sector": "Technology",
            }
        ]

        dependencies = RuntimeDependencies(
            settings=Settings(tavily_api_key="test-key", max_research_loops=1),
            llm=StubModel(["NVIDIA moved on strong earnings and analyst enthusiasm."]),
            json_llm=StubModel(
                [
                    json.dumps(
                        {
                            "query": "NVDA quarterly earnings results revenue EPS analyst",
                            "target_source_type": "Reuters or SEC filing",
                            "hypothesis": "Earnings drove the move",
                            "rationale": "This query focuses on primary catalysts",
                        }
                    ),
                    json.dumps(
                        {
                            "confidence_pct": 92,
                            "confidence_rationale": "Reuters and earnings data align with the move.",
                            "gap": "Minor detail on analyst target changes.",
                            "missing_source_type": "Analyst note",
                            "follow_up_query": "NVDA analyst upgrade price target Reuters",
                        }
                    ),
                ]
            ),
            tavily_client=FakeSearchClient(),
        )

        graph = build_graph(dependencies=dependencies)
        result = graph.invoke(
            StockAnalysisState(
                tickers=["NVDA"],
                lookback_days=5,
                max_research_loops=1,
                confidence_threshold=80,
            )
        )

        self.assertIn("### NVDA", result["final_report"])
        self.assertEqual(result["ticker_confidences"]["NVDA"], 92)

    @patch("stock_movement_analyzer.nodes.get_portfolio_movements")
    def test_graph_keeps_sources_scoped_to_each_ticker(self, mock_movements) -> None:
        mock_movements.return_value = [
            {
                "ticker": "NVDA",
                "direction": "UP",
                "change_pct": 4.2,
                "current_price": 108.52,
                "prev_price": 104.23,
                "lookback_days": 5,
                "sector": "Technology",
            },
            {
                "ticker": "AAPL",
                "direction": "UP",
                "change_pct": 1.1,
                "current_price": 210.10,
                "prev_price": 207.82,
                "lookback_days": 5,
                "sector": "Technology",
            },
        ]

        dependencies = RuntimeDependencies(
            settings=Settings(tavily_api_key="test-key", max_research_loops=1),
            llm=StubModel(
                [
                    "NVIDIA moved on strong earnings and analyst enthusiasm.",
                    "Apple moved on strong services growth and buyback support.",
                    "## Market Overview\n\nLarge-cap technology gained on company-specific catalysts.",
                ]
            ),
            json_llm=StubModel(
                [
                    json.dumps(
                        {
                            "query": "NVDA quarterly earnings results revenue EPS analyst",
                            "target_source_type": "Reuters or SEC filing",
                            "hypothesis": "Earnings drove the move",
                            "rationale": "This query focuses on primary catalysts",
                        }
                    ),
                    json.dumps(
                        {
                            "confidence_pct": 92,
                            "confidence_rationale": "Reuters and earnings data align with the move.",
                            "gap": "Minor detail on analyst target changes.",
                            "missing_source_type": "Analyst note",
                            "follow_up_query": "NVDA analyst upgrade price target Reuters",
                        }
                    ),
                    json.dumps(
                        {
                            "query": "AAPL quarterly earnings results services revenue buyback",
                            "target_source_type": "Reuters or SEC filing",
                            "hypothesis": "Earnings and services growth drove the move",
                            "rationale": "This query focuses on primary catalysts",
                        }
                    ),
                    json.dumps(
                        {
                            "confidence_pct": 88,
                            "confidence_rationale": "Reuters and earnings context explain the move.",
                            "gap": "No major remaining gaps.",
                            "missing_source_type": "N/A",
                            "follow_up_query": "AAPL services revenue Reuters",
                        }
                    ),
                ]
            ),
            tavily_client=FakeSearchClient(),
        )

        graph = build_graph(dependencies=dependencies)
        result = graph.invoke(
            StockAnalysisState(
                tickers=["NVDA", "AAPL"],
                lookback_days=5,
                max_research_loops=1,
                confidence_threshold=80,
            )
        )

        nvda_report = result["ticker_reports"]["NVDA"]
        aapl_report = result["ticker_reports"]["AAPL"]

        self.assertIn("https://www.reuters.com/markets/us/nvidia-earnings-test", nvda_report)
        self.assertNotIn("https://www.reuters.com/technology/apple-services-test", nvda_report)
        self.assertIn("https://www.reuters.com/technology/apple-services-test", aapl_report)
        self.assertNotIn("https://www.reuters.com/markets/us/nvidia-earnings-test", aapl_report)
