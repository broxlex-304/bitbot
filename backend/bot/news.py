"""
BitBot News & Sentiment Analyzer
Fetches live crypto news and computes a sentiment score.
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from textblob import TextBlob
from bot import logger
from config import settings


CRYPTO_NEWS_SOURCES = [
    "https://cryptopanic.com/api/v1/posts/?auth_token={key}&filter=hot&currencies={coin}",
    "https://newsapi.org/v2/everything?q={coin}+crypto&sortBy=publishedAt&apiKey={key}&pageSize=20",
]

FEARGREED_URL = "https://api.alternative.me/fng/?limit=1"

POSITIVE_KEYWORDS = [
    "bullish", "surge", "rally", "breakout", "moon", "soar", "gain", "rise",
    "adoption", "institutional", "partnership", "upgrade", "launch", "milestone",
    "all-time high", "ath", "recovery", "pump", "positive", "bull"
]
NEGATIVE_KEYWORDS = [
    "bearish", "crash", "dump", "plunge", "ban", "hack", "lawsuit", "regulation",
    "fear", "sell-off", "correction", "drop", "decline", "warning", "risk",
    "liquidation", "short", "bear", "negative", "scam", "fraud"
]


def _score_text(text: str) -> float:
    """Returns sentiment in range [-1.0, +1.0]"""
    text_lower = text.lower()
    blob_score = TextBlob(text).sentiment.polarity

    keyword_score = 0.0
    for word in POSITIVE_KEYWORDS:
        if word in text_lower:
            keyword_score += 0.15
    for word in NEGATIVE_KEYWORDS:
        if word in text_lower:
            keyword_score -= 0.15

    return max(-1.0, min(1.0, (blob_score + keyword_score) / 2))


async def _fetch_cryptopanic(coin: str) -> List[Dict]:
    key = settings.cryptopanic_key
    if not key:
        return []
    coin_base = coin.split("/")[0]
    url = f"https://cryptopanic.com/api/v1/posts/?auth_token={key}&filter=hot&currencies={coin_base}&public=true"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                return data.get("results", [])[:15]
    except Exception as e:
        logger.warning(f"CryptoPanic fetch failed: {e}")
        return []


async def _fetch_newsapi(coin: str) -> List[Dict]:
    key = settings.newsapi_key
    if not key:
        return []
    coin_base = coin.split("/")[0]
    url = (f"https://newsapi.org/v2/everything?q={coin_base}+cryptocurrency"
           f"&sortBy=publishedAt&apiKey={key}&pageSize=15&language=en")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                return data.get("articles", [])[:15]
    except Exception as e:
        logger.warning(f"NewsAPI fetch failed: {e}")
        return []


async def _fetch_fear_greed() -> Dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FEARGREED_URL, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                fg = data["data"][0]
                return {"value": int(fg["value"]), "classification": fg["value_classification"]}
    except Exception as e:
        logger.warning(f"Fear & Greed fetch failed: {e}")
        return {"value": 50, "classification": "Neutral"}


async def _fetch_coingecko_trending() -> List[str]:
    try:
        url = "https://api.coingecko.com/api/v3/search/trending"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                return [c["item"]["symbol"].upper() for c in data.get("coins", [])[:5]]
    except Exception:
        return []


class NewsAnalyzer:
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(minutes=10)

    def _is_cached(self, key: str) -> bool:
        if key not in self._cache:
            return False
        return datetime.utcnow() < self._cache_expiry.get(key, datetime.min)

    def _set_cache(self, key: str, value: Any):
        self._cache[key] = value
        self._cache_expiry[key] = datetime.utcnow() + self._cache_ttl

    async def analyze(self, coin: str) -> Dict[str, Any]:
        cache_key = f"news_{coin}"
        if self._is_cached(cache_key):
            logger.info(f"Using cached news sentiment for {coin}")
            return self._cache[cache_key]

        logger.news(f"Fetching live news & sentiment for {coin}...")

        # Concurrent fetches
        cryptopanic_items, newsapi_items, fear_greed, trending = await asyncio.gather(
            _fetch_cryptopanic(coin),
            _fetch_newsapi(coin),
            _fetch_fear_greed(),
            _fetch_coingecko_trending(),
        )

        articles = []

        # Parse CryptoPanic
        for item in cryptopanic_items:
            text = item.get("title", "")
            score = _score_text(text)
            # Boost from votes
            votes = item.get("votes", {})
            positive_votes = votes.get("positive", 0)
            negative_votes = votes.get("negative", 0)
            if positive_votes > negative_votes:
                score = min(1.0, score + 0.1)
            elif negative_votes > positive_votes:
                score = max(-1.0, score - 0.1)
            articles.append({"source": "CryptoPanic", "title": text, "score": score})

        # Parse NewsAPI
        for item in newsapi_items:
            title = item.get("title", "") or ""
            desc  = item.get("description", "") or ""
            text  = f"{title} {desc}"
            score = _score_text(text)
            articles.append({"source": "NewsAPI", "title": title, "score": score})

        # Fear & Greed influence
        fg_val = fear_greed.get("value", 50)
        fg_score = (fg_val - 50) / 50  # -1 to +1

        if articles:
            avg_article_score = sum(a["score"] for a in articles) / len(articles)
        else:
            avg_article_score = 0.0

        # Weighted: 60% articles + 40% fear-greed
        composite_score = (avg_article_score * 0.6) + (fg_score * 0.4)

        # Normalize to 0–100 scale
        sentiment_pct = ((composite_score + 1) / 2) * 100

        if composite_score > 0.2:
            sentiment = "POSITIVE"
        elif composite_score < -0.2:
            sentiment = "NEGATIVE"
        else:
            sentiment = "NEUTRAL"

        coin_in_trending = coin.split("/")[0].upper() in trending

        result = {
            "sentiment": sentiment,
            "sentiment_score": round(composite_score, 3),
            "sentiment_pct": round(sentiment_pct, 1),
            "article_count": len(articles),
            "articles": articles[:5],  # Top 5 for display
            "fear_greed": fear_greed,
            "trending": trending,
            "coin_is_trending": coin_in_trending,
        }

        self._set_cache(cache_key, result)

        direction_map = {"POSITIVE": "▲", "NEGATIVE": "▼", "NEUTRAL": "→"}
        logger.news(
            f"Sentiment [{coin}]: {sentiment} {direction_map.get(sentiment,'')} "
            f"({composite_score:+.2f}) | F&G: {fg_val} {fear_greed['classification']} "
            f"| {len(articles)} articles | Trending: {coin_in_trending}",
            result
        )

        return result


# Singleton
news_analyzer = NewsAnalyzer()
