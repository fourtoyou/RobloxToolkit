"""ออโต้คลิก / กดปุ่มรัว — ส่งอินพุตจริงด้วย SendInput (Roblox รับเฉพาะอินพุตจริง)

ความสามารถ (เทียบกับ OP Auto Clicker / Speed AutoClicker / GS / Murgee):
- โหมดสลับ (กด F6 ติด-ดับ) และ **โหมดกดค้าง** (กดปุ่มค้างไว้ถึงจะคลิก — แบบ Speed AutoClicker)
- คลิกเดี่ยว / ดับเบิล / ทริปเปิล
- ตามเคอร์เซอร์ หรือ **ล็อกตำแหน่ง/หลายจุดวนไปเรื่อยๆ** (แบบ GS / Murgee) — F7 เก็บตำแหน่งที่เมาส์ชี้อยู่
- สุ่มช่วงเวลาแบบกำหนดเอง (ต่ำสุด-สูงสุด %) แทนค่าตายตัว
- โหมดรัวเป็นชุด (คลิก N ครั้ง แล้วพักกี่วินาที)
- โปรไฟล์: บันทึกชุดตั้งค่าไว้ต่อเกมได้

ข้อควรรู้ (สำคัญ):
- นี่คือมาโครอินพุตธรรมดา ไม่ได้ฉีดโค้ด ไม่ได้อ่าน/แก้หน่วยความจำเกม
- แต่หลายเกม (โดยเฉพาะแนวคลิกเกอร์/ซิมูเลเตอร์) มีระบบตรวจจับการคลิกอัตโนมัติเอง
  ถ้าเกมนั้นห้ามและจับได้ = โดนแบนเกมนั้น · การสุ่มจังหวะทำให้ไม่เป๊ะเท่าหุ่นยนต์
  แต่ไม่ได้แปลว่าปลอดภัยจากการตรวจจับ
- กันพลาดไว้: คลิกเฉพาะตอนที่ Roblox เป็นหน้าต่างที่โฟกัสอยู่ (เปิดเป็นค่าเริ่มต้น)
"""
import ctypes
import json
import os
import random
import threading
import time
from ctypes import wintypes

from . import config
from .win import roblox_windows, u

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
BUTTONS = {           # ชื่อ -> (flag กดลง, flag ปล่อย)
    "left": (0x0002, 0x0004),
    "right": (0x0008, 0x0010),
    "middle": (0x0020, 0x0040),
}
KEYEVENTF_KEYUP = 0x0002
MAX_CPS = 1000        # เพดานจริงของ SendInput คือหมื่นกว่า/วิ · แต่เกมอ่านอินพุตทีละเฟรม
                      # 60 fps = รับได้จริงราว 60 ครั้ง/วิ ที่เกินจากนั้นเกมส่วนใหญ่ทิ้ง
SPIN_UNDER = 0.005    # ช่วงเวลาต่ำกว่านี้ต้องหน่วงแบบวนรอ (time.sleep ละเอียดไม่พอ)
_win_cache = {"at": 0.0, "set": ()}
PROFILES_PATH = os.path.join(config.DATA_DIR, "click_profiles.json")

# ค่าที่โปรไฟล์เก็บ (คีย์ใน settings.json)
PROFILE_KEYS = ("click_cps", "click_mode", "click_button", "click_key", "click_vk", "click_type",
                "click_trigger", "click_hold_key", "click_hold_vk", "click_interval_ms", "click_rand_min", "click_rand_max",
                "click_only_roblox", "click_max_min", "click_max_clicks", "click_points",
                "click_restore_cursor", "click_burst", "click_burst_pause")

# ชื่อปุ่ม -> virtual-key code (โหมดกดปุ่มรัว และปุ่มที่ใช้กดค้าง)
VK_MAP = {c: ord(c.upper()) for c in "abcdefghijklmnopqrstuvwxyz0123456789"}
VK_MAP.update({"space": 0x20, "enter": 0x0D, "tab": 0x09, "shift": 0x10, "ctrl": 0x11, "alt": 0x12,
               "esc": 0x1B, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27})
