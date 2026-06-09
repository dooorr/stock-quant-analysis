"""RSI 回测模块单元测试"""

import pandas as pd
import pytest

from src.analysis.rsi_backtest import compute_rsi, prepare_ohlc_df, run_rsi_backtest


def _make_uptrend(n: int = 40) -> pd.DataFrame:
  dates = pd.date_range("2024-01-01", periods=n, freq="D")
  close = pd.Series(range(100, 100 + n), dtype=float)
  return pd.DataFrame({"日期": dates, "收盘": close})


class TestPrepareOhlcDf:
  def test_parses_comma_prices(self):
    df = pd.DataFrame({"日期": ["2024-01-01", "2024-01-02"], "收盘": ["3,240.94", "3,160.75"]})
    out = prepare_ohlc_df(df)
    assert out["收盘"].tolist() == [3240.94, 3160.75]

  def test_sorts_ascending(self):
    df = pd.DataFrame({"日期": ["2024-01-03", "2024-01-01"], "收盘": [102.0, 100.0]})
    out = prepare_ohlc_df(df)
    assert out["日期"].iloc[0] == pd.Timestamp("2024-01-01")


class TestComputeRsi:
  def test_rsi_in_range(self):
    close = pd.Series([44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
                       45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64])
    rsi = compute_rsi(close, period=14).dropna()
    assert not rsi.empty
    assert rsi.between(0, 100).all()


class TestRunRsiBacktest:
  def test_returns_metrics(self):
    result = run_rsi_backtest(_make_uptrend(50), rsi_period=14)
    assert "Cumulative_Strategy_Return" in result.df.columns
    assert "Cumulative_Market_Return" in result.df.columns
    assert result.total_return_benchmark > 0
    assert result.trade_count >= 0

  def test_insufficient_data_raises(self):
    with pytest.raises(ValueError, match="数据不足"):
      run_rsi_backtest(_make_uptrend(10), rsi_period=14)

  def test_invalid_thresholds(self):
    with pytest.raises(ValueError, match="oversold"):
      run_rsi_backtest(_make_uptrend(50), oversold=80, overbought=70)
