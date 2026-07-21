"""Backtests the equal-weighted 8-asset portfolio, rebalanced quarterly
back to target weights, against a simple SPY buy-and-hold benchmark.
"""

import pandas as pd

from data import get_portfolio_and_benchmark, EQUAL_WEIGHT


def _quarter_end_trading_days(index: pd.DatetimeIndex) -> set:
    """The actual last trading day of each calendar quarter present in the
    index -- not a resample label, which may land on a non-trading day."""
    as_series = index.to_series()
    return set(as_series.groupby(index.to_period("Q")).max())


def simulate_portfolio(prices: pd.DataFrame, weights: dict, starting_value: float = 10_000.0) -> pd.Series:
    """Equal-weighted portfolio, rebalanced back to target weights at the
    end of each quarter. Returns a daily equity curve."""
    tickers = list(weights.keys())
    w = pd.Series(weights)[tickers]
    rebalance_dates = _quarter_end_trading_days(prices.index)

    shares = None
    equity_curve = []

    for date in prices.index:
        row = prices.loc[date, tickers]
        if shares is None:
            shares = (w * starting_value) / row
        elif date in rebalance_dates:
            current_value = (shares * row).sum()
            shares = (w * current_value) / row

        equity_curve.append((shares * row).sum())

    return pd.Series(equity_curve, index=prices.index, name="portfolio")


def benchmark_curve(benchmark_prices: pd.Series, starting_value: float = 10_000.0) -> pd.Series:
    shares = starting_value / benchmark_prices.iloc[0]
    return benchmark_prices * shares


def drawdown_series(equity: pd.Series) -> pd.Series:
    running_max = equity.cummax()
    return (equity - running_max) / running_max


def run_backtest(period: str = "3y", weights: dict = None, starting_value: float = 10_000.0, prefetched: tuple = None) -> dict:
    """Pass `prefetched` as (prices, benchmark_prices) -- from
    data.get_portfolio_and_benchmark -- to reuse already-fetched data
    instead of hitting yfinance again."""
    weights = weights or EQUAL_WEIGHT
    prices, benchmark_prices = prefetched or get_portfolio_and_benchmark(period=period)

    portfolio_equity = simulate_portfolio(prices, weights, starting_value)
    bench_equity = benchmark_curve(benchmark_prices, starting_value)

    portfolio_dd = drawdown_series(portfolio_equity)
    benchmark_dd = drawdown_series(bench_equity)

    return {
        "portfolio_equity": portfolio_equity,
        "benchmark_equity": bench_equity,
        "portfolio_drawdown": portfolio_dd,
        "benchmark_drawdown": benchmark_dd,
        "portfolio_return_pct": (portfolio_equity.iloc[-1] / starting_value - 1) * 100,
        "benchmark_return_pct": (bench_equity.iloc[-1] / starting_value - 1) * 100,
        "portfolio_max_drawdown_pct": portfolio_dd.min() * 100,
        "benchmark_max_drawdown_pct": benchmark_dd.min() * 100,
    }


if __name__ == "__main__":
    r = run_backtest()
    print("=== Portfolio Backtest: Equal-Weighted (quarterly rebalance) vs. SPY ===\n")
    print(f"Portfolio total return: {r['portfolio_return_pct']:.1f}%")
    print(f"SPY total return:       {r['benchmark_return_pct']:.1f}%")
    print(f"Portfolio max drawdown: {r['portfolio_max_drawdown_pct']:.1f}%")
    print(f"SPY max drawdown:       {r['benchmark_max_drawdown_pct']:.1f}%")
