"""
Agent utama: orkestrasi pengambilan data, pembuatan konten, dan publishing.
"""
import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from config import LIGA_FAVORIT, OUTPUT_DIR
import football_api as api
import content_generator as gen
import facebook_publisher as fb
import youtube_publisher as yt

log = logging.getLogger(__name__)


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
        """Ambil jadwal hari ini → buat konten → posting ke platform."""
        log.info("Mengambil data pertandingan hari ini...")
        liga_ids = [
            api.LIGA_ID[l] for l in LIGA_FAVORIT if l in api.LIGA_ID
        ]
        fixtures = api.get_fixtures_hari_ini(liga_ids)

        if not fixtures:
            log.warning("Tidak ada pertandingan hari ini.")
            return {"status": "tidak_ada_pertandingan"}

        fixture_teks = [api.format_fixture_untuk_prompt(f) for f in fixtures]
        log.info(f"Ditemukan {len(fixtures)} pertandingan. Membuat konten...")

        konten = gen.buat_preview_pertandingan(fixture_teks)
        hasil = {"konten": konten, "platform": []}

        if simpan_lokal:
            self._simpan_konten("preview", konten)

        if ke_facebook and konten.get("facebook_caption"):
            try:
                res = fb.post_teks(konten["facebook_caption"])
                hasil["platform"].append({"facebook": res})
                log.info(f"Facebook: berhasil diposting — ID {res.get('id')}")
            except Exception as e:
                log.error(f"Facebook gagal: {e}")
                hasil["platform"].append({"facebook_error": str(e)})

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
        liga_ids = [
            api.LIGA_ID[l] for l in LIGA_FAVORIT if l in api.LIGA_ID
        ]
        fixtures = api.get_fixtures_kemarin(liga_ids)

        selesai = [f for f in fixtures if
                   f.get("fixture", {}).get("status", {}).get("short") == "FT"]

        if not selesai:
            log.warning("Tidak ada pertandingan selesai kemarin.")
            return {"status": "tidak_ada_hasil"}

        fixture_teks = [api.format_fixture_untuk_prompt(f) for f in selesai]
        konten = gen.buat_rekap_hasil(fixture_teks)
        hasil = {"konten": konten, "platform": []}

        if simpan_lokal:
            self._simpan_konten("rekap", konten)

        if ke_facebook and konten.get("facebook_caption"):
            try:
                res = fb.post_teks(konten["facebook_caption"])
                hasil["platform"].append({"facebook": res})
                log.info(f"Facebook: rekap diposting — ID {res.get('id')}")
            except Exception as e:
                log.error(f"Facebook gagal: {e}")
                hasil["platform"].append({"facebook_error": str(e)})

        return hasil

    def posting_klasemen(
        self,
        nama_liga: str,
        ke_facebook: bool = True,
        simpan_lokal: bool = True,
    ) -> dict:
        """Ambil klasemen → buat konten → posting."""
        liga_id = api.LIGA_ID.get(nama_liga)
        if not liga_id:
            raise ValueError(f"Liga tidak dikenal: {nama_liga}")

        log.info(f"Mengambil klasemen {nama_liga}...")
        standings = api.get_standings(liga_id)

        if not standings:
            return {"status": "gagal_ambil_klasemen"}

        # Format teks klasemen
        baris = []
        for i, tim in enumerate(standings[:5], 1):
            t = tim.get("team", {})
            s = tim.get("points", 0)
            baris.append(f"{i}. {t.get('name')} — {s} poin")
        # Tambah zona degradasi
        baris.append("...")
        for tim in standings[-3:]:
            t = tim.get("team", {})
            r = tim.get("rank", "?")
            s = tim.get("points", 0)
            baris.append(f"{r}. {t.get('name')} — {s} poin ⚠️")

        standings_teks = "\n".join(baris)
        konten = gen.buat_analisis_klasemen(nama_liga, standings_teks)
        hasil = {"konten": konten, "platform": []}

        if simpan_lokal:
            self._simpan_konten(f"klasemen_{nama_liga.lower().replace(' ', '_')}", konten)

        if ke_facebook and konten.get("facebook_caption"):
            try:
                res = fb.post_teks(konten["facebook_caption"])
                hasil["platform"].append({"facebook": res})
            except Exception as e:
                hasil["platform"].append({"facebook_error": str(e)})

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

    def posting_ke_facebook_dengan_gambar(
        self, topik: str, url_gambar: str
    ) -> dict:
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

    def _simpan_konten(self, nama: str, konten: dict):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(OUTPUT_DIR, f"{nama}_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(konten, f, ensure_ascii=False, indent=2)
        log.info(f"Konten disimpan: {path}")
