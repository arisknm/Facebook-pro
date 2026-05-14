"""
Generator konten bola.
Primary: Groq API (llama-3.3-70b-versatile) — 14,400 req/hari gratis, lebih cepat.
Fallback: Google Gemini API (gemini-2.0-flash-lite) — 1,500 req/hari gratis.
"""
import re
import logging
import requests
from config import GEMINI_API_KEY, GROQ_API_KEY

log = logging.getLogger(__name__)

# ── Groq ──────────────────────────────────────────────────────────────────────
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# ── Gemini (fallback) ─────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.0-flash-lite"
GEMINI_URL   = (
    f"https://generativelanguage.googleapis.com/v1beta/models"
    f"/{GEMINI_MODEL}:generateContent"
)

SYSTEM_PROMPT = (
    "Kamu adalah jurnalis olahraga profesional Indonesia yang ahli sepak bola. "
    "Tulis konten yang informatif, menarik, dan menggunakan bahasa Indonesia gaul "
    "yang mudah dipahami semua kalangan. Gunakan emoji yang relevan."
)


def _chat_groq(prompt: str) -> str:
    resp = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens": 2048,
            "temperature": 0.8,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _chat_gemini(prompt: str) -> str:
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


def _chat(prompt: str) -> str:
    """Coba Groq dulu (cepat, 14.400 req/hari). Fallback ke Gemini jika gagal."""
    if GROQ_API_KEY:
        try:
            return _chat_groq(prompt)
        except Exception as e:
            log.warning(f"Groq gagal ({e}), fallback ke Gemini...")
    return _chat_gemini(prompt)


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

Tulis output dengan FORMAT TEPAT berikut (jangan tambah teks apapun sebelum baris pertama):

=== CAPTION FACEBOOK ===
[200-300 kata, engaging, call-to-action, hashtag]

=== DESKRIPSI YOUTUBE ===
[150-200 kata, SEO-friendly, ada timestamp]

=== JUDUL YOUTUBE ===
[1 baris, maks 70 karakter, clickbait tapi tidak bohong]

=== TAGS YOUTUBE ===
[15-20 tag dipisahkan koma]
"""
    return _parse_output(_chat(prompt))


def buat_rekap_hasil(fixture_teks: list[str]) -> dict:
    """Buat rekap hasil pertandingan kemarin."""
    daftar = "\n".join(f"- {f}" for f in fixture_teks)
    prompt = f"""
Buat konten rekap hasil pertandingan sepak bola kemarin.

Hasil pertandingan:
{daftar}

Tulis output dengan FORMAT TEPAT berikut (jangan tambah teks apapun sebelum baris pertama):

=== CAPTION FACEBOOK ===
[250-350 kata, analisis singkat, reaksi, hashtag]

=== DESKRIPSI YOUTUBE ===
[150-200 kata, highlight poin, SEO]

=== JUDUL YOUTUBE ===
[1 baris, maks 70 karakter]

=== TAGS YOUTUBE ===
[15-20 tag dipisahkan koma]
"""
    return _parse_output(_chat(prompt))


def buat_analisis_klasemen(liga: str, standings_teks: str) -> dict:
    """Buat konten analisis klasemen liga."""
    prompt = f"""
Buat konten analisis klasemen {liga} untuk media sosial.

Data klasemen (5 besar dan 3 zona degradasi):
{standings_teks}

Tulis output dengan FORMAT TEPAT berikut (jangan tambah teks apapun sebelum baris pertama):

=== CAPTION FACEBOOK ===
[200-280 kata, analisis perebutan gelar & degradasi, hashtag]

=== DESKRIPSI YOUTUBE ===
[150 kata, SEO]

=== JUDUL YOUTUBE ===
[1 baris, maks 70 karakter]

=== TAGS YOUTUBE ===
[15 tag dipisahkan koma]
"""
    return _parse_output(_chat(prompt))


def buat_konten_transfer(berita: str) -> dict:
    """Buat konten gosip/berita transfer."""
    prompt = f"""
