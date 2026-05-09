"""
Generator video otomatis dari gambar AI + teks overlay + musik latar.
Menggunakan moviepy + Pillow (ffmpeg sudah tersedia di GitHub Actions ubuntu-latest).
Teks dirender dengan Pillow agar tidak bergantung pada ImageMagick.
Musik latar di-synthesize dengan numpy (tanpa file eksternal).
"""
import os
import re
import textwrap
import requests
import tempfile
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

try:
    import numpy as np
    NP_AVAILABLE = True
except ImportError:
    NP_AVAILABLE = False
    np = None  # type: ignore

try:
    from moviepy.editor import ImageClip, CompositeVideoClip, VideoClip
    from moviepy.audio.AudioClip import AudioArrayClip
    from PIL import Image, ImageDraw, ImageFont
    MOVIEPY_AVAILABLE = True
except Exception as _moviepy_err:
    MOVIEPY_AVAILABLE = False
    log.warning(f"moviepy/Pillow tidak tersedia ({type(_moviepy_err).__name__}: {_moviepy_err}) — video generation dinonaktifkan")


VIDEO_W      = 1080
VIDEO_H      = 1080
DURASI       = 20       # detik
FPS          = 24
SAMPLE_RATE  = 44100
VOLUME_MUSIK = 0.28     # volume musik (0.0–1.0), tidak terlalu keras


# --------------------------------------------------------------------------- #
#  MUSIK LATAR (synthesized, sports/upbeat vibes)
# --------------------------------------------------------------------------- #

def _nada(freq: float, dur: float, sr: int, amp: float = 1.0,
          attack: float = 0.01, release: float = 0.08) -> "np.ndarray":
    """Buat gelombang sinus satu nada dengan envelope ADSR sederhana."""
    n    = int(sr * dur)
    t    = np.linspace(0, dur, n, endpoint=False)
    wave = amp * np.sin(2 * np.pi * freq * t)
    # Attack
    atk  = int(sr * attack)
    wave[:atk] *= np.linspace(0, 1, atk)
    # Release
    rel  = int(sr * release)
    if rel > 0:
        wave[-rel:] *= np.linspace(1, 0, rel)
    return wave


def _kick(sr: int, dur: float = 0.18) -> "np.ndarray":
    """Bass drum sintetis."""
    n   = int(sr * dur)
    t   = np.linspace(0, dur, n, endpoint=False)
    env = np.exp(-t * 28)
    # Pitch envelope: mulai 150 Hz turun ke 50 Hz
    pitch = 150 * np.exp(-t * 35) + 50
    phase = np.cumsum(2 * np.pi * pitch / sr)
    return env * np.sin(phase) * 0.90


def _snare(sr: int, dur: float = 0.12) -> "np.ndarray":
    """Snare drum sintetis (noise + nada)."""
    n    = int(sr * dur)
    t    = np.linspace(0, dur, n, endpoint=False)
    env  = np.exp(-t * 38)
    noise = np.random.default_rng(42).standard_normal(n)
    tone = np.sin(2 * np.pi * 220 * t)
    return env * (noise * 0.6 + tone * 0.4) * 0.55


def _hihat(sr: int, dur: float = 0.06, open_hat: bool = False) -> "np.ndarray":
    """Hi-hat sintetis."""
    n   = int(sr * dur)
    t   = np.linspace(0, dur, n, endpoint=False)
    decay = 10 if open_hat else 60
    env  = np.exp(-t * decay)
    noise = np.random.default_rng(7).standard_normal(n)
    # High-pass: ambil komponen frekuensi tinggi saja
    hp = noise - np.convolve(noise, np.ones(8)/8, mode='same')
    return env * hp * 0.30


