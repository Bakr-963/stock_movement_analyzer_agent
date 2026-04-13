"""Fetch market data for stock movement analysis."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import yfinance as yf

from .state import StockMovement

logger = logging.getLogger(__name__)


def _lookup_sector(stock: yf.Ticker) -> str | None:
    """Look up the sector for a stock, if available."""
    try:
        info = stock.info or {}
    except Exception as exc:  # pragma: no cover - depends on remote API state.
        logger.debug("Failed to fetch sector metadata: %s", exc)
        return None

    for key in ("sectorDisp", "sector"):
        value = info.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def get_stock_movement(ticker: str, lookback_days: int = 5) -> StockMovement:
    """Fetch recent price data and summarize the move for one ticker."""
    normalized_ticker = ticker.upper().strip()
    stock = yf.Ticker(normalized_ticker)
    end = datetime.now()
    start = end - timedelta(days=lookback_days + 5)

    try:
        history = stock.history(start=start, end=end)
    except Exception as exc:  # pragma: no cover - depends on remote API state.
        logger.exception("Failed to fetch price history for %s", normalized_ticker)
        return {
            "ticker": normalized_ticker,
            "error": f"Failed to fetch price history: {exc}",
        }

    close_prices = history.get("Close")
    if close_prices is None:
        return {"ticker": normalized_ticker, "error": "Close-price data was missing"}

    close_prices = close_prices.dropna()
    if close_prices.empty or len(close_prices) < 2:
        return {"ticker": normalized_ticker, "error": "Not enough price data found"}

    reference_index = -lookback_days if len(close_prices) >= lookback_days else 0
    current_price = float(close_prices.iloc[-1])
    previous_price = float(close_prices.iloc[reference_index])
    change_pct = ((current_price - previous_price) / previous_price) * 100

    movement: StockMovement = {
        "ticker": normalized_ticker,
        "current_price": round(current_price, 2),
        "prev_price": round(previous_price, 2),
        "change_pct": round(change_pct, 2),
        "direction": (
            "UP"
            if change_pct > 0
            else "DOWN"
            if change_pct < 0
            else "FLAT"
        ),
        "period_high": round(float(close_prices.max()), 2),
        "period_low": round(float(close_prices.min()), 2),
        "volume_avg": int(history["Volume"].dropna().mean()),
        "lookback_days": lookback_days,
    }

    sector = _lookup_sector(stock)
    if sector:
        movement["sector"] = sector

    return movement


def get_portfolio_movements(
    tickers: list[str],
    lookback_days: int = 5,
) -> list[StockMovement]:
    """Fetch recent movements for a list of tickers."""
    return [get_stock_movement(ticker, lookback_days) for ticker in tickers]
