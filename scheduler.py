"""
Penjadwal otomatis konten — jalankan sebagai service atau cron.
"""
import schedule
import time
import logging
from datetime import datetime
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


def job_preview_pertandingan():
    """Posting preview pertandingan hari ini — setiap pagi pukul 08:00."""
    log.info("Menjalankan: preview pertandingan hari ini")
    agent = FootballContentAgent()
    agent.posting_preview_hari_ini()


def job_rekap_hasil():
    """Posting rekap hasil — setiap malam pukul 23:00."""
    log.info("Menjalankan: rekap hasil pertandingan")
    agent = FootballContentAgent()
    agent.posting_rekap_kemarin()


def job_klasemen_mingguan():
    """Posting klasemen — setiap Senin pukul 10:00."""
    log.info("Menjalankan: update klasemen mingguan")
    agent = FootballContentAgent()
    agent.posting_klasemen("Premier League")


def main():
    import os
    os.makedirs("logs", exist_ok=True)

    log.info("Agent Konten Bola AKTIF")

    schedule.every().day.at("08:00").do(job_preview_pertandingan)
    schedule.every().day.at("23:00").do(job_rekap_hasil)
    schedule.every().monday.at("10:00").do(job_klasemen_mingguan)

    log.info("Jadwal terdaftar:")
    log.info("  - 08:00 setiap hari: Preview pertandingan")
    log.info("  - 23:00 setiap hari: Rekap hasil")
    log.info("  - 10:00 setiap Senin: Klasemen mingguan")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
