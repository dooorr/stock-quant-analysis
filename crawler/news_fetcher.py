"""
轻量财经新闻抓取（requests + JSON，无需 Selenium）

优先使用新浪财经滚动新闻 API；失败时返回空列表，由 Pipeline 记录日志。
"""

from __future__ import annotations

import time
from typing import List, Optional

import requests
from loguru import logger

from crawler.news_crawler import NewsItem

# 新浪财经滚动新闻（A 股 / 财经频道，结构稳定）
SINA_ROLL_API = "https://feed.mix.sina.com.cn/api/roll/get"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; stock-quant-pipeline/1.0)",
    "Referer": "https://finance.sina.com.cn/",
}


def fetch_sina_finance_news(limit: int = 30, timeout: float = 15.0) -> List[NewsItem]:
    """
    从新浪滚动 API 拉取财经新闻标题。

    pageid/lid 为新浪站内频道标识；仅抓标题与链接，不抓正文。
    """
    params = {
        "pageid": "153",
        "lid": "2510",
        "k": "",
        "num": min(max(limit, 1), 50),
        "page": 1,
    }
    resp = requests.get(SINA_ROLL_API, params=params, headers=DEFAULT_HEADERS, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()

    data = payload.get("result", {}).get("data", [])
    if not isinstance(data, list):
        logger.warning("新浪新闻 API 返回结构异常")
        return []

    items: List[NewsItem] = []
    for row in data[:limit]:
        if not isinstance(row, dict):
            continue
        title = (row.get("title") or "").strip()
        url = (row.get("url") or row.get("wapurl") or "").strip()
        if not title:
            continue
        ctime = row.get("ctime") or row.get("create_time") or ""
        if isinstance(ctime, (int, float)) and ctime > 1e9:
            ctime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ctime))
        items.append(
            NewsItem(
                title=title,
                url=url,
                publish_time=str(ctime),
                source="sina_roll",
            )
        )

    logger.success(f"新浪财经新闻：获取 {len(items)} 条")
    return items


def fetch_stock_news(limit: int = 30, timeout: float = 15.0) -> List[NewsItem]:
    """统一入口：当前仅新浪源，后续可在此链式回退其他源。"""
    try:
        return fetch_sina_finance_news(limit=limit, timeout=timeout)
    except Exception as e:
        logger.error(f"财经新闻抓取失败: {e}")
        return []
