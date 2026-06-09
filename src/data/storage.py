"""
SQLite 增量存储层

提供股票数据的持久化与增量更新能力：
- 自动建表（日期为主键）
- 增量 upsert（INSERT OR REPLACE）
- 支持 DataFrame 批量写入
"""

import sqlite3
from pathlib import Path
from typing import Optional
import pandas as pd
from loguru import logger


DEFAULT_DB_PATH = Path("data/stock_data.db")
TABLE_NAME = "stock_data"


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """获取 SQLite 连接（自动创建目录）"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_stock_table(conn: sqlite3.Connection) -> None:
    """初始化股票数据表（如果不存在）"""
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            日期 TEXT PRIMARY KEY,
            收盘 REAL,
            开盘 REAL,
            高 REAL,
            低 REAL,
            交易量 TEXT,
            涨跌幅 TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def save_stock_data_incremental(
    df: pd.DataFrame,
    db_path: Path = DEFAULT_DB_PATH,
    table: str = TABLE_NAME,
) -> int:
    """
    增量保存股票数据（upsert）

    Args:
        df: 包含股票数据的 DataFrame，必须有「日期」列
        db_path: 数据库文件路径
        table: 表名

    Returns:
        实际写入/更新的记录数
    """
    if df is None or df.empty:
        logger.warning("DataFrame 为空，跳过保存")
        return 0

    # 标准化列名（去除空格等）
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if "日期" not in df.columns:
        logger.error("DataFrame 缺少「日期」列，无法增量保存")
        return 0

    conn = get_connection(db_path)
    init_stock_table(conn)

    # 只保留表中存在的列
    table_cols = ["日期", "收盘", "开盘", "高", "低", "交易量", "涨跌幅"]
    existing_cols = [c for c in table_cols if c in df.columns]
    df_to_save = df[existing_cols].copy()

    # 转换为记录列表
    records = df_to_save.to_dict(orient="records")

    # 使用 INSERT OR REPLACE 实现 upsert
    placeholders = ", ".join(["?"] * len(existing_cols))
    columns_str = ", ".join(existing_cols)
    sql = f"INSERT OR REPLACE INTO {table} ({columns_str}) VALUES ({placeholders})"

    cursor = conn.cursor()
    cursor.executemany(sql, [tuple(r.values()) for r in records])
    conn.commit()

    inserted = cursor.rowcount
    logger.success(f"SQLite 增量保存完成：{inserted} 条记录写入/更新 → {db_path}")
    conn.close()
    return inserted


def load_stock_data(
    db_path: Path = DEFAULT_DB_PATH,
    table: str = TABLE_NAME,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """从 SQLite 读取股票数据"""
    if not db_path.exists():
        return pd.DataFrame()

    conn = get_connection(db_path)
    query = f"SELECT * FROM {table} ORDER BY 日期 DESC"
    if limit:
        query += f" LIMIT {limit}"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df
