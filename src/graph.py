"""Build and export the stock movement analysis graph."""

from __future__ import annotations

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from .config import RuntimeDependencies, Settings, build_dependencies
from .nodes import GraphNodes
from .routing import route_next_ticker, route_research
from .state import StockAnalysisState


def build_graph(
    *,
    settings: Settings | None = None,
    dependencies: RuntimeDependencies | None = None,
):
    """Build a compiled LangGraph stock-analysis graph."""
    load_dotenv()
    resolved_dependencies = dependencies or build_dependencies(settings)
    nodes = GraphNodes(resolved_dependencies)

    builder = StateGraph(StockAnalysisState)
    builder.add_node("fetch_prices", nodes.fetch_prices)
    builder.add_node("generate_stock_query", nodes.generate_stock_query)
    builder.add_node("search_and_filter_news", nodes.search_and_filter_news)
    builder.add_node("analyze_movement", nodes.analyze_movement)
    builder.add_node("reflect_and_deepen", nodes.reflect_and_deepen)
    builder.add_node("save_ticker_report", nodes.save_ticker_report)
    builder.add_node("compile_final_report", nodes.compile_final_report)

    builder.add_edge(START, "fetch_prices")
    builder.add_edge("fetch_prices", "generate_stock_query")
    builder.add_edge("generate_stock_query", "search_and_filter_news")
    builder.add_edge("search_and_filter_news", "analyze_movement")
    builder.add_edge("analyze_movement", "reflect_and_deepen")
    builder.add_conditional_edges("reflect_and_deepen", route_research)
    builder.add_conditional_edges("save_ticker_report", route_next_ticker)
    builder.add_edge("compile_final_report", END)

    return builder.compile()


graph = build_graph()
