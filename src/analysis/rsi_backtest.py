"""
RSI 超买超卖策略回测（pandas 向量化 + 简单状态机持仓）

策略规则：
- RSI < oversold（默认 30）→ 建仓做多
- RSI > overbought（默认 70）→ 平仓
- 收益按 T+1 计入（当日收盘信号，次日涨跌计入策略收益）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import numpy as np
import pandas as pd

from .backtest_base import BacktestResult, BaseStrategy, prepare_ohlc_df


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder 平滑 RSI（rolling mean 版本）。"""
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


@dataclass
class RsiStrategy(BaseStrategy):
    rsi_period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0

    name: str = "RSI"

    def validate(self) -> None:
        if self.rsi_period < 2:
            raise ValueError("rsi_period 至少为 2")
        if not (0 < self.oversold < self.overbought < 100):
            raise ValueError("需满足 0 < oversold < overbought < 100")

    def min_rows(self) -> int:
        return self.rsi_period + 2

    def params_dict(self) -> Dict[str, Any]:
        return {
            "rsi_period": self.rsi_period,
            "oversold": self.oversold,
            "overbought": self.overbought,
        }

    def build_frame(self, data: pd.DataFrame, price_col: str = "收盘") -> pd.DataFrame:
        out = data.copy()
        close = out[price_col]
        out["RSI"] = compute_rsi(close, self.rsi_period)
        out["position"] = _position_from_rsi(out["RSI"], self.oversold, self.overbought)
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


def run_rsi_backtest(
    df: pd.DataFrame,
    *,
    price_col: str = "收盘",
    date_col: str = "日期",
    rsi_period: int = 14,
    oversold: float = 30.0,
    overbought: float = 70.0,
) -> BacktestResult:
    """便捷入口：运行 RSI 策略回测。"""
    return RsiStrategy(
        rsi_period=rsi_period,
        oversold=oversold,
        overbought=overbought,
    ).run(df, price_col=price_col, date_col=date_col)
