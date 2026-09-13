"""Game Launcher: เกมโปรด (จากสถิติ + เพิ่มเอง), เข้าเกม / เซิร์ฟเดิม / เซิร์ฟที่ ping ต่ำสุด, จำนวนคนเล่นสด"""
import json
import os
import re
import threading
import time

from . import config

FAV_PATH = os.path.join(config.DATA_DIR, "favorites.json")
_info_cache = {}


def parse_place(s):
    m = re.search(r"(\d{6,})", s or "")
    return m.group(1) if m else None


def load_favs():
    try:
        with open(FAV_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_favs(favs):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(FAV_PATH, "w", encoding="utf-8") as f:
        json.dump(favs, f, ensure_ascii=False, indent=2)


def add_fav(place, name=None):
    favs = load_favs()
    if any(f["place"] == place for f in favs):
        return favs
    favs.append({"place": place, "name": name or f"place {place}", "added": time.time()})
    save_favs(favs)
    return favs


def remove_fav(place):
    favs = [f for f in load_favs() if f["place"] != place]
    save_favs(favs)
    return favs


def game_info(place, max_age=60):
    """ชื่อ/คนเล่นตอนนี้/ไอคอน (cache 60 วิ)"""
    c = _info_cache.get(place)
    if c and time.time() - c["at"] < max_age:
        return c
    try:
        import requests
        uid = requests.get(f"https://apis.roblox.com/universes/v1/places/{place}/universe", timeout=6).json().get("universeId")
        g = requests.get(f"https://games.roblox.com/v1/games?universeIds={uid}", timeout=6).json()["data"][0]
        info = {"at": time.time(), "name": g.get("name"), "playing": g.get("playing", 0), "visits": g.get("visits", 0),
                "max": g.get("maxPlayers", 0), "universe": uid, "creator": (g.get("creator") or {}).get("name")}
    except Exception:
        info = {"at": time.time(), "name": None, "playing": None, "visits": None, "max": None, "universe": None, "creator": None}
    _info_cache[place] = info
    return info


def best_server(place):
    """เซิร์ฟสาธารณะที่ ping ต่ำสุด (จาก API ของ Roblox — ค่าประมาณ) และมีที่ว่าง"""
    try:
        import requests
        d = requests.get(f"https://games.roblox.com/v1/games/{place}/servers/Public?sortOrder=Asc&excludeFullGames=true&limit=50", timeout=8).json()
        servers = [s for s in d.get("data", []) if s.get("playing", 0) < s.get("maxPlayers", 1)]
        if not servers:
            return None
        return min(servers, key=lambda s: (s.get("ping") or 9999, -s.get("playing", 0)))
    except Exception:
        return None


def launch(place, job=None):
    url = f"roblox://experiences/start?placeId={place}" + (f"&gameInstanceId={job}" if job else "")
    os.startfile(url)
    return url


def launch_best(place, log=lambda s: None):
    def _go():
        s = best_server(place)
        if s:
            log(f"เข้าเซิร์ฟ ping {s.get('ping')} ms ({s.get('playing')}/{s.get('maxPlayers')} คน)")
            launch(place, s["id"])
        else:
            log("หาเซิร์ฟว่างไม่ได้ เข้าแบบสุ่มแทน")
            launch(place)
    threading.Thread(target=_go, daemon=True).start()
