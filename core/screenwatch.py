"""👁 เฝ้าจอ — ถ่ายหน้าต่าง Roblox เป็นระยะ → OCR → เจอคำที่ตั้งไว้แล้วแจ้ง
ทำไมต้องมี: เกมแนว Steal An Egg ไข่หายากโผล่เป็นครั้งคราว ผู้ใช้ AFK อยู่ในเซิร์ฟคนน้อยที่หายาก ไม่อยากออกไปหาใหม่ อยากรู้ทันทีตอนมันโผล่
วิธี: PrintWindow (ถ่ายได้แม้ถูกบัง/ซ่อน alpha 0 — แต่ไม่ได้ถ้าย่อ) → ขยาย 2 เท่า (OCR ขนาดจริงอ่านแทบไม่ได้) → Windows OCR
ไม่แตะโปรเซสเกมเลย เป็นแค่การถ่ายจอ"""
import glob
import os
import threading
import time
from collections import deque

from . import config
from .win import roblox_windows, u

DIR = os.path.join(config.DATA_DIR, "watch")


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
        # สลับชื่อไฟล์ 3 ชื่อ — PowerShell/WinRT ยังถือไฟล์ที่เพิ่งอ่านไว้แป๊บหนึ่ง เขียนทับทันทีจะติด "Invalid argument"
        self._n = (getattr(self, "_n", 0) + 1) % 3
        path = os.path.join(DIR, f"frame{self._n}.png")
        big.save(path, compress_level=1)
        lines = ocr.get().recognize(path)
        self._last_im = im          # เก็บภาพขนาดจริงไว้ทำรูปแจ้งเตือน ไม่ต้องเปิดไฟล์ซ้ำ
        return lines, path

    def scan(self):
        t0 = time.time()
        for h in self.windows():
            lines, path = self.read_once(h)
            self.last_text = lines
            self.last_at = time.time()
            self.last_err = None
            low = [l.lower() for l in lines]
            for w in self.words:
                wl = w.lower()
                hit_line = next((lines[i] for i, l in enumerate(low) if wl in l), None)
                if hit_line is None:
                    continue
                if time.time() - self._last_hit.get(w, 0) < self.cooldown:
                    continue
                self._last_hit[w] = time.time()
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
            time.sleep(max(2.0, self.interval - (time.time() - t0)))

    def status(self):
        return {"on": self.enabled, "words": self.words, "interval": self.interval, "cooldown": self.cooldown,
                "last_at": self.last_at, "last_err": self.last_err, "last_ms": self.last_ms, "scans": self.scans,
                "hits": [{k: v for k, v in h.items() if k != "hwnd"} for h in list(self.hits)[:5]]}
