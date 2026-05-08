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
    from moviepy.editor import ImageClip, CompositeVideoClip, VideoClip, AudioArrayClip
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    log.warning("moviepy/Pillow tidak tersedia — video generation dinonaktifkan")


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
          attack: float = 0.01, release: float = 0.08) -> np.ndarray:
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


def _kick(sr: int, dur: float = 0.18) -> np.ndarray:
    """Bass drum sintetis."""
    n   = int(sr * dur)
    t   = np.linspace(0, dur, n, endpoint=False)
    env = np.exp(-t * 28)
    # Pitch envelope: mulai 150 Hz turun ke 50 Hz
    pitch = 150 * np.exp(-t * 35) + 50
    phase = np.cumsum(2 * np.pi * pitch / sr)
    return env * np.sin(phase) * 0.90


def _snare(sr: int, dur: float = 0.12) -> np.ndarray:
    """Snare drum sintetis (noise + nada)."""
    n    = int(sr * dur)
    t    = np.linspace(0, dur, n, endpoint=False)
    env  = np.exp(-t * 38)
    noise = np.random.default_rng(42).standard_normal(n)
    tone = np.sin(2 * np.pi * 220 * t)
    return env * (noise * 0.6 + tone * 0.4) * 0.55


def _hihat(sr: int, dur: float = 0.06, open_hat: bool = False) -> np.ndarray:
    """Hi-hat sintetis."""
    n   = int(sr * dur)
    t   = np.linspace(0, dur, n, endpoint=False)
    decay = 10 if open_hat else 60
    env  = np.exp(-t * decay)
    noise = np.random.default_rng(7).standard_normal(n)
    # High-pass: ambil komponen frekuensi tinggi saja
    hp = noise - np.convolve(noise, np.ones(8)/8, mode='same')
    return env * hp * 0.30


def _pad_chord(freqs: list, dur: float, sr: int, amp: float = 0.18) -> np.ndarray:
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


def _buat_musik_latar(durasi: float, sr: int = SAMPLE_RATE) -> np.ndarray:
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

def _download_image(url: str, timeout: int = 90) -> str:
    """Download gambar dari URL ke file sementara, return path."""
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


def _buat_frame(img_pil: "Image.Image", judul: str, poin_list: list[str]) -> "np.ndarray":
    """Tambahkan teks overlay ke gambar Pillow. Return numpy array RGB."""
    frame = img_pil.copy().convert("RGBA")
    w, h  = frame.size

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    # Gradient gelap bagian bawah (52%–100%)
    zona_y = int(h * 0.52)
    for y in range(zona_y, h):
        alpha = int(200 * (y - zona_y) / (h - zona_y))
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

    frame  = Image.alpha_composite(frame, overlay)
    draw2  = ImageDraw.Draw(frame)

    # Watermark
    draw2.text((30, 28), "INFO BOLA ⚽", font=_cari_font(30), fill=(255, 255, 255, 200))

    # Judul
    judul_bersih = re.sub(r'[^\w\s\-|:/!]', '', judul)[:55]
    judul_wrap   = _wrap(judul_bersih, max_chars=26)
    font_judul   = _cari_font(54)
    y_judul      = int(h * 0.57)
    draw2.text((w // 2 + 2, y_judul + 2), judul_wrap, font=font_judul,
               fill=(0, 0, 0, 200), anchor="mt", align="center")
    draw2.text((w // 2, y_judul), judul_wrap, font=font_judul,
               fill=(255, 255, 255, 255), anchor="mt", align="center")

    # Poin caption
    font_poin = _cari_font(32)
    y_poin    = y_judul + (judul_wrap.count("\n") + 1) * 64 + 18
    for poin in poin_list:
        poin_wrap = _wrap("• " + poin, max_chars=38)
        draw2.text((w // 2 + 1, y_poin + 1), poin_wrap, font=font_poin,
                   fill=(0, 0, 0, 180), anchor="mt", align="center")
        draw2.text((w // 2, y_poin), poin_wrap, font=font_poin,
                   fill=(255, 221, 68, 240), anchor="mt", align="center")
        y_poin += (poin_wrap.count("\n") + 1) * 40 + 12

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
        import numpy as np
        from moviepy.editor import VideoClip, AudioArrayClip

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
