# stock_hound
股海追猎


## 目标

- 做成一个web，打开看到很多仪表盘，当前先进行每个小模块的编程，后续再汇总做成web


## 宏观基本面数据追踪

### 美联储

+ 监控美联储降息通知

### 中国利率

+ 监控中国降息降准通知

### 参考指标

+ 监控经济基本面：30年国债的涨跌



## 市场的实时追踪

### 大盘追踪

- 统计个股上涨分布条，情绪预警发布
- 前一天上涨情况预警——已完成python函数
- 盘中预警

+ marketMonitorV2.3-241216.py
  + 1）对A股所有个股进行统计，统计频率是每5秒统计一次、
  + 2）x坐标按照从涨停到跌停，从左到右依次是：涨停、>7%、7-5%、5-2%、2-0%、平、0-2%、2-5%、5-7%、>7%、跌停；
  + 3）涨的数据条显示为红色，跌的显示为绿色；
  + 4）给出一个涨跌家数对比，具体为涨数：平数：跌数；
  + 5）根据上涨家数，和上涨算术平均值，评价大盘情绪
  + 6）我希望图表展示在网页上（未完成）
  + **待完成工作：目前只能警示涨跌，需要功能扩展，并实现网页上数据可视化**

+ 大盘资金面：对大盘的量能进行监控与评价
  + 上涨：缩量or放量
  + 下跌：缩量or放量

### 盘前海外股市表现提示

- 开盘前，隔夜美股等海外指标的提前发现，比如小米adr

  

## 选个股

### 涨停选个股

#### 连续涨停股筛选

+ 筛选连续涨停股，供后续分析，按涨停板数从动到少排列
+ 研究连续涨停第一个放量日买进，后续收益分析

#### 连续大涨回调

+ 连续多日上涨回调至黄金分割点——已完成python函数
+ selectStock20241120_通义优化.py
  + **待完善**：目前的缺陷，每分钟只能访问数据库500次，会卡住

### 急速涨跌选个股

#### 尾盘15分钟急速拉升和急速下降选股



## 题材概念股监控

### 影视概念股

+ 监控票房数据

### 汽车概念股

+ 监控车型销量



## 舆情监控


+ **待完成**
  + 设置关键词，然后按照关键词搜罗信息



## 待探索的模式

- 监测港币汇率、美元汇率->图表展示

- 对应热点，隔夜涨停挂单抢筹
- 同一类型的热点，某一只股票反弹，其它股票虽然滞后，也会反弹，可以设定个程序，抓这个
- 热点当天从超跌到翻红，赚到这个甚至超过一个涨停，从-13到13%，就是26个点。
- 找到一个2~4个涨停板，然后突然成交量放大的（涨停交易日平均值的5倍以上，给出放大强度值）
- 如果持有一只股，就可以做T，假设这只股今天开盘触及跌停了，但不是非常的盯死在跌停板，今天后半天跌无可跌，那么就可以介入，只要他回5个点，就做T
