"""
策略回测公共层：数据清洗、收益计算、BaseStrategy 抽象
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

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
    strategy_name: str = ""
    params: Dict[str, Any] = field(default_factory=dict)


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


def max_drawdown(cumulative_return: pd.Series) -> float:
    wealth = 1 + cumulative_return.fillna(0)
    peak = wealth.cummax()
    drawdown = (wealth - peak) / peak.replace(0, np.nan)
    return float(drawdown.min()) if len(drawdown) else 0.0


def run_backtest_engine(
    data: pd.DataFrame,
    position: pd.Series,
    *,
    price_col: str = "收盘",
    strategy_name: str = "",
    params: Optional[Dict[str, Any]] = None,
) -> BacktestResult:
    """
    通用回测引擎：T+1 计入策略收益，基准为买入持有。
    position: 1=持仓, 0=空仓
    """
    out = data.copy()
    close = out[price_col]
    out["position"] = position.astype(float)
    out["daily_return"] = close.pct_change()
    out["strategy_return"] = out["position"].shift(1).fillna(0) * out["daily_return"]
    out["Cumulative_Strategy_Return"] = (1 + out["strategy_return"].fillna(0)).cumprod() - 1
    out["Cumulative_Market_Return"] = (1 + out["daily_return"].fillna(0)).cumprod() - 1

    trade_count = int((out["position"].diff().fillna(0).abs() > 0).sum())

    return BacktestResult(
        df=out,
        total_return_strategy=float(out["Cumulative_Strategy_Return"].iloc[-1]),
        total_return_benchmark=float(out["Cumulative_Market_Return"].iloc[-1]),
        max_drawdown_strategy=max_drawdown(out["Cumulative_Strategy_Return"]),
        max_drawdown_benchmark=max_drawdown(out["Cumulative_Market_Return"]),
        trade_count=trade_count,
        strategy_name=strategy_name,
        params=params or {},
    )


class BaseStrategy(ABC):
    """策略抽象：子类实现信号生成，统一走 run_backtest_engine。"""

    name: str = "base"

    @abstractmethod
    def min_rows(self) -> int:
        ...

    @abstractmethod
    def validate(self) -> None:
        ...

    @abstractmethod
    def build_frame(self, data: pd.DataFrame) -> pd.DataFrame:
        """返回带 position 列及指标列的 DataFrame（与 data 行对齐）。"""
        ...

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

        framed = self.build_frame(clean)
        return run_backtest_engine(
            framed,
            framed["position"],
            price_col=price_col,
            strategy_name=self.name,
            params=self.params_dict(),
        )

    @abstractmethod
    def params_dict(self) -> Dict[str, Any]:
        ...
