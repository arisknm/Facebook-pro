"""
Generator link affiliate Shopee otomatis.
Platform: CAWGO (affiliate.shopee.co.id) — app resmi Shopee Indonesia.

Cara mendapatkan SHOPEE_AFFILIATE_ID:
1. Buka app CAWGO → Akun → Ubah Link
2. Tap salah satu produk/penawaran → "Dapatkan Link"
3. Link yang muncul contohnya: https://s.shopee.co.id/XXXXXXXX
4. Bagian "XXXXXXXX" itulah Affiliate ID kamu

Format link yang dipakai:
  https://s.shopee.co.id/{affiliate_id}  ← link pendek (redirect ke produk)
  https://shopee.co.id/search?keyword={keyword}&smtt=0.0.9&utm_source=an&utm_medium=affiliates&af_id={affiliate_id}
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
    """
    Buat link affiliate Shopee dengan keyword tertentu.
    Mendukung 2 format SHOPEE_AFFILIATE_ID:
    - ID pendek (mis. "3AK7xyzABC") → pakai s.shopee.co.id/{id}
    - ID angka panjang (mis. "123456789") → pakai format af_id
    """
    if not SHOPEE_AFFILIATE_ID:
        return ""

    encoded = urllib.parse.quote(keyword)

    # Jika ID terlihat seperti short link code (huruf+angka, ≤12 karakter)
    if len(SHOPEE_AFFILIATE_ID) <= 12 and not SHOPEE_AFFILIATE_ID.isdigit():
        # Format short link CAWGO: s.shopee.co.id/{code}
        # Tambahkan keyword sebagai parameter pencarian setelah redirect
        return (
            f"https://shopee.co.id/search?keyword={encoded}"
            f"&smtt=0.0.9&utm_source=an&utm_medium=affiliates"
            f"&af_id={SHOPEE_AFFILIATE_ID}"
        )
    else:
        # Format ID angka (publisher ID)
        return (
            f"https://shopee.co.id/search?keyword={encoded}"
            f"&smtt=0.0.9&utm_source=an&utm_medium=affiliates"
            f"&af_id={SHOPEE_AFFILIATE_ID}"
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
        f"\n\n🛍️ Dapatkan jersey & perlengkapan bola di Shopee!\n"
        f"👉 {link}\n"
        f"🔍 Cari: \"{keyword}\" — gratis ongkir!"
    )


def tambah_affiliate_ke_caption(caption: str, tipe: str = "default") -> str:
    """Append blok affiliate ke caption. Idempotent (tidak duplikasi)."""
    if not SHOPEE_AFFILIATE_ID or "shopee.co.id" in caption:
        return caption
    blok = buat_blok_affiliate(caption, tipe)
    return caption + blok if blok else caption
