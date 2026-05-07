"""
Modul pengambil data pertandingan dari API Football.
"""
import requests
from datetime import datetime, timedelta
from config import FOOTBALL_API_KEY, FOOTBALL_API_HOST


BASE_URL = f"https://{FOOTBALL_API_HOST}"
HEADERS = {
    "x-rapidapi-host": FOOTBALL_API_HOST,
    "x-rapidapi-key": FOOTBALL_API_KEY,
}

LIGA_ID = {
    "Premier League": 39,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
    "Liga 1": 466,
    "Champions League": 2,
    "Europa League": 3,
}


def get_fixtures_hari_ini(liga_ids: list[int] | None = None) -> list[dict]:
    """Ambil semua pertandingan hari ini."""
    tanggal = datetime.now().strftime("%Y-%m-%d")
    hasil = []
    ids = liga_ids or list(LIGA_ID.values())
    for lid in ids:
        resp = requests.get(
            f"{BASE_URL}/fixtures",
            headers=HEADERS,
            params={"league": lid, "date": tanggal, "season": datetime.now().year},
            timeout=10,
        )
        if resp.ok:
            hasil.extend(resp.json().get("response", []))
    return hasil


def get_fixtures_kemarin(liga_ids: list[int] | None = None) -> list[dict]:
    """Ambil pertandingan kemarin (untuk rekap hasil)."""
    tanggal = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    hasil = []
    ids = liga_ids or list(LIGA_ID.values())
    for lid in ids:
        resp = requests.get(
            f"{BASE_URL}/fixtures",
            headers=HEADERS,
            params={"league": lid, "date": tanggal, "season": datetime.now().year},
            timeout=10,
        )
        if resp.ok:
            hasil.extend(resp.json().get("response", []))
    return hasil


def get_standings(liga_id: int) -> list[dict]:
    """Ambil klasemen liga."""
    resp = requests.get(
        f"{BASE_URL}/standings",
        headers=HEADERS,
        params={"league": liga_id, "season": datetime.now().year},
        timeout=10,
    )
    if resp.ok:
        data = resp.json().get("response", [])
        if data:
            return data[0]["league"]["standings"][0]
    return []


def get_top_scorers(liga_id: int) -> list[dict]:
    """Ambil top skor liga."""
    resp = requests.get(
        f"{BASE_URL}/players/topscorers",
        headers=HEADERS,
        params={"league": liga_id, "season": datetime.now().year},
        timeout=10,
    )
    if resp.ok:
        return resp.json().get("response", [])[:5]
    return []


def format_fixture_untuk_prompt(fixture: dict) -> str:
    """Ubah data fixture API menjadi teks ringkas untuk prompt Claude."""
    f = fixture.get("fixture", {})
    t = fixture.get("teams", {})
    g = fixture.get("goals", {})
    l = fixture.get("league", {})
    status = f.get("status", {}).get("long", "")
    waktu = f.get("date", "")[:16].replace("T", " ")
    home = t.get("home", {}).get("name", "")
    away = t.get("away", {}).get("name", "")
    skor_home = g.get("home", "-")
    skor_away = g.get("away", "-")
    liga = l.get("name", "")
    round_ = l.get("round", "")

    if status in ("Match Finished", "Full Time"):
        return f"[SELESAI] {liga} | {round_} | {home} {skor_home}-{skor_away} {away}"
    else:
        return f"[AKAN MAIN] {liga} | {round_} | {home} vs {away} @ {waktu} WIB"