Buat konten berita transfer pemain untuk media sosial.

Informasi transfer:
{berita}

Tulis output dengan FORMAT TEPAT berikut (jangan tambah teks apapun sebelum baris pertama):

=== CAPTION FACEBOOK ===
[200-300 kata, dramatis tapi faktual, hashtag]

=== DESKRIPSI YOUTUBE ===
[150 kata]

=== JUDUL YOUTUBE ===
[1 baris, maks 70 karakter, attention-grabbing]

=== TAGS YOUTUBE ===
[15-20 tag dipisahkan koma]
"""
    return _parse_output(_chat(prompt))


def buat_konten_bebas(topik: str) -> dict:
    """Buat konten bola bertopik bebas sesuai input user."""
    prompt = f"""
Buat konten sepak bola untuk media sosial dengan topik berikut:

{topik}

Tulis output dengan FORMAT TEPAT berikut (jangan tambah teks apapun sebelum baris pertama):

=== CAPTION FACEBOOK ===
[200-300 kata, engaging, hashtag relevan]

=== DESKRIPSI YOUTUBE ===
[150-200 kata, SEO-friendly]

=== JUDUL YOUTUBE ===
[1 baris, maks 70 karakter]

=== TAGS YOUTUBE ===
[15-20 tag dipisahkan koma]
"""
    return _parse_output(_chat(prompt))


def buat_konten_berita_transfer(berita_teks: str) -> dict:
    """Buat konten pagi dari berita transfer terkini."""
    prompt = f"""
Buat konten berita transfer sepak bola pagi hari untuk media sosial.

Berita terkini:
{berita_teks}

Tulis output dengan FORMAT TEPAT berikut (jangan tambah teks apapun sebelum baris pertama):

=== CAPTION FACEBOOK ===
[200-280 kata, gaya berita pagi, energetik, emoji, hashtag]

=== DESKRIPSI YOUTUBE ===
[150 kata, SEO-friendly]

=== JUDUL YOUTUBE ===
[1 baris, maks 70 karakter, clickbait tapi faktual]

=== TAGS YOUTUBE ===
[15-20 tag dipisahkan koma]
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


def buat_konten_topik_khusus(berita_teks: str, topik: str) -> dict:
    """Buat konten berita untuk topik spesifik (Timnas, Liga1, Premier League, dll.)."""
    label_map = {
        "timnas"         : "Timnas Indonesia & pemain Indonesia di luar negeri",
        "liga1"          : "BRI Liga 1 Indonesia",
        "premier_league" : "Premier League Inggris",
        "liga_champion"  : "UEFA Champions League",
    }
    label = label_map.get(topik, topik)
    prompt = f"""
Buat konten berita sepak bola tentang {label} untuk media sosial.

Berita terkini:
{berita_teks}

Format output:
1. CAPTION FACEBOOK (200-280 kata, informatif, engaging, emoji, hashtag)
2. HEADLINE VIDEO (1 kalimat tajam, maks 70 karakter — untuk judul di video)
3. POIN UTAMA (3 poin singkat, masing-masing maks 55 karakter — untuk bullet di video)
4. TAGS YOUTUBE (12-15 tag relevan)

Pisahkan setiap bagian dengan === BAGIAN ===
"""
    raw    = _chat(prompt)
    bagian = raw.split("=== BAGIAN ===") if "=== BAGIAN ===" in raw else __import__("re").split(r"===\s*[^=]+\s*===", raw)
    bagian = [b.strip() for b in bagian if b.strip()]

    hasil = {
        "facebook_caption": bagian[0] if len(bagian) > 0 else "",
        "headline_video"  : bagian[1].split("\n")[0].strip() if len(bagian) > 1 else "",
        "poin_video"      : [],
        "youtube_tags"    : [],
    }
    if len(bagian) > 2:
        import re
        for line in bagian[2].split("\n"):
            line = re.sub(r"^[-•*\d.▸]+\s*", "", line).strip()
            if line and len(line) > 5:
                hasil["poin_video"].append(line[:55])
        hasil["poin_video"] = hasil["poin_video"][:3]
    if len(bagian) > 3:
        import re
        hasil["youtube_tags"] = [t.strip() for t in re.split(r"[,\n]", bagian[3]) if t.strip()]
    return hasil


