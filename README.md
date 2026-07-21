# Finance/Business Portfolio

A working portfolio of three quantitative finance projects, built end to end:

1. **Stock Analysis Agent** — entry/exit signal generation
2. **Stock Valuation Model** — DDM + comparables (BlackRock, BLK)
3. **Portfolio Analysis & Backtesting Model** — including correlation/risk analysis

This repo is the single link referenced on my resume and applications.

## Contents

- [`docs/concept-reference.html`](docs/concept-reference.html) — a glossary of every concept behind these three projects, with diagrams. Open it directly in a browser.
- [`docs/day-trading-field-manual.html`](docs/day-trading-field-manual.html) — risk management, execution mechanics, IB-linked catalysts, honest survival statistics, and where AI genuinely helps in day trading.
- `agent/` — Stock Analysis Agent: a swing-trading (20/50-day MA, RSI) signal engine with backtesting, walk-forward validation, and a drift check, wrapped in an LLM reasoning layer (`llm_agent.py`) with tools for signals, backtests, news/catalysts, and watchlist scanning. Analysis only -- it never places trades.
  - `agent/dashboard.py` — a trading-terminal-style Streamlit dashboard: live price/MA/RSI charts, backtest-vs-buy-and-hold stats, a drift indicator, a ranked watchlist tier list, and **Moover** — a floating chat widget for free-form questions, grounded in the same tools and honesty rules as the rest of the Agent. Run with `streamlit run dashboard.py`.
  - `agent/notify.py` — fires a native macOS notification for notable new events only (a fresh golden/death cross, or a new drift warning). Meant to run once per trading day, since these are daily-close signals. Run with `python notify.py`.
- [`docs/ddm-comps.html`](docs/ddm-comps.html) — Dividend Discount Model & Comparable Company Analysis, applied to BlackRock (BLK).
- [`docs/sotp-aum.html`](docs/sotp-aum.html) — Sum-of-the-Parts & AUM-based valuation, covering BlackRock's Aladdin technology segment specifically.
- `valuation-model/` — Stock Valuation Model for BlackRock (BLK): `data.py` (fundamentals via yfinance, with real-world gap handling), `ddm.py` (CAPM cost of equity + Gordon Growth DDM), `comps.py` (P/E + EV/EBITDA vs. STT/TROW/IVZ/BEN), `valuation.py` (combined summary), `dashboard.py` (Streamlit dashboard, monotone institutional design). Live result: DDM implies BLK is ~68% overvalued, comps imply ~28-30% -- the gap itself is diagnosed (BLK's ~52% payout ratio means DDM can't see value from reinvested earnings) rather than papered over. See `docs/ddm-comps.html` and `docs/sotp-aum.html` for the full reasoning.
  - `valuation-model/build_excel_model.py` — generates a real, formula-driven Excel version (4 sheets: Assumptions, DDM, Comps, Summary + football-field chart) seeded with the same live data snapshot, following standard IB/PE formatting conventions (blue = input, black = formula, green = cross-sheet link). Verified error-free via LibreOffice recalculation. Run with `python build_excel_model.py`.
- `portfolio-backtesting/` — Portfolio Analysis & Backtesting Model *(coming soon)*

## Status

🚧 In progress — building one project at a time.
