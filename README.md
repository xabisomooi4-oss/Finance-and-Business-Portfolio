# Finance/Business Portfolio

A working portfolio of three quantitative finance projects, built end to end:

1. **Stock Analysis Agent** — entry/exit signal generation
2. **Stock Valuation Model** — DCF + comparables
3. **Portfolio Analysis & Backtesting Model** — including correlation/risk analysis

This repo is the single link referenced on my resume and applications.

## Contents

- [`docs/concept-reference.html`](docs/concept-reference.html) — a glossary of every concept behind these three projects, with diagrams. Open it directly in a browser.
- [`docs/day-trading-field-manual.html`](docs/day-trading-field-manual.html) — risk management, execution mechanics, IB-linked catalysts, honest survival statistics, and where AI genuinely helps in day trading.
- `agent/` — Stock Analysis Agent: a swing-trading (20/50-day MA, RSI) signal engine with backtesting, walk-forward validation, and a drift check, wrapped in an LLM reasoning layer (`llm_agent.py`) with tools for signals, backtests, news/catalysts, and watchlist scanning. Analysis only -- it never places trades.
  - `agent/dashboard.py` — a trading-terminal-style Streamlit dashboard: live price/MA/RSI charts, backtest-vs-buy-and-hold stats, a drift indicator, a ranked watchlist tier list, and **Moover** — a multi-turn chat panel for free-form questions, grounded in the same tools and honesty rules as the rest of the Agent. Run with `streamlit run dashboard.py`.
- `valuation-model/` — Stock Valuation Model *(coming soon)*
- `portfolio-backtesting/` — Portfolio Analysis & Backtesting Model *(coming soon)*

## Status

🚧 In progress — building one project at a time.
