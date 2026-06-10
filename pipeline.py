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
from loguru import logger

from crawler.shanghai_index import fetch_shanghai_index
from crawler.news_crawler import NewsCrawler
from src.analysis.data_quality import (
    log_data_quality_report,
    run_data_quality_check,
    save_quality_report_json,
)
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


def run_news_pipeline(sites: list[str] = None, output_dir: Path = Path("data")):
    """新闻采集（可选）"""
    output_dir.mkdir(parents=True, exist_ok=True)

    crawler = NewsCrawler(headless=True)
    crawler.login_all()

    all_items = []
    for site in (sites or ["sina"]):
        items = crawler.fetch_news(site, limit=30)
        all_items.extend(items)

    crawler.close()

    if all_items:
        from crawler.news_crawler import NewsItem
        # 简单保存为 JSON
        import json
        data = [item.__dict__ for item in all_items]
        json_path = output_dir / "news.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.success(f"新闻数据已保存到 {json_path}")

    return all_items


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