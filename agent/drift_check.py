"""'Is the rule still working?' -- compares how the chosen strategy has
performed recently against how it performed on the history it was validated
on. The walk-forward test already proved a rule that looks fine in one
window can fail in the next; this is the ongoing version of that same
check, run against live/recent data instead of a historical fold.

This does NOT try to auto-fix anything. It flags. A human (you) decides
what to do about a flag -- re-validate, switch rules, or just keep watching.
"""

from backtest import prepare_data, run_backtest, buy_and_hold_return_pct

# Thresholds for what counts as "drifting enough to flag." These are
# deliberately loose (a Sharpe drop of 1.0 or more is a large move) so the
# check doesn't cry wolf over ordinary day-to-day noise.
SHARPE_DROP_THRESHOLD = 1.0
UNDERPERFORMANCE_THRESHOLD_PCT = -15.0


def check_drift(df, params: dict, reference_window: tuple, recent_window_days: int = 90) -> dict:
    """
    reference_window: (start_idx, end_idx) -- the period the rule was
    validated on (e.g. the training data behind your walk-forward result).
    recent_window_days: how many of the most recent trading days count as
    "live" performance to check against that reference.
    """
    reference_df = df.iloc[reference_window[0]:reference_window[1]]
    recent_df = df.iloc[-recent_window_days:]

    reference_result = run_backtest(reference_df, **params)
    recent_result = run_backtest(recent_df, **params)

    reference_sharpe = reference_result["sharpe_ratio"]
    recent_sharpe = recent_result["sharpe_ratio"]
    sharpe_drop = reference_sharpe - recent_sharpe

    recent_strategy_return = recent_result["total_return_pct"]
    recent_buy_hold_return = buy_and_hold_return_pct(recent_df)
    relative_performance = recent_strategy_return - recent_buy_hold_return

    flags = []
    if recent_result["num_trades"] == 0:
        flags.append(f"No trades fired in the last {recent_window_days} trading days -- not enough live data to judge yet.")
    else:
        if sharpe_drop > SHARPE_DROP_THRESHOLD:
            flags.append(
                f"Recent Sharpe ({recent_sharpe}) is well below the validated Sharpe "
                f"({reference_sharpe}), a drop of {round(sharpe_drop, 2)}."
            )
        if relative_performance < UNDERPERFORMANCE_THRESHOLD_PCT:
            flags.append(
                f"Strategy has underperformed buy-and-hold by {round(-relative_performance, 2)} "
                f"points over the last {recent_window_days} trading days."
            )

    if not flags:
        status = "OK"
    elif recent_result["num_trades"] == 0:
        status = "INSUFFICIENT DATA"
    else:
        status = "DRIFT WARNING"

    return {
        "status": status,
        "reference_sharpe": reference_sharpe,
        "recent_sharpe": recent_sharpe,
        "recent_strategy_return_pct": recent_strategy_return,
        "recent_buy_hold_return_pct": round(recent_buy_hold_return, 2),
        "relative_performance_pct": round(relative_performance, 2),
        "recent_num_trades": recent_result["num_trades"],
        "flags": flags,
    }


if __name__ == "__main__":
    df = prepare_data("NVDA", period="5y")
    n = len(df)

    # Treat the first 80% of history as "what we validated the rule on."
    reference_window = (0, int(n * 0.8))

    # The walk-forward test found no confirmation filter with a consistent
    # edge, so the defensible live choice is the plain, unfiltered crossover
    # -- no arbitrary threshold pretending to be more validated than it is.
    live_params = dict(spread_threshold=None, rsi_threshold=None, persistence_threshold=None)

    result = check_drift(df, live_params, reference_window, recent_window_days=90)

    print("=== Drift Check: is the rule still working? ===\n")
    for k, v in result.items():
        print(f"  {k}: {v}")
