"""
Generator konten bola menggunakan Google Gemini API (gratis 1.500 req/hari).
Model: gemini-2.0-flash — via REST API (tidak butuh library tambahan).
"""
import requests
from config import GEMINI_API_KEY

MODEL = "gemini-2.0-flash-lite"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models"
    f"/{MODEL}:generateContent"
)

SYSTEM_PROMPT = (
    "Kamu adalah jurnalis olahraga profesional Indonesia yang ahli sepak bola. "
    "Tulis konten yang informatif, menarik, dan menggunakan bahasa Indonesia gaul "
    "yang mudah dipahami semua kalangan. Gunakan emoji yang relevan."
)


def _chat(prompt: str) -> str:
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 2048, "temperature": 0.8},
    }
    resp = requests.post(
        GEMINI_URL,
        params={"key": GEMINI_API_KEY},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


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
    return _parse_output(_chat(prompt))


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
    return _parse_output(_chat(prompt))


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
    return _parse_output(_chat(prompt))


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
    return _parse_output(_chat(prompt))


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
    return _parse_output(_chat(prompt))


def buat_konten_berita_transfer(berita_teks: str) -> dict:
    """Buat konten pagi dari berita transfer terkini."""
    prompt = f"""
Buat konten berita transfer sepak bola pagi hari untuk media sosial.

Berita terkini:
{berita_teks}

Format output:
1. CAPTION FACEBOOK (200-280 kata, gaya berita pagi, energetik, emoji, hashtag)
2. DESKRIPSI YOUTUBE (150 kata, SEO-friendly)
3. JUDUL YOUTUBE (maks 70 karakter, clickbait tapi faktual)
4. TAGS YOUTUBE (15-20 tag)

Pisahkan setiap bagian dengan === BAGIAN ===
"""
    return _parse_output(_chat(prompt))


# Label topik pundit yang tampil di video
LABEL_TOPIK = {
    "timnas"            : "🇮🇩 Timnas Indonesia",
    "liga1"             : "🏆 BRI Liga 1",
    "persija"           : "🔴 Persija Jakarta",
    "persib"            : "💙 Persib Bandung",
    "manchester_united" : "👹 Manchester United",
    "liga_champion"     : "⭐ UEFA Champions League",
}


def buat_analisis_pundit(berita_teks: str, topik: str = "timnas") -> dict:
    """Buat konten analisis gaya pundit TV untuk topik tertentu."""
    label = LABEL_TOPIK.get(topik, "⚽ Sepak Bola")
    prompt = f"""
Kamu adalah pundit/analis sepak bola profesional Indonesia yang sering tampil di TV.
Topik hari ini: {label}

Berita terkini:
{berita_teks}

Buat konten analisis pundit yang tajam, berani berpendapat, dan menghibur.

Format output:
1. CAPTION FACEBOOK
   - Gaya pundit TV: tegas, lugas, ada opini kuat
   - Buka dengan kutipan/pernyataan mengejutkan
   - Analisis 2-3 poin utama
   - Tutup dengan pertanyaan provokatif ke pembaca
   - 220-300 kata, emoji, hashtag #{topik.replace("_", "")} #infobola

2. KUTIPAN PUNDIT (untuk teks di video)
   - 1 kalimat tajam dan berkesan, maks 120 karakter
   - Gaya komentar pundit TV yang to-the-point
   - Contoh: "Ronaldo sudah habis di level Eropa — itu fakta, bukan opini!"

3. JUDUL VIDEO (maks 65 karakter, clickbait tapi faktual)

4. POIN ANALISIS (3 poin, masing-masing maks 60 karakter)
   - Format: poin singkat dan padat
   - Akan ditampilkan sebagai bullet point di video

Pisahkan setiap bagian dengan === BAGIAN ===
"""
    raw = _chat(prompt)
    hasil = _parse_output_pundit(raw)
    return hasil


def _parse_output_pundit(teks: str) -> dict:
    """Parse output pundit ke dict berstruktur."""
    import re

    hasil = {
        "facebook_caption": "",
        "kutipan_pundit"  : "",
        "judul_video"     : "",
        "poin_analisis"   : [],
    }

    # Split bagian
    if "=== BAGIAN ===" in teks:
        bagian = [b.strip() for b in teks.split("=== BAGIAN ===") if b.strip()]
    else:
        bagian = re.split(r"===\s*[^=]+\s*===", teks)
        bagian = [b.strip() for b in bagian if b.strip()]

    keys = ["facebook_caption", "kutipan_pundit", "judul_video", "poin_analisis"]
    for i, key in enumerate(keys):
        if i >= len(bagian):
            break
        konten = bagian[i].strip()
        lines  = [l for l in konten.split("\n")
                  if not re.match(r"^(===|CAPTION|KUTIPAN|JUDUL|POIN|\*\*[0-9])", l.strip().upper())]
        konten = "\n".join(lines).strip()

        if key == "poin_analisis":
            poin = []
            for line in konten.split("\n"):
                line = re.sub(r"^[-•*\d.]+\s*", "", line).strip()
                if line and len(line) > 5:
                    poin.append(line[:65])
            hasil[key] = poin[:3]
        else:
            hasil[key] = konten

    return hasil


def generate_image_url(topik: str, style: str = "football") -> str:
    """Generate URL gambar Full HD dari Pollinations.ai (gratis, tanpa API key).
    Resolusi 1920x1080, model flux, enhance=true untuk kualitas maksimal.
    """
    import urllib.parse
    styles = {
        "football"  : "professional football soccer photography, dynamic action shot, packed stadium, dramatic cinematic lighting, ultra sharp focus, 8K hyperrealistic",
        "transfer"  : "football player transfer signing ceremony, press conference, new jersey reveal, professional photography, sharp focus, cinematic lighting",
        "viral"     : "epic football viral moment, massive fans celebration explosion, dramatic stadium aerial view, ultra realistic cinematic",
        "klasemen"  : "football league championship golden trophy, confetti rain, stadium crowd euphoria, ultra HD photorealistic",
        "hype"      : "football match epic night countdown, stadium floodlights blazing, electric crowd atmosphere, dramatic wide angle ultra sharp",
        "statistik" : "football match analytics dashboard, neon data visualization, dark modern background, professional sports infographic ultra HD",
    }
    style_text = styles.get(style, styles["football"])
    prompt = (
        f"{topik}, {style_text}, "
        f"4K ultra HD, photorealistic, award winning sports photography, "
        f"no blur, tack sharp, vibrant saturated colors, professional studio quality"
    )
    encoded = urllib.parse.quote(prompt)
    seed    = abs(hash(topik)) % 99999
    return (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=1920&height=1080&model=flux&enhance=true&nologo=true&seed={seed}"
    )


def buat_hype_mendatang(fixture_teks: list[str], hari_lagi: int) -> dict:
    """Buat konten hype countdown pertandingan mendatang (H-N)."""
    daftar = "\n".join(f"- {f}" for f in fixture_teks)
    label  = f"H-{hari_lagi}" if hari_lagi > 1 else "BESOK"
    prompt = f"""
Buat konten hype sepak bola untuk media sosial. Pertandingan besar akan berlangsung {label}!

Pertandingan mendatang:
{daftar}

Instruksi:
- Buka dengan kalimat hype countdown "{label} LAGI!" yang semangat
- Highlight 1-2 pertandingan paling menarik
- Bangun antisipasi dan excitement para fans
- Ajak followers untuk save postingan dan pantau terus
- Panjang caption Facebook: 200-280 kata, emoji, hashtag

Format output:
1. CAPTION FACEBOOK
2. DESKRIPSI YOUTUBE (100-150 kata, SEO)
3. JUDUL YOUTUBE (maks 70 karakter, ada "{label}")
4. TAGS YOUTUBE (15 tag)

Pisahkan setiap bagian dengan === BAGIAN ===
"""
    return _parse_output(_chat(prompt))


def buat_polling_interaktif(fixture_teks: list[str]) -> str:
    """Buat caption polling/kuis untuk pertandingan malam ini (hanya Facebook)."""
    daftar = "\n".join(f"- {f}" for f in fixture_teks)
    prompt = f"""
Buat caption Facebook berisi polling interaktif untuk pertandingan malam ini.

Pertandingan:
{daftar}

Instruksi:
- Pilih 1 pertandingan paling menarik sebagai fokus polling
- Buat pertanyaan "Siapa yang menang?" dengan pilihan A/B atau komentar tim
- Tambahkan prediksi singkat kamu sebagai penulis
- Akhiri dengan ajakan vote di kolom komentar
- Panjang: 150-200 kata, emoji, hashtag
- Jangan sertakan format YOUTUBE, hanya caption Facebook saja
"""
    return _chat(prompt)


def buat_pengingat_pertandingan(fixture_teks: list[str]) -> str:
    """Buat caption pengingat pertandingan malam ini (hanya Facebook)."""
    daftar = "\n".join(f"- {f}" for f in fixture_teks)
    prompt = f"""
Buat caption Facebook sebagai pengingat (reminder) pertandingan malam ini.

Pertandingan:
{daftar}

Instruksi:
- Sebutkan kick-off time dengan jelas
- Beri highlight 1-2 pertandingan paling menarik
- Ajak followers untuk nonton dan pantau skor bareng
- Gaya hype, semangat, seperti siaran radio bola
- Panjang: 150-200 kata, emoji, hashtag
- Hanya caption Facebook saja, tanpa format YouTube
"""
    return _chat(prompt)


def buat_konten_topik_viral(berita_teks: str) -> dict:
    """Buat konten dari topik viral sepak bola sore hari."""
    prompt = f"""
Buat konten analisis topik viral sepak bola untuk media sosial sore hari.

Topik/berita viral:
{berita_teks}

Format output:
1. CAPTION FACEBOOK (220-300 kata, opini + analisis, ajakan diskusi, hashtag)
2. DESKRIPSI YOUTUBE (150 kata, SEO)
3. JUDUL YOUTUBE (maks 70 karakter, provokatif tapi tidak hoaks)
4. TAGS YOUTUBE (15-20 tag)

Pisahkan setiap bagian dengan === BAGIAN ===
"""
    return _parse_output(_chat(prompt))


def buat_statistik_malam(fixture_teks: list[str]) -> str:
    """Buat caption statistik menarik dari pertandingan malam ini (hanya Facebook)."""
    daftar = "\n".join(f"- {f}" for f in fixture_teks)
    prompt = f"""
Buat caption Facebook berisi statistik dan fakta menarik dari pertandingan tadi malam.

Data pertandingan:
{daftar}

Instruksi:
- Angkat 3-5 statistik paling menarik (gol, assist, kartu merah, rekor)
- Gaya infografik teks — gunakan angka dan emoji yang menonjol
- Tambahkan trivia atau fakta unik
- Panjang: 180-250 kata, hashtag relevan
- Hanya caption Facebook saja
"""
    return _chat(prompt)


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
    """Parsing output Gemini ke dict berstruktur."""
    bagian = [b.strip() for b in teks.split("=== BAGIAN ===")]
    bagian = [b for b in bagian if b]

    hasil = {
        "facebook_caption"  : "",
        "youtube_description": "",
        "youtube_title"     : "",
        "youtube_tags"      : [],
    }

    keys = ["facebook_caption", "youtube_description", "youtube_title", "youtube_tags"]
    for i, key in enumerate(keys):
        if i < len(bagian):
            lines = bagian[i].split("\n")
            konten_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and not (
                    len(stripped) > 2
                    and stripped[0].isdigit()
                    and stripped[1] in (".", ")")
                    and stripped[2:].strip().isupper()
                ):
                    konten_lines.append(line)
            konten = "\n".join(konten_lines).strip()

            if key == "youtube_tags":
                hasil[key] = [t.strip() for t in konten.split(",") if t.strip()]
            else:
                hasil[key] = konten

    return hasil
