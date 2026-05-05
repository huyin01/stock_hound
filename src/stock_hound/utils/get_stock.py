import tushare as ts
import pandas as pd
import os
import sys
import datetime
import time

# 配置Tushare
token = os.getenv('TUSHARE_TOKEN')
ts.set_token(token)  # 替换成你的 Tushare token
pro = ts.pro_api()

# # 配置工作文件夹
# # 获取相关目录
# src_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
# data_dir = os.path.join(src_dir, '..', 'data')
# # 切换工作目录到脚本所在目录
# os.chdir(src_dir)

# 获取股票数据函数：获取某只股票的历史数据（最近40天）
# ——采用tushare数据库——！
def getstock(stock_symbol, days=40):
    end_date = datetime.datetime.today().strftime('%Y%m%d')
    start_date = (datetime.datetime.today() - datetime.timedelta(days=days)).strftime('%Y%m%d')
    # 获取股票数据
    try:
        stock_data = pro.daily(ts_code=stock_symbol, start_date=start_date, end_date=end_date)
        # stock_data = stock_data[['trade_date', 'close']].sort_values(by='trade_date')
        # stock_data['trade_date'] = pd.to_datetime(stock_data['trade_date'], format='%Y%m%d')
    except Exception as e:
        print(f"Error fetching data for {stock_symbol}: {e}")
        return None
    return stock_data

# 待完成函数：获取所有股票代码

# 待完成函数：获取A股交易日列表

# 待完成函数：获取A股所有股票最近N年的数据