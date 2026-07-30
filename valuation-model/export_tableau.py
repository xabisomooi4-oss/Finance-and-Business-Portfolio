"""Flattens the DDM + Comps valuation output into tidy CSVs for Tableau
Public, which wants one row per observation rather than the nested dicts
run_valuation() returns. Run with `python export_tableau.py`.
"""

import csv
import os

from ddm import cost_of_equity, present_value_series, project_dividends, terminal_value, TERMINAL_GROWTH_RATE
from comps import PEERS
from valuation import run_valuation

OUT_DIR = os.path.join(os.path.dirname(__file__), "tableau_data")


def write_csv(filename: str, fieldnames: list, rows: list) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


def export_ddm_cashflows(result: dict) -> None:
    ddm = result["ddm"]
    rows = []
    for i, (proj, pv) in enumerate(zip(ddm["projected_dividends"], ddm["pv_dividends"]), start=1):
        rows.append({
            "symbol": result["symbol"], "period": f"Year {i}", "period_order": i,
            "component": "Dividend", "projected_cash_flow": round(proj, 4), "present_value": round(pv, 4),
        })
    rows.append({
        "symbol": result["symbol"], "period": "Terminal Value", "period_order": len(ddm["projected_dividends"]) + 1,
        "component": "Terminal Value", "projected_cash_flow": round(ddm["terminal_value"], 4),
        "present_value": round(ddm["pv_terminal_value"], 4),
    })
    write_csv(
        "ddm_cashflow_detail.csv",
        ["symbol", "period", "period_order", "component", "projected_cash_flow", "present_value"],
        rows,
    )


def export_ddm_sensitivity(result: dict) -> None:
    """Intrinsic value across a grid of growth-rate and discount-rate
    assumptions -- the standard IB sensitivity table, since the base case
    is just one point on this surface and DDM output is highly sensitive
    to both inputs."""
    ddm = result["ddm"]
    base_growth = ddm["dividend_growth_rate"]
    base_re = ddm["cost_of_equity"]
    current_dividend = ddm["current_annual_dividend"]

    growth_scenarios = [base_growth + delta for delta in (-0.02, -0.01, 0.0, 0.01, 0.02)]
    discount_scenarios = [base_re + delta for delta in (-0.02, -0.01, 0.0, 0.01, 0.02)]

    rows = []
    for g in growth_scenarios:
        for r in discount_scenarios:
            if r <= TERMINAL_GROWTH_RATE:
                continue  # Gordon Growth is undefined here, skip
            projected = project_dividends(current_dividend, g, len(ddm["projected_dividends"]))
            pv_divs = present_value_series(projected, r)
            tv = terminal_value(projected[-1], r, TERMINAL_GROWTH_RATE)
            pv_tv = tv / (1 + r) ** len(projected)
            intrinsic = sum(pv_divs) + pv_tv
            rows.append({
                "symbol": result["symbol"],
                "growth_rate": round(g, 4), "discount_rate": round(r, 4),
                "is_base_case": g == base_growth and r == base_re,
                "intrinsic_value_per_share": round(intrinsic, 2),
                "upside_downside_pct": round((intrinsic / ddm["current_price"] - 1) * 100, 2),
            })
    write_csv(
        "ddm_sensitivity.csv",
        ["symbol", "growth_rate", "discount_rate", "is_base_case", "intrinsic_value_per_share", "upside_downside_pct"],
        rows,
    )


def export_comps_peers(result: dict) -> None:
    comps = result["comps"]
    rows = [{
        "symbol": comps["symbol"], "is_target": True,
        "trailing_pe": comps["own_pe"], "ev_to_ebitda": comps["own_ev_ebitda"],
    }]
    for peer in comps["peer_data"]:
        rows.append({
            "symbol": peer["symbol"], "is_target": False,
            "trailing_pe": peer.get("trailing_pe"), "ev_to_ebitda": peer.get("ev_to_ebitda"),
        })
    rows.append({
        "symbol": f"Peer Avg ({'/'.join(PEERS)})", "is_target": False,
        "trailing_pe": round(comps["peer_avg_pe"], 2) if comps["peer_avg_pe"] else None,
        "ev_to_ebitda": round(comps["peer_avg_ev_ebitda"], 2) if comps["peer_avg_ev_ebitda"] else None,
    })
    write_csv("comps_peer_multiples.csv", ["symbol", "is_target", "trailing_pe", "ev_to_ebitda"], rows)


def export_valuation_summary(result: dict) -> None:
    ddm, comps = result["ddm"], result["comps"]
    price = ddm["current_price"]
    rows = [
        {"symbol": result["symbol"], "method": "DDM (Dividend-Based)", "implied_price": round(ddm["intrinsic_value_per_share"], 2),
         "current_price": round(price, 2), "upside_downside_pct": round(ddm["upside_downside_pct"], 2)},
        {"symbol": result["symbol"], "method": "Comps -- P/E", "implied_price": round(comps["implied_price_pe"], 2),
         "current_price": round(price, 2), "upside_downside_pct": round(comps["upside_downside_pe_pct"], 2)},
        {"symbol": result["symbol"], "method": "Comps -- EV/EBITDA", "implied_price": round(comps["implied_price_ev_ebitda"], 2),
         "current_price": round(price, 2), "upside_downside_pct": round(comps["upside_downside_ev_ebitda_pct"], 2)},
    ]
    write_csv("valuation_summary.csv", ["symbol", "method", "implied_price", "current_price", "upside_downside_pct"], rows)


if __name__ == "__main__":
    result = run_valuation("BLK")
    export_ddm_cashflows(result)
    export_ddm_sensitivity(result)
    export_comps_peers(result)
    export_valuation_summary(result)
    print("\nDone. Open valuation-model/tableau_data/*.csv in Tableau Public.")
