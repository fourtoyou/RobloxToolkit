"""หาเซิร์ฟที่คนน้อยที่สุด + เฝ้าจำนวนคนในเซิร์ฟที่เล่นอยู่

ความจริงที่ต้องรู้ก่อน:
- Roblox ไม่มีทางให้ "ล็อกเซิร์ฟสาธารณะไม่ให้ใครเข้า" — การรับคนเข้าเกิดที่เซิร์ฟเวอร์ของ Roblox ไม่ใช่ที่เครื่องเรา
  ถ้าเกมเปิดให้สร้าง Private Server ได้ (ดู private_allowed) อันนั้นคือคำตอบเดียวที่อยู่คนเดียวได้จริง
- ถ้าเกมไม่เปิด สิ่งที่ทำได้จริงคือ สุ่มดูเซิร์ฟสาธารณะแล้วเลือกอันที่คนน้อยสุด และเฝ้าไว้
- API เซิร์ฟของ Roblox โดน rate limit เร็วมาก (429 ตั้งแต่หน้าที่ 4) → ดูได้ทีละ ~300 เซิร์ฟ และต้องเว้นช่วง
  เกมใหญ่ (คนเล่นเป็นล้าน) มีเซิร์ฟเป็นแสน → หา "เซิร์ฟที่เราอยู่" ในลิสต์ไม่เจอ เป็นเรื่องปกติ ไม่ใช่บั๊ก
"""
import threading
import time

from . import config
from .win import idle_seconds

API = "https://games.roblox.com/v1/games"
PAGES = 1               # sortOrder=Asc ให้ Roblox เรียงคนน้อยสุดมาให้เอง → หน้าเดียว (100 เซิร์ฟ) ก็ได้ตัวที่เงียบสุดจริง
_snap = {}              # place -> {"at": ts, "data": [...]}
_lock = threading.Lock()
_cooldown_until = 0     # โดน 429 แล้วหยุดยิงชั่วคราว
_fails = 0              # โดน 429 ติดกันกี่รอบ (ยิ่งเยอะยิ่งพักนาน)
_priv_cache = {}


def limited():
    """ตอนนี้ติด rate limit อยู่ไหม (เหลืออีกกี่วินาที)"""
    return max(0, int(_cooldown_until - time.time()))


def scan(place, pages=PAGES, timeout=8):
    """สุ่มดูเซิร์ฟสาธารณะ (หน้าละ 100) — คืน list ว่างถ้าโดน rate limit หรือ API ไม่ตอบ"""
    global _cooldown_until, _fails
    if time.time() < _cooldown_until:
        return []
    import requests
    out, cursor = [], ""
    s = requests.Session()
    for i in range(pages):
        url = f"{API}/{place}/servers/Public?limit=100&sortOrder=Asc&excludeFullGames=false"
        if cursor:
            url += "&cursor=" + cursor
        try:
            r = s.get(url, timeout=timeout)
        except Exception as e:
            config.dbg(f"servers.scan {place}: {e}")
            break
        if r.status_code == 429:
            if out:                     # ได้ข้อมูลมาบ้างแล้ว ถือว่าพอใช้ได้ พักสั้นๆ
                _cooldown_until = max(_cooldown_until, time.time() + 120)
            else:                       # ไม่ได้อะไรเลย → พักนานขึ้นเรื่อยๆ 2,4,8,16,30 นาที
                _fails += 1
                wait = min(120 * 2 ** (_fails - 1), 1800)
                _cooldown_until = time.time() + wait
                config.dbg(f"servers.scan {place}: โดน rate limit (ครั้งที่ {_fails}) — พัก {wait // 60} นาที")
            break
        if r.status_code != 200:
            config.dbg(f"servers.scan {place}: HTTP {r.status_code}")
            break
        try:
            d = r.json()
        except Exception:
            break
        out += d.get("data", [])
        _fails = 0
        cursor = d.get("nextPageCursor")
        if not cursor:
            break
    return out


