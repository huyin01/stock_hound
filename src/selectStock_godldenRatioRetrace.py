import tushare as ts
import pandas as pd
import datetime
import os
import sys
import time

# 配置：容差
limit_up_tolerance = 0.095  # 涨停容差 9.5%
retracement_lower_bound = 0.60  # 回调下限 60%
retracement_upper_bound = 0.65  # 回调上限 65%
max_non_limit_up_days = 3  # 最多允许非涨停天数

# 配置Tushare
token = os.getenv('TUSHARE_TOKEN')
ts.set_token(token)  # 替换成你的 Tushare token
pro = ts.pro_api()

# 配置工作文件夹
# 获取相关目录
src_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
data_dir = os.path.join(src_dir, '..', 'data')
# 切换工作目录到脚本所在目录
os.chdir(src_dir)

# 获取股票数据函数：获取某只股票的历史数据（最近40天）
def get_stock_data(stock_symbol, days=40):
    end_date = datetime.datetime.today().strftime('%Y%m%d')
    start_date = (datetime.datetime.today() - datetime.timedelta(days=days)).strftime('%Y%m%d')
    time.sleep(0.12)  # 数据库每分钟只能调用500次，为了防止被限制
    # 获取股票数据
    try:
        stock_data = pro.daily(ts_code=stock_symbol, start_date=start_date, end_date=end_date)
        stock_data = stock_data[['trade_date', 'close']].sort_values(by='trade_date')
        stock_data['trade_date'] = pd.to_datetime(stock_data['trade_date'], format='%Y%m%d')
    except Exception as e:
        print(f"Error fetching data for {stock_symbol}: {e}")
        return None
    return stock_data


# 检查是否涨停日
def is_limit_up(current_close, last_close):
    return (current_close - last_close) / last_close >= limit_up_tolerance


# 判断是否符合回调条件
def is_in_fibonacci_retracement(low, high, price):
    return low <= price and price <= high


# 找到连续涨停序列
def find_continuous_limit_up(stock_data):
    limit_up_days = 0
    non_limit_up_days = 0
    limit_up_sequence = []
    highest_price = None
    starting_price = None
    max_increase = None

    for i in range(1, len(stock_data)):
        current_close = stock_data['close'].iloc[i]
        last_close = stock_data['close'].iloc[i - 1]

        if is_limit_up(current_close, last_close):
            # 是涨停日
            if non_limit_up_days > max_non_limit_up_days or non_limit_up_days > limit_up_days * 0.33:
                break  # 超过最大非涨停天数，结束判断
            if starting_price is None:
                starting_price = last_close  # 记录涨停开始的前一天收盘价
            limit_up_days += 1
            limit_up_sequence.append(i)
            highest_price = current_close
            max_increase = (highest_price - starting_price) / starting_price
        else:
            non_limit_up_days += 1

        # 判断连续涨停是否结束
        if non_limit_up_days > max_non_limit_up_days:
            break

    if limit_up_days >= 3 and highest_price is not None and starting_price is not None:
        # 找到符合条件的连续涨停序列
        return limit_up_sequence, highest_price, starting_price, max_increase
    else:
        return None


# 检查是否已回调到黄金分隔位置
def check_fibonacci_retracement(stock_data, starting_price, highest_price, max_increase, limit_up_sequence):
    """
    从连续涨停后的第一个非涨停日开始，检查是否回调到黄金分割点（0.618线）。
    :param stock_data: 股票历史数据
    :param starting_price: 涨停开始时的前一天收盘价
    :param highest_price: 连续涨停的最高点
    :param max_increase: 从起始价到最高点的涨幅
    :param limit_up_sequence: 连续涨停的日期序列（涨停的日期索引列表）
    :return: 返回回调的日期和价格，如果没有回调到黄金分割点返回 None
    """
    # 回调的下限和上限，0.618是黄金分割线
    retracement_lower = starting_price + max_increase * retracement_lower_bound
    retracement_upper = starting_price + max_increase * retracement_upper_bound

    # 找到最后一个涨停日后的一天（第一个非涨停日）
    last_limit_up_day = limit_up_sequence[-1]  # 获取最后一个涨停日
    start_index = last_limit_up_day + 1  # 从下一个交易日开始检查

    # 从涨停序列后的第二天开始检查是否回调到黄金分割区间
    for i in range(start_index, len(stock_data)):
        current_price = stock_data['close'].iloc[i]

        # 检查当前价格是否在黄金分割区间内
        if is_in_fibonacci_retracement(retracement_lower, retracement_upper, current_price):
            return i, current_price  # 返回回调的日期索引和价格

    return None  # 没有回调到黄金分割点


# 获取所有A股股票列表
def get_all_stocks():
    Codes_file_path = os.path.join(data_dir, 'ASharesCodes.csv')
    try:
        stock_codes = pd.read_csv(Codes_file_path)
    except FileNotFoundError:
        try:
            stock_codes = pro.stock_basic(list_status='L')  # 获取上市股票列表
            stock_codes.to_csv(Codes_file_path)
        except Exception as e:
            print(f"Error fetching stock list: {e}")
            return []
    return stock_codes['ts_code'].tolist()


# 筛选符合条件的股票
def filter_stocks(stock_symbol):
    # 获取股票数据
    stock_data = get_stock_data(stock_symbol, days=40)
    if stock_data is None:
        return None

    # 查找连续涨停序列
    result = find_continuous_limit_up(stock_data)

    if result:
        limit_up_sequence, highest_price, starting_price, max_increase = result
        print(f"Stock {stock_symbol} found continuous limit up sequence:")
        print(
            f"Limit up days: {len(limit_up_sequence)}, Starting price: {starting_price}, Highest price: {highest_price}, Max increase: {max_increase * 100}%\n")

        # 检查是否回调到黄金分割点
        retracement_result = check_fibonacci_retracement(stock_data, starting_price, highest_price, max_increase,
                                                         limit_up_sequence)
        if retracement_result:
            retracement_day, retracement_price = retracement_result
            print(
                f"Retraced to Fibonacci level, Retracement day: {retracement_day}, Retracement price: {retracement_price}\n\n")
            return {
                "股票代码": stock_symbol,
                "回调日期": stock_data['trade_date'].iloc[retracement_day],
                "回调价格": retracement_price,
                "涨停序列天数": len(limit_up_sequence),
                "最大涨幅": max_increase * 100
            }
        else:
            print(f"Stock {stock_symbol} did not retrace to Fibonacci level!\n\n")
            return None
    else:
        return None


# 输出符合条件的股票到文件
def result_to_str(result):
    return (
        f"股票代码: {result['股票代码']}\n" \
        f"回调日期: {result['回调日期']}\n" \
        f"回调价格: {result['回调价格']}\n" \
        f"涨停序列天数: {result['涨停序列天数']}\n" \
        f"最大涨幅: {result['最大涨幅']}%"
    )


def output_results(results):
    content = '\n'.join([result_to_str(result) for result in results])
    with open("筛选结果.txt", "w") as f:
        f.write(content)

    # 主执行函数


def main():
    stocks_to_check = get_all_stocks()  # 获取所有股票代码

    # 筛查符合条件的，存储在results中
    results = [result for stock_symbol in stocks_to_check if (result := filter_stocks(stock_symbol))]

    # 输出筛选结果到文件
    output_results(results)


if __name__ == "__main__":
    main()