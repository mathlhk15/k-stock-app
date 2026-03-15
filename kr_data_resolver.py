import FinanceDataReader as fdr


def resolve_kr_symbol(user_input):
    df = fdr.StockListing("KRX")

    if "Code" in df.columns and "Symbol" not in df.columns:
        df = df.rename(columns={"Code": "Symbol"})

    raw = (user_input or "").strip()

    if not raw:
        return None, None, None

    if raw.isdigit() and len(raw) == 6:
        row = df[df["Symbol"].astype(str) == raw]
    else:
        row = df[df["Name"].astype(str).str.contains(raw, case=False, na=False)]

    if len(row) == 0:
        return None, None, None

    r = row.iloc[0]

    symbol = str(r["Symbol"]) if "Symbol" in r.index else None
    name = str(r["Name"]) if "Name" in r.index else raw
    market = str(r["Market"]) if "Market" in r.index else "N/A"

    return symbol, name, market
