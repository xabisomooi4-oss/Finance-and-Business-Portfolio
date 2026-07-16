"""Pulls historical price data for a ticker from Yahoo Finance."""

import yfinance as yf
import pandas as pd


def get_price_history(ticker: str, period: str = "2y") -> pd.DataFrame:
    """Download daily OHLCV data for a ticker.

    period examples: "6mo", "1y", "2y", "5y"
    Returns a DataFrame indexed by date with columns:
    Open, High, Low, Close, Volume
    """
    df = yf.download(ticker, period=period, progress=False, auto_adjust=True)

    # yfinance returns MultiIndex columns (Price, Ticker) when given a single
    # ticker as a list-like; flatten it so columns are just "Close", "Open", etc.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.dropna()
    return df


if __name__ == "__main__":
    data = get_price_history("NVDA", period="2y")
    print(data.tail())
    print(f"\nRows: {len(data)}  |  Date range: {data.index.min().date()} to {data.index.max().date()}")