def get_real_photo_url(keyword: str) -> str:
    """Cari foto asli pemain/tim dari TheSportsDB. Return URL atau string kosong."""
    if not keyword or len(keyword) < 3:
        return ""
    try:
        # Coba cari sebagai pemain dulu
        r = requests.get(
            "https://www.thesportsdb.com/api/v1/json/3/searchplayers.php",
            params={"p": keyword[:50]}, timeout=8,
        )
        data = r.json() if r.ok else {}
        players = data.get("player") or []
        for p in players:
            url = p.get("strThumb") or p.get("strCutout") or ""
            if url and url.startswith("http"):
                log.info(f"TheSportsDB player photo: {p.get('strPlayer')} → {url[:60]}")
                return url

        # Fallback: cari sebagai tim
        r2 = requests.get(
            "https://www.thesportsdb.com/api/v1/json/3/searchteams.php",
            params={"t": keyword[:50]}, timeout=8,
        )
        data2 = r2.json() if r2.ok else {}
        teams = data2.get("teams") or []
        for t in teams:
            url = t.get("strTeamBanner") or t.get("strTeamFanart1") or t.get("strTeamLogo") or ""
            if url and url.startswith("http"):
                log.info(f"TheSportsDB team photo: {t.get('strTeam')} → {url[:60]}")
                return url
    except Exception as e:
        log.debug(f"TheSportsDB search gagal ({keyword}): {e}")
    return ""


