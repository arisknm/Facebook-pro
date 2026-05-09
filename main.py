"""
CLI interaktif untuk agent konten bola.
Jalankan: python main.py
"""
import argparse
import json
import sys
import logging
from datetime import datetime
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


def cetak_video_stats(stats: dict):
    print("\n" + "=" * 60)
    print(f"VIDEO  : {stats['title']}")
    print(f"ID     : {stats['video_id']}")
    print(f"URL    : {stats['url']}")
    print(f"Tayang : {stats['published_at']}")
    print(f"Durasi : {stats['duration']}")
    print("-" * 60)
    print(f"Views     : {stats['views']:,}")
    print(f"Likes     : {stats['likes']:,}")
    print(f"Komentar  : {stats['comments']:,}")
    print("=" * 60 + "\n")


def cetak_list_video(videos: list[dict]):
    print("\n" + "=" * 60)
    print(f"{'#':<4} {'Views':>8}  {'Likes':>7}  Judul")
    print("-" * 60)
    for i, v in enumerate(videos, 1):
        judul = v["title"][:45]
        print(f"{i:<4} {v['views']:>8,}  {v['likes']:>7,}  {judul}")
        print(f"     {v['url']}")
    print("=" * 60 + "\n")


def _parse_waktu(teks: str) -> datetime:
    """Parse string 'YYYY-MM-DD HH:MM' menjadi datetime."""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(teks, fmt)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"Format waktu tidak valid: '{teks}'. Gunakan YYYY-MM-DD HH:MM"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Agent Konten Bola — Facebook & YouTube",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  python main.py preview                           # Preview pertandingan hari ini
  python main.py rekap                             # Rekap hasil kemarin
  python main.py klasemen "Premier League"         # Analisis klasemen
  python main.py topik "El Clasico 2025"           # Konten topik bebas
  python main.py script "Top 5 Gol Minggu Ini" --durasi 7
  python main.py upload video.mp4 "Match Highlights"
  python main.py upload video.mp4 "Highlights" --privasi unlisted
  python main.py upload video.mp4 "Highlights" --jadwal "2025-06-01 20:00"
  python main.py yt-list                           # Daftar video channel
  python main.py yt-list --jumlah 20
  python main.py yt-video dQw4w9WgXcQ             # Statistik video
  python main.py yt-update dQw4w9WgXcQ --judul "Judul Baru"
  python main.py yt-update dQw4w9WgXcQ --privasi public
  python main.py stats                             # Statistik channel
  python main.py jadwal                            # Jalankan scheduler otomatis

