"""
Publisher konten ke Facebook Page via Graph API.
"""
import requests
from config import FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN

GRAPH_BASE = "https://graph.facebook.com/v19.0"


def _check_config():
    if not FACEBOOK_PAGE_ID or not FACEBOOK_ACCESS_TOKEN:
        raise ValueError(
            "FACEBOOK_PAGE_ID dan FACEBOOK_ACCESS_TOKEN harus diisi di .env"
        )


def post_teks(caption: str) -> dict:
    """Upload post teks ke Facebook Page."""
    _check_config()
    resp = requests.post(
        f"{GRAPH_BASE}/{FACEBOOK_PAGE_ID}/feed",
        data={
            "message": caption,
            "access_token": FACEBOOK_ACCESS_TOKEN,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def post_dengan_gambar(caption: str, url_gambar: str) -> dict:
    """Upload post dengan gambar ke Facebook Page."""
    _check_config()
    resp = requests.post(
        f"{GRAPH_BASE}/{FACEBOOK_PAGE_ID}/photos",
        data={
            "caption": caption,
            "url": url_gambar,
            "access_token": FACEBOOK_ACCESS_TOKEN,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def post_dengan_video(caption: str, url_video: str, judul: str = "") -> dict:
    """Upload video ke Facebook Page."""
    _check_config()
    data = {
        "description": caption,
        "file_url": url_video,
        "access_token": FACEBOOK_ACCESS_TOKEN,
    }
    if judul:
        data["title"] = judul
    resp = requests.post(
        f"{GRAPH_BASE}/{FACEBOOK_PAGE_ID}/videos",
        data=data,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def jadwalkan_post(caption: str, timestamp_unix: int, url_gambar: str = "") -> dict:
    """Jadwalkan post di waktu tertentu (Unix timestamp)."""
    _check_config()
    endpoint = "photos" if url_gambar else "feed"
    data = {
        "message" if not url_gambar else "caption": caption,
        "scheduled_publish_time": timestamp_unix,
        "published": "false",
        "access_token": FACEBOOK_ACCESS_TOKEN,
    }
    if url_gambar:
        data["url"] = url_gambar
    resp = requests.post(
        f"{GRAPH_BASE}/{FACEBOOK_PAGE_ID}/{endpoint}",
        data=data,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_page_insights() -> dict:
    """Ambil statistik dasar halaman Facebook."""
    _check_config()
    resp = requests.get(
        f"{GRAPH_BASE}/{FACEBOOK_PAGE_ID}/insights",
        params={
            "metric": "page_fans,page_impressions,page_post_engagements",
            "period": "day",
            "access_token": FACEBOOK_ACCESS_TOKEN,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
