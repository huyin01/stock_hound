import os
from utils import get_stock as gs

stock_id = '300150.SZ'
data = gs.gsfrtushare(stock_id,100)

output_path = f'{stock_id}.csv'
data.to_csv(
    output_path,
    index= False,
    # float_format= '{:.2f}',
    encoding='utf-8-sig'
)
print(f"数据已成功保存至：{os.path.abspath(output_path)}")