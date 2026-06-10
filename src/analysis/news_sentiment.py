"""
财经新闻标题情感分析（金融情感词典 + 规则打分）

不依赖深度学习模型，便于离线测试与 CI；适合实习项目演示 NLP 入门。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

# 常见财经利好 / 利空词（可扩展）
POSITIVE_WORDS = (
    "上涨",
    "大涨",
    "拉升",
    "突破",
    "利好",
    "增长",
    "盈利",
    "回购",
    "增持",
    "创新高",
    "超预期",
    "景气",
    "回暖",
    "复苏",
    "降准",
    "降息",
)

NEGATIVE_WORDS = (
    "下跌",
    "大跌",
    "暴跌",
    "下挫",
    "利空",
    "亏损",
    "减持",
    "质押",
    "违约",
    "调查",
    "处罚",
    "警示",
    "退市",
    "放缓",
    "不及预期",
)

LABEL_POSITIVE = "正面"
LABEL_NEUTRAL = "中性"
LABEL_NEGATIVE = "负面"


@dataclass
class SentimentSummary:
    total: int
    positive: int
    neutral: int
    negative: int
    avg_score: float

    @property
    def positive_ratio(self) -> float:
        return self.positive / self.total if self.total else 0.0

    @property
    def negative_ratio(self) -> float:
        return self.negative / self.total if self.total else 0.0


def _tokenize_title(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip())


def score_text(text: str) -> float:
    """
    对标题打分，范围约 [-1, 1]。
    命中正面词 +1，负面词 -1，按命中数归一化。
    """
    t = _tokenize_title(text)
    if not t:
        return 0.0

    pos = sum(1 for w in POSITIVE_WORDS if w in t)
    neg = sum(1 for w in NEGATIVE_WORDS if w in t)
    hits = pos + neg
    if hits == 0:
        return 0.0
    return (pos - neg) / hits


def label_sentiment(score: float, *, pos_threshold: float = 0.25, neg_threshold: float = -0.25) -> str:
    if score >= pos_threshold:
        return LABEL_POSITIVE
    if score <= neg_threshold:
        return LABEL_NEGATIVE
    return LABEL_NEUTRAL


def analyze_titles(
    titles: Sequence[str],
    *,
    pos_threshold: float = 0.25,
    neg_threshold: float = -0.25,
) -> pd.DataFrame:
    rows = []
    for title in titles:
        s = score_text(title)
        rows.append(
            {
                "title": title,
                "sentiment_score": round(s, 4),
                "sentiment_label": label_sentiment(s, pos_threshold=pos_threshold, neg_threshold=neg_threshold),
            }
        )
    return pd.DataFrame(rows)


def analyze_news_records(
    records: Sequence[Dict[str, Any]],
    *,
    title_key: str = "title",
    pos_threshold: float = 0.25,
    neg_threshold: float = -0.25,
) -> pd.DataFrame:
    """对新闻 dict 列表（含 title/url/time）附加情感列。"""
    if not records:
        return pd.DataFrame(
            columns=["title", "url", "publish_time", "source", "sentiment_score", "sentiment_label"]
        )

    rows = []
    for r in records:
        title = str(r.get(title_key, "") or "")
        score = score_text(title)
        rows.append(
            {
                "title": title,
                "url": r.get("url", ""),
                "publish_time": r.get("publish_time", r.get("ctime", "")),
                "source": r.get("source", ""),
                "sentiment_score": round(score, 4),
                "sentiment_label": label_sentiment(
                    score, pos_threshold=pos_threshold, neg_threshold=neg_threshold
                ),
            }
        )
    return pd.DataFrame(rows)


def summarize_sentiment(df: pd.DataFrame) -> SentimentSummary:
    if df is None or df.empty:
        return SentimentSummary(0, 0, 0, 0, 0.0)

    labels = df["sentiment_label"].value_counts()
    total = len(df)
    return SentimentSummary(
        total=total,
        positive=int(labels.get(LABEL_POSITIVE, 0)),
        neutral=int(labels.get(LABEL_NEUTRAL, 0)),
        negative=int(labels.get(LABEL_NEGATIVE, 0)),
        avg_score=float(df["sentiment_score"].mean()),
    )


def sentiment_report_to_dict(summary: SentimentSummary) -> Dict[str, Any]:
    return {
        "total": summary.total,
        "positive": summary.positive,
        "neutral": summary.neutral,
        "negative": summary.negative,
        "avg_score": round(summary.avg_score, 4),
        "positive_ratio": round(summary.positive_ratio, 4),
        "negative_ratio": round(summary.negative_ratio, 4),
    }
