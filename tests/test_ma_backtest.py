"""MA 金叉死叉策略回测单元测试"""

import pandas as pd
import pytest

from src.analysis.ma_backtest import MaCrossStrategy, compute_sma, run_ma_backtest


def _make_uptrend(n: int = 60) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = pd.Series(range(100, 100 + n), dtype=float)
    return pd.DataFrame({"日期": dates, "收盘": close})


class TestComputeSma:
    def test_sma_length(self):
        close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        sma = compute_sma(close, 3)
        assert pd.isna(sma.iloc[1])
        assert sma.iloc[2] == pytest.approx(2.0)


class TestMaCrossStrategy:
    def test_uptrend_mostly_long(self):
        result = run_ma_backtest(_make_uptrend(60), short_period=5, long_period=20)
        assert result.strategy_name == "MA Cross"
        assert result.params["short_period"] == 5
        assert result.total_return_benchmark > 0
        assert "MA_short" in result.df.columns
        assert "MA_long" in result.df.columns
        # 持续上涨趋势，后半段应大多持仓
        tail_pos = result.df["position"].tail(20)
        assert tail_pos.mean() > 0.5

    def test_insufficient_data_raises(self):
        with pytest.raises(ValueError, match="数据不足"):
            run_ma_backtest(_make_uptrend(15), short_period=5, long_period=20)

    def test_invalid_periods(self):
        with pytest.raises(ValueError, match="long_period"):
            MaCrossStrategy(short_period=20, long_period=10).validate()

    def test_death_cross_flattens_position(self):
        # 先涨后跌，制造金叉/死叉切换
        close = list(range(100, 125)) + list(range(124, 104, -1))
        dates = pd.date_range("2024-01-01", periods=len(close), freq="D")
        df = pd.DataFrame({"日期": dates, "收盘": close})
        result = run_ma_backtest(df, short_period=3, long_period=8)
        assert result.trade_count >= 1
