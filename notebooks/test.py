import os
import sys
import pandas
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from utils import get_stock as gs

# 定义待查询股票
stock_id = '300150.SZ'

# 获得300天数据
df = gs.getstock_tushare(stock_id,30)

# # 输出股票数据
# output_path = f'{stock_id}.csv'
# df.to_csv(
#     output_path,
#     index= False,
#     # float_format='%.2f',
#     encoding='utf-8-sig'
# )
#
# print(f"数据已成功保存至：{os.path.abspath(output_path)}")

#————查询某一天是否为5倍放量
# 定义查询日期，转换成日期格式
query_date = '20250715'
query_date_obj =pd.to_datetime(query_date)

# 将df数据的日期由字符串转为date
df['trade_date'] = pd.to_datetime(df['trade_date'])

# 获得目标行的行号
target_index = df[df['trade_date'] == query_date_obj].index[0]

# # 获取目标日期+前10天的索引
prev_11_indices = df.index[df.index >= target_index][0:11]

# 获取这些索引对应的 'trade_date'、'amount' 列的数据
prev_11_data = df.loc[prev_11_indices, ['trade_date','amount']]

# 查询日的成交量
query_amout = prev_11_data.iloc[0,1]
print(f'查询日的成交量是：{query_amout}')

prev_10amout_mean = prev_11_data['amount'].iloc[1:11].mean()
print(f'查询日前10天成交量的均值是：{prev_10amout_mean}')

