# -*- coding: utf-8 -*-
"""
数据拉取模块 - A股日K数据库
使用 Baostock 数据源，按股票代码拉取
"""

import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from config import START_DATE

# 配置日志
logger = logging.getLogger(__name__)


class DataFetcher:
    """数据拉取器 - 基于 Baostock"""
    
    def __init__(self):
        self.bs = None
        self._login()
    
    def _login(self):
        """登录 Baostock"""
        try:
            import baostock as bs
            self.bs = bs
            rs = bs.login()
            if rs.error_code == '0':
                logger.info("Baostock 登录成功")
            else:
                logger.error(f"Baostock 登录失败: {rs.error_msg}")
                self.bs = None
        except ImportError:
            logger.error("未安装 baostock，请运行: pip install baostock")
            self.bs = None
        except Exception as e:
            logger.error(f"Baostock 初始化失败: {e}")
            self.bs = None
    
    def logout(self):
        """登出 Baostock"""
        if self.bs:
            self.bs.logout()
            logger.info("Baostock 已登出")
    
    # ==================== 股票列表 ====================
    
    def get_all_stocks(self, date: str = None) -> List[Dict[str, Any]]:
        """
        获取所有股票列表
        
        Args:
            date: 日期，格式 YYYY-MM-DD，用于获取某日上市的所有股票
            
        Returns:
            股票列表 [{code, code_name, type}, ...]
        """
        if not self.bs:
            logger.error("Baostock未初始化")
            return []
        
        if date is None:
            # 使用一个确定有数据的交易日（ETF数据从2026-01-05开始提供）
            date = "2026-04-30"
        
        all_stocks = []
        
        try:
            logger.info(f"正在获取股票列表 (日期: {date})...")
            
            rs = self.bs.query_all_stock(day=date)
            
            if rs.error_code != '0':
                logger.error(f"获取股票列表失败: {rs.error_msg}")
                return []
            
            stocks = []
            while rs.next():
                stocks.append(rs.get_row_data())
            
            logger.info(f"Baostock返回 {len(stocks)} 条数据")
            
            # 处理数据
            # Baostock返回字段: [code, tradeStatus, code_name]
            for row in stocks:
                code = row[0]  # 如 sh.600000, sz.000001
                trade_status = row[1]  # 交易状态
                name = row[2] if len(row) > 2 else ''  # 名称
                
                # 通过代码前缀判断类型
                # 上交所股票: sh.60开头
                # 深交所股票: sz.00或sz.30开头
                # 上交所ETF: sh.51开头
                # 深交所ETF: sz.15开头
                is_stock = code.startswith('sh.60') or code.startswith('sz.00') or code.startswith('sz.30')
                is_etf = code.startswith('sh.51') or code.startswith('sh.56') or code.startswith('sh.58') or code.startswith('sz.15') or code.startswith('sz.16')
                
                # 只保留股票和ETF
                if not (is_stock or is_etf):
                    continue
                
                stock = {
                    'code': code,
                    'name': name,
                    'type': '1',  # 股票
                    'is_etf': 1 if is_etf else 0,
                    'market': 'SH' if code.startswith('sh.') else 'SZ',
                    'symbol': code.split('.')[1]  # 如 600000
                }
                all_stocks.append(stock)
            
            logger.info(f"获取到 {len(all_stocks)} 只股票/ETF")
            
            return all_stocks
            
        except Exception as e:
            logger.error(f"获取股票列表异常: {e}")
            return []
    
    def get_etf_list(self) -> List[Dict[str, Any]]:
        """
        获取ETF列表（优先从akshare，失败则从本地文件）
        ETF的K线数据仍从Baostock获取（支持复权）
        
        Returns:
            ETF列表 [{code, name, type, is_etf, market, symbol}, ...]
        """
        # 方案1: 尝试从 akshare 获取
        try:
            import akshare as ak
            
            logger.info("正在获取ETF列表 (akshare)...")
            
            etf_list = []
            
            # 获取场内基金列表
            df = ak.fund_etf_spot_em()
            
            for _, row in df.iterrows():
                code = str(row['代码'])
                name = str(row['名称'])
                
                # 判断市场（扩展支持更多ETF代码）
                # 上交所: 51开头(主板ETF)、56开头(科创ETF)、58开头(科创板ETF)
                # 深交所: 15开头、16开头
                if code.startswith('51') or code.startswith('56') or code.startswith('58'):
                    market = 'SH'
                    bs_code = f'sh.{code}'
                elif code.startswith('15') or code.startswith('16'):
                    market = 'SZ'
                    bs_code = f'sz.{code}'
                else:
                    continue
                
                etf_list.append({
                    'code': bs_code,
                    'name': name,
                    'type': 'ETF',
                    'is_etf': 1,
                    'market': market,
                    'symbol': code
                })
            
            logger.info(f"从akshare获取到 {len(etf_list)} 只ETF")
            return etf_list
            
        except Exception as e:
            logger.warning(f"从akshare获取ETF列表失败: {e}，尝试从本地文件获取...")
        
        # 方案2: 从本地文件获取
        try:
            import csv
            # from pathlib import Path
            from config import ETF_LIST_PATH  # 从config导入
            etf_file = ETF_LIST_PATH  # 使用配置的路径
            # etf_file = Path(__file__).parent / 'etf_list.csv'
            
            if not etf_file.exists():
                logger.warning(f"ETF列表文件不存在: {etf_file}")
                logger.warning("请创建 etf_list.csv 文件，格式: 代码,名称")
                return []
            
            logger.info(f"正在读取ETF列表: {etf_file}")
            
            etf_list = []
            
            with open(etf_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get('代码', '').strip()
                    name = row.get('名称', '').strip()
                    
                    if not code:
                        continue
                    
                    # 判断市场（扩展支持更多ETF代码）
                    if code.startswith('51') or code.startswith('56') or code.startswith('58'):
                        market = 'SH'
                        bs_code = f'sh.{code}'
                    elif code.startswith('15') or code.startswith('16'):
                        market = 'SZ'
                        bs_code = f'sz.{code}'
                    else:
                        continue
                    
                    etf_list.append({
                        'code': bs_code,
                        'name': name,
                        'type': 'ETF',
                        'is_etf': 1,
                        'market': market,
                        'symbol': code
                    })
            
            logger.info(f"从本地文件获取到 {len(etf_list)} 只ETF")
            return etf_list
            
        except Exception as e:
            logger.error(f"读取ETF列表失败: {e}")
            return []
    
    def get_history_k_data(
        self, 
        code: str, 
        start_date: str = None, 
        end_date: str = None,
        adjustflag: str = "3"  # 1=后复权, 2=前复权, 3=不复权
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        获取单个股票的历史K线数据
        
        Args:
            code: 股票代码，如 sh.600000
            start_date: 开始日期，格式 YYYY-MM-DD
            end_date: 结束日期，格式 YYYY-MM-DD
            adjustflag: 复权方式 1=后复权, 2=前复权, 3=不复权
            
        Returns:
            Tuple[str, List[Dict]]: (股票代码, 数据列表)
        """
        if not self.bs:
            return code, []
        
        start_date = start_date or START_DATE
        end_date = end_date or datetime.now().strftime('%Y-%m-%d')
        
        # 字段说明
        fields = (
            "date,code,open,high,low,close,volume,amount,"
            "turn,pctChg,isST"
        )
        
        try:
            rs = self.bs.query_history_k_data_plus(
                code,
                fields,
                start_date=start_date,
                end_date=end_date,
                frequency="d",  # 日线
                adjustflag=adjustflag
            )
            
            if rs.error_code != '0':
                logger.warning(f"获取 {code} 数据失败: {rs.error_msg}")
                return code, []
            
            data_list = []
            while rs.next():
                row = rs.get_row_data()
                # 过滤空数据
                if row and row[0]:
                    data = {
                        'trade_date': row[0].replace('-', ''),  # 转为 YYYYMMDD
                        'ts_code': self._convert_code(row[1]),  # 转为 600000.SH 格式
                        'open': float(row[2]) if row[2] else 0,
                        'high': float(row[3]) if row[3] else 0,
                        'low': float(row[4]) if row[4] else 0,
                        'close': float(row[5]) if row[5] else 0,
                        'volume': float(row[6]) if row[6] else 0,
                        'amount': float(row[7]) if row[7] else 0,
                        'turnover': float(row[8]) if row[8] else 0,
                        'pct_chg': float(row[9]) if row[9] else 0,
                        'is_st': 1 if row[10] == '1' else 0
                    }
                    data_list.append(data)
            
            return code, data_list
            
        except Exception as e:
            logger.warning(f"获取 {code} 数据异常: {e}")
            return code, []
    
    def get_history_with_all_adjust(
        self,
        code: str,
        start_date: str = None,
        end_date: str = None
    ) -> Tuple[str, Dict[str, List[Dict[str, Any]]]]:
        """
        获取单个股票的历史数据（包含三种复权）
        
        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Tuple[str, Dict]: (股票代码, {normal: [], qfq: [], hfq: []})
        """
        # 不复权
        _, normal_data = self.get_history_k_data(code, start_date, end_date, adjustflag="3")
        
        # 前复权
        _, qfq_data = self.get_history_k_data(code, start_date, end_date, adjustflag="2")
        
        # 后复权
        _, hfq_data = self.get_history_k_data(code, start_date, end_date, adjustflag="1")
        
        return code, {
            'normal': normal_data,
            'qfq': qfq_data,
            'hfq': hfq_data
        }
    
    def _convert_code(self, bs_code: str) -> str:
        """
        将 Baostock 代码格式转换为 tushare 格式
        
        sh.600000 -> 600000.SH
        sz.000001 -> 000001.SZ
        """
        if not bs_code:
            return ""
        
        parts = bs_code.split('.')
        if len(parts) != 2:
            return bs_code
        
        market, symbol = parts
        market_suffix = 'SH' if market == 'sh' else 'SZ'
        
        return f"{symbol}.{market_suffix}"
    
    # ==================== 批量拉取 ====================
    
    def fetch_stocks_data(
        self,
        stocks: List[Dict[str, Any]],
        start_date: str = None,
        end_date: str = None,
        adjustflag: str = "3",
        progress_callback: callable = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        批量拉取多只股票的历史数据
        
        Args:
            stocks: 股票列表
            start_date: 开始日期
            end_date: 结束日期
            adjustflag: 复权方式
            progress_callback: 进度回调 (已完成数, 总数)
            
        Returns:
            Tuple[List[Dict], List[str]]: (所有数据, 失败的股票代码)
        """
        total = len(stocks)
        all_data = []
        failed_codes = []
        
        logger.info(f"开始拉取 {total} 只股票的数据...")
        
        for i, stock in enumerate(stocks):
            code = stock.get('code', '')
            
            try:
                _, data_list = self.get_history_k_data(
                    code, start_date, end_date, adjustflag
                )
                
                if data_list:
                    all_data.extend(data_list)
                    logger.debug(f"{code}: {len(data_list)} 条数据")
                else:
                    logger.debug(f"{code}: 无数据")
                
            except Exception as e:
                logger.warning(f"拉取 {code} 失败: {e}")
                failed_codes.append(code)
            
            # 进度回调
            if progress_callback:
                progress_callback(i + 1, total, len(all_data))
            
            # 每处理一批打印一次进度
            if (i + 1) % 50 == 0:
                logger.info(f"进度: {i+1}/{total} ({len(all_data)} 条数据)")
            
            # Baostock 建议每次查询间隔一小段时间，避免过于频繁
            time.sleep(0.08)
        
        return all_data, failed_codes


def fetch_all_stocks(date: str = None) -> List[Dict[str, Any]]:
    """获取所有股票列表的便捷函数"""
    fetcher = DataFetcher()
    stocks = fetcher.get_all_stocks(date)
    fetcher.logout()
    return stocks
