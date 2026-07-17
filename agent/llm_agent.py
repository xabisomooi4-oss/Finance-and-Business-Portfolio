"""The Agent: an LLM reasoning loop wrapped around the Signal Engine tools.

This is Layer 2 from the original design -- Layer 1 (data.py, indicators.py,
backtest.py, walk_forward.py, drift_check.py) computes and validates
everything; this layer reasons across those results and produces a written
call. It never fabricates a number -- every figure in its answer has to come
from a tool call.

This does NOT place trades. It's analysis only -- see Chapter VI of the Day
Trading Field Manual for why that's a deliberate design choice, not a
missing feature.
"""

import json
import os

from dotenv import load_dotenv
from anthropic import Anthropic

from tools import TOOL_DEFINITIONS, TOOL_DISPATCH

load_dotenv()

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You are a stock analysis agent built for a swing-trading, \
momentum/trend-following strategy (20-day and 50-day moving averages, \
14-day RSI, MA spread, volume ratio, trend persistence).

Ground rules, non-negotiable:
1. Never state a price, indicator value, or performance number you did not \
just get from a tool call. If you don't have a number, call a tool to get it.
2. Always call get_backtest_summary and compare the strategy's return to its \
buy_and_hold_return_pct. Walk-forward testing on this exact strategy already \
showed it does NOT reliably beat buy-and-hold on trending stocks -- report \
this honestly every time, even if it undercuts the recommendation.
3. Always call get_drift_status. If status is "DRIFT WARNING" or \
"INSUFFICIENT DATA", say so plainly and reduce your confidence accordingly.
4. Use get_recent_crossovers to check how similar past signals for this \
ticker actually resolved before trusting a new one -- a signal with a poor \
history of forward returns should be flagged as such, not ignored.
5. End with a clear call: BUY / HOLD / SELL / NO CLEAR SIGNAL, an entry \
level, a stop-loss level, and a one-line reason for each -- but frame it as \
analysis, not a guarantee. You are not placing trades; a human decides what \
to do with this.
6. If the data doesn't support a confident call, say that directly instead \
of manufacturing one. Low trade counts and small samples are real \
limitations, not details to gloss over.
"""


def run_agent(user_message: str, max_turns: int = 6, on_tool_call=None) -> str:
    """on_tool_call(name, inputs), if given, is called for every tool the
    Agent invokes -- lets a caller (e.g. the dashboard) display tool calls
    live instead of only printing to stdout."""
    client = Anthropic()
    messages = [{"role": "user", "content": user_message}]

    for _ in range(max_turns):
        response = client.messages.create(
            model=MODEL,
            max_tokens=3000,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "max_tokens":
            print("  [warning] response was cut off by the token limit -- consider raising max_tokens further")

        if response.stop_reason != "tool_use":
            return "".join(block.text for block in response.content if block.type == "text")

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if on_tool_call:
                on_tool_call(block.name, block.input)
            else:
                print(f"  [tool call] {block.name}({block.input})")
            fn = TOOL_DISPATCH[block.name]
            try:
                result = fn(**block.input)
                content = json.dumps(result)
            except Exception as e:
                content = json.dumps({"error": str(e)})
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            })

        messages.append({"role": "user", "content": tool_results})

    return "(Stopped after max_turns without a final answer -- inspect the transcript.)"


if __name__ == "__main__":
    print("=== Stock Analysis Agent ===")
    print("(Analysis only -- it never places trades. Press Ctrl+C to quit.)\n")

    ticker = input("Ticker to analyze [NVDA]: ").strip().upper() or "NVDA"
    default_question = f"What's your current read on {ticker} -- is this a buy, sell, or hold right now, and why?"
    question = input(f"Question [{default_question}]: ").strip() or default_question

    print(f"\nQuestion: {question}\n")
    answer = run_agent(question)
    print("\n=== Agent's Answer ===\n")
    print(answer)
