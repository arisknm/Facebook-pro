"""
CLI interaktif untuk agent konten bola.
Jalankan: python main.py
"""
import argparse
import json
import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

from agent import FootballContentAgent


def cetak_konten(konten: dict):
    print("\n" + "=" * 60)
    print("CAPTION FACEBOOK:")
    print("-" * 60)
    print(konten.get("facebook_caption", ""))
    print("\n" + "=" * 60)
    print("JUDUL YOUTUBE:")
    print("-" * 60)
    print(konten.get("youtube_title", ""))
    print("\n" + "=" * 60)
    print("DESKRIPSI YOUTUBE:")
    print("-" * 60)
    print(konten.get("youtube_description", ""))
    print("\n" + "=" * 60)
    print("TAGS YOUTUBE:")
    print("-" * 60)
    print(", ".join(konten.get("youtube_tags", [])))
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Agent Konten Bola — Facebook & YouTube",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  python main.py preview                    # Preview pertandingan hari ini
  python main.py rekap                      # Rekap hasil kemarin
  python main.py klasemen "Premier League"  # Analisis klasemen
  python main.py topik "El Clasico 2025"   # Konten topik bebas
  python main.py script "Top 5 Gol Minggu Ini" --durasi 7
  python main.py upload video.mp4 "Match Highlights" --privasi unlisted
  python main.py stats                      # Statistik channel
  python main.py jadwal                     # Jalankan scheduler otomatis
        """,
    )
    sub = parser.add_subparsers(dest="perintah")

    # preview
    p_prev = sub.add_parser("preview", help="Preview pertandingan hari ini")
    p_prev.add_argument("--facebook", action="store_true", default=False, help="Langsung posting ke Facebook")
    p_prev.add_argument("--no-simpan", action="store_true", help="Jangan simpan ke file")

    # rekap
    p_rekap = sub.add_parser("rekap", help="Rekap hasil kemarin")
    p_rekap.add_argument("--facebook", action="store_true", default=False)
    p_rekap.add_argument("--no-simpan", action="store_true")

    # klasemen
    p_kls = sub.add_parser("klasemen", help="Analisis klasemen liga")
    p_kls.add_argument("liga", nargs="?", default="Premier League")
    p_kls.add_argument("--facebook", action="store_true", default=False)

    # topik bebas
    p_topik = sub.add_parser("topik", help="Konten topik bebas")
    p_topik.add_argument("teks", help="Topik konten")
    p_topik.add_argument("--facebook", action="store_true", default=False)
    p_topik.add_argument("--gambar", default="", help="URL gambar untuk Facebook")

    # script video
    p_script = sub.add_parser("script", help="Buat script narasi video")
    p_script.add_argument("teks", help="Topik video")
    p_script.add_argument("--durasi", type=int, default=5, help="Durasi menit (default: 5)")

    # upload youtube
    p_up = sub.add_parser("upload", help="Upload video ke YouTube")
    p_up.add_argument("file", help="Path file video")
    p_up.add_argument("topik", help="Topik/judul video")
    p_up.add_argument("--privasi", default="public", choices=["public", "unlisted", "private"])

    # stats
    sub.add_parser("stats", help="Statistik Facebook & YouTube")

    # scheduler
    sub.add_parser("jadwal", help="Jalankan scheduler otomatis (daemon)")

    args = parser.parse_args()

    if not args.perintah:
        parser.print_help()
        sys.exit(0)

    agent = FootballContentAgent()

    if args.perintah == "preview":
        hasil = agent.posting_preview_hari_ini(
            ke_facebook=args.facebook,
            simpan_lokal=not args.no_simpan,
        )
        if "konten" in hasil:
            cetak_konten(hasil["konten"])

    elif args.perintah == "rekap":
        hasil = agent.posting_rekap_kemarin(
            ke_facebook=args.facebook,
            simpan_lokal=not args.no_simpan,
        )
        if "konten" in hasil:
            cetak_konten(hasil["konten"])

    elif args.perintah == "klasemen":
        hasil = agent.posting_klasemen(
            nama_liga=args.liga,
            ke_facebook=args.facebook,
        )
        if "konten" in hasil:
            cetak_konten(hasil["konten"])

    elif args.perintah == "topik":
        if args.gambar and args.facebook:
            hasil = agent.posting_ke_facebook_dengan_gambar(args.teks, args.gambar)
        else:
            konten = agent.buat_konten_topik(args.teks)
            if args.facebook:
                import facebook_publisher as fb_pub
                fb_pub.post_teks(konten["facebook_caption"])
            hasil = {"konten": konten}
        if "konten" in hasil:
            cetak_konten(hasil["konten"])

    elif args.perintah == "script":
        script = agent.buat_script_video(args.teks, args.durasi)
        print(script)

    elif args.perintah == "upload":
        hasil = agent.upload_video_ke_youtube(args.file, args.topik, args.privasi)
        print(json.dumps(hasil.get("youtube", {}), indent=2))
        if "konten" in hasil:
            cetak_konten(hasil["konten"])

    elif args.perintah == "stats":
        stats = agent.tampilkan_statistik()
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    elif args.perintah == "jadwal":
        from scheduler import main as run_scheduler
        print("Menjalankan scheduler... (Ctrl+C untuk berhenti)")
        run_scheduler()


if __name__ == "__main__":
    main()
