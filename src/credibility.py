"""Score source credibility for stock movement research."""

from __future__ import annotations

from typing import Any, TypedDict
from urllib.parse import urlparse


class CredibilityRating(TypedDict):
    """Represent a scored source-credibility result."""

    url: str
    score: int
    tier: int
    tier_label: str
    reason: str


TIER_1_DOMAINS = {
    "sec.gov",
    "edgar.sec.gov",
    "federalreserve.gov",
    "bls.gov",
    "bea.gov",
    "treasury.gov",
    "earningswhispers.com",
    "apnews.com",
    "reuters.com",
}

TIER_2_DOMAINS = {
    "bloomberg.com",
    "wsj.com",
    "ft.com",
    "cnbc.com",
    "marketwatch.com",
    "nytimes.com",
    "washingtonpost.com",
    "economist.com",
    "barrons.com",
    "morningstar.com",
    "spglobal.com",
    "fitchratings.com",
    "moodys.com",
}

TIER_3_DOMAINS = {
    "finance.yahoo.com",
    "seekingalpha.com",
    "fool.com",
    "investopedia.com",
    "thestreet.com",
    "investors.com",
    "benzinga.com",
    "zacks.com",
    "tipranks.com",
    "businessinsider.com",
    "forbes.com",
}

BLACKLISTED_DOMAINS = {
    "medium.com",
    "substack.com",
    "reddit.com",
    "twitter.com",
    "x.com",
    "stocktwits.com",
    "quora.com",
    "wikipedia.org",
    "investorplace.com",
    "247wallst.com",
}


def _extract_domain(url: str) -> str:
    """Extract a normalized domain from a URL."""
    try:
        domain = urlparse(url).netloc.lower()
    except ValueError:
        return ""

    if domain.startswith("www."):
        return domain[4:]
    return domain


def _domain_matches_tier(domain: str, tier_set: set[str]) -> bool:
    """Check whether a domain belongs to a credibility tier."""
    if domain in tier_set:
        return True
    return any(domain.endswith(f".{tier_domain}") for tier_domain in tier_set)


def _is_investor_relations(url: str) -> bool:
    """Detect whether a URL looks like an investor-relations page."""
    investor_relations_signals = (
        "investor",
        "/ir/",
        "/ir.",
        "investors.",
        "sec-filings",
        "press-release",
        "press_release",
        "newsroom",
        "/news/",
    )
    url_lower = url.lower()
    return any(signal in url_lower for signal in investor_relations_signals)


def score_source(url: str, title: str = "", content: str = "") -> CredibilityRating:
    """Score a source by credibility and financial specificity."""
    domain = _extract_domain(url)

    if _domain_matches_tier(domain, BLACKLISTED_DOMAINS):
        return {
            "url": url,
            "score": 0,
            "tier": 4,
            "tier_label": "BLACKLISTED",
            "reason": f"{domain} is a blacklisted source",
        }

    if _is_investor_relations(url):
        return {
            "url": url,
            "score": 95,
            "tier": 1,
            "tier_label": "PRIMARY",
            "reason": "Company investor relations or press-release page",
        }

    if _domain_matches_tier(domain, TIER_1_DOMAINS):
        return {
            "url": url,
            "score": 95,
            "tier": 1,
            "tier_label": "PRIMARY",
            "reason": f"{domain} is an official or primary source",
        }

    if _domain_matches_tier(domain, TIER_2_DOMAINS):
        return {
            "url": url,
            "score": 80,
            "tier": 2,
            "tier_label": "TRUSTED",
            "reason": f"{domain} is top-tier financial press",
        }

    if _domain_matches_tier(domain, TIER_3_DOMAINS):
        return {
            "url": url,
            "score": 55,
            "tier": 3,
            "tier_label": "ACCEPTABLE",
            "reason": f"{domain} is a known financial site with lower rigor",
        }

    content_lower = f"{content} {title}".lower()
    financial_signals = (
        "earnings",
        "revenue",
        "eps",
        "guidance",
        "sec filing",
        "analyst",
        "upgrade",
        "downgrade",
        "price target",
        "quarterly results",
        "10-k",
        "10-q",
        "8-k",
    )
    signal_hits = sum(1 for signal in financial_signals if signal in content_lower)

    if signal_hits >= 3:
        return {
            "url": url,
            "score": 35,
            "tier": 4,
            "tier_label": "UNVERIFIED",
            "reason": (
                f"{domain} is unknown but has potentially relevant financial "
                f"signals ({signal_hits})"
            ),
        }

    return {
        "url": url,
        "score": 10,
        "tier": 4,
        "tier_label": "JUNK",
        "reason": f"{domain} is unknown with weak financial substance",
    }


def filter_and_score_results(
    search_response: dict[str, Any],
    min_score: int = 30,
) -> dict[str, Any]:
    """Filter search results by credibility and annotate the survivors."""
    raw_results = search_response.get("results", [])
    results: list[dict[str, Any]] = [dict(result) for result in raw_results]
    scored_results: list[tuple[int, dict[str, Any]]] = []

    for result in results:
        credibility = score_source(
            result.get("url", ""),
            result.get("title", ""),
            result.get("content", ""),
        )
        result["credibility"] = credibility
        scored_results.append((credibility["score"], result))

    scored_results.sort(key=lambda item: item[0], reverse=True)

    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for score, result in scored_results:
        if score >= min_score:
            kept.append(result)
        else:
            dropped.append(result)

    if not kept and scored_results:
        _, best_result = scored_results[0]
        kept = [best_result]
        dropped = [result for _, result in scored_results[1:]]

    filtered_response = dict(search_response)
    filtered_response["results"] = kept
    filtered_response["credibility_summary"] = {
        "kept": len(kept),
        "dropped": len(dropped),
        "dropped_sources": [
            {
                "url": result.get("url", ""),
                "reason": result.get("credibility", {}).get("reason", ""),
            }
            for result in dropped
        ],
        "best_tier": min(
            result.get("credibility", {}).get("tier", 4) for result in kept
        )
        if kept
        else 4,
    }
    return filtered_response
