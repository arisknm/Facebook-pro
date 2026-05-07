"""
Generator konten bola menggunakan Claude AI.
"""
import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
MODEL = "claude-sonnet-4-6"


def _chat(prompt: str, system: str = "") -> str:
    sys = system or (
        "Kamu adalah jurnalis olahraga profesional Indonesia yang ahli sepak bola. "
        "Tulis konten yang informatif, menarik, dan menggunakan bahasa Indonesia gaul "
        "yang mudah dipahami semua kalangan. Gunakan emoji yang relevan."
    )
    msg = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=sys,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# --------------------------------------------------------------------------- #
#  TIPE KONTEN
# --------------------------------------------------------------------------- #

def buat_preview_pertandingan(fixture_teks: list[str]) -> dict:
    """Buat konten preview pertandingan hari ini."""
    daftar = "\n".join(f"- {f}" for f in fixture_teks)
    prompt = f"""
Buat konten preview pertandingan sepak bola hari ini untuk media sosial.

Data pertandingan:
{daftar}

Format output:
1. CAPTION FACEBOOK (200-300 kata, engaging, ada call-to-action, hashtag)
2. DESKRIPSI YOUTUBE (150-200 kata, SEO-friendly, ada timestamp section)
3. JUDUL YOUTUBE (maks 70 karakter, clickbait tapi tidak bohong)
4. TAGS YOUTUBE (15-20 tag, pisahkan dengan koma)

Pisahkan setiap bagian dengan === BAGIAN ===
"""
    hasil = _chat(prompt)
    return _parse_output(hasil)


def buat_rekap_hasil(fixture_teks: list[str]) -> dict:
    """Buat rekap hasil pertandingan kemarin."""
    daftar = "\n".join(f"- {f}" for f in fixture_teks)
    prompt = f"""
Buat konten rekap hasil pertandingan sepak bola kemarin.

Hasil pertandingan:
{daftar}

Format output:
1. CAPTION FACEBOOK (250-350 kata, analisis singkat, reaksi, hashtag)
2. DESKRIPSI YOUTUBE (150-200 kata, highlight poin, SEO)
3. JUDUL YOUTUBE (maks 70 karakter)
4. TAGS YOUTUBE (15-20 tag)

Pisahkan setiap bagian dengan === BAGIAN ===
"""
    hasil = _chat(prompt)
    return _parse_output(hasil)


def buat_analisis_klasemen(liga: str, standings_teks: str) -> dict:
    """Buat konten analisis klasemen liga."""
    prompt = f"""
Buat konten analisis klasemen {liga} untuk media sosial.

Data klasemen (5 besar dan 3 zona degradasi):
{standings_teks}

Format output:
1. CAPTION FACEBOOK (200-280 kata, analisis perebutan gelar & degradasi, hashtag)
2. DESKRIPSI YOUTUBE (150 kata, SEO)
3. JUDUL YOUTUBE (maks 70 karakter)
4. TAGS YOUTUBE (15 tag)

Pisahkan setiap bagian dengan === BAGIAN ===
"""
    hasil = _chat(prompt)
    return _parse_output(hasil)


def buat_konten_transfer(berita: str) -> dict:
    """Buat konten gosip/berita transfer."""
    prompt = f"""
Buat konten berita transfer pemain untuk media sosial.

Informasi transfer:
{berita}

Format output:
1. CAPTION FACEBOOK (200-300 kata, dramatis tapi faktual, hashtag)
2. DESKRIPSI YOUTUBE (150 kata)
3. JUDUL YOUTUBE (maks 70 karakter, attention-grabbing)
4. TAGS YOUTUBE (15-20 tag)

Pisahkan setiap bagian dengan === BAGIAN ===
"""
    hasil = _chat(prompt)
    return _parse_output(hasil)


def buat_konten_bebas(topik: str) -> dict:
    """Buat konten bola bertopik bebas sesuai input user."""
    prompt = f"""
Buat konten sepak bola untuk media sosial dengan topik berikut:

{topik}

Format output:
1. CAPTION FACEBOOK (200-300 kata, engaging, hashtag relevan)
2. DESKRIPSI YOUTUBE (150-200 kata, SEO-friendly)
3. JUDUL YOUTUBE (maks 70 karakter)
4. TAGS YOUTUBE (15-20 tag)

Pisahkan setiap bagian dengan === BAGIAN ===
"""
    hasil = _chat(prompt)
    return _parse_output(hasil)


def buat_script_video(topik: str, durasi_menit: int = 5) -> str:
    """Buat script narasi video YouTube."""
    prompt = f"""
Buat script narasi video YouTube berdurasi {durasi_menit} menit tentang:
{topik}

Struktur:
- INTRO (hook 10 detik + salam pembuka)
- ISI UTAMA (poin per poin dengan transisi)
- OUTRO (ajakan subscribe, like, komen)

Gunakan bahasa Indonesia yang natural dan energetik seperti komentar bola.
Tandai jeda dengan [PAUSE] dan efek visual dengan [VISUAL: deskripsi].
"""
    return _chat(prompt)


# --------------------------------------------------------------------------- #
#  HELPER
# --------------------------------------------------------------------------- #

def _parse_output(teks: str) -> dict:
    """Parsing output Claude ke dict berstruktur."""
    bagian = [b.strip() for b in teks.split("=== BAGIAN ===")]
    # Hapus bagian kosong
    bagian = [b for b in bagian if b]

    # Cari section berdasarkan label
    hasil = {
        "facebook_caption": "",
        "youtube_description": "",
        "youtube_title": "",
        "youtube_tags": [],
    }

    keys = ["facebook_caption", "youtube_description", "youtube_title", "youtube_tags"]
    for i, key in enumerate(keys):
        if i < len(bagian):
            teks_bagian = bagian[i]
            # Hapus header "1. CAPTION FACEBOOK" dsb
            lines = teks_bagian.split("\n")
            konten_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and not (
                    stripped[0].isdigit() and stripped[1] in (".", ")") and stripped[2:].strip().isupper()
                ):
                    konten_lines.append(line)
            konten = "\n".join(konten_lines).strip()

            if key == "youtube_tags":
                hasil[key] = [t.strip() for t in konten.split(",") if t.strip()]
            else:
                hasil[key] = konten

    return hasil