def _pad_chord(freqs: list, dur: float, sr: int, amp: float = 0.18) -> "np.ndarray":
    """Chord pad: gabungan beberapa sine wave lembut."""
    n      = int(sr * dur)
    result = np.zeros(n)
    t      = np.linspace(0, dur, n, endpoint=False)
    env    = np.ones(n)
    # Fade in 10%
    fi = int(n * 0.10)
    env[:fi] = np.linspace(0, 1, fi)
    for f in freqs:
        result += np.sin(2 * np.pi * f * t) * amp
        result += np.sin(2 * np.pi * f * 2 * t) * (amp * 0.3)   # harmonic 2
    return result * env


def _buat_musik_latar(durasi: float, sr: int = SAMPLE_RATE) -> "np.ndarray":
    """
    Synthesize musik latar sports/upbeat ±20 detik.
    Struktur: kick + snare + hihat + melodi + pad chord.
    BPM 120, 4/4.
    """
    n_total = int(sr * durasi)
    track   = np.zeros(n_total)

    bpm  = 120
    beat = sr * 60 / bpm          # samples per beat
    bar  = beat * 4               # samples per bar (4/4)

    def _place(samples: np.ndarray, pos: int):
        end = min(pos + len(samples), n_total)
        track[pos:end] += samples[:end - pos]

    # ── Drum pattern (1 bar = 4 ketukan) ──────────────────────────────────
    kick_wav  = _kick(sr)
    snare_wav = _snare(sr)
    hh_wav    = _hihat(sr, dur=0.05)
    hh_open   = _hihat(sr, dur=0.10, open_hat=True)

    # Ulangi pola sepanjang video
    for b in range(int(durasi * bpm / 60) + 2):
        pos_beat   = int(b * beat)
        beat_in_bar = b % 4

        # Kick: ketukan 1 dan 3
        if beat_in_bar in (0, 2):
            _place(kick_wav, pos_beat)

        # Snare: ketukan 2 dan 4
        if beat_in_bar in (1, 3):
            _place(snare_wav, pos_beat)

        # Hi-hat: setiap setengah ketukan
        _place(hh_wav, pos_beat)
        _place(hh_wav, pos_beat + int(beat / 2))

        # Open hi-hat di akhir bar (ketukan 4.5)
        if beat_in_bar == 3:
            _place(hh_open, pos_beat + int(beat * 0.75))

    # ── Melodi (pentatonic minor, sports fanfare) ──────────────────────────
    # A pentatonic minor: A4, C5, D5, E5, G5 → 440, 523, 587, 659, 784 Hz
    # Motif 4 bar (diulang)
    motif = [
        (440, 0.25), (523, 0.25), (659, 0.5),
        (784, 0.5),  (659, 0.25), (523, 0.25),
        (440, 0.5),  (0,   0.5),
        (523, 0.25), (659, 0.25), (784, 0.5),
        (880, 0.75), (0,   0.25),
        (784, 0.25), (659, 0.25), (523, 0.25), (440, 0.25),
        (392, 1.0),  (0,   0.0),
    ]
    mel_pos = int(sr * 1.0)   # mulai melodi setelah 1 detik (biar tidak mendadak)
    while mel_pos < n_total:
        for freq, dur_beat in motif:
            dur_sec = dur_beat * (60 / bpm)
            if freq > 0:
                wave = _nada(freq, dur_sec, sr, amp=0.35, attack=0.02, release=0.06)
                _place(wave, mel_pos)
            mel_pos += int(sr * dur_sec)
            if mel_pos >= n_total:
                break

    # ── Pad chord (latar lembut) ───────────────────────────────────────────
    # A minor chord: A3 (220), C4 (261.6), E4 (329.6)
    chord_dur = durasi
    pad = _pad_chord([220, 261.6, 329.6, 440], chord_dur, sr, amp=0.10)
    track[:len(pad)] += pad

    # ── Normalize + fade in/out ────────────────────────────────────────────
    peak = np.max(np.abs(track))
    if peak > 0:
        track = track / peak * VOLUME_MUSIK

    # Fade in 1.5 detik
    fi = int(sr * 1.5)
    track[:fi] *= np.linspace(0, 1, fi)
    # Fade out 1.5 detik
    fo = int(sr * 1.5)
    track[-fo:] *= np.linspace(1, 0, fo)

    return track.astype(np.float32)


