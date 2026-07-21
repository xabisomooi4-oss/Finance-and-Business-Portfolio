"""Portfolio Analysis & Backtesting dashboard: correlation, risk metrics,
and a quarterly-rebalanced equal-weighted portfolio vs. SPY.

Reuses the Agent's dark trading-terminal palette for visual consistency
across the trading-related projects (the Valuation Model uses a separate
monotone institutional style, appropriate to that project instead).

Run with: streamlit run dashboard.py
(from inside portfolio-backtesting/, with the venv activated)
"""

import streamlit as st
import plotly.graph_objects as go

from data import HOLDINGS, BENCHMARK, EQUAL_WEIGHT, get_portfolio_and_benchmark, get_returns
from correlation import correlation_matrix, average_pairwise_correlation
from metrics import run_metrics
from backtest import run_backtest

SURFACE = "#0A0E14"
CARD = "#131A24"
BLUE = "#3B82F6"
BLUE_SLATE = "#4E7FBE"
GAIN = "#2FAE72"
LOSS = "#EF4444"
MUTED = "#5C6B7A"
TEXT = "#E8EDF2"
DIVERGE_NEG = "#4B8EC4"  # negative correlation pole
DIVERGE_POS = "#BC8434"  # positive correlation pole

st.set_page_config(page_title="Portfolio Analysis & Backtesting", page_icon="\U0001F4CA", layout="wide")

st.title("\U0001F4CA Portfolio Analysis & Backtesting")
st.caption(
    f"Equal-weighted, quarterly-rebalanced: {', '.join(HOLDINGS)} vs. {BENCHMARK}."
)

if st.button("Run Analysis", type="primary"):
    st.session_state.pop("data", None)

if "data" not in st.session_state:
    with st.spinner("Pulling live data and computing correlation, risk metrics, and backtest..."):
        prefetched = get_portfolio_and_benchmark()
        prices, benchmark_prices = prefetched
        returns = get_returns(prices)
        corr = correlation_matrix(returns)
        avg_corr = average_pairwise_correlation(corr)
        tech = [t for t in HOLDINGS if t not in ("GLD", "TLT")]
        tech_avg_corr = average_pairwise_correlation(corr.loc[tech, tech])
        metrics = run_metrics(prefetched=prefetched)
        backtest = run_backtest(prefetched=prefetched)
        st.session_state.data = {
            "corr": corr, "avg_corr": avg_corr, "tech_avg_corr": tech_avg_corr,
            "metrics": metrics, "backtest": backtest,
        }

d = st.session_state.data
corr, metrics, bt = d["corr"], d["metrics"], d["backtest"]

# --- Top stat row ---
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Annualized Return", f"{metrics['annualized_return']:.1%}")
c2.metric("Annualized Volatility", f"{metrics['annualized_volatility']:.1%}")
c3.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")
c4.metric("Max Drawdown", f"{metrics['max_drawdown']:.1%}")
c5.metric("Beta vs. SPY", f"{metrics['beta_vs_spy']:.2f}")

st.divider()

# --- Correlation heatmap ---
st.subheader("Correlation Matrix")
st.caption(
    f"Average pairwise correlation: **{d['avg_corr']:.2f}** overall, "
    f"**{d['tech_avg_corr']:.2f}** among the 6 tech holdings alone. "
    f"GLD/TLT are doing real diversification work here, not just adding position count."
)

tickers = list(corr.columns)
fig_corr = go.Figure(data=go.Heatmap(
    z=corr.values, x=tickers, y=tickers,
    colorscale=[[0, DIVERGE_NEG], [0.5, CARD], [1, DIVERGE_POS]],
    zmid=0, zmin=-1, zmax=1,
    text=corr.round(2).values, texttemplate="%{text}",
    textfont=dict(color=TEXT, family="Helvetica Neue, Helvetica, Arial, sans-serif"),
    colorbar=dict(title="Corr", tickfont=dict(color=TEXT)),
    hovertemplate="%{y} vs %{x}: %{z:.2f}<extra></extra>",
))
fig_corr.update_layout(
    height=460, plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
    font=dict(color=TEXT),
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(side="bottom"), yaxis=dict(autorange="reversed"),
)
st.plotly_chart(fig_corr, use_container_width=True)

st.divider()

# --- Diversification benefit ---
st.subheader("Diversification Benefit")
b1, b2, b3 = st.columns(3)
b1.metric("Actual Portfolio Volatility", f"{metrics['annualized_volatility']:.1%}")
b2.metric("If Fully Correlated (naive)", f"{metrics['naive_weighted_avg_volatility']:.1%}")
b3.metric("Volatility Reduction", f"{metrics['diversification_benefit_pct']:.1f}%", delta_color="off")
st.caption(
    "Actual volatility is computed from the full covariance matrix (accounts for how holdings move "
    "together); the naive figure is what volatility would be if every holding moved in perfect lockstep. "
    "The gap between them is the real, quantified diversification benefit -- not an assumption."
)

st.divider()

# --- Backtest ---
st.subheader("Backtest: Portfolio vs. SPY")
e1, e2, e3, e4 = st.columns(4)
e1.metric("Portfolio Return (3y)", f"{bt['portfolio_return_pct']:.1f}%")
e2.metric("SPY Return (3y)", f"{bt['benchmark_return_pct']:.1f}%")
e3.metric("Portfolio Max Drawdown", f"{bt['portfolio_max_drawdown_pct']:.1f}%")
e4.metric("SPY Max Drawdown", f"{bt['benchmark_max_drawdown_pct']:.1f}%")

fig_bt = go.Figure()
fig_bt.add_trace(go.Scatter(
    x=bt["portfolio_equity"].index, y=bt["portfolio_equity"].values,
    name="Portfolio (equal-weighted, rebalanced quarterly)", line=dict(color=BLUE, width=2),
))
fig_bt.add_trace(go.Scatter(
    x=bt["benchmark_equity"].index, y=bt["benchmark_equity"].values,
    name="SPY (buy & hold)", line=dict(color=BLUE_SLATE, width=2),
))
fig_bt.update_layout(
    height=420, plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
    font=dict(color=TEXT),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    margin=dict(l=10, r=10, t=10, b=10),
    yaxis=dict(gridcolor=CARD, title="Value of $10,000"), xaxis=dict(gridcolor=CARD),
)
st.plotly_chart(fig_bt, use_container_width=True)

st.warning(
    "**Honest caveat:** the portfolio's return outperformance vs. SPY is driven substantially by "
    "NVDA and TSLA's exceptional runs over this specific 3-year window -- not a general property of "
    "diversification. The volatility reduction above (a real, quantified 35%+ benefit from spreading "
    "risk across imperfectly-correlated assets) is the generalizable finding here. Higher returns from "
    "picking stocks that already did well is not evidence those stocks will keep doing so.",
    icon="⚠️",
)
