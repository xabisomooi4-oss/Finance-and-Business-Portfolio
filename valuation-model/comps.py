"""Comparable Company Analysis: peer P/E and EV/EBITDA multiples applied
to BlackRock's own earnings and EBITDA to back into an implied price.

Peer data has real gaps (STT has no EV/EBITDA, IVZ has negative EPS so no
P/E) -- averages are computed only from peers where that specific metric
is available, and which peers were excluded is reported explicitly rather
than silently skewing the average.
"""

from concurrent.futures import ThreadPoolExecutor

from data import get_fundamentals

PEERS = ["STT", "TROW", "IVZ", "BEN"]


def fetch_peers(peers: list) -> list:
    """Peer fetches are independent network calls -- run them concurrently
    instead of one at a time. Order is preserved to match `peers`."""
    with ThreadPoolExecutor(max_workers=len(peers)) as pool:
        return list(pool.map(get_fundamentals, peers))


def peer_average_multiple(peer_data: list, field: str) -> tuple:
    """Returns (average, included_symbols, excluded_symbols)."""
    included = [(p["symbol"], p[field]) for p in peer_data if p.get(field) is not None]
    excluded = [p["symbol"] for p in peer_data if p.get(field) is None]
    if not included:
        return None, [], excluded
    avg = sum(v for _, v in included) / len(included)
    return avg, [s for s, _ in included], excluded


def run_comps(symbol: str = "BLK", peers: list = None, target_fundamentals: dict = None) -> dict:
    """Pass `target_fundamentals` (from data.get_fundamentals) to reuse an
    already-fetched result for `symbol` instead of hitting yfinance again."""
    peers = peers or PEERS
    target = target_fundamentals or get_fundamentals(symbol)
    peer_data = fetch_peers(peers)

    avg_pe, pe_included, pe_excluded = peer_average_multiple(peer_data, "trailing_pe")
    avg_ev_ebitda, ev_included, ev_excluded = peer_average_multiple(peer_data, "ev_to_ebitda")

    implied_price_pe = avg_pe * target["trailing_eps"] if avg_pe and target["trailing_eps"] else None

    implied_price_ev_ebitda = None
    if avg_ev_ebitda and target["ebitda"]:
        implied_ev = avg_ev_ebitda * target["ebitda"]
        implied_equity_value = implied_ev - target["total_debt"] + target["total_cash"]
        implied_price_ev_ebitda = implied_equity_value / target["shares_outstanding"]

    price = target["price"]
    return {
        "symbol": symbol,
        "current_price": price,
        "target_data": target,
        "peer_data": peer_data,
        "own_pe": target["trailing_pe"],
        "own_ev_ebitda": target["ev_to_ebitda"],
        "peer_avg_pe": avg_pe,
        "peer_pe_included": pe_included,
        "peer_pe_excluded": pe_excluded,
        "peer_avg_ev_ebitda": avg_ev_ebitda,
        "peer_ev_ebitda_included": ev_included,
        "peer_ev_ebitda_excluded": ev_excluded,
        "implied_price_pe": implied_price_pe,
        "implied_price_ev_ebitda": implied_price_ev_ebitda,
        "upside_downside_pe_pct": (implied_price_pe / price - 1) * 100 if implied_price_pe and price else None,
        "upside_downside_ev_ebitda_pct": (implied_price_ev_ebitda / price - 1) * 100 if implied_price_ev_ebitda and price else None,
    }


if __name__ == "__main__":
    r = run_comps()
    print(f"=== Comps: {r['symbol']} vs. {', '.join(PEERS)} ===\n")
    print(f"Current price: ${r['current_price']:.2f}")
    print(f"BLK's own P/E: {r['own_pe']:.1f}x   BLK's own EV/EBITDA: {r['own_ev_ebitda']:.1f}x")
    print()
    print(f"Peer avg P/E:       {r['peer_avg_pe']:.1f}x  (from {', '.join(r['peer_pe_included'])}; "
          f"excluded: {', '.join(r['peer_pe_excluded']) or 'none'})")
    print(f"Peer avg EV/EBITDA: {r['peer_avg_ev_ebitda']:.1f}x  (from {', '.join(r['peer_ev_ebitda_included'])}; "
          f"excluded: {', '.join(r['peer_ev_ebitda_excluded']) or 'none'})")
    print()
    print(f"Implied price (P/E method):       ${r['implied_price_pe']:.2f}  ({r['upside_downside_pe_pct']:+.1f}%)")
    print(f"Implied price (EV/EBITDA method): ${r['implied_price_ev_ebitda']:.2f}  ({r['upside_downside_ev_ebitda_pct']:+.1f}%)")
