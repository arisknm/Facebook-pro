"""
Setup otomatis GitHub Actions Secrets dari file .env.
Jalankan sekali — semua secrets langsung tersimpan ke GitHub Actions.

Cara pakai:
  python setup_github_secrets.py --pat GITHUB_PAT_ANDA
  python setup_github_secrets.py --pat GITHUB_PAT_ANDA --token TOKEN_FB_BARU
"""
import argparse
import base64
import os
import sys
import requests
from pathlib import Path
from nacl import encoding, public

REPO_OWNER = "arisknm"
REPO_NAME  = "Facebook-pro"


def load_env(env_path: str) -> dict:
    """Baca file .env dan return dict key=value."""
    env = {}
    path = Path(env_path)
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip()
    return env


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    pub_key   = public.PublicKey(public_key_b64.encode(), encoding.Base64Encoder())
    encrypted = public.SealedBox(pub_key).encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def get_public_key(session: requests.Session) -> tuple[str, str]:
    r = session.get(
        f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/secrets/public-key"
    )
    r.raise_for_status()
    data = r.json()
    return data["key_id"], data["key"]


def set_secret(session: requests.Session, key_id: str, pub_key: str, name: str, value: str):
    encrypted = encrypt_secret(pub_key, value)
    r = session.put(
        f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/secrets/{name}",
        json={"encrypted_value": encrypted, "key_id": key_id},
    )
    if r.status_code in (201, 204):
        print(f"  ✓ {name}")
    else:
        print(f"  ✗ {name} — {r.status_code}: {r.text[:120]}")


def main():
    parser = argparse.ArgumentParser(description="Setup GitHub Actions Secrets dari .env")
    parser.add_argument("--pat", metavar="GITHUB_PAT", help="GitHub Personal Access Token (scope: repo)")
    parser.add_argument("--token", metavar="FACEBOOK_TOKEN", help="Update hanya FACEBOOK_ACCESS_TOKEN")
    args = parser.parse_args()

    env_file = os.path.join(os.path.dirname(__file__), ".env")
    env = load_env(env_file)

    # Daftar secrets yang akan diupload (ambil dari .env)
    secret_keys = [
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "FACEBOOK_PAGE_ID",
        "FACEBOOK_ACCESS_TOKEN",
        "THREADS_USER_ID",
        "THREADS_ACCESS_TOKEN",
        "SHOPEE_AFFILIATE_ID",
        "FOOTBALL_API_KEY",
        "NEWS_API_KEY",
    ]

    print("=" * 55)
    if args.token:
        print("  UPDATE FACEBOOK ACCESS TOKEN")
    else:
        print("  SETUP GITHUB ACTIONS SECRETS OTOMATIS")
    print("=" * 55)
    print(f"\nRepository: {REPO_OWNER}/{REPO_NAME}")
    print(f"Sumber    : {env_file}\n")

    # Ambil PAT
    gh_token = (args.pat or "").strip()
    if not gh_token:
        gh_token = os.environ.get("GH_PAT", "").strip()
    if not gh_token:
        gh_token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not gh_token:
        print("GitHub PAT tidak ditemukan.")
        print("Buat di: github.com → Settings → Developer settings")
        print("         → Personal access tokens → Fine-grained tokens")
        print("         → Permissions: Actions (R/W), Secrets (R/W)\n")
        gh_token = input("Paste GitHub PAT: ").strip()
    if not gh_token:
        print("PAT diperlukan. Batalkan.")
        sys.exit(1)

    session = requests.Session()
    session.headers.update({
        "Authorization"       : f"Bearer {gh_token}",
        "Accept"              : "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })

    me = session.get("https://api.github.com/user")
    if not me.ok:
        print(f"PAT tidak valid: {me.status_code}")
        sys.exit(1)
    print(f"Login sebagai: {me.json().get('login')}\n")

    print("Mengambil public key repository...")
    try:
        key_id, pub_key = get_public_key(session)
    except Exception as e:
        print(f"Gagal ambil public key: {e}")
        print("Pastikan PAT punya akses ke repository ini.")
        sys.exit(1)

    if args.token:
        new_token = args.token.strip()
        print("\nMengupdate FACEBOOK_ACCESS_TOKEN...\n")
        set_secret(session, key_id, pub_key, "FACEBOOK_ACCESS_TOKEN", new_token)
    else:
        print(f"Mengupload {len(secret_keys)} secrets...\n")
        missing = []
        for name in secret_keys:
            value = env.get(name, "")
            if not value:
                missing.append(name)
                print(f"  ⚠ {name} — kosong di .env, dilewati")
                continue
            set_secret(session, key_id, pub_key, name, value)

        # Simpan PAT itu sendiri sebagai GH_PAT agar auto-refresh token bisa jalan
        print(f"\n  Menyimpan GH_PAT untuk auto-refresh token...")
        set_secret(session, key_id, pub_key, "GH_PAT", gh_token)

        if missing:
            print(f"\n⚠ {len(missing)} secret kosong: {', '.join(missing)}")
            print("  Isi di .env lalu jalankan ulang script ini.")

    print("\n" + "=" * 55)
    print("  SELESAI! Semua secrets tersimpan di GitHub Actions.")
    print("=" * 55)
    print("\nLangkah selanjutnya:")
    if not args.token:
        print("1. Buka GitHub → Actions → 'Refresh Token Facebook'")
        print("2. Klik 'Run workflow' → isi User Token dari Graph API Explorer")
        print("3. Setelah itu, token akan auto-refresh setiap 50 hari otomatis")
    else:
        print("Jalankan workflow 'Konten Bola Otomatis' untuk verifikasi.")


if __name__ == "__main__":
    main()
