"""
Cara pakai:
  1. Buka: https://developers.facebook.com/tools/explorer/
  2. Pilih app Threads kamu di dropdown "Meta App"
  3. Tambahkan permission: threads_basic, threads_content_publish
  4. Klik "Generate Access Token" → copy token pendek (mulai dengan EAA atau angka)
  5. Jalankan: python setup_threads_token.py <short_token> <app_secret>

Script ini menukar short-lived token (1-2 jam) menjadi long-lived token (60 hari).
"""
import sys
import requests


THREADS_BASE = "https://graph.threads.net"


def tukar_ke_long_lived(short_token: str, app_secret: str) -> dict:
    """Tukar short-lived token ke long-lived token (60 hari)."""
    resp = requests.get(
        f"{THREADS_BASE}/access_token",
        params={
            "grant_type"    : "th_exchange_token",
            "client_secret" : app_secret,
            "access_token"  : short_token,
        },
        timeout=15,
    )
    if not resp.ok:
        print(f"ERROR: {resp.status_code} — {resp.text}")
        sys.exit(1)
    return resp.json()


def cek_token(token: str) -> dict:
    """Verifikasi token dan ambil info user Threads."""
    resp = requests.get(
        f"{THREADS_BASE}/v1.0/me",
        params={
            "fields"       : "id,username,threads_profile_picture_url",
            "access_token" : token,
        },
        timeout=10,
    )
    if not resp.ok:
        print(f"Gagal cek token: {resp.text}")
        return {}
    return resp.json()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    short_token = sys.argv[1].strip()
    app_secret  = sys.argv[2].strip()

    print("Menukar ke long-lived token (60 hari)...")
    hasil = tukar_ke_long_lived(short_token, app_secret)

    long_token = hasil.get("access_token", "")
    expires_in = hasil.get("expires_in", 0)
    hari       = expires_in // 86400 if expires_in else "~60"

    if not long_token:
        print(f"Gagal: {hasil}")
        sys.exit(1)

    # Verifikasi token baru
    info = cek_token(long_token)
    username = info.get("username", "tidak diketahui")
    user_id  = info.get("id", "")

    print("\n" + "=" * 60)
    print("✅ BERHASIL! Long-lived token Threads:")
    print("=" * 60)
    print(f"Username  : @{username}")
    print(f"User ID   : {user_id}")
    print(f"Berlaku   : {hari} hari")
    print()
    print("─── Simpan ke GitHub Secrets ──────────────────────────────")
    print(f"THREADS_USER_ID      = {user_id}")
    print(f"THREADS_ACCESS_TOKEN = {long_token}")
    print("=" * 60)
    print()
    print("Tambahkan kedua nilai di atas ke:")
    print("GitHub → Settings → Secrets and variables → Actions → New secret")
    print()
    print("Token ini berlaku ±60 hari. Setelah habis, ulangi proses ini.")


if __name__ == "__main__":
    main()
