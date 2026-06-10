"""
上证指数历史数据采集

数据源（按优先级）：
1. 东方财富 JSON API — 一次最多约 10000 条日 K
2. 新浪财经 JSON API — 单次最多约 1023 条（国内网络通常更稳）
3. Investing.com AJAX 分页 — 按年份分段抓取
4. Investing.com 首页表格 — 仅 ~20 条，最后兜底

用法：
    from crawler.shanghai_index import fetch_shanghai_index
    df = fetch_shanghai_index(lmt=3000)  # 默认自动选源，最多 3000 条
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Literal, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from loguru import logger

SourceType = Literal["auto", "eastmoney", "sina", "investing"]

EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
SINA_KLINE_URL = (
    "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "CN_MarketData.getKLineData"
)
INVESTING_AJAX_URL = "https://cn.investing.com/instruments/HistoricalDataAjax"
INVESTING_PAGE_URL = "https://cn.investing.com/indices/shanghai-composite-historical-data"
INVESTING_CURR_ID = "40820"  # 上证指数

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _request_with_retry(
    method: str,
    url: str,
    *,
    max_retries: int = 3,
    timeout: int = 20,
    **kwargs,
) -> Optional[requests.Response]:
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.request(method, url, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            logger.warning(f"[请求] 第 {attempt}/{max_retries} 次失败: {exc}")
            if attempt < max_retries:
                time.sleep(2)
    return None


def _normalize_stock_df(df: pd.DataFrame) -> pd.DataFrame:
    """统一列名与排序（最新日期在前，与原有 CSV 一致）。"""
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]

    rename_map = {
        "Date": "日期",
        "Price": "收盘",
        "Open": "开盘",
        "High": "高",
        "Low": "低",
        "Vol.": "交易量",
        "Change %": "涨跌幅",
    }
    out = out.rename(columns={k: v for k, v in rename_map.items() if k in out.columns})

    if "日期" in out.columns:
        out["日期"] = pd.to_datetime(out["日期"], errors="coerce")
        out = out.dropna(subset=["日期"])
        out["日期"] = out["日期"].dt.strftime("%Y-%m-%d")
        out = out.drop_duplicates(subset=["日期"], keep="first")
        out = out.sort_values("日期", ascending=False)

    return out.reset_index(drop=True)


def fetch_shanghai_index_eastmoney(
    lmt: int = 5000,
    secid: str = "1.000001",
    max_retries: int = 3,
) -> pd.DataFrame:
    """
    东方财富日 K 接口。secid=1.000001 为上证指数，lmt 最大约 10000。
    """
    lmt = max(1, min(int(lmt), 10000))
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "end": "20500101",
        "lmt": lmt,
    }
    headers = {**_DEFAULT_HEADERS, "Referer": "https://quote.eastmoney.com/"}

    resp = _request_with_retry(
        "GET",
        EASTMONEY_KLINE_URL,
        params=params,
        headers=headers,
        max_retries=max_retries,
    )
    if resp is None:
        return pd.DataFrame()

    payload = resp.json()
    klines = (payload.get("data") or {}).get("klines") or []
    if not klines:
        logger.warning("[东方财富] 响应无 klines 数据")
        return pd.DataFrame()

    rows = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 9:
            continue
        pct = parts[8]
        rows.append(
            {
                "日期": parts[0],
                "开盘": parts[1],
                "收盘": parts[2],
                "高": parts[3],
                "低": parts[4],
                "交易量": parts[5],
                "涨跌幅": f"{pct}%" if not str(pct).endswith("%") else str(pct),
            }
        )

    df = _normalize_stock_df(pd.DataFrame(rows))
    logger.success(f"[东方财富] 获取 {len(df)} 条上证指数日 K")
    return df


def fetch_shanghai_index_sina(
    datalen: int = 1023,
    symbol: str = "sh000001",
    max_retries: int = 3,
) -> pd.DataFrame:
    """
    新浪财经日 K 接口。symbol=sh000001 为上证指数，单次最多约 1023 条。
    """
    datalen = max(1, min(int(datalen), 1023))
    params = {"symbol": symbol, "scale": 240, "ma": "no", "datalen": datalen}
    headers = {**_DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn/"}

    resp = _request_with_retry(
        "GET",
        SINA_KLINE_URL,
        params=params,
        headers=headers,
        max_retries=max_retries,
    )
    if resp is None:
        return pd.DataFrame()

    try:
        payload = resp.json()
    except Exception as exc:
        logger.warning(f"[新浪财经] JSON 解析失败: {exc}")
        return pd.DataFrame()

    if not isinstance(payload, list) or not payload:
        logger.warning("[新浪财经] 响应为空")
        return pd.DataFrame()

    rows = []
    for item in payload:
        if not isinstance(item, dict) or "day" not in item:
            continue
        close = float(item.get("close", 0) or 0)
        open_ = float(item.get("open", 0) or 0)
        if close <= 0:
            continue
        pct = (close - open_) / open_ * 100 if open_ else 0.0
        rows.append(
            {
                "日期": item["day"],
                "开盘": item.get("open"),
                "收盘": item.get("close"),
                "高": item.get("high"),
                "低": item.get("low"),
                "交易量": item.get("volume"),
                "涨跌幅": f"{pct:.2f}%",
            }
        )

    df = _normalize_stock_df(pd.DataFrame(rows))
    logger.success(f"[新浪财经] 获取 {len(df)} 条上证指数日 K")
    return df


def fetch_shanghai_index_investing_ajax(
    max_rows: int = 500,
    years_per_chunk: int = 1,
    max_retries: int = 3,
) -> pd.DataFrame:
    """
    Investing.com 历史数据 AJAX，按年份分段请求并合并。
    比首页多页表格稳定，但单次仍只有几十条，需分段。
    """
    headers = {
        **_DEFAULT_HEADERS,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": INVESTING_PAGE_URL,
        "Origin": "https://cn.investing.com",
    }

    end = datetime.now()
    chunks: list[pd.DataFrame] = []
    total = 0

    while total < max_rows:
        start = end - timedelta(days=365 * years_per_chunk)
        data = {
            "curr_id": INVESTING_CURR_ID,
            "st_date": start.strftime("%m/%d/%Y"),
            "end_date": end.strftime("%m/%d/%Y"),
            "interval_sec": "Daily",
            "sort_col": "date",
            "sort_ord": "DESC",
            "action": "historical_data",
        }
        resp = _request_with_retry(
            "POST",
            INVESTING_AJAX_URL,
            headers=headers,
            data=data,
            max_retries=max_retries,
        )
        if resp is None or not resp.text.strip():
            break

        try:
            tables = pd.read_html(resp.text)
            if not tables:
                break
            chunk = _normalize_stock_df(tables[0])
        except Exception as exc:
            logger.warning(f"[Investing AJAX] 解析失败: {exc}")
            break

        if chunk.empty:
            break

        chunks.append(chunk)
        total += len(chunk)
        logger.info(f"[Investing AJAX] 分段 {data['st_date']}~{data['end_date']} → {len(chunk)} 条")

        end = start - timedelta(days=1)
        if end.year < 1990:
            break

    if not chunks:
        return pd.DataFrame()

    df = pd.concat(chunks, ignore_index=True)
    df = _normalize_stock_df(df).head(max_rows)
    logger.success(f"[Investing AJAX] 合计 {len(df)} 条")
    return df


def fetch_shanghai_index_requests(
    url: str = INVESTING_PAGE_URL,
    max_retries: int = 3,
    timeout: int = 15,
) -> pd.DataFrame:
    """Investing.com 首页表格（仅最近约 20 条，兜底用）。"""
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"[Investing 首页] 尝试第 {attempt} 次...")
            resp = requests.get(url, headers=_DEFAULT_HEADERS, timeout=timeout)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")
            table = soup.find("table")
            if table is None:
                logger.warning("[Investing 首页] 未找到表格")
                return pd.DataFrame()

            df = _normalize_stock_df(pd.read_html(str(table))[0])
            logger.success(f"[Investing 首页] 获取 {len(df)} 条")
            return df

        except Exception as exc:
            logger.warning(f"[Investing 首页] 第 {attempt} 次失败: {exc}")
            if attempt < max_retries:
                time.sleep(2)

    return pd.DataFrame()


def fetch_shanghai_index(
    lmt: int = 3000,
    source: SourceType = "auto",
) -> pd.DataFrame:
    """
    统一采集入口。

    Args:
        lmt: 目标最大条数（日 K 根数）
        source: auto | eastmoney | sina | investing
    """
    lmt = max(1, int(lmt))

    if source in ("auto", "eastmoney"):
        df = fetch_shanghai_index_eastmoney(lmt=lmt)
        if not df.empty:
            return df.head(lmt)
        if source == "eastmoney":
            return df

    if source in ("auto", "sina"):
        df = fetch_shanghai_index_sina(datalen=lmt)
        if not df.empty:
            if source == "auto" and len(df) < lmt:
                logger.info(
                    f"[采集] 新浪源返回 {len(df)} 条（上限 1023），"
                    f"未达目标 {lmt} 条"
                )
            return df.head(lmt)
        if source == "sina":
            return df

    if source in ("auto", "investing"):
        df = fetch_shanghai_index_investing_ajax(max_rows=lmt)
        if not df.empty:
            return df.head(lmt)
        df = fetch_shanghai_index_requests()
        if not df.empty:
            logger.warning(
                f"[采集] 仅获取到首页 {len(df)} 条；"
                "可检查网络或稍后重试东方财富源"
            )
        return df.head(lmt)

    return pd.DataFrame()


def fetch_shanghai_index_selenium(url: str = "...") -> pd.DataFrame:
    """原版 Selenium 方式（保留作为备选，默认未启用）。"""
    logger.info("[提示] Selenium 版本已注释，如需使用请取消注释")
    return pd.DataFrame()


if __name__ == "__main__":
    print("=== 上证指数数据采集（多源） ===\n")
    df = fetch_shanghai_index(lmt=100)
    if not df.empty:
        print(df.head())
        print(f"\n共 {len(df)} 条，列：{list(df.columns)}")
    else:
        print("未能获取数据")
