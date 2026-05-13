# -*- coding: utf-8 -*-
"""
配置文件 - A股日K数据库
使用 Baostock 作为数据源
"""

import os
# 禁用代理，确保直接连接 Baostock 服务器
os.environ['NO_PROXY'] = '*'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

from pathlib import Path

# ========== 路径配置 ==========
# 项目根目录 (从 src/stock_hound/fetch_stock_data/ 向上走3层)
BASE_DIR = Path(__file__).parent.parent.parent.parent.absolute()

# 数据库路径 (移到项目根目录下的 data 文件夹)
DATABASE_PATH = BASE_DIR / "data" / "stock_data.db"

# 日志文件路径
LOG_DIR = BASE_DIR / "data" / "logs"
LOG_FILE = LOG_DIR / "stock_data.log"

# ETF列表文件路径
ETF_LIST_PATH = BASE_DIR / "data" / "etf_list.csv"

# ========== 数据范围配置 ==========
# 开始日期（2000年开始）
START_DATE = "2000-01-01"
END_DATE = ""  # 留空则取今天

# ========== 数据库配置 ==========
# SQLite pragmas优化
DB_PRAGMAS = {
    "journal_mode": "WAL",           # Write-Ahead Logging模式
    "cache_size": -1024*1024*200,  # 200MB缓存
    "synchronous": 1,              # 关闭同步提升写入速度
    "temp_store": "MEMORY",        # 临时表存在内存
    "mmap_size": 300*1024*1024,   # 内存映射大小
}

# ========== Baostock 配置 ==========
# 无需 token，完全免费使用

# ========== 批量处理配置 ==========
BATCH_SIZE = 500               # 批量插入大小
STOCK_BATCH_SIZE = 100        # 每批处理的股票数量（内存友好）
PROGRESS_INTERVAL = 10         # 每处理多少只股票打印一次进度

# ========== 日志配置 ==========
LOG_LEVEL = "INFO"            # DEBUG/INFO/WARNING/ERROR
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_MAX_BYTES = 10*1024*1024  # 单个日志文件最大10MB
LOG_BACKUP_COUNT = 5         # 保留的旧日志文件数量
