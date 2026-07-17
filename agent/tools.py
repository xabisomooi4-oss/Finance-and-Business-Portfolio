"""Tools the LLM Agent can call. Each tool wraps functions already built and
validated in data.py / indicators.py / backtest.py / drift_check.py -- the
Agent never invents numbers, it only reasons over what these return.
"""

import numpy as np
import pandas as pd
import yfinance as yf

from data import get_price_history
from indicators import (
    add_moving_averages, detect_crossovers, add_rsi,
    add_ma_spread, add_volume_ratio, add_trend_persistence,
)
from backtest import prepare_data, run_backtest, buy_and_hold_return_pct
from drift_check import check_drift

DEFAULT_WATCHLIST = ["NVDA", "AAPL", "MSFT", "TSLA", "AMD", "GOOGL"]


def _clean(value):
    """Recursively convert numpy/pandas types to plain Python so results are
    JSON-serializable for the API."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return round(float(value), 4)
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    return value


def tool_get_current_signal(ticker: str) -> dict:
    """Latest indicator snapshot: where price sits relative to the 20/50-day
    moving averages, RSI, MA spread, volume ratio, and trend persistence.
    """
    df = prepare_data(ticker, period="2y")
    latest = df.iloc[-1]

    if latest["trend_persistence"] > 0:
        trend_state = f"price has closed above both moving averages for {int(latest['trend_persistence'])} straight day(s)"
    elif latest["trend_persistence"] < 0:
        trend_state = f"price has closed below both moving averages for {abs(int(latest['trend_persistence']))} straight day(s)"
    else:
        trend_state = "price is sitting between the two moving averages -- no clear side"

    return _clean({
        "ticker": ticker.upper(),
        "as_of_date": latest.name if isinstance(latest.name, str) else df.index[-1],
        "close": latest["Close"],
        "ma_20": latest["MA_20"],
        "ma_50": latest["MA_50"],
        "ma_spread_pct": latest["ma_spread_pct"],
        "rsi_14": latest["RSI_14"],
        "volume_ratio": latest["volume_ratio"],
        "trend_persistence_days": latest["trend_persistence"],
        "trend_state": trend_state,
        "golden_cross_today": latest["golden_cross"],
        "death_cross_today": latest["death_cross"],
    })


def tool_get_recent_crossovers(ticker: str, lookback_days: int = 500, forward_days: int = 10) -> list:
    """Past golden/death cross events with their confirmation metrics AND
    what actually happened in the following `forward_days` trading days --
    grounds the Agent's reasoning in how similar past signals played out,
    not just theory.
    """
    df = prepare_data(ticker, period="5y").tail(lookback_days + 60)
    events = df[df["golden_cross"] | df["death_cross"]].copy()

    results = []
    for idx in events.index:
        pos = df.index.get_loc(idx)
        row = df.loc[idx]
        forward_pos = pos + forward_days
        if forward_pos < len(df):
            forward_return_pct = (df.iloc[forward_pos]["Close"] / row["Close"] - 1) * 100
        else:
            forward_return_pct = None

        results.append(_clean({
            "date": idx,
            "type": "golden_cross" if row["golden_cross"] else "death_cross",
            "close": row["Close"],
            "rsi_14": row["RSI_14"],
            "ma_spread_pct": row["ma_spread_pct"],
            "trend_persistence_days": row["trend_persistence"],
            f"forward_{forward_days}d_return_pct": forward_return_pct,
        }))
    return results


def tool_get_backtest_summary(
    ticker: str,
    period: str = "5y",
    spread_threshold: float = None,
    rsi_threshold: float = None,
    persistence_threshold: int = None,
) -> dict:
    """Backtested performance of the crossover strategy (optionally with
    confirmation filters) vs. simply buying and holding over the same period.
    """
    df = prepare_data(ticker, period=period)
    result = run_backtest(
        df, spread_threshold=spread_threshold,
        rsi_threshold=rsi_threshold, persistence_threshold=persistence_threshold,
    )
    return _clean({
        "ticker": ticker.upper(),
        "period": period,
        "filters_applied": {
            "spread_threshold": spread_threshold,
            "rsi_threshold": rsi_threshold,
            "persistence_threshold": persistence_threshold,
        },
        "total_return_pct": result["total_return_pct"],
        "sharpe_ratio": result["sharpe_ratio"],
        "max_drawdown_pct": result["max_drawdown_pct"],
        "num_trades": result["num_trades"],
        "win_rate_pct": result["win_rate_pct"],
        "buy_and_hold_return_pct": buy_and_hold_return_pct(df),
    })


def tool_get_drift_status(ticker: str, period: str = "5y", recent_window_days: int = 90) -> dict:
    """Whether the strategy's recent behavior still matches what it was
    validated on, or shows signs of the edge decaying."""
    df = prepare_data(ticker, period=period)
    n = len(df)
    reference_window = (0, int(n * 0.8))
    live_params = dict(spread_threshold=None, rsi_threshold=None, persistence_threshold=None)
    result = check_drift(df, live_params, reference_window, recent_window_days=recent_window_days)
    return _clean(result)


def tool_scan_watchlist(tickers: list = None) -> list:
    """Compact signal + backtest snapshot for several tickers at once, done
    as one fast local pass (not one LLM tool call per ticker) so ranking a
    watchlist doesn't require dozens of round trips. Use this before
    producing any kind of ranked list or "best trades" summary."""
    if not tickers:
        tickers = DEFAULT_WATCHLIST

    results = []
    for t in tickers:
        try:
            df = prepare_data(t, period="1y")
            latest = df.iloc[-1]
            bt = run_backtest(df)
            bh = buy_and_hold_return_pct(df)
            results.append(_clean({
                "ticker": t.upper(),
                "close": latest["Close"],
                "rsi_14": latest["RSI_14"],
                "ma_spread_pct": latest["ma_spread_pct"],
                "trend_persistence_days": latest["trend_persistence"],
                "golden_cross_today": latest["golden_cross"],
                "death_cross_today": latest["death_cross"],
                "backtest_sharpe_1y": bt["sharpe_ratio"],
                "backtest_vs_buy_hold_pts_1y": round(bt["total_return_pct"] - bh, 2),
            }))
        except Exception as e:
            results.append({"ticker": t.upper(), "error": str(e)})
    return results


def tool_get_recent_news(ticker: str, max_articles: int = 8) -> list:
    """Recent headlines for a ticker (via yfinance, no separate API key
    needed) -- lets the Agent factor in real catalysts (earnings, guidance,
    analyst moves, macro news) instead of reasoning on price alone."""
    articles = yf.Ticker(ticker).news or []
    results = []
    for a in articles[:max_articles]:
        content = a.get("content", a)  # yfinance nests fields under "content"
        results.append(_clean({
            "title": content.get("title"),
            "publisher": (content.get("provider") or {}).get("displayName"),
            "published": content.get("pubDate"),
            "summary": content.get("summary"),
        }))
    return results


TOOL_DEFINITIONS = [
    {
        "name": "get_current_signal",
        "description": "Get the latest technical signal snapshot for a stock ticker: price vs. its 20/50-day moving averages, RSI, MA spread, volume ratio, and how many days price has held its current trend. Always call this first for any ticker being analyzed.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string", "description": "Stock ticker symbol, e.g. NVDA"}},
            "required": ["ticker"],
        },
    },
    {
        "name": "get_recent_crossovers",
        "description": "Get past golden/death cross events with their confirmation metrics and what actually happened in the following trading days. Use this to check how similar past signals for this ticker actually played out before trusting a new one.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "lookback_days": {"type": "integer", "description": "How many recent trading days of history to scan. Default 500."},
                "forward_days": {"type": "integer", "description": "How many trading days forward to measure the outcome of each past signal. Default 10."},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_backtest_summary",
        "description": "Run a backtest of the moving-average crossover strategy against a ticker's history, with optional confirmation filters, and compare it to simply buying and holding. Use this to ground any recommendation in validated historical performance rather than assumption.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "period": {"type": "string", "description": "e.g. '2y', '5y'. Default '5y'."},
                "spread_threshold": {"type": "number", "description": "Optional minimum MA spread %% to confirm a signal."},
                "rsi_threshold": {"type": "number", "description": "Optional minimum RSI to confirm a golden cross."},
                "persistence_threshold": {"type": "integer", "description": "Optional minimum trend-persistence days to confirm a signal."},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_drift_status",
        "description": "Check whether the strategy's recent live performance still matches what it was validated on historically, or shows signs the edge is decaying. Call this before making a strong recommendation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "period": {"type": "string", "description": "Default '5y'."},
                "recent_window_days": {"type": "integer", "description": "Default 90."},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "scan_watchlist",
        "description": "Get a compact signal + backtest snapshot for several tickers at once in a single call. Always call this first when asked to rank, compare, or produce a tier list / best-trades summary across multiple stocks -- do not call get_current_signal repeatedly for that instead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {"type": "array", "items": {"type": "string"}, "description": "List of ticker symbols. Omit to use the default watchlist."},
            },
            "required": [],
        },
    },
    {
        "name": "get_recent_news",
        "description": "Get recent real headlines for a ticker (earnings, guidance, analyst ratings, macro news). Use this to check for a concrete catalyst behind a technical move, or to flag upcoming events (like an earnings date) that could invalidate a purely technical read.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "max_articles": {"type": "integer", "description": "Default 8."},
            },
            "required": ["ticker"],
        },
    },
]

TOOL_DISPATCH = {
    "get_current_signal": tool_get_current_signal,
    "get_recent_crossovers": tool_get_recent_crossovers,
    "get_backtest_summary": tool_get_backtest_summary,
    "get_drift_status": tool_get_drift_status,
    "get_recent_news": tool_get_recent_news,
    "scan_watchlist": tool_scan_watchlist,
}
