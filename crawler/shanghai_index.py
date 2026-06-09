"""
上证指数历史数据采集 - 升级版

基于原版「股票数据分析与可视化.ipynb」逻辑重写：
- 优先使用 requests + pandas.read_html（更快、更稳定）
- 保留 Selenium 版本作为备选（注释）
- 增加异常处理和简单重试
"""

import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from typing import Optional


def fetch_shanghai_index_requests(
    url: str = "https://cn.investing.com/indices/shanghai-composite-historical-data",
    max_retries: int = 3,
    timeout: int = 15,
) -> pd.DataFrame:
    """
    使用 requests + pandas.read_html 获取上证指数历史数据

    这是升级后的推荐方式，比 Selenium 快很多，也更稳定。
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[请求] 尝试第 {attempt} 次获取数据...")
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")
            table = soup.find("table")

            if table is None:
                print("[警告] 未找到表格，页面结构可能已变化")
                return pd.DataFrame()

            # pandas.read_html 可以直接把 HTML 表格转成 DataFrame
            df = pd.read_html(str(table))[0]

            print(f"[成功] 共获取 {len(df)} 条记录")
            return df

        except Exception as e:
            print(f"[错误] 第 {attempt} 次失败: {e}")
            if attempt < max_retries:
                time.sleep(2)
            else:
                print("[失败] 已达到最大重试次数")
                return pd.DataFrame()

    return pd.DataFrame()


def fetch_shanghai_index_selenium(url: str = "...") -> pd.DataFrame:
    """
    原版 Selenium 方式（保留作为备选）

    原始代码来自「股票数据分析与可视化.ipynb」，未做修改。
    如需使用，取消下方注释并安装 selenium + webdriver-manager。
    """
    # from selenium import webdriver
    # from selenium.webdriver.common.by import By
    # from selenium.webdriver.support.ui import WebDriverWait
    # from selenium.webdriver.support import expected_conditions as EC
    # from selenium.webdriver.chrome.options import Options
    #
    # chrome_options = Options()
    # chrome_options.add_argument("--lang=zh-CN")
    # browser = webdriver.Chrome(options=chrome_options)
    #
    # browser.get(url)
    # table_xpath = '//*[@id="__next"]/div[2]/div[2]/div[2]/div[1]/div[2]'
    # table = WebDriverWait(browser, 30).until(
    #     EC.presence_of_element_located((By.XPATH, table_xpath))
    # )
    # rows = table.find_elements(By.TAG_NAME, "tr")
    #
    # data = []
    # for row in rows[1:]:
    #     columns = row.find_elements(By.TAG_NAME, "td")
    #     column_data = [col.text for col in columns]
    #     while len(column_data) < 7:
    #         column_data.append("")
    #     data.append(column_data)
    #
    # browser.quit()
    # return pd.DataFrame(data, columns=["日期", "收盘", "开盘", "高", "低", "交易量", "涨跌幅"])

    print("[提示] Selenium 版本已注释，如需使用请取消注释")
    return pd.DataFrame()


if __name__ == "__main__":
    print("=== 升级版：上证指数数据采集 ===\n")

    # 推荐使用 requests 版本
    df = fetch_shanghai_index_requests()

    if not df.empty:
        print("\n前 5 条数据预览：")
        print(df.head())
        print(f"\n列名：{list(df.columns)}")
    else:
        print("未能获取数据")