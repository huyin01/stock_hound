

# 配置工作文件夹
work_dir_office = r"D:\BaiduNetdiskWorkspace\J计算机\python\stock\marketMonitoring20241119"
work_dir_home = r"D:\BaiduSyncdisk\J计算机\python\stock\marketMonitoring20241119"
# 修改工作目录至当前文件夹
host_name = socket.gethostname()
work_dir = work_dir_office if host_name == "jtzb-huyinD01" else work_dir_home
os.chdir(work_dir)

# 配置要监测的国外指数列表 - 使用正确的指数代码
us_index_dic = {
    "道琼斯": ".dji",
    "纳斯达克": ".ixic",
    "标普500": ".INX",
    "纳斯达克100": ".NDX",
    "纳指金龙中国": ".HXC",
}
cn_index_dic = {
    "上证综指": "sh000001",
    "深证成指": "sz399001",
    "创业板指": "sz399006",
    "上证50ETF": "sh000016",
}
hk_index_dic = {"恒生指数": "HSI"}  # 恒生指数
index_dic = us_index_dic | cn_index_dic | hk_index_dic

WARING_VALUE = 2  # 涨跌幅预警值（%）

# 配置日志
def setup_logger() -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()
    log_file_path = "monitor.log"
    # 创建文件处理程序
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    # 创建控制台处理程序
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 创建格式化器
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 添加处理程序到logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


# 获取股市数据的函数
def get_last2days_index_data(code: str) -> pd.DataFrame:
    logging.info(f"Start running get_code_last2_day of {code}")

    assert code in index_dic.values(), f"\n\n！！{code}不在监控之列！！\n\n"

    if code in us_index_dic.values():
        return ak.index_us_stock_sina(symbol=code).tail(2)  # 直接返回

    if code in cn_index_dic.values():
        return ak.stock_zh_index_daily(symbol=code).tail(2)

    return ak.stock_hk_index_daily_sina(symbol=code).tail(2)


# 检查指数异动
def check_code(check_dic: dict) -> None:
    logging.info("Start running check_code")
    for name, code in check_dic.items():
        change_pct = None
        try:
            data2day = get_last2days_index_data(code)
        except Exception as e:
            logging.error(f"\n\n！！！获取data2day数据时发生错误: {e}！！！\n\n")

        a = data2day["close"].iloc[0]
        b = data2day["close"].iloc[1]
        change_pct = (b - a) / a * 100

        if change_pct is None:
            logging.warning(f"Skipping {name,code} - missing data")
            continue

        # 与涨跌幅阈值比较并进行预警
        if change_pct > WARING_VALUE:
            logging.warning(f"\n\n↑↑↑↑{name,code} 涨幅预警：上涨幅度为 {change_pct:.2f}%↑↑↑↑\n")
        elif change_pct < -WARING_VALUE:
            logging.warning(f"\n\n↓↓↓↓{name,code} 跌幅预警：下跌幅度为 {change_pct:.2f}%↓↓↓↓\n")
        else:
            logging.info(f"----{name,code} 涨跌幅在正常范围内：{change_pct:.2f}%----\n")


# 主函数，设置定时任务
def main() -> None:
    logging.info("Start running main")

    # 设置日志
    setup_logger()

    # 立即执行一次检查
    check_code(index_dic)
    logging.info("check_code运行结束")

    # 设置定时任务执行
    schedule.every().day.at("09:16").do(partial(check_code, index_dic))
    schedule.every().day.at("15:15").do(partial(check_code, cn_index_dic))
    schedule.every().day.at("16:35").do(partial(check_code, hk_index_dic))

    logging.info("已设置定时任务schedule")


if __name__ == "__main__":
    main()
