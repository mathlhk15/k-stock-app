import FinanceDataReader as fdr
import pandas as pd


def get_price_data(symbol):

    try:

        df = fdr.DataReader(symbol)

        df.index = pd.to_datetime(df.index)

        return df

    except:

        return pd.DataFrame()