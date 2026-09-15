"""👁 เฝ้าจอ — ถ่ายหน้าต่าง Roblox เป็นระยะ → OCR → เจอคำที่ตั้งไว้แล้วแจ้ง
ทำไมต้องมี: เกมแนว Steal An Egg ไข่หายากโผล่เป็นครั้งคราว ผู้ใช้ AFK อยู่ในเซิร์ฟคนน้อยที่หายาก ไม่อยากออกไปหาใหม่ อยากรู้ทันทีตอนมันโผล่
วิธี: PrintWindow (ถ่ายได้แม้ถูกบัง/ซ่อน alpha 0 — แต่ไม่ได้ถ้าย่อ) → ขยาย 2 เท่า (OCR ขนาดจริงอ่านแทบไม่ได้) → Windows OCR
ไม่แตะโปรเซสเกมเลย เป็นแค่การถ่ายจอ"""
import glob
import os
import re
import threading
import time
from collections import deque

from . import config
from .win import roblox_windows, u

DIR = os.path.join(config.DATA_DIR, "watch")
RE_COUNTDOWN = re.compile(r"(?i)\bin\s*(\d{1,3})\s*s\b")      # นาฬิการีเซ็ตของ Steal An Egg: "in 56s"


def local_norm(g, tile=96):
    """ยืดคอนทราสต์ทีละกล่องเล็ก — ตัวหนังสือดำบนแผงแชทมืด (ต่างกันแค่ ~10 ระดับ) จะโผล่ขึ้นมาให้ OCR อ่านได้"""
    from PIL import ImageOps
    out = g.copy()
    for y in range(0, g.height, tile):
        for x in range(0, g.width, tile):
            box = (x, y, min(x + tile, g.width), min(y + tile, g.height))
            t = g.crop(box)
            lo, hi = t.getextrema()
            if hi - lo < 6:
                continue
            out.paste(ImageOps.autocontrast(t, cutoff=0), box)
    return out


def fuzzy_in(word, line):
    """คำอยู่ในบรรทัดไหม — ตรงตัว หรือ OCR อ่านเพี้ยน 1-2 ตัวอักษร (Seeret, Cerberuk) สำหรับคำเดี่ยวยาว ≥5"""
    wl, ll = word.lower(), line.lower()
    if wl in ll:
        return True
    if " " in wl or len(wl) < 5:
        return False
    # ยอมให้เพี้ยนได้ 1 ตัวอักษร (แทน/เพิ่ม/หาย) — "Seeret", "Divlne", "Cerberuk" นับ · "secure"/"External"/"secretary" ไม่นับ
    for tok in re.findall(r"[a-z0-9\-]{4,}", ll):
        if abs(len(tok) - len(wl)) <= 1 and _lev1(wl, tok):
            return True
    return False


def _lev1(a, b):
    """ระยะแก้ไข (Levenshtein) ≤ 1 ไหม"""
    if a == b:
        return True
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


