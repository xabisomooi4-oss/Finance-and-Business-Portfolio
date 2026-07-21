"""Combined valuation summary: DDM and comps side by side, plus an honest
read on why they diverge -- not a forced single "fair value" number.
"""

from data import get_fundamentals
from ddm import run_ddm
from comps import run_comps, PEERS


def run_valuation(symbol: str = "BLK") -> dict:
    fundamentals = get_fundamentals(symbol)  # fetched once, reused by both methods below
    ddm = run_ddm(symbol, fundamentals=fundamentals)
    comps = run_comps(symbol, target_fundamentals=fundamentals)
    return {"symbol": symbol, "ddm": ddm, "comps": comps, "payout_ratio": fundamentals["payout_ratio"]}


def print_summary(result: dict) -> None:
    symbol = result["symbol"]
    ddm = result["ddm"]
    comps = result["comps"]
    price = ddm["current_price"]

    print(f"=== Valuation Summary: {symbol} ===\n")
    print(f"Current market price: ${price:.2f}\n")

    print("Method                          Implied Value    vs. Market")
    print("-" * 60)
    print(f"DDM (dividend-based)            ${ddm['intrinsic_value_per_share']:>10.2f}    {ddm['upside_downside_pct']:+.1f}%")
    print(f"Comps -- P/E                    ${comps['implied_price_pe']:>10.2f}    {comps['upside_downside_pe_pct']:+.1f}%")
    print(f"Comps -- EV/EBITDA              ${comps['implied_price_ev_ebitda']:>10.2f}    {comps['upside_downside_ev_ebitda_pct']:+.1f}%")

    payout = result["payout_ratio"]
    print()
    print("Reading the spread, not just the numbers:")
    print(
        f"- BLK pays out only ~{payout:.0%} of earnings as dividends -- DDM only values that slice. "
        f"It structurally cannot see value created by the other ~{1 - payout:.0%}, retained and reinvested into "
        f"Aladdin, buybacks, and M&A, which is most of the gap versus its own comps-implied value."
    )
    print(
        f"- Comps show BLK trading at a real premium to {', '.join(PEERS)} "
        f"(P/E {comps['own_pe']:.1f}x vs. peer avg {comps['peer_avg_pe']:.1f}x), "
        f"consistent with the market pricing in the technology/Aladdin story that DDM misses entirely -- "
        f"but comps still shows real skepticism about how large that premium should be."
    )
    print(
        "- Neither method here directly prices Aladdin as its own asset -- that's what the SOTP approach "
        "in docs/sotp-aum.html is for. Treat DDM as a lower-bound sanity check, comps as the market-based "
        "read, and SOTP/AUM (conceptual, in the docs) as the fuller picture."
    )


if __name__ == "__main__":
    result = run_valuation("BLK")
    print_summary(result)
