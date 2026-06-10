"""
股票数据可视化与分析 - Streamlit

功能：
- 从 SQLite / CSV 加载上证指数数据
- 数据质量监控（空值、缺口、异常跳变、OHLC 一致性）
- 价格 + RSI 图表
- RSI 超买超卖策略回测，对比买入持有基准收益
- 财经新闻标题情感分析（金融词典规则打分）
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.data_quality import run_data_quality_check
from src.analysis.ma_backtest import compute_sma, run_ma_backtest
from src.analysis.rsi_backtest import compute_rsi, prepare_ohlc_df, run_rsi_backtest
from src.analysis.news_sentiment import summarize_sentiment
from src.data.news_storage import load_news_data
from src.data.storage import DEFAULT_DB_PATH, load_stock_data


def _load_news_sentiment() -> tuple[pd.DataFrame, str]:
    """优先 SQLite news_items，其次 data/news_sentiment.json。"""
    db_path = ROOT / DEFAULT_DB_PATH
    df = load_news_data(db_path, limit=200)
    if not df.empty:
        return df, f"SQLite ({db_path.relative_to(ROOT)})"

    json_path = ROOT / "data" / "news_sentiment.json"
    if json_path.exists():
        import json

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        items = payload.get("items", [])
        if items:
            return pd.DataFrame(items), str(json_path.relative_to(ROOT))

    return pd.DataFrame(), ""


def _render_news_sentiment_tab() -> None:
    st.subheader("📰 财经新闻情感分析")

    df_news, news_source = _load_news_sentiment()
    if df_news.empty:
        st.info("暂无新闻数据。请运行：`python pipeline.py --news-only`")
        st.code("python pipeline.py --news-only", language="bash")
        return

    st.caption(f"数据来源：{news_source}（标题级规则情感，非深度学习）")

    summary = summarize_sentiment(df_news)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("新闻条数", str(summary.total))
    c2.metric("正面", str(summary.positive))
    c3.metric("中性", str(summary.neutral))
    c4.metric("负面", str(summary.negative))
    c5.metric("平均情感分", f"{summary.avg_score:.3f}")

    if summary.total:
        pie_df = pd.DataFrame(
            {
                "情感": ["正面", "中性", "负面"],
                "数量": [summary.positive, summary.neutral, summary.negative],
            }
        )
        fig_pie, ax_pie = plt.subplots(figsize=(4, 4))
        colors = ["#2A9D8F", "#8D99AE", "#E63946"]
        ax_pie.pie(
            pie_df["数量"],
            labels=pie_df["情感"],
            autopct="%1.0f%%",
            colors=colors,
            startangle=90,
        )
        ax_pie.set_title("情感分布")
        st.pyplot(fig_pie)

    st.markdown("#### 新闻列表（按抓取时间）")

    def _color_label(val: str) -> str:
        if val == "正面":
            return "background-color: #d8f3dc"
        if val == "负面":
            return "background-color: #ffe5e5"
        return "background-color: #f1f3f5"

    show = df_news.copy()
    for col in ("sentiment_score",):
        if col in show.columns:
            show[col] = show[col].map(lambda x: f"{float(x):.3f}" if pd.notna(x) else "")

    display_cols = [c for c in ("title", "sentiment_label", "sentiment_score", "publish_time", "source", "url") if c in show.columns]
    styled = show[display_cols].style.map(_color_label, subset=["sentiment_label"]) if "sentiment_label" in show.columns else show[display_cols]
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.caption(
        "说明：基于财经正/负面词典对标题打分（-1~1），供舆情概览学习演示；"
        "不构成投资建议。词典见 src/analysis/news_sentiment.py。"
    )


def _load_market_data() -> tuple[pd.DataFrame, str]:
    """优先 SQLite，其次 cleaned CSV，最后原始 CSV。"""
    db_path = ROOT / DEFAULT_DB_PATH
    if db_path.exists():
        df = load_stock_data(db_path)
        if not df.empty:
            df = df.sort_values("日期")
            return df, f"SQLite ({db_path.relative_to(ROOT)})"

    for name in ("cleaned_stock_data.csv", "stock_data.csv", "data/stock_data.csv"):
        path = ROOT / name
        if path.exists():
            return pd.read_csv(path), name

    return pd.DataFrame(), ""


def _health_badge(score: float) -> str:
    if score >= 90:
        return "🟢 优秀"
    if score >= 80:
        return "🟡 良好"
    if score >= 60:
        return "🟠 需关注"
    return "🔴 较差"


def _render_quality_tab(df_raw: pd.DataFrame) -> None:
    st.subheader("🔍 数据质量监控")

    c1, c2 = st.columns([1, 2])
    with c1:
        jump_pct = st.slider(
            "异常跳变阈值（日收益率 %）",
            3,
            15,
            8,
            1,
            help="日收益率绝对值超过该比例时标记为异常跳变",
        )
        jump_threshold = jump_pct / 100.0
    with c2:
        sigma_k = st.slider("动态阈值（收益率标准差倍数）", 2.0, 5.0, 3.0, 0.5)

    report = run_data_quality_check(
        df_raw,
        jump_threshold=jump_threshold,
        sigma_k=sigma_k,
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("健康评分", f"{report.health_score:.0f}", _health_badge(report.health_score))
    m2.metric("有效记录", str(report.row_count))
    m3.metric("重复日期", str(report.duplicate_date_count))
    m4.metric("交易日缺口", str(report.missing_trading_days))
    m5.metric("异常跳变", str(len(report.price_jump_rows)))

    if report.date_start is not None and report.date_end is not None:
        st.caption(
            f"覆盖区间：{report.date_start.date()} ~ {report.date_end.date()}"
        )

    if report.issues:
        st.warning("检测到的问题：" + "；".join(report.issues))
    else:
        st.success("未发现明显数据质量问题")

    st.markdown("#### 各列空值率")
    if not report.null_rates.empty:
        null_view = report.null_rates.copy()
        null_view["空值率"] = null_view["空值率"].map(lambda x: f"{x:.1%}")
        st.dataframe(null_view, use_container_width=True, hide_index=True)
    else:
        st.info("无空值统计")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### 价格异常跳变")
        if report.price_jump_rows.empty:
            st.info("未检测到超阈值跳变")
        else:
            show = report.price_jump_rows.copy()
            show["daily_return"] = show["daily_return"].map(lambda x: f"{x:.2%}")
            st.dataframe(show, use_container_width=True, hide_index=True)

    with col_b:
        st.markdown("#### OHLC 逻辑异常")
        if report.ohlc_violation_rows.empty:
            st.info("OHLC 字段一致")
        else:
            st.dataframe(
                report.ohlc_violation_rows,
                use_container_width=True,
                hide_index=True,
            )

    if report.missing_trading_days > 0:
        st.markdown("#### 缺失交易日（工作日）")
        missing_df = pd.DataFrame({"缺失日期": report.missing_dates})
        st.dataframe(missing_df, use_container_width=True, hide_index=True)
        if report.missing_trading_days > len(report.missing_dates):
            st.caption(
                f"仅展示前 {len(report.missing_dates)} 条，"
                f"共缺失 {report.missing_trading_days} 个工作日"
            )


def _render_backtest_metrics(result, title: str) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("策略累计收益", f"{result.total_return_strategy:.2%}")
    c2.metric("基准累计收益（买入持有）", f"{result.total_return_benchmark:.2%}")
    c3.metric("策略最大回撤", f"{result.max_drawdown_strategy:.2%}")
    c4.metric("调仓次数", str(result.trade_count))

    bt = result.df
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(bt["日期"], bt["Cumulative_Strategy_Return"], label=f"{result.strategy_name} 策略", color="#E63946")
    ax.plot(
        bt["日期"],
        bt["Cumulative_Market_Return"],
        label="市场收益（买入持有）",
        color="#2E86AB",
        linestyle="--",
    )
    ax.axhline(0, color="gray", linewidth=0.8, alpha=0.5)
    ax.set_ylabel("累计收益率")
    ax.set_title(title)
    ax.legend(loc="upper left")
    plt.xticks(rotation=45)
    st.pyplot(fig)


def _render_analysis_tab(
    df: pd.DataFrame,
    rsi_period: int,
    oversold: float,
    overbought: float,
    ma_short: int,
    ma_long: int,
) -> None:
    st.subheader("📋 数据预览")
    st.dataframe(df.tail(20), use_container_width=True)

    st.subheader("📊 价格与 RSI 图表")

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["日期"], df["收盘"], label="收盘价", color="#2E86AB")
    ax.set_ylabel("价格")
    ax.legend(loc="upper left")

    if len(df) > rsi_period:
        rsi = compute_rsi(df["收盘"], rsi_period)
        ax2 = ax.twinx()
        ax2.plot(df["日期"], rsi, label=f"RSI({rsi_period})", color="#E63946", alpha=0.7)
        ax2.axhline(overbought, color="gray", linestyle="--", alpha=0.5)
        ax2.axhline(oversold, color="gray", linestyle="--", alpha=0.5)
        ax2.set_ylabel("RSI")
        ax2.set_ylim(0, 100)
        ax2.legend(loc="upper right")

    plt.xticks(rotation=45)
    st.pyplot(fig)

    st.subheader("📉 RSI 策略回测（对比基准收益）")

    if len(df) < rsi_period + 2:
        st.warning(f"数据不足 {rsi_period + 2} 条，无法回测。请采集更多行情后再试。")
    else:
        try:
            result = run_rsi_backtest(
                df,
                rsi_period=rsi_period,
                oversold=float(oversold),
                overbought=float(overbought),
            )
            bt = result.df

            _render_backtest_metrics(
                result,
                f"RSI({rsi_period}) 策略：<{oversold} 建仓，>{overbought} 平仓",
            )

            st.caption(
                "策略规则：RSI 低于超卖线建仓做多，高于超买线平仓；"
                "策略收益按 T+1 计入。仅供学习演示，不构成投资建议。"
            )

            with st.expander("查看回测明细（最近 20 行）"):
                cols = ["日期", "收盘", "RSI", "position", "daily_return", "strategy_return"]
                st.dataframe(bt[cols].tail(20), use_container_width=True)

        except ValueError as e:
            st.error(str(e))

    st.subheader("📊 价格与双均线")
    if len(df) >= ma_long:
        fig_ma, ax_ma = plt.subplots(figsize=(10, 4))
        ax_ma.plot(df["日期"], df["收盘"], label="收盘价", color="#2E86AB")
        ma_s = compute_sma(df["收盘"], ma_short)
        ma_l = compute_sma(df["收盘"], ma_long)
        ax_ma.plot(df["日期"], ma_s, label=f"MA({ma_short})", color="#E63946", alpha=0.85)
        ax_ma.plot(df["日期"], ma_l, label=f"MA({ma_long})", color="#F4A261", alpha=0.85)
        ax_ma.set_ylabel("价格")
        ax_ma.legend(loc="upper left")
        plt.xticks(rotation=45)
        st.pyplot(fig_ma)
    else:
        st.info(f"数据不足 {ma_long} 条，无法绘制双均线")

    st.subheader("📉 MA 金叉死叉策略回测")
    if len(df) < ma_long + 2:
        st.warning(f"数据不足 {ma_long + 2} 条，无法回测 MA 策略。")
    else:
        try:
            ma_result = run_ma_backtest(df, short_period=ma_short, long_period=ma_long)
            _render_backtest_metrics(
                ma_result,
                f"MA({ma_short}/{ma_long})：短期 > 长期持仓，否则空仓",
            )
            st.caption(
                "策略规则：短期均线上穿长期均线（金叉）后持仓，死叉后空仓；"
                "收益按 T+1 计入。仅供学习演示，不构成投资建议。"
            )
            with st.expander("查看 MA 回测明细（最近 20 行）"):
                cols = ["日期", "收盘", "MA_short", "MA_long", "position", "strategy_return"]
                st.dataframe(ma_result.df[cols].tail(20), use_container_width=True)
        except ValueError as e:
            st.error(str(e))

    st.subheader("📈 基础统计")
    col1, col2, col3 = st.columns(3)
    col1.metric("最新收盘", f"{df['收盘'].iloc[-1]:.2f}")
    col2.metric("最高价", f"{df['收盘'].max():.2f}")
    col3.metric("最低价", f"{df['收盘'].min():.2f}")


st.set_page_config(page_title="股票量化分析", layout="wide")
st.title("📈 股票数据分析与量化回测")

st.sidebar.header("数据设置")
df_raw, source = _load_market_data()

if df_raw.empty:
    st.sidebar.error("未找到数据，请先运行 python pipeline.py --stock-only")
    st.stop()

try:
    df = prepare_ohlc_df(df_raw)
except ValueError as e:
    st.sidebar.error(str(e))
    st.stop()

st.sidebar.success(f"已加载 {len(df)} 条记录")
st.sidebar.caption(f"数据来源：{source}")

st.sidebar.markdown("---")
st.sidebar.header("RSI 参数")
rsi_period = st.sidebar.slider("RSI 周期", 5, 30, 14)
oversold = st.sidebar.slider("超卖阈值（建仓）", 10, 40, 30)
overbought = st.sidebar.slider("超买阈值（平仓）", 60, 90, 70)

st.sidebar.markdown("---")
st.sidebar.header("MA 参数")
ma_short = st.sidebar.slider("短期均线", 3, 15, 5)
ma_long = st.sidebar.slider("长期均线", 10, 60, 20)
if ma_long <= ma_short:
    st.sidebar.warning("长期均线应大于短期均线")

tab_quality, tab_analysis, tab_news = st.tabs(["数据质量监控", "量化分析", "新闻情感"])

with tab_quality:
    _render_quality_tab(df_raw)

with tab_analysis:
    _render_analysis_tab(df, rsi_period, oversold, overbought, ma_short, ma_long)

with tab_news:
    _render_news_sentiment_tab()
