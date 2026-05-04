import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from utils import get_stock as gs

# 定义待查询股票
stock_id = '300150.SZ'

# 获得300天数据
data = gs.getstock_tushare(stock_id,300)

print(data.dtypes)