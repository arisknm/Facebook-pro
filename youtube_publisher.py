"""
Publisher konten ke YouTube via Data API v3.
"""
import os
import json
import requests
from config import (
    YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET,
    YOUTUBE_REFRESH_TOKEN,
    YOUTUBE_CHANNEL_ID,
)

TOKEN_URL = "https://oauth2.googleapis.com/token"
YT_BASE = "https://www.googleapis.com/youtube/v3"
YT_UPLOAD = "https://www.googleapis.com/upload/youtube/v3"


def _check_config():
    if not YOUTUBE_CLIENT_ID or not YOUTUBE_CLIENT_SECRET or not YOUTUBE_REFRESH_TOKEN:
        raise ValueError(
            "YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, dan YOUTUBE_REFRESH_TOKEN "
            "harus diisi di .env"
        )


def _get_access_token() -> str:
    """Ambil access token baru menggunakan refresh token."""
    _check_config()
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": YOUTUBE_CLIENT_ID,
            "client_secret": YOUTUBE_CLIENT_SECRET,
            "refresh_token": YOUTUBE_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def upload_video(
    file_path: str,
    judul: str,
    deskripsi: str,
    tags: list[str],
    kategori_id: str = "17",  # 17 = Sports
    privasi: str = "public",
) -> dict:
    """
    Upload video ke YouTube.

    Args:
        file_path: Path ke file video lokal
        judul: Judul video (maks 100 karakter)
        deskripsi: Deskripsi video
        tags: Daftar tag
        kategori_id: ID kategori YouTube (17 = Sports)
        privasi: 'public', 'private', atau 'unlisted'
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File tidak ditemukan: {file_path}")

    access_token = _get_access_token()

    metadata = {
        "snippet": {
            "title": judul[:100],
            "description": deskripsi,
            "tags": tags[:30],
            "categoryId": kategori_id,
            "defaultLanguage": "id",
        },
        "status": {
            "privacyStatus": privasi,
            "selfDeclaredMadeForKids": False,
        },
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Upload-Content-Type": "video/*",
        "X-Upload-Content-Length": str(os.path.getsize(file_path)),
    }

    # Inisiasi upload
    init_resp = requests.post(
        f"{YT_UPLOAD}/videos?uploadType=resumable&part=snippet,status",
        headers=headers,
        data=json.dumps(metadata),
        timeout=30,
    )
    init_resp.raise_for_status()
    upload_url = init_resp.headers["Location"]

    # Upload file
    with open(file_path, "rb") as f:
        upload_resp = requests.put(
            upload_url,
            headers={"Authorization": f"Bearer {access_token}"},
            data=f,
            timeout=600,
        )
    upload_resp.raise_for_status()
    return upload_resp.json()


def buat_playlist(nama: str, deskripsi: str = "", privasi: str = "public") -> dict:
    """Buat playlist baru di YouTube."""
    access_token = _get_access_token()
    resp = requests.post(
        f"{YT_BASE}/playlists?part=snippet,status",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "snippet": {"title": nama, "description": deskripsi},
            "status": {"privacyStatus": privasi},
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def tambah_ke_playlist(video_id: str, playlist_id: str) -> dict:
    """Tambahkan video ke playlist."""
    access_token = _get_access_token()
    resp = requests.post(
        f"{YT_BASE}/playlistItems?part=snippet",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_channel_stats() -> dict:
    """Ambil statistik channel YouTube."""
    access_token = _get_access_token()
    resp = requests.get(
        f"{YT_BASE}/channels",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "part": "statistics,snippet",
            "id": YOUTUBE_CHANNEL_ID,
        },
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return items[0] if items else {}


def perbarui_thumbnail(video_id: str, thumbnail_path: str) -> bool:
    """Upload thumbnail kustom untuk video."""
    if not os.path.exists(thumbnail_path):
        raise FileNotFoundError(f"Thumbnail tidak ditemukan: {thumbnail_path}")

    access_token = _get_access_token()
    with open(thumbnail_path, "rb") as f:
        resp = requests.post(
            f"{YT_UPLOAD}/thumbnails/set?videoId={video_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            data=f,
            timeout=60,
        )
    resp.raise_for_status()
    return True
