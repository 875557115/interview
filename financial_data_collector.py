import yfinance as yf
import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import schedule
import time
import tushare as ts


def get_us_stock_data(ticker_symbol: str):
    """
    获取指定美股代码的最新股票数据。
    """
    try:
        stock = yf.Ticker(ticker_symbol)
        # 获取最新股票信息，例如收盘价、开盘价、最高价、最低价、成交量等
        hist = stock.history(period="1d") # 获取最近一天的历史数据
        if not hist.empty:
            latest_data = hist.iloc[-1]
            print(f"--- 美股 {ticker_symbol} 最新数据 ---")
            print(f"开盘价: {latest_data['Open']:.2f}")
            print(f"最高价: {latest_data['High']:.2f}")
            print(f"最低价: {latest_data['Low']:.2f}")
            print(f"收盘价: {latest_data['Close']:.2f}")
            print(f"成交量: {latest_data['Volume']}")
            return latest_data
        else:
            print(f"未获取到 {ticker_symbol} 的数据。")
            return None
    except Exception as e:
        print(f"获取 {ticker_symbol} 美股数据时发生错误: {e}")
        return None

def get_a_share_data(stock_code: str):
    """
    获取指定A股代码的最新股票数据。
    """
    try:
        # 登陆系统
        lg = bs.login()
        # 显示登陆返回信息
        print('login respond error_code:'+lg.error_code)
        print('login respond error_msg:'+lg.error_msg)

        # 获取今日K线数据
        rs = bs.query_history_k_data_plus(stock_code,
            "date,code,open,high,low,close,preclose,volume,amount,pctChg",
            start_date=datetime.now().strftime('%Y-%m-%d'),
            end_date=datetime.now().strftime('%Y-%m-%d'),
            frequency="d", adjustflag="3") #填写数据类型、日期范围，默认调整方式
        
        # 打印结果集
        data_list = []
        while (rs.error_code == '0') & rs.next():
            # 获取一条记录，将第一条记录（即今日数据）存入data_list
            data_list.append(rs.get_row_data())
            break # 只取最新一条数据

        # 登出系统
        bs.logout()

        if data_list:
            result = pd.DataFrame(data_list, columns=rs.fields)
            latest_data = result.iloc[-1]
            print(f"--- A股 {stock_code} 最新数据 ---")
            print(f"日期: {latest_data['date']}")
            print(f"开盘价: {float(latest_data['open']):.2f}")
            print(f"最高价: {float(latest_data['high']):.2f}")
            print(f"最低价: {float(latest_data['low']):.2f}")
            print(f"收盘价: {float(latest_data['close']):.2f}")
            print(f"成交量: {float(latest_data['volume']):.2f}")
            print(f"涨跌幅: {float(latest_data['pctChg']):.2f}%")
            return latest_data
        else:
            print(f"未获取到 {stock_code} 的数据。")
            return None

    except Exception as e:
        print(f"获取 {stock_code} A股数据时发生错误: {e}")
        return None

def get_financial_news():
    """
    获取金融新闻摘要，使用 Tushare Pro 接口。
    """
    print("--- 金融新闻摘要 (来自 Tushare Pro) ---")
    # 请替换为您的 Tushare Pro API Token
    # 您可以在 Tushare Pro 官网 (https://tushare.pro/) 注册并获取 Token。
    TUSHARE_PRO_TOKEN = "YOUR_TUSHARE_PRO_TOKEN" # <<<<<<<< IMPORTANT: REPLACE THIS WITH YOUR ACTUAL TOKEN

    if TUSHARE_PRO_TOKEN == "YOUR_TUSHARE_PRO_TOKEN":
        print("错误: 请在 financial_data_collector.py 中设置 TUSHARE_PRO_TOKEN。")
        return

    try:
        pro = ts.pro_api(TUSHARE_PRO_TOKEN)
        # 获取最新的新闻，可以根据需要调整参数，例如 src='sina' 或 top=N
        # Tushare Pro 接口文档: https://tushare.pro/document/2?doc_id=143
        news_df = pro.news(src='sina', start_date=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'))

        if news_df is not None and not news_df.empty:
            for index, row in news_df.head(5).iterrows(): # 获取最新的5条新闻
                print(f"[{row['datetime']}] {row['title']} - {row['url']}")
        else:
            print("未获取到金融新闻，请检查 Tushare Pro 配置或网站数据。")

    except Exception as e:
        print(f"获取金融新闻时发生错误: {e}")
    return None

def run_all_tasks():
    print(f"\n{'='*30}\n开始执行定时任务: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*30}")
    get_us_stock_data("AAPL")
    get_us_stock_data("MSFT")
    get_a_share_data("sh.600030")
    get_a_share_data("sz.000001")
    get_financial_news()
    print(f"\n{'='*30}\n定时任务执行完毕: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*30}")

if __name__ == '__main__':
    # 首次立即执行一次
    run_all_tasks()

    # 设置定时任务，例如每5分钟运行一次
    # 在实际应用中，您可以根据需求调整时间，例如：
    # schedule.every().day.at("10:30").do(run_all_tasks)
    # schedule.every().hour.do(run_all_tasks)
    schedule.every(5).minutes.do(run_all_tasks) # 用于测试，每5分钟运行一次

    while True:
        schedule.run_pending()
        time.sleep(1) # 每秒检查一次计划任务 

