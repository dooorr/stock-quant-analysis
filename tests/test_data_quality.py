"""数据质量检测模块单元测试"""

import pandas as pd
import pytest

from src.analysis.data_quality import run_data_quality_check


def _base_df() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=20)
    close = pd.Series([3000 + i * 5 for i in range(20)], dtype=float)
    return pd.DataFrame(
        {
            "日期": dates,
            "收盘": close,
            "开盘": close - 2,
            "高": close + 3,
            "低": close - 5,
        }
    )


class TestRunDataQualityCheck:
    def test_healthy_data_high_score(self):
        report = run_data_quality_check(_base_df())
        assert report.row_count == 20
        assert report.health_score >= 80
        assert report.duplicate_date_count == 0
        assert report.missing_trading_days == 0

    def test_empty_data(self):
        report = run_data_quality_check(pd.DataFrame())
        assert report.health_score == 0
        assert "数据为空" in report.issues

    def test_duplicate_dates(self):
        df = _base_df()
        dup = df.iloc[[0]].copy()
        df = pd.concat([df, dup], ignore_index=True)
        report = run_data_quality_check(df)
        assert report.duplicate_date_count == 1
        assert report.health_score < 100

    def test_detects_price_jump(self):
        df = _base_df()
        df.loc[5, "收盘"] = df.loc[4, "收盘"] * 1.2
        report = run_data_quality_check(df, jump_threshold=0.05)
        assert not report.price_jump_rows.empty
        assert any("跳变" in i for i in report.issues)

    def test_ohlc_violation(self):
        df = _base_df()
        df.loc[3, "高"] = df.loc[3, "低"] - 1
        report = run_data_quality_check(df)
        assert not report.ohlc_violation_rows.empty

    def test_missing_weekday_gap(self):
        df = _base_df()
        df = df.drop(index=5).reset_index(drop=True)
        report = run_data_quality_check(df)
        assert report.missing_trading_days >= 1

    def test_parses_comma_prices(self):
        df = pd.DataFrame(
            {
                "日期": ["2024-01-02", "2024-01-03"],
                "收盘": ["3,240.94", "3,160.75"],
            }
        )
        report = run_data_quality_check(df)
        assert report.row_count == 2
        assert report.health_score > 0
