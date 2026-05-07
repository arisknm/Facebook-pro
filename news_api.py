"""
Pengambil berita sepak bola via NewsAPI.org.
"""
import logging
import requests
from config import NEWS_API_KEY

log = logging.getLogger(__name__)

NEWS_BASE = "https://newsapi.org/v2"

QUERY_TRANSFER = (
    "football transfer OR pemain bola pindah OR bola transfer"
)
QUERY_VIRAL = (
    "sepak bola OR football goal OR football match OR Liga 1"
)


def _check_config():
    if not NEWS_API_KEY:
        raise ValueError("NEWS_API_KEY harus diisi di .env")


def get_transfer_news(jumlah: int = 5) -> list[dict]:
    """
    Ambil berita transfer terbaru.

    Returns list of dict: title, description, source, url, publishedAt.
    """
    _check_config()
    resp = requests.get(
        f"{NEWS_BASE}/everything",
        params={
            "q": QUERY_TRANSFER,
            "language": "id",
            "sortBy": "publishedAt",
            "pageSize": max(jumlah * 2, 10),  # ambil lebih, filter duplikat
            "apiKey": NEWS_API_KEY,
        },
        timeout=10,
    )

    # Fallback ke bahasa Inggris jika hasil Indonesia kosong
    if resp.ok:
        articles = resp.json().get("articles", [])
    else:
        articles = []

    if not articles:
        resp = requests.get(
            f"{NEWS_BASE}/everything",
            params={
                "q": "football transfer news",
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": max(jumlah * 2, 10),
                "apiKey": NEWS_API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        articles = resp.json().get("articles", [])

    hasil = []
    seen = set()
    for a in articles:
        judul = a.get("title", "") or ""
        if not judul or judul in seen or "[Removed]" in judul:
            continue
        seen.add(judul)
        hasil.append({
            "title": judul,
            "description": a.get("description", "") or "",
            "source": a.get("source", {}).get("name", ""),
            "url": a.get("url", ""),
            "published_at": a.get("publishedAt", ""),
        })
        if len(hasil) >= jumlah:
            break

    log.info(f"NewsAPI: {len(hasil)} berita transfer ditemukan.")
    return hasil


def get_viral_topics(jumlah: int = 5) -> list[dict]:
    """
    Ambil topik viral sepak bola hari ini.

    Returns list of dict: title, description, source, url, publishedAt.
    """
    _check_config()
    resp = requests.get(
        f"{NEWS_BASE}/top-headlines",
        params={
            "q": "football OR sepak bola",
            "category": "sports",
            "language": "id",
            "pageSize": max(jumlah * 2, 10),
            "apiKey": NEWS_API_KEY,
        },
        timeout=10,
    )

    articles = resp.json().get("articles", []) if resp.ok else []

    # Fallback: everything endpoint jika top-headlines kosong
    if not articles:
        resp = requests.get(
            f"{NEWS_BASE}/everything",
            params={
                "q": "football viral OR football controversy OR bola viral",
                "language": "en",
                "sortBy": "popularity",
                "pageSize": max(jumlah * 2, 10),
                "apiKey": NEWS_API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        articles = resp.json().get("articles", [])

    hasil = []
    seen = set()
    for a in articles:
        judul = a.get("title", "") or ""
        if not judul or judul in seen or "[Removed]" in judul:
            continue
        seen.add(judul)
        hasil.append({
            "title": judul,
            "description": a.get("description", "") or "",
            "source": a.get("source", {}).get("name", ""),
            "url": a.get("url", ""),
            "published_at": a.get("publishedAt", ""),
        })
        if len(hasil) >= jumlah:
            break

    log.info(f"NewsAPI: {len(hasil)} topik viral ditemukan.")
    return hasil


def format_berita_untuk_prompt(berita_list: list[dict]) -> str:
    """Format list berita menjadi teks untuk prompt Claude."""
    baris = []
    for i, b in enumerate(berita_list, 1):
        baris.append(f"{i}. {b['title']}")
        if b.get("description"):
            baris.append(f"   {b['description'][:120]}")
        if b.get("source"):
            baris.append(f"   Sumber: {b['source']}")
    return "\n".join(baris)
