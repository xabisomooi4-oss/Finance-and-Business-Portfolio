"""FastAPI backend for the Stock Analysis Agent frontend.

Wraps the existing, already-tested logic (tools.py, llm_agent.py,
backtest.py) as REST endpoints -- none of that logic changes here, this
is purely a transport layer so a real frontend can call it over HTTP
instead of running inside a Streamlit script.
"""

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from tools import (
    tool_get_current_signal, tool_get_recent_crossovers, tool_get_backtest_summary,
    tool_get_drift_status, tool_get_recent_news, tool_scan_watchlist, DEFAULT_WATCHLIST,
)
from backtest import prepare_data
from llm_agent import run_agent, run_agent_chat

app = FastAPI(title="Stock Analysis Agent API")

# GitHub Pages frontend origin(s) -- update ALLOWED_ORIGINS after the
# frontend is deployed and its real URL is known. "*" is used locally
# during development only.
ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _wrap(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/signal/{ticker}")
def signal(ticker: str):
    return _wrap(tool_get_current_signal, ticker)


@app.get("/api/crossovers/{ticker}")
def crossovers(ticker: str, lookback_days: int = 500, forward_days: int = 10):
    return _wrap(tool_get_recent_crossovers, ticker, lookback_days, forward_days)


@app.get("/api/backtest/{ticker}")
def backtest(ticker: str, period: str = "5y"):
    return _wrap(tool_get_backtest_summary, ticker, period)


@app.get("/api/drift/{ticker}")
def drift(ticker: str, period: str = "5y", recent_window_days: int = 90):
    return _wrap(tool_get_drift_status, ticker, period, recent_window_days)


@app.get("/api/news/{ticker}")
def news(ticker: str, max_articles: int = 8):
    return _wrap(tool_get_recent_news, ticker, max_articles)


@app.get("/api/watchlist")
def watchlist(tickers: str = None):
    """`tickers` as a comma-separated string, e.g. ?tickers=NVDA,AAPL -- omit for the default watchlist."""
    ticker_list = [t.strip().upper() for t in tickers.split(",")] if tickers else None
    return _wrap(tool_scan_watchlist, ticker_list)


@app.get("/api/chart/{ticker}")
def chart(ticker: str, period: str = "1y"):
    """OHLC + moving averages + RSI, formatted for TradingView's
    lightweight-charts library (candlestick + line series shapes)."""
    try:
        df = prepare_data(ticker, period=period)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    df = df.dropna(subset=["MA_20", "MA_50", "RSI_14"])
    candles = [
        {
            "time": idx.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
        }
        for idx, row in df.iterrows()
    ]
    ma20 = [{"time": idx.strftime("%Y-%m-%d"), "value": round(float(row["MA_20"]), 2)} for idx, row in df.iterrows()]
    ma50 = [{"time": idx.strftime("%Y-%m-%d"), "value": round(float(row["MA_50"]), 2)} for idx, row in df.iterrows()]
    rsi = [{"time": idx.strftime("%Y-%m-%d"), "value": round(float(row["RSI_14"]), 2)} for idx, row in df.iterrows()]
    markers = [
        {
            "time": idx.strftime("%Y-%m-%d"),
            "position": "belowBar" if row["golden_cross"] else "aboveBar",
            "color": "#2FAE72" if row["golden_cross"] else "#EF4444",
            "shape": "arrowUp" if row["golden_cross"] else "arrowDown",
            "text": "Golden Cross" if row["golden_cross"] else "Death Cross",
        }
        for idx, row in df.iterrows() if row["golden_cross"] or row["death_cross"]
    ]

    return {"candles": candles, "ma20": ma20, "ma50": ma50, "rsi": rsi, "markers": markers}


class AnalyzeRequest(BaseModel):
    ticker: str
    question: str = None


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    ticker = req.ticker.upper()
    question = req.question or f"What's your current read on {ticker} -- is this a buy, sell, or hold right now, and why?"
    tool_calls = []
    try:
        answer = run_agent(question, on_tool_call=lambda name, inputs: tool_calls.append({"name": name, "inputs": inputs}))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"answer": answer, "tool_calls": tool_calls}


class WatchlistAnalyzeRequest(BaseModel):
    tickers: list[str] = None


@app.post("/api/analyze-watchlist")
def analyze_watchlist(req: WatchlistAnalyzeRequest):
    tickers = req.tickers or DEFAULT_WATCHLIST
    question = (
        f"Scan this watchlist using scan_watchlist: {', '.join(tickers)}. "
        "Then produce a ranked tier list: Tier 1 = strongest confirmed setups right now, "
        "Tier 2 = has potential but not yet confirmed, Tier 3 = avoid or watch cautiously. "
        "For your top 1-2 picks, also check recent news and drift status before finalizing. "
        "Give a one-line reason for each ticker's tier placement, grounded in the actual numbers -- "
        "and say plainly if nothing in the watchlist looks like a strong setup right now."
    )
    tool_calls = []
    try:
        answer = run_agent(question, on_tool_call=lambda name, inputs: tool_calls.append({"name": name, "inputs": inputs}))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"answer": answer, "tool_calls": tool_calls}


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatRequest(BaseModel):
    history: list[ChatMessage] = []
    message: str


@app.post("/api/chat")
def chat(req: ChatRequest):
    history = [{"role": m.role, "content": m.content} for m in req.history]
    tool_calls = []
    try:
        answer, updated_history = run_agent_chat(
            history, req.message,
            on_tool_call=lambda name, inputs: tool_calls.append({"name": name, "inputs": inputs}),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"answer": answer, "history": updated_history, "tool_calls": tool_calls}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
