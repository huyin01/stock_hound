from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd


class StockDataLoader:

    def __init__(self, db_path: str | Path):

        self.db_path = Path(db_path)

        if not self.db_path.exists():
            raise FileNotFoundError(
                f"数据库不存在: {self.db_path}"
            )

    def read_sql(
        self,
        sql: str,
        params: Optional[list] = None,
    ) -> pd.DataFrame:

        with sqlite3.connect(self.db_path) as conn:

            df = pd.read_sql(
                sql,
                conn,
                params=params,
                parse_dates=["trade_date"],
            )

        return df