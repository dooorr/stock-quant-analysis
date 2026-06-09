"""
RSI 超买超卖策略回测（pandas 向量化 + 简单状态机持仓）

策略规则：
- RSI < oversold（默认 30）→ 建仓做多
- RSI > overbought（默认 70）→ 平仓
- 收益按 T+1 计入（当日收盘信号，次日涨跌计入策略收益）
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
  df: pd.DataFrame
  total_return_strategy: float
  total_return_benchmark: float
  max_drawdown_strategy: float
  max_drawdown_benchmark: float
  trade_count: int
  rsi_period: int
  oversold: float
  overbought: float


def prepare_ohlc_df(
  df: pd.DataFrame,
  *,
  price_col: str = "收盘",
  date_col: str = "日期",
) -> pd.DataFrame:
  """清洗日期与收盘价，按时间升序排列。"""
  if df is None or df.empty:
    raise ValueError("数据为空")

  out = df.copy()
  out.columns = [str(c).strip() for c in out.columns]

  if date_col not in out.columns or price_col not in out.columns:
    raise ValueError(f"缺少必要列：{date_col}、{price_col}")

  out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
  out[price_col] = pd.to_numeric(
    out[price_col].astype(str).str.replace(",", "", regex=False),
    errors="coerce",
  )

  out = out.dropna(subset=[date_col, price_col]).sort_values(date_col)
  return out.reset_index(drop=True)


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
  """Wilder 平滑 RSI（与 Streamlit 原图一致：rolling mean 版本）。"""
  delta = close.diff()
  gain = delta.where(delta > 0, 0.0).rolling(window=period, min_periods=period).mean()
  loss = (-delta.where(delta < 0, 0.0)).rolling(window=period, min_periods=period).mean()
  rs = gain / loss
  return 100 - (100 / (1 + rs))


def _position_from_rsi(rsi: pd.Series, oversold: float, overbought: float) -> pd.Series:
  """RSI 下穿超卖区建仓，上穿超买区平仓。"""
  position = np.zeros(len(rsi), dtype=float)
  holding = 0.0
  for i, val in enumerate(rsi):
    if pd.isna(val):
      position[i] = holding
      continue
    if val < oversold:
      holding = 1.0
    elif val > overbought:
      holding = 0.0
    position[i] = holding
  return pd.Series(position, index=rsi.index)


def _max_drawdown(cumulative_return: pd.Series) -> float:
  wealth = 1 + cumulative_return.fillna(0)
  peak = wealth.cummax()
  drawdown = (wealth - peak) / peak.replace(0, np.nan)
  return float(drawdown.min()) if len(drawdown) else 0.0


def run_rsi_backtest(
  df: pd.DataFrame,
  *,
  price_col: str = "收盘",
  date_col: str = "日期",
  rsi_period: int = 14,
  oversold: float = 30.0,
  overbought: float = 70.0,
) -> BacktestResult:
  """
  运行 RSI 策略回测，返回带累计收益列的 DataFrame 与摘要指标。

  基准收益：买入并持有（全仓持有标的）。
  """
  if rsi_period < 2:
    raise ValueError("rsi_period 至少为 2")
  if not (0 < oversold < overbought < 100):
    raise ValueError("需满足 0 < oversold < overbought < 100")

  data = prepare_ohlc_df(df, price_col=price_col, date_col=date_col)
  min_rows = rsi_period + 2
  if len(data) < min_rows:
    raise ValueError(f"数据不足，至少需要 {min_rows} 条有效记录")

  close = data[price_col]
  data = data.copy()
  data["RSI"] = compute_rsi(close, rsi_period)
  data["position"] = _position_from_rsi(data["RSI"], oversold, overbought)
  data["daily_return"] = close.pct_change()
  data["strategy_return"] = data["position"].shift(1).fillna(0) * data["daily_return"]
  data["Cumulative_Strategy_Return"] = (1 + data["strategy_return"].fillna(0)).cumprod() - 1
  data["Cumulative_Market_Return"] = (1 + data["daily_return"].fillna(0)).cumprod() - 1

  trade_count = int((data["position"].diff().fillna(0).abs() > 0).sum())

  return BacktestResult(
    df=data,
    total_return_strategy=float(data["Cumulative_Strategy_Return"].iloc[-1]),
    total_return_benchmark=float(data["Cumulative_Market_Return"].iloc[-1]),
    max_drawdown_strategy=_max_drawdown(data["Cumulative_Strategy_Return"]),
    max_drawdown_benchmark=_max_drawdown(data["Cumulative_Market_Return"]),
    trade_count=trade_count,
    rsi_period=rsi_period,
    oversold=oversold,
    overbought=overbought,
  )
