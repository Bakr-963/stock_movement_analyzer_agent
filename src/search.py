"""Handle Tavily search and source formatting."""

from __future__ import annotations

from typing import Any, Iterable

from tavily import TavilyClient


def _iter_results(search_response: dict[str, Any] | list[Any]) -> Iterable[dict[str, Any]]:
    """Yield result dictionaries from Tavily-like responses."""
    if isinstance(search_response, dict):
        yield from search_response.get("results", [])
        return

    for response in search_response:
        if isinstance(response, dict) and "results" in response:
            yield from response["results"]
        elif isinstance(response, list):
            yield from response
        elif isinstance(response, dict):
            yield response


def search_web(
    client: TavilyClient | None,
    query: str,
    *,
    include_raw_content: bool = True,
    max_results: int = 5,
) -> dict[str, Any]:
    """Search the web with Tavily."""
    if client is None:
        raise RuntimeError(
            "Tavily search is not configured. Set TAVILY_API_KEY before running the analyzer."
        )

    return client.search(
        query=query,
        max_results=max_results,
        include_raw_content=include_raw_content,
    )


def deduplicate_and_format_sources(
    search_response: dict[str, Any] | list[Any],
    *,
    max_tokens_per_source: int = 1000,
    include_raw_content: bool = True,
) -> str:
    """Format search results as an LLM-ready source bundle."""
    unique_sources: dict[str, dict[str, Any]] = {}
    for source in _iter_results(search_response):
        url = source.get("url")
        if url and url not in unique_sources:
            unique_sources[url] = source

    formatted_parts = ["Sources:", ""]
    char_limit = max_tokens_per_source * 4

    for source in unique_sources.values():
        credibility = source.get("credibility", {})
        tier_label = credibility.get("tier_label", "UNKNOWN")
        score = credibility.get("score", "?")

        formatted_parts.extend(
            [
                f"Source {source.get('title', 'Untitled')}:",
                "===",
                f"URL: {source.get('url', 'N/A')}",
                f"CREDIBILITY: {tier_label} (score: {score}/100)",
                "===",
                (
                    "Most relevant content from source: "
                    f"{source.get('content', '')}"
                ),
                "===",
            ]
        )

        if include_raw_content:
            raw_content = source.get("raw_content", "") or ""
            if len(raw_content) > char_limit:
                raw_content = f"{raw_content[:char_limit]}... [truncated]"
            formatted_parts.append(
                "Full source content limited to "
                f"{max_tokens_per_source} tokens: {raw_content}"
            )
            formatted_parts.append("")

    return "\n".join(formatted_parts).strip()


def format_sources(search_results: dict[str, Any]) -> str:
    """Format search results as a markdown bullet list."""
    lines = []
    for source in search_results.get("results", []):
        credibility = source.get("credibility", {})
        tier_label = credibility.get("tier_label", "?")
        score = credibility.get("score", "?")
        lines.append(
            f"* [{tier_label} {score}/100] "
            f"{source.get('title', 'Untitled')} : {source.get('url', 'N/A')}"
        )
    return "\n".join(lines)
