"""
Publisher konten ke YouTube via Data API v3.
"""
import os
import json
import time
import math
import logging
import requests
from datetime import datetime, timezone
from config import (
    YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET,
    YOUTUBE_REFRESH_TOKEN,
    YOUTUBE_CHANNEL_ID,
)

log = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
YT_BASE = "https://www.googleapis.com/youtube/v3"
YT_UPLOAD = "https://www.googleapis.com/upload/youtube/v3"

CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB per chunk
MAX_RETRY = 5


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


# --------------------------------------------------------------------------- #
#  UPLOAD VIDEO
# --------------------------------------------------------------------------- #

def upload_video(
    file_path: str,
    judul: str,
    deskripsi: str,
    tags: list[str],
    kategori_id: str = "17",  # 17 = Sports
    privasi: str = "public",
    waktu_publish: datetime | None = None,
) -> dict:
    """
    Upload video ke YouTube dengan chunked upload dan progress.

    Args:
        file_path     : Path ke file video lokal.
        judul         : Judul video (maks 100 karakter).
        deskripsi     : Deskripsi video.
        tags          : Daftar tag (maks 30).
        kategori_id   : ID kategori YouTube (17 = Sports).
        privasi       : 'public', 'private', atau 'unlisted'.
        waktu_publish : Jadwal publikasi (datetime). Jika diisi, privasi
                        otomatis diset 'private' dengan publishAt.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File tidak ditemukan: {file_path}")

    file_size = os.path.getsize(file_path)
    access_token = _get_access_token()

    status_block: dict = {"privacyStatus": privasi, "selfDeclaredMadeForKids": False}
    if waktu_publish is not None:
        # YouTube mensyaratkan privacyStatus = private untuk video terjadwal
        status_block["privacyStatus"] = "private"
        if waktu_publish.tzinfo is None:
            waktu_publish = waktu_publish.replace(tzinfo=timezone.utc)
        status_block["publishAt"] = waktu_publish.isoformat()

    metadata = {
        "snippet": {
            "title": judul[:100],
            "description": deskripsi,
            "tags": tags[:30],
            "categoryId": kategori_id,
            "defaultLanguage": "id",
        },
        "status": status_block,
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Upload-Content-Type": "video/*",
        "X-Upload-Content-Length": str(file_size),
    }

    # Inisiasi resumable upload → dapatkan upload URL
    init_resp = requests.post(
        f"{YT_UPLOAD}/videos?uploadType=resumable&part=snippet,status",
        headers=headers,
        data=json.dumps(metadata),
        timeout=30,
    )
    init_resp.raise_for_status()
    upload_url = init_resp.headers["Location"]

    # Upload file per chunk dengan progress dan retry
    return _upload_chunks(upload_url, file_path, file_size, access_token)


def _upload_chunks(upload_url: str, file_path: str, file_size: int, access_token: str) -> dict:
    """Kirim file dalam potongan 8 MB dengan progress dan retry."""
    total_chunks = math.ceil(file_size / CHUNK_SIZE)
    uploaded = 0

    with open(file_path, "rb") as f:
        chunk_num = 0
        while uploaded < file_size:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break

            end = uploaded + len(chunk) - 1
            content_range = f"bytes {uploaded}-{end}/{file_size}"

            for attempt in range(1, MAX_RETRY + 1):
                try:
                    resp = requests.put(
                        upload_url,
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Range": content_range,
                            "Content-Type": "video/*",
                        },
                        data=chunk,
                        timeout=300,
                    )

                    # 308 = Resume Incomplete (chunk diterima, lanjut)
                    # 200/201 = selesai
                    if resp.status_code in (200, 201):
                        pct = 100
                        log.info(f"Upload selesai 100% — {file_size / 1_048_576:.1f} MB")
                        return resp.json()
                    elif resp.status_code == 308:
                        uploaded += len(chunk)
                        chunk_num += 1
                        pct = int(uploaded / file_size * 100)
                        log.info(
                            f"  Chunk {chunk_num}/{total_chunks} — {pct}% "
                            f"({uploaded / 1_048_576:.1f}/{file_size / 1_048_576:.1f} MB)"
                        )
                        break  # lanjut chunk berikutnya
                    else:
                        resp.raise_for_status()

                except (requests.ConnectionError, requests.Timeout) as exc:
                    wait = 2 ** attempt
                    log.warning(f"Chunk {chunk_num + 1} gagal (percobaan {attempt}/{MAX_RETRY}): {exc} — retry dalam {wait}s")
                    if attempt == MAX_RETRY:
                        raise
                    time.sleep(wait)

    raise RuntimeError("Upload selesai tapi respons tidak diterima.")


# --------------------------------------------------------------------------- #
#  UPDATE METADATA
# --------------------------------------------------------------------------- #

def perbarui_video(
    video_id: str,
    judul: str | None = None,
    deskripsi: str | None = None,
    tags: list[str] | None = None,
    privasi: str | None = None,
    kategori_id: str | None = None,
) -> dict:
    """
    Update metadata video yang sudah ada.

    Hanya field yang diisi (bukan None) yang akan diperbarui.
    Catatan: YouTube API mewajibkan snippet.title dan snippet.categoryId
    selalu disertakan jika snippet di-update.
    """
    access_token = _get_access_token()

    # Ambil data video saat ini agar title/categoryId selalu tersedia
    current = _get_video_raw(video_id, access_token)
    snippet = current.get("snippet", {})
    status = current.get("status", {})

    update_parts = []
    body: dict = {"id": video_id}

    if any(v is not None for v in [judul, deskripsi, tags, kategori_id]):
        body["snippet"] = {
            "title": (judul[:100] if judul else snippet.get("title", ""))[:100],
            "description": deskripsi if deskripsi is not None else snippet.get("description", ""),
            "tags": tags[:30] if tags is not None else snippet.get("tags", []),
            "categoryId": kategori_id or snippet.get("categoryId", "17"),
            "defaultLanguage": snippet.get("defaultLanguage", "id"),
        }
        update_parts.append("snippet")

    if privasi is not None:
        body["status"] = {**status, "privacyStatus": privasi}
        update_parts.append("status")

    if not update_parts:
        return {"info": "Tidak ada perubahan yang diminta."}

    resp = requests.put(
        f"{YT_BASE}/videos?part={','.join(update_parts)}",
        headers={"Authorization": f"Bearer {access_token}"},
        json=body,
        timeout=15,
    )
    resp.raise_for_status()
    log.info(f"Metadata video {video_id} diperbarui.")
    return resp.json()


def _get_video_raw(video_id: str, access_token: str) -> dict:
    """Ambil data mentah video (snippet + status)."""
    resp = requests.get(
        f"{YT_BASE}/videos",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"part": "snippet,status", "id": video_id},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        raise ValueError(f"Video tidak ditemukan: {video_id}")
    return items[0]


# --------------------------------------------------------------------------- #
#  STATISTIK
# --------------------------------------------------------------------------- #

def get_video_stats(video_id: str) -> dict:
    """
    Ambil statistik sebuah video: views, likes, komentar, durasi, judul.

    Returns dict dengan kunci: video_id, title, views, likes, comments,
    favorites, duration, published_at, url.
    """
    access_token = _get_access_token()
    resp = requests.get(
        f"{YT_BASE}/videos",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"part": "snippet,statistics,contentDetails", "id": video_id},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        raise ValueError(f"Video tidak ditemukan: {video_id}")

    item = items[0]
    stats = item.get("statistics", {})
    snippet = item.get("snippet", {})
    details = item.get("contentDetails", {})

    return {
        "video_id": video_id,
        "title": snippet.get("title", ""),
        "published_at": snippet.get("publishedAt", ""),
        "duration": details.get("duration", ""),  # format ISO 8601, e.g. PT5M30S
        "views": int(stats.get("viewCount", 0)),
        "likes": int(stats.get("likeCount", 0)),
        "comments": int(stats.get("commentCount", 0)),
        "favorites": int(stats.get("favoriteCount", 0)),
        "url": f"https://youtu.be/{video_id}",
    }


def list_videos(max_results: int = 10) -> list[dict]:
    """
    Ambil daftar video terbaru dari channel.

    Returns list of dict dengan kunci: video_id, title, published_at,
    views, likes, url.
    """
    access_token = _get_access_token()

    # Langkah 1: cari uploads playlist dari channel
    ch_resp = requests.get(
        f"{YT_BASE}/channels",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"part": "contentDetails", "id": YOUTUBE_CHANNEL_ID},
        timeout=10,
    )
    ch_resp.raise_for_status()
    ch_items = ch_resp.json().get("items", [])
    if not ch_items:
        raise ValueError("Channel tidak ditemukan atau YOUTUBE_CHANNEL_ID salah.")
    uploads_playlist = ch_items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # Langkah 2: ambil item dari uploads playlist
    pl_resp = requests.get(
        f"{YT_BASE}/playlistItems",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "part": "snippet",
            "playlistId": uploads_playlist,
            "maxResults": min(max_results, 50),
        },
        timeout=10,
    )
    pl_resp.raise_for_status()
    pl_items = pl_resp.json().get("items", [])
    video_ids = [
        it["snippet"]["resourceId"]["videoId"]
        for it in pl_items
        if it.get("snippet", {}).get("resourceId", {}).get("kind") == "youtube#video"
    ]

    if not video_ids:
        return []

    # Langkah 3: ambil statistik sekaligus (batch)
    stats_resp = requests.get(
        f"{YT_BASE}/videos",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "part": "snippet,statistics",
            "id": ",".join(video_ids),
        },
        timeout=15,
    )
    stats_resp.raise_for_status()

    result = []
    for item in stats_resp.json().get("items", []):
        vid = item["id"]
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})
        result.append({
            "video_id": vid,
            "title": snippet.get("title", ""),
            "published_at": snippet.get("publishedAt", ""),
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "url": f"https://youtu.be/{vid}",
        })

    return result


# --------------------------------------------------------------------------- #
#  CHANNEL & PLAYLIST
# --------------------------------------------------------------------------- #

def get_channel_stats() -> dict:
    """Ambil statistik channel YouTube."""
    access_token = _get_access_token()
    resp = requests.get(
        f"{YT_BASE}/channels",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"part": "statistics,snippet", "id": YOUTUBE_CHANNEL_ID},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return items[0] if items else {}


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
