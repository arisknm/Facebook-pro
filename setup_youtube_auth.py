"""
Setup otomatis YouTube OAuth — jalankan sekali saja.
Script ini akan membuka browser, minta izin akses YouTube,
lalu menyimpan REFRESH_TOKEN langsung ke file .env.

Jalankan:
    pip install google-auth-oauthlib
    python setup_youtube_auth.py
"""
import os
import json
import webbrowser
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
import urllib.request
import urllib.error

# ------------------------------------------------------------------ #
#  KONFIGURASI
# ------------------------------------------------------------------ #
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
REDIRECT_URI = "http://localhost:8080/callback"
AUTH_URL     = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL    = "https://oauth2.googleapis.com/token"
ENV_FILE     = Path(".env")


# ------------------------------------------------------------------ #
#  BACA CLIENT ID & SECRET
# ------------------------------------------------------------------ #
def baca_env(key: str) -> str:
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return ""


def tulis_env(key: str, value: str):
    """Tulis atau update satu baris KEY=VALUE di .env."""
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(new_lines) + "\n")


# ------------------------------------------------------------------ #
#  HTTP SERVER LOKAL (tangkap callback OAuth)
# ------------------------------------------------------------------ #
_auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            _auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"""
            <html><body style="font-family:sans-serif;text-align:center;padding:60px">
            <h2 style="color:green">&#10003; Autentikasi Berhasil!</h2>
            <p>Refresh token sudah disimpan ke file .env</p>
            <p>Kamu bisa tutup tab ini.</p>
            </body></html>
            """)
        else:
            error = params.get("error", ["unknown"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<h2>Error: {error}</h2>".encode())

    def log_message(self, *args):
        pass  # sembunyikan log request


# ------------------------------------------------------------------ #
#  MAIN
# ------------------------------------------------------------------ #
def main():
    global _auth_code

    print("=" * 55)
    print("  SETUP YOUTUBE OAUTH — SEKALI JALAN")
    print("=" * 55)

    # Ambil Client ID & Secret dari .env atau tanya user
    client_id = baca_env("YOUTUBE_CLIENT_ID")
    client_secret = baca_env("YOUTUBE_CLIENT_SECRET")

    if not client_id:
        client_id = input("\nMasukkan YOUTUBE_CLIENT_ID  : ").strip()
        tulis_env("YOUTUBE_CLIENT_ID", client_id)

    if not client_secret:
        client_secret = input("Masukkan YOUTUBE_CLIENT_SECRET: ").strip()
        tulis_env("YOUTUBE_CLIENT_SECRET", client_secret)

    # Pastikan redirect URI sudah didaftarkan di Google Cloud
    print(f"\nPastikan redirect URI ini sudah didaftarkan di Google Cloud Console:")
    print(f"  → {REDIRECT_URI}\n")

    # Bangun URL otorisasi
    params = {
        "client_id"     : client_id,
        "redirect_uri"  : REDIRECT_URI,
        "response_type" : "code",
        "scope"         : " ".join(SCOPES),
        "access_type"   : "offline",
        "prompt"        : "consent",
    }
    auth_link = f"{AUTH_URL}?{urlencode(params)}"

    # Buka browser otomatis
    print("Membuka browser untuk login Google...")
    webbrowser.open(auth_link)
    print("Jika browser tidak terbuka, buka URL ini secara manual:")
    print(f"  {auth_link}\n")

    # Tunggu callback di localhost:8080
    print("Menunggu otorisasi... (jangan tutup terminal ini)")
    server = HTTPServer(("localhost", 8080), CallbackHandler)
    server.handle_request()  # tunggu satu request (callback)

    if not _auth_code:
        print("\nGagal mendapatkan authorization code.")
        return

    # Tukar code → refresh token
    print("\nMendapatkan refresh token...")
    data = urlencode({
        "code"          : _auth_code,
        "client_id"     : client_id,
        "client_secret" : client_secret,
        "redirect_uri"  : REDIRECT_URI,
        "grant_type"    : "authorization_code",
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            token_data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Error: {e.read().decode()}")
        return

    refresh_token = token_data.get("refresh_token", "")
    if not refresh_token:
        print("Refresh token tidak ditemukan di respons.")
        print("Pastikan parameter 'prompt=consent' dan 'access_type=offline' sudah benar.")
        return

    # Simpan ke .env
    tulis_env("YOUTUBE_REFRESH_TOKEN", refresh_token)

    print("\n" + "=" * 55)
    print("  BERHASIL! Refresh token disimpan ke .env")
    print("=" * 55)
    print(f"\nYOUTUBE_REFRESH_TOKEN={refresh_token[:30]}...")
    print("\nSekarang jalankan: python main.py jadwal")


if __name__ == "__main__":
    main()
