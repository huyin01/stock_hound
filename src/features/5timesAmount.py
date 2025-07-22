import os
import sys
import time

from datetime import datetime
import pandas as pd

from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from utils import get_stock as gs


#————查询某一天是否为5倍放量
# 定义查询日期，转换成日期格式
query_date = '20250718'
query_date_obj =pd.to_datetime(query_date)


# 定义5倍放量判断函数
def amount_5times(stock,output_list):
    # 获得300天数据
    df = gs.getstock(stock,50)
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

    # 获得目标日期所在的行号
    try:
        target_index = df[df['trade_date'] == query_date_obj].index[0]
    except IndexError:
        print(f"{stock} 在 {query_date} 没有数据")
        return
    # 获取目标日期以及前10天的索引
    if len(df.index[df.index >= target_index]) < 11:
        print(f"{stock} 数据不足，跳过")
        return
    prev_11_indices = df.index[df.index >= target_index][0:11]

    # 获取这些索引对应的 'trade_date'、'amount' 列的数据
    prev_11_data = df.loc[prev_11_indices, ['trade_date','amount']]

    # 查询日的成交量
    query_amount = prev_11_data.iloc[0,1]
    # print(f'查询日的成交量是：{query_amount}')

    prev_10amount_mean = prev_11_data['amount'].iloc[1:11].mean()
    # print(f'查询日前10天成交量的均值是：{prev_10amount_mean}')

    if query_amount >= prev_10amount_mean*5:
        # print(f'{stock}在{query_date}满足成交量5倍放大')
        output_list.append(stock)


def main():
    # 准备结果列表
    result_list = []

    # 读取待循环股票dataframe
    file_path = (Path(__file__).parent.parent.parent / 'data' / 'ASharesCodes.csv').resolve()
    df_stock = pd.read_csv(file_path)

    # 对df_stock中的stock_id循环，完成操作
    for stock_id in df_stock['ts_code']:
        amount_5times(stock_id,result_list)
        time.sleep(0.12)
    print(result_list)

if __name__ == "__main__":
    main()




