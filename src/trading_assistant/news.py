from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
import re
from typing import Iterable
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


DEFAULT_CNBC_RSS_URL = "https://www.cnbcindonesia.com/market/rss"
DEFAULT_BLOOMBERG_RSS_URL = "https://feeds.bloomberg.com/markets/news.rss"
DEFAULT_IDX_NEWS_URL = "https://www.idx.id/en/news/news/"
DEFAULT_YAHOO_FINANCE_RSS_URL = "https://finance.yahoo.com/rss/headline?s=%5EJKSE,BBCA.JK,BBRI.JK,BMRI.JK,TLKM.JK"
DEFAULT_NEWS_SOURCES = {
    "CNBC": DEFAULT_CNBC_RSS_URL,
    "IDX": DEFAULT_IDX_NEWS_URL,
    "Bloomberg": DEFAULT_BLOOMBERG_RSS_URL,
    "Yahoo Finance": DEFAULT_YAHOO_FINANCE_RSS_URL,
}
DEFAULT_NEWS_RSS_URL = DEFAULT_CNBC_RSS_URL

POSITIVE_TERMS = {
    "akuisisi",
    "bertumbuh",
    "buyback",
    "cuan",
    "dividen",
    "ekspansi",
    "kenaikan",
    "kontrak",
    "laba",
    "melaju",
    "melesat",
    "melonjak",
    "menguat",
    "naik",
    "optimis",
    "positif",
    "pulih",
    "rekor",
    "right issue sukses",
    "tumbuh",
    "untung",
}

NEGATIVE_TERMS = {
    "anjlok",
    "bangkrut",
    "beban",
    "denda",
    "gagal bayar",
    "gugatan",
    "konflik",
    "korupsi",
    "krisis",
    "merugi",
    "negatif",
    "pailit",
    "pelemahan",
    "penurunan",
    "rugi",
    "sanksi",
    "sengketa",
    "tersungkur",
    "turun",
    "utang",
}


@dataclass(frozen=True)
class NewsItem:
    title: str
    link: str
    published: str | None
    summary: str
    source: str = "UNKNOWN"

    @property
    def text(self) -> str:
        return f"{self.title} {self.summary}".strip()


def fetch_market_news(
    sources: dict[str, str] | None = None,
    timeout: int = 20,
) -> tuple[list[NewsItem], dict]:
    selected_sources = sources or DEFAULT_NEWS_SOURCES
    items: list[NewsItem] = []
    source_statuses: list[dict] = []
    seen_links: set[str] = set()

    for source_name, url in selected_sources.items():
        if source_name.upper() == "IDX":
            fetched_items, status = fetch_idx_news(url=url, source_name=source_name, timeout=timeout)
        else:
            fetched_items, status = fetch_rss_news(url=url, source_name=source_name, timeout=timeout)
        source_statuses.append(status)
        for item in fetched_items:
            dedupe_key = item.link or f"{item.source}:{item.title}"
            if dedupe_key in seen_links:
                continue
            seen_links.add(dedupe_key)
            items.append(item)

    overall_status = "OK" if any(status.get("status") == "OK" for status in source_statuses) else "NEWS_UNAVAILABLE"
    return items, {
        "status": overall_status,
        "sources": source_statuses,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "items": len(items),
    }


def fetch_rss_news(
    url: str = DEFAULT_NEWS_RSS_URL,
    source_name: str = "RSS",
    timeout: int = 20,
) -> tuple[list[NewsItem], dict]:
    request = Request(url, headers={"User-Agent": "WanacciTradingAssistant/0.1"})
    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except (OSError, URLError) as exc:
        return [], {
            "status": "NEWS_UNAVAILABLE",
            "name": source_name,
            "source": url,
            "fetched_at": fetched_at,
            "error": str(exc),
        }

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        return [], {
            "status": "NEWS_PARSE_ERROR",
            "name": source_name,
            "source": url,
            "fetched_at": fetched_at,
            "error": str(exc),
        }

    items: list[NewsItem] = []
    for item in root.findall(".//item"):
        title = _text(item, "title")
        link = _text(item, "link")
        published_raw = _text(item, "pubDate")
        summary = _text(item, "description")
        published = _parse_date(published_raw)
        if title:
            items.append(NewsItem(title=title, link=link, published=published, summary=_strip_html(summary), source=source_name))

    return items, {
        "status": "OK",
        "name": source_name,
        "source": url,
        "fetched_at": fetched_at,
        "items": len(items),
    }


def fetch_cnbc_rss(url: str = DEFAULT_CNBC_RSS_URL, timeout: int = 20) -> tuple[list[NewsItem], dict]:
    return fetch_rss_news(url=url, source_name="CNBC", timeout=timeout)


