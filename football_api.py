"""
Pengambil data pertandingan dari TheSportsDB (gratis, tanpa API key).
https://www.thesportsdb.com/api.php
"""
import requests
from datetime import datetime, timedelta

BASE = "https://www.thesportsdb.com/api/v1/json/3"

# ID liga di TheSportsDB
LIGA_ID = {
    "Premier League"  : 4328,
    "La Liga"         : 4335,
    "Serie A"         : 4332,
    "Bundesliga"      : 4331,
    "Ligue 1"         : 4334,
    "Liga 1"          : 4399,
    "Champions League": 4480,
}

# Kode liga untuk endpoint tabel
LIGA_SEASON = {
    "Premier League"  : ("4328", "2024-2025"),
    "La Liga"         : ("4335", "2024-2025"),
    "Serie A"         : ("4332", "2024-2025"),
    "Bundesliga"      : ("4331", "2024-2025"),
    "Ligue 1"         : ("4334", "2024-2025"),
    "Liga 1"          : ("4399", "2024"),
    "Champions League": ("4480", "2024-2025"),
}

from config import LIGA_FAVORIT


def _get(endpoint: str, params: dict = {}) -> dict:
    resp = requests.get(f"{BASE}/{endpoint}", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _tanggal(offset_hari: int = 0) -> str:
    return (datetime.now() + timedelta(days=offset_hari)).strftime("%Y-%m-%d")


def get_fixtures_hari_ini(liga_ids=None) -> list[dict]:
    """Ambil pertandingan hari ini dari semua liga favorit."""
    tanggal = _tanggal(0)
    data = _get("eventsday.php", {"d": tanggal, "s": "Soccer"})
    events = data.get("events") or []

    liga_names = set(LIGA_FAVORIT)
    hasil = [
        e for e in events
        if e.get("strLeague") in liga_names
    ]
    return hasil


def get_fixtures_kemarin(liga_ids=None) -> list[dict]:
    """Ambil pertandingan kemarin."""
    tanggal = _tanggal(-1)
    data = _get("eventsday.php", {"d": tanggal, "s": "Soccer"})
    events = data.get("events") or []

    liga_names = set(LIGA_FAVORIT)
    hasil = [
        e for e in events
        if e.get("strLeague") in liga_names
    ]
    return hasil


def get_standings(nama_liga: str) -> list[dict]:
    """Ambil klasemen liga."""
    if nama_liga not in LIGA_SEASON:
        return []
    liga_id, season = LIGA_SEASON[nama_liga]
    data = _get("lookuptable.php", {"l": liga_id, "s": season})
    return data.get("table") or []


def get_top_scorers(nama_liga: str) -> list[dict]:
    """TheSportsDB tidak support top scorer di free tier — return kosong."""
    return []


def format_fixture_untuk_prompt(fixture: dict) -> str:
    """Ubah data TheSportsDB ke teks ringkas untuk prompt Claude."""
    home    = fixture.get("strHomeTeam", "")
    away    = fixture.get("strAwayTeam", "")
    liga    = fixture.get("strLeague", "")
    tanggal = fixture.get("dateEvent", "")
    waktu   = fixture.get("strTime", "")[:5] if fixture.get("strTime") else "TBD"
    skor_h  = fixture.get("intHomeScore")
    skor_a  = fixture.get("intAwayScore")
    status  = fixture.get("strStatus", "")

    if skor_h is not None and skor_a is not None and status in ("Match Finished", "FT", "AOT", "AP"):
        return f"[SELESAI] {liga} | {home} {skor_h}-{skor_a} {away}"
    else:
        return f"[AKAN MAIN] {liga} | {home} vs {away} @ {tanggal} {waktu} WIB"
