import os
import sys
import pandas
from datetime import datetime
import pandas as pd

from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from utils import get_stock as gs



#————查询某一天是否为5倍放量
# 定义查询日期，转换成日期格式
query_date = '20250715'
query_date_obj =pd.to_datetime(query_date)

# 准备结果列表
result_stock_list = []

# 读取带循环股票dataframe
file_path = (Path(__file__).parent.parent.parent / 'data' / 'ASharesCodes.csv').resolve()
print(file_path)