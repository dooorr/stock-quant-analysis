"""
完整数据流程（Pipeline）

串联三个模块：
1. 股票行情采集
2. 新闻数据挖掘（可选）
3. 数据分析 + 可视化

用法示例：
    python pipeline.py --stock-only
    python pipeline.py --all
"""

import argparse
from pathlib import Path

import pandas as pd
from loguru import logger

from crawler.shanghai_index import fetch_shanghai_index
from crawler.news_fetcher import fetch_stock_news
from src.analysis.data_quality import (
    log_data_quality_report,
    run_data_quality_check,
    save_quality_report_json,
)
from src.analysis.news_sentiment import (
    analyze_news_records,
    sentiment_report_to_dict,
    summarize_sentiment,
)
from src.data.news_storage import save_news_dataframe, save_sentiment_report_json
from src.data.storage import load_stock_data, save_stock_data_incremental

DB_FILENAME = "stock_data.db"


def _db_path(output_dir: Path) -> Path:
    return output_dir / DB_FILENAME


def run_stock_data_quality_gate(
    output_dir: Path = Path("data"),
    *,
    db_path: Path | None = None,
) -> None:
    """入库后读取 SQLite 全量数据，输出质量日志并写入 JSON 报告。"""
    db = db_path or _db_path(output_dir)
    stored = load_stock_data(db)
    if stored.empty:
        logger.warning(f"数据质量检测跳过：SQLite 为空或不存在 ({db})")
        return

    report = run_data_quality_check(stored)
    log_data_quality_report(report)
    save_quality_report_json(report, output_dir / "quality_report.json")


def run_stock_pipeline(output_dir: Path = Path("data"), *, history_limit: int = 3000):
    """股票行情采集 + 保存"""
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"开始采集上证指数数据（目标 {history_limit} 条）...")
    df = fetch_shanghai_index(lmt=history_limit)

    if df.empty:
        logger.error("股票数据采集失败")
        return None

    # CSV 备份（兼容原有流程）
    csv_path = output_dir / "stock_data.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.success(f"股票数据已保存到 {csv_path}")

    # SQLite 增量持久化（核心工程化特性）
    save_stock_data_incremental(df, db_path=_db_path(output_dir))

    # 入库后质量检测（日志 + JSON 报告）
    run_stock_data_quality_gate(output_dir)

    return df


def run_news_pipeline(output_dir: Path = Path("data"), *, limit: int = 40):
    """财经新闻抓取 + 标题情感分析 + SQLite/JSON 持久化（无需 Selenium）"""
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = _db_path(output_dir)

    logger.info(f"开始采集财经新闻（目标 {limit} 条）...")
    items = fetch_stock_news(limit=limit)
    if not items:
        logger.warning("未获取到新闻，跳过情感分析")
        return pd.DataFrame()

    records = [item.__dict__ for item in items]
    df_sent = analyze_news_records(records)
    summary = summarize_sentiment(df_sent)

    logger.info(
        f"情感摘要：共 {summary.total} 条 | 正面 {summary.positive} | "
        f"中性 {summary.neutral} | 负面 {summary.negative} | 均分 {summary.avg_score:.3f}"
    )

    # JSON 备份（含情感列）
    import json

    news_json = output_dir / "news_sentiment.json"
    payload = {
        "summary": sentiment_report_to_dict(summary),
        "items": df_sent.to_dict(orient="records"),
    }
    news_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.success(f"新闻情感结果已保存到 {news_json}")

    save_news_dataframe(df_sent, db_path=db_path)
    save_sentiment_report_json(sentiment_report_to_dict(summary), output_dir / "sentiment_report.json")

    return df_sent


def run_full_pipeline(
    stock_only: bool = False,
    news_only: bool = False,
    history_limit: int = 3000,
):
    """一键运行完整流程"""
    logger.info("=== 开始完整数据流程 ===")

    if not news_only:
        run_stock_pipeline(history_limit=history_limit)

    if not stock_only:
        run_news_pipeline()

    logger.success("=== 流程结束 ===")
    logger.info("提示：可运行 `streamlit run gui/streamlit_app.py` 查看可视化界面")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="股票+新闻数据完整流程")
    parser.add_argument("--stock-only", action="store_true", help="仅采集股票数据")
    parser.add_argument("--news-only", action="store_true", help="仅采集新闻数据")
    parser.add_argument("--all", action="store_true", help="采集股票+新闻（默认）")
    parser.add_argument(
        "--history-limit",
        type=int,
        default=3000,
        metavar="N",
        help="上证指数历史日 K 条数上限（默认 3000，东方财富源最多约 10000）",
    )

    args = parser.parse_args()

    if args.stock_only:
        run_full_pipeline(stock_only=True, history_limit=args.history_limit)
    elif args.news_only:
        run_full_pipeline(news_only=True)
    else:
        run_full_pipeline(history_limit=args.history_limit)