class ScreenWatch(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        c = app.cfg
        self.enabled = bool(c.get("watch_on"))
        self.words = [w.strip() for w in (c.get("watch_words") or []) if w.strip()]
        self.interval = max(3, int(c.get("watch_interval") or 8))
        self.cooldown = max(10, int(c.get("watch_cooldown") or 120))
        self.last_text = []
        self.last_at = 0
        self.last_err = None
        self.last_ms = 0
        self.hits = deque(maxlen=50)      # {"t","word","line","image","hwnd"}
        self._last_hit = {}               # word → เวลาแจ้งล่าสุด (cooldown)
        self.scans = 0
        self.cycle = max(30, int(c.get("watch_cycle") or 300))
        self.reset_at = None              # เวลารีเซ็ตรอบถัดไป (จากนาฬิกาบนจอ หรือคาดจากรอบก่อน)
        self.burst_until = 0
        os.makedirs(DIR, exist_ok=True)

    # ---------- ตั้งค่า ----------
    def configure(self, on=None, words=None, interval=None, cooldown=None):
        if on is not None:
            self.enabled = bool(on)
        if words is not None:
            self.words = [w.strip() for w in words if w.strip()]
        if interval is not None:
            self.interval = max(3, int(interval))
        if cooldown is not None:
            self.cooldown = max(10, int(cooldown))
        c = self.app.cfg
        c["watch_on"], c["watch_words"], c["watch_interval"], c["watch_cooldown"] = self.enabled, self.words, self.interval, self.cooldown
        config.save(c)

    def windows(self):
        eng = self.app.eng
        return roblox_windows(True) + [h for h in eng.hidden if u.IsWindow(h)]

    # ---------- อ่านจอครั้งเดียว ----------
    def read_once(self, hwnd=None):
        """ถ่าย + OCR หน้าต่างเดียว — คืน (บรรทัดข้อความ, path รูป) · ยกเว้น RuntimeError พร้อมข้อความไทย"""
        from PIL import Image
        from .ipc import grab_window
        from . import ocr
        wins = [hwnd] if hwnd else self.windows()
        if not wins:
            raise RuntimeError("ไม่เจอหน้าต่าง Roblox")
        im, msg = grab_window(wins[0])
        if im is None:
            raise RuntimeError(msg)
        big = im.resize((im.width * 2, im.height * 2), Image.BICUBIC)
        # ชื่อไฟล์ไม่ซ้ำทุกครั้ง — WinRT (StorageFile) ถือไฟล์ที่เพิ่งอ่านไว้จนกว่า GC จะเก็บ เขียนทับชื่อเดิมจะติด "[Errno 22] Invalid argument"
        self._n = getattr(self, "_n", 0) + 1
        path = os.path.join(DIR, f"frame_{self._n % 1000:03d}.png")
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            path = os.path.join(DIR, f"frame_{int(time.time() * 1000)}.png")
        big.save(path, compress_level=1)
        eng = ocr.get()
        lines = eng.recognize(path)
        # รอบ B: เทา + ยืดคอนทราสต์ทีละกล่อง → อ่านตัวหนังสือดำบนพื้นมืด (Secret ในแชท)
        from PIL import ImageOps
        pathb = path[:-4] + "b.png"
        local_norm(ImageOps.grayscale(big), 96).save(pathb, compress_level=1)
        seen = {l.strip().lower() for l in lines}
        for l in eng.recognize(pathb):
            if l.strip().lower() not in seen:
                lines.append(l)
                seen.add(l.strip().lower())
        # ลบเฟรมเก่าแบบไม่ซีเรียส (ตัวที่ยังถูกถืออยู่จะลบไม่ได้ ค่อยลบรอบหน้า)
        for old in sorted(glob.glob(os.path.join(DIR, "frame_*.png")))[:-4]:
            try:
                os.remove(old)
            except OSError:
                pass
        self._last_im = im          # เก็บภาพขนาดจริงไว้ทำรูปแจ้งเตือน ไม่ต้องเปิดไฟล์ซ้ำ
        return lines, path

    def scan(self):
        t0 = time.time()
        for h in self.windows():
            lines, path = self.read_once(h)
            self.last_text = lines
            self.last_at = time.time()
            self.last_err = None
            for l in lines:
                m = RE_COUNTDOWN.search(l)
                if m:
                    self.reset_at = time.time() + int(m.group(1))     # จูนเวลารีเซ็ตจากนาฬิกาจริงบนจอ
                    break
            low = [l.lower() for l in lines]
            now = time.time()
            # ประกาศไข่หายากอยู่ในแชท ซึ่งค้างบนจอนานหลายนาที — จำ "บรรทัด" ที่เคยเจอไว้ 30 นาที ไม่งั้นจะเตือนซ้ำทุกรอบ cooldown ทั้งที่เป็นข้อความเดิม
            self._seen = {k: t for k, t in getattr(self, "_seen", {}).items() if now - t < 1800}
            for w in self.words:
                wl = w.lower()
                hit_line = next((lines[i] for i, l in enumerate(low) if fuzzy_in(wl, l) and "".join(ch for ch in l if ch.isalnum()) not in self._seen), None)
                if hit_line is None:
                    continue
                if now - self._last_hit.get(w, 0) < self.cooldown:
                    continue
                self._last_hit[w] = now
                self._seen["".join(ch for ch in hit_line.lower() if ch.isalnum())] = now
                snap = os.path.join(DIR, f"hit_{int(time.time())}_{w[:12]}.png")
                try:
                    im = self._last_im
                    im.resize((960, max(1, int(960 * im.height / im.width)))).save(snap)
                except Exception:
                    snap = path
                hit = {"t": time.time(), "word": w, "line": hit_line[:120], "image": snap, "hwnd": h}
                self.hits.appendleft(hit)
                self.app.on_event("watch_hit", hit)
        self.scans += 1
        self.last_ms = int((time.time() - t0) * 1000)
        # เก็บรูปที่เจอไว้แค่ 30 ไฟล์ล่าสุด
        old = sorted(glob.glob(os.path.join(DIR, "hit_*.png")))[:-30]
        for p in old:
            try:
                os.remove(p)
            except OSError:
                pass

    def run(self):
        while True:
            if not self.enabled or not self.words:
                time.sleep(2)
                continue
            t0 = time.time()
            try:
                self.scan()
            except Exception as e:
                self.last_err = str(e)
            # รอบรีเซ็ตของเกม: ไข่หายากสุ่ม/ประกาศตอนนั้น → สแกนถี่ทุก 2 วิ ช่วง -5..+45 วิ แล้วคาดรอบถัดไป +cycle
            now = time.time()
            iv = self.interval
            if self.reset_at:
                if now > self.reset_at + 45:
                    while self.reset_at + 45 < now:
                        self.reset_at += self.cycle
                if -5 <= now - self.reset_at <= 45:
                    iv = 2
            time.sleep(max(1.0, iv - (time.time() - t0)))

    def status(self):
        return {"on": self.enabled, "words": self.words, "interval": self.interval, "cooldown": self.cooldown,
                "last_at": self.last_at, "last_err": self.last_err, "last_ms": self.last_ms, "scans": self.scans,
                "reset_in": (int(self.reset_at - time.time()) if self.reset_at else None), "burst": bool(self.reset_at and -5 <= time.time() - self.reset_at <= 45),
                "hits": [{k: v for k, v in h.items() if k != "hwnd"} for h in list(self.hits)[:5]]}
