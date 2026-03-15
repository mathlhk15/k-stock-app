import FinanceDataReader as fdr


def resolve_kr_symbol(user_input):

    df = fdr.StockListing("KRX")

    if user_input.isdigit():

        row = df[df["Symbol"] == user_input]

    else:

        row = df[df["Name"].str.contains(user_input)]

    if len(row) == 0:
        return None, None, None

    r = row.iloc[0]

    return r.Symbol, r.Name, r.Market