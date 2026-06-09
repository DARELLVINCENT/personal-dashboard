# perlu di taruh di github
"""
Sentiment Analysis router — NLP-based market sentiment from news articles.
Uses NewsAPI for fetching news and TextBlob for sentiment scoring.
"""
from fastapi import APIRouter, HTTPException
import requests
import logging
from datetime import datetime, timedelta

try:
    from textblob import TextBlob
except ImportError:
    TextBlob = None

from config import NEWS_API_KEY

router = APIRouter(prefix="/api/sentiment", tags=["Sentiment"])
logger = logging.getLogger(__name__)

# Mapping ticker ke nama perusahaan untuk pencarian berita yang lebih akurat
TICKER_MAP = {
    "BBCA.JK": "Bank Central Asia BCA",
    "BBRI.JK": "Bank Rakyat Indonesia BRI",
    "BMRI.JK": "Bank Mandiri",
    "BBNI.JK": "Bank Negara Indonesia BNI",
    "TLKM.JK": "Telkom Indonesia",
    "ASII.JK": "Astra International",
    "UNVR.JK": "Unilever Indonesia",
    "HMSP.JK": "HM Sampoerna",
    "ICBP.JK": "Indofood CBP",
    "INDF.JK": "Indofood",
    "GGRM.JK": "Gudang Garam",
    "KLBF.JK": "Kalbe Farma",
    "SMGR.JK": "Semen Indonesia",
    "PGAS.JK": "Perusahaan Gas Negara",
    "ADRO.JK": "Adaro Energy",
    "ANTM.JK": "Aneka Tambang",
    "PTBA.JK": "Bukit Asam",
    "INCO.JK": "Vale Indonesia",
    "EXCL.JK": "XL Axiata",
    "ISAT.JK": "Indosat Ooredoo",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOG": "Google Alphabet",
    "AMZN": "Amazon",
    "TSLA": "Tesla",
    "NVDA": "Nvidia",
    "META": "Meta Facebook",
}


def _get_search_query(ticker: str) -> str:
    """Translate ticker ke query pencarian berita yang lebih relevan."""
    clean = ticker.upper().strip()
    if clean in TICKER_MAP:
        return TICKER_MAP[clean]
    # Hapus suffix .JK dan return
    return clean.replace(".JK", "").replace(".SI", "")


def _analyze_sentiment(text: str) -> dict:
    """Analisis sentimen satu teks menggunakan TextBlob."""
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity  # -1.0 (negatif) to +1.0 (positif)
    subjectivity = blob.sentiment.subjectivity  # 0.0 (objektif) to 1.0 (subjektif)

    if polarity > 0.1:
        label = "Bullish"
    elif polarity < -0.1:
        label = "Bearish"
    else:
        label = "Neutral"

    return {
        "polarity": round(polarity, 4),
        "subjectivity": round(subjectivity, 4),
        "label": label,
    }


@router.get("")
def get_sentiment(ticker: str, max_articles: int = 15):
    """Ambil berita terkini dan analisis sentimennya."""
    if not TextBlob:
        raise HTTPException(
            status_code=500,
            detail="Library textblob belum diinstal. Jalankan: pip install textblob",
        )

    if not NEWS_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="NEWS_API_KEY belum dikonfigurasi di file .env",
        )

    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker wajib diisi.")

    ticker = ticker.upper().strip()
    query = _get_search_query(ticker)

    try:
        # Fetch berita dari NewsAPI (7 hari terakhir)
        date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "from": date_from,
            "sortBy": "relevancy",
            "language": "en",
            "pageSize": min(max_articles, 30),
            "apiKey": NEWS_API_KEY,
        }

        response = requests.get(url, params=params, timeout=10)
        news_data = response.json()

        if news_data.get("status") != "ok":
            error_msg = news_data.get("message", "Gagal mengambil data berita")
            raise HTTPException(status_code=502, detail=f"NewsAPI error: {error_msg}")

        raw_articles = news_data.get("articles", [])

        if not raw_articles:
            return {
                "ticker": ticker,
                "query": query,
                "articles": [],
                "overall_sentiment": 0,
                "overall_label": "Neutral",
                "bullish_count": 0,
                "bearish_count": 0,
                "neutral_count": 0,
                "total_articles": 0,
                "summary": f"Tidak ditemukan berita terkini untuk {ticker}.",
            }

        # Proses setiap artikel dengan NLP
        articles = []
        total_polarity = 0.0
        bullish, bearish, neutral = 0, 0, 0

        for art in raw_articles:
            title = art.get("title") or ""
            description = art.get("description") or ""
            content = art.get("content") or ""

            # Gabungkan title + description untuk analisis sentimen
            combined_text = f"{title}. {description}"
            if not combined_text.strip() or combined_text.strip() == ".":
                continue

            sentiment = _analyze_sentiment(combined_text)
            total_polarity += sentiment["polarity"]

            if sentiment["label"] == "Bullish":
                bullish += 1
            elif sentiment["label"] == "Bearish":
                bearish += 1
            else:
                neutral += 1

            articles.append({
                "title": title,
                "description": description[:200] if description else "",
                "source": art.get("source", {}).get("name", "Unknown"),
                "url": art.get("url", ""),
                "published_at": art.get("publishedAt", ""),
                "image_url": art.get("urlToImage", ""),
                "sentiment": sentiment,
            })

        total = len(articles)
        if total == 0:
            avg_polarity = 0
            overall_label = "Neutral"
        else:
            avg_polarity = total_polarity / total
            if avg_polarity > 0.1:
                overall_label = "Bullish"
            elif avg_polarity < -0.1:
                overall_label = "Bearish"
            else:
                overall_label = "Neutral"

        # Buat rangkuman
        if overall_label == "Bullish":
            summary = f"Sentimen pasar terhadap {ticker} cenderung POSITIF. Dari {total} berita yang dianalisis, {bullish} menunjukkan sinyal bullish. Pasar menunjukkan optimisme terhadap aset ini."
        elif overall_label == "Bearish":
            summary = f"Sentimen pasar terhadap {ticker} cenderung NEGATIF. Dari {total} berita yang dianalisis, {bearish} menunjukkan sinyal bearish. Pasar menunjukkan kehati-hatian terhadap aset ini."
        else:
            summary = f"Sentimen pasar terhadap {ticker} cenderung NETRAL. Dari {total} berita yang dianalisis, tidak ada dominasi sentimen yang kuat. Pasar belum menunjukkan arah yang jelas."

        return {
            "ticker": ticker,
            "query": query,
            "articles": articles,
            "overall_sentiment": round(avg_polarity, 4),
            "overall_label": overall_label,
            "bullish_count": bullish,
            "bearish_count": bearish,
            "neutral_count": neutral,
            "total_articles": total,
            "summary": summary,
        }

    except requests.RequestException as e:
        logger.error(f"Network error fetching news for {ticker}: {e}")
        raise HTTPException(status_code=502, detail=f"Gagal menghubungi NewsAPI: {str(e)}")
    except Exception as e:
        logger.error(f"Error in sentiment analysis for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
