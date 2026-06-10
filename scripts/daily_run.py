"""
每日定时任务入口脚本

用法：
    python scripts/daily_run.py

适合本地手动运行、Windows 任务计划程序、Linux cron 调用。
"""

from pathlib import Path
import sys

# 确保能导入项目根目录的模块
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline import run_stock_pipeline
from loguru import logger

if __name__ == "__main__":
    data_dir = PROJECT_ROOT / "data"
    logger.info("=== 每日股票数据采集任务启动 ===")
    # 每日任务拉取近 3 年左右的日 K（约 750 个交易日），可按需调大
    df = run_stock_pipeline(output_dir=data_dir, history_limit=800)
    if df is not None and not df.empty:
        logger.success(f"每日任务完成，共采集 {len(df)} 条记录")
        report_path = data_dir / "quality_report.json"
        if report_path.exists():
            logger.info(f"质量报告：{report_path}")
    else:
        logger.error("每日任务失败，未获取到数据")
        sys.exit(1)
