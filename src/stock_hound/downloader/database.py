# -*- coding: utf-8 -*-
"""
数据库操作模块 - A股日K数据库
支持SQLite的建表、插入、查询等操作
"""

import sqlite3
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
import logging

from config import DATABASE_PATH, DB_PRAGMAS, BATCH_SIZE

# 配置日志
logger = logging.getLogger(__name__)


class StockDatabase:
    """A股数据库操作类"""
    
    def __init__(self, db_path: str = None):
        """初始化数据库连接"""
        self.db_path = str(db_path) if db_path else str(DATABASE_PATH)
        self.conn: Optional[sqlite3.Connection] = None
        self._ensure_db_dir()
        
    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def connect(self):
        """建立数据库连接"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            # 应用PRAGMA优化
            for pragma, value in DB_PRAGMAS.items():
                self.conn.execute(f"PRAGMA {pragma} = {value}")
            logger.info(f"数据库连接成功: {self.db_path}")
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("数据库连接已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        if exc_type is None:
            self.commit()
        self.close()
        return False
    
    def commit(self):
        """提交事务"""
        if self.conn:
            self.conn.commit()
    
    # ==================== 表结构操作 ====================
    
    def create_tables(self):
        """创建数据库表"""
        self.connect()
        cursor = self.conn.cursor()
        
        # 股票信息表（存储股票基本信息）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_info (
                ts_code VARCHAR(20) PRIMARY KEY,     -- 股票代码 (带后缀，如000001.SZ)
                symbol VARCHAR(20),                  -- 股票代码（不带后缀）
                name VARCHAR(100),                    -- 股票名称
                market VARCHAR(50),                  -- 市场（SSE/SZSE/BSE）
                list_status VARCHAR(10),             -- 上市状态（L/D/P）
                list_date VARCHAR(20),               -- 上市日期
                delist_date VARCHAR(20),             -- 退市日期
                is_etf INTEGER DEFAULT 0,            -- 是否ETF
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_info_symbol ON stock_info(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_info_market ON stock_info(market)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_info_list_status ON stock_info(list_status)")
        
        # 日K数据表（支持前复权、后复权、不复权三种价格）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_data (
                ts_code VARCHAR(20),                 -- 股票代码
                trade_date VARCHAR(20),              -- 交易日期
                open DECIMAL(10, 3),                  -- 开盘价（不复权）
                high DECIMAL(10, 3),                  -- 最高价（不复权）
                low DECIMAL(10, 3),                   -- 最低价（不复权）
                close DECIMAL(10, 3),                 -- 收盘价（不复权）
                pre_close DECIMAL(10, 3),             -- 昨收价
                volume DECIMAL(20, 2),                -- 成交量
                amount DECIMAL(20, 2),                -- 成交额
                pct_chg DECIMAL(10, 4),               -- 涨跌幅
                -- 前复权价格
                open_qfq DECIMAL(10, 3),
                high_qfq DECIMAL(10, 3),
                low_qfq DECIMAL(10, 3),
                close_qfq DECIMAL(10, 3),
                -- 后复权价格
                open_hfq DECIMAL(10, 3),
                high_hfq DECIMAL(10, 3),
                low_hfq DECIMAL(10, 3),
                close_hfq DECIMAL(10, 3),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ts_code, trade_date)
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_code_date ON daily_data(ts_code, trade_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_trade_date ON daily_data(trade_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_ts_code ON daily_data(ts_code)")
        
        # 日期拉取记录表（记录每天的数据状态）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fetch_log (
                trade_date VARCHAR(20) PRIMARY KEY,   -- 交易日期
                status VARCHAR(20),                   -- 状态（pending/doing/done/failed）
                record_count INTEGER DEFAULT 0,       -- 记录数
                error_msg TEXT,                        -- 错误信息
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.conn.commit()
        logger.info("数据库表创建完成")
    
    # ==================== 股票信息操作 ====================
    
    def insert_stock_info(self, stock_list: List[Dict[str, Any]]):
        """批量插入股票信息"""
        if not stock_list:
            return 0
            
        self.connect()
        cursor = self.conn.cursor()
        
        sql = """
            INSERT OR REPLACE INTO stock_info 
            (ts_code, symbol, name, market, list_status, list_date, delist_date, is_etf)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        data = [
            (
                s.get('ts_code', ''),
                s.get('symbol', ''),
                s.get('name', ''),
                s.get('market', ''),
                s.get('list_status', 'L'),
                s.get('list_date', ''),
                s.get('delist_date', ''),
                1 if s.get('is_etf') else 0
            )
            for s in stock_list
        ]
        
        cursor.executemany(sql, data)
        self.conn.commit()
        logger.info(f"成功插入/更新 {len(data)} 条股票信息")
        return len(data)
    
    def get_all_stocks(self, list_status: str = None, is_etf: int = None) -> List[Dict[str, Any]]:
        """获取股票列表"""
        self.connect()
        cursor = self.conn.cursor()
        
        sql = "SELECT * FROM stock_info WHERE 1=1"
        params = []
        
        if list_status:
            sql += " AND list_status = ?"
            params.append(list_status)
        
        if is_etf is not None:
            sql += " AND is_etf = ?"
            params.append(is_etf)
        
        sql += " ORDER BY ts_code"
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_stock_count(self, list_status: str = None) -> int:
        """获取股票数量"""
        self.connect()
        cursor = self.conn.cursor()
        
        if list_status:
            cursor.execute("SELECT COUNT(*) FROM stock_info WHERE list_status = ?", (list_status,))
        else:
            cursor.execute("SELECT COUNT(*) FROM stock_info")
        
        return cursor.fetchone()[0]
    
    def get_stock_by_code(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """根据代码获取股票信息"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM stock_info WHERE ts_code = ?", (ts_code,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    # ==================== 日K数据操作 ====================
    
    def insert_daily_data(self, data_list: List[Dict[str, Any]], batch_size: int = None):
        """批量插入日K数据"""
        if not data_list:
            return 0
            
        self.connect()
        batch_size = batch_size or BATCH_SIZE
        
        cursor = self.conn.cursor()
        sql = """
            INSERT OR REPLACE INTO daily_data 
            (ts_code, trade_date, open, high, low, close, pre_close, volume, amount, pct_chg,
             open_qfq, high_qfq, low_qfq, close_qfq, open_hfq, high_hfq, low_hfq, close_hfq)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        total = 0
        for i in range(0, len(data_list), batch_size):
            batch = data_list[i:i+batch_size]
            
            data = [
                (
                    d.get('ts_code', ''),
                    d.get('trade_date', ''),
                    float(d.get('open', 0)),
                    float(d.get('high', 0)),
                    float(d.get('low', 0)),
                    float(d.get('close', 0)),
                    float(d.get('pre_close', 0)),
                    float(d.get('volume', 0)),
                    float(d.get('amount', 0)),
                    float(d.get('pct_chg', 0)) if d.get('pct_chg') is not None else 0,
                    # 前复权
                    float(d.get('open_qfq', d.get('open', 0))),
                    float(d.get('high_qfq', d.get('high', 0))),
                    float(d.get('low_qfq', d.get('low', 0))),
                    float(d.get('close_qfq', d.get('close', 0))),
                    # 后复权
                    float(d.get('open_hfq', d.get('open', 0))),
                    float(d.get('high_hfq', d.get('high', 0))),
                    float(d.get('low_hfq', d.get('low', 0))),
                    float(d.get('close_hfq', d.get('close', 0))),
                )
                for d in batch
            ]
            
            cursor.executemany(sql, data)
            total += len(batch)
        
        self.conn.commit()
        return total
    
    def get_latest_date(self, ts_code: str = None) -> Optional[str]:
        """获取最新交易日期"""
        self.connect()
        cursor = self.conn.cursor()
        
        if ts_code:
            cursor.execute("SELECT MAX(trade_date) FROM daily_data WHERE ts_code = ?", (ts_code,))
        else:
            cursor.execute("SELECT MAX(trade_date) FROM daily_data")
        
        result = cursor.fetchone()[0]
        return result if result else None
    
    def get_earliest_date(self, ts_code: str = None) -> Optional[str]:
        """获取最早交易日期"""
        self.connect()
        cursor = self.conn.cursor()
        
        if ts_code:
            cursor.execute("SELECT MIN(trade_date) FROM daily_data WHERE ts_code = ?", (ts_code,))
        else:
            cursor.execute("SELECT MIN(trade_date) FROM daily_data")
        
        result = cursor.fetchone()[0]
        return result if result else None
    
    def get_data_count(self, ts_code: str = None) -> int:
        """获取数据条数"""
        self.connect()
        cursor = self.conn.cursor()
        
        if ts_code:
            cursor.execute("SELECT COUNT(*) FROM daily_data WHERE ts_code = ?", (ts_code,))
        else:
            cursor.execute("SELECT COUNT(*) FROM daily_data")
        
        return cursor.fetchone()[0]
    
    def check_date_has_data(self, trade_date: str) -> bool:
        """检查某天是否有数据"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM daily_data WHERE trade_date = ?", (trade_date,))
        return cursor.fetchone()[0] > 0
    
    def check_data_exists(self, ts_code: str, trade_date: str) -> bool:
        """检查某条数据是否存在"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM daily_data WHERE ts_code = ? AND trade_date = ?",
            (ts_code, trade_date)
        )
        return cursor.fetchone() is not None
    
    # ==================== 拉取日志 ====================
    
    def mark_fetch_start(self, trade_date: str):
        """标记开始拉取某天的数据"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO fetch_log (trade_date, status, start_time)
            VALUES (?, 'doing', CURRENT_TIMESTAMP)
        """, (trade_date,))
        self.conn.commit()
    
    def mark_fetch_done(self, trade_date: str, record_count: int):
        """标记拉取完成"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE fetch_log 
            SET status = 'done', record_count = ?, end_time = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE trade_date = ?
        """, (record_count, trade_date))
        self.conn.commit()
    
    def mark_fetch_failed(self, trade_date: str, error_msg: str):
        """标记拉取失败"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE fetch_log 
            SET status = 'failed', error_msg = ?, end_time = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE trade_date = ?
        """, (error_msg, trade_date))
        self.conn.commit()
    
    def get_fetch_status(self, trade_date: str) -> Optional[Dict[str, Any]]:
        """获取某天的拉取状态"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM fetch_log WHERE trade_date = ?", (trade_date,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_all_fetch_dates(self) -> List[str]:
        """获取所有已拉取的日期"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT trade_date FROM fetch_log WHERE status = 'done' ORDER BY trade_date")
        return [row[0] for row in cursor.fetchall()]
    
    def get_failed_dates(self) -> List[str]:
        """获取失败的日期列表"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT trade_date FROM fetch_log WHERE status = 'failed' ORDER BY trade_date")
        return [row[0] for row in cursor.fetchall()]
    
    def get_missing_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取缺失的日期列表"""
        self.connect()
        cursor = self.conn.cursor()
        
        # 获取所有已完成和正在进行的日期
        cursor.execute("""
            SELECT trade_date FROM fetch_log 
            WHERE trade_date BETWEEN ? AND ?
            AND status IN ('done', 'doing')
            ORDER BY trade_date
        """, (start_date, end_date))
        
        fetched = set(row[0] for row in cursor.fetchall())
        
        # 生成完整日期范围
        from datetime import datetime, timedelta
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')
        
        all_dates = []
        current = start
        while current <= end:
            date_str = current.strftime('%Y%m%d')
            if date_str not in fetched:
                all_dates.append(date_str)
            current += timedelta(days=1)
        
        return all_dates
    
    # ==================== 查询功能 ====================
    
    def query_daily_data(self, ts_code: str = None, start_date: str = None, 
                         end_date: str = None, limit: int = None,
                         adjust: str = None) -> List[Dict[str, Any]]:
        """
        查询日K数据
        adjust: None-不复权, 'qfq'-前复权, 'hfq'-后复权
        """
        self.connect()
        cursor = self.conn.cursor()
        
        # 选择复权后的价格字段
        if adjust == 'qfq':
            price_fields = "open_qfq as open, high_qfq as high, low_qfq as low, close_qfq as close"
        elif adjust == 'hfq':
            price_fields = "open_hfq as open, high_hfq as high, low_hfq as low, close_hfq as close"
        else:
            price_fields = "open, high, low, close"
        
        sql = f"""
            SELECT ts_code, trade_date, {price_fields}, 
                   pre_close, volume, amount, pct_chg
            FROM daily_data WHERE 1=1
        """
        params = []
        
        if ts_code:
            sql += " AND ts_code = ?"
            params.append(ts_code)
        
        if start_date:
            sql += " AND trade_date >= ?"
            params.append(start_date)
        
        if end_date:
            sql += " AND trade_date <= ?"
            params.append(end_date)
        
        sql += " ORDER BY trade_date DESC"
        
        if limit:
            sql += f" LIMIT {limit}"
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_db_size(self) -> str:
        """获取数据库大小"""
        db_path = Path(self.db_path)
        if db_path.exists():
            size_bytes = db_path.stat().st_size
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024*1024:
                return f"{size_bytes/1024:.2f} KB"
            elif size_bytes < 1024*1024*1024:
                return f"{size_bytes/(1024*1024):.2f} MB"
            else:
                return f"{size_bytes/(1024*1024*1024):.2f} GB"
        return "0 B"
    
    def vacuum(self):
        """压缩数据库"""
        self.connect()
        self.conn.execute("VACUUM")
        logger.info("数据库压缩完成")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        self.connect()
        cursor = self.conn.cursor()
        
        stats = {}
        
        # 股票数量
        cursor.execute("SELECT COUNT(*) FROM stock_info")
        stats['stock_count'] = cursor.fetchone()[0]
        
        # ETF数量
        cursor.execute("SELECT COUNT(*) FROM stock_info WHERE is_etf = 1")
        stats['etf_count'] = cursor.fetchone()[0]
        
        # 日K数据量
        cursor.execute("SELECT COUNT(*) FROM daily_data")
        stats['daily_data_count'] = cursor.fetchone()[0]
        
        # 日期范围
        cursor.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_data")
        result = cursor.fetchone()
        stats['date_range'] = (result[0], result[1]) if result[0] else (None, None)
        
        # 已拉取天数
        cursor.execute("SELECT COUNT(*) FROM fetch_log WHERE status = 'done'")
        stats['fetched_days'] = cursor.fetchone()[0]
        
        # 数据库大小
        stats['db_size'] = self.get_db_size()
        
        return stats
    
    def get_fetched_stock_codes(self) -> List[str]:
        """从 daily_data 表获取已有股票代码"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT ts_code FROM daily_data")
        return [row[0] for row in cursor.fetchall()]


def init_database(db_path: str = None) -> StockDatabase:
    """初始化数据库（创建表结构）"""
    db = StockDatabase(db_path)
    db.create_tables()
    return db
