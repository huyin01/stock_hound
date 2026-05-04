import numpy as np
import sys
import time

import pandas as pd

from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from utils import get_stock as gs


# 定义查询日期，转换成日期格式
query_date = '20250812'
query_date_obj =pd.to_datetime(query_date)

# 定义激活条件
ACTIVATE_Dict = {4:6.5, 3:7.5, 2:8.5, 1:9.5, 0:0.9}

def select_pullback(stock_data,output_list):

    """
    筛选股票的函数
    :param stock_data: DataFrame，包含股票的历史数据，列包括：'Date', 'Close', 'Low', 'High', 'Volume', 'MA20', 'MA30'
    :return: 筛选结果，包括符合条件的股票代码和最大偏离值
    """
    # 获得70天数据
    df = gs.getstock(stock_data, 70)
    if df is None or df.empty:
        print(f"{stock} 没有返回有效数据，跳过")
        return

    # 检查是否有必要字段
    required_columns = {'trade_date', 'amount'}
    if not required_columns.issubset(df.columns):
        print(f"{stock} 数据缺失必要字段（{required_columns}），实际字段：{df.columns}")
        return

    # 将df数据的日期由字符串转为date
    df['trade_date'] = pd.to_datetime(df['trade_date'])


    # 计算30日均线和20日均线
    stock_data['MA30'] = stock_data['Close'].rolling(window=30).mean()
    stock_data['MA20'] = stock_data['Close'].rolling(window=20).mean()
    # ------------------------------------------------
    # 获取今天的数据
    today = stock_data.iloc[-1]
    today_close = today['Close']
    today_low = today['Low']
    ma30_today = today['MA30']

    # 判断今日条件
    if not (abs(today_close - ma30_today) / ma30_today <= 0.04 and today_low < today['MA20']):
        return False, None

    # 检查30日内是否发生过放量激活
    volume_thresholds = [4, 3, 2, 1, 0]
    price_thresholds = [6.5, 7.5, 8.5, 9.5, 9.9]
    recent_30_days = stock_data.iloc[-30:]

    def check_volume_price(row):
        for vol, price in zip(volume_thresholds, price_thresholds):
            if row['Volume'] > vol * row['Volume'].mean() and row['Close'] >= price:
                return True
        return False

    volume_price_activation = recent_30_days.apply(check_volume_price, axis=1)
    if not volume_price_activation.any():
        return False, None

    # 找到放量涨停的第一天
    activation_day = recent_30_days[volume_price_activation].index[0]
    activation_day_data = stock_data.loc[activation_day]

    # 检查从放量涨停开始到今天的收盘价是否在30均线以上超过85%的天数
    days_above_ma30 = stock_data.loc[activation_day:].apply(lambda x: x['Close'] > x['MA30'], axis=1).sum()
    total_days = len(stock_data.loc[activation_day:])
    if days_above_ma30 / total_days < 0.85:
        return False, None

    # 检查30日内每日最大值与30均线偏离值是否超过10%
    max_deviation = recent_30_days.apply(lambda x: abs(x['High'] - x['MA30']) / x['MA30'], axis=1).max()
    if max_deviation <= 0.1:
        return False, None

    return True, max_deviation * 100  # 返回最大偏离值的百分比

# 示例：加载股票数据
# 假设你已经从金融数据源获取了股票数据，这里用一个示例数据
data = {
    'Date': pd.date_range(start='2025-07-01', periods=60, freq='D'),
    'Close': np.random.uniform(90, 110, 60),  # 随机生成收盘价
    'Low': np.random.uniform(85, 105, 60),    # 随机生成最低价
    'High': np.random.uniform(95, 115, 60),   # 随机生成最高价
    'Volume': np.random.uniform(100000, 500000, 60)  # 随机生成成交量
}
stock_data = pd.DataFrame(data)

# 调用筛选函数
result, max_deviation = screen_stocks(stock_data)
print(f"筛选结果: {result}, 最大偏离值: {max_deviation:.2f}%")