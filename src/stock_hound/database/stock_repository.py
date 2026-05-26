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
            ts_code,
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
    def get_all_stocks_recent_data(self, limit: int = 50) -> pd.DataFrame:
        # 1. 设定时间过滤的起始日期（比如取最近1年，从2025年5月1日开始）
        start_date = '2025-05-01'
    
        # 2. 编写优化后的 SQL 语句
        sql = f"""
        SELECT 
            ts_code, 
            trade_date, 
            open, 
            high, 
            low, 
            close, 
            volume, 
            pct_chg
        FROM (
            SELECT 
                *,
                ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
            FROM daily_data
            WHERE trade_date >= ?  -- 【建议1】先在这里把时间范围大幅缩小
        ) ranked_data
        WHERE rn <= ?              -- 【核心逻辑】再筛选每只股票的最近 N 天
        ORDER BY ts_code, trade_date DESC
        """
        
        # 3. 传入参数执行查询
        # 第一个 ? 对应 start_date，第二个 ? 对应 limit
        df = self.loader.read_sql(sql, params=[start_date, limit])
        
        return df