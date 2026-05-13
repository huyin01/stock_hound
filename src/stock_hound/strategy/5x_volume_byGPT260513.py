import time
from pathlib import Path

import pandas as pd

from database.stock_repository import StockRepository


# =========================
# 参数设置
# =========================
QUERY_DATE = '20250827'

AMPLY_VALUE = 6
CHANGE_VALUE = 6


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
    stock: str,
    output_list: list,
):

    try:

        # 获取最近50天数据
        df = repo.get_recent_daily_data(
            symbol=stock,
            limit=50,
        )

    except Exception as e:

        print(f"{stock} 读取失败: {e}")

        return

    # =========================
    # 数据为空
    # =========================
    if df.empty:

        print(f"{stock} 数据为空")

        return

    # =========================
    # 检查必要字段
    # =========================
    required_columns = {
        'trade_date',
        'volume',
        'pct_chg',
    }

    if not required_columns.issubset(df.columns):

        print(
            f"{stock} 缺少必要字段: "
            f"{required_columns}"
        )

        return

    # =========================
    # 查找目标日期
    # =========================
    target_df = df[
        df['trade_date'] == pd.to_datetime(QUERY_DATE)
    ]

    if target_df.empty:

        print(f"{stock} 在 {QUERY_DATE} 无数据")

        return

    # 当前目标日索引
    target_index = target_df.index[0]

    # =========================
    # 涨幅过滤
    # =========================
    pct_chg = df.loc[target_index, 'pct_chg']

    if pct_chg < CHANGE_VALUE:

        return

    # =========================
    # 获取目标日 + 前10日
    # 数据已经按日期倒序排列
    # =========================
    sub_df = df.iloc[
        target_index: target_index + 11
    ]

    # 数据不足
    if len(sub_df) < 11:

        print(f"{stock} 历史数据不足")

        return

    # =========================
    # 当前成交量
    # =========================
    query_volume = sub_df.iloc[0]['volume']

    # =========================
    # 前10日平均成交量
    # =========================
    prev_10_mean = (
        sub_df.iloc[1:11]['volume']
        .mean()
    )

    # =========================
    # N倍放量判断
    # =========================
    if query_volume >= prev_10_mean * AMPLY_VALUE:

        print(
            f"{stock} 在 {QUERY_DATE} "
            f"满足成交量 "
            f"{AMPLY_VALUE} 倍放大"
        )

        output_list.append(stock)


# =========================
# 主程序
# =========================
def main():

    print("5x_volume：程序开始运行...")

    result_list = []

    # =========================
    # 读取股票列表
    # =========================
    df_stock = pd.read_csv(STOCK_LIST_PATH)

    # =========================
    # 遍历股票
    # =========================
    for stock_id in df_stock['ts_code']:

        amount_Ntimes(
            stock=stock_id,
            output_list=result_list,
        )

        # 本地数据库读取
        # 不需要太长sleep
        time.sleep(0.02)

    # =========================
    # 输出结果
    # =========================
    print()
    print("最终结果：")
    print(result_list)


# =========================
# 程序入口
# =========================
if __name__ == "__main__":

    main()