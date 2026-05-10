"""
Pengambil berita sepak bola via RSS feed (gratis, tanpa API key).
Sumber: BBC Sport, Sky Sports, Guardian, Talksport, 90min, NYTimes Soccer
"""
import logging
import requests
import xml.etree.ElementTree as ET

log = logging.getLogger(__name__)

RSS_FEEDS = {
    "bbc_sport" : "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "sky_sports": "https://www.skysports.com/rss/12040",
    "guardian"  : "https://www.theguardian.com/football/rss",
    "talksport" : "https://talksport.com/feed/",
    "90min"     : "https://www.90min.com/posts.rss",
    "nytimes"   : "https://rss.nytimes.com/services/xml/rss/nyt/Soccer.xml",
}

RSS_TRANSFER = {
    "bbc_sport" : "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "sky_sports": "https://www.skysports.com/rss/12040",
    "talksport" : "https://talksport.com/feed/",
}

RSS_INDONESIA = {
    "bbc_sport" : "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "sky_sports": "https://www.skysports.com/rss/12040",
    "guardian"  : "https://www.theguardian.com/football/rss",
}

TOPIK_PUNDIT = {
    "timnas": [
        "timnas", "indonesia", "garuda", "shin tae-yong", "sty",
        "ragnar", "pratama arhan", "witan", "egy", "struick",
        "marselino", "rizky ridho", "elkan baggott", "naturalisasi",
    ],
    "liga1": [
        "liga 1", "bri liga", "liga indonesia", "persija", "persib",
        "arema", "borneo fc", "psm", "bali united", "persebaya",
    ],
    "persija": ["persija", "macan kemayoran", "jak mania", "the jak"],
    "persib" : ["persib", "maung bandung", "bobotoh", "david da silva"],
    "manchester_united": [
        "manchester united", "man united", "man utd", "old trafford",
        "ruben amorim", "rasmus hojlund", "bruno fernandes", "red devils",
    ],
    "liga_champion": [
        "champions league", "ucl", "liga champion", "uefa", "el clasico",
        "semifinal", "final champions", "real madrid", "barcelona",
        "man city", "arsenal", "psg", "inter milan", "dortmund",
    ],
}


def _upgrade_bbc_image(url: str) -> str:
    """BBC CDN: ganti resolusi 240 → 1280 untuk kualitas lebih baik."""
    if "ichef.bbci.co.uk" in url:
        import re
        url = re.sub(r"/standard/\d+/", "/standard/1280/", url)
    return url


def _fetch_rss(url: str, timeout: int = 12) -> list[dict]:
    """Fetch dan parse RSS feed, return list of artikel dengan image_url asli."""
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

            # Cari gambar dari berbagai elemen RSS
            image_url = ""
            for tag in ["media:content", "media:thumbnail"]:
                el = item.find(tag, ns)
                if el is not None:
                    image_url = el.get("url", "")
                    if image_url:
                        break
            if not image_url:
                enc = item.find("enclosure")
                if enc is not None and "image" in enc.get("type", ""):
                    image_url = enc.get("url", "")

            if image_url:
                image_url = _upgrade_bbc_image(image_url)

            if title and "[Removed]" not in title:
                items.append({
                    "title"       : title,
                    "description" : desc[:250] if desc else "",
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
    semua = []
    for url in RSS_FEEDS.values():
        semua.extend(_fetch_rss(url))

    filtered = _filter_topik(semua, topik)
    if not filtered:
        log.warning(f"Tidak ada berita untuk topik '{topik}', pakai berita umum")
        seen = set()
        for a in semua:
            if a["title"] not in seen:
                seen.add(a["title"])
                filtered.append(a)

    log.info(f"RSS pundit '{topik}': {len(filtered[:jumlah])} berita ditemukan.")
    return filtered[:jumlah]


def get_topik_pundit_hari_ini() -> str:
    from datetime import datetime
    hari = datetime.now().weekday()
    rotasi = {
        0: "timnas",
        1: "liga_champion",
        2: "manchester_united",
        3: "liga1",
        4: "timnas",
        5: "liga1",
        6: "liga_champion",
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
            baris.append(f"   {b['description'][:200]}")
        if b.get("source"):
            baris.append(f"   Sumber: {b['source']}")
    return "\n".join(baris)
