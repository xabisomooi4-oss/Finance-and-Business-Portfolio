"""Valuation Model dashboard: DDM + Comps on live data, in the same
monotone institutional style as docs/ddm-comps.html and docs/sotp-aum.html.

Run with: streamlit run dashboard.py
(from inside valuation-model/, with the venv activated)
"""

import streamlit as st
import plotly.graph_objects as go

from comps import PEERS
from valuation import run_valuation as _run_valuation

run_valuation = st.cache_data(ttl=300)(_run_valuation)  # avoid re-fetching on every rerun within 5 minutes

INK = "#101214"
INK_2 = "#6B7075"
MUTED = "#9BA0A5"
SURFACE = "#F3F4F5"
CARD = "#FBFBFC"
FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"


def esc(text: str) -> str:
    """Streamlit's markdown renderer treats '$...$' as LaTeX math -- escape
    dollar amounts before rendering plain text."""
    return text.replace("$", "\\$")


st.set_page_config(page_title="Valuation Model", page_icon="\U0001F3DB️", layout="wide")

st.title("Valuation Model")
st.caption("Dividend Discount Model + Comparable Company Analysis, on live data.")

col1, col2 = st.columns([3, 1])
with col1:
    ticker = st.text_input("Ticker", value="BLK", label_visibility="collapsed").strip().upper()
with col2:
    run = st.button("Run Valuation", type="primary", use_container_width=True)

if not ticker:
    st.stop()

if run or "result" not in st.session_state or st.session_state.get("last_ticker") != ticker:
    try:
        with st.spinner(f"Pulling live data and running DDM + Comps for {ticker}..."):
            st.session_state.result = run_valuation(ticker)
            st.session_state.last_ticker = ticker
    except Exception as e:
        st.error(f"Couldn't run the valuation for '{ticker}': {e}")
        st.stop()

result = st.session_state.result
ddm = result["ddm"]
comps = result["comps"]
payout = result["payout_ratio"]

# --- Top stat row ---
c1, c2, c3 = st.columns(3)
c1.metric("Current Price", f"${ddm['current_price']:.2f}")
c2.metric("DDM Intrinsic Value", f"${ddm['intrinsic_value_per_share']:.2f}", delta=f"{ddm['upside_downside_pct']:.1f}%")
c3.metric("Cost of Equity (CAPM)", f"{ddm['cost_of_equity']:.2%}")

st.divider()

# --- DDM ---
st.subheader("Dividend Discount Model")
d1, d2, d3, d4 = st.columns(4)
d1.metric("Risk-Free Rate (10y UST)", f"{ddm['risk_free_rate']:.2%}")
d2.metric("Beta", f"{ddm['beta']:.2f}")
d3.metric("Dividend Growth (5y CAGR)", f"{ddm['dividend_growth_rate']:.2%}")
d4.metric("Terminal Growth", f"{ddm['terminal_growth_rate']:.2%}")

years = [f"Yr {i + 1}" for i in range(len(ddm["pv_dividends"]))]
fig_ddm = go.Figure()
fig_ddm.add_trace(go.Bar(
    x=years, y=ddm["pv_dividends"], name="PV of projected dividends",
    marker_color=INK,
    text=[f"${v:.0f}" for v in ddm["pv_dividends"]], textposition="outside",
))
fig_ddm.add_trace(go.Bar(
    x=["Terminal"], y=[ddm["pv_terminal_value"]], name="PV of terminal value",
    marker_color=INK_2,
    text=[f"${ddm['pv_terminal_value']:.0f}"], textposition="outside",
))
fig_ddm.update_layout(
    height=380, plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
    font=dict(color=INK, family=FONT),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    margin=dict(l=10, r=10, t=10, b=10),
    yaxis=dict(gridcolor=CARD), xaxis=dict(gridcolor=CARD),
)
st.plotly_chart(fig_ddm, use_container_width=True)
st.caption(
    esc(f"Sum of both series = ${ddm['intrinsic_value_per_share']:.2f} intrinsic value per share, "
        f"discounted at the {ddm['cost_of_equity']:.2%} cost of equity.")
)

# --- Comps ---
st.divider()
st.subheader("Comparable Company Analysis")
e1, e2 = st.columns(2)
e1.metric("Implied Price (P/E)", f"${comps['implied_price_pe']:.2f}", delta=f"{comps['upside_downside_pe_pct']:.1f}%")
e2.metric("Implied Price (EV/EBITDA)", f"${comps['implied_price_ev_ebitda']:.2f}", delta=f"{comps['upside_downside_ev_ebitda_pct']:.1f}%")

all_symbols = [ticker] + PEERS
all_data = [comps["target_data"]] + comps["peer_data"]

fig_comps = go.Figure()
fig_comps.add_trace(go.Bar(
    x=all_symbols, y=[d["trailing_pe"] for d in all_data], name="P/E",
    marker_color=INK,
    text=[f"{d['trailing_pe']:.1f}x" if d["trailing_pe"] else "n/a" for d in all_data], textposition="outside",
))
fig_comps.add_trace(go.Bar(
    x=all_symbols, y=[d["ev_to_ebitda"] for d in all_data], name="EV/EBITDA",
    marker_color=INK, opacity=0.4,
    text=[f"{d['ev_to_ebitda']:.1f}x" if d["ev_to_ebitda"] else "n/a" for d in all_data], textposition="outside",
))
fig_comps.update_layout(
    barmode="group", height=380, plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
    font=dict(color=INK, family=FONT),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    margin=dict(l=10, r=10, t=10, b=10),
    yaxis=dict(gridcolor=CARD), xaxis=dict(gridcolor=CARD),
)
st.plotly_chart(fig_comps, use_container_width=True)
st.caption(
    f"P/E peers included: {', '.join(comps['peer_pe_included'])} "
    f"(excluded: {', '.join(comps['peer_pe_excluded']) or 'none'}) &middot; "
    f"EV/EBITDA peers included: {', '.join(comps['peer_ev_ebitda_included'])} "
    f"(excluded: {', '.join(comps['peer_ev_ebitda_excluded']) or 'none'})"
)

# --- Reading the spread ---
st.divider()
st.subheader("Reading the Spread")
st.markdown(esc(
    f"- **{ticker} pays out only ~{payout:.0%} of earnings as dividends** -- DDM only values that slice. "
    f"It structurally cannot see value created by the other ~{1 - payout:.0%}, retained and reinvested, "
    f"which is most of the gap between DDM and its comps-implied value."
))
st.markdown(esc(
    f"- **Comps show a real premium to peers** (P/E {comps['own_pe']:.1f}x vs. peer avg {comps['peer_avg_pe']:.1f}x) "
    f"-- consistent with the market pricing in growth/technology value that DDM misses entirely, "
    f"while still showing real skepticism about how large that premium should be."
))
st.markdown(
    "- Neither method here directly prices a technology/platform segment as its own asset -- "
    "see the Sum-of-the-Parts approach in `docs/sotp-aum.html` for that fuller picture."
)

with st.expander("Raw fundamentals (target + peers)"):
    import pandas as pd
    rows = []
    for d in all_data:
        rows.append({
            "Ticker": d["symbol"], "Price": d["price"], "P/E": d["trailing_pe"],
            "EV/EBITDA": d["ev_to_ebitda"], "Beta": d["beta"], "Payout Ratio": d["payout_ratio"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
