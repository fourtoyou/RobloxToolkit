"""จำกัด FPS ของ Roblox ตอนที่ไม่ได้โฟกัสหน้าต่าง + ปิดเสียงเกมตอน AFK

วิธีจำกัด FPS (เทคนิคเดียวกับ AntiAFK-RBX — ดูซอร์สเขาแล้ว):
ไม่ได้ไปแก้ FastFlag หรือไฟล์ตั้งค่าของ Roblox เลย แต่ **หยุด-ปลุกเธรดของเกมเป็นจังหวะ**
    SuspendThread ทุกเธรด → Sleep(1000/fps - 1) → ResumeThread ทุกเธรด
5 FPS = หยุด 199 ms ปลุก 1 ms วนไปเรื่อยๆ

ข้อดี: ใช้ได้กับ Roblox ทุกเวอร์ชันรวมถึงตัว Microsoft Store (ที่ไม่มีโฟลเดอร์ ClientSettings)
ข้อควรระวังที่ต้องทำให้ถูก:
- หน้าต่างที่กำลังโฟกัสอยู่ ห้ามหยุด (กำลังเล่นอยู่ต้องลื่น)
- ต้องพักตัวจำกัด FPS ก่อน Anti-AFK กดปุ่ม ไม่งั้นปุ่มไม่เข้า
- ตอนปิดโปรแกรม/ปิดฟีเจอร์ ต้อง ResumeThread ให้ครบ ไม่งั้นเกมค้างถาวร
"""
import ctypes
import threading
import time
from ctypes import wintypes

from . import config
from .win import roblox_windows, u

k = ctypes.windll.kernel32
TH32CS_SNAPTHREAD = 0x4
THREAD_SUSPEND_RESUME = 0x0002
PRESETS = (3, 5, 10, 15, 30)


class THREADENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ThreadID", wintypes.DWORD),
                ("th32OwnerProcessID", wintypes.DWORD), ("tpBasePri", wintypes.LONG),
                ("tpDeltaPri", wintypes.LONG), ("dwFlags", wintypes.DWORD)]


k.OpenThread.restype = wintypes.HANDLE
k.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]


def threads_of(pid):
    """thread id ทั้งหมดของโปรเซส"""
    out = []
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if not snap or snap == wintypes.HANDLE(-1).value:
        return out
    te = THREADENTRY32()
    te.dwSize = ctypes.sizeof(THREADENTRY32)
    ok = k.Thread32First(snap, ctypes.byref(te))
    while ok:
        if te.th32OwnerProcessID == pid:
            out.append(te.th32ThreadID)
        ok = k.Thread32Next(snap, ctypes.byref(te))
    k.CloseHandle(snap)
    return out