# --------------------------------------------------------------------------- #
#  VISUAL HELPERS
# --------------------------------------------------------------------------- #

def _download_image(url: str, timeout: int = 120) -> str:
    """Download gambar dari URL ke file sementara, return path.
    Untuk video kita minta resolusi 1920x1920 agar crop ke 1080x1080 tetap tajam.
    """
    # Paksa resolusi 4K untuk Pollinations.ai
    if "image.pollinations.ai" in url:
        import re
        url = re.sub(r'width=\d+',  'width=2048',  url)
        url = re.sub(r'height=\d+', 'height=2048', url)
        if "enhance=" not in url:
            url += "&enhance=true"
        # Pastikan model flux (kualitas terbaik)
        if "model=" not in url:
            url += "&model=flux"

    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    tmp.write(resp.content)
    tmp.close()
    return tmp.name


def _wrap(teks: str, max_chars: int) -> str:
    return "\n".join(textwrap.wrap(teks.strip(), width=max_chars))


def _ambil_poin(caption: str, max_poin: int = 2) -> list[str]:
    """Ambil kalimat pertama dari caption untuk subtitle video."""
    kalimat = re.split(r'(?<=[.!?])\s+', caption.strip())
    bersih  = [k.strip() for k in kalimat if len(re.sub(r'[^\w\s]', '', k)) > 15]
    return bersih[:max_poin]


def _cari_font(ukuran: int) -> "ImageFont.ImageFont":
    """Cari font tersedia di sistem, fallback ke default."""
    kandidat = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ]
    for path in kandidat:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, ukuran)
            except Exception:
                continue
    return ImageFont.load_default()


def _buat_frame(img_pil: "Image.Image", judul: str, poin_list: list) -> "np.ndarray":
    """Frame video square 1080×1080 — full-bleed foto + gradient bawah + headline besar."""
    frame = img_pil.copy().convert("RGBA")
    w, h  = frame.size

    # Gradient gelap: transparan di atas → hitam pekat di bawah (mulai 45%)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    grad_start = int(h * 0.45)
    for y in range(grad_start, h):
        t_g   = (y - grad_start) / (h - grad_start)
        alpha = int(235 * (t_g ** 1.2))
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, min(alpha, 235)))

    frame = Image.alpha_composite(frame, overlay)
    draw2 = ImageDraw.Draw(frame)

    # Watermark kiri atas
    draw2.text((30, 30), "INFO BOLA ⚽", font=_cari_font(30), fill=(255, 255, 255, 210))

    # Judul besar uppercase di tengah bawah
    judul_bersih = re.sub(r'[^\w\s\-|:/!?.,]', '', judul).upper()[:70]
    judul_wrap   = _wrap(judul_bersih, max_chars=24)
    font_judul   = _cari_font(58)
    y_judul      = int(h * 0.55)

    jd_bbox = draw2.multiline_textbbox((0, 0), judul_wrap, font=font_judul, align="center")
    jd_x    = (w - (jd_bbox[2] - jd_bbox[0])) // 2
    for dx, dy in [(3, 3), (3, -3), (-2, 2)]:
        draw2.multiline_text((jd_x + dx, y_judul + dy), judul_wrap, font=font_judul,
                             fill=(0, 0, 0, 195), align="center")
    draw2.multiline_text((jd_x, y_judul), judul_wrap, font=font_judul,
                         fill=(255, 255, 255), align="center")

    # Garis merah di bawah judul
    baris = judul_wrap.count("\n") + 1
    y_garis = y_judul + baris * 70 + 12
    draw2.rectangle([(60, y_garis), (w - 60, y_garis + 4)], fill=(220, 30, 30, 220))

    # Satu poin pertama saja (jika ada)
    if poin_list:
        font_poin = _cari_font(32)
        poin_wrap = _wrap(poin_list[0][:70], max_chars=34)
        y_poin    = y_garis + 20
        pn_bbox   = draw2.multiline_textbbox((0, 0), poin_wrap, font=font_poin, align="center")
        pn_x      = (w - (pn_bbox[2] - pn_bbox[0])) // 2
        draw2.multiline_text((pn_x + 1, y_poin + 1), poin_wrap, font=font_poin,
                             fill=(0, 0, 0, 170), align="center")
        draw2.multiline_text((pn_x, y_poin), poin_wrap, font=font_poin,
                             fill=(255, 221, 68, 235), align="center")

    return np.array(frame.convert("RGB"))


