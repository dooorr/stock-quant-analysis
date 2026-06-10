"""
双均线金叉死叉策略回测

规则（趋势跟踪）：
- 短期 MA > 长期 MA → 持仓做多
- 短期 MA <= 长期 MA → 空仓
- 收益按 T+1 计入
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import pandas as pd

from .backtest_base import BacktestResult, BaseStrategy, prepare_ohlc_df


def compute_sma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(window=period, min_periods=period).mean()


@dataclass
class MaCrossStrategy(BaseStrategy):
    short_period: int = 5
    long_period: int = 20

    name: str = "MA Cross"

    def validate(self) -> None:
        if self.short_period < 2:
            raise ValueError("short_period 至少为 2")
        if self.long_period <= self.short_period:
            raise ValueError("long_period 必须大于 short_period")

    def min_rows(self) -> int:
        return self.long_period + 2

    def params_dict(self) -> Dict[str, Any]:
        return {
            "short_period": self.short_period,
            "long_period": self.long_period,
        }

    def build_frame(self, data: pd.DataFrame, price_col: str = "收盘") -> pd.DataFrame:
        out = data.copy()
        close = out[price_col]
        out["MA_short"] = compute_sma(close, self.short_period)
        out["MA_long"] = compute_sma(close, self.long_period)
        out["position"] = (out["MA_short"] > out["MA_long"]).astype(float)
        # MA 未就绪前保持空仓
        out.loc[out["MA_long"].isna(), "position"] = 0.0
        return out

    def run(
        self,
        df: pd.DataFrame,
        *,
        price_col: str = "收盘",
        date_col: str = "日期",
    ) -> BacktestResult:
        self.validate()
        clean = prepare_ohlc_df(df, price_col=price_col, date_col=date_col)
        if len(clean) < self.min_rows():
            raise ValueError(f"数据不足，至少需要 {self.min_rows()} 条有效记录")

        framed = self.build_frame(clean, price_col=price_col)
        from .backtest_base import run_backtest_engine

        return run_backtest_engine(
            framed,
            framed["position"],
            price_col=price_col,
            strategy_name=self.name,
            params=self.params_dict(),
        )


def run_ma_backtest(
    df: pd.DataFrame,
    *,
    price_col: str = "收盘",
    date_col: str = "日期",
    short_period: int = 5,
    long_period: int = 20,
) -> BacktestResult:
    """便捷入口：运行双均线策略回测。"""
    return MaCrossStrategy(short_period=short_period, long_period=long_period).run(
        df,
        price_col=price_col,
        date_col=date_col,
    )