class FpsCapper(threading.Thread):
    """หยุด-ปลุกเธรดของ Roblox เพื่อจำกัด FPS ตอนไม่ได้โฟกัส"""
    REFRESH = 2.0            # เช็ครายชื่อเธรดใหม่ทุกกี่วินาที

    def __init__(self, log, cfg):
        super().__init__(daemon=True)
        self.log, self.cfg = log, cfg
        self.handles = []
        self.lock = threading.Lock()
        self.paused = False       # พักชั่วคราว (ตอน Anti-AFK จะกดปุ่ม)
        self.capping = False      # ตอนนี้กำลังจำกัดอยู่จริงไหม
        self.last_refresh = 0

    # ---------- ควบคุม ----------
    def pause(self):
        """พักการจำกัด FPS แล้วปลุกเธรดทั้งหมด — เรียกก่อนสั่ง Anti-AFK กดปุ่ม"""
        was = self.paused
        self.paused = True
        self.release()
        return was

    def resume(self, previous=False):
        self.paused = previous

    def release(self):
        """ปลุกเธรดทุกตัวและปล่อย handle — ต้องเรียกให้ครบเสมอ ไม่งั้นเกมค้าง"""
        with self.lock:
            for h in self.handles:
                while k.ResumeThread(h) > 1:      # กันกรณีถูก suspend ซ้อนกันหลายชั้น
                    pass
                k.CloseHandle(h)
            self.handles = []
        self.capping = False

    # ---------- ลูป ----------
    def target_fps(self):
        return int(self.cfg.get("fps_cap", 0) or 0)

    def should_cap(self):
        if self.paused or not self.cfg.get("fps_cap_on") or self.target_fps() <= 0:
            return False
        wins = roblox_windows(True)
        if not wins:
            return False
        if self.cfg.get("fps_unlock_focus", True) and u.GetForegroundWindow() in wins:
            return False        # กำลังเล่นอยู่ อย่าไปหน่วง
        return True

    def refresh_handles(self):
        from .win import hwnd_pid
        wins = roblox_windows(True)
        fg = u.GetForegroundWindow() if self.cfg.get("fps_unlock_focus", True) else None
        pids = {hwnd_pid(h) for h in wins if h != fg}
        want = []
        for pid in pids:
            want += [(pid, t) for t in threads_of(pid)]
        self.release()
        with self.lock:
            for _, tid in want:
                h = k.OpenThread(THREAD_SUSPEND_RESUME, False, tid)
                if h:
                    self.handles.append(h)

    def run(self):
        while True:
            try:
                if not self.should_cap():
                    if self.handles:
                        self.release()
                    time.sleep(0.3)
                    continue
                if time.time() - self.last_refresh >= self.REFRESH:
                    self.last_refresh = time.time()
                    self.refresh_handles()
                with self.lock:
                    hs = list(self.handles)
                if not hs:
                    time.sleep(0.4)
                    continue
                self.capping = True
                gap = max(0.002, 1.0 / max(1, self.target_fps()) - 0.001)
                for h in hs:
                    k.SuspendThread(h)
                time.sleep(gap)
                for h in hs:
                    k.ResumeThread(h)
                time.sleep(0.005)
            except Exception as e:
                config.dbg(f"fpscap: {e}")
                self.release()
                time.sleep(1)


# ---------- ปิดเสียงเกม ----------
def set_roblox_muted(mute=True):
    """ปิด/เปิดเสียงเฉพาะ Roblox (ไม่ยุ่งกับเสียงโปรแกรมอื่น) — คืน (ทำได้ไหม, จำนวนที่ทำ)"""
    try:
        from pycaw.pycaw import AudioUtilities
    except ImportError:
        return False, 0
    n = 0
    try:
        for s in AudioUtilities.GetAllSessions():
            if not s.Process:
                continue
            if (s.Process.name() or "").lower() in ("robloxplayerbeta.exe", "windows10universal.exe"):
                s.SimpleAudioVolume.SetMute(1 if mute else 0, None)
                n += 1
    except Exception as e:
        config.dbg(f"mute: {e}")
        return False, 0
    return True, n


def roblox_muted():
    """ตอนนี้ Roblox ถูกปิดเสียงอยู่ไหม — None ถ้าเช็คไม่ได้"""
    try:
        from pycaw.pycaw import AudioUtilities
        for s in AudioUtilities.GetAllSessions():
            if s.Process and (s.Process.name() or "").lower() == "robloxplayerbeta.exe":
                return bool(s.SimpleAudioVolume.GetMute())
    except Exception:
        pass
    return None


# ---------- เปิด Roblox ได้หลายตัว ----------
_mutex = None


def multi_instance(on=True):
    """จอง mutex ที่ Roblox ใช้กันเปิดซ้ำ → เปิดได้หลายหน้าต่าง (เทคนิคเดียวกับที่ทุกเจ้าใช้)"""
    global _mutex
    if on:
        if _mutex:
            return True
        _mutex = k.CreateMutexW(None, True, "ROBLOX_singletonEvent")
        return bool(_mutex)
    if _mutex:
        k.CloseHandle(_mutex)
        _mutex = None
    return False


def multi_instance_on():
    return _mutex is not None
