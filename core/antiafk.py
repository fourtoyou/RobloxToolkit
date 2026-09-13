"""Anti-AFK engine + ตัวตาม log ของ Roblox (ย้ายมาจาก v4 แล้วเพิ่ม event hook)
เทคนิคหลักจาก JunkBeat/AntiAFK-Roblox: เด้งหน้าต่างขึ้นมา (โปร่งใส) → กดคีย์จริง → ย่อกลับ → คืน focus
โหมดซ่อน: SW_HIDE หน้าต่างที่ย่ออยู่ → ยังรับ focus/คีย์ได้โดยไม่โผล่บนจอ
"""
import atexit
import glob
import os
import re
import threading
import time

from . import config
from .win import (SW_HIDE, SW_MINIMIZE, SW_RESTORE, SW_SHOW, VK_ESCAPE, VK_I, VK_O, VK_R, VK_RETURN, VK_SPACE, force_fg, idle_seconds,
                  kill_pid, proc_start_epoch, roblox_pids, roblox_windows, set_alpha, tap, u)

RE_JOIN = re.compile(r"! Joining game '([0-9a-f-]+)' place (\d+) at ([\d.]+)")
RE_SERVER = re.compile(r"serverId: ([\d.]+)\|(\d+)")
RE_DISC = re.compile(r"Sending disconnect with reason: (\d+)")
RE_LOGTS = re.compile(r"_(\d{8}T\d{6})Z_Player_")
REASONS = {277: "เน็ตหลุด/เซิร์ฟล่ม", 278: "โดนเตะ idle 20 นาที", 273: "ล็อกอินที่อื่น", 267: "โดนสคริปต์เตะ",
           268: "โดนเตะ", 264: "ล็อกอินซ้ำ", 279: "เข้าเซิร์ฟไม่ได้", 280: "เวอร์ชันไม่ตรง", 285: "ออกเอง/วาร์ป",
           260: "แพ็กเก็ตเสียหาย", 262: "ส่งข้อมูลผิดพลาด", 274: "เซิร์ฟปิดปรับปรุง", 291: "ถูกปิดจากที่อื่น",
           276: "เซิร์ฟตัดการเชื่อมต่อ", 272: "ข้อมูลไม่ตรงกับเซิร์ฟ", 265: "ตัวละครถูกลบ", 266: "เซิร์ฟไม่ตอบ"}
IGNORE_REASONS = {285}
IDLE_NEED, IDLE_MAX_WAIT = 3.0, 120


def reason_text(code):
    return REASONS.get(code, f"reason {code}")


def log_epoch(path):
    m = RE_LOGTS.search(os.path.basename(path))
    if not m:
        return None
    t = time.strptime(m.group(1), "%Y%m%dT%H%M%S")
    return time.mktime(t) - time.timezone


class LogWatcher(threading.Thread):
    """ตาม log ทุก 2 วิ → event: ("join", place, job, ip) / ("server", ip, port) / ("disconnect", reason, place, job, path)"""

    def __init__(self, on_event):
        super().__init__(daemon=True)
        self.on_event = on_event
        self.files = {}
        self.lock = threading.Lock()
        self.last_join_at = 0
        self.current = {"place": None, "job": None, "server": None, "in_game": False}

    def run(self):
        while True:
            try:
                self.scan()
            except Exception:
                pass
            time.sleep(2)

    def scan(self):
        now = time.time()
        with self.lock:
            for d in config.LOG_DIRS:
                for p in glob.glob(os.path.join(d, "*_Player_*.log")):
                    try:
                        mtime = os.path.getmtime(p)
                    except OSError:
                        continue
                    st = self.files.get(p)
                    if st is None:
                        if now - mtime > 600:
                            continue
                        st = self.files[p] = {"pos": 0, "job": None, "place": None, "handled": True, "server": None}
                        self.backfill(p, st)
                    else:
                        self.read_new(p, st)

    def backfill(self, p, st):
        size = os.path.getsize(p)
        with open(p, "rb") as f:
            f.seek(max(0, size - 512 * 1024))
            data = f.read().decode("utf-8", "ignore")
        for line in data.splitlines():
            m = RE_JOIN.search(line)
            if m:
                st["job"], st["place"], st["handled"] = m.group(1), m.group(2), False
                self.current.update(place=st["place"], job=st["job"], in_game=True)
            elif RE_SERVER.search(line):
                ms = RE_SERVER.search(line)
                st["server"] = (ms.group(1), int(ms.group(2)))
                self.current["server"] = st["server"]
            elif RE_DISC.search(line):
                st["handled"] = True
                self.current["in_game"] = False
        st["pos"] = size

    def read_new(self, p, st):
        size = os.path.getsize(p)
        if size <= st["pos"]:
            return
        with open(p, "rb") as f:
            f.seek(st["pos"])
            data = f.read().decode("utf-8", "ignore")
        st["pos"] = size
        for line in data.splitlines():
            self.parse_line(p, st, line)

    def parse_line(self, p, st, line):
        m = RE_JOIN.search(line)
        if m:
            st["job"], st["place"], st["handled"] = m.group(1), m.group(2), False
            self.last_join_at = time.time()
            self.current.update(place=st["place"], job=st["job"], in_game=True, server=None)
            self.on_event(("join", st["place"], st["job"], m.group(3)))
            return
        m = RE_SERVER.search(line)
        if m:
            st["server"] = (m.group(1), int(m.group(2)))
            self.current["server"] = st["server"]
            self.on_event(("server", m.group(1), int(m.group(2))))
            return
        m = RE_DISC.search(line)
        if m and not st["handled"] and st["place"]:
            st["handled"] = True
            self.current["in_game"] = False
            reason = int(m.group(1))
            self.on_event(("disconnect", reason, st["place"], st["job"], p))

    def refresh(self, p):
        with self.lock:
            if p in self.files:
                self.read_new(p, self.files[p])
            return self.files.get(p, {}).get("handled", True)