# --------------------------------------------------------------------------- #
#  ENTRY POINT
# --------------------------------------------------------------------------- #

def buat_video(
    judul: str,
    caption: str,
    image_url: str,
    output_dir: str = "output",
    nama_file: str = "",
) -> str:
    """
    Buat video MP4 dari gambar AI + teks overlay + musik latar dengan efek Ken Burns.
    Return path file MP4, atau string kosong jika gagal.
    """
    if not MOVIEPY_AVAILABLE:
        log.warning("moviepy tidak tersedia, skip video generation")
        return ""

    img_path = ""
    try:
        log.info(f"Download gambar untuk video: {image_url[:70]}...")
        img_path = _download_image(image_url)

        # Siapkan frame dasar (1080×1080)
        img_base     = Image.open(img_path).convert("RGB")
        img_base     = img_base.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)
        img_base_arr = np.array(img_base)

        poin_list         = _ambil_poin(caption, max_poin=2)
        frame_dengan_teks = _buat_frame(img_base, judul, poin_list)

        # ── Video frames ──────────────────────────────────────────────────
        def make_frame(t: float) -> np.ndarray:
            """Ken Burns zoom 1.0x→1.18x; teks fade-in setelah 0.8 detik."""
            progress = t / DURASI
            scale    = 1.0 + 0.18 * progress

            h, w  = img_base_arr.shape[:2]
            new_h = int(h / scale)
            new_w = int(w / scale)
            y1    = (h - new_h) // 2
            x1    = (w - new_w) // 2
            zoomed = np.array(
                Image.fromarray(img_base_arr[y1:y1 + new_h, x1:x1 + new_w])
                    .resize((w, h), Image.LANCZOS)
            )
            if t < 0.8:
                return zoomed
            alpha = min(1.0, (t - 0.8) / 0.7)
            return (
                zoomed.astype(np.float32) * (1 - alpha)
                + frame_dengan_teks.astype(np.float32) * alpha
            ).astype(np.uint8)

        clip = VideoClip(make_frame, duration=DURASI)
        clip = clip.fadein(0.6).fadeout(0.6)

        # ── Musik latar ───────────────────────────────────────────────────
        log.info("Synthesizing background music...")
        musik_mono  = _buat_musik_latar(DURASI, SAMPLE_RATE)
        musik_stereo = np.column_stack([musik_mono, musik_mono])  # mono → stereo
        audio_clip  = AudioArrayClip(musik_stereo, fps=SAMPLE_RATE)
        audio_clip  = audio_clip.set_duration(DURASI)
        clip        = clip.set_audio(audio_clip)

        # ── Export ────────────────────────────────────────────────────────
        Path(output_dir).mkdir(exist_ok=True)
        if not nama_file:
            ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
            slug     = re.sub(r'\W+', '_', judul[:28].lower()).strip('_')
            nama_file = f"video_{slug}_{ts}.mp4"

        output_path = os.path.join(output_dir, nama_file)
        log.info(f"Render video (dengan musik) → {output_path}")

        clip.write_videofile(
            output_path,
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            audio_fps=SAMPLE_RATE,
            logger=None,
            threads=2,
            preset="ultrafast",
        )
        clip.close()
        audio_clip.close()
        log.info(f"Video selesai: {output_path}")
        return output_path

    except Exception as e:
        log.error(f"Gagal buat video: {e}", exc_info=True)
        return ""
    finally:
        if img_path and os.path.exists(img_path):
            try:
                os.unlink(img_path)
            except Exception:
                pass


