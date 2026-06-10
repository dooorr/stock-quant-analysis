"""
股票行情数据质量检测

用于 Pipeline 入库后与 Streamlit 看板展示：
- 空值率
- 重复日期
- 交易日缺口（工作日维度）
- 收盘价异常跳变（日收益率超阈值或 3σ）
- OHLC 逻辑一致性（高 >= 低，收盘落在高低区间内）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

from .backtest_base import prepare_ohlc_df


REQUIRED_COLS = ("日期", "收盘")
OHLC_COLS = ("开盘", "高", "低", "收盘")


@dataclass
class DataQualityReport:
    row_count: int
    date_start: Optional[pd.Timestamp]
    date_end: Optional[pd.Timestamp]
    duplicate_date_count: int
    missing_trading_days: int
    missing_dates: List[pd.Timestamp] = field(default_factory=list)
    null_rates: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_jump_rows: pd.DataFrame = field(default_factory=pd.DataFrame)
    ohlc_violation_rows: pd.DataFrame = field(default_factory=pd.DataFrame)
    issues: List[str] = field(default_factory=list)
    health_score: float = 100.0

    @property
    def is_healthy(self) -> bool:
        return self.health_score >= 80 and not self.issues


def _parse_optional_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in OHLC_COLS:
        if col in out.columns:
            out[col] = pd.to_numeric(
                out[col].astype(str).str.replace(",", "", regex=False),
                errors="coerce",
            )
    return out


def _find_missing_weekdays(dates: pd.Series) -> List[pd.Timestamp]:
    if dates.empty:
        return []
    start = dates.min()
    end = dates.max()
    expected = pd.bdate_range(start=start, end=end)
    actual = pd.DatetimeIndex(dates.dt.normalize().unique())
    missing = expected.difference(actual)
    return list(missing)


def _find_price_jumps(
    df: pd.DataFrame,
    *,
    price_col: str = "收盘",
    jump_threshold: float = 0.08,
    sigma_k: float = 3.0,
) -> pd.DataFrame:
    if len(df) < 2:
        return pd.DataFrame()

    daily_ret = df[price_col].pct_change()
    ret_std = daily_ret.std()
    # 波动极小时不用 σ 规则，避免平滑序列被误报为跳变
    if pd.notna(ret_std) and ret_std > 1e-4:
        sigma_limit = sigma_k * ret_std
    else:
        sigma_limit = np.inf

    flagged = df.loc[
        daily_ret.abs().gt(jump_threshold) | daily_ret.abs().gt(sigma_limit)
    ].copy()
    if flagged.empty:
        return pd.DataFrame()

    flagged["daily_return"] = daily_ret.loc[flagged.index]
    flagged["jump_reason"] = np.where(
        daily_ret.loc[flagged.index].abs().gt(jump_threshold),
        f"|日收益率| > {jump_threshold:.0%}",
        f"|日收益率| > {sigma_k}σ",
    )
    cols = ["日期", price_col, "daily_return", "jump_reason"]
    return flagged[cols].reset_index(drop=True)


def _find_ohlc_violations(df: pd.DataFrame) -> pd.DataFrame:
    needed = [c for c in OHLC_COLS if c in df.columns]
    if len(needed) < 4:
        return pd.DataFrame()

    high = df["高"]
    low = df["低"]
    close = df["收盘"]
    open_ = df["开盘"]

    bad = (
        (high < low)
        | (close > high)
        | (close < low)
        | (open_ > high)
        | (open_ < low)
    )
    if not bad.any():
        return pd.DataFrame()

    out = df.loc[bad, ["日期", "开盘", "高", "低", "收盘"]].copy()
    out["violation"] = "OHLC 逻辑不一致"
    return out.reset_index(drop=True)


def run_data_quality_check(
    df: pd.DataFrame,
    *,
    price_col: str = "收盘",
    date_col: str = "日期",
    jump_threshold: float = 0.08,
    sigma_k: float = 3.0,
    max_missing_dates_list: int = 30,
) -> DataQualityReport:
    """
    对原始或 SQLite 读出的 DataFrame 做质量检测。

    jump_threshold: 日收益率绝对值超过该比例视为异常跳变（默认 8%）
    sigma_k: 同时用收益率标准差的 k 倍作为动态阈值
    """
    issues: List[str] = []
    score = 100.0

    if df is None or df.empty:
        return DataQualityReport(
            row_count=0,
            date_start=None,
            date_end=None,
            duplicate_date_count=0,
            missing_trading_days=0,
            issues=["数据为空"],
            health_score=0.0,
        )

    try:
        clean = prepare_ohlc_df(df, price_col=price_col, date_col=date_col)
    except ValueError as exc:
        return DataQualityReport(
            row_count=len(df),
            date_start=None,
            date_end=None,
            duplicate_date_count=0,
            missing_trading_days=0,
            issues=[str(exc)],
            health_score=0.0,
        )

    clean = _parse_optional_ohlc(clean)
    row_count = len(clean)
    date_start = clean[date_col].min()
    date_end = clean[date_col].max()

    dup_count = int(clean[date_col].duplicated().sum())
    if dup_count:
        issues.append(f"存在 {dup_count} 条重复日期")
        score -= min(25, dup_count * 5)

    missing_all = _find_missing_weekdays(clean[date_col])
    missing_count = len(missing_all)
    if missing_count:
        issues.append(f"交易日缺口 {missing_count} 天（按工作日计）")
        score -= min(30, missing_count * 2)

    null_rows = []
    for col in clean.columns:
        if col == "updated_at":
            continue
        n_null = int(clean[col].isna().sum())
        null_rows.append(
            {
                "列名": col,
                "空值数": n_null,
                "空值率": n_null / row_count if row_count else 0.0,
            }
        )
    null_rates = pd.DataFrame(null_rows)
    critical_null = null_rates[null_rates["列名"].isin(REQUIRED_COLS)]
    if not critical_null.empty and critical_null["空值数"].sum() > 0:
        issues.append("关键列（日期/收盘）存在空值")
        score -= 20

    price_jumps = _find_price_jumps(
        clean,
        price_col=price_col,
        jump_threshold=jump_threshold,
        sigma_k=sigma_k,
    )
    if not price_jumps.empty:
        issues.append(f"检测到 {len(price_jumps)} 条价格异常跳变")
        score -= min(20, len(price_jumps) * 3)

    ohlc_bad = _find_ohlc_violations(clean)
    if not ohlc_bad.empty:
        issues.append(f"检测到 {len(ohlc_bad)} 条 OHLC 逻辑异常")
        score -= min(20, len(ohlc_bad) * 5)

    zero_neg = int((clean[price_col] <= 0).sum())
    if zero_neg:
        issues.append(f"收盘价 <= 0 的记录 {zero_neg} 条")
        score -= 15

    score = max(0.0, min(100.0, score))

    return DataQualityReport(
        row_count=row_count,
        date_start=date_start,
        date_end=date_end,
        duplicate_date_count=dup_count,
        missing_trading_days=missing_count,
        missing_dates=missing_all[:max_missing_dates_list],
        null_rates=null_rates,
        price_jump_rows=price_jumps,
        ohlc_violation_rows=ohlc_bad,
        issues=issues,
        health_score=score,
    )


def quality_report_to_dict(report: DataQualityReport) -> Dict[str, Any]:
    """将报告序列化为可 JSON 保存的 dict。"""
    def _ts(v: Optional[pd.Timestamp]) -> Optional[str]:
        if v is None or pd.isna(v):
            return None
        return pd.Timestamp(v).strftime("%Y-%m-%d")

    return {
        "health_score": round(report.health_score, 1),
        "is_healthy": report.is_healthy,
        "row_count": report.row_count,
        "date_start": _ts(report.date_start),
        "date_end": _ts(report.date_end),
        "duplicate_date_count": report.duplicate_date_count,
        "missing_trading_days": report.missing_trading_days,
        "missing_dates": [_ts(d) for d in report.missing_dates],
        "price_jump_count": len(report.price_jump_rows),
        "ohlc_violation_count": len(report.ohlc_violation_rows),
        "issues": list(report.issues),
        "null_rates": report.null_rates.to_dict(orient="records") if not report.null_rates.empty else [],
    }


def log_data_quality_report(report: DataQualityReport) -> None:
    """通过 loguru 输出数据质量摘要（供 Pipeline / CI 日志查看）。"""
    summary = (
        f"数据质量检测 | 评分={report.health_score:.0f} | "
        f"记录={report.row_count} | 重复日期={report.duplicate_date_count} | "
        f"交易日缺口={report.missing_trading_days} | "
        f"异常跳变={len(report.price_jump_rows)} | "
        f"OHLC异常={len(report.ohlc_violation_rows)}"
    )
    if report.date_start is not None and report.date_end is not None:
        summary += f" | 区间={report.date_start.date()}~{report.date_end.date()}"

    if report.is_healthy:
        logger.success(summary)
    elif report.health_score >= 60:
        logger.warning(summary)
    else:
        logger.error(summary)

    if report.issues:
        for issue in report.issues:
            logger.warning(f"  [数据质量] {issue}")
    else:
        logger.info("  [数据质量] 未发现明显问题")


def save_quality_report_json(
    report: DataQualityReport,
    path: Path,
) -> Path:
    """将质量报告写入 JSON 文件（随 data/ 目录一并归档）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = quality_report_to_dict(report)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"数据质量报告已保存 → {path}")
    return path
