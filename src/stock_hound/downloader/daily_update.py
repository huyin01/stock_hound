# -*- coding: utf-8 -*-
"""
每日更新脚本 - A股日K数据库
增量更新：检查每只股票最新日期，只拉取缺失的数据
"""

import sys
import logging
import logging.handlers
from datetime import datetime, timedelta
from pathlib import Path
import time
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent))

from config import LOG_FILE, LOG_DIR, LOG_LEVEL, LOG_FORMAT, START_DATE
from database import StockDatabase, init_database
from fetcher import DataFetcher


def setup_logging():
    """配置日志"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, LOG_LEVEL))
    logger.handlers.clear()
    
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


logger = setup_logging()


class DailyUpdater:
    """每日数据更新器 - 增量更新模式"""
    
    def __init__(self):
        self.fetcher = DataFetcher()
        self.db = init_database()
        self.today = datetime.now().strftime('%Y-%m-%d')
    
    def get_all_codes(self) -> List[str]:
        """获取所有股票和ETF代码"""
        all_codes = []
        
        # # 获取股票
        # stocks = self.fetcher.get_all_stocks()
        # all_codes.extend([s['code'] for s in stocks])
        
        # # 获取ETF
        # etfs = self.fetcher.get_etf_list()
        # all_codes.extend([e['code'] for e in etfs])
        
        # return all_codes

        stocks = self.fetcher.get_all_stocks()
        return [s['code'] for s in stocks]
    
    def update_incremental(
        self, 
        adjustflag: str = "2",
        days_limit: int = 365
    ) -> dict:
        """
        增量更新：检查每只股票最新日期，只拉取缺失的数据
        
        Args:
            adjustflag: 复权方式
            days_limit: 最多回溯天数（默认365天，支持补更长时间段的数据）
        """
        result = {
            'success': False,
            'total_stocks': 0,
            'updated_stocks': 0,
            'total_records': 0,
            'failed_stocks': 0,
            'error': None
        }
        
        logger.info("=" * 60)
        logger.info("增量更新模式")
        logger.info("=" * 60)
        
        # 获取所有代码
        all_codes = self.get_all_codes()
        result['total_stocks'] = len(all_codes)
        logger.info(f"共 {len(all_codes)} 只股票/ETF")
        
        # 获取数据库中每只股票的最新日期
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT ts_code, MAX(trade_date) FROM daily_data GROUP BY ts_code")
        latest_dates = {row[0]: row[1] for row in cursor.fetchall()}
        
        # 计算起始日期（不超过days_limit天前）
        start_limit = (datetime.now() - timedelta(days=days_limit)).strftime('%Y%m%d')
        
        # 统计
        updated_count = 0
        failed_count = 0
        total_records = 0
        all_data = []
        
        for i, bs_code in enumerate(all_codes):
            try:
                # 转换代码格式：sh.600000 -> 600000.SH
                parts = bs_code.split('.')
                if len(parts) != 2:
                    continue
                market, symbol = parts
                ts_code = f"{symbol}.{'SH' if market == 'sh' else 'SZ'}"
                
                # 确定起始日期
                if ts_code in latest_dates:
                    # 从最新日期的下一天开始
                    latest = latest_dates[ts_code]
                    start_date_dt = datetime.strptime(latest, '%Y%m%d') + timedelta(days=1)
                    start_date = start_date_dt.strftime('%Y-%m-%d')
                else:
                    # 新股票，从限制的起始日期开始
                    start_date = start_limit[:4] + '-' + start_limit[4:6] + '-' + start_limit[6:8]
                
                # 如果起始日期超过今天，跳过
                if start_date > self.today:
                    continue
                
                # 拉取数据
                _, data_list = self.fetcher.get_history_k_data(
                    bs_code, start_date, self.today, adjustflag
                )
                
                if data_list:
                    all_data.extend(data_list)
                    updated_count += 1
                    
                    # 每100只股票写入一次
                    if len(all_data) >= 10000:
                        count = self.db.insert_daily_data(all_data)
                        total_records += count
                        logger.info(f"  [批次写入] {count} 条，累计: {total_records}")
                        all_data = []
                
            except Exception as e:
                logger.warning(f"更新 {bs_code} 失败: {e}")
                failed_count += 1
            
            # 进度显示
            if (i + 1) % 100 == 0:
                logger.info(f"进度: {i+1}/{len(all_codes)} | 已更新: {updated_count} | 失败: {failed_count}")
            
            # 间隔
            time.sleep(0.08)
        
        # 写入剩余数据
        if all_data:
            count = self.db.insert_daily_data(all_data)
            total_records += count
            logger.info(f"  [最后批次] {count} 条，总计: {total_records}")
        
        result['success'] = True
        result['updated_stocks'] = updated_count
        result['total_records'] = total_records
        result['failed_stocks'] = failed_count
        
        return result
    
    def update_full_day(self, trade_date: str, adjustflag: str = "2") -> dict:
        """
        更新指定日期的所有数据（用于补数据）
        
        Args:
            trade_date: 交易日期 YYYY-MM-DD
            adjustflag: 复权方式
        """
        result = {
            'date': trade_date,
            'success': False,
            'record_count': 0,
            'error': None
        }
        
        logger.info("=" * 60)
        logger.info(f"全量更新: {trade_date}")
        logger.info("=" * 60)
        
        # 获取所有代码
        all_codes = self.get_all_codes()
        logger.info(f"共 {len(all_codes)} 只股票/ETF")
        
        date_str = trade_date.replace('-', '')
        all_data = []
        failed = 0
        
        for i, code in enumerate(all_codes):
            try:
                _, data_list = self.fetcher.get_history_k_data(
                    code, trade_date, trade_date, adjustflag
                )
                
                if data_list:
                    # 只保留当天数据
                    day_data = [d for d in data_list if d.get('trade_date') == date_str]
                    all_data.extend(day_data)
                
            except Exception as e:
                failed += 1
            
            if (i + 1) % 100 == 0:
                logger.info(f"进度: {i+1}/{len(all_codes)} ({len(all_data)} 条)")
            
            time.sleep(0.08)
        
        # 写入数据库
        if all_data:
            count = self.db.insert_daily_data(all_data)
            result['success'] = True
            result['record_count'] = count
            logger.info(f"更新成功! {count} 条数据")
        else:
            result['success'] = True
            logger.info("当天无数据（可能是非交易日）")
        
        if failed > 0:
            logger.warning(f"失败数: {failed}")
        
        return result
    
    def run(self, mode: str = "incremental", date: str = None, adjustflag: str = "2"):
        """
        运行更新
        
        Args:
            mode: 更新模式 incremental=增量, full=全量
            date: 指定日期（仅full模式）
            adjustflag: 复权方式
        """
        logger.info("=" * 60)
        logger.info("A股日K每日更新 (Baostock)")
        logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"更新模式: {'增量更新' if mode == 'incremental' else '全量更新'}")
        logger.info("=" * 60)
        
        try:
            # 显示当前状态
            db_stats = self.db.get_stats()
            logger.info(f"数据库状态:")
            logger.info(f"  股票数: {db_stats['stock_count']}")
            logger.info(f"  ETF数: {db_stats['etf_count']}")
            logger.info(f"  日K数据: {db_stats['daily_data_count']} 条")
            logger.info(f"  日期范围: {db_stats['date_range']}")
            logger.info("-" * 60)
            
            # 执行更新
            if mode == "incremental":
                result = self.update_incremental(adjustflag)
                
                logger.info("=" * 60)
                logger.info("更新完成!")
                logger.info(f"  更新股票数: {result['updated_stocks']}")
                logger.info(f"  新增记录: {result['total_records']}")
                logger.info(f"  失败数: {result['failed_stocks']}")
                
            else:  # full mode
                if not date:
                    date = self.today
                result = self.update_full_day(date, adjustflag)
                
                logger.info("=" * 60)
                logger.info("更新完成!")
                logger.info(f"  更新日期: {result['date']}")
                logger.info(f"  记录数: {result['record_count']}")
            
            # 最终状态
            logger.info(f"  数据库大小: {self.db.get_db_size()}")
            logger.info("=" * 60)
            
        except KeyboardInterrupt:
            logger.warning("\n用户中断")
        except Exception as e:
            logger.error(f"更新失败: {e}")
            raise
        finally:
            self.fetcher.logout()
            self.db.close()


def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='每日更新A股日K数据 (Baostock)')
    parser.add_argument('--mode', '-m', choices=['incremental', 'full'], default='incremental',
                        help='更新模式: incremental=增量(默认), full=全量')
    parser.add_argument('--date', '-d', default=None, help='指定日期 YYYY-MM-DD（仅full模式）')
    parser.add_argument('--qfq', action='store_true', default=True, help='前复权（默认）')
    parser.add_argument('--hfq', action='store_true', help='后复权')
    parser.add_argument('--normal', action='store_true', help='不复权')
    
    args = parser.parse_args()
    
    # 确定复权方式
    if args.normal:
        adjustflag = "3"
    elif args.hfq:
        adjustflag = "1"
    else:
        adjustflag = "2"  # 默认前复权
    
    updater = DailyUpdater()
    updater.run(mode=args.mode, date=args.date, adjustflag=adjustflag)


if __name__ == '__main__':
    main()