# --------------------------------------------------------------------------- #
#  VIDEO BERITA VERTIKAL (9:16) — format siaran / Reels
# --------------------------------------------------------------------------- #

# Warna tema per topik / tipe posting
_WARNA_TOPIK = {
    # Topik khusus
    "timnas"            : (220, 30,  30),
    "liga1"             : (20,  120, 220),
    "persija"           : (220, 40,  40),
    "persib"            : (30,  80,  200),
    "manchester_united" : (200, 15,  15),
    "liga_champion"     : (15,  15,  100),
    # Tipe posting harian
    "transfer"          : (230, 100,  0),
    "viral"             : (160,  0,  200),
    "preview"           : (0,  130,  80),
    "rekap"             : (20,  20,  160),
    "statistik"         : (50,  50,   50),
    "polling"           : (0,  160,  160),
    "pengingat"         : (180,  0,   80),
    "klasemen"          : (180, 150,   0),
    "hype"              : (220,  80,   0),
    "football"          : (20,  130,  50),
}

_LABEL_TOPIK = {
    # Topik khusus
    "timnas"            : "🇮🇩 TIMNAS INDONESIA",
    "liga1"             : "🏆 BRI LIGA 1",
    "persija"           : "🔴 PERSIJA JAKARTA",
    "persib"            : "💙 PERSIB BANDUNG",
    "manchester_united" : "👹 MANCHESTER UNITED",
    "liga_champion"     : "⭐ UEFA CHAMPIONS LEAGUE",
    # Tipe posting harian
    "transfer"          : "🔄 BERITA TRANSFER",
    "viral"             : "🔥 TOPIK VIRAL",
    "preview"           : "📅 PREVIEW PERTANDINGAN",
    "rekap"             : "📊 REKAP HASIL",
    "statistik"         : "📈 STATISTIK MALAM",
    "polling"           : "🗳️ POLLING FANS",
    "pengingat"         : "⏰ REMINDER MATCH",
    "klasemen"          : "🥇 KLASEMEN LIGA",
    "hype"              : "🔥 COUNTDOWN MATCH",
    "football"          : "⚽ INFO BOLA",
}

REEL_W = 1080
REEL_H = 1920
REEL_DURASI = 15


