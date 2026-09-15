"""อ่าน log ของ Roblox ทั้งหมด → เซสชันการเล่น (เข้าเมื่อไหร่ ออกเมื่อไหร่ เกมอะไร หลุดเพราะอะไร)
cache ผลต่อไฟล์ไว้ใน cache.json (ไฟล์เดิมขนาดเดิม = ไม่อ่านซ้ำ)"""
import glob
import json
import os
import re
import threading
import time
from datetime import datetime, timezone

from . import config
from .antiafk import RE_DC, RE_DISC, RE_JOIN, reason_text

CACHE_VER = 2      # 2 = มี dc ต่อเซสชัน — เปลี่ยนเลขแล้วไฟล์เก่าจะถูกอ่านใหม่รอบเดียว

RE_TS = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.(\d{3})Z")
_names_lock = threading.Lock()


def _ts(line):
    m = RE_TS.match(line)
    if not m:
        return None
    dt = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.timestamp() + int(m.group(2)) / 1000


def parse_file(path):
    """คืน list ของ session dict สำหรับ log 1 ไฟล์"""
    sessions, cur, last_ts = [], None, None
    try:
        with open(path, "rb") as f:
            for raw in f:
                if b"Joining game" not in raw and b"Sending disconnect" not in raw and b"shutDown" not in raw and b"DatacenterId=" not in raw:
                    # เก็บเวลาบรรทัดล่าสุดแบบประหยัด: เช็คแค่บรรทัดที่ขึ้นต้นด้วยปี
                    if raw[:2] == b"20":
                        last_ts = raw[:24]
                    continue
                line = raw.decode("utf-8", "ignore")
                t = _ts(line)
                if t is None:
                    continue
                last_ts = raw[:24]
                m = RE_JOIN.search(line)
                if m:
                    if cur and cur["end"] is None:  # teleport/reconnect โดยไม่มี disconnect line
                        cur["end"], cur["reason"] = t, 0
                    cur = {"start": t, "end": None, "place": m.group(2), "job": m.group(1), "reason": None}
                    sessions.append(cur)
                    continue
                m = RE_DC.search(line)
                if m:
                    if cur and cur["end"] is None:
                        cur["dc"] = int(m.group(1))
                    continue
                m = RE_DISC.search(line)
                if m and cur and cur["end"] is None:
                    cur["end"], cur["reason"] = t, int(m.group(1))
    except OSError:
        return []
    if cur and cur["end"] is None:
        end = _ts(last_ts.decode("ascii", "ignore")) if last_ts else None
        cur["end"], cur["reason"] = (end or cur["start"]), -1  # -1 = ปิดเกม/ค้าง โดยไม่มี disconnect
    return [s for s in sessions if s["end"] - s["start"] >= 5]


ARCHIVE_PATH = os.path.join(config.DATA_DIR, "sessions.json")
ARCHIVE_KEEP_DAYS = 730


def _key(s):
    return f"{int(s['start'])}|{s['place']}|{s.get('job') or ''}"


def load_archive():
    """คลังเซสชันถาวรของเราเอง — Roblox ลบ log ทิ้งเรื่อยๆ ถ้าไม่เก็บเองสถิติจะหายหมด"""
    try:
        with open(ARCHIVE_PATH, encoding="utf-8") as f:
            return {_key(s): s for s in json.load(f)}
    except Exception:
        return {}


def save_archive(arch):
    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        tmp = ARCHIVE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sorted(arch.values(), key=lambda s: s["start"]), f, ensure_ascii=False)
        os.replace(tmp, ARCHIVE_PATH)
    except Exception:
        pass