def snapshot(place, max_age=50):
    """scan แบบมี cache — กันยิง API ถี่เกินจนโดน 429"""
    with _lock:
        c = _snap.get(place)
        if c and time.time() - c["at"] < max_age:
            return c["data"]
    data = scan(place)
    if data:
        with _lock:
            _snap[place] = {"at": time.time(), "data": data}
        return data
    with _lock:
        c = _snap.get(place)
        return c["data"] if c else []


def find(servers, job):
    return next((s for s in servers if s.get("id") == job), None)


def quietest(servers, max_ping=150, exclude=None, need_slots=2):
    """เซิร์ฟที่คนน้อยสุดและยังมีที่ว่าง (กรอง ping ก่อน ถ้าไม่มีค่อยเอาทั้งหมด)

    บางเกมใช้เซิร์ฟเล็กมาก (เช่น 7 คน/เซิร์ฟ) จนไม่มีเซิร์ฟไหนว่าง 2 ที่เลย → ลดเหลือ 1 ที่ว่าง
    """
    for slots in (need_slots, 1):
        cand = [s for s in servers if s.get("id") != exclude and (s.get("maxPlayers", 0) - s.get("playing", 0)) >= slots]
        if cand:
            good = [s for s in cand if (s.get("ping") or 9999) <= max_ping]
            return min(good or cand, key=lambda s: (s.get("playing", 0), s.get("ping") or 9999))
    return None


def private_allowed(place):
    """เกมนี้เปิดให้ผู้เล่นสร้าง Private Server เองไหม → (ได้ไหม, ชื่อเกม) · None ถ้าเช็คไม่ได้"""
    c = _priv_cache.get(place)
    if c and time.time() - c[0] < 3600:
        return c[1]
    try:
        import requests
        uid = requests.get(f"https://apis.roblox.com/universes/v1/places/{place}/universe", timeout=6).json()["universeId"]
        g = requests.get(f"{API}?universeIds={uid}", timeout=6).json()["data"][0]
        res = (bool(g.get("createVipServersAllowed")), g.get("name"))
    except Exception as e:
        config.dbg(f"private_allowed {place}: {e}")
        res = None
    _priv_cache[place] = (time.time(), res)
    return res