VK_MAP.update({f"f{i}": 0x6F + i for i in range(1, 13)})
# ปุ่มเมาส์ (ใช้เป็นปุ่มกดค้างได้ เช่น mouse1 = คลิกซ้าย, mouse4/5 = ปุ่มข้าง)
VK_MAP.update({"mouse1": 0x01, "mouse2": 0x02, "mouse3": 0x04, "mouse4": 0x05, "mouse5": 0x06})


def vk_of(name):
    """แปลงชื่อปุ่มเป็นรหัส — คืน None ถ้าไม่รู้จัก"""
    return VK_MAP.get((name or "").strip().lower())


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


u.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
u.SendInput.restype = wintypes.UINT


def _send(*inputs):
    arr = (INPUT * len(inputs))(*inputs)
    return u.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def _mouse(flag):
    return INPUT(type=INPUT_MOUSE, u=_U(mi=MOUSEINPUT(0, 0, 0, flag, 0, None)))


def _key(vk, up=False):
    return INPUT(type=INPUT_KEYBOARD, u=_U(ki=KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, None)))


def click(button="left", times=1, batch=1):
    """times = คลิกเดี่ยว/ดับเบิล/ทริปเปิล · batch = ยัดกี่คลิกลง SendInput ครั้งเดียว (โหมดเทอร์โบ)"""
    down, up_ = BUTTONS.get(button, BUTTONS["left"])
    if batch > 1 and times == 1:
        ev = []
        for _ in range(batch):
            ev += [_mouse(down), _mouse(up_)]
        return _send(*ev)
    for i in range(max(1, times)):
        _send(_mouse(down), _mouse(up_))
        if i + 1 < times:
            time.sleep(0.03)      # ต้องมีช่องว่างเล็กน้อย Windows ถึงจะนับเป็นดับเบิลคลิก


def press(vk, times=1, batch=1):
    if batch > 1 and times == 1:
        ev = []
        for _ in range(batch):
            ev += [_key(vk), _key(vk, True)]
        return _send(*ev)
    for i in range(max(1, times)):
        _send(_key(vk), _key(vk, True))
        if i + 1 < times:
            time.sleep(0.03)


def wait(sec):
    """หน่วงเวลาให้แม่น — time.sleep บน Windows คลาดเคลื่อน ~0.5 ms ซึ่งพังตอนตั้งเร็วๆ"""
    if sec <= 0:
        return
    end = time.perf_counter() + sec
    if sec > SPIN_UNDER:
        time.sleep(sec - 0.0015)
    while time.perf_counter() < end:   # วนรอเฉพาะเสี้ยวสุดท้าย
        pass


def cursor_pos():
    p = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def click_at(x, y, button="left", times=1, restore=True):
    """ย้ายเมาส์ไปคลิกที่จุดที่กำหนด แล้ว (ถ้าต้องการ) เอาเมาส์กลับที่เดิม"""
    old = cursor_pos()
    u.SetCursorPos(int(x), int(y))
    time.sleep(0.008)
    click(button, times)
    if restore:
        u.SetCursorPos(*old)


def key_down(vk):
    return bool(u.GetAsyncKeyState(vk) & 0x8000)


def roblox_focused():
    """เช็คว่าหน้าต่างที่โฟกัสอยู่คือ Roblox — แคชรายชื่อหน้าต่างไว้ 1 วิ
    (roblox_windows() ไล่ทุกหน้าต่างในเครื่อง ใช้ ~0.4 ms ถ้าเรียกทุกคลิกจะคอขวดทันทีตอนตั้งเร็วๆ)"""
    now = time.perf_counter()
    if now - _win_cache["at"] > 1.0:
        _win_cache["at"], _win_cache["set"] = now, frozenset(roblox_windows(True))
    fg = u.GetForegroundWindow()
    if fg in _win_cache["set"]:
        return True
    _win_cache["at"], _win_cache["set"] = now, frozenset(roblox_windows(True))   # เผลอเปิดหน้าต่างใหม่ ตรวจซ้ำทันที
    return fg in _win_cache["set"]


