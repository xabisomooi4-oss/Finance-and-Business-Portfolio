"""Backtests the moving-average crossover strategy, with optional
confirmation filters (MA spread, RSI, trend persistence) layered on top.

Strategy: long-only. Enter on a golden cross that passes the confirmation
filters, exit on the next death cross (exits are never filtered -- you want
to be quick to protect capital, not slow to confirm a warning sign).

Trades execute at the NEXT day's open, not the signal day's close. This
matters: a crossover is only knowable once that day's bar has fully closed,
so trading at that same day's price would be lookahead bias -- using
information you couldn't actually have had yet.
"""

import numpy as np
import pandas as pd

from data import get_price_history
from indicators import (
    add_moving_averages, detect_crossovers, add_rsi,
    add_ma_spread, add_volume_ratio, add_trend_persistence,
)


def prepare_data(ticker: str, period: str = "2y", short: int = 20, long: int = 50) -> pd.DataFrame:
    df = get_price_history(ticker, period=period)
    df = add_moving_averages(df, short, long)
    df = detect_crossovers(df, short, long)
    df = add_rsi(df, period=14)
    df = add_ma_spread(df, short, long)
    df = add_volume_ratio(df, window=20)
    df = add_trend_persistence(df, short, long)
    return df


def run_backtest(
    df: pd.DataFrame,
    spread_threshold: float = None,
    rsi_threshold: float = None,
    persistence_threshold: int = None,
    starting_cash: float = 10_000.0,
) -> dict:
    """Set a threshold to None to disable that filter. All three None gives
    the raw, unfiltered crossover strategy -- useful as a baseline to compare
    the filtered version against.
    """
    df = df.reset_index()

    in_position = False
    entry_price = 0.0
    entry_date = None
    cash = starting_cash
    shares = 0.0
    equity_curve = []
    trades = []

    for i in range(len(df) - 1):  # need a "next day" to execute on
        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        equity = shares * row["Close"] if in_position else cash
        equity_curve.append({"Date": row["Date"], "equity": equity})

        if not in_position and row["golden_cross"]:
            confirmed = True
            if spread_threshold is not None:
                confirmed &= abs(row["ma_spread_pct"]) >= spread_threshold
            if rsi_threshold is not None:
                confirmed &= row["RSI_14"] >= rsi_threshold
            if persistence_threshold is not None:
                confirmed &= row["trend_persistence"] >= persistence_threshold

            if confirmed:
                entry_price = next_row["Open"]
                entry_date = next_row["Date"]
                shares = cash / entry_price
                cash = 0.0
                in_position = True

        elif in_position and row["death_cross"]:
            exit_price = next_row["Open"]
            cash = shares * exit_price
            trades.append({
                "entry_date": entry_date, "entry_price": entry_price,
                "exit_date": next_row["Date"], "exit_price": exit_price,
                "return_pct": (exit_price / entry_price - 1) * 100,
            })
            shares = 0.0
            in_position = False

    last_row = df.iloc[-1]
    if in_position:
        cash = shares * last_row["Close"]
        trades.append({
            "entry_date": entry_date, "entry_price": entry_price,
            "exit_date": last_row["Date"], "exit_price": last_row["Close"],
            "return_pct": (last_row["Close"] / entry_price - 1) * 100,
        })
        in_position = False
    equity_curve.append({"Date": last_row["Date"], "equity": cash})

    equity_df = pd.DataFrame(equity_curve).set_index("Date")
    trades_df = pd.DataFrame(trades)

    return {
        "equity_curve": equity_df,
        "trades": trades_df,
        **compute_metrics(equity_df, trades_df, starting_cash),
    }


def compute_metrics(equity_df: pd.DataFrame, trades_df: pd.DataFrame, starting_cash: float) -> dict:
    final_equity = equity_df["equity"].iloc[-1]
    total_return_pct = (final_equity / starting_cash - 1) * 100

    daily_returns = equity_df["equity"].pct_change().dropna()
    sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() > 0 else 0.0

    running_max = equity_df["equity"].cummax()
    drawdown = (equity_df["equity"] - running_max) / running_max
    max_drawdown_pct = drawdown.min() * 100

    num_trades = len(trades_df)
    win_rate = (trades_df["return_pct"] > 0).mean() * 100 if num_trades > 0 else 0.0

    return {
        "total_return_pct": round(total_return_pct, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "num_trades": num_trades,
        "win_rate_pct": round(win_rate, 2),
    }


def buy_and_hold_return_pct(df: pd.DataFrame) -> float:
    return (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100


def print_result(label: str, result: dict) -> None:
    print(f"=== {label} ===")
    for k in ["total_return_pct", "sharpe_ratio", "max_drawdown_pct", "num_trades", "win_rate_pct"]:
        print(f"  {k}: {result[k]}")
    print()


if __name__ == "__main__":
    df = prepare_data("NVDA", period="2y")

    baseline = run_backtest(df)
    print_result("Baseline: raw crossover, no confirmation filter", baseline)

    filtered = run_backtest(df, spread_threshold=0.3, rsi_threshold=50, persistence_threshold=None)
    print_result("Filtered: spread >= 0.3%, RSI >= 50", filtered)

    print(f"Buy & hold NVDA over the same period: {buy_and_hold_return_pct(df):.2f}%")
