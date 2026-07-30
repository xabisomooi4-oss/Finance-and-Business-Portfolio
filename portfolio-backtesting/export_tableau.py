"""Flattens the portfolio backtest + risk output into tidy CSVs for
Tableau Public. Run with `python export_tableau.py`.
"""

import csv
import os

import numpy as np

from data import get_portfolio_and_benchmark, get_returns, EQUAL_WEIGHT, HOLDINGS, BENCHMARK
from correlation import correlation_matrix
from metrics import (
    run_metrics, portfolio_daily_returns, annualized_return, sharpe_ratio, max_drawdown, TRADING_DAYS,
)
from backtest import run_backtest

OUT_DIR = os.path.join(os.path.dirname(__file__), "tableau_data")


def write_csv(filename: str, fieldnames: list, rows: list) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


def export_equity_curve(bt: dict) -> None:
    rows = []
    for date in bt["portfolio_equity"].index:
        rows.append({
            "date": date.strftime("%Y-%m-%d"),
            "portfolio_equity": round(bt["portfolio_equity"].loc[date], 2),
            "benchmark_equity": round(bt["benchmark_equity"].loc[date], 2),
            "portfolio_drawdown_pct": round(bt["portfolio_drawdown"].loc[date] * 100, 3),
            "benchmark_drawdown_pct": round(bt["benchmark_drawdown"].loc[date] * 100, 3),
        })
    write_csv(
        "equity_curve.csv",
        ["date", "portfolio_equity", "benchmark_equity", "portfolio_drawdown_pct", "benchmark_drawdown_pct"],
        rows,
    )


def export_correlation_matrix(corr) -> None:
    """Long format (one row per cell) -- what Tableau needs to build a
    heatmap, rather than the wide matrix pandas prints."""
    rows = []
    for ticker_a in corr.index:
        for ticker_b in corr.columns:
            rows.append({
                "ticker_a": ticker_a, "ticker_b": ticker_b,
                "correlation": round(corr.loc[ticker_a, ticker_b], 4),
            })
    write_csv("correlation_matrix.csv", ["ticker_a", "ticker_b", "correlation"], rows)


def export_risk_comparison(metrics: dict, returns, benchmark_returns, rf: float) -> None:
    """Portfolio vs. benchmark, side by side, for a comparison bar chart --
    metrics.py only computes the portfolio side plus beta, so the
    benchmark's own return/vol/Sharpe/drawdown are computed here."""
    bench_ann_return = annualized_return(benchmark_returns)
    bench_ann_vol = benchmark_returns.std() * np.sqrt(TRADING_DAYS)
    bench_sharpe = sharpe_ratio(benchmark_returns, rf)
    bench_dd = max_drawdown(benchmark_returns)

    rows = [
        {"entity": "Portfolio (8-asset, equal-weight)", "annualized_return_pct": round(metrics["annualized_return"] * 100, 2),
         "annualized_volatility_pct": round(metrics["annualized_volatility"] * 100, 2),
         "sharpe_ratio": round(metrics["sharpe_ratio"], 3), "max_drawdown_pct": round(metrics["max_drawdown"] * 100, 2)},
        {"entity": f"Benchmark ({BENCHMARK})", "annualized_return_pct": round(bench_ann_return * 100, 2),
         "annualized_volatility_pct": round(bench_ann_vol * 100, 2),
         "sharpe_ratio": round(bench_sharpe, 3), "max_drawdown_pct": round(bench_dd * 100, 2)},
    ]
    write_csv(
        "risk_comparison.csv",
        ["entity", "annualized_return_pct", "annualized_volatility_pct", "sharpe_ratio", "max_drawdown_pct"],
        rows,
    )

    diversification_rows = [
        {"metric": "Real volatility (covariance-based)", "value_pct": round(metrics["annualized_volatility"] * 100, 2)},
        {"metric": "Naive volatility (if perfectly correlated)", "value_pct": round(metrics["naive_weighted_avg_volatility"] * 100, 2)},
    ]
    write_csv("diversification_benefit.csv", ["metric", "value_pct"], diversification_rows)


def export_holdings(weights: dict) -> None:
    rows = [{"ticker": t, "weight_pct": round(w * 100, 2)} for t, w in weights.items()]
    write_csv("holdings_weights.csv", ["ticker", "weight_pct"], rows)


if __name__ == "__main__":
    prices, benchmark_prices = get_portfolio_and_benchmark(period="3y")
    prefetched = (prices, benchmark_prices)

    returns = get_returns(prices)
    benchmark_returns = benchmark_prices.pct_change().dropna()

    metrics = run_metrics(period="3y", prefetched=prefetched)
    bt = run_backtest(period="3y", prefetched=prefetched)
    corr = correlation_matrix(returns)

    export_equity_curve(bt)
    export_correlation_matrix(corr)
    export_risk_comparison(metrics, returns, benchmark_returns, metrics["risk_free_rate"])
    export_holdings(EQUAL_WEIGHT)

    print("\nDone. Open portfolio-backtesting/tableau_data/*.csv in Tableau Public.")
