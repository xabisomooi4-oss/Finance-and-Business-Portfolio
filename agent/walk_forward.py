"""Walk-forward validation: pick the best confirmation-rule combination on a
training window, then check whether it still performs on the *next*, unseen
window. A combination that wins in-sample but fails out-of-sample is a sign
of overfitting to a lucky stretch of history, not a real edge.
"""

import pandas as pd

from backtest import prepare_data, run_backtest, buy_and_hold_return_pct

# A small, deliberately limited set of candidates -- not an exhaustive grid.
# With only ~2 years of NVDA data, testing dozens of combinations would let
# something look good purely by chance.
CANDIDATES = {
    "no_filter":        dict(spread_threshold=None, rsi_threshold=None, persistence_threshold=None),
    "spread_only":      dict(spread_threshold=0.2,  rsi_threshold=None, persistence_threshold=None),
    "rsi_only":         dict(spread_threshold=None, rsi_threshold=50,   persistence_threshold=None),
    "spread_and_rsi":   dict(spread_threshold=0.2,  rsi_threshold=50,   persistence_threshold=None),
    "persistence_only": dict(spread_threshold=None, rsi_threshold=None, persistence_threshold=2),
}


def run_fold(df: pd.DataFrame, train_range: tuple, test_range: tuple) -> dict:
    train_df = df.iloc[train_range[0]:train_range[1]]
    test_df = df.iloc[test_range[0]:test_range[1]]

    # Rank every candidate on the training window by Sharpe ratio.
    train_sharpe = {name: run_backtest(train_df, **params)["sharpe_ratio"] for name, params in CANDIDATES.items()}
    best_name = max(train_sharpe, key=train_sharpe.get)
    best_params = CANDIDATES[best_name]

    # Apply that SAME combination, unmodified, to the unseen test window.
    test_result = run_backtest(test_df, **best_params)

    return {
        "best_on_train": best_name,
        "train_sharpe": round(train_sharpe[best_name], 2),
        "test_return_pct": test_result["total_return_pct"],
        "test_sharpe": test_result["sharpe_ratio"],
        "test_max_drawdown_pct": test_result["max_drawdown_pct"],
        "test_num_trades": test_result["num_trades"],
        "test_buy_hold_pct": round(buy_and_hold_return_pct(test_df), 2),
    }


if __name__ == "__main__":
    # 2 years produced 1-3 trades per test window -- too few to trust in
    # either direction. Pulling more history so each fold has enough trades
    # for the comparison to mean something.
    df = prepare_data("NVDA", period="5y")
    n = len(df)
    print(f"Total trading days: {n} ({df.index.min().date()} to {df.index.max().date()})\n")

    # Three expanding-window folds: training window grows each time, test
    # window rolls forward to a stretch of history the selection never saw.
    cuts = [n // 4, n // 2, (n * 3) // 4, n]
    folds = [
        run_fold(df, train_range=(0, cuts[i]), test_range=(cuts[i], cuts[i + 1]))
        for i in range(len(cuts) - 1)
    ]

    for i, fold in enumerate(folds, start=1):
        print(f"=== Fold {i} (out-of-sample) ===")
        for k, v in fold.items():
            print(f"  {k}: {v}")
        print()
