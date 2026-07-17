# Finance/Business Portfolio

A working portfolio of three quantitative finance projects, built end to end:

1. **Stock Analysis Agent** — entry/exit signal generation
2. **Stock Valuation Model** — DCF + comparables
3. **Portfolio Analysis & Backtesting Model** — including correlation/risk analysis

This repo is the single link referenced on my resume and applications.

## Contents

- [`docs/concept-reference.html`](docs/concept-reference.html) — a glossary of every concept behind these three projects, with diagrams. Open it directly in a browser.
- [`docs/day-trading-field-manual.html`](docs/day-trading-field-manual.html) — risk management, execution mechanics, IB-linked catalysts, honest survival statistics, and where AI genuinely helps in day trading.
- `agent/` — Stock Analysis Agent: a swing-trading (20/50-day MA, RSI) signal engine with backtesting, walk-forward validation, and a drift check, wrapped in an LLM reasoning layer (`llm_agent.py`) that calls these as tools and produces a written entry/exit call. Analysis only -- it never places trades.
- `valuation-model/` — Stock Valuation Model *(coming soon)*
- `portfolio-backtesting/` — Portfolio Analysis & Backtesting Model *(coming soon)*

## Status

🚧 In progress — building one project at a time.
