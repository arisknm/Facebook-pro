"""
Setup otomatis GitHub Actions Secrets.
Jalankan sekali dari GitHub Codespaces — semua secrets langsung tersimpan.

Cara pakai:
  python setup_github_secrets.py
"""
import base64
import json
import os
import sys
import requests
from nacl import encoding, public

# ------------------------------------------------------------------ #
#  SECRETS YANG AKAN DISIMPAN
# ------------------------------------------------------------------ #
SECRETS = {
    "GEMINI_API_KEY"       : "AIzaSyDgDOEkZEsILRgWL3BSWZdTDJa4du45U7Y",
    "FACEBOOK_PAGE_ID"     : "1164718290049590",
    "FACEBOOK_ACCESS_TOKEN": "EAAXfJflJLCkBRY7FS88HKsMl9TQmVrph5Rzfw9j2fwVHrOEH5S9KmPUL8qbWDdkdKOIUbsZAQd6ZCINUq6kaisXMqIe7pp0C6YLpLsXK9PP7TZBQrtjC2rGJzEefzd3UAdMMW7tZAxa515ObrhvJl9toBgWtib3ZBZBvDYJZAfCEeprFo1ODnyNz27d5mbZBWwnvC3zf8Lut3auwBJOChA8SHWrBLLJqJZBdxoihB5nsZD",
    "FOOTBALL_API_KEY"     : "26faf2a8d79465cbfc88b0419880ba00",
    "NEWS_API_KEY"         : "98288eb6ce0145eaaf217564d416d446",
}

REPO_OWNER = "arisknm"
REPO_NAME  = "Facebook-pro"


# ------------------------------------------------------------------ #
#  ENKRIPSI & UPLOAD
# ------------------------------------------------------------------ #

def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """Enkripsi secret menggunakan repo public key (NaCl sealed box)."""
    pub_key = public.PublicKey(public_key_b64.encode(), encoding.Base64Encoder())
    sealed  = public.SealedBox(pub_key)
    encrypted = sealed.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def get_public_key(session: requests.Session) -> tuple[str, str]:
    """Ambil public key repository untuk enkripsi secrets."""
    r = session.get(
        f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/secrets/public-key"
    )
    r.raise_for_status()
    data = r.json()
    return data["key_id"], data["key"]


def set_secret(session: requests.Session, key_id: str, pub_key: str, name: str, value: str):
    """Upload satu secret ke GitHub Actions."""
    encrypted = encrypt_secret(pub_key, value)
    r = session.put(
        f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/secrets/{name}",
        json={"encrypted_value": encrypted, "key_id": key_id},
    )
    if r.status_code in (201, 204):
        print(f"  ✓ {name}")
    else:
        print(f"  ✗ {name} — {r.status_code}: {r.text[:80]}")


# ------------------------------------------------------------------ #
#  MAIN
# ------------------------------------------------------------------ #

def main():
    print("=" * 55)
    print("  SETUP GITHUB ACTIONS SECRETS OTOMATIS")
    print("=" * 55)
    print(f"\nRepository: {REPO_OWNER}/{REPO_NAME}\n")

    # Cek token dari environment (Codespaces otomatis punya GITHUB_TOKEN)
    token = os.environ.get("GITHUB_TOKEN", "").strip()

    if not token:
        print("GitHub token tidak ditemukan otomatis.")
        print("Buat token di: github.com → Settings → Developer settings")
        print("→ Personal access tokens → Fine-grained tokens")
        print("→ Permissions: Secrets (read & write)\n")
        token = input("Paste GitHub Token: ").strip()

    if not token:
        print("Token diperlukan. Batalkan.")
        sys.exit(1)

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept"       : "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })

    # Verifikasi token
    me = session.get("https://api.github.com/user")
    if not me.ok:
        print(f"Token tidak valid: {me.status_code}")
        sys.exit(1)
    print(f"Login sebagai: {me.json().get('login')}\n")

    # Ambil public key repo
    print("Mengambil public key repository...")
    try:
        key_id, pub_key = get_public_key(session)
    except Exception as e:
        print(f"Gagal ambil public key: {e}")
        print("Pastikan token punya akses ke repository ini.")
        sys.exit(1)

    # Upload semua secrets
    print(f"\nMengupload {len(SECRETS)} secrets...\n")
    for name, value in SECRETS.items():
        set_secret(session, key_id, pub_key, name, value)

    print("\n" + "=" * 55)
    print("  SELESAI! Semua secrets sudah tersimpan.")
    print("=" * 55)
    print("\nSekarang buka tab Actions di GitHub untuk")
    print("menjalankan workflow 'Konten Bola Otomatis'.")


if __name__ == "__main__":
    main()