def fetch_idx_news(
    url: str = DEFAULT_IDX_NEWS_URL,
    source_name: str = "IDX",
    timeout: int = 20,
) -> tuple[list[NewsItem], dict]:
    request = Request(url, headers={"User-Agent": "WanacciTradingAssistant/0.1"})
    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        with urlopen(request, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except (OSError, URLError) as exc:
        return [], {
            "status": "NEWS_UNAVAILABLE",
            "name": source_name,
            "source": url,
            "fetched_at": fetched_at,
            "error": str(exc),
        }

    items: list[NewsItem] = []
    seen_titles: set[str] = set()
    pattern = re.compile(
        r"(?P<date>\d{1,2}\s+[A-Za-z]+\s+\d{4})\s*(?P<title>[^<>\n]{12,180})",
        re.IGNORECASE,
    )
    for match in pattern.finditer(_strip_html(html)):
        title = " ".join(unescape(match.group("title")).split())
        if title in seen_titles:
            continue
        seen_titles.add(title)
        items.append(
            NewsItem(
                title=title,
                link=urljoin(url, "/en/news/news/"),
                published=match.group("date"),
                summary="",
                source=source_name,
            )
        )
        if len(items) >= 30:
            break

    status = "OK" if items else "NEWS_PARSE_ERROR"
    return items, {
        "status": status,
        "name": source_name,
        "source": url,
        "fetched_at": fetched_at,
        "items": len(items),
    }


def build_news_context(
    ticker: str,
    news_items: Iterable[NewsItem],
    aliases: Iterable[str] | None = None,
    max_items: int = 5,
) -> dict:
    base_symbol = ticker.replace(".JK", "").upper()
    terms = {base_symbol}
    for alias in aliases or []:
        if alias:
            terms.add(alias.upper())

    matches: list[dict] = []
    total_score = 0
    for item in news_items:
        haystack = item.text.upper()
        if not any(_contains_term(haystack, term) for term in terms):
            continue
        sentiment_score, evidence_terms = score_news_text(item.text)
        total_score += sentiment_score
        matches.append(
            {
                "title": item.title,
                "link": item.link,
                "published": item.published,
                "source": item.source,
                "sentiment_score": sentiment_score,
                "sentiment_terms": evidence_terms,
            }
        )
        if len(matches) >= max_items:
            break

    if not matches:
        return {
            "news_status": "NO_RELEVANT_NEWS",
            "news_sentiment": "NEUTRAL",
            "news_score": 0,
            "matched_articles": [],
        }

    if total_score > 0:
        sentiment = "POSITIVE"
    elif total_score < 0:
        sentiment = "NEGATIVE"
    else:
        sentiment = "NEUTRAL"

    return {
        "news_status": "OK",
        "news_sentiment": sentiment,
        "news_score": total_score,
        "matched_articles": matches,
    }


def score_news_text(text: str) -> tuple[int, list[str]]:
    lowered = text.lower()
    score = 0
    terms: list[str] = []
    for term in POSITIVE_TERMS:
        if term in lowered:
            score += 1
            terms.append(f"positive:{term}")
    for term in NEGATIVE_TERMS:
        if term in lowered:
            score -= 1
            terms.append(f"negative:{term}")
    return score, terms


def apply_news_confirmation(analysis: dict, news_context: dict) -> dict:
    updated = dict(analysis)
    updated["news"] = news_context
    plan = dict(updated.get("trade_plan", {}))
    wyckoff = updated.get("wyckoff_vpa", {})
    phase = wyckoff.get("phase")
    main_signal = wyckoff.get("main_signal")
    sentiment = news_context.get("news_sentiment")
    status = news_context.get("news_status")

    confirmation = "NEWS_NOT_USED"
    adjustment = 0
    if status == "OK" and sentiment == "POSITIVE" and phase in {"DISTRIBUTION", "MARKDOWN"}:
        confirmation = "POSITIVE_NEWS_DISTRIBUTION_SELL_CONFIRMATION"
        adjustment = 10
        if plan.get("trade_action") in {None, "WAIT", "HOLD"}:
            plan["trade_action"] = "DISTRIBUTION_WARNING"
        plan["trade_reason"] = _append_reason(plan.get("trade_reason"), "positive news appears while VPA shows distribution risk")
    elif status == "OK" and sentiment == "NEGATIVE" and phase == "ACCUMULATION":
        confirmation = "NEGATIVE_NEWS_ACCUMULATION_BUY_CONFIRMATION"
        adjustment = 10
        if plan.get("trade_action") == "WAIT":
            plan["trade_action"] = "ACCUMULATION_WATCH"
        plan["trade_reason"] = _append_reason(plan.get("trade_reason"), "negative news appears while VPA shows accumulation pressure")
    elif status == "OK":
        confirmation = "NEWS_PRESENT_NO_STRONG_VPA_CONFIRMATION"
    elif status in {"NEWS_UNAVAILABLE", "NEWS_PARSE_ERROR"}:
        confirmation = "NEWS_UNAVAILABLE"
    else:
        confirmation = "NO_RELEVANT_NEWS"

    confidence = plan.get("confidence")
    if isinstance(confidence, (int, float)) and adjustment:
        plan["confidence"] = min(100, int(confidence + adjustment))
    plan["news_confirmation"] = confirmation
    updated["trade_plan"] = plan
    updated["confidence"] = plan.get("confidence")
    return updated


def _text(item: ET.Element, tag: str) -> str:
    found = item.find(tag)
    return "" if found is None or found.text is None else found.text.strip()


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value).strip()


def _parse_date(value: str) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError):
        return value


def _contains_term(haystack: str, term: str) -> bool:
    if len(term) <= 5 and term.isalnum():
        return re.search(rf"\b{re.escape(term)}\b", haystack) is not None
    return term in haystack


def _append_reason(existing: str | None, addition: str) -> str:
    if existing:
        return f"{existing}, {addition}"
    return addition
