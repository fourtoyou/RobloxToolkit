"""อัดมาโคร — บันทึกการขยับเมาส์ / คลิก / กดปุ่ม พร้อมจังหวะเวลา แล้วเล่นซ้ำ (แบบ TinyTask)

วิธีทำงาน: ดักอินพุตทั้งระบบด้วย low-level hook (WH_MOUSE_LL / WH_KEYBOARD_LL) ซึ่งต้องมี
message loop ของเธรดตัวเอง · ตัวจัดการ hook ต้องทำงานเร็วมาก ไม่งั้น Windows ถอด hook ทิ้งเงียบๆ
เราจึงแค่ "เก็บใส่ลิสต์" ในนั้น แล้วค่อยไปประมวลผลทีหลัง

อินพุตที่เราส่งเองตอนเล่นมาโคร จะถูกกรองทิ้ง (ธง LLMHF_INJECTED) ไม่งั้นจะอัดซ้ำตัวเอง
"""
import ctypes
import json
import os
import threading
import time
from ctypes import wintypes

from . import config
from .clicker import BUTTONS, _key, _mouse, _send, wait
from .win import roblox_windows, u

MACRO_DIR = os.path.join(config.DATA_DIR, "macros")
WH_KEYBOARD_LL, WH_MOUSE_LL = 13, 14
LLMHF_INJECTED = 0x01
MOVE_MIN_PX, MOVE_MIN_GAP = 4, 0.02        # อัดการขยับเมาส์ไม่ถี่เกินไป ไฟล์จะได้ไม่บวม
MAX_EVENTS = 20000

WM = {0x0201: ("mouse", "left", 0), 0x0202: ("mouse", "left", 1),
      0x0204: ("mouse", "right", 0), 0x0205: ("mouse", "right", 1),
      0x0207: ("mouse", "middle", 0), 0x0208: ("mouse", "middle", 1)}
WM_MOUSEMOVE, WM_WHEEL = 0x0200, 0x020A
KEY_DOWN, KEY_UP = (0x0100, 0x0104), (0x0101, 0x0105)

HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
u.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
u.SetWindowsHookExW.restype = wintypes.HHOOK
u.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
u.CallNextHookEx.restype = ctypes.c_long
u.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]


class MSLL(ctypes.Structure):
    _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class KBLL(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


# ---------- ไฟล์ ----------
def macro_list():
    try:
        return sorted(f[:-5] for f in os.listdir(MACRO_DIR) if f.endswith(".json"))
    except OSError:
        return []


def macro_path(name):
    safe = "".join(ch for ch in name if ch not in '\\/:*?"<>|').strip() or "macro"
    return os.path.join(MACRO_DIR, safe + ".json")


def macro_save(name, events):
    os.makedirs(MACRO_DIR, exist_ok=True)
    with open(macro_path(name), "w", encoding="utf-8") as f:
        json.dump({"at": time.time(), "events": events}, f, ensure_ascii=False)


def macro_load(name):
    try:
        with open(macro_path(name), encoding="utf-8") as f:
            return json.load(f).get("events") or []
    except Exception:
        return []


def macro_delete(name):
    try:
        os.remove(macro_path(name))
    except OSError:
        pass


def macro_info(name):
    ev = macro_load(name)
    dur = ev[-1][0] if ev else 0
    clicks = sum(1 for e in ev if e[1] == "mouse" and e[3] == 0)
    keys = sum(1 for e in ev if e[1] == "key" and e[3] == 0)
    return {"events": len(ev), "seconds": dur, "clicks": clicks, "keys": keys}


class Recorder(threading.Thread):
    """อัดอินพุตทั้งระบบ — events = [[เวลาจากเริ่ม, ชนิด, ค่า, กด/ปล่อย], ...]

    ชนิด: "move" (ค่า = [x, y]) · "mouse" (ค่า = left/right/middle) · "key" (ค่า = vk) · "wheel" (ค่า = คลิกล้อ)
    """

    def __init__(self, on_done, ignore_vks=()):
        super().__init__(daemon=True)
        self.on_done = on_done
        self.ignore = set(ignore_vks)
        self.events = []
        self.stop_ev = threading.Event()
        self.t0 = 0
        self._last_move = 0
        self._last_pt = (0, 0)
        self._hooks = []
        self._tid = 0

    def _t(self):
        return round(time.perf_counter() - self.t0, 4)

    def _mouse_cb(self, code, wparam, lparam):
        if code >= 0 and len(self.events) < MAX_EVENTS:
            d = ctypes.cast(lparam, ctypes.POINTER(MSLL)).contents
            if not (d.flags & LLMHF_INJECTED):
                msg = int(wparam)
                if msg == WM_MOUSEMOVE:
                    now = time.perf_counter()
                    x, y = d.pt.x, d.pt.y
                    if now - self._last_move >= MOVE_MIN_GAP and (abs(x - self._last_pt[0]) + abs(y - self._last_pt[1])) >= MOVE_MIN_PX:
                        self._last_move, self._last_pt = now, (x, y)
                        self.events.append([self._t(), "move", [x, y], 0])
                elif msg in WM:
                    _, btn, updown = WM[msg]
                    self.events.append([self._t(), "mouse", btn, updown])
                elif msg == WM_WHEEL:
                    self.events.append([self._t(), "wheel", ctypes.c_short(d.mouseData >> 16).value, 0])
        return u.CallNextHookEx(None, code, wparam, lparam)

    def _key_cb(self, code, wparam, lparam):
        if code >= 0 and len(self.events) < MAX_EVENTS:
            d = ctypes.cast(lparam, ctypes.POINTER(KBLL)).contents
            if not (d.flags & 0x10) and d.vkCode not in self.ignore:    # 0x10 = LLKHF_INJECTED
                msg = int(wparam)
                if msg in KEY_DOWN:
                    self.events.append([self._t(), "key", d.vkCode, 0])
                elif msg in KEY_UP:
                    self.events.append([self._t(), "key", d.vkCode, 1])
        return u.CallNextHookEx(None, code, wparam, lparam)

    def run(self):
        self.t0 = time.perf_counter()
        self._tid = ctypes.windll.kernel32.GetCurrentThreadId()
        cbs = [HOOKPROC(self._mouse_cb), HOOKPROC(self._key_cb)]   # ต้องถือ reference ไว้ ไม่งั้นโดน GC
        self._cbs = cbs
        for hid, cb in ((WH_MOUSE_LL, cbs[0]), (WH_KEYBOARD_LL, cbs[1])):
            h = u.SetWindowsHookExW(hid, cb, None, 0)
            if h:
                self._hooks.append(h)
        if len(self._hooks) < 2:
            config.dbg("macro: ติดตั้ง hook ไม่ครบ")
        msg = wintypes.MSG()
        while not self.stop_ev.is_set():
            if u.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                u.TranslateMessage(ctypes.byref(msg))
                u.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.002)
        for h in self._hooks:
            u.UnhookWindowsHookEx(h)
        self._hooks.clear()
        self.on_done(self.events)

    def stop(self):
        self.stop_ev.set()


