"""Correlation matrix across the portfolio's holdings -- the actual
diagnostic for whether "8 positions" means real diversification or just
8 ways of making the same bet."""

import pandas as pd

from data import get_portfolio_and_benchmark, get_returns, HOLDINGS


def correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    return returns.corr()


def average_pairwise_correlation(corr: pd.DataFrame) -> float:
    """Mean of all off-diagonal correlations -- one number summarizing how
    correlated the whole portfolio is with itself."""
    n = len(corr)
    off_diagonal_sum = corr.values.sum() - n  # subtract the n diagonal 1.0s
    num_pairs = n * (n - 1)
    return off_diagonal_sum / num_pairs


if __name__ == "__main__":
    prices, _ = get_portfolio_and_benchmark()
    returns = get_returns(prices)
    corr = correlation_matrix(returns)

    pd.set_option("display.width", 120)
    print("=== Correlation Matrix ===\n")
    print(corr.round(2))

    print(f"\nAverage pairwise correlation: {average_pairwise_correlation(corr):.2f}")

    tech = [t for t in HOLDINGS if t not in ("GLD", "TLT")]
    tech_corr = corr.loc[tech, tech]
    print(f"Average pairwise correlation, tech-only ({', '.join(tech)}): {average_pairwise_correlation(tech_corr):.2f}")
