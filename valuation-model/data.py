"""Fundamentals fetcher for the Valuation Model. Pulls dividends, earnings,
beta, capital structure, and EBITDA from yfinance, with fallbacks for the
fields it sometimes leaves empty (seen live on both BLK and its peers).
"""

import yfinance as yf
import pandas as pd


def get_risk_free_rate() -> float:
    """10-year US Treasury yield (^TNX), as a decimal (e.g. 0.0456)."""
    tnx = yf.Ticker("^TNX").history(period="5d")["Close"]
    if tnx.empty:
        raise RuntimeError("Could not fetch ^TNX for the risk-free rate.")
    return round(tnx.iloc[-1] / 100, 4)


def get_shares_outstanding(ticker: yf.Ticker) -> float:
    """yfinance's info.sharesOutstanding is unreliable (None for BLK) --
    fall back to fast_info, then the balance sheet's most recent figure."""
    shares = ticker.fast_info.get("shares")
    if shares:
        return float(shares)

    bs = ticker.balance_sheet
    if "Ordinary Shares Number" in bs.index:
        return float(bs.loc["Ordinary Shares Number"].dropna().iloc[0])

    raise RuntimeError("Could not determine shares outstanding.")


def get_ebitda(ticker: yf.Ticker) -> float:
    """info.ebitda (trailing-twelve-months, more current) is preferred;
    falls back to the income statement's last full fiscal year if missing
    (seen live on STT). The two can legitimately differ -- TTM vs. FY-end
    is a real distinction, not a data bug."""
    info = ticker.info
    if info.get("ebitda"):
        return float(info["ebitda"])

    stmt = ticker.income_stmt
    if "EBITDA" in stmt.index:
        recent = stmt.loc["EBITDA"].dropna()
        if not recent.empty:
            return float(recent.iloc[0])

    return None


def get_enterprise_value(ticker: yf.Ticker, market_cap: float, total_debt: float, total_cash: float) -> float:
    """info.enterpriseValue is sometimes missing -- fall back to the
    standard formula: EV = market cap + total debt - total cash."""
    info = ticker.info
    if info.get("enterpriseValue"):
        return float(info["enterpriseValue"])
    if market_cap is not None and total_debt is not None and total_cash is not None:
        return market_cap + total_debt - total_cash
    return None


def get_fundamentals(symbol: str) -> dict:
    """Everything the DDM and comps engines need for one ticker."""
    t = yf.Ticker(symbol)
    info = t.info

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    shares = get_shares_outstanding(t)
    market_cap = info.get("marketCap") or (price * shares if price and shares else None)
    total_debt = info.get("totalDebt")
    total_cash = info.get("totalCash")
    ebitda = get_ebitda(t)
    enterprise_value = get_enterprise_value(t, market_cap, total_debt, total_cash)

    dividends = t.dividends
    # Annualize from the most recent 4 quarterly payments if available --
    # more current than info['dividendRate'], which can lag a recent raise.
    trailing_annual_dividend = float(dividends.tail(4).sum()) if len(dividends) >= 4 else info.get("dividendRate")

    return {
        "symbol": symbol,
        "price": price,
        "shares_outstanding": shares,
        "market_cap": market_cap,
        "total_debt": total_debt,
        "total_cash": total_cash,
        "beta": info.get("beta"),
        "trailing_eps": info.get("trailingEps"),
        "trailing_pe": info.get("trailingPE"),
        "payout_ratio": info.get("payoutRatio"),
        "ebitda": ebitda,
        "enterprise_value": enterprise_value,
        "ev_to_ebitda": (enterprise_value / ebitda) if enterprise_value and ebitda else None,
        "trailing_annual_dividend": trailing_annual_dividend,
        "dividend_history": dividends,
    }


if __name__ == "__main__":
    pd.set_option("display.width", 120)
    rf = get_risk_free_rate()
    print(f"Risk-free rate (10y Treasury): {rf:.2%}\n")

    for symbol in ["BLK", "STT", "TROW", "IVZ", "BEN"]:
        f = get_fundamentals(symbol)
        print(f"=== {symbol} ===")
        for k, v in f.items():
            if k == "dividend_history":
                continue
            print(f"  {k}: {v}")
        print()
