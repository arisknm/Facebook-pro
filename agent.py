"""
Agent utama: orkestrasi pengambilan data, pembuatan konten, dan publishing.
"""
import os
import glob
import json
import shutil
import logging
from datetime import datetime, timezone
from pathlib import Path

from config import LIGA_FAVORIT, OUTPUT_DIR
import football_api as api
import content_generator as gen
import facebook_publisher as fb
import youtube_publisher as yt
import news_api as news
import video_generator as vg
import threads_publisher as threads
import affiliate as aff
from config import THREADS_USER_ID, THREADS_ACCESS_TOKEN

log = logging.getLogger(__name__)


def _fixture_selesai(f: dict) -> bool:
    status = (f.get("strStatus") or f.get("fixture", {}).get("status", {}).get("short", "")).lower()
    skor_h = f.get("intHomeScore") or f.get("goals", {}).get("home")
    skor_a = f.get("intAwayScore") or f.get("goals", {}).get("away")
    return status in ("match finished", "ft", "aet", "pen", "aot", "ap") or (
        skor_h is not None and skor_a is not None
    )


class FootballContentAgent:
    """Agent konten bola yang mengintegrasikan semua modul."""

    def __init__(self):
        Path(OUTPUT_DIR).mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)

    # ------------------------------------------------------------------ #
    #  POSTING OTOMATIS
    # ------------------------------------------------------------------ #

    def posting_preview_hari_ini(
        self,
        ke_facebook: bool = True,
        ke_youtube: bool = False,
        simpan_lokal: bool = True,
    ) -> dict:
        """Ambil jadwal hari ini → buat konten → posting ke platform.
        Jika tidak ada pertandingan hari ini, cari mendatang dan posting hype countdown.
        """
        log.info("Mengambil data pertandingan hari ini...")
        fixtures = api.get_fixtures_hari_ini()

        if not fixtures:
            log.warning("Tidak ada pertandingan hari ini, mencari pertandingan mendatang...")
            mendatang = api.get_fixtures_mendatang(max_hari=7)
            if not mendatang:
                return {"status": "tidak_ada_pertandingan"}
            hari_lagi, fixtures_depan = mendatang[0]
            label = "besok" if hari_lagi == 1 else f"{hari_lagi} hari lagi"
            log.info(f"Ditemukan pertandingan {label}, membuat konten hype countdown...")
            fixture_teks = [api.format_fixture_untuk_prompt(f) for f in fixtures_depan]
            konten = gen.buat_hype_mendatang(fixture_teks, hari_lagi)
            hasil = {"konten": konten, "platform": [], "countdown": f"H-{hari_lagi}"}
            if simpan_lokal:
                self._simpan_konten(f"hype_h{hari_lagi}", konten)
            if ke_facebook and konten.get("facebook_caption"):
                teams = api.format_fixture_untuk_prompt(fixtures_depan[0])
                image_url = gen.generate_image_url(f"H-{hari_lagi} {teams}", style="hype")
                self._post_facebook(konten["facebook_caption"], hasil, image_url,
                                    judul=konten.get("youtube_title", f"H-{hari_lagi} Big Match!"),
                                    tipe_aff="hype")
            return hasil

        fixture_teks = [api.format_fixture_untuk_prompt(f) for f in fixtures]
        log.info(f"Ditemukan {len(fixtures)} pertandingan. Membuat konten...")

        konten = gen.buat_preview_pertandingan(fixture_teks)
        hasil = {"konten": konten, "platform": []}

        if simpan_lokal:
            self._simpan_konten("preview", konten)

        if ke_facebook and konten.get("facebook_caption"):
            teams = " vs ".join([api.format_fixture_untuk_prompt(f) for f in fixtures[:1]])
            image_url = gen.generate_image_url(teams, style="football")
            self._post_facebook(konten["facebook_caption"], hasil, image_url,
                                judul=konten.get("youtube_title", "Preview Pertandingan Hari Ini"),
                                tipe_aff="preview")

        if ke_youtube and konten.get("youtube_title"):
            log.info("YouTube: diperlukan file video. Gunakan upload_video_ke_youtube().")
            hasil["platform"].append({"youtube": "manual_upload_required"})

        return hasil

    def posting_rekap_kemarin(
        self,
        ke_facebook: bool = True,
        simpan_lokal: bool = True,
    ) -> dict:
        """Ambil hasil kemarin → buat rekap → posting."""
        log.info("Mengambil hasil pertandingan kemarin...")
        fixtures = api.get_fixtures_kemarin()
        selesai = [f for f in fixtures if _fixture_selesai(f)]

        if not selesai:
            log.warning("Tidak ada pertandingan selesai kemarin.")
            return {"status": "tidak_ada_hasil"}

        fixture_teks = [api.format_fixture_untuk_prompt(f) for f in selesai]
        konten = gen.buat_rekap_hasil(fixture_teks)
        hasil = {"konten": konten, "platform": []}

        if simpan_lokal:
            self._simpan_konten("rekap", konten)

        if ke_facebook and konten.get("facebook_caption"):
            teams = " vs ".join([api.format_fixture_untuk_prompt(f) for f in selesai[:1]])
            image_url = gen.generate_image_url(f"rekap hasil {teams}", style="football")
            self._post_facebook(konten["facebook_caption"], hasil, image_url,
                                judul=konten.get("youtube_title", "Rekap Hasil Pertandingan"),
                                tipe_aff="rekap")

        return hasil

    def posting_klasemen(
        self,
        nama_liga: str,
        ke_facebook: bool = True,
        simpan_lokal: bool = True,
    ) -> dict:
        """Ambil klasemen → buat konten → posting."""
        if nama_liga not in api.LIGA_ID:
            raise ValueError(f"Liga tidak dikenal: {nama_liga}")

        log.info(f"Mengambil klasemen {nama_liga}...")
        standings = api.get_standings(nama_liga)

        if not standings:
            return {"status": "gagal_ambil_klasemen"}

        baris = []
        for i, tim in enumerate(standings[:5], 1):
            nama = tim.get("team", {}).get("name") or tim.get("strTeam", "")
            poin = tim.get("points") or tim.get("intPoints", 0)
            baris.append(f"{i}. {nama} — {poin} poin")
        baris.append("...")
        for tim in standings[-3:]:
            nama = tim.get("team", {}).get("name") or tim.get("strTeam", "")
            rank = tim.get("rank") or tim.get("intRank", "?")
            poin = tim.get("points") or tim.get("intPoints", 0)
            baris.append(f"{rank}. {nama} — {poin} poin ⚠️")

        standings_teks = "\n".join(baris)
        konten = gen.buat_analisis_klasemen(nama_liga, standings_teks)
        hasil = {"konten": konten, "platform": []}

        if simpan_lokal:
            self._simpan_konten(f"klasemen_{nama_liga.lower().replace(' ', '_')}", konten)

        if ke_facebook and konten.get("facebook_caption"):
            image_url = gen.generate_image_url(f"klasemen {nama_liga}", style="klasemen")
            self._post_facebook(konten["facebook_caption"], hasil, image_url,
                                judul=konten.get("youtube_title", f"Klasemen {nama_liga}"),
                                tipe_aff="klasemen")

        return hasil

    # ------------------------------------------------------------------ #
    #  JADWAL HARIAN OTOMATIS
    # ------------------------------------------------------------------ #

    def posting_berita_transfer(self) -> dict:
        """06:30 — Berita transfer terkini dari RSS feed."""
        log.info("Job 06:30: berita transfer pagi")
        berita = news.get_transfer_news(jumlah=5)
        if not berita:
            log.warning("Tidak ada berita transfer ditemukan.")
            return {"status": "tidak_ada_berita"}
        berita_teks = news.format_berita_untuk_prompt(berita)
        konten = gen.buat_konten_berita_transfer(berita_teks)
        self._simpan_konten("transfer_pagi", konten)
        hasil = {"konten": konten, "platform": []}
        image_url = next((b["image_url"] for b in berita if b.get("image_url")), "")
        if not image_url:
            image_url = gen.generate_image_url(berita[0]["title"], style="transfer")
        self._post_facebook(konten["facebook_caption"], hasil, image_url,
                            judul=konten.get("youtube_title", "Berita Transfer Terkini"),
                            tipe_aff="transfer")
        return hasil

    def posting_polling(self) -> dict:
        """12:00 — Polling interaktif pertandingan malam ini atau mendatang."""
        log.info("Job 12:00: polling pertandingan malam")
        fixtures = api.get_fixtures_hari_ini()
        if not fixtures:
            mendatang = api.get_fixtures_mendatang(max_hari=3)
            if not mendatang:
                return {"status": "tidak_ada_pertandingan"}
            _, fixtures = mendatang[0]
        fixture_teks = [api.format_fixture_untuk_prompt(f) for f in fixtures]
        caption = gen.buat_polling_interaktif(fixture_teks)
        hasil = {"caption": caption, "platform": []}
        image_url = gen.generate_image_url(fixture_teks[0] if fixture_teks else "football poll", style="football")
        self._post_facebook(caption, hasil, image_url, judul="Prediksi Kamu Siapa?", tipe_aff="polling")
        return hasil

    def posting_topik_viral(self) -> dict:
        """15:00 — Konten topik viral sepak bola sore hari."""
        log.info("Job 15:00: topik viral sore")
        berita = news.get_viral_topics(jumlah=5)
        if not berita:
            log.warning("Tidak ada topik viral ditemukan.")
            return {"status": "tidak_ada_topik"}
        berita_teks = news.format_berita_untuk_prompt(berita)
        konten = gen.buat_konten_topik_viral(berita_teks)
        self._simpan_konten("viral_sore", konten)
        hasil = {"konten": konten, "platform": []}
        image_url = next((b["image_url"] for b in berita if b.get("image_url")), "")
        if not image_url:
            image_url = gen.generate_image_url(berita[0]["title"], style="viral")
        self._post_facebook(konten["facebook_caption"], hasil, image_url,
                            judul=konten.get("youtube_title", "Topik Viral Sepak Bola"),
                            tipe_aff="viral")
        return hasil

    def posting_pengingat_pertandingan(self) -> dict:
        """19:00 — Pengingat pertandingan malam ini atau hype mendatang."""
        log.info("Job 19:00: pengingat pertandingan")
        fixtures = api.get_fixtures_hari_ini()
        if not fixtures:
            mendatang = api.get_fixtures_mendatang(max_hari=3)
            if not mendatang:
                return {"status": "tidak_ada_pertandingan"}
            _, fixtures = mendatang[0]
        fixture_teks = [api.format_fixture_untuk_prompt(f) for f in fixtures]
        caption = gen.buat_pengingat_pertandingan(fixture_teks)
        hasil = {"caption": caption, "platform": []}
        image_url = gen.generate_image_url(
            fixture_teks[0] if fixture_teks else "football match tonight", style="hype"
        )
        self._post_facebook(caption, hasil, image_url, judul="Pertandingan Malam Ini!", tipe_aff="pengingat")
        return hasil

    def upload_video_folder_otomatis(self, folder: str = "videos") -> dict:
        """21:00 — Upload semua .mp4 di folder ke YouTube, lalu pindah ke uploaded/."""
        log.info(f"Job 21:00: scan folder '{folder}' untuk upload YouTube")
        Path(folder).mkdir(exist_ok=True)
        uploaded_dir = Path(folder) / "uploaded"
        uploaded_dir.mkdir(exist_ok=True)

        video_files = sorted(glob.glob(f"{folder}/*.mp4"))
        if not video_files:
            log.info("Tidak ada file .mp4 di folder videos/.")
            return {"status": "tidak_ada_video", "uploaded": []}

        hasil_list = []
        for file_path in video_files:
            topik = Path(file_path).stem.replace("_", " ").replace("-", " ")
            log.info(f"Mengupload: {file_path} (topik: {topik})")
            try:
                hasil = self.upload_video_ke_youtube(file_path, topik)
                shutil.move(file_path, str(uploaded_dir / Path(file_path).name))
                hasil_list.append({"file": file_path, "result": hasil})
                log.info(f"Selesai: {file_path} → {hasil.get('url')}")
            except Exception as e:
                log.error(f"Gagal upload {file_path}: {e}")
                hasil_list.append({"file": file_path, "error": str(e)})

        return {"status": "selesai", "uploaded": hasil_list}

    def posting_statistik_malam(self) -> dict:
        """23:30 — Statistik menarik dari pertandingan tadi malam."""
        log.info("Job 23:30: statistik malam")
        fixtures = api.get_fixtures_kemarin()
        selesai = [f for f in fixtures if _fixture_selesai(f)]
        if not selesai:
            log.warning("Tidak ada pertandingan selesai untuk statistik.")
            return {"status": "tidak_ada_data"}
        fixture_teks = [api.format_fixture_untuk_prompt(f) for f in selesai]
        caption = gen.buat_statistik_malam(fixture_teks)
        hasil = {"caption": caption, "platform": []}
        image_url = gen.generate_image_url("football match statistics highlights", style="statistik")
        self._post_facebook(caption, hasil, image_url, judul="Statistik Pertandingan Semalam", tipe_aff="statistik")
        return hasil

    def posting_berita_topik_khusus(self, topik: str = "") -> dict:
        """
        Job berita topik khusus — rotasi harian:
        Timnas | Liga 1 | Persija | Persib | Man Utd | Liga Champion
        Buat video vertikal 9:16 (Reels format) + post ke FB & Threads.
        """
        if not topik:
            topik = news.get_topik_pundit_hari_ini()

        label_map = {
            "timnas"            : "Timnas Indonesia",
            "liga1"             : "BRI Liga 1",
            "persija"           : "Persija Jakarta",
            "persib"            : "Persib Bandung",
            "manchester_united" : "Manchester United",
            "liga_champion"     : "Liga Champions",
        }
        label = label_map.get(topik, topik)
        log.info(f"Job topik khusus: {label}")

        berita = news.get_berita_pundit(topik, jumlah=5)
        if not berita:
            log.warning(f"Tidak ada berita untuk topik '{topik}'")
            return {"status": "tidak_ada_berita", "topik": topik}

        berita_teks = news.format_berita_untuk_prompt(berita)
        konten      = gen.buat_konten_topik_khusus(berita_teks, topik)
        self._simpan_konten(f"topik_{topik}", konten)

        hasil     = {"konten": konten, "platform": [], "topik": topik}
        headline  = konten.get("headline_video") or berita[0]["title"]
        poin_list = konten.get("poin_video", [])
        caption   = konten.get("facebook_caption", "")

        # Gambar background (portrait untuk video vertikal)
        image_url = next((b["image_url"] for b in berita if b.get("image_url")), "")
        if not image_url:
            style_map = {
                "timnas": "football", "liga1": "football",
                "persija": "football", "persib": "football",
                "manchester_united": "football", "liga_champion": "klasemen",
            }
            image_url = gen.generate_image_url(
                f"{label} football", style=style_map.get(topik, "football")
            )

        # Buat video vertikal 9:16
        video_path = vg.buat_video_berita(
            topik=topik,
            headline=headline,
            caption=caption,
            image_url=image_url,
        )

        try:
            if video_path:
                res = fb.upload_video_file(caption, video_path, headline)
                log.info(f"Facebook: video berita {label} — ID {res.get('id')}")
                hasil["platform"].append({"facebook": res, "tipe": "reel"})
                try:
                    os.unlink(video_path)
                except Exception:
                    pass
            else:
                # Fallback ke foto
                res = fb.post_dengan_gambar(caption, image_url)
                hasil["platform"].append({"facebook": res, "tipe": "foto"})
        except Exception as e:
            log.error(f"Facebook gagal: {e}")
            try:
                res = fb.post_teks(caption)
                hasil["platform"].append({"facebook": res, "tipe": "teks_fallback"})
            except Exception as e2:
                hasil["platform"].append({"facebook_error": str(e2)})

        # Threads
        if THREADS_USER_ID and THREADS_ACCESS_TOKEN:
            try:
                res_t = threads.post_dengan_gambar(caption, image_url)
                log.info(f"Threads: berita {label} — ID {res_t.get('id')}")
                hasil["platform"].append({"threads": res_t})
            except Exception as et:
                log.warning(f"Threads gagal: {et}")

        return hasil

    # ------------------------------------------------------------------ #
    #  KONTEN MANUAL
    # ------------------------------------------------------------------ #

    def buat_konten_topik(self, topik: str, simpan_lokal: bool = True) -> dict:
        """Buat konten bertopik bebas tanpa posting otomatis."""
        log.info(f"Membuat konten untuk topik: {topik}")
        konten = gen.buat_konten_bebas(topik)
        if simpan_lokal:
            slug = topik[:30].lower().replace(" ", "_")
            self._simpan_konten(f"topik_{slug}", konten)
        return konten

    def buat_script_video(self, topik: str, durasi: int = 5) -> str:
        """Buat script video YouTube."""
        log.info(f"Membuat script video: {topik}")
        script = gen.buat_script_video(topik, durasi)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = topik[:30].lower().replace(" ", "_")
        path = os.path.join(OUTPUT_DIR, f"script_{slug}_{ts}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(script)
        log.info(f"Script disimpan: {path}")
        return script

    def upload_video_ke_youtube(
        self,
        file_path: str,
        topik: str,
        privasi: str = "public",
        waktu_publish: datetime | None = None,
    ) -> dict:
        """Generate konten YouTube lalu upload video (dengan progress & retry)."""
        konten = gen.buat_konten_bebas(topik)
        log.info(f"Mengupload video: {file_path}")
        res = yt.upload_video(
            file_path=file_path,
            judul=konten["youtube_title"],
            deskripsi=konten["youtube_description"],
            tags=konten["youtube_tags"],
            privasi=privasi,
            waktu_publish=waktu_publish,
        )
        video_id = res.get("id", "")
        url = f"https://youtu.be/{video_id}" if video_id else ""
        log.info(f"YouTube: video diupload — ID {video_id} | {url}")
        return {"youtube": res, "video_id": video_id, "url": url, "konten": konten}

    def perbarui_video_youtube(
        self,
        video_id: str,
        judul: str | None = None,
        deskripsi: str | None = None,
        tags: list[str] | None = None,
        privasi: str | None = None,
    ) -> dict:
        """Update metadata video YouTube yang sudah ada."""
        return yt.perbarui_video(video_id, judul, deskripsi, tags, privasi)

    def stats_video_youtube(self, video_id: str) -> dict:
        """Ambil statistik video tertentu."""
        return yt.get_video_stats(video_id)

    def list_video_youtube(self, max_results: int = 10) -> list[dict]:
        """Ambil daftar video terbaru dari channel."""
        return yt.list_videos(max_results)

    def posting_ke_facebook_dengan_gambar(self, topik: str, url_gambar: str) -> dict:
        """Buat caption + posting foto ke Facebook."""
        konten = gen.buat_konten_bebas(topik)
        res = fb.post_dengan_gambar(konten["facebook_caption"], url_gambar)
        return {"facebook": res, "konten": konten}

    # ------------------------------------------------------------------ #
    #  STATISTIK
    # ------------------------------------------------------------------ #

    def tampilkan_statistik(self) -> dict:
        """Tampilkan statistik Facebook dan YouTube."""
        stats = {}
        try:
            stats["facebook"] = fb.get_page_insights()
        except Exception as e:
            stats["facebook_error"] = str(e)
        try:
            stats["youtube"] = yt.get_channel_stats()
        except Exception as e:
            stats["youtube_error"] = str(e)
        return stats

    # ------------------------------------------------------------------ #
    #  HELPER
    # ------------------------------------------------------------------ #

    def _post_facebook(self, caption: str, hasil: dict, image_url: str = "",
                       judul: str = "", tipe_aff: str = "default"):
        """Helper: posting ke Facebook + Threads secara bersamaan.
        Otomatis menambahkan link affiliate Shopee ke caption.
        Urutan fallback Facebook: video lokal → foto via URL → teks.
        Threads: foto via URL (Pollinations) → teks.
        """
        # Tambahkan link affiliate Shopee ke caption
        caption = aff.tambah_affiliate_ke_caption(caption, tipe_aff)

        # ── Facebook ──────────────────────────────────────────────────────
        try:
            if image_url:
                video_path = vg.buat_video(judul or "Info Bola", caption, image_url)
                if video_path:
                    try:
                        res = fb.upload_video_file(caption, video_path, judul)
                        log.info(f"Facebook: diposting sebagai VIDEO — ID {res.get('id')}")
                        hasil["platform"].append({"facebook": res, "tipe": "video"})
                    except Exception as ev:
                        log.warning(f"Upload video FB gagal ({ev}), fallback ke foto")
                        res = fb.post_dengan_gambar(caption, image_url)
                        log.info(f"Facebook: diposting dengan gambar — ID {res.get('id')}")
                        hasil["platform"].append({"facebook": res, "tipe": "foto"})
                    finally:
                        try:
                            os.unlink(video_path)
                        except Exception:
                            pass
                else:
                    res = fb.post_dengan_gambar(caption, image_url)
                    log.info(f"Facebook: diposting dengan gambar — ID {res.get('id')}")
                    hasil["platform"].append({"facebook": res, "tipe": "foto"})
            else:
                res = fb.post_teks(caption)
                log.info(f"Facebook: diposting teks — ID {res.get('id')}")
                hasil["platform"].append({"facebook": res, "tipe": "teks"})
        except Exception as e:
            log.error(f"Facebook gagal: {e}")
            try:
                res = fb.post_teks(caption)
                hasil["platform"].append({"facebook": res, "tipe": "teks_fallback"})
                log.info("Facebook: fallback ke teks berhasil")
            except Exception as e2:
                hasil["platform"].append({"facebook_error": str(e2)})

        # ── Threads ───────────────────────────────────────────────────────
        if THREADS_USER_ID and THREADS_ACCESS_TOKEN:
            try:
                if image_url:
                    res_t = threads.post_dengan_gambar(caption, image_url)
                else:
                    res_t = threads.post_teks(caption)
                log.info(f"Threads: diposting — ID {res_t.get('id')}")
                hasil["platform"].append({"threads": res_t})
            except Exception as et:
                log.warning(f"Threads gagal: {et}")
                hasil["platform"].append({"threads_error": str(et)})

    def _simpan_konten(self, nama: str, konten: dict):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(OUTPUT_DIR, f"{nama}_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(konten, f, ensure_ascii=False, indent=2)
        log.info(f"Konten disimpan: {path}")
