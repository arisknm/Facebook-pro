"""
Generate Facebook Page Access Token permanen (tidak pernah expire).

Cara pakai:
  python get_permanent_token.py USER_TOKEN

Atau lewat GitHub Actions (workflow token-refresh.yml).
Auto-refresh: jika tidak ada USER_TOKEN, gunakan FACEBOOK_LONG_TOKEN dari env.
"""
import sys
import os
import requests

APP_ID     = "1452223299431141"
APP_SECRET = "0886f0c492a1c02cfce06f899d4c98b7"
PAGE_ID    = "1164718290049590"
GRAPH      = "https://graph.facebook.com/v19.0"


def exchange_long_lived(short_token: str) -> str:
    """Tukar short-lived user token → long-lived user token (60 hari)."""
    resp = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "grant_type"        : "fb_exchange_token",
            "client_id"         : APP_ID,
            "client_secret"     : APP_SECRET,
            "fb_exchange_token" : short_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise ValueError(f"Error: {data['error']['message']}")
    return data["access_token"]


def get_page_token(long_lived_user_token: str) -> str:
    """Ambil Page Access Token permanen dari long-lived user token."""
    resp = requests.get(
        f"{GRAPH}/me/accounts",
        params={"access_token": long_lived_user_token},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    pages = data.get("data", [])
    for page in pages:
        if page.get("id") == PAGE_ID:
            return page["access_token"]
    # Jika page ID tidak cocok, tampilkan semua halaman
    print("\nHalaman yang ditemukan:")
    for p in pages:
        print(f"  - {p.get('name')} (ID: {p.get('id')})")
    raise ValueError(f"Halaman dengan ID {PAGE_ID} tidak ditemukan.")


def update_github_secret(secret_name: str, secret_value: str):
    """Update secret di GitHub menggunakan GH_PAT atau GITHUB_TOKEN."""
    try:
        import base64
        from nacl import encoding, public

        # Utamakan GH_PAT (PAT dengan permission secrets:write)
        gh_token = os.environ.get("GH_PAT", "").strip()
        if not gh_token:
            gh_token = os.environ.get("GITHUB_TOKEN", "").strip()
        if not gh_token:
            print(f"  ⚠ Token GitHub tidak tersedia, skip update {secret_name}.")
            return

        session = requests.Session()
        session.headers.update({
            "Authorization"       : f"Bearer {gh_token}",
            "Accept"              : "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

        r = session.get(
            "https://api.github.com/repos/arisknm/Facebook-pro/actions/secrets/public-key"
        )
        r.raise_for_status()
        key_id  = r.json()["key_id"]
        pub_key = r.json()["key"]

        pk        = public.PublicKey(pub_key.encode(), encoding.Base64Encoder())
        box       = public.SealedBox(pk)
        encrypted = base64.b64encode(box.encrypt(secret_value.encode())).decode()

        r2 = session.put(
            f"https://api.github.com/repos/arisknm/Facebook-pro/actions/secrets/{secret_name}",
            json={"encrypted_value": encrypted, "key_id": key_id},
        )
        if r2.status_code in (201, 204):
            print(f"  ✓ GitHub Secret {secret_name} diupdate otomatis")
        else:
            print(f"  ✗ Gagal update {secret_name}: {r2.status_code} — {r2.text}")
    except Exception as e:
        print(f"  ⚠ Tidak bisa update GitHub Secret {secret_name}: {e}")


def main():
    # Ambil user_token dari argumen atau env FACEBOOK_LONG_TOKEN (auto-refresh)
    if len(sys.argv) >= 2:
        user_token = sys.argv[1].strip()
        mode = "manual"
    else:
        user_token = os.environ.get("FACEBOOK_LONG_TOKEN", "").strip()
        mode = "auto"
        if not user_token:
            print("Penggunaan: python get_permanent_token.py USER_TOKEN")
            print("\nAtau set env FACEBOOK_LONG_TOKEN untuk auto-refresh.")
            print("\nCara dapat USER_TOKEN:")
            print("1. Buka https://developers.facebook.com/tools/explorer/")
            print("2. Pilih app Football Automation")
            print("3. Pastikan dropdown: Token Pengguna (bukan Token Halaman)")
            print("4. Klik Generate Access Token")
            print("5. Salin token → jalankan script ini")
            sys.exit(1)

    print("=" * 55)
    print("  GENERATE TOKEN FACEBOOK PERMANEN")
    if mode == "auto":
        print("  Mode: AUTO-REFRESH (dari FACEBOOK_LONG_TOKEN)")
    print("=" * 55)

    print("\n1. Menukar ke long-lived user token (60 hari)...")
    try:
        long_token = exchange_long_lived(user_token)
        print("   ✓ Long-lived user token didapat")
    except Exception as e:
        print(f"   ✗ Gagal: {e}")
        sys.exit(1)

    # Simpan long-lived token ke secret agar bisa auto-refresh bulan depan
    print("\n2. Menyimpan long-lived token untuk auto-refresh...")
    update_github_secret("FACEBOOK_LONG_TOKEN", long_token)

    print("\n3. Mengambil Page Access Token permanen...")
    try:
        page_token = get_page_token(long_token)
        print("   ✓ Page Access Token permanen didapat!")
    except Exception as e:
        print(f"   ✗ Gagal: {e}")
        sys.exit(1)

    print("\n4. Menyimpan token...")
    print(f"\nTOKEN PERMANEN:\n{page_token}\n")

    # Update FACEBOOK_ACCESS_TOKEN di GitHub Secrets
    update_github_secret("FACEBOOK_ACCESS_TOKEN", page_token)

    # Update .env lokal jika ada
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            content = f.read()
        lines = content.splitlines()
        new_lines = []
        for line in lines:
            if line.startswith("FACEBOOK_ACCESS_TOKEN="):
                new_lines.append(f"FACEBOOK_ACCESS_TOKEN={page_token}")
            else:
                new_lines.append(line)
        with open(env_path, "w") as f:
            f.write("\n".join(new_lines))
        print("  ✓ .env lokal diupdate")

    print("\n" + "=" * 55)
    print("  SELESAI! Token permanen sudah tersimpan.")
    print("  Token ini TIDAK AKAN EXPIRE selama app aktif.")
    print("=" * 55)


if __name__ == "__main__":
    main()