def generate_image_url(topik: str, style: str = "football") -> str:
    """Generate URL gambar — coba foto asli TheSportsDB dulu, fallback ke Pollinations AI."""
    import urllib.parse

    # Visual spesifik per tim/liga agar gambar tidak generik
    _VISUAL_TIM = {
        "liverpool"         : "Liverpool FC iconic red Adidas kit, Anfield stadium roaring Kop end",
        "chelsea"           : "Chelsea FC royal blue jersey, Stamford Bridge London",
        "manchester united" : "Manchester United classic red jersey, Old Trafford Theatre of Dreams",
        "man utd"           : "Manchester United classic red jersey, Old Trafford Theatre of Dreams",
        "manchester city"   : "Manchester City sky blue jersey, Etihad Stadium",
        "arsenal"           : "Arsenal red white Adidas jersey, Emirates Stadium",
        "tottenham"         : "Tottenham Hotspur white jersey, Spurs stadium",
        "barcelona"         : "FC Barcelona iconic blaugrana jersey, Camp Nou massive crowd",
        "real madrid"       : "Real Madrid all white jersey, Santiago Bernabeu stadium",
        "atletico"          : "Atletico Madrid red white stripes, Metropolitano stadium",
        "juventus"          : "Juventus black white stripes jersey, Allianz Stadium Turin",
        "inter milan"       : "Inter Milan black blue jersey, San Siro stadium Milan",
        "ac milan"          : "AC Milan red black jersey, San Siro stadium",
        "psg"               : "Paris Saint-Germain dark blue red jersey, Parc des Princes Paris",
        "dortmund"          : "Borussia Dortmund yellow black jersey, Signal Iduna Park yellow wall",
        "bayern"            : "Bayern Munich red jersey, Allianz Arena Munich",
        "timnas"            : "Indonesia national football team Garuda, red white jersey, packed stadium fans",
        "persija"           : "Persija Jakarta orange-red jersey Macan Kemayoran, Gelora Bung Karno Jakarta",
        "persib"            : "Persib Bandung blue white jersey Maung Bandung, GBLA stadium Bandung",
        "liga champion"     : "UEFA Champions League starball trophy, massive floodlit European stadium night",
        "liga 1"            : "BRI Liga 1 Indonesia, colorful local football supporters, vibrant stadium",
        "premier league"    : "English Premier League iconic green pitch, packed British stadium",
        "la liga"           : "La Liga Spanish football, sunny Mediterranean stadium",
        "serie a"           : "Serie A Italian football, passionate Ultras crowd tifo display",
        "bundesliga"        : "Bundesliga German football, packed stadium yellow wall atmosphere",
    }

    topik_lower = topik.lower()

    # Coba foto asli dari TheSportsDB untuk kata kunci spesifik
    _kata_cari = [w for w in topik.split() if len(w) > 3 and w.istitle()]
    if _kata_cari:
        real_url = get_real_photo_url(" ".join(_kata_cari[:3]))
        if real_url:
            return real_url

    visual_konteks = ""
    for keyword, visual in _VISUAL_TIM.items():
        if keyword in topik_lower:
            visual_konteks = visual + ", "
            break

    styles = {
        "football"  : "action sports photography, packed roaring stadium, cinematic dramatic lighting, motion blur, hyperrealistic",
        "transfer"  : "football transfer signing announcement, media conference stage, new jersey reveal, press cameras flash",
        "viral"     : "epic viral football moment, massive crowd explosion, dramatic wide angle aerial shot",
        "klasemen"  : "football league championship golden trophy ceremony, confetti rain, victorious celebration",
        "hype"      : "epic match night atmosphere, blazing stadium floodlights, electric crowd energy",
        "statistik" : "sports statistics broadcast overlay, modern dark neon infographic, professional TV studio",
    }
    style_text = styles.get(style, styles["football"])

    prompt = (
        f"{visual_konteks}{topik}, {style_text}, "
        f"Canon EOS R5 100mm f/1.4, tack sharp focus, 4K ultra HD photorealistic, "
        f"award winning sports photography, vivid saturated colors, dramatic professional lighting"
    )
    encoded = urllib.parse.quote(prompt)
    seed    = abs(hash(topik)) % 99999
    return (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=2048&height=1152&model=flux&enhance=true&nologo=true&safe=false&seed={seed}"
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

Tulis output dengan FORMAT TEPAT berikut (jangan tambah teks apapun sebelum baris pertama):

=== CAPTION FACEBOOK ===
[200-280 kata, hype countdown, emoji, hashtag]

=== DESKRIPSI YOUTUBE ===
[100-150 kata, SEO]

=== JUDUL YOUTUBE ===
[1 baris, maks 70 karakter, ada "{label}"]

=== TAGS YOUTUBE ===
[15 tag dipisahkan koma]
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

Tulis output dengan FORMAT TEPAT berikut (jangan tambah teks apapun sebelum baris pertama):

=== CAPTION FACEBOOK ===
[220-300 kata, opini + analisis, ajakan diskusi, hashtag]

=== DESKRIPSI YOUTUBE ===
[150 kata, SEO-friendly]

=== JUDUL YOUTUBE ===
[1 baris, maks 70 karakter, provokatif tapi tidak hoaks]

=== TAGS YOUTUBE ===
[15-20 tag dipisahkan koma]
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
    """Parsing output AI ke dict berstruktur. Handle tiga format:
    1. '=== CAPTION FACEBOOK ===' (format eksplisit/Groq)
    2. '=== BAGIAN ===' (format lama/Gemini)
    3. '1. CAPTION FACEBOOK\\n...' (fallback numbered sections)
    """
    hasil = {
        "facebook_caption"   : "",
        "youtube_description": "",
        "youtube_title"      : "",
        "youtube_tags"       : [],
    }

    _SEP = re.compile(r"===\s*([^=]+?)\s*===")
    _KEY_MAP = {
        "caption facebook"   : "facebook_caption",
        "facebook"           : "facebook_caption",
        "deskripsi youtube"  : "youtube_description",
        "youtube description": "youtube_description",
        "judul youtube"      : "youtube_title",
        "judul video"        : "youtube_title",
        "judul"              : "youtube_title",
        "title"              : "youtube_title",
        "tags youtube"       : "youtube_tags",
        "tags"               : "youtube_tags",
        "hashtag"            : "youtube_tags",
    }

    header_matches = list(_SEP.finditer(teks))

    if header_matches:
        # ── Format 1: === NAMA BAGIAN === ──────────────────────────────────
        for idx, match in enumerate(header_matches):
            header_key = match.group(1).strip().lower()
            start = match.end()
            end = header_matches[idx + 1].start() if idx + 1 < len(header_matches) else len(teks)
            isi = teks[start:end].strip()
            isi_bersih = "\n".join(
                ln for ln in isi.splitlines()
                if not re.fullmatch(r"\s*===.*===\s*", ln)
            ).strip()
            for kata, field in _KEY_MAP.items():
                if kata in header_key:
                    if field == "youtube_tags":
                        hasil[field] = [t.strip() for t in re.split(r"[,\n]", isi_bersih) if t.strip()]
                    else:
                        hasil[field] = isi_bersih
                    break

    elif "=== BAGIAN ===" in teks:
        # ── Format 2: === BAGIAN === (format lama) ─────────────────────────
        bagian = [b.strip() for b in teks.split("=== BAGIAN ===") if b.strip()]
        keys = ["facebook_caption", "youtube_description", "youtube_title", "youtube_tags"]
        for i, key in enumerate(keys):
            if i < len(bagian):
                isi = bagian[i].strip()
                if key == "youtube_tags":
                    hasil[key] = [t.strip() for t in isi.split(",") if t.strip()]
                else:
                    hasil[key] = isi

    else:
        # ── Format 3: numbered sections "1. CAPTION FACEBOOK\n...\n2. ..." ─
        _NUM_HDR = re.compile(
            r"(?:^|\n)\d+\.\s*(?:CAPTION FACEBOOK|DESKRIPSI YOUTUBE|JUDUL YOUTUBE|TAGS YOUTUBE"
            r"|JUDUL VIDEO|HEADLINE VIDEO|TAGS)",
            re.IGNORECASE,
        )
        parts = re.split(_NUM_HDR, teks)
        labels = re.findall(_NUM_HDR, teks)
        if len(parts) > 1:
            for label_raw, isi in zip(labels, parts[1:]):
                lbl = label_raw.strip().lower()
                lbl = re.sub(r"^\d+\.\s*", "", lbl)
                isi = isi.strip()
                for kata, field in _KEY_MAP.items():
                    if kata in lbl:
                        if field == "youtube_tags":
                            hasil[field] = [t.strip() for t in re.split(r"[,\n]", isi) if t.strip()]
                        else:
                            hasil[field] = isi
                        break

    # ── Bersihkan caption dari sisa header yang mungkin lolos ─────────────
    if hasil["facebook_caption"]:
        # Hapus baris yang berupa label section (mis. "1. CAPTION FACEBOOK")
        lines = hasil["facebook_caption"].splitlines()
        lines = [
            ln for ln in lines
            if not re.match(
                r"^\s*\d+\.\s*(?:CAPTION FACEBOOK|DESKRIPSI YOUTUBE|JUDUL YOUTUBE|TAGS YOUTUBE"
                r"|JUDUL VIDEO|TAGS)\s*$",
                ln, re.IGNORECASE,
            )
        ]
        hasil["facebook_caption"] = "\n".join(lines).strip()

    # ── Fallback mutlak: jika caption masih kosong, bersihkan teks mentah ──
    if not hasil["facebook_caption"]:
        hasil["facebook_caption"] = _SEP.sub("", teks).strip()

    return hasil
