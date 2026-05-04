import os
import sys
import pandas
from datetime import datetime
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from utils import get_stock as gs

# 定义待查询股票
stock_id = '300150.SZ'

# 获得300天数据
df = gs.getstock_tushare(stock_id,300)
print(df.dtypes)

# 定义查询日期
query_date = '20250715'
query_date_obj = datetime.strptime(query_date, '%Y%m%d')
query_date_obj_date = query_date_obj.date()
print(query_date_obj)

x = df.iloc[1,1]
print(type(x))
# 获得查询日期对应的索引号
print( x == query_date_obj_date )
target_index = df[df['trade_date'] == query_date_obj_date].index[0]
print(target_index)
# # 获取目标日期前一天的索引
# prev_10_indices = df.index[df.index > target_index][0:10]
# print(prev_10_indices)



