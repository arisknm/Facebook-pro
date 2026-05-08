"""
Generator video otomatis dari gambar AI + teks overlay.
Menggunakan moviepy + Pillow (ffmpeg sudah tersedia di GitHub Actions ubuntu-latest).
Teks dirender dengan Pillow agar tidak bergantung pada ImageMagick.
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
    from moviepy.editor import ImageClip, CompositeVideoClip, VideoClip
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    log.warning("moviepy/Pillow tidak tersedia — video generation dinonaktifkan")


VIDEO_W  = 1080
VIDEO_H  = 1080
DURASI   = 20    # detik
FPS      = 24


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
    bersih = [k.strip() for k in kalimat if len(re.sub(r'[^\w\s]', '', k)) > 15]
    return bersih[:max_poin]


def _cari_font(ukuran: int) -> ImageFont.ImageFont:
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
    """
    Tambahkan teks overlay ke gambar Pillow.
    Return numpy array RGBA.
    """
    frame = img_pil.copy().convert("RGBA")
    w, h = frame.size

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Gradient gelap di bagian bawah (55%-100% tinggi)
    zona_y = int(h * 0.52)
    for y in range(zona_y, h):
        alpha = int(200 * (y - zona_y) / (h - zona_y))
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

    frame = Image.alpha_composite(frame, overlay)
    draw2 = ImageDraw.Draw(frame)

    # Watermark kiri atas
    font_wm = _cari_font(30)
    draw2.text((30, 28), "INFO BOLA ⚽", font=font_wm, fill=(255, 255, 255, 200))

    # Judul besar
    judul_bersih = re.sub(r'[^\w\s\-|:/!]', '', judul)[:55]
    judul_wrap = _wrap(judul_bersih, max_chars=26)
    font_judul = _cari_font(54)
    y_judul = int(h * 0.57)
    # Shadow
    draw2.text((w // 2 + 2, y_judul + 2), judul_wrap, font=font_judul,
               fill=(0, 0, 0, 200), anchor="mt", align="center")
    draw2.text((w // 2, y_judul), judul_wrap, font=font_judul,
               fill=(255, 255, 255, 255), anchor="mt", align="center")

    # Poin caption
    font_poin = _cari_font(32)
    y_poin = y_judul + (judul_wrap.count("\n") + 1) * 64 + 18
    for poin in poin_list:
        poin_wrap = _wrap("• " + poin, max_chars=38)
        # Shadow
        draw2.text((w // 2 + 1, y_poin + 1), poin_wrap, font=font_poin,
                   fill=(0, 0, 0, 180), anchor="mt", align="center")
        draw2.text((w // 2, y_poin), poin_wrap, font=font_poin,
                   fill=(255, 221, 68, 240), anchor="mt", align="center")
        y_poin += (poin_wrap.count("\n") + 1) * 40 + 12

    return np.array(frame.convert("RGB"))


def buat_video(
    judul: str,
    caption: str,
    image_url: str,
    output_dir: str = "output",
    nama_file: str = "",
) -> str:
    """
    Buat video MP4 dari gambar AI + teks overlay dengan efek Ken Burns.
    Return path file MP4, atau string kosong jika gagal.
    """
    if not MOVIEPY_AVAILABLE:
        log.warning("moviepy tidak tersedia, skip video generation")
        return ""

    img_path = ""
    try:
        import numpy as np
        from moviepy.editor import VideoClip

        log.info(f"Download gambar untuk video: {image_url[:70]}...")
        img_path = _download_image(image_url)

        # Siapkan gambar dasar (square 1080x1080)
        img_base = Image.open(img_path).convert("RGB")
        img_base = img_base.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)

        poin_list = _ambil_poin(caption, max_poin=2)
        frame_dengan_teks = _buat_frame(img_base, judul, poin_list)
        img_base_arr = np.array(img_base)

        def make_frame(t: float) -> np.ndarray:
            """Ken Burns: zoom in perlahan 1.0x → 1.18x, teks muncul setelah 0.8 detik."""
            progress = t / DURASI
            scale    = 1.0 + 0.18 * progress

            h, w = img_base_arr.shape[:2]
            new_h = int(h / scale)
            new_w = int(w / scale)
            y1 = (h - new_h) // 2
            x1 = (w - new_w) // 2

            # Potong + resize balik ke 1080x1080
            cropped = img_base_arr[y1:y1 + new_h, x1:x1 + new_w]
            zoomed = np.array(Image.fromarray(cropped).resize((w, h), Image.LANCZOS))

            if t < 0.8:
                return zoomed

            # Blend teks overlay (muncul fade-in 0.8–1.5 detik)
            alpha_teks = min(1.0, (t - 0.8) / 0.7)
            blended = (
                zoomed.astype(np.float32) * (1 - alpha_teks)
                + frame_dengan_teks.astype(np.float32) * alpha_teks
            ).astype(np.uint8)

            # Gambar di bagian bawah juga perlu di-zoom — pakai yang sudah ter-crop
            # Tapi kita pakai frame_dengan_teks sebagai target akhir
            return blended

        clip = VideoClip(make_frame, duration=DURASI)
        clip = clip.fadein(0.6).fadeout(0.6)

        Path(output_dir).mkdir(exist_ok=True)
        if not nama_file:
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            slug = re.sub(r'\W+', '_', judul[:28].lower()).strip('_')
            nama_file = f"video_{slug}_{ts}.mp4"

        output_path = os.path.join(output_dir, nama_file)
        log.info(f"Render video → {output_path}")

        clip.write_videofile(
            output_path,
            fps=FPS,
            codec="libx264",
            audio=False,
            logger=None,
            threads=2,
            preset="ultrafast",
        )
        clip.close()
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
