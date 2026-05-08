"""
Pengambil berita sepak bola via RSS feed (gratis, tanpa API key).
Sumber internasional: BBC Sport, Sky Sports, ESPN FC, Goal.com
Sumber Indonesia: Bola.com, Bola.net, Detik Sport, Kompas Bola
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

# RSS feed berita sepak bola Indonesia
RSS_INDONESIA = {
    "bola_com"   : "https://www.bola.com/feeds/all",
    "bola_net"   : "https://bola.net/feed",
    "detik_sport": "https://feed.detik.com/detik_sport",
    "goal_id"    : "https://www.goal.com/feeds/id/news",
}

# Keyword filter per topik pundit
TOPIK_PUNDIT = {
    "timnas": [
        "timnas", "indonesia", "garuda", "shin tae-yong", "sty",
        "ragnar", "pratama arhan", "witan", "egy", "struick", "paes",
        "nathan", "jordi amat", "ivar jenner", "thom haye",
        "marselino", "rizky ridho", "elkan baggott",
        "pemain indonesia", "naturalisasi",
    ],
    "liga1": [
        "liga 1", "bri liga", "liga indonesia", "persija", "persib",
        "arema", "borneo fc", "psm", "bali united", "persebaya",
        "psis", "dewa united", "madura united", "bhayangkara",
    ],
    "persija": [
        "persija", "macan kemayoran", "jak mania", "the jak",
        "carlos fortes", "persija jakarta",
    ],
    "persib": [
        "persib", "maung bandung", "bobotoh", "david da silva",
        "ciro alves", "persib bandung",
    ],
    "manchester_united": [
        "manchester united", "man united", "man utd", "old trafford",
        "ruben amorim", "rasmus hojlund", "marcus rashford",
        "bruno fernandes", "red devils",
    ],
    "liga_champion": [
        "champions league", "ucl", "liga champion", "uefa",
        "el clasico", "semifinal", "final champions",
        "real madrid", "barcelona", "man city", "arsenal",
        "psg", "inter milan", "dortmund", "liverpool champions",
    ],
}


def _fetch_rss(url: str, timeout: int = 10) -> list[dict]:
    """Fetch dan parse RSS feed, return list of {title, description, link, pubDate, image_url}."""
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

            image_url = ""
            media = item.find("media:content", ns)
            if media is not None:
                image_url = media.get("url", "")
            if not image_url:
                thumb = item.find("media:thumbnail", ns)
                if thumb is not None:
                    image_url = thumb.get("url", "")
            if not image_url:
                enc = item.find("enclosure")
                if enc is not None and "image" in enc.get("type", ""):
                    image_url = enc.get("url", "")

            if title and "[Removed]" not in title:
                items.append({
                    "title"       : title,
                    "description" : desc[:200] if desc else "",
                    "url"         : link,
                    "published_at": pub,
                    "source"      : url,
                    "image_url"   : image_url,
                })
        return items
    except Exception as e:
        log.warning(f"RSS gagal ({url}): {e}")
        return []


def _filter_topik(articles: list[dict], topik: str) -> list[dict]:
    """Filter artikel berdasarkan topik pundit."""
    kata_kunci = TOPIK_PUNDIT.get(topik, [])
    hasil = []
    seen  = set()
    for a in articles:
        teks = (a["title"] + " " + a["description"]).lower()
        if any(k in teks for k in kata_kunci) and a["title"] not in seen:
            seen.add(a["title"])
            hasil.append(a)
    return hasil


def _filter_transfer(articles: list[dict]) -> list[dict]:
    kata_kunci = [
        "transfer", "signing", "sign", "deal", "move", "loan",
        "bid", "fee", "contract", "pindah", "gabung", "rekrut",
        "beli", "jual", "hengkang",
    ]
    hasil = []
    seen  = set()
    for a in articles:
        teks = (a["title"] + " " + a["description"]).lower()
        if any(k in teks for k in kata_kunci) and a["title"] not in seen:
            seen.add(a["title"])
            hasil.append(a)
    return hasil


def get_berita_pundit(topik: str, jumlah: int = 5) -> list[dict]:
    """
    Ambil berita terkini untuk topik pundit tertentu.
    Topik: timnas | liga1 | persija | persib | manchester_united | liga_champion
    """
    semua = []

    # Untuk topik Indonesia, prioritaskan feed lokal
    if topik in ("timnas", "liga1", "persija", "persib"):
        for url in RSS_INDONESIA.values():
            semua.extend(_fetch_rss(url))

    # Selalu tambah feed internasional
    for url in RSS_FEEDS.values():
        semua.extend(_fetch_rss(url))

    filtered = _filter_topik(semua, topik)

    # Fallback: jika tidak ada berita spesifik, ambil berita umum
    if not filtered:
        log.warning(f"Tidak ada berita untuk topik '{topik}', pakai berita umum")
        seen  = set()
        for a in semua:
            if a["title"] not in seen:
                seen.add(a["title"])
                filtered.append(a)

    log.info(f"RSS pundit '{topik}': {len(filtered[:jumlah])} berita ditemukan.")
    return filtered[:jumlah]


def get_topik_pundit_hari_ini() -> str:
    """
    Rotasi topik pundit berdasarkan hari dalam seminggu.
    Setiap hari membahas topik berbeda.
    """
    from datetime import datetime
    hari = datetime.now().weekday()  # 0=Senin, 6=Minggu
    rotasi = {
        0: "timnas",            # Senin
        1: "liga_champion",     # Selasa
        2: "manchester_united", # Rabu
        3: "liga1",             # Kamis
        4: "timnas",            # Jumat
        5: "persija",           # Sabtu
        6: "persib",            # Minggu
    }
    return rotasi.get(hari, "timnas")


def get_transfer_news(jumlah: int = 5) -> list[dict]:
    semua = []
    for url in RSS_TRANSFER.values():
        semua.extend(_fetch_rss(url))
    filtered = _filter_transfer(semua)
    if len(filtered) < jumlah:
        for url in RSS_FEEDS.values():
            semua.extend(_fetch_rss(url))
        filtered = _filter_transfer(semua)
    log.info(f"RSS: {len(filtered)} berita transfer ditemukan.")
    return filtered[:jumlah]


def get_viral_topics(jumlah: int = 5) -> list[dict]:
    semua = []
    seen  = set()
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
    baris = []
    for i, b in enumerate(berita_list, 1):
        baris.append(f"{i}. {b['title']}")
        if b.get("description"):
            baris.append(f"   {b['description'][:150]}")
        if b.get("source"):
            baris.append(f"   Sumber: {b['source']}")
    return "\n".join(baris)



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