class Player(threading.Thread):
    """เล่นมาโครซ้ำ — loops = 0 คือวนไม่หยุดจนกว่าจะสั่งหยุด"""

    def __init__(self, events, log, on_done, loops=1, speed=1.0, only_roblox=True):
        super().__init__(daemon=True)
        self.events, self.log, self.on_done = events, log, on_done
        self.loops, self.speed, self.only_roblox = loops, max(0.1, speed), only_roblox
        self.stop_ev = threading.Event()
        self.round = 0

    def stop(self):
        self.stop_ev.set()

    def run(self):
        try:
            n = 0
            while not self.stop_ev.is_set() and (self.loops == 0 or n < self.loops):
                n += 1
                self.round = n
                if not self.play_once():
                    break
        finally:
            self.on_done(self.round)

    def play_once(self):
        prev = 0.0
        for t, kind, val, updown in self.events:
            if self.stop_ev.is_set():
                return False
            gap = (t - prev) / self.speed
            prev = t
            if gap > 0:
                wait(min(gap, 10))       # ถ้าตอนอัดหยุดคิดนาน อย่ารอเกิน 10 วิ
            if self.only_roblox and u.GetForegroundWindow() not in roblox_windows(True):
                self.log("⏸ มาโครพัก — ไม่ได้อยู่ที่หน้าต่าง Roblox")
                while not self.stop_ev.is_set() and u.GetForegroundWindow() not in roblox_windows(True):
                    time.sleep(0.3)
                if self.stop_ev.is_set():
                    return False
            if kind == "move":
                u.SetCursorPos(int(val[0]), int(val[1]))
            elif kind == "mouse":
                down, up_ = BUTTONS.get(val, BUTTONS["left"])
                _send(_mouse(up_ if updown else down))
            elif kind == "key":
                _send(_key(int(val), bool(updown)))
            elif kind == "wheel":
                _send(_mouse_wheel(int(val)))
        return True


def _mouse_wheel(delta):
    from .clicker import INPUT, MOUSEINPUT, _U, INPUT_MOUSE
    return INPUT(type=INPUT_MOUSE, u=_U(mi=MOUSEINPUT(0, 0, delta, 0x0800, 0, None)))   # MOUSEEVENTF_WHEEL
