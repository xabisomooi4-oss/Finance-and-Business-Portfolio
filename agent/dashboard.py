"""Trading-app-style dashboard for the Stock Analysis Agent.

Run with: streamlit run dashboard.py
(from inside the agent/ folder, with the venv activated)
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from backtest import prepare_data, run_backtest, buy_and_hold_return_pct
from drift_check import check_drift
from llm_agent import run_agent, run_agent_chat
from tools import DEFAULT_WATCHLIST

MOOVER_AVATAR = "\U0001F30A"  # 🌊

# Dark "trading terminal" palette -- validated for contrast/CVD-safety
# against this exact dark surface (see dataviz skill's validate_palette.js).
# Red/green are reserved specifically for bullish/bearish trend meaning,
# never used decoratively elsewhere.
SURFACE = "#0A0E14"
CARD = "#131A24"
BLUE = "#3B82F6"       # primary accent -- MA20, UI
BLUE_SLATE = "#4E7FBE"  # secondary -- MA50
GAIN = "#2FAE72"        # bullish: golden cross, oversold band, uptrend
LOSS = "#EF4444"        # bearish: death cross, overbought band, downtrend
MUTED = "#5C6B7A"       # price line, gridlines, non-signal ink
TEXT = "#E8EDF2"

st.set_page_config(page_title="Stock Analysis Agent", page_icon="\U0001F4C8", layout="wide")

st.title("\U0001F4C8 Stock Analysis Agent")
st.caption("Analysis only — it never places trades. A human decides what to do with this.")

col1, col2 = st.columns([3, 1])
with col1:
    ticker = st.text_input("Ticker", value="NVDA", label_visibility="collapsed", placeholder="Ticker, e.g. NVDA").strip().upper()
with col2:
    analyze = st.button("Analyze with Agent", type="primary", use_container_width=True)

if not ticker:
    st.stop()

try:
    df = prepare_data(ticker, period="1y")
except Exception as e:
    st.error(f"Couldn't load data for '{ticker}': {e}")
    st.stop()

latest = df.iloc[-1]

# --- Top stat row ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Price", f"${latest['Close']:.2f}")
c2.metric("RSI (14)", f"{latest['RSI_14']:.1f}")
c3.metric("MA Spread", f"{latest['ma_spread_pct']:.2f}%")
persistence = int(latest["trend_persistence"])
trend_label = f"+{persistence}d above" if persistence > 0 else f"{persistence}d below" if persistence < 0 else "neutral"
c4.metric("Trend Persistence", trend_label)

# --- Price + MA chart, RSI subplot ---
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.06)

fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Close", line=dict(color=MUTED, width=1.5)), row=1, col=1)
fig.add_trace(go.Scatter(x=df.index, y=df["MA_20"], name="MA 20", line=dict(color=BLUE, width=2)), row=1, col=1)
fig.add_trace(go.Scatter(x=df.index, y=df["MA_50"], name="MA 50", line=dict(color=BLUE_SLATE, width=2)), row=1, col=1)

golden = df[df["golden_cross"]]
death = df[df["death_cross"]]
fig.add_trace(go.Scatter(x=golden.index, y=golden["Close"], mode="markers", name="Golden Cross",
                          marker=dict(color=GAIN, size=11, symbol="triangle-up")), row=1, col=1)
fig.add_trace(go.Scatter(x=death.index, y=death["Close"], mode="markers", name="Death Cross",
                          marker=dict(color=LOSS, size=11, symbol="triangle-down")), row=1, col=1)

fig.add_trace(go.Scatter(x=df.index, y=df["RSI_14"], name="RSI (14)", line=dict(color=BLUE_SLATE, width=1.5)), row=2, col=1)
fig.add_hline(y=70, line_dash="dot", line_color=LOSS, row=2, col=1)
fig.add_hline(y=30, line_dash="dot", line_color=GAIN, row=2, col=1)
fig.update_yaxes(range=[0, 100], row=2, col=1)

fig.update_layout(
    height=560, margin=dict(l=10, r=10, t=10, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=TEXT)),
    hovermode="x unified",
    paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
    font=dict(color=TEXT),
)
fig.update_xaxes(gridcolor=CARD, zerolinecolor=CARD)
fig.update_yaxes(gridcolor=CARD, zerolinecolor=CARD)
st.plotly_chart(fig, use_container_width=True)

# --- Backtest vs. buy-and-hold + drift ---
bt = run_backtest(df)
bh = buy_and_hold_return_pct(df)
n = len(df)
drift = check_drift(
    df, dict(spread_threshold=None, rsi_threshold=None, persistence_threshold=None),
    (0, int(n * 0.8)), recent_window_days=90,
)

st.subheader("Backtest vs. Buy & Hold (1y)")
b1, b2, b3, b4 = st.columns(4)
b1.metric("Strategy Return", f"{bt['total_return_pct']:.1f}%")
b2.metric("Buy & Hold Return", f"{bh:.1f}%", delta=f"{bt['total_return_pct'] - bh:.1f} pts vs. strategy", delta_color="inverse")
b3.metric("Sharpe Ratio", f"{bt['sharpe_ratio']}")
b4.metric("Max Drawdown", f"{bt['max_drawdown_pct']}%")

status_icon = {"OK": "\U0001F7E2", "DRIFT WARNING": "\U0001F7E0", "INSUFFICIENT DATA": "⚪"}.get(drift["status"], "⚪")
st.caption(
    f"{status_icon} Drift status: **{drift['status']}** — recent Sharpe {drift['recent_sharpe']} "
    f"vs. reference {drift['reference_sharpe']} · {drift['recent_num_trades']} trade(s) in the last 90 days"
)

# --- Agent reasoning ---
st.subheader("Agent's Read")

if analyze:
    tool_log = st.expander("Tool calls made by the Agent", expanded=False)

    def log_tool_call(name, inputs):
        tool_log.write(f"`{name}({inputs})`")

    with st.spinner("Agent is reasoning through the signals..."):
        question = f"What's your current read on {ticker} -- is this a buy, sell, or hold right now, and why?"
        answer = run_agent(question, on_tool_call=log_tool_call)

    # Streamlit's markdown renderer treats "$...$" as LaTeX math and a pair
    # of stray "~" (the model's shorthand for "approximately") as
    # strikethrough -- escape both so prices render as plain text.
    safe_answer = answer.replace("$", "\\$").replace("~", "\\~")
    st.markdown(safe_answer)
else:
    st.info("Click **Analyze with Agent** above to get its full written reasoning for this ticker.")

# --- Watchlist tier list ---
st.divider()
st.subheader("\U0001F4CB Watchlist Tier List")
st.caption(
    "Ranked from real technical + backtest data across your watchlist — not a guarantee. "
    "See Chapter V of the Day Trading Field Manual for why."
)

watchlist_input = st.text_input(
    "Watchlist (comma-separated tickers)",
    value=", ".join(DEFAULT_WATCHLIST),
)
scan = st.button("Scan Watchlist with Agent", use_container_width=True)

if scan:
    tickers = [t.strip().upper() for t in watchlist_input.split(",") if t.strip()]
    tier_log = st.expander("Tool calls made by the Agent", expanded=False)

    def log_tier_tool_call(name, inputs):
        tier_log.write(f"`{name}({inputs})`")

    with st.spinner(f"Agent is scanning {len(tickers)} tickers..."):
        tier_question = (
            f"Scan this watchlist using scan_watchlist: {', '.join(tickers)}. "
            "Then produce a ranked tier list: Tier 1 = strongest confirmed setups right now, "
            "Tier 2 = has potential but not yet confirmed, Tier 3 = avoid or watch cautiously. "
            "For your top 1-2 picks, also check recent news and drift status before finalizing. "
            "Give a one-line reason for each ticker's tier placement, grounded in the actual numbers -- "
            "and say plainly if nothing in the watchlist looks like a strong setup right now."
        )
        tier_answer = run_agent(tier_question, on_tool_call=log_tier_tool_call)

    safe_tier_answer = tier_answer.replace("$", "\\$").replace("~", "\\~")
    st.markdown(safe_tier_answer)
else:
    st.info("Click **Scan Watchlist with Agent** to get a ranked tier list across these tickers.")

# --- Moover chat ---
st.divider()
st.subheader(f"{MOOVER_AVATAR} Ask Moover")
st.caption(
    "Moover uses the exact same tools and rules as the Agent above -- grounded in real data, "
    "always honest about buy-and-hold comparisons and low confidence. Not a different, looser AI."
)

if "moover_display_history" not in st.session_state:
    st.session_state.moover_display_history = []
if "moover_raw_history" not in st.session_state:
    st.session_state.moover_raw_history = []

for msg in st.session_state.moover_display_history:
    avatar = MOOVER_AVATAR if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"].replace("$", "\\$").replace("~", "\\~"))

user_input = st.chat_input("Ask Moover about a ticker, a signal, or the strategy...")

if user_input:
    st.session_state.moover_display_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    chat_log = st.expander("Tool calls made by Moover", expanded=False)

    def log_chat_tool_call(name, inputs):
        chat_log.write(f"`{name}({inputs})`")

    with st.chat_message("assistant", avatar=MOOVER_AVATAR):
        with st.spinner("Moover is thinking..."):
            answer, updated_history = run_agent_chat(
                st.session_state.moover_raw_history, user_input, on_tool_call=log_chat_tool_call,
            )
        st.markdown(answer.replace("$", "\\$").replace("~", "\\~"))

    st.session_state.moover_raw_history = updated_history
    st.session_state.moover_display_history.append({"role": "assistant", "content": answer})
