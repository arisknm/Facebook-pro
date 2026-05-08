"""
Generator link affiliate Shopee otomatis.
Daftar: https://affiliate.shopee.co.id/ → dapatkan Affiliate ID kamu.

Format link:
  https://shopee.co.id/search?keyword={keyword}&af_id={affiliate_id}
  atau gunakan link pendek shope.ee yang kamu buat manual di dashboard.
"""
import urllib.parse
from config import SHOPEE_AFFILIATE_ID

# --------------------------------------------------------------------------- #
#  MAPPING TOPIK → KEYWORD PRODUK SHOPEE
# --------------------------------------------------------------------------- #

# Kata kunci produk per kategori konten
_KEYWORD_MAP = {
    "transfer"   : ["jersey bola original", "jersey bola terbaru", "kaos bola"],
    "preview"    : ["jersey bola", "syal bola", "topi bola"],
    "rekap"      : ["jersey bola", "bola futsal", "sepatu bola"],
    "hype"       : ["jersey bola premium", "sepatu bola original"],
    "viral"      : ["bola futsal", "jersey bola murah", "sarung tangan kiper"],
    "polling"    : ["jersey bola", "score board mini", "jersey timnas"],
    "pengingat"  : ["jersey bola", "tv layar lebar nonton bola"],
    "statistik"  : ["jersey bola premium", "sepatu futsal"],
    "klasemen"   : ["jersey liga champion", "bola kulit original"],
    "default"    : ["jersey bola", "sepatu bola", "perlengkapan bola"],
}

# Keyword khusus per nama liga/tim
_LIGA_KEYWORD = {
    "premier league" : "jersey premier league",
    "la liga"        : "jersey la liga",
    "serie a"        : "jersey serie a",
    "bundesliga"     : "jersey bundesliga",
    "liga 1"         : "jersey timnas indonesia",
    "champions"      : "jersey liga champions",
    "manchester"     : "jersey manchester",
    "barcelona"      : "jersey barcelona",
    "real madrid"    : "jersey real madrid",
    "liverpool"      : "jersey liverpool",
    "chelsea"        : "jersey chelsea",
    "arsenal"        : "jersey arsenal",
    "psg"            : "jersey psg",
    "juventus"       : "jersey juventus",
    "ac milan"       : "jersey ac milan",
    "inter milan"    : "jersey inter milan",
    "timnas"         : "jersey timnas indonesia",
    "persija"        : "jersey persija",
    "persib"         : "jersey persib",
}


def buat_link(keyword: str) -> str:
    """Buat satu link affiliate Shopee dengan keyword tertentu."""
    if not SHOPEE_AFFILIATE_ID:
        return ""
    encoded = urllib.parse.quote(keyword)
    return (
        f"https://shopee.co.id/search?keyword={encoded}"
        f"&af_id={SHOPEE_AFFILIATE_ID}&smtt=0&utm_source=an&utm_medium=affiliates"
    )


def _deteksi_keyword(teks: str, tipe: str = "default") -> str:
    """
    Deteksi keyword produk yang paling relevan dari teks konten.
    Cek nama tim/liga dulu, lalu fallback ke kategori tipe konten.
    """
    teks_lower = teks.lower()

    # Cek nama tim/liga spesifik
    for kata, keyword in _LIGA_KEYWORD.items():
        if kata in teks_lower:
            return keyword

    # Fallback ke kategori tipe konten
    keywords = _KEYWORD_MAP.get(tipe, _KEYWORD_MAP["default"])
    return keywords[0]


def buat_blok_affiliate(teks_konten: str, tipe: str = "default") -> str:
    """
    Buat blok teks affiliate untuk ditempel di akhir caption.
    Return string kosong jika SHOPEE_AFFILIATE_ID tidak diset.
    """
    if not SHOPEE_AFFILIATE_ID:
        return ""

    keyword  = _deteksi_keyword(teks_konten, tipe)
    link     = buat_link(keyword)

    return (
        f"\n\n🛍️ Belanja perlengkapan bola di Shopee:\n"
        f"👉 {link}\n"
        f"🔍 Cari: \"{keyword}\""
    )


def tambah_affiliate_ke_caption(caption: str, tipe: str = "default") -> str:
    """Append blok affiliate ke caption. Idempotent (tidak duplikasi)."""
    if not SHOPEE_AFFILIATE_ID or "shopee.co.id" in caption:
        return caption
    blok = buat_blok_affiliate(caption, tipe)
    return caption + blok if blok else caption
