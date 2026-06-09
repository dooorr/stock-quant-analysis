"""
股票数据可视化与分析 - Streamlit 升级版

功能：
- 从 SQLite / CSV 加载上证指数数据
- 价格 + RSI 图表
- RSI 超买超卖策略回测，对比买入持有基准收益
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

from src.analysis.rsi_backtest import compute_rsi, prepare_ohlc_df, run_rsi_backtest
from src.data.storage import DEFAULT_DB_PATH, load_stock_data


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


st.set_page_config(page_title="股票量化分析", layout="wide")
st.title("📈 股票数据分析与量化回测（升级版）")

# ------------------------------
# 侧边栏
# ------------------------------
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

# ------------------------------
# 数据预览
# ------------------------------
st.subheader("📋 数据预览")
st.dataframe(df.tail(20), use_container_width=True)

# ------------------------------
# 价格与 RSI
# ------------------------------
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

# ------------------------------
# RSI 策略回测
# ------------------------------
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

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("策略累计收益", f"{result.total_return_strategy:.2%}")
        c2.metric("基准累计收益（买入持有）", f"{result.total_return_benchmark:.2%}")
        c3.metric("策略最大回撤", f"{result.max_drawdown_strategy:.2%}")
        c4.metric("调仓次数", str(result.trade_count))

        fig2, ax_bt = plt.subplots(figsize=(10, 4))
        ax_bt.plot(
            bt["日期"],
            bt["Cumulative_Strategy_Return"],
            label="RSI 策略收益",
            color="#E63946",
        )
        ax_bt.plot(
            bt["日期"],
            bt["Cumulative_Market_Return"],
            label="市场收益（买入持有）",
            color="#2E86AB",
            linestyle="--",
        )
        ax_bt.axhline(0, color="gray", linewidth=0.8, alpha=0.5)
        ax_bt.set_ylabel("累计收益率")
        ax_bt.set_title(
            f"RSI({rsi_period}) 策略：<{oversold} 建仓，>{overbought} 平仓"
        )
        ax_bt.legend(loc="upper left")
        plt.xticks(rotation=45)
        st.pyplot(fig2)

        st.caption(
            "策略规则：RSI 低于超卖线建仓做多，高于超买线平仓；"
            "策略收益按 T+1 计入。仅供学习演示，不构成投资建议。"
        )

        with st.expander("查看回测明细（最近 20 行）"):
            cols = ["日期", "收盘", "RSI", "position", "daily_return", "strategy_return"]
            st.dataframe(bt[cols].tail(20), use_container_width=True)

    except ValueError as e:
        st.error(str(e))

# ------------------------------
# 基础统计
# ------------------------------
st.subheader("📈 基础统计")
col1, col2, col3 = st.columns(3)
col1.metric("最新收盘", f"{df['收盘'].iloc[-1]:.2f}")
col2.metric("最高价", f"{df['收盘'].max():.2f}")
col3.metric("最低价", f"{df['收盘'].min():.2f}")
