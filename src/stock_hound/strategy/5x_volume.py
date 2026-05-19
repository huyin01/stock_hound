import time

import pandas as pd

from pathlib import Path

from database.stock_repository import StockRepository

# =========================
# 参数设置
# =========================

#————查询某一天是否为N倍放量
# 定义查询日期，转换成日期格式
query_date = '20250827' #！！！！！查询时手工调整，后期可以设置为当天日期！！！！！！！
query_date_obj =pd.to_datetime(query_date)
AMPLY_VALUE = 6   # 只选取放量value倍以上的，前次用值2.5
CHANGE_VALUE = 6    # 只选取上涨幅度为value%以上的,前次用值4

# =========================
# 路径
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent.parent

DB_PATH = BASE_DIR / 'stock_data.db'

STOCK_LIST_PATH = (
    BASE_DIR / 'data' / 'ASharesCodes.csv'
)

# =========================
# 初始化 Repository
# =========================
repo = StockRepository(DB_PATH)


# =========================
# 判断是否为N倍放量
# =========================
def amount_Ntimes(
    stock:str,
    output_list:list
    ):
    try:
        # 获得50天数据
        df = repo.get_recent_daily_data(
            symbol=stock,
            limit=50,
        )
    except Exception as e:
        print(f"{stock}读取失败：{e}")
        return None
    #==========
    #数据为空
    #==========
    if df is None or df.empty:
        print(f"{stock} 数据为空")
        return None
    #=================
    # 检查是否有必要字段
    #=================
    required_columns = {
        'trade_date',
        'volume',
        'pct_chg',
        }
    if not required_columns.issubset(df.columns):
        print(
            f"{stock} 缺少必要字段"
            f"{required_columns}"
            )
        return None
    #=================
    # 查找目标日期
    #=================
    # 将df数据的日期由字符串转为date
    df['trade_date'] = pd.to_datetime(df['trade_date'])

    # 获得目标日期所在的行号
    try:
        target_index = df[df['trade_date'] == query_date_obj].index[0]
    except IndexError:
        print(f"{stock} 在 {query_date} 没有数据")
        return None
    #=========================
    # 涨幅过滤
    #=========================
    if df.loc[target_index, "pct_chg"] < CHANGE_VALUE:
        # print(f"{stock} 在 {query_date} 上涨幅度不足{CHANGE_VALUE}%")
        return None
    #===========================
    # 获取目标日+前10日
    # 数据已经按日期倒序排列
    #===========================
    if len(df.index[df.index >= target_index]) < 11:
        print(f"{stock} 数据不足，跳过")
        return None
    prev_11_indices = df.index[df.index >= target_index][0:11]

    # 获取这些索引对应的 'trade_date'、'amount' 列的数据
    prev_11_data = df.loc[prev_11_indices, ['trade_date','volume']]

    # 查询日的成交量
    query_volume = prev_11_data.iloc[0,1]
    # print(f'查询日的成交量是：{query_amount}')

    prev_10volume_mean = (
        prev_11_data['volume'].iloc[1:11]
        .mean()
    )
    # print(f'查询日前10天成交量的均值是：{prev_10amount_mean}')

    # =========================
    # N倍放量判断
    # =========================
    if query_volume >= prev_10volume_mean*AMPLY_VALUE:
        print(
            f"{stock}在{query_date}"
            f"满足成交量"
            f"{AMPLY_VALUE}倍放大"
            )
        return {
            "code": stock,
            "trade_date": query_date,
            "pct_chg": df.loc[target_index, "pct_chg"],
            "volume_ratio": query_volume / prev_10volume_mean
        }
    return None

#=========
#主程序
#=========
def main():
    print("5x_volume：程序开始运行...")
    # 准备结果列表
    results = []

    # 读取待循环股票列表
    # file_path = (Path(__file__).parent.parent.parent / 'data' / 'ASharesCodes.csv').resolve()
    df_stock = pd.read_csv(STOCK_LIST_PATH)

    # 对df_stock中的stock_id循环，完成操作
    for stock_id in df_stock['ts_code']:
        res = amount_Ntimes(stock_id)
        if res is not None:
            results.append(res)
            print(f"发现目标: {stock_id}") 
        # time.sleep(0.12*10)   #在线数据库限制频率时使用
    df_result = pd.DataFrame(results)
    print("\n最终筛选结果：")
    print(df_result)
    return df_result

if __name__ == "__main__":
    main()




