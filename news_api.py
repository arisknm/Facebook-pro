"""
Pengambil berita sepak bola via RSS feed (gratis, tanpa API key).
Sumber: BBC Sport, Sky Sports, ESPN FC, Goal.com
"""
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

log = logging.getLogger(__name__)

RSS_FEEDS = {
    "bbc_sport"  : "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "sky_sports" : "https://www.skysports.com/rss/12040",
    "espn"       : "https://www.espn.com/espn/rss/soccer/news",
    "goal"       : "https://www.goal.com/feeds/en/news",
}

RSS_TRANSFER = {
    "bbc_sport"  : "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "sky_sports" : "https://www.skysports.com/rss/12040",
}


def _fetch_rss(url: str, timeout: int = 10) -> list[dict]:
    """Fetch dan parse RSS feed, return list of {title, description, link, pubDate}."""
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = []
        ns = {"media": "http://search.yahoo.com/mrss/"}
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            desc  = (item.findtext("description") or "").strip()
            link  = (item.findtext("link") or "").strip()
            pub   = (item.findtext("pubDate") or "").strip()
            if title and "[Removed]" not in title:
                items.append({
                    "title"       : title,
                    "description" : desc[:200] if desc else "",
                    "url"         : link,
                    "published_at": pub,
                    "source"      : url,
                })
        return items
    except Exception as e:
        log.warning(f"RSS gagal ({url}): {e}")
        return []


def _filter_transfer(articles: list[dict]) -> list[dict]:
    """Filter artikel yang berkaitan dengan transfer pemain."""
    kata_kunci = [
        "transfer", "signing", "sign", "deal", "move", "loan",
        "bid", "fee", "contract", "pindah", "gabung", "rekrut",
        "beli", "jual", "hengkang",
    ]
    hasil = []
    seen = set()
    for a in articles:
        teks = (a["title"] + " " + a["description"]).lower()
        if any(k in teks for k in kata_kunci) and a["title"] not in seen:
            seen.add(a["title"])
            hasil.append(a)
    return hasil


def get_transfer_news(jumlah: int = 5) -> list[dict]:
    """Ambil berita transfer terkini dari RSS feeds."""
    semua = []
    for url in RSS_TRANSFER.values():
        semua.extend(_fetch_rss(url))

    filtered = _filter_transfer(semua)

    # Jika tidak cukup artikel transfer, ambil berita umum
    if len(filtered) < jumlah:
        for url in RSS_FEEDS.values():
            semua.extend(_fetch_rss(url))
        filtered = _filter_transfer(semua)

    log.info(f"RSS: {len(filtered)} berita transfer ditemukan.")
    return filtered[:jumlah]


def get_viral_topics(jumlah: int = 5) -> list[dict]:
    """Ambil topik viral/berita terpopuler sepak bola dari RSS feeds."""
    semua = []
    seen = set()
    hasil = []

    for url in RSS_FEEDS.values():
        for a in _fetch_rss(url):
            if a["title"] not in seen:
                seen.add(a["title"])
                hasil.append(a)
        if len(hasil) >= jumlah * 3:
            break

    log.info(f"RSS: {len(hasil[:jumlah])} topik viral ditemukan.")
    return hasil[:jumlah]


def format_berita_untuk_prompt(berita_list: list[dict]) -> str:
    """Format list berita menjadi teks untuk prompt Claude."""
    baris = []
    for i, b in enumerate(berita_list, 1):
        baris.append(f"{i}. {b['title']}")
        if b.get("description"):
            baris.append(f"   {b['description'][:150]}")
        if b.get("source"):
            baris.append(f"   Sumber: {b['source']}")
    return "\n".join(baris)