Posting Facebook manual:
  python main.py transfer                          # Berita transfer (job 06:30)
  python main.py preview --facebook                # Preview pertandingan (job 08:00)
  python main.py polling                           # Polling interaktif (job 12:00)
  python main.py viral                             # Topik viral (job 15:00)
  python main.py pengingat                         # Pengingat malam (job 19:00)
  python main.py rekap --facebook                  # Rekap hasil (job 23:00)
  python main.py statistik                         # Statistik malam (job 23:30)
  python main.py semua                             # Posting SEMUA ke Facebook sekarang
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
    p_up.add_argument("topik", help="Topik/judul video (untuk generate konten AI)")
    p_up.add_argument(
        "--privasi",
        default="public",
        choices=["public", "unlisted", "private"],
        help="Status privasi (default: public)",
    )
    p_up.add_argument(
        "--jadwal",
        metavar="WAKTU",
        type=_parse_waktu,
        default=None,
        help="Jadwal publikasi, format: 'YYYY-MM-DD HH:MM' (WIB/lokal). "
             "Otomatis set privasi ke private hingga waktu publish.",
    )
    p_up.add_argument(
        "--thumbnail",
        metavar="FILE",
        default=None,
        help="Path gambar thumbnail (JPG/PNG) untuk diupload setelah video.",
    )

    # yt-list
    p_list = sub.add_parser("yt-list", help="Daftar video terbaru channel")
    p_list.add_argument("--jumlah", type=int, default=10, metavar="N", help="Jumlah video (default: 10)")

    # yt-video (stats)
    p_vid = sub.add_parser("yt-video", help="Statistik video tertentu")
    p_vid.add_argument("video_id", help="ID video YouTube (misal: dQw4w9WgXcQ)")

    # yt-update
    p_upd = sub.add_parser("yt-update", help="Update metadata video")
    p_upd.add_argument("video_id", help="ID video YouTube")
    p_upd.add_argument("--judul", default=None, help="Judul baru")
    p_upd.add_argument("--deskripsi", default=None, help="Deskripsi baru")
    p_upd.add_argument(
        "--tags",
        default=None,
        help="Tags baru, pisahkan dengan koma: 'bola,liga,gol'",
    )
    p_upd.add_argument(
        "--privasi",
        default=None,
        choices=["public", "unlisted", "private"],
        help="Status privasi baru",
    )

    # stats channel
    sub.add_parser("stats", help="Statistik Facebook & YouTube")

    # cek token
    sub.add_parser("cek-token", help="Verifikasi token Facebook (debug)")

    # scheduler
    sub.add_parser("jadwal", help="Jalankan scheduler otomatis (daemon)")

    # --- job harian manual ---
    sub.add_parser("transfer",  help="[Facebook] Berita transfer terkini (job 06:30)")
    sub.add_parser("polling",   help="[Facebook] Polling pertandingan malam ini (job 12:00)")
    p_topik_k = sub.add_parser("topik", help="[Facebook] Berita topik khusus rotasi harian (job 13:00)")
    p_topik_k.add_argument(
        "--topik",
        default="",
        choices=["timnas", "liga1", "persija", "persib", "manchester_united", "liga_champion", ""],
        help="Topik spesifik (default: rotasi otomatis berdasarkan hari)",
    )
    sub.add_parser("viral",     help="[Facebook] Topik viral sepak bola (job 15:00)")
    sub.add_parser("pengingat", help="[Facebook] Pengingat pertandingan malam (job 19:00)")
    sub.add_parser("statistik", help="[Facebook] Statistik menarik malam ini (job 23:30)")
    sub.add_parser("semua",     help="[Facebook] Posting SEMUA konten hari ini sekarang")

    args = parser.parse_args()

    if not args.perintah:
        parser.print_help()
        sys.exit(0)

    agent = FootballContentAgent()

    # ------------------------------------------------------------------ #

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
        hasil = agent.upload_video_ke_youtube(
            args.file,
            args.topik,
            privasi=args.privasi,
            waktu_publish=args.jadwal,
        )

        video_id = hasil.get("video_id", "")
        url = hasil.get("url", "")

        print("\n" + "=" * 60)
        print("UPLOAD BERHASIL")
        print("-" * 60)
        print(f"Video ID : {video_id}")
        print(f"URL      : {url}")
        if args.jadwal:
            print(f"Jadwal   : {args.jadwal.strftime('%Y-%m-%d %H:%M')} (privasi: private hingga publish)")
        print("=" * 60)

        if "konten" in hasil:
            cetak_konten(hasil["konten"])

        # Upload thumbnail jika disediakan
        if args.thumbnail and video_id:
            try:
                import youtube_publisher as yt_pub
                yt_pub.perbarui_thumbnail(video_id, args.thumbnail)
                print(f"Thumbnail diupload untuk video {video_id}")
            except Exception as e:
                print(f"Gagal upload thumbnail: {e}")

    elif args.perintah == "yt-list":
        videos = agent.list_video_youtube(args.jumlah)
        if not videos:
            print("Tidak ada video ditemukan di channel.")
        else:
            cetak_list_video(videos)

    elif args.perintah == "yt-video":
        stats = agent.stats_video_youtube(args.video_id)
        cetak_video_stats(stats)

    elif args.perintah == "yt-update":
        tags = None
        if args.tags:
            tags = [t.strip() for t in args.tags.split(",") if t.strip()]

        hasil = agent.perbarui_video_youtube(
            args.video_id,
            judul=args.judul,
            deskripsi=args.deskripsi,
            tags=tags,
            privasi=args.privasi,
        )
        print(json.dumps(hasil, indent=2, ensure_ascii=False))

    elif args.perintah == "stats":
        stats = agent.tampilkan_statistik()
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    elif args.perintah == "cek-token":
        import facebook_publisher as fb_pub
        print("Memeriksa token Facebook...")
        try:
            info = fb_pub.cek_token()
            print("\n✓ TOKEN VALID")
            print(f"  User/App: {info['token_user'].get('name', info['token_user'].get('id'))}")
            print(f"  Page    : {info['page'].get('name')} (ID: {info['page'].get('id')})")
            fans = info['page'].get('fan_count')
            if fans is not None:
                print(f"  Followers: {fans:,}")
            print("\nToken aktif — siap posting ke Facebook!")
        except Exception as e:
            print(f"\n✗ TOKEN BERMASALAH: {e}")
            print("\nSolusi:")
            print("1. Buka: https://developers.facebook.com/tools/explorer/")
            print("2. Pilih App → Generate Access Token")
            print("3. Tambahkan permission: pages_manage_posts, pages_read_engagement")
            print("4. Klik 'Generate Access Token'")
            print("5. Salin token baru ke .env atau GitHub Secrets")
            sys.exit(1)

    elif args.perintah == "jadwal":
        from scheduler import main as run_scheduler
        print("Menjalankan scheduler... (Ctrl+C untuk berhenti)")
        run_scheduler()

    elif args.perintah == "transfer":
        print("Posting berita transfer ke Facebook...")
        hasil = agent.posting_berita_transfer()
        if "konten" in hasil:
            cetak_konten(hasil["konten"])
        print(json.dumps(hasil.get("platform", []), indent=2, ensure_ascii=False))

    elif args.perintah == "topik":
        topik = getattr(args, "topik", "") or ""
        label = topik or "rotasi hari ini"
        print(f"Posting berita topik khusus ({label}) ke Facebook + Threads...")
        hasil = agent.posting_berita_topik_khusus(topik)
        if "konten" in hasil:
            print("\n" + "=" * 60)
            print(hasil["konten"].get("facebook_caption", ""))
            print("=" * 60)
        print(json.dumps(hasil.get("platform", []), indent=2, ensure_ascii=False))

    elif args.perintah == "polling":
        print("Posting polling interaktif ke Facebook...")
        hasil = agent.posting_polling()
        if "caption" in hasil:
            print("\n" + "=" * 60)
            print(hasil["caption"])
            print("=" * 60)
        print(json.dumps(hasil.get("platform", []), indent=2, ensure_ascii=False))

    elif args.perintah == "viral":
        print("Posting topik viral ke Facebook...")
        hasil = agent.posting_topik_viral()
        if "konten" in hasil:
            cetak_konten(hasil["konten"])
        print(json.dumps(hasil.get("platform", []), indent=2, ensure_ascii=False))

    elif args.perintah == "pengingat":
        print("Posting pengingat pertandingan ke Facebook...")
        hasil = agent.posting_pengingat_pertandingan()
        if "caption" in hasil:
            print("\n" + "=" * 60)
            print(hasil["caption"])
            print("=" * 60)
        print(json.dumps(hasil.get("platform", []), indent=2, ensure_ascii=False))

    elif args.perintah == "statistik":
        print("Posting statistik malam ke Facebook...")
        hasil = agent.posting_statistik_malam()
        if "caption" in hasil:
            print("\n" + "=" * 60)
            print(hasil["caption"])
            print("=" * 60)
        print(json.dumps(hasil.get("platform", []), indent=2, ensure_ascii=False))

    elif args.perintah == "semua":
        jobs = [
            ("Berita transfer",        agent.posting_berita_transfer),
            ("Preview pertandingan",   agent.posting_preview_hari_ini),
            ("Polling interaktif",     agent.posting_polling),
            ("Topik khusus hari ini",  agent.posting_berita_topik_khusus),
            ("Topik viral",            agent.posting_topik_viral),
            ("Pengingat pertandingan", agent.posting_pengingat_pertandingan),
            ("Rekap hasil kemarin",    agent.posting_rekap_kemarin),
            ("Statistik malam",        agent.posting_statistik_malam),
        ]
        print(f"\nMemposting {len(jobs)} konten ke Facebook...\n")
        for nama, fn in jobs:
            print(f"  [{nama}]...")
            try:
                hasil = fn()
                platform = hasil.get("platform", [])
                fb_ok = any("facebook" in p and "error" not in p for p in platform)
                status = "BERHASIL" if fb_ok else hasil.get("status", "tidak_ada_data")
            except Exception as e:
                status = f"ERROR: {e}"
            print(f"  → {status}\n")
        print("Selesai.")


if __name__ == "__main__":
    main()
