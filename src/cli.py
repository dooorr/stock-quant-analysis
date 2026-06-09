"""
命令行入口（使用 Typer）
"""
import typer
from rich import print as rprint
from rich.table import Table

app = typer.Typer(help="股票数据采集与量化分析系统（升级版）")


@app.command()
def version():
    """显示版本信息"""
    from src import __version__
    rprint(f"[bold green]stock-quant-analysis[/bold green] v{__version__}")


@app.command()
def fetch(source: str = typer.Argument("stock", help="数据源: stock / news")):
    """采集数据"""
    if source == "stock":
        from crawler.shanghai_index import fetch_shanghai_index_requests
        df = fetch_shanghai_index_requests()
        rprint(f"[green]成功采集 {len(df)} 条股票数据[/green]")
    elif source == "news":
        from crawler.news_crawler import NewsCrawler
        crawler = NewsCrawler(headless=True)
        items = crawler.fetch_news("sina", limit=10)
        crawler.close()
        rprint(f"[green]成功采集 {len(items)} 条新闻[/green]")
    else:
        rprint("[red]不支持的数据源[/red]")


@app.command()
def pipeline(
    mode: str = typer.Argument("all", help="模式: all / stock / news"),
    output_dir: str = typer.Option("data", "--output-dir", help="输出目录"),
):
    """运行完整数据流程"""
    from pathlib import Path
    from pipeline import run_stock_pipeline, run_news_pipeline, run_full_pipeline

    out = Path(output_dir)
    if mode == "stock":
        run_stock_pipeline(output_dir=out)
    elif mode == "news":
        run_news_pipeline(output_dir=out)
    else:
        run_full_pipeline()


@app.command()
def gui(type: str = typer.Argument("streamlit", help="界面类型: streamlit / tk")):
    """启动可视化界面"""
    import subprocess
    import sys

    if type == "streamlit":
        rprint("[cyan]启动 Streamlit 界面...[/cyan]")
        subprocess.run([sys.executable, "-m", "streamlit", "run", "gui/streamlit_app.py"])
    elif type == "tk":
        rprint("[cyan]启动 Tkinter 界面...[/cyan]")
        subprocess.run([sys.executable, "gui/tk_app.py"])
    else:
        rprint("[red]不支持的界面类型[/red]")


if __name__ == "__main__":
    app()