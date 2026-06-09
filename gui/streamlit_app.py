"""
股票数据可视化与分析 - Streamlit 升级版

现代 Web 界面，替代原版 Tkinter GUI。
功能：
- 加载本地 CSV 数据
- 查看数据表格
- 价格 + RSI 图表
- 简单参数调节
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

st.set_page_config(page_title="股票量化分析", layout="wide")
st.title("📈 股票数据分析与可视化（升级版）")

# ------------------------------
# 侧边栏 - 数据加载
# ------------------------------
st.sidebar.header("数据设置")

data_path = st.sidebar.text_input(
    "数据文件路径",
    value="../stock_data.csv",
    help="相对于本文件的路径，或使用绝对路径"
)

if not Path(data_path).exists():
    st.sidebar.error("文件不存在，请检查路径")
    st.stop()

df = pd.read_csv(data_path)
st.sidebar.success(f"已加载 {len(df)} 条记录")

# 日期列处理（原版可能是中文列名）
if "日期" in df.columns:
    df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
    df = df.sort_values("日期")

st.sidebar.markdown("---")
st.sidebar.caption("原版数据来源：investing.com（上证指数）")

# ------------------------------
# 主界面 - 数据预览
# ------------------------------
st.subheader("📋 数据预览")
st.dataframe(df.head(20), use_container_width=True)

# ------------------------------
# 图表区域
# ------------------------------
st.subheader("📊 价格与 RSI 图表")

col1, col2 = st.columns([3, 1])

with col2:
    rsi_period = st.slider("RSI 周期", 5, 30, 14)
    show_volume = st.checkbox("显示成交量", value=True)

with col1:
    fig, ax = plt.subplots(figsize=(10, 4))

    # 收盘价
    if "收盘" in df.columns:
        ax.plot(df["日期"], df["收盘"], label="收盘价", color="#2E86AB")
        ax.set_ylabel("价格")
        ax.legend(loc="upper left")

    # 简单 RSI 计算（演示用）
    if "收盘" in df.columns and len(df) > rsi_period:
        delta = df["收盘"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        ax2 = ax.twinx()
        ax2.plot(df["日期"], rsi, label=f"RSI({rsi_period})", color="#E63946", alpha=0.7)
        ax2.axhline(70, color="gray", linestyle="--", alpha=0.5)
        ax2.axhline(30, color="gray", linestyle="--", alpha=0.5)
        ax2.set_ylabel("RSI")
        ax2.set_ylim(0, 100)
        ax2.legend(loc="upper right")

    plt.xticks(rotation=45)
    st.pyplot(fig)

# ------------------------------
# 简单统计
# ------------------------------
st.subheader("📈 基础统计")

if "收盘" in df.columns:
    col1, col2, col3 = st.columns(3)
    col1.metric("最新收盘", f"{df['收盘'].iloc[-1]:.2f}")
    col2.metric("最高价", f"{df['收盘'].max():.2f}")
    col3.metric("最低价", f"{df['收盘'].min():.2f}")

st.caption("提示：此界面为升级版 Streamlit 实现，保留原版核心功能并提供更现代的交互体验。")