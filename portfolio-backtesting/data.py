"""Price data fetcher for the Portfolio Analysis & Backtesting Model."""

import yfinance as yf
import pandas as pd

HOLDINGS = ["NVDA", "AAPL", "MSFT", "TSLA", "AMD", "GOOGL", "GLD", "TLT"]
BENCHMARK = "SPY"
EQUAL_WEIGHT = {t: 1 / len(HOLDINGS) for t in HOLDINGS}


def get_price_history(tickers: list, period: str = "3y") -> pd.DataFrame:
    """Adjusted close prices for all tickers, aligned by date (rows where
    every ticker has a price -- drops any date with a gap in any one of them)."""
    df = yf.download(tickers, period=period, auto_adjust=True, progress=False)["Close"]
    df = df.dropna()
    if df.empty:
        raise RuntimeError(f"No overlapping price data for {tickers}.")
    return df


def get_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change().dropna()


def get_portfolio_and_benchmark(period: str = "3y") -> tuple:
    all_tickers = HOLDINGS + [BENCHMARK]
    prices = get_price_history(all_tickers, period=period)
    return prices[HOLDINGS], prices[BENCHMARK]


if __name__ == "__main__":
    portfolio_prices, benchmark_prices = get_portfolio_and_benchmark()
    print(f"Holdings: {HOLDINGS}")
    print(f"Benchmark: {BENCHMARK}")
    print(f"Date range: {portfolio_prices.index.min().date()} to {portfolio_prices.index.max().date()}")
    print(f"Rows: {len(portfolio_prices)}")
    print()
    print("Portfolio prices (tail):")
    print(portfolio_prices.tail())
    print()
    print("Benchmark prices (tail):")
    print(benchmark_prices.tail())
