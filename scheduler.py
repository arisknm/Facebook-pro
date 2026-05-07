"""
Penjadwal otomatis konten — jalankan sebagai service atau cron.

Jadwal harian:
  06:30  Berita transfer pagi              → Facebook
  08:00  Preview pertandingan hari ini     → Facebook
  12:00  Polling interaktif malam ini      → Facebook
  15:00  Topik viral sepak bola            → Facebook
  19:00  Pengingat pertandingan malam      → Facebook
  21:00  Upload video dari folder videos/  → YouTube
  23:00  Rekap hasil pertandingan          → Facebook
  23:30  Statistik menarik malam ini       → Facebook

Jadwal mingguan:
  Senin 10:00  Analisis klasemen Premier League → Facebook
"""
import os
import logging
import schedule
import time
from agent import FootballContentAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/agent.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def _agent() -> FootballContentAgent:
    return FootballContentAgent()


# ------------------------------------------------------------------ #
#  JOBS
# ------------------------------------------------------------------ #

def job_berita_transfer():
    """06:30 — Berita transfer terkini."""
    try:
        _agent().posting_berita_transfer()
    except Exception as e:
        log.error(f"[06:30] job_berita_transfer gagal: {e}")


def job_preview_pertandingan():
    """08:00 — Preview pertandingan hari ini."""
    try:
        _agent().posting_preview_hari_ini()
    except Exception as e:
        log.error(f"[08:00] job_preview_pertandingan gagal: {e}")


def job_polling():
    """12:00 — Polling interaktif pertandingan malam."""
    try:
        _agent().posting_polling()
    except Exception as e:
        log.error(f"[12:00] job_polling gagal: {e}")


def job_topik_viral():
    """15:00 — Topik viral sepak bola."""
    try:
        _agent().posting_topik_viral()
    except Exception as e:
        log.error(f"[15:00] job_topik_viral gagal: {e}")


def job_pengingat_pertandingan():
    """19:00 — Pengingat pertandingan malam ini."""
    try:
        _agent().posting_pengingat_pertandingan()
    except Exception as e:
        log.error(f"[19:00] job_pengingat_pertandingan gagal: {e}")


def job_upload_video():
    """21:00 — Upload video dari folder videos/."""
    try:
        hasil = _agent().upload_video_folder_otomatis()
        n = len([r for r in hasil.get("uploaded", []) if "error" not in r])
        log.info(f"[21:00] Upload selesai: {n} video berhasil diupload.")
    except Exception as e:
        log.error(f"[21:00] job_upload_video gagal: {e}")


def job_rekap_hasil():
    """23:00 — Rekap hasil pertandingan."""
    try:
        _agent().posting_rekap_kemarin()
    except Exception as e:
        log.error(f"[23:00] job_rekap_hasil gagal: {e}")


def job_statistik_malam():
    """23:30 — Statistik menarik malam ini."""
    try:
        _agent().posting_statistik_malam()
    except Exception as e:
        log.error(f"[23:30] job_statistik_malam gagal: {e}")


def job_klasemen_mingguan():
    """Senin 10:00 — Update klasemen mingguan."""
    try:
        _agent().posting_klasemen("Premier League")
    except Exception as e:
        log.error(f"[Senin 10:00] job_klasemen_mingguan gagal: {e}")


# ------------------------------------------------------------------ #
#  MAIN
# ------------------------------------------------------------------ #

def main():
    os.makedirs("logs", exist_ok=True)
    os.makedirs("videos", exist_ok=True)
    os.makedirs("videos/uploaded", exist_ok=True)

    log.info("=" * 55)
    log.info("  AGENT KONTEN BOLA — SCHEDULER AKTIF")
    log.info("=" * 55)

    # Daftar semua job
    schedule.every().day.at("06:30").do(job_berita_transfer)
    schedule.every().day.at("08:00").do(job_preview_pertandingan)
    schedule.every().day.at("12:00").do(job_polling)
    schedule.every().day.at("15:00").do(job_topik_viral)
    schedule.every().day.at("19:00").do(job_pengingat_pertandingan)
    schedule.every().day.at("21:00").do(job_upload_video)
    schedule.every().day.at("23:00").do(job_rekap_hasil)
    schedule.every().day.at("23:30").do(job_statistik_malam)
    schedule.every().monday.at("10:00").do(job_klasemen_mingguan)

    log.info("Jadwal terdaftar:")
    log.info("  06:30  Berita transfer pagi        → Facebook")
    log.info("  08:00  Preview pertandingan         → Facebook")
    log.info("  12:00  Polling interaktif           → Facebook")
    log.info("  15:00  Topik viral                  → Facebook")
    log.info("  19:00  Pengingat pertandingan        → Facebook")
    log.info("  21:00  Upload video (folder videos/) → YouTube")
    log.info("  23:00  Rekap hasil                  → Facebook")
    log.info("  23:30  Statistik malam              → Facebook")
    log.info("  Senin 10:00  Klasemen mingguan       → Facebook")
    log.info("=" * 55)
    log.info("Tekan Ctrl+C untuk berhenti.\n")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
