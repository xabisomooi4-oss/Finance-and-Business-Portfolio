"""Portfolio-level risk metrics for the equal-weighted 8-asset portfolio.

Portfolio volatility is computed via the full covariance matrix (w^T . Cov . w),
not a weighted average of individual volatilities -- that's the actual math
behind "diversification reduces risk," not just an assertion. The gap
between the two numbers below IS the diversification benefit, quantified.
"""

import numpy as np
import pandas as pd
import yfinance as yf

from data import get_portfolio_and_benchmark, get_returns, EQUAL_WEIGHT

TRADING_DAYS = 252


def get_risk_free_rate() -> float:
    tnx = yf.Ticker("^TNX").history(period="5d")["Close"]
    return round(tnx.iloc[-1] / 100, 4)


def portfolio_daily_returns(returns: pd.DataFrame, weights: dict) -> pd.Series:
    w = np.array([weights[t] for t in returns.columns])
    return returns.dot(w)


def annualized_return(daily_returns: pd.Series) -> float:
    return daily_returns.mean() * TRADING_DAYS


def annualized_volatility_from_covariance(returns: pd.DataFrame, weights: dict) -> float:
    """The real diversification math: w^T * Cov * w."""
    w = np.array([weights[t] for t in returns.columns])
    cov = returns.cov() * TRADING_DAYS
    portfolio_variance = w @ cov.values @ w
    return float(np.sqrt(portfolio_variance))


def weighted_average_individual_volatility(returns: pd.DataFrame, weights: dict) -> float:
    """What volatility WOULD be with zero diversification benefit (as if
    every holding moved in lockstep) -- the naive weighted sum, for
    comparison against the real, correlation-aware number above."""
    individual_vol = returns.std() * np.sqrt(TRADING_DAYS)
    w = np.array([weights[t] for t in returns.columns])
    return float(np.dot(w, individual_vol.values))


def sharpe_ratio(daily_returns: pd.Series, risk_free_rate: float) -> float:
    ann_return = annualized_return(daily_returns)
    ann_vol = daily_returns.std() * np.sqrt(TRADING_DAYS)
    if ann_vol == 0:
        return 0.0
    return (ann_return - risk_free_rate) / ann_vol


def max_drawdown(daily_returns: pd.Series) -> float:
    cumulative = (1 + daily_returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    return float(drawdown.min())


def beta_vs_benchmark(portfolio_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()
    aligned.columns = ["portfolio", "benchmark"]
    cov = aligned.cov().loc["portfolio", "benchmark"]
    var = aligned["benchmark"].var()
    return float(cov / var)


def run_metrics(period: str = "3y", weights: dict = None, prefetched: tuple = None) -> dict:
    """Pass `prefetched` as (prices, benchmark_prices) -- from
    data.get_portfolio_and_benchmark -- to reuse already-fetched data
    instead of hitting yfinance again."""
    weights = weights or EQUAL_WEIGHT
    prices, benchmark_prices = prefetched or get_portfolio_and_benchmark(period=period)
    returns = get_returns(prices)
    benchmark_returns = benchmark_prices.pct_change().dropna()

    port_returns = portfolio_daily_returns(returns, weights)
    rf = get_risk_free_rate()

    port_vol = annualized_volatility_from_covariance(returns, weights)
    naive_vol = weighted_average_individual_volatility(returns, weights)

    return {
        "annualized_return": annualized_return(port_returns),
        "annualized_volatility": port_vol,
        "naive_weighted_avg_volatility": naive_vol,
        "diversification_benefit_pct": (1 - port_vol / naive_vol) * 100 if naive_vol else None,
        "sharpe_ratio": sharpe_ratio(port_returns, rf),
        "max_drawdown": max_drawdown(port_returns),
        "beta_vs_spy": beta_vs_benchmark(port_returns, benchmark_returns),
        "risk_free_rate": rf,
    }


if __name__ == "__main__":
    r = run_metrics()
    print("=== Portfolio Metrics (equal-weighted, 3y) ===\n")
    print(f"Risk-free rate:                 {r['risk_free_rate']:.2%}")
    print(f"Annualized return:              {r['annualized_return']:.2%}")
    print(f"Annualized volatility (real):   {r['annualized_volatility']:.2%}")
    print(f"Naive weighted-avg volatility:  {r['naive_weighted_avg_volatility']:.2%}  (if holdings were perfectly correlated)")
    print(f"Diversification benefit:        {r['diversification_benefit_pct']:.1f}% lower vol than naive sum")
    print(f"Sharpe ratio:                   {r['sharpe_ratio']:.2f}")
    print(f"Max drawdown:                   {r['max_drawdown']:.2%}")
    print(f"Beta vs. SPY:                   {r['beta_vs_spy']:.2f}")
