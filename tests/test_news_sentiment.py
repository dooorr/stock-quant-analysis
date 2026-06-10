"""新闻情感分析单元测试"""

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from crawler.news_fetcher import fetch_sina_finance_news
from src.analysis.news_sentiment import (
    LABEL_NEGATIVE,
    LABEL_POSITIVE,
    analyze_news_records,
    label_sentiment,
    score_text,
    summarize_sentiment,
)


class TestScoreText:
    def test_positive_title(self):
        assert score_text("沪指大涨突破3000点，市场情绪回暖") > 0

    def test_negative_title(self):
        assert score_text("地产股暴跌，多家公司亏损预警") < 0

    def test_neutral_title(self):
        assert score_text("今日市场窄幅震荡") == 0.0

    def test_empty(self):
        assert score_text("") == 0.0


class TestLabelSentiment:
    def test_labels(self):
        assert label_sentiment(0.5) == LABEL_POSITIVE
        assert label_sentiment(-0.5) == LABEL_NEGATIVE
        assert label_sentiment(0.0) == "中性"


class TestAnalyzeNewsRecords:
    def test_dataframe_columns(self):
        records = [
            {"title": "央行降准利好股市", "url": "http://a", "publish_time": "2024-01-01"},
            {"title": "某公司被立案调查", "url": "http://b", "publish_time": "2024-01-02"},
        ]
        df = analyze_news_records(records)
        assert len(df) == 2
        assert "sentiment_score" in df.columns
        assert df.iloc[0]["sentiment_label"] == LABEL_POSITIVE
        assert df.iloc[1]["sentiment_label"] == LABEL_NEGATIVE

    def test_summary(self):
        df = analyze_news_records([{"title": "大涨"}, {"title": "大跌"}])
        s = summarize_sentiment(df)
        assert s.total == 2
        assert s.positive + s.negative + s.neutral == 2


class TestNewsFetcher:
    @patch("crawler.news_fetcher.requests.get")
    def test_fetch_sina_parses_json(self, mock_get):
        payload = {
            "result": {
                "data": [
                    {"title": "测试利好上涨", "url": "http://x", "ctime": "2024-06-01 10:00:00"},
                ]
            }
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        items = fetch_sina_finance_news(limit=5)
        assert len(items) == 1
        assert items[0].title == "测试利好上涨"
        assert items[0].source == "sina_roll"