class Engine:
    MAX_REJOIN = 5

    def __init__(self, log, on_event=lambda kind, data: None):
        self.log = log
        self.emit = on_event
        self.hidden = set()
        self.lock = threading.Lock()
        self.stop_ev = threading.Event()
        self.thread = None
        self.next_at = 0
        self.delay, self.action, self.invisible = 600, "jump", True
        self.wait_idle, self.auto_rejoin = True, True
        self.rejoining = False
        self.poke_count = 0
        self.last_fail = 0            # รอบที่แล้วกดไม่ติดกี่ครั้งติดกัน
        self.last_place = self.last_job = None
        self.session_start = None
        self.adaptive = True          # ลด delay เองเมื่อโดนเตะ idle (278) ทั้งที่กำลังทำงาน
        self.pre_poke = lambda: False    # ให้ app เสียบตัวพัก FPS capper เข้ามา (ไม่งั้นปุ่มไม่เข้า)
        self.post_poke = lambda prev: None
        self.last_disconnect_at = 0
        self.watcher = LogWatcher(self.on_log_event)
        self.watcher.start()
        atexit.register(self.unhide_all)

    # ---------- poke ----------
    def poke(self, hwnd, is_hidden, keys=None):
        prev = u.GetForegroundWindow()
        import ctypes
        from ctypes import wintypes
        pt = wintypes.POINT()
        u.GetCursorPos(ctypes.byref(pt))
        was_min = bool(u.IsIconic(hwnd))
        ok = False
        try:
            if is_hidden:
                ok = force_fg(hwnd)
                time.sleep(0.15)
            else:
                if self.invisible:
                    set_alpha(hwnd, 0)
                if was_min:
                    u.ShowWindow(hwnd, SW_RESTORE)
                ok = force_fg(hwnd)
                time.sleep(1.2 if was_min else 0.2)
            if keys:
                for vk, gap in keys:
                    tap(vk)
                    time.sleep(gap)
            elif self.action == "camera":
                tap(VK_I)
                time.sleep(0.08)
                tap(VK_O)
            else:
                tap(VK_SPACE)
            time.sleep(0.1)
        finally:
            if not is_hidden:
                if was_min:
                    u.ShowWindow(hwnd, SW_MINIMIZE)
                if self.invisible:
                    set_alpha(hwnd, 255)
            if prev and prev != hwnd and u.IsWindow(prev):
                force_fg(prev)
            u.SetCursorPos(pt.x, pt.y)
        return ok

    # ลำดับปุ่มรีเซ็ตตัวละคร: ESC เปิดเมนู → R เลือก Reset Character → Enter ยืนยัน
    RESET_KEYS = ((VK_ESCAPE, 0.25), (VK_R, 0.25), (VK_RETURN, 0.15))

    def reset_character(self):
        """รีเซ็ตตัวละคร (เผื่อตกแมพ/ติดอยู่ในที่แปลกๆ ระหว่าง AFK) — คืนจำนวนหน้าต่างที่สั่งไป"""
        prev = self.pre_poke()
        try:
            with self.lock:
                self.hidden = {h for h in self.hidden if u.IsWindow(h)}
                wins = list(self.hidden) + roblox_windows(True)
                for h in wins:
                    self.poke(h, h in self.hidden, keys=self.RESET_KEYS)
                    time.sleep(0.3)
                if wins:
                    self.log(f"🔄 สั่งรีเซ็ตตัวละคร {len(wins)} หน้าต่าง (ESC → R → Enter)")
                else:
                    self.log("ไม่เจอหน้าต่าง Roblox")
                self.emit("reset", {"windows": len(wins)})
                return len(wins)
        finally:
            self.post_poke(prev)

    def wait_for_idle(self):
        if not self.wait_idle:
            return
        t0 = time.time()
        said = False
        while idle_seconds() < IDLE_NEED and time.time() - t0 < IDLE_MAX_WAIT:
            if not said:
                self.log("คุณกำลังใช้เครื่องอยู่ — รอให้ว่างมือก่อน")
                said = True
            if self.stop_ev.wait(0.5):
                return

    def poke_all(self):
        self.wait_for_idle()
        if self.stop_ev.is_set():
            return 0
        prev_paused = self.pre_poke()      # หยุดจำกัด FPS ชั่วคราว ไม่งั้นเกมรับปุ่มไม่ทัน
        with self.lock:
            self.hidden = {h for h in self.hidden if u.IsWindow(h)}
            vis = roblox_windows(True)
            n = ok_n = 0
            for h in list(self.hidden) + vis:
                hid = h in self.hidden
                ok = self.poke(h, hid)
                n += 1
                ok_n += bool(ok)
                self.poke_count += 1
                tag = " (ซ่อน)" if hid else (" (ย่อ)" if u.IsIconic(h) else "")
                self.log(f"{'✓' if ok else '⚠ focus ไม่ติด'} HWND {h}{tag} → {'Space' if self.action == 'jump' else 'I/O'}")
                time.sleep(0.3)
            if n == 0:
                self.log("ยังไม่เจอหน้าต่าง Roblox")
            # กดไม่ติดสักหน้าต่าง (หรือไม่เจอหน้าต่างเลย) → อย่ารออีก 10 นาที ไม่งั้นครบ 20 นาทีโดนเตะ
            self.last_fail = self.last_fail + 1 if ok_n == 0 else 0
            if self.last_fail == 2:
                self.log("⚠ กดไม่ติด 2 ครั้งติด — เสี่ยงโดนเตะ idle กำลังลองถี่ขึ้นทุก 1 นาที")
                self.emit("poke_failing", {"times": self.last_fail})
            self.emit("poke", {"count": n})
            self.post_poke(prev_paused)
            return n

    def loop(self, immediate):
        if immediate:
            self.poke_all()
        while not self.stop_ev.is_set():
            wait = min(60, self.delay) if self.last_fail else self.delay
            self.next_at = time.time() + wait
            if self.stop_ev.wait(wait):
                break
            self.poke_all()

    def start(self, immediate=True):
        if self.running:
            return
        self.stop_ev.clear()
        self.thread = threading.Thread(target=self.loop, args=(immediate,), daemon=True)
        self.thread.start()
        self.emit("state", {"running": True})

    def stop(self):
        self.stop_ev.set()
        self.next_at = 0
        self.emit("state", {"running": False})

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    # ---------- hide mode ----------
    def hide_minimized(self):
        with self.lock:
            c = 0
            for h in roblox_windows(True):
                if u.IsIconic(h):
                    u.ShowWindow(h, SW_RESTORE)
                    u.ShowWindow(h, SW_HIDE)
                    self.hidden.add(h)
                    c += 1
            return c

    def unhide_all(self):
        with self.lock:
            for h in list(self.hidden):
                if u.IsWindow(h):
                    u.ShowWindow(h, SW_MINIMIZE)
                    u.ShowWindow(h, SW_SHOW)
            n = len(self.hidden)
            self.hidden.clear()
            return n

    # ---------- auto-reconnect ----------
    def on_log_event(self, ev):
        kind = ev[0]
        if kind == "join":
            self.last_place, self.last_job = ev[1], ev[2]
            self.session_start = time.time()
            self.log(f"เข้าเกมแล้ว place {ev[1]}")
            self.emit("join", {"place": ev[1], "job": ev[2]})
        elif kind == "server":
            self.emit("server", {"ip": ev[1], "port": ev[2]})
        elif kind == "disconnect":
            reason, place, job, path = ev[1:]
            self.log(f"{'ออกจากเกม' if reason in IGNORE_REASONS else '⚠ หลุด'}: {reason_text(reason)} (code {reason})")
            self.emit("disconnect", {"reason": reason, "text": reason_text(reason), "place": place, "job": job, "path": path,
                                     "session_start": self.session_start})
            self.session_start = None
            self.last_disconnect_at = time.time()
            if reason in IGNORE_REASONS:
                return
            if reason == 278 and self.running and self.adaptive:
                new = max(60, int(self.delay * 0.7) // 10 * 10)
                if new < self.delay:
                    self.log(f"โดนเตะ idle ทั้งที่ Anti-AFK ทำงานอยู่ (กดทุก {self.delay} วิ) → ลดเหลือทุก {new} วิ")
                    self.delay = new
                    self.emit("adapt", {"delay": new})
            if self.auto_rejoin and not self.rejoining:
                self.rejoining = True
                threading.Thread(target=self.rejoin, args=(reason, place, job, path), daemon=True).start()

    def match_pid(self, path):
        ts = log_epoch(path) if path else None
        pids = roblox_pids()
        if ts:
            for pid in pids:
                st = proc_start_epoch(pid)
                if st and -5 <= ts - st <= 30:
                    return pid
        return next(iter(pids)) if len(pids) == 1 else None

    def rejoin(self, reason, place, job, path, force=False):
        try:
            was_hidden = bool(self.hidden)
            if not force:
                time.sleep(5)
                if not self.watcher.refresh(path):
                    self.log("ต่อกลับเองได้แล้ว ไม่ต้องทำอะไร")
                    return
            for attempt in range(1, self.MAX_REJOIN + 1):
                pid = self.match_pid(path)
                if pid:
                    kill_pid(pid)
                    self.log(f"ปิด Roblox เดิม (pid {pid})")
                    time.sleep(2)
                use_job = job and attempt <= 2
                url = f"roblox://experiences/start?placeId={place}" + (f"&gameInstanceId={job}" if use_job else "")
                self.log(f"ต่อใหม่ครั้งที่ {attempt}/{self.MAX_REJOIN} → {'เซิร์ฟเดิม' if use_job else 'เซิร์ฟไหนก็ได้'}")
                t0 = time.time()
                os.startfile(url)
                while time.time() - t0 < 90:
                    time.sleep(3)
                    if self.watcher.last_join_at > t0:
                        self.log("✓ กลับเข้าเกมแล้ว")
                        self.emit("rejoin", {"place": place, "attempt": attempt})
                        if was_hidden:
                            threading.Thread(target=self.rehide_later, daemon=True).start()
                        return
                self.log("ยังเข้าไม่ได้ ลองใหม่")
            self.log(f"✗ ต่อใหม่ไม่สำเร็จหลังลอง {self.MAX_REJOIN} ครั้ง")
            self.emit("rejoin_failed", {"place": place})
        except Exception as e:
            self.log(f"✗ rejoin error: {e}")
        finally:
            self.rejoining = False

    def hop(self, place, pick, attempts=3):
        """ย้ายไปเซิร์ฟอื่นของเกมเดิม — pick() คืน jobId ที่จะไป (เรียกใหม่ทุกครั้งที่ลอง เผื่อเซิร์ฟเต็มไปก่อน)"""
        try:
            was_hidden = bool(self.hidden)
            for attempt in range(1, attempts + 1):
                job = pick()
                if not job:
                    self.log("หาเซิร์ฟที่เข้าได้ไม่เจอ")
                    break
                for pid in roblox_pids():
                    kill_pid(pid)
                with self.lock:
                    self.hidden = {h for h in self.hidden if u.IsWindow(h)}
                time.sleep(2)
                t0 = time.time()
                os.startfile(f"roblox://experiences/start?placeId={place}&gameInstanceId={job}")
                while time.time() - t0 < 90:
                    time.sleep(3)
                    if self.watcher.last_join_at > t0:
                        self.log("✓ ย้ายเซิร์ฟแล้ว")
                        self.emit("hop", {"place": place, "job": job, "attempt": attempt})
                        if was_hidden:
                            threading.Thread(target=self.rehide_later, daemon=True).start()
                        return True
                self.log(f"เข้าเซิร์ฟนั้นไม่ได้ (ลอง {attempt}/{attempts}) — หาใหม่")
            self.emit("hop_failed", {"place": place})
            return False
        except Exception as e:
            self.log(f"✗ ย้ายเซิร์ฟไม่ได้: {e}")
            return False
        finally:
            self.rejoining = False

    def rehide_later(self):
        time.sleep(20)
        for h in roblox_windows(True):
            if not u.IsIconic(h):
                u.ShowWindow(h, SW_MINIMIZE)
        time.sleep(0.5)
        n = self.hide_minimized()
        self.log(f"ซ่อนหน้าต่างใหม่ให้แล้ว ({n})")
