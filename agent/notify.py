"""Desktop notification check: scans the watchlist once and fires a native
macOS notification for any notable NEW event -- a fresh golden/death cross
today, or a drift status that just flipped to warning.

Meant to run once per trading day, ideally after market close (~4:30pm ET).
These signals come from daily closing prices, so checking more often than
once a day won't surface anything new -- there's nothing to poll for.
"""

import json
import subprocess
from pathlib import Path

from tools import DEFAULT_WATCHLIST, tool_scan_watchlist
from drift_check import check_drift
from backtest import prepare_data

STATE_FILE = Path(__file__).parent / ".notify_state.json"


def send_macos_notification(title: str, message: str) -> None:
    safe_title = title.replace('"', '\\"')
    safe_message = message.replace('"', '\\"')
    script = f'display notification "{safe_message}" with title "{safe_title}" sound name "Glass"'
    subprocess.run(["osascript", "-e", script], check=False)


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def check_and_notify(tickers: list = None) -> int:
    tickers = tickers or DEFAULT_WATCHLIST
    state = load_state()
    notified = 0

    for row in tool_scan_watchlist(tickers):
        ticker = row.get("ticker")
        if "error" in row:
            continue

        if row.get("golden_cross_today"):
            send_macos_notification(f"{ticker}: Golden Cross", f"MA20 crossed above MA50 today at ${row['close']}.")
            notified += 1
        if row.get("death_cross_today"):
            send_macos_notification(f"{ticker}: Death Cross", f"MA20 crossed below MA50 today at ${row['close']}.")
            notified += 1

        # Drift warnings can persist for days -- only notify on the day it
        # first appears, not every single day it remains true.
        df = prepare_data(ticker, period="5y")
        n = len(df)
        drift = check_drift(
            df, dict(spread_threshold=None, rsi_threshold=None, persistence_threshold=None),
            (0, int(n * 0.8)), recent_window_days=90,
        )
        was_warning = state.get(ticker, {}).get("drift_warning", False)
        is_warning = drift["status"] == "DRIFT WARNING"
        if is_warning and not was_warning:
            send_macos_notification(
                f"{ticker}: Drift Warning",
                f"Recent Sharpe {drift['recent_sharpe']} vs. reference {drift['reference_sharpe']} -- edge may be decaying.",
            )
            notified += 1
        state.setdefault(ticker, {})["drift_warning"] = is_warning

    save_state(state)
    return notified


if __name__ == "__main__":
    count = check_and_notify()
    print(f"Checked {len(DEFAULT_WATCHLIST)} tickers. Sent {count} notification(s).")
