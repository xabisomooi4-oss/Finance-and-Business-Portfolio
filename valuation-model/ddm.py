"""Dividend Discount Model: CAPM cost of equity, dividend projection,
Gordon Growth terminal value, discounted to an intrinsic value per share.

Discounts at cost of equity, not WACC -- dividends are a cash flow that
reaches equity holders specifically, never debt holders, so there's no
capital structure to blend. See docs/ddm-comps.html for the full reasoning.
"""

import pandas as pd

from data import get_fundamentals, get_risk_free_rate

EQUITY_RISK_PREMIUM = 0.05   # Damodaran-style long-run US ERP assumption
TERMINAL_GROWTH_RATE = 0.04  # long-run sustainable growth, ~nominal GDP
FORECAST_YEARS = 5


def cost_of_equity(beta: float, risk_free_rate: float, erp: float = EQUITY_RISK_PREMIUM) -> float:
    """CAPM: Re = Rf + Beta * ERP."""
    return risk_free_rate + beta * erp


def historical_dividend_growth(dividend_history: pd.Series, years: int = 5) -> float:
    """CAGR of annual dividend totals, computed from real payment history.
    Only counts years with a full 4 quarterly payments -- the current
    partial year would otherwise understate growth."""
    annual = dividend_history.groupby(dividend_history.index.year).agg(["sum", "count"])
    complete_years = annual[annual["count"] >= 4]["sum"]
    if len(complete_years) < 2:
        return None

    recent = complete_years.tail(years + 1)
    n_years = len(recent) - 1
    if n_years < 1:
        return None
    return (recent.iloc[-1] / recent.iloc[0]) ** (1 / n_years) - 1


def project_dividends(current_annual_dividend: float, growth_rate: float, years: int = FORECAST_YEARS) -> list:
    divs = []
    d = current_annual_dividend
    for _ in range(years):
        d = d * (1 + growth_rate)
        divs.append(d)
    return divs


def terminal_value(final_year_dividend: float, discount_rate: float, terminal_growth: float = TERMINAL_GROWTH_RATE) -> float:
    """Gordon Growth Model: TV = D_(n+1) / (r - g)."""
    if discount_rate <= terminal_growth:
        raise ValueError("Discount rate must exceed terminal growth rate for Gordon Growth to be valid.")
    next_dividend = final_year_dividend * (1 + terminal_growth)
    return next_dividend / (discount_rate - terminal_growth)


def present_value_series(cash_flows: list, discount_rate: float) -> list:
    return [cf / (1 + discount_rate) ** (i + 1) for i, cf in enumerate(cash_flows)]


def run_ddm(symbol: str, growth_rate: float = None, forecast_years: int = FORECAST_YEARS) -> dict:
    f = get_fundamentals(symbol)
    rf = get_risk_free_rate()
    re = cost_of_equity(f["beta"], rf)

    if growth_rate is None:
        growth_rate = historical_dividend_growth(f["dividend_history"])
        if growth_rate is None:
            raise ValueError(f"Not enough dividend history for {symbol} to estimate a growth rate -- pass one explicitly.")

    current_dividend = f["trailing_annual_dividend"]
    projected = project_dividends(current_dividend, growth_rate, forecast_years)
    pv_dividends = present_value_series(projected, re)

    tv = terminal_value(projected[-1], re, TERMINAL_GROWTH_RATE)
    pv_terminal = tv / (1 + re) ** forecast_years

    intrinsic_value = sum(pv_dividends) + pv_terminal

    return {
        "symbol": symbol,
        "current_price": f["price"],
        "risk_free_rate": rf,
        "beta": f["beta"],
        "cost_of_equity": re,
        "dividend_growth_rate": growth_rate,
        "terminal_growth_rate": TERMINAL_GROWTH_RATE,
        "current_annual_dividend": current_dividend,
        "projected_dividends": projected,
        "pv_dividends": pv_dividends,
        "terminal_value": tv,
        "pv_terminal_value": pv_terminal,
        "intrinsic_value_per_share": intrinsic_value,
        "upside_downside_pct": (intrinsic_value / f["price"] - 1) * 100 if f["price"] else None,
    }


if __name__ == "__main__":
    r = run_ddm("BLK")
    print(f"=== DDM: {r['symbol']} ===\n")
    print(f"Current price:              ${r['current_price']:.2f}")
    print(f"Risk-free rate (10y UST):   {r['risk_free_rate']:.2%}")
    print(f"Beta:                       {r['beta']}")
    print(f"Cost of equity (CAPM):      {r['cost_of_equity']:.2%}")
    print(f"Dividend growth (5y CAGR):  {r['dividend_growth_rate']:.2%}")
    print(f"Terminal growth rate:       {r['terminal_growth_rate']:.2%}")
    print(f"Current annual dividend:    ${r['current_annual_dividend']:.2f}")
    print()
    print("Projected dividends:", [f"${d:.2f}" for d in r["projected_dividends"]])
    print("PV of dividends:    ", [f"${d:.2f}" for d in r["pv_dividends"]])
    print(f"Terminal value:             ${r['terminal_value']:.2f}")
    print(f"PV of terminal value:       ${r['pv_terminal_value']:.2f}")
    print()
    print(f"Intrinsic value per share:  ${r['intrinsic_value_per_share']:.2f}")
    print(f"Current market price:       ${r['current_price']:.2f}")
    print(f"Implied upside/downside:    {r['upside_downside_pct']:.1f}%")