def _buat_frame_berita(
    img_pil: "Image.Image",
    topik: str,
    headline: str,
) -> "np.ndarray":  # noqa: F821
    """
    Frame video berita full-bleed style siaran olahraga (ref: SCTV Sports / ESPN).
    Foto memenuhi seluruh frame 1080×1920. Gradient gelap di bawah 42%.
    Headline besar uppercase + badge topik berwarna + watermark atas.
    """
    warna = _WARNA_TOPIK.get(topik, (220, 30, 30))
    label = _LABEL_TOPIK.get(topik, "INFO BOLA")

    # Foto full-bleed
    canvas = img_pil.copy().convert("RGBA").resize((REEL_W, REEL_H), Image.LANCZOS)

    # Gradient: transparan di atas → hitam pekat di bawah (mulai 42%)
    overlay = Image.new("RGBA", (REEL_W, REEL_H), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    grad_start = int(REEL_H * 0.42)
    for y in range(grad_start, REEL_H):
        t_g   = (y - grad_start) / (REEL_H - grad_start)
        alpha = int(248 * (t_g ** 1.2))
        draw_ov.line([(0, y), (REEL_W, y)], fill=(0, 0, 0, min(alpha, 248)))
    canvas = Image.alpha_composite(canvas, overlay)

    draw = ImageDraw.Draw(canvas)

    # ── Watermark kanan atas ──────────────────────────────────────────────
    font_wm = _cari_font(32)
    draw.text((REEL_W - 30, 36), "INFO BOLA ⚽",
              font=font_wm, fill=(255, 255, 255, 220), anchor="rt")

    # ── Badge topik berwarna (di atas headline) ───────────────────────────
    font_badge = _cari_font(36)
    badge_text = f"  {label}  "
    badge_y    = REEL_H - 395

    bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    bw   = bbox[2] - bbox[0] + 24
    bh   = 56
    bx   = (REEL_W - bw) // 2

    draw.rectangle([(bx, badge_y), (bx + bw, badge_y + bh)], fill=(*warna, 255))
    draw.text((REEL_W // 2, badge_y + bh // 2), badge_text,
              font=font_badge, fill=(255, 255, 255), anchor="mm")

    # ── Hook visual — SANGAT PENDEK, gaya "EL CLASICO" ──────────────────
    # Ambil max 3 kata kunci paling penting (kata kapital / kata utama)
    kata_semua = re.sub(r'[^\w\s]', '', headline).split()
    # Prioritaskan kata yang diawali huruf kapital (nama tim/pemain/event)
    kata_penting = [k for k in kata_semua if k[0].isupper() and len(k) > 2][:3]
    if not kata_penting:
        kata_penting = kata_semua[:3]
    hook          = " ".join(kata_penting).upper()
    headline_wrap = _wrap(hook, max_chars=12)   # max 12 karakter per baris → 1-2 baris
    font_headline = _cari_font(96)              # besar dan bold
    y_hl          = badge_y + bh + 28

    hl_bbox = draw.multiline_textbbox((0, 0), headline_wrap, font=font_headline, align="center")
    hl_w    = hl_bbox[2] - hl_bbox[0]
    hl_x    = (REEL_W - hl_w) // 2

    for dx, dy in [(3, 3), (3, -3), (-3, 3), (-2, -2)]:
        draw.multiline_text((hl_x + dx, y_hl + dy), headline_wrap,
                            font=font_headline, fill=(0, 0, 0, 210), align="center")
    draw.multiline_text((hl_x, y_hl), headline_wrap,
                        font=font_headline, fill=(255, 255, 255), align="center")

    baris_hl  = headline_wrap.count("\n") + 1
    y_setelah = y_hl + baris_hl * 110

    # ── Garis aksen berwarna ──────────────────────────────────────────────
    garis_y = min(y_setelah + 18, REEL_H - 76)
    draw.rectangle([(60, garis_y), (REEL_W - 60, garis_y + 5)], fill=(*warna, 220))

    # ── Footer kecil ─────────────────────────────────────────────────────
    font_foot = _cari_font(27)
    foot_text = "INFO BOLA  -  Update Sepak Bola Terkini"
    foot_bbox = draw.textbbox((0, 0), foot_text, font=font_foot)
    foot_x    = (REEL_W - (foot_bbox[2] - foot_bbox[0])) // 2
    draw.text((foot_x, garis_y + 20), foot_text,
              font=font_foot, fill=(190, 190, 190, 210))

    return np.array(canvas.convert("RGB"))


def buat_video_berita(
    topik: str,
    headline: str,
    caption: str,
    image_url: str,
    output_dir: str = "output",
    nama_file: str = "",
) -> str:
    """
    Buat video Reels vertikal 1080×1920 style siaran olahraga.
    Foto pemain full-bleed + Ken Burns zoom + headline besar fade-in + musik.
    Return path file MP4, atau string kosong jika gagal.
    """
    if not MOVIEPY_AVAILABLE:
        log.warning("moviepy tidak tersedia, skip video berita")
        return ""

    img_path = ""
    try:
        # Untuk Pollinations, minta portrait 9:16. Untuk gambar landscape (RSS), tetap download.
        img_url_v = image_url
        if "image.pollinations.ai" in image_url:
            img_url_v = re.sub(r'width=\d+',  'width=1080',  image_url)
            img_url_v = re.sub(r'height=\d+', 'height=1920', img_url_v)

        log.info(f"Download gambar: {img_url_v[:70]}...")
        img_path = _download_image(img_url_v)

        img_raw  = Image.open(img_path).convert("RGB")
        orig_w, orig_h = img_raw.size
        is_landscape = orig_w > orig_h * 1.2   # landscape jika lebar > 1.2x tinggi

        if is_landscape:
            # Gambar landscape (mis. RSS BBC 16:9): blur + fill portrait
            # 1. Scale gambar agar lebar = REEL_W, posisi di tengah vertikal
            scale_w  = REEL_W / orig_w
            fit_w    = REEL_W
            fit_h    = int(orig_h * scale_w)
            img_fit  = img_raw.resize((fit_w, fit_h), Image.LANCZOS)
            # 2. Latar belakang: gambar di-blur + scale penuh ke frame
            import PIL.ImageFilter as _IF
            bg = img_raw.resize((REEL_W, REEL_H), Image.LANCZOS)
            bg = bg.filter(_IF.GaussianBlur(radius=22))
            # Gelapi latar agar tidak terlalu terang
            dark = Image.new("RGB", (REEL_W, REEL_H), (0, 0, 0))
            bg   = Image.blend(bg, dark, 0.45)
            # 3. Paste gambar asli di tengah vertikal
            y_offset = (REEL_H - fit_h) // 2
            bg.paste(img_fit, (0, y_offset))
            img_base = bg
        else:
            # Gambar portrait / square: smart crop ke 1080×1920
            scale = max(REEL_W / orig_w, REEL_H / orig_h)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)
            img_resized = img_raw.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - REEL_W) // 2
            top  = (new_h - REEL_H) // 2
            img_base = img_resized.crop((left, top, left + REEL_W, top + REEL_H))

        img_arr     = np.array(img_base)                  # (1920, 1080, 3)
        frame_teks  = _buat_frame_berita(img_base, topik, headline)  # statis dengan teks

        # Ken Burns: zoom perlahan 1.0x → 1.12x + fade-in teks setelah 0.8 detik
        def make_frame(t: float) -> np.ndarray:
            progress = t / REEL_DURASI
            scale_kb = 1.0 + 0.12 * progress
            h, w     = img_arr.shape[:2]
            new_h_kb = int(h / scale_kb)
            new_w_kb = int(w / scale_kb)
            y1 = (h - new_h_kb) // 2
            x1 = (w - new_w_kb) // 2
            zoomed = np.array(
                Image.fromarray(img_arr[y1:y1 + new_h_kb, x1:x1 + new_w_kb])
                    .resize((w, h), Image.LANCZOS)
            )
            if t < 0.8:
                return zoomed
            alpha = min(1.0, (t - 0.8) / 0.7)
            return (
                zoomed.astype(np.float32) * (1 - alpha)
                + frame_teks.astype(np.float32) * alpha
            ).astype(np.uint8)

        clip = VideoClip(make_frame, duration=REEL_DURASI)
        clip = clip.fadein(0.5).fadeout(0.5)

        # Musik latar
        musik_mono   = _buat_musik_latar(REEL_DURASI, SAMPLE_RATE)
        musik_stereo = np.column_stack([musik_mono, musik_mono])
        audio_clip   = AudioArrayClip(musik_stereo, fps=SAMPLE_RATE).set_duration(REEL_DURASI)
        clip         = clip.set_audio(audio_clip)

        Path(output_dir).mkdir(exist_ok=True)
        if not nama_file:
            ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
            slug      = re.sub(r'\W+', '_', topik)
            nama_file = f"reel_{slug}_{ts}.mp4"

        output_path = os.path.join(output_dir, nama_file)
        log.info(f"Render Reels video → {output_path}")

        clip.write_videofile(
            output_path,
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            audio_fps=SAMPLE_RATE,
            logger=None,
            threads=2,
            preset="fast",
            ffmpeg_params=["-crf", "20", "-profile:v", "high"],
        )
        clip.close()
        audio_clip.close()
        log.info(f"Reels video selesai: {output_path}")
        return output_path

    except Exception as e:
        log.error(f"Gagal buat video berita: {e}", exc_info=True)
        return ""
    finally:
        if img_path and os.path.exists(img_path):
            try:
                os.unlink(img_path)
            except Exception:
                pass
