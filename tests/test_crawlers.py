"""
Crawler 模块单元测试

使用 unittest.mock 模拟网络请求，避免真实 HTTP 调用。
"""

import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path

from crawler.shanghai_index import (
    fetch_shanghai_index,
    fetch_shanghai_index_eastmoney,
    fetch_shanghai_index_requests,
    fetch_shanghai_index_sina,
)
from crawler.news_crawler import NewsCrawler, NewsItem


class TestShanghaiIndexCrawler:
    """上证指数采集器测试"""

    @patch("crawler.shanghai_index.pd.read_html")
    @patch("crawler.shanghai_index.requests.get")
    def test_fetch_success(self, mock_get, mock_read_html):
        """正常情况：返回有效表格数据"""
        # Mock the network response
        html = "<html><body><table><tr><th>日期</th><th>收盘</th></tr><tr><td>2024-01-01</td><td>3000.00</td></tr></table></body></html>"
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        # Mock pandas.read_html to return a predictable DataFrame (avoids environment-specific parsing quirks)
        import pandas as pd
        expected_df = pd.DataFrame({"日期": ["2024-01-01"], "收盘": [3000.00]})
        mock_read_html.return_value = [expected_df]

        df = fetch_shanghai_index_requests()
        assert not df.empty
        assert "日期" in df.columns

    @patch("crawler.shanghai_index.requests.get")
    def test_fetch_no_table(self, mock_get):
        """异常情况：页面无表格"""
        mock_resp = MagicMock()
        mock_resp.text = "<html><body>no table</body></html>"
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        df = fetch_shanghai_index_requests()
        assert df.empty

    @patch("crawler.shanghai_index.requests.get", side_effect=Exception("timeout"))
    def test_fetch_retry_exhausted(self, mock_get):
        """重试耗尽后返回空 DataFrame"""
        df = fetch_shanghai_index_requests(max_retries=2)
        assert df.empty

    @patch("crawler.shanghai_index._request_with_retry")
    def test_eastmoney_parses_klines(self, mock_request):
        """东方财富 JSON 解析"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "klines": [
                    "2024-01-02,2962.28,2968.27,2997.13,2962.28,100,200,1.2,0.35,10,0.5",
                    "2024-01-03,2968.27,2970.00,2980.00,2960.00,110,210,1.1,-0.20,-6,0.4",
                ]
            }
        }
        mock_request.return_value = mock_resp

        df = fetch_shanghai_index_eastmoney(lmt=100)
        assert len(df) == 2
        assert {"日期", "收盘", "开盘", "高", "低"}.issubset(df.columns)
        assert df.iloc[0]["日期"] == "2024-01-03"  # 最新在前

    @patch("crawler.shanghai_index._request_with_retry")
    def test_sina_parses_json(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"day": "2024-01-02", "open": "2962.28", "high": "2997.13", "low": "2962.28", "close": "2968.27", "volume": "100"},
            {"day": "2024-01-03", "open": "2968.27", "high": "2980.00", "low": "2960.00", "close": "2970.00", "volume": "110"},
        ]
        mock_request.return_value = mock_resp

        df = fetch_shanghai_index_sina(datalen=100)
        assert len(df) == 2
        assert df.iloc[0]["日期"] == "2024-01-03"

    @patch("crawler.shanghai_index.fetch_shanghai_index_investing_ajax")
    @patch("crawler.shanghai_index.fetch_shanghai_index_eastmoney")
    def test_fetch_auto_prefers_eastmoney(self, mock_em, mock_inv):
        """auto 模式优先东方财富"""
        mock_em.return_value = pd.DataFrame(
            {"日期": ["2024-01-01"], "收盘": [3000.0], "开盘": [2990.0], "高": [3010.0], "低": [2980.0]}
        )
        df = fetch_shanghai_index(lmt=500, source="auto")
        assert len(df) == 1
        mock_em.assert_called_once()
        mock_inv.assert_not_called()

    @patch("crawler.shanghai_index.fetch_shanghai_index_sina")
    @patch("crawler.shanghai_index.fetch_shanghai_index_eastmoney")
    def test_fetch_fallback_to_sina(self, mock_em, mock_sina):
        """东方财富失败时回退新浪"""
        mock_em.return_value = pd.DataFrame()
        mock_sina.return_value = pd.DataFrame(
            {"日期": ["2024-01-01", "2024-01-02"], "收盘": [3000.0, 3010.0]}
        )
        df = fetch_shanghai_index(lmt=100, source="auto")
        assert len(df) == 2
        mock_sina.assert_called_once()


class TestNewsCrawler:
    """新闻采集器测试（使用 mock 避免真实登录）"""

    def test_news_item_dataclass(self):
        """NewsItem 数据类基本功能"""
        item = NewsItem(title="测试标题", url="http://example.com", source="sina")
        assert item.title == "测试标题"
        assert item.source == "sina"

    @patch.object(NewsCrawler, "login_all")
    @patch.object(NewsCrawler, "fetch_news")
    def test_fetch_news_mock(self, mock_fetch, mock_login):
        """模拟 fetch_news 返回"""
        mock_fetch.return_value = [
            NewsItem(title="新闻1", url="u1", source="sina"),
            NewsItem(title="新闻2", url="u2", source="sina"),
        ]

        crawler = NewsCrawler(headless=True)
        items = crawler.fetch_news("sina", limit=2)
        crawler.close()

        assert len(items) == 2
        assert items[0].title == "新闻1"
