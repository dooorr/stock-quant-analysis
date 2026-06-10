"""
新闻 + 情感分析结果 SQLite 存储
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger

from src.data.storage import get_connection

DEFAULT_DB_PATH = Path("data/stock_data.db")
NEWS_TABLE = "news_items"


def init_news_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {NEWS_TABLE} (
            url TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            publish_time TEXT,
            source TEXT,
            sentiment_score REAL,
            sentiment_label TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


def save_news_dataframe(
    df: pd.DataFrame,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    if df is None or df.empty:
        logger.warning("新闻 DataFrame 为空，跳过入库")
        return 0

    conn = get_connection(db_path)
    init_news_table(conn)

    cols = ["url", "title", "publish_time", "source", "sentiment_score", "sentiment_label"]
    for c in cols:
        if c not in df.columns:
            df[c] = ""

    records = df[cols].to_dict(orient="records")
    sql = f"""
        INSERT OR REPLACE INTO {NEWS_TABLE}
        (url, title, publish_time, source, sentiment_score, sentiment_label)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    cursor = conn.cursor()
    cursor.executemany(
        sql,
        [
            (
                r.get("url") or f"local://{hash(r.get('title', ''))}",
                r.get("title", ""),
                r.get("publish_time", ""),
                r.get("source", ""),
                r.get("sentiment_score"),
                r.get("sentiment_label", ""),
            )
            for r in records
        ],
    )
    conn.commit()
    n = cursor.rowcount
    conn.close()
    logger.success(f"新闻情感数据入库：{n} 条 → {db_path}")
    return n


def load_news_data(
    db_path: Path = DEFAULT_DB_PATH,
    limit: Optional[int] = 100,
) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame()

    conn = get_connection(db_path)
    init_news_table(conn)
    q = f"SELECT * FROM {NEWS_TABLE} ORDER BY fetched_at DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    df = pd.read_sql_query(q, conn)
    conn.close()
    return df


def save_sentiment_report_json(report: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"情感摘要已写入 {path}")
