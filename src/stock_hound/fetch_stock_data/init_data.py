# -*- coding: utf-8 -*-
"""
初始化历史数据脚本 - A股日K数据库
使用 Baostock 数据源，按股票代码拉取
支持断点续传、分段初始化
"""

import sys
import logging
import logging.handlers
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import time

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    DATABASE_PATH, LOG_FILE, LOG_DIR, LOG_LEVEL, LOG_FORMAT,
    STOCK_BATCH_SIZE, PROGRESS_INTERVAL, START_DATE
)
from database import StockDatabase, init_database
from fetcher import DataFetcher


def setup_logging():
    """配置日志"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # 清除已有的handlers
    logger.handlers.clear()
    
    # 文件日志
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    
    # 控制台日志
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


logger = setup_logging()


class ProgressTracker:
    """进度跟踪器"""
    
    def __init__(self, total: int):
        self.total = total
        self.completed = 0
        self.failed = 0
        self.cached_records = 0
        self.start_time = time.time()
        self.last_log_time = time.time()
    
    def update(self, completed: int, failed: int, cached_records: int):
        self.completed = completed
        self.failed = failed
        self.cached_records = cached_records
    
    def get_elapsed(self) -> float:
        return time.time() - self.start_time
    
    def get_eta(self) -> Optional[float]:
        if self.completed == 0:
            return None
        elapsed = self.get_elapsed()
        rate = self.completed / elapsed
        remaining = self.total - self.completed
        if rate > 0:
            return remaining / rate
        return None
    
    def format_time(self, seconds: float) -> str:
        if seconds is None:
            return "未知"
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            return f"{int(seconds/60)}分{int(seconds%60)}秒"
        else:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            return f"{hours}小时{mins}分"
    
    def should_log(self) -> bool:
        return time.time() - self.last_log_time > 10
    
    def log_now(self):
        self.last_log_time = time.time()
    
    def get_summary(self) -> str:
        pct = (self.completed / self.total * 100) if self.total > 0 else 0
        eta = self.get_eta()
        elapsed = self.get_elapsed()
        cache_mb = self.cached_records * 100 / (1024 * 1024)
        
        return (
            f"[{self.completed}/{self.total}] ({pct:.1f}%) | "
            f"失败:{self.failed} | "
            f"缓存:~{cache_mb:.0f}MB | "
            f"已用:{self.format_time(elapsed)} | "
            f"剩余:{self.format_time(eta)}"
        )


class InitDataRunner:
    """历史数据初始化运行器"""
    
    def __init__(self):
        self.fetcher = DataFetcher()
        self.db = init_database()
        self.today = datetime.now().strftime('%Y-%m-%d')
        self.progress: Optional[ProgressTracker] = None
        self.cached_data: List[Dict[str, Any]] = []
        self.failed_stocks: List[str] = []
    
    def update_stock_list(self) -> int:
        """更新股票列表（股票 + ETF）"""
        logger.info("=" * 60)
        logger.info("步骤1: 更新股票列表")
        logger.info("=" * 60)
        
        existing_count = self.db.get_stock_count()
        logger.info(f"数据库中已有 {existing_count} 只股票")
        
        all_records = []
        
        # 获取股票列表（从Baostock）
        stocks = self.fetcher.get_all_stocks()
        if stocks:
            for s in stocks:
                record = {
                    'ts_code': self._bs_code_to_ts_code(s['code']),
                    'symbol': s['symbol'],
                    'name': s['name'],
                    'market': s['market'],
                    'list_status': 'L',
                    'list_date': '',
                    'delist_date': '',
                    'is_etf': 0
                }
                all_records.append(record)
            logger.info(f"股票: {len(stocks)} 只")
        
        # 获取ETF列表（从akshare）
        etfs = self.fetcher.get_etf_list()
        if etfs:
            for e in etfs:
                record = {
                    'ts_code': self._bs_code_to_ts_code(e['code']),
                    'symbol': e['symbol'],
                    'name': e['name'],
                    'market': e['market'],
                    'list_status': 'L',
                    'list_date': '',
                    'delist_date': '',
                    'is_etf': 1
                }
                all_records.append(record)
            logger.info(f"ETF: {len(etfs)} 只")
        
        if all_records:
            self.db.insert_stock_info(all_records)
            logger.info(f"股票列表更新完成: {len(all_records)} 只（股票+ETF）")
        else:
            logger.warning("未能获取到股票列表")
        
        return len(all_records)
    
    def _bs_code_to_ts_code(self, bs_code: str) -> str:
        """Baostock代码转为tushare格式"""
        if not bs_code:
            return ""
        parts = bs_code.split('.')
        if len(parts) != 2:
            return bs_code
        market, symbol = parts
        return f"{symbol}.{'SH' if market == 'sh' else 'SZ'}"
    
    def _on_progress(self, completed: int, total: int, cached_records: int):
        """进度回调"""
        if self.progress:
            self.progress.update(completed, len(self.failed_stocks), cached_records)
            if self.progress.should_log():
                logger.info(self.progress.get_summary())
                self.progress.log_now()
    
    def fetch_and_cache(
        self, 
        stock_codes: List[str] = None,
        start_date: str = None,
        end_date: str = None,
        adjustflag: str = "3",
        batch_size: int = 100  # 每100只写入一次
    ) -> Dict[str, Any]:
        """
        拉取股票数据并分批写入数据库
        
        Args:
            stock_codes: 股票代码列表，默认全部
            start_date: 开始日期
            end_date: 结束日期
            adjustflag: 复权方式 1=后复权, 2=前复权, 3=不复权
            batch_size: 每多少只股票写入一次数据库
        """
        logger.info("=" * 60)
        logger.info(f"步骤2: 拉取历史数据")
        logger.info(f"复权方式: {'前复权' if adjustflag=='2' else '后复权' if adjustflag=='1' else '不复权'}")
        logger.info(f"写入策略: 每 {batch_size} 只股票写入一次数据库")
        logger.info("=" * 60)
        
        # 如果没有指定股票代码，获取全部（股票 + ETF）
        if stock_codes is None:
            all_codes = []
            # 获取股票
            stocks = self.fetcher.get_all_stocks()
            all_codes.extend([s['code'] for s in stocks])
            # 获取ETF
            etfs = self.fetcher.get_etf_list()
            all_codes.extend([e['code'] for e in etfs])
            stock_codes = all_codes
        
        total_stocks = len(stock_codes)
        logger.info(f"共 {total_stocks} 只（股票+ETF）")
        
        # 检查已有数据（断点续传）
        existing_stocks = self._get_fetched_stocks()
        stocks_to_fetch = [c for c in stock_codes if c not in existing_stocks]
        skipped = total_stocks - len(stocks_to_fetch)
        
        if skipped > 0:
            logger.info(f"跳过已有数据: {skipped} 只（断点续传）")
        
        if not stocks_to_fetch:
            logger.info("没有需要拉取的股票，数据已是最新")
            return {
                'total_stocks': total_stocks,
                'skipped': skipped,
                'fetched': 0,
                'failed': 0,
                'total_records': 0
            }
        
        logger.info(f"需要拉取: {len(stocks_to_fetch)} 只")
        logger.info("-" * 60)
        
        # 初始化
        self.progress = ProgressTracker(len(stocks_to_fetch))
        self.cached_data = []
        self.failed_stocks = []
        total_records_written = 0
        
        # 批量拉取
        for i, code in enumerate(stocks_to_fetch):
            try:
                _, data_list = self.fetcher.get_history_k_data(
                    code, start_date, end_date, adjustflag
                )
                
                if data_list:
                    self.cached_data.extend(data_list)
                    logger.debug(f"{code}: {len(data_list)} 条数据")
                
                # 更新进度
                self._on_progress(i + 1, len(stocks_to_fetch), len(self.cached_data))
                
                # 每隔一定数量打印详细进度
                if (i + 1) % PROGRESS_INTERVAL == 0 or (i + 1) == len(stocks_to_fetch):
                    logger.info(f">>> {code} | {self.progress.get_summary()}")
                
            except Exception as e:
                logger.error(f"拉取 {code} 失败: {e}")
                self.failed_stocks.append(code)
                self._on_progress(i + 1, len(stocks_to_fetch), len(self.cached_data))
            
            # Baostock 建议每次查询间隔一小段时间
            time.sleep(0.08)
            
            # 每 batch_size 只股票写入一次数据库
            if (i + 1) % batch_size == 0 and self.cached_data:
                count = self.db.insert_daily_data(self.cached_data)
                total_records_written += count
                logger.info(f"  [批次写入] {count} 条记录，累计: {total_records_written}")
                self.cached_data = []  # 清空缓存，释放内存
        
        # 写入剩余数据
        if self.cached_data:
            count = self.db.insert_daily_data(self.cached_data)
            total_records_written += count
            logger.info(f"  [最后批次] {count} 条记录，总计: {total_records_written}")
            self.cached_data = []
        
        # 最终统计
        logger.info("-" * 60)
        logger.info(f"拉取完成!")
        logger.info(f"  股票数: {len(stocks_to_fetch)}")
        logger.info(f"  失败: {len(self.failed_stocks)} 只")
        logger.info(f"  写入记录: {total_records_written} 条")
        
        if self.failed_stocks:
            logger.warning(f"失败股票: {self.failed_stocks[:20]}...")
        
        return {
            'total_stocks': total_stocks,
            'skipped': skipped,
            'fetched': len(stocks_to_fetch),
            'failed': len(self.failed_stocks),
            'total_records': total_records_written
        }
    
    def _get_fetched_stocks(self) -> set:
        """获取已拉取的股票代码（从 daily_data 表）"""
        ts_codes = self.db.get_fetched_stock_codes()
        # 转换为 baostock 格式
        fetched = set()
        for ts_code in ts_codes:
            # 600000.SH -> sh.600000
            parts = ts_code.split('.')
            if len(parts) == 2:
                code = f"{'sh' if parts[1] == 'SH' else 'sz'}.{parts[0]}"
                fetched.add(code)
        return fetched

    def save_to_database(self, adjustflag: str = "3") -> int:
        """将缓存的数据一次性写入数据库"""
        if not self.cached_data:
            logger.info("没有缓存数据需要写入")
            return 0
        
        logger.info("=" * 60)
        logger.info(f"步骤3: 写入数据库")
        logger.info(f"待写入: {len(self.cached_data)} 条记录")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        try:
            # 批量插入
            count = self.db.insert_daily_data(self.cached_data)
            
            elapsed = time.time() - start_time
            logger.info(f"写入完成! {count} 条记录，耗时 {elapsed:.1f} 秒")
            
            return count
            
        except Exception as e:
            logger.error(f"写入数据库失败: {e}")
            raise
    
    def retry_failed(self) -> int:
        """重试失败的股票"""
        if not self.failed_stocks:
            return 0
        
        logger.info("=" * 60)
        logger.info(f"重试失败的股票: {len(self.failed_stocks)} 只")
        logger.info("=" * 60)
        
        retried_data = []
        still_failed = []
        
        for code in self.failed_stocks:
            try:
                _, data_list = self.fetcher.get_history_k_data(code)
                if data_list:
                    retried_data.extend(data_list)
                    logger.info(f"重试成功: {code} ({len(data_list)} 条)")
            except Exception as e:
                logger.error(f"重试失败: {code} - {e}")
                still_failed.append(code)
        
        # 合并重试成功的数据
        self.cached_data.extend(retried_data)
        self.failed_stocks = still_failed
        
        if still_failed:
            logger.warning(f"仍有 {len(still_failed)} 只股票重试失败")
        
        return len(retried_data)
    
    def run(
        self, 
        stock_codes: List[str] = None,
        start_year: int = None,
        end_year: int = None,
        adjustflag: str = "3",
        retry: bool = True
    ):
        """
        运行完整初始化流程
        
        Args:
            stock_codes: 股票代码列表
            start_year: 开始年份
            end_year: 结束年份
            adjustflag: 复权方式
            retry: 是否重试失败的股票
        """
        start_date = f"{start_year or 2000}-01-01"
        end_date = f"{end_year or datetime.now().year}-12-31" if end_year else None
        
        total_start_time = time.time()
        
        logger.info("=" * 60)
        logger.info("A股日K数据库初始化 (Baostock)")
        logger.info(f"数据范围: {start_date} ~ {end_date or '今天'}")
        logger.info(f"复权方式: {'前复权' if adjustflag=='2' else '后复权' if adjustflag=='1' else '不复权'}")
        logger.info("=" * 60)
        
        try:
            # 步骤1: 更新股票列表
            self.update_stock_list()
            
            # 步骤2: 拉取数据到内存
            fetch_stats = self.fetch_and_cache(
                stock_codes=stock_codes,
                start_date=start_date,
                end_date=end_date,
                adjustflag=adjustflag
            )
            
            # 步骤3: 重试失败的股票
            if retry and self.failed_stocks:
                logger.info("-" * 60)
                self.retry_failed()
            
            # 步骤4: 一次性写入数据库
            if self.cached_data:
                write_count = self.save_to_database(adjustflag)
            else:
                write_count = 0
            
            # 总耗时
            total_elapsed = time.time() - total_start_time
            
            # 输出最终统计
            logger.info("=" * 60)
            logger.info("初始化完成!")
            logger.info(f"  股票总数: {fetch_stats['total_stocks']}")
            logger.info(f"  跳过已有: {fetch_stats['skipped']}")
            logger.info(f"  本次拉取: {fetch_stats['fetched']} 只")
            logger.info(f"  失败: {fetch_stats['failed']} 只")
            logger.info(f"  写入记录: {write_count} 条")
            logger.info(f"  总耗时: {self.progress.format_time(total_elapsed) if self.progress else 'N/A'}")
            logger.info("=" * 60)
            
            # 显示数据库统计
            db_stats = self.db.get_stats()
            logger.info(f"数据库统计:")
            logger.info(f"  股票数量: {db_stats['stock_count']}")
            logger.info(f"  ETF数量: {db_stats['etf_count']}")
            logger.info(f"  日K数据: {db_stats['daily_data_count']}")
            logger.info(f"  日期范围: {db_stats['date_range']}")
            logger.info(f"  数据库大小: {db_stats['db_size']}")
            
        except KeyboardInterrupt:
            logger.warning("\n用户中断!")
            if self.cached_data:
                logger.warning(f"已缓存 {len(self.cached_data)} 条数据")
                logger.info("将保存已拉取的数据...")
                try:
                    self.save_to_database()
                    logger.info("数据已保存")
                except:
                    logger.error("保存失败")
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            raise
        finally:
            self.fetcher.logout()
            self.db.close()


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description='初始化A股日K数据库 (Baostock)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 拉取全部历史数据（2000年至今）
  python init_data.py
  
  # 只拉取特定年份
  python init_data.py --start 2020 --end 2024
  
  # 只拉取2020年至今
  python init_data.py --start 2020
  
  # 选择复权方式
  python init_data.py --qfq        # 前复权（默认）
  python init_data.py --hfq        # 后复权
  python init_data.py --normal     # 不复权

Baostock 说明:
  - 完全免费，无需注册
  - 无频率限制
  - 复权方式: 1=后复权, 2=前复权, 3=不复权
        """
    )
    
    parser.add_argument('--start', '-s', type=int, default=None,
                        help='开始年份，如 2000')
    parser.add_argument('--end', '-e', type=int, default=None,
                        help='结束年份，如 2024')
    parser.add_argument('--qfq', action='store_true', default=True,
                        help='前复权（默认）')
    parser.add_argument('--hfq', action='store_true',
                        help='后复权')
    parser.add_argument('--normal', action='store_true',
                        help='不复权')
    parser.add_argument('--no-retry', action='store_true',
                        help='不重试失败的股票')
    
    args = parser.parse_args()
    
    # 确定复权方式
    if args.normal:
        adjustflag = "3"
    elif args.hfq:
        adjustflag = "1"
    else:
        adjustflag = "2"  # 默认前复权
    
    runner = InitDataRunner()
    runner.run(
        start_year=args.start,
        end_year=args.end,
        adjustflag=adjustflag,
        retry=not args.no_retry
    )


if __name__ == '__main__':
    main()
