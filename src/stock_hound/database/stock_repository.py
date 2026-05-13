from pathlib import Path

import pandas as pd

from database.data_loader import StockDataLoader


class StockRepository:

    def __init__(self, db_path):

        self.loader = StockDataLoader(db_path)

    def get_recent_daily_data(
        self,
        symbol: str,
        limit: int = 50,
    ) -> pd.DataFrame:

        sql = f"""
        SELECT
            symbol,
            trade_date,
            open,
            high,
            low,
            close,
            volume,
            pct_chg
        FROM daily_data
        WHERE symbol = ?
        ORDER BY trade_date DESC
        LIMIT ?
        """

        df = self.loader.read_sql(
            sql,
            params=[symbol, limit]
        )

        return df

    def get_latest_trade_date(self):

        sql = """
        SELECT MAX(trade_date) AS latest_date
        FROM daily_data
        """

        df = self.loader.read_sql(sql)

        return df.iloc[0]["latest_date"]