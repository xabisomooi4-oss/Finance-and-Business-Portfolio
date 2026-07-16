"""Technical indicators: moving averages and crossover detection."""

import pandas as pd


def add_moving_averages(df: pd.DataFrame, short: int = 20, long: int = 50) -> pd.DataFrame:
    """Adds short and long simple moving average columns to the price DataFrame."""
    df = df.copy()
    df[f"MA_{short}"] = df["Close"].rolling(window=short).mean()
    df[f"MA_{long}"] = df["Close"].rolling(window=long).mean()
    return df


def detect_crossovers(df: pd.DataFrame, short: int = 20, long: int = 50) -> pd.DataFrame:
    """Flags golden cross (short MA moves above long MA) and death cross
    (short MA moves below long MA) events.

    A crossover happens on the specific day the *relationship* flips, not
    every day the short MA happens to be above the long MA.
    """
    df = df.copy()
    short_col, long_col = f"MA_{short}", f"MA_{long}"

    above = df[short_col] > df[long_col]
    # True on the day 'above' flips from False to True (yesterday was below/equal, today is above)
    df["golden_cross"] = above & ~above.shift(1, fill_value=False)
    # True on the day 'above' flips from True to False
    df["death_cross"] = ~above & above.shift(1, fill_value=False)

    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Adds a 14-day RSI column, 0-100.

    RSI compares the size of recent up-days to recent down-days. It uses
    Wilder's smoothing (an exponential moving average with alpha = 1/period),
    which is the standard convention every charting platform uses -- a plain
    rolling average here would give a subtly different number than what
    you'd see on a real chart.
    """
    df = df.copy()
    delta = df["Close"].diff()

    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)

    avg_gain = gains.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    df[f"RSI_{period}"] = 100 - (100 / (1 + rs))

    return df


def add_ma_spread(df: pd.DataFrame, short: int = 20, long: int = 50) -> pd.DataFrame:
    """% gap between the short and long MA. Near zero means the two averages
    are sitting on top of each other -- exactly the condition that produces
    whipsaws, since small price wiggles are enough to flip which one is on top.
    """
    df = df.copy()
    short_col, long_col = f"MA_{short}", f"MA_{long}"
    df["ma_spread_pct"] = (df[short_col] - df[long_col]) / df[long_col] * 100
    return df


def add_volume_ratio(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Today's volume relative to its recent average. Above 1.0 means more
    trading interest than usual -- real trends tend to show up on
    above-average volume; whipsaws often happen on quiet, unremarkable days.
    """
    df = df.copy()
    avg_volume = df["Volume"].rolling(window=window).mean()
    df["volume_ratio"] = df["Volume"] / avg_volume
    return df


def add_trend_persistence(df: pd.DataFrame, short: int = 20, long: int = 50) -> pd.DataFrame:
    """Signed streak counter: +N means price has closed above BOTH moving
    averages for N straight days, -N means below both for N straight days,
    0 means price is sitting between them (no clear side). A crossover that
    only ever reaches a persistence of 1 or 2 before resetting is the
    signature of a whipsaw; a real trend keeps building this number.
    """
    df = df.copy()
    short_col, long_col = f"MA_{short}", f"MA_{long}"
    above_both = (df["Close"] > df[short_col]) & (df["Close"] > df[long_col])
    below_both = (df["Close"] < df[short_col]) & (df["Close"] < df[long_col])

    streak = []
    current = 0
    for is_above, is_below in zip(above_both, below_both):
        if is_above:
            current = current + 1 if current > 0 else 1
        elif is_below:
            current = current - 1 if current < 0 else -1
        else:
            current = 0
        streak.append(current)

    df["trend_persistence"] = streak
    return df


if __name__ == "__main__":
    from data import get_price_history

    df = get_price_history("NVDA", period="2y")
    df = add_moving_averages(df, short=20, long=50)
    df = detect_crossovers(df, short=20, long=50)
    df = add_rsi(df, period=14)
    df = add_ma_spread(df, short=20, long=50)
    df = add_volume_ratio(df, window=20)
    df = add_trend_persistence(df, short=20, long=50)

    cols = ["Close", "RSI_14", "ma_spread_pct", "volume_ratio", "trend_persistence", "golden_cross", "death_cross"]
    crossovers = df[df["golden_cross"] | df["death_cross"]][cols]
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", None)
    print("Crossover events in the last 2 years, full confirmation picture:\n")
    print(crossovers.round(2).to_string())
