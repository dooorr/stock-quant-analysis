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

from crawler.shanghai_index import fetch_shanghai_index_requests
from crawler.news_crawler import NewsCrawler
from src.data.storage import save_stock_data_incremental


def run_stock_pipeline(output_dir: Path = Path("data")):
    """股票行情采集 + 保存"""
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("开始采集上证指数数据...")
    df = fetch_shanghai_index_requests()

    if df.empty:
        logger.error("股票数据采集失败")
        return None

    # CSV 备份（兼容原有流程）
    csv_path = output_dir / "stock_data.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.success(f"股票数据已保存到 {csv_path}")

    # SQLite 增量持久化（核心工程化特性）
    save_stock_data_incremental(df)

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


def run_full_pipeline(stock_only: bool = False, news_only: bool = False):
    """一键运行完整流程"""
    logger.info("=== 开始完整数据流程 ===")

    if not news_only:
        run_stock_pipeline()

    if not stock_only:
        run_news_pipeline()

    logger.success("=== 流程结束 ===")
    logger.info("提示：可运行 `streamlit run gui/streamlit_app.py` 查看可视化界面")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="股票+新闻数据完整流程")
    parser.add_argument("--stock-only", action="store_true", help="仅采集股票数据")
    parser.add_argument("--news-only", action="store_true", help="仅采集新闻数据")
    parser.add_argument("--all", action="store_true", help="采集股票+新闻（默认）")

    args = parser.parse_args()

    if args.stock_only:
        run_full_pipeline(stock_only=True)
    elif args.news_only:
        run_full_pipeline(news_only=True)
    else:
        run_full_pipeline()