class ServerWatch(threading.Thread):
    """เฝ้าเซิร์ฟที่เล่นอยู่ · ย้ายไปเซิร์ฟที่คนน้อยสุดให้อัตโนมัติตอน AFK (ถ้าเปิดไว้)

    ย้ายอัตโนมัติเฉพาะเมื่อ: Anti-AFK ทำงาน + ไม่ได้แตะเครื่องมา 60 วิ + รู้จำนวนคนในเซิร์ฟเราจริงๆ
    (ไม่งั้นมันจะเด้งเกมตอนกำลังเล่นอยู่)
    """
    SCAN_EVERY = 60
    SCAN_EVERY_IDLE = 600     # เกมที่หาเซิร์ฟเราไม่เจอและไม่มีเซิร์ฟว่าง → สแกนห่างๆ พอ
    HOP_COOLDOWN = 300

    def __init__(self, engine, log, on_event, cfg):
        super().__init__(daemon=True)
        self.eng, self.log, self.emit, self.cfg = engine, log, on_event, cfg
        self.players = self.maxp = self.quiet = self.ping = None
        self.seen = False          # เจอเซิร์ฟของเราในลิสต์ไหม (เกมใหญ่มักไม่เจอ)
        self.sample = 0            # ดูไปกี่เซิร์ฟรอบล่าสุด
        self.last_scan = self.last_hop = 0
        self.hops = 0
        self.useless = 0          # สแกนแล้วไม่ได้อะไรเลยกี่รอบติด
        self.place = None

    def reset(self):
        self.players = self.maxp = self.quiet = self.ping = None
        self.seen, self.sample = False, 0

    def interval(self):
        """ยิ่งสแกนแล้วไม่ได้อะไร ยิ่งเว้นห่าง — กันโดน Roblox rate limit รัวๆ"""
        return self.SCAN_EVERY_IDLE if self.useless >= 3 else self.SCAN_EVERY

    def run(self):
        while True:
            try:
                self.tick()
            except Exception as e:
                config.dbg(f"serverwatch: {e}")
            time.sleep(5)

    def tick(self):
        cur = self.eng.watcher.current
        place, job = cur.get("place"), cur.get("job")
        if not (cur.get("in_game") and place and job and self.cfg.get("watch_players")):
            if self.players is not None or self.seen:
                self.reset()
            return
        if place != self.place:           # เปลี่ยนเกม → เริ่มนับใหม่
            self.place, self.useless = place, 0
        if time.time() - self.last_scan < self.interval() or self.eng.rejoining or limited():
            return
        self.last_scan = time.time()
        lst = snapshot(place, max_age=self.SCAN_EVERY - 10)
        if not lst:
            return
        self.sample = len(lst)
        best = quietest(lst, self.cfg.get("hop_max_ping", 150), exclude=job)
        self.quiet = best.get("playing") if best else None
        me = find(lst, job)
        self.seen = bool(me)
        self.useless = 0 if (me or self.quiet is not None) else self.useless + 1
        if self.useless == 3:
            config.dbg(f"serverwatch: {place} หาเซิร์ฟเราไม่เจอและไม่มีเซิร์ฟว่าง → ลดการสแกนเหลือทุก {self.SCAN_EVERY_IDLE // 60} นาที")
        if not me:
            self.players = self.ping = None
            self.maxp = (best or lst[0]).get("maxPlayers")
            return
        prev = self.players
        self.players, self.maxp, self.ping = me.get("playing"), me.get("maxPlayers"), me.get("ping")
        if prev is not None and self.players != prev:
            self.emit("players", {"players": self.players, "max": self.maxp, "was": prev, "quiet": self.quiet})
        self.maybe_hop(place, job, best)

    def maybe_hop(self, place, job, best):
        if not (self.cfg.get("auto_hop") and best and self.eng.running and not self.eng.rejoining):
            return
        if self.players is None or self.players <= self.cfg.get("hop_over", 12):
            return
        if best.get("playing", 99) >= self.players - 2:      # ย้ายแล้วไม่ได้ดีขึ้นจริง อย่าย้าย
            return
        if time.time() - self.last_hop < self.HOP_COOLDOWN or idle_seconds() < 60:
            return
        self.last_hop = time.time()
        self.hops += 1
        self.log(f"🔀 เซิร์ฟนี้ {self.players}/{self.maxp} คนแล้ว → ย้ายไปเซิร์ฟที่มี {best['playing']} คน")
        self.emit("hop_start", {"from": self.players, "to": best.get("playing"), "ping": best.get("ping")})
        self.go(place, exclude=job)

    def go(self, place, exclude=None):
        """ย้ายไปเซิร์ฟที่คนน้อยสุดตอนนี้ — ใช้ทั้งแบบอัตโนมัติและกดปุ่มเอง"""
        if self.eng.rejoining:
            return self.log("กำลังต่อเกมอยู่ รอสักครู่")
        self.eng.rejoining = True

        def pick():
            lst = snapshot(place, max_age=15)
            if not lst:
                self.log(f"ดูรายชื่อเซิร์ฟไม่ได้ตอนนี้ (Roblox จำกัดการเรียก — รออีก {limited()} วิ)" if limited() else "ดูรายชื่อเซิร์ฟไม่ได้")
                return None
            s = quietest(lst, self.cfg.get("hop_max_ping", 150), exclude=exclude)
            if s:
                self.log(f"เลือกเซิร์ฟ {s['playing']}/{s['maxPlayers']} คน · ping {s.get('ping')} ms (จาก {len(lst)} เซิร์ฟที่ดูได้)")
            return s.get("id") if s else None

        threading.Thread(target=self.eng.hop, args=(place, pick), daemon=True).start()
