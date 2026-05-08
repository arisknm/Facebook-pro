"""
Publisher konten ke Threads via Meta Threads API.
Docs: https://developers.facebook.com/docs/threads

Setup:
1. Buat Meta App → Tambahkan produk "Threads API"
2. OAuth: minta scope threads_basic + threads_content_publish
3. Simpan THREADS_USER_ID dan THREADS_ACCESS_TOKEN ke .env / GitHub Secrets

Batas posting:
- Caption: maks 500 karakter
- 250 post per 24 jam per pengguna
- Gambar: URL publik (JPEG/PNG/WebP, maks 8 MB)
"""
import time
import requests
from config import THREADS_USER_ID, THREADS_ACCESS_TOKEN

THREADS_BASE = "https://graph.threads.net/v1.0"
CAPTION_MAX  = 500


def _check_config():
    if not THREADS_USER_ID or not THREADS_ACCESS_TOKEN:
        raise ValueError(
            "THREADS_USER_ID dan THREADS_ACCESS_TOKEN harus diisi di .env / GitHub Secrets"
        )


def _raise_threads_error(resp: requests.Response):
    try:
        err  = resp.json().get("error", {})
        code = err.get("code", resp.status_code)
        msg  = err.get("message", resp.text[:200])
        raise requests.HTTPError(f"Threads API error {code}: {msg}", response=resp)
    except (ValueError, KeyError):
        resp.raise_for_status()


def _potong_caption(caption: str) -> str:
    """Potong caption agar tidak melebihi 500 karakter Threads."""
    if len(caption) <= CAPTION_MAX:
        return caption
    return caption[:CAPTION_MAX - 3].rsplit(" ", 1)[0] + "..."


def _tunggu_container(container_id: str, max_coba: int = 8, interval: int = 4) -> bool:
    """Tunggu container Threads siap di-publish. Return True jika FINISHED."""
    for _ in range(max_coba):
        resp = requests.get(
            f"{THREADS_BASE}/{container_id}",
            params={
                "fields": "status,error_message",
                "access_token": THREADS_ACCESS_TOKEN,
            },
            timeout=15,
        )
        if not resp.ok:
            return False
        data   = resp.json()
        status = data.get("status", "")
        if status == "FINISHED":
            return True
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Container Threads gagal: {data.get('error_message', status)}")
        time.sleep(interval)
    return False  # timeout, coba publish saja


def _buat_container(media_type: str, caption: str, **kwargs) -> str:
    """Buat media container Threads, return container_id."""
    _check_config()
    params = {
        "media_type"  : media_type,
        "text"        : _potong_caption(caption),
        "access_token": THREADS_ACCESS_TOKEN,
        **kwargs,
    }
    resp = requests.post(
        f"{THREADS_BASE}/{THREADS_USER_ID}/threads",
        params=params,
        timeout=30,
    )
    if not resp.ok:
        _raise_threads_error(resp)
    return resp.json()["id"]


def _publish(container_id: str) -> dict:
    """Publish container ke Threads."""
    resp = requests.post(
        f"{THREADS_BASE}/{THREADS_USER_ID}/threads_publish",
        params={
            "creation_id" : container_id,
            "access_token": THREADS_ACCESS_TOKEN,
        },
        timeout=30,
    )
    if not resp.ok:
        _raise_threads_error(resp)
    return resp.json()


# --------------------------------------------------------------------------- #
#  FUNGSI PUBLIK
# --------------------------------------------------------------------------- #

def post_teks(caption: str) -> dict:
    """Post teks saja ke Threads."""
    _check_config()
    cid = _buat_container("TEXT", caption)
    time.sleep(2)
    return _publish(cid)


def post_dengan_gambar(caption: str, image_url: str) -> dict:
    """Post gambar + caption ke Threads (image_url harus publik)."""
    _check_config()
    cid = _buat_container("IMAGE", caption, image_url=image_url)
    _tunggu_container(cid)
    return _publish(cid)


def post_dengan_video_url(caption: str, video_url: str) -> dict:
    """Post video ke Threads via URL publik."""
    _check_config()
    cid = _buat_container("VIDEO", caption, video_url=video_url)
    # Video perlu waktu lebih lama untuk diproses
    _tunggu_container(cid, max_coba=15, interval=6)
    return _publish(cid)


def cek_token() -> dict:
    """Verifikasi token Threads dan ambil info profil."""
    _check_config()
    resp = requests.get(
        f"{THREADS_BASE}/{THREADS_USER_ID}",
        params={
            "fields"       : "id,username,threads_profile_picture_url,threads_biography",
            "access_token" : THREADS_ACCESS_TOKEN,
        },
        timeout=10,
    )
    if not resp.ok:
        _raise_threads_error(resp)
    return resp.json()
