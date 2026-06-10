"""Pipeline 数据质量门禁单元测试"""

import json
from pathlib import Path

import pandas as pd

from pipeline import run_stock_data_quality_gate
from src.analysis.data_quality import (
    log_data_quality_report,
    quality_report_to_dict,
    run_data_quality_check,
    save_quality_report_json,
)
from src.data.storage import save_stock_data_incremental


def _sample_df(n: int = 25) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=n)
    close = pd.Series([3000 + i * 2 for i in range(n)], dtype=float)
    return pd.DataFrame(
        {
            "日期": dates.strftime("%Y-%m-%d"),
            "收盘": close,
            "开盘": close - 1,
            "高": close + 2,
            "低": close - 3,
        }
    )


class TestQualityReportPersistence:
    def test_save_json_roundtrip(self, tmp_path: Path):
        report = run_data_quality_check(_sample_df())
        out = save_quality_report_json(report, tmp_path / "quality_report.json")
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "health_score" in data
        assert data["row_count"] == 25

    def test_quality_report_to_dict(self):
        report = run_data_quality_check(_sample_df())
        d = quality_report_to_dict(report)
        assert d["is_healthy"] is True
        assert isinstance(d["issues"], list)


class TestPipelineQualityGate:
    def test_gate_logs_and_writes_report(self, tmp_path: Path):
        df = _sample_df()
        db_path = tmp_path / "stock_data.db"
        save_stock_data_incremental(df, db_path=db_path)

        run_stock_data_quality_gate(tmp_path, db_path=db_path)

        report_file = tmp_path / "quality_report.json"
        assert report_file.exists()
        payload = json.loads(report_file.read_text(encoding="utf-8"))
        assert payload["row_count"] == 25

    def test_log_data_quality_report_no_raise(self):
        report = run_data_quality_check(_sample_df())
        log_data_quality_report(report)
