from __future__ import annotations

from trading_assistant.news import NewsItem, apply_news_confirmation, build_news_context, fetch_market_news, score_news_text


def test_news_sentiment_scores_positive_and_negative_terms() -> None:
    positive_score, positive_terms = score_news_text("Laba emiten naik dan ekspansi positif")
    negative_score, negative_terms = score_news_text("Emiten merugi karena utang dan sanksi")

    assert positive_score > 0
    assert negative_score < 0
    assert positive_terms
    assert negative_terms


def test_build_news_context_matches_ticker() -> None:
    items = [
        NewsItem(
            title="BBCA cetak laba naik",
            link="https://example.com",
            published=None,
            summary="Kinerja positif",
        )
    ]

    context = build_news_context("BBCA.JK", items)

    assert context["news_status"] == "OK"
    assert context["news_sentiment"] == "POSITIVE"
    assert context["matched_articles"][0]["source"] == "UNKNOWN"


def test_fetch_market_news_combines_sources(monkeypatch) -> None:
    def fake_fetch_rss_news(url: str, source_name: str, timeout: int = 20):
        return [NewsItem(title=f"{source_name} BBCA naik", link=url, published=None, summary="", source=source_name)], {
            "status": "OK",
            "name": source_name,
            "source": url,
            "items": 1,
        }

    def fake_fetch_idx_news(url: str, source_name: str, timeout: int = 20):
        return [NewsItem(title="IDX BBCA disclosure", link=url, published=None, summary="", source=source_name)], {
            "status": "OK",
            "name": source_name,
            "source": url,
            "items": 1,
        }

    monkeypatch.setattr("trading_assistant.news.fetch_rss_news", fake_fetch_rss_news)
    monkeypatch.setattr("trading_assistant.news.fetch_idx_news", fake_fetch_idx_news)

    items, status = fetch_market_news(
        {
            "CNBC": "https://cnbc.example/rss",
            "IDX": "https://idx.example/news",
            "Bloomberg": "https://bloomberg.example/rss",
            "Yahoo Finance": "https://yahoo.example/rss",
        }
    )

    assert status["status"] == "OK"
    assert status["items"] == 4
    assert {item.source for item in items} == {"CNBC", "IDX", "Bloomberg", "Yahoo Finance"}


def test_positive_news_confirms_distribution_warning() -> None:
    analysis = {
        "wyckoff_vpa": {"phase": "DISTRIBUTION", "main_signal": "DISTRIBUTION_PRESSURE"},
        "trade_plan": {"trade_action": "WAIT", "confidence": 50, "trade_reason": "distribution risk"},
    }
    news = {
        "news_status": "OK",
        "news_sentiment": "POSITIVE",
        "news_score": 1,
        "matched_articles": [],
    }

    updated = apply_news_confirmation(analysis, news)

    assert updated["trade_plan"]["trade_action"] == "DISTRIBUTION_WARNING"
    assert updated["trade_plan"]["news_confirmation"] == "POSITIVE_NEWS_DISTRIBUTION_SELL_CONFIRMATION"


def test_negative_news_confirms_accumulation_watch() -> None:
    analysis = {
        "wyckoff_vpa": {"phase": "ACCUMULATION", "main_signal": "ACCUMULATION_PRESSURE"},
        "trade_plan": {"trade_action": "WAIT", "confidence": 50, "trade_reason": "accumulation"},
    }
    news = {
        "news_status": "OK",
        "news_sentiment": "NEGATIVE",
        "news_score": -1,
        "matched_articles": [],
    }

    updated = apply_news_confirmation(analysis, news)

    assert updated["trade_plan"]["trade_action"] == "ACCUMULATION_WATCH"
    assert updated["trade_plan"]["news_confirmation"] == "NEGATIVE_NEWS_ACCUMULATION_BUY_CONFIRMATION"
