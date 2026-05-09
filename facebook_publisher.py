"""
Publisher konten ke Facebook Page via Graph API.
"""
import os
import requests
from config import FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN

GRAPH_BASE = "https://graph.facebook.com/v19.0"


def _check_config():
    if not FACEBOOK_PAGE_ID or not FACEBOOK_ACCESS_TOKEN:
        raise ValueError(
            "FACEBOOK_PAGE_ID dan FACEBOOK_ACCESS_TOKEN harus diisi di .env"
        )


def _raise_facebook_error(resp: requests.Response):
    """Raise exception dengan pesan error Facebook yang jelas."""
    try:
        err = resp.json().get("error", {})
        code = err.get("code", resp.status_code)
        msg = err.get("message", resp.text[:200])
        subcode = err.get("error_subcode", "")
        hint = ""
        if code == 190 or subcode in (463, 467):
            hint = "\n→ Token expired! Buat token baru di: https://developers.facebook.com/tools/explorer/"
        elif code == 200:
            hint = "\n→ Token tidak punya izin pages_manage_posts. Tambahkan permission tersebut."
        elif code == 100:
            hint = f"\n→ Page ID salah atau tidak ditemukan: {FACEBOOK_PAGE_ID}"
        raise requests.HTTPError(
            f"Facebook API error {code}: {msg}{hint}", response=resp
        )
    except (ValueError, KeyError):
        resp.raise_for_status()


def cek_token() -> dict:
    """Verifikasi token dan ambil info page. Return dict dengan status."""
    _check_config()
    resp = requests.get(
        f"{GRAPH_BASE}/me",
        params={"access_token": FACEBOOK_ACCESS_TOKEN, "fields": "id,name"},
        timeout=10,
    )
    if not resp.ok:
        _raise_facebook_error(resp)
    me = resp.json()

    page_resp = requests.get(
        f"{GRAPH_BASE}/{FACEBOOK_PAGE_ID}",
        params={"access_token": FACEBOOK_ACCESS_TOKEN, "fields": "id,name,fan_count"},
        timeout=10,
    )
    if not page_resp.ok:
        _raise_facebook_error(page_resp)
    page = page_resp.json()

    return {"token_user": me, "page": page, "status": "OK"}


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
    if not resp.ok:
        _raise_facebook_error(resp)
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
    if not resp.ok:
        _raise_facebook_error(resp)
    return resp.json()


def post_dengan_video(caption: str, url_video: str, judul: str = "") -> dict:
    """Upload video ke Facebook Page via URL publik."""
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
    if not resp.ok:
        _raise_facebook_error(resp)
    return resp.json()


def upload_video_file(caption: str, file_path: str, judul: str = "") -> dict:
    """Upload file video lokal (MP4) ke Facebook Page via multipart."""
    _check_config()
    data = {
        "description": caption,
        "access_token": FACEBOOK_ACCESS_TOKEN,
    }
    if judul:
        data["title"] = judul
    with open(file_path, "rb") as f:
        files = {"source": (os.path.basename(file_path), f, "video/mp4")}
        resp = requests.post(
            f"{GRAPH_BASE}/{FACEBOOK_PAGE_ID}/videos",
            data=data,
            files=files,
            timeout=300,
        )
    if not resp.ok:
        _raise_facebook_error(resp)
    return resp.json()


def upload_reels(caption: str, file_path: str, judul: str = "") -> dict:
    """Upload video sebagai Facebook Reels (vertical 9:16) via Reels API 3-langkah.
    Step 1: Initialize → dapatkan video_id + upload_url
    Step 2: Upload binary ke upload_url
    Step 3: Publish dengan description
    """
    _check_config()
    file_size = os.path.getsize(file_path)

    # Step 1 — Initialize
    init_resp = requests.post(
        f"{GRAPH_BASE}/{FACEBOOK_PAGE_ID}/video_reels",
        data={
            "upload_phase": "start",
            "access_token": FACEBOOK_ACCESS_TOKEN,
        },
        timeout=30,
    )
    if not init_resp.ok:
        _raise_facebook_error(init_resp)
    init_data  = init_resp.json()
    video_id   = init_data["video_id"]
    upload_url = init_data["upload_url"]

    # Step 2 — Transfer binary
    with open(file_path, "rb") as f:
        up_resp = requests.post(
            upload_url,
            headers={
                "Authorization": f"OAuth {FACEBOOK_ACCESS_TOKEN}",
                "offset": "0",
                "file_size": str(file_size),
            },
            data=f,
            timeout=300,
        )
    if not up_resp.ok:
        raise requests.HTTPError(
            f"Reels upload transfer gagal: {up_resp.status_code} {up_resp.text[:300]}"
        )

    # Step 3 — Publish
    finish_data: dict = {
        "upload_phase"  : "finish",
        "video_id"      : video_id,
        "video_state"   : "PUBLISHED",
        "description"   : caption[:2200],
        "access_token"  : FACEBOOK_ACCESS_TOKEN,
    }
    if judul:
        finish_data["title"] = judul[:255]
    fin_resp = requests.post(
        f"{GRAPH_BASE}/{FACEBOOK_PAGE_ID}/video_reels",
        data=finish_data,
        timeout=30,
    )
    if not fin_resp.ok:
        _raise_facebook_error(fin_resp)
    return {"video_id": video_id, **fin_resp.json()}


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
    if not resp.ok:
        _raise_facebook_error(resp)
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
    if not resp.ok:
        _raise_facebook_error(resp)
    return resp.json()
