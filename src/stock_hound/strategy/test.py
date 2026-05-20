import baostock as bs
import pandas as pd

def test_baostock_data():
    """
    测试函数：从 Baostock 获取股票数据并展示
    """
    # 1. 登录 Baostock 系统
    lg = bs.login()
    if lg.error_code != '0':
        print(f"登录失败: {lg.error_msg}")
        return

    print("登录成功！开始获取数据...\n")

    # 2. 设置查询参数（以贵州茅台为例）
    stock_code = 'sh.600519'  # 股票代码：贵州茅台
    start_date = '2023-01-01' # 开始日期
    end_date = '2023-12-31'   # 结束日期
    frequency = 'd'           # 日线
    adjustflag = '3'          # 不复权

    # 3. 获取历史 K 线数据
    rs = bs.query_history_k_data_plus(
        stock_code,
        fields="date,code,open,high,low,close,volume,amount,pctChg", # 请求的字段
        start_date=start_date, 
        end_date=end_date,
        frequency=frequency, 
        adjustflag=adjustflag
    )

    # 4. 将结果集转换为 Pandas DataFrame
    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    
    df = pd.DataFrame(data_list, columns=rs.fields)

    # 5. 数据清洗：将字符串类型的字段转换为数值和日期格式
    # 注意：Baostock 返回的数据默认全是 object (字符串)，必须转换才能做计算
    df['date'] = pd.to_datetime(df['date'])
    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'pctChg']
    df[numeric_cols] = df[numeric_cols].astype('float')

    # 6. 展示数据
    print(f"✅ 成功获取 {stock_code} 的数据，共 {len(df)} 行\n")
    
    print("👀 数据前 5 行预览：")
    print(df.head())  # 打印前 5 行
    
    print("\n📊 数据基本信息（查看字段类型）：")
    print(df.info())  # 查看数据类型和缺失情况

    # 7. 登出系统
    bs.logout()

# 运行测试函数
if __name__ == "__main__":
    test_baostock_data()