class History:
    def __init__(self):
        self.cache = config.load_cache()
        if self.cache.get("hist_ver") != CACHE_VER:
            self.cache["files"] = {}
            self.cache["hist_ver"] = CACHE_VER
        self.cache.setdefault("files", {})
        self.cache.setdefault("names", {})
        self.archive = load_archive()
        self.sessions = sorted(self.archive.values(), key=lambda s: s["start"])
        self.lock = threading.Lock()
        self._scan_lock = threading.Lock()
        self.loading = False

    # ---------- scan ----------
    def scan(self, progress=lambda done, total: None):
        with self._scan_lock:          # ถ้ามีคนสแกนอยู่ รอให้เสร็จแล้วใช้ผลนั้น
            return self._scan(progress)

    def _scan(self, progress):
        self.loading = True
        files = []
        for d in config.LOG_DIRS:
            files += glob.glob(os.path.join(d, "*_Player_*.log"))
        files.sort()
        out, dirty = [], False
        for i, p in enumerate(files):
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            key = os.path.basename(p)
            ent = self.cache["files"].get(key)
            recent = time.time() - os.path.getmtime(p) < 3600  # ไฟล์ที่ยังเขียนอยู่ อ่านใหม่เสมอ
            if ent and ent["size"] == size and not recent:
                out += ent["sessions"]
            else:
                s = parse_file(p)
                self.cache["files"][key] = {"size": size, "sessions": s}
                out += s
                dirty = True
            progress(i + 1, len(files))
        # รวมเข้าคลังถาวร (เซสชันเดิมจะถูกอัปเดตทับด้วยข้อมูลล่าสุด เช่นตอนที่ยังเล่นค้างอยู่)
        for sess in out:
            self.archive[_key(sess)] = sess
        cutoff = time.time() - ARCHIVE_KEEP_DAYS * 86400
        self.archive = {k: v for k, v in self.archive.items() if v["end"] >= cutoff}
        save_archive(self.archive)
        with self.lock:
            self.sessions = sorted(self.archive.values(), key=lambda s: s["start"])
        if dirty:
            config.save_cache(self.cache)
        self.loading = False
        return self.sessions

    # ---------- ชื่อเกม ----------
    def name(self, place):
        return self.cache["names"].get(str(place), f"place {place}")

    def resolve_names(self, places, done=lambda: None):
        """ถามชื่อเกมจาก Roblox API (public, ไม่ต้อง login) ทีละ place แล้ว cache"""
        import requests
        missing = [p for p in dict.fromkeys(map(str, places)) if p not in self.cache["names"]]
        changed = False
        for i, p in enumerate(missing):
            if i and i % 4 == 0:
                done()  # ทยอยโชว์ชื่อระหว่างรอ
            try:
                r = requests.get(f"https://apis.roblox.com/universes/v1/places/{p}/universe", timeout=6)
                uid = r.json().get("universeId")
                if uid:
                    r2 = requests.get(f"https://games.roblox.com/v1/games?universeIds={uid}", timeout=6)
                    data = r2.json().get("data") or []
                    if data:
                        with _names_lock:
                            self.cache["names"][p] = data[0]["name"]
                        changed = True
            except Exception:
                pass
        if changed:
            config.save_cache(self.cache)
        done()

    # ---------- สรุป ----------
    def summary(self, days=None):
        now = time.time()
        since = now - days * 86400 if days else 0
        per = {}
        total = 0
        disconnects = []
        with self.lock:
            for s in self.sessions:
                if s["end"] < since:
                    continue
                dur = s["end"] - max(s["start"], since)
                total += dur
                e = per.setdefault(s["place"], {"place": s["place"], "seconds": 0, "sessions": 0, "last": 0})
                e["seconds"] += dur
                e["sessions"] += 1
                e["last"] = max(e["last"], s["end"])
                if s["reason"] not in (None, 0, -1, 285):
                    disconnects.append(s)
        top = sorted(per.values(), key=lambda e: -e["seconds"])
        return {"total": total, "games": top, "disconnects": sorted(disconnects, key=lambda s: -s["end"]),
                "sessions": sum(e["sessions"] for e in top)}

    def daily(self, days=14):
        """วินาทีที่เล่นต่อวัน ย้อนหลัง N วัน (เวลาท้องถิ่น)"""
        buckets = {}
        today = datetime.now().date()
        with self.lock:
            for s in self.sessions:
                t = s["start"]
                while t < s["end"]:
                    d = datetime.fromtimestamp(t).date()
                    day_end = datetime.combine(d, datetime.max.time()).timestamp()
                    seg = min(s["end"], day_end) - t
                    buckets[d] = buckets.get(d, 0) + seg
                    t = day_end + 0.001
        out = []
        for i in range(days - 1, -1, -1):
            d = datetime.fromtimestamp(time.time() - i * 86400).date()
            out.append((d, buckets.get(d, 0)))
        return out


def fmt_dur(sec):
    sec = int(sec)
    h, m = sec // 3600, (sec % 3600) // 60
    return f"{h} ชม. {m} นาที" if h else f"{m} นาที"


def fmt_reason(code):
    if code == -1:
        return "ปิดเกม"
    if code == 0:
        return "วาร์ป/เปลี่ยนเซิร์ฟ"
    return reason_text(code)