# ---------- โปรไฟล์ ----------
def load_profiles():
    try:
        with open(PROFILES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_profile(name, cfg):
    p = load_profiles()
    p[name] = {k: cfg[k] for k in PROFILE_KEYS if k in cfg}
    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        with open(PROFILES_PATH, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
    return p


def delete_profile(name):
    p = load_profiles()
    p.pop(name, None)
    try:
        with open(PROFILES_PATH, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
    return p


class Clicker(threading.Thread):
    """เธรดคลิก/กดปุ่มรัว — start_clicking() / stop_clicking() · อ่านค่าจาก cfg สดๆ ทุกครั้ง"""

    def __init__(self, log, on_event, cfg):
        super().__init__(daemon=True)
        self.log, self.emit, self.cfg = log, on_event, cfg
        self.on = threading.Event()
        self.clicks = 0
        self.started_at = 0
        self.paused_reason = ""
        self.point_i = 0
        self.burst_n = 0
        self._hold_active = False
        self._up_polls = 0

    # ---------- ควบคุม ----------
    def describe(self):
        c = self.cfg
        kind = {1: "คลิก", 2: "ดับเบิลคลิก", 3: "ทริปเปิลคลิก"}.get(c["click_type"], "คลิก")
        what = f"ปุ่ม {c['click_key'].upper()}" if c["click_mode"] == "key" else \
            kind + {"left": "ซ้าย", "right": "ขวา", "middle": "กลาง"}[c["click_button"]]
        where = f"{len(c['click_points'])} จุดที่ล็อกไว้" if c["click_points"] else "ตามเคอร์เซอร์"
        ms = float(c.get("click_interval_ms") or 0)
        speed = f"ทุก {ms:g} ms (~{1000 / ms:.0f} ครั้ง/วิ)" if ms > 0 else f"{c['click_cps']} ครั้ง/วิ"
        return f"{what} · {speed} · {where}"

    def start_clicking(self):
        if self.on.is_set():
            return
        self.clicks, self.started_at, self.paused_reason = 0, time.time(), ""
        self.point_i = self.burst_n = 0
        self._hold_active, self._up_polls = False, 0
        self.on.set()
        self.log(f"🖱 เริ่มออโต้ — {self.describe()}" + ("  (เฉพาะตอนอยู่ในหน้าต่าง Roblox)" if self.cfg["click_only_roblox"] else "  ⚠ ทุกหน้าต่าง"))
        self.emit("click_state", {"on": True})

    def stop_clicking(self, why=""):
        if not self.on.is_set():
            return
        self.on.clear()
        dur = time.time() - self.started_at
        self.log(f"🖱 หยุดออโต้ — คลิกไป {self.clicks} ครั้งใน {dur:.0f} วิ" + (f" ({why})" if why else ""))
        self.emit("click_state", {"on": False, "clicks": self.clicks, "seconds": dur, "why": why})

    def toggle(self):
        self.stop_clicking("กดปิดเอง") if self.on.is_set() else self.start_clicking()

    def add_point(self):
        """เก็บตำแหน่งที่เมาส์ชี้อยู่ตอนนี้เข้าลิสต์ (ผูกกับ F7)"""
        x, y = cursor_pos()
        self.cfg["click_points"].append([x, y])
        self.log(f"📍 เก็บจุดที่ {len(self.cfg['click_points'])}: ({x}, {y})")
        self.emit("click_points", {"points": self.cfg["click_points"]})

    @property
    def running(self):
        return self.on.is_set()

    @property
    def armed(self):
        """โหมดกดค้าง: ติดอยู่ (รอให้กดปุ่มค้าง) — ใช้โชว์สถานะ"""
        return self.on.is_set() and self.cfg["click_trigger"] == "hold"

    # ---------- ลูป ----------
    def run(self):
        while True:
            if not self.on.wait(0.2):
                continue
            try:
                self.tick()
            except Exception as e:
                self.log(f"ออโต้คลิกมีปัญหา: {e}")
                self.stop_clicking("เกิดข้อผิดพลาด")

    def base_gap(self):
        """ช่วงเวลาระหว่างคลิก (วินาที) — ถ้าระบุ ms เองไว้ ใช้อันนั้นก่อน"""
        c = self.cfg
        ms = float(c.get("click_interval_ms") or 0)
        if ms > 0:
            return max(0.0002, ms / 1000.0)
        return 1.0 / max(1, min(int(c["click_cps"]), MAX_CPS))

    def gap(self):
        c = self.cfg
        base = self.base_gap()
        lo, hi = c["click_rand_min"], c["click_rand_max"]
        if hi > lo:
            base *= random.uniform(lo, hi) / 100.0
        return max(0.0002, base)

    def tick(self):
        c = self.cfg
        # เบรกกันพัง: หยุดเองเมื่อครบจำนวน/ครบเวลา
        if c["click_max_min"] and time.time() - self.started_at >= c["click_max_min"] * 60:
            return self.stop_clicking(f"ครบ {c['click_max_min']} นาทีที่ตั้งไว้")
        if c["click_max_clicks"] and self.clicks >= c["click_max_clicks"]:
            return self.stop_clicking(f"ครบ {c['click_max_clicks']} ครั้งที่ตั้งไว้")
        if c["click_only_roblox"] and not roblox_focused():
            if self.paused_reason != "focus":
                self.paused_reason = "focus"
                self.log("⏸ พักไว้ก่อน — ตอนนี้ไม่ได้อยู่ที่หน้าต่าง Roblox (คลิกกลับไปที่เกมแล้วจะทำต่อเอง)")
            return time.sleep(0.25)
        if self.paused_reason == "focus":
            self.paused_reason = ""
            self.log("▶ กลับมาที่ Roblox แล้ว — ทำต่อ")
        # โหมดกดค้าง: คลิกเฉพาะตอนที่ปุ่มถูกกดค้างไว้จริงๆ
        if c["click_trigger"] == "hold":
            if key_down(c["click_hold_vk"]):
                self._hold_active, self._up_polls = True, 0
                self.paused_reason = ""
            else:
                # ทนต่อการอ่านค่าพลาดสั้นๆ ได้ 3 รอบ (อินพุตที่เราส่งเองอาจไปกวนสถานะปุ่มเดียวกัน)
                self._up_polls += 1
                if self._up_polls >= 3:
                    self._hold_active = False
            if not self._hold_active:
                self.paused_reason = "hold"
                return time.sleep(0.02)

        times = max(1, min(int(c["click_type"]), 3))
        # เร็วมากจน Python ตามไม่ทัน -> ยัดหลายคลิกลง SendInput ครั้งเดียว
        g = self.base_gap()
        batch = 1 if g >= 0.002 or times > 1 or c["click_points"] else min(20, max(1, int(0.002 / max(g, 1e-5))))
        if c["click_mode"] == "key":
            press(c["click_vk"], times, batch)
        elif c["click_points"]:
            x, y = c["click_points"][self.point_i % len(c["click_points"])]
            self.point_i += 1
            click_at(x, y, c["click_button"], times, c["click_restore_cursor"])
        else:
            click(c["click_button"], times, batch)
        self.clicks += batch

        # รัวเป็นชุดแล้วพัก
        if c["click_burst"]:
            self.burst_n += batch
            if self.burst_n >= c["click_burst"]:
                self.burst_n = 0
                return time.sleep(max(0.05, c["click_burst_pause"]))
        wait(self.gap() * batch)
