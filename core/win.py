"""Win32 helpers ที่ใช้ร่วมกันทั้งโปรแกรม (ctypes ล้วน ไม่มี dependency)"""
import ctypes
import os
import time
from ctypes import wintypes

u, k = ctypes.windll.user32, ctypes.windll.kernel32

SW_HIDE, SW_SHOW, SW_MINIMIZE, SW_RESTORE = 0, 5, 6, 9
GWL_EXSTYLE, WS_EX_LAYERED, LWA_ALPHA = -20, 0x80000, 0x2
KEYEVENTF_KEYUP = 0x2
VK_MENU, VK_SPACE, VK_I, VK_O, VK_F8 = 0x12, 0x20, 0x49, 0x4F, 0x77
VK_F4, VK_F5, VK_F6, VK_F7 = 0x73, 0x74, 0x75, 0x76
VK_ESCAPE, VK_RETURN, VK_R = 0x1B, 0x0D, 0x52
MOD_NOREPEAT, WM_HOTKEY = 0x4000, 0x0312
ROBLOX_EXES = {"robloxplayerbeta.exe", "windows10universal.exe", "applicationframehost.exe"}
EnumP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def proc_path(pid):
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        return ""
    buf = ctypes.create_unicode_buffer(1024)
    n = wintypes.DWORD(1024)
    ok = k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
    k.CloseHandle(h)
    return buf.value if ok else ""


def proc_name(pid):
    h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    buf = ctypes.create_unicode_buffer(1024)
    n = wintypes.DWORD(1024)
    ok = k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
    k.CloseHandle(h)
    return os.path.basename(buf.value).lower() if ok else ""


def hwnd_pid(hwnd):
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def title(hwnd):
    n = u.GetWindowTextLengthW(hwnd)
    b = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(hwnd, b, n + 1)
    return b.value


def roblox_windows(visible=True):
    out = []

    def cb(h, _):
        if bool(u.IsWindowVisible(h)) == visible and title(h) == "Roblox" and proc_name(hwnd_pid(h)) in ROBLOX_EXES:
            out.append(h)
        return True

    u.EnumWindows(EnumP(cb), 0)
    return out


def roblox_pids():
    return {hwnd_pid(h) for h in roblox_windows(True) + roblox_windows(False)}


class _PE32(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]


def procs_named(name):
    """pid ทั้งหมดของโปรเซสที่ชื่อไฟล์ตรงกับ name (ไม่สนตัวพิมพ์) — ไม่ต้องมีหน้าต่างก็เจอ"""
    out = []
    snap = k.CreateToolhelp32Snapshot(0x2, 0)
    if not snap or snap == wintypes.HANDLE(-1).value:
        return out
    pe = _PE32()
    pe.dwSize = ctypes.sizeof(_PE32)
    ok = k.Process32FirstW(snap, ctypes.byref(pe))
    while ok:
        if pe.szExeFile.lower() == name.lower():
            out.append(pe.th32ProcessID)
        ok = k.Process32NextW(snap, ctypes.byref(pe))
    k.CloseHandle(snap)
    return out


class _PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def proc_mem_mb(pid):
    """หน่วยความจำ (working set) ของโปรเซส เป็น MB — 0 ถ้าอ่านไม่ได้"""
    h = k.OpenProcess(0x1000 | 0x0400, False, pid)
    if not h:
        return 0
    pmc = _PMC()
    pmc.cb = ctypes.sizeof(_PMC)
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb)
    k.CloseHandle(h)
    return pmc.WorkingSetSize / 1048576 if ok else 0


def proc_start_epoch(pid):
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        return None
    c, e, kn, us = (wintypes.FILETIME() for _ in range(4))
    ok = k.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kn), ctypes.byref(us))
    k.CloseHandle(h)
    if not ok:
        return None
    return (((c.dwHighDateTime << 32) | c.dwLowDateTime) - 116444736000000000) / 1e7


def kill_pid(pid):
    h = k.OpenProcess(1, False, pid)  # PROCESS_TERMINATE
    if not h:
        return False
    ok = k.TerminateProcess(h, 0)
    k.CloseHandle(h)
    return bool(ok)


def force_fg(hwnd):
    for _ in range(2):
        fg = u.GetForegroundWindow()
        cur, tgt = k.GetCurrentThreadId(), u.GetWindowThreadProcessId(fg, None)
        u.AttachThreadInput(cur, tgt, True)
        u.BringWindowToTop(hwnd)
        u.SetForegroundWindow(hwnd)
        u.AttachThreadInput(cur, tgt, False)
        time.sleep(0.05)
        if u.GetForegroundWindow() == hwnd:
            return True
        u.keybd_event(VK_MENU, 0, 0, 0)  # Alt trick ปลด foreground lock
        u.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    return u.GetForegroundWindow() == hwnd


def set_alpha(hwnd, a):
    st = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if a < 255:
        u.SetWindowLongW(hwnd, GWL_EXSTYLE, st | WS_EX_LAYERED)
        u.SetLayeredWindowAttributes(hwnd, 0, a, LWA_ALPHA)
    else:
        u.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)
        u.SetWindowLongW(hwnd, GWL_EXSTYLE, st & ~WS_EX_LAYERED)


def tap(vk, hold=0.05):
    sc = u.MapVirtualKeyW(vk, 0)
    u.keybd_event(vk, sc, 0, 0)
    time.sleep(hold)
    u.keybd_event(vk, sc, KEYEVENTF_KEYUP, 0)


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def idle_seconds():
    li = LASTINPUTINFO()
    li.cbSize = ctypes.sizeof(li)
    u.GetLastInputInfo(ctypes.byref(li))
    return ((k.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000.0


def hotkey_loop(bindings, on_fail, retries=6, gap=2.0):
    """รันใน thread แยก: bindings = {vk: callback}; RegisterHotKey ต้องมี message loop ของ thread ตัวเอง

    ลองซ้ำได้ เพราะตอนเพิ่งปิดโปรแกรมตัวเก่าแล้วเปิดใหม่ ตัวเก่าอาจยังถือปุ่มลัดค้างอยู่ไม่กี่วินาที
    """
    import time as _t
    ids, left = {}, dict(enumerate(bindings.items(), 1))
    for attempt in range(retries):
        for i, (vk, cb) in list(left.items()):
            if u.RegisterHotKey(None, i, MOD_NOREPEAT, vk):
                ids[i] = cb
                left.pop(i)
        if not left:
            break
        if attempt < retries - 1:
            _t.sleep(gap)
    for i, (vk, cb) in left.items():
        on_fail(vk)
    if not ids:
        return
    msg = wintypes.MSG()
    while u.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY and msg.wParam in ids:
            ids[msg.wParam]()


VK_F9 = 0x78


# ---------- ICMP ping ผ่าน iphlpapi (ไม่ต้อง admin) ----------
_iphlp = ctypes.windll.iphlpapi
_ws2 = ctypes.windll.ws2_32
_iphlp.IcmpCreateFile.restype = ctypes.c_void_p
_iphlp.IcmpCloseHandle.argtypes = [ctypes.c_void_p]
_iphlp.IcmpSendEcho.restype = wintypes.DWORD
_iphlp.IcmpSendEcho.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.WORD, ctypes.c_void_p,
                                ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD]
_ws2.inet_addr.restype = wintypes.DWORD
_ws2.inet_addr.argtypes = [ctypes.c_char_p]


class ICMP_ECHO_REPLY(ctypes.Structure):
    _fields_ = [("Address", wintypes.DWORD), ("Status", wintypes.ULONG), ("RoundTripTime", wintypes.ULONG),
                ("DataSize", wintypes.USHORT), ("Reserved", wintypes.USHORT), ("Data", ctypes.c_void_p),
                ("Options", ctypes.c_byte * 8)]


def ping(ip, timeout_ms=1000):
    """คืน RTT (ms) หรือ None ถ้าไม่ตอบ"""
    try:
        addr = _ws2.inet_addr(ip.encode())
        if addr == 0xFFFFFFFF:
            return None
        h = _iphlp.IcmpCreateFile()
        if not h:
            return None
        data = ctypes.create_string_buffer(b"RobloxToolkit")
        size = ctypes.sizeof(ICMP_ECHO_REPLY) + 32 + 8
        buf = ctypes.create_string_buffer(size)
        n = _iphlp.IcmpSendEcho(h, addr, data, 13, None, buf, size, timeout_ms)
        _iphlp.IcmpCloseHandle(h)
        if n == 0:
            return None
        rep = ctypes.cast(buf, ctypes.POINTER(ICMP_ECHO_REPLY)).contents
        return int(rep.RoundTripTime) if rep.Status == 0 else None
    except Exception:
        return None


def default_gateway():
    import subprocess
    try:
        out = subprocess.run(["route", "print", "0.0.0.0"], capture_output=True, text=True, timeout=5,
                             creationflags=0x08000000).stdout
        for line in out.splitlines():
            p = line.split()
            if len(p) >= 3 and p[0] == "0.0.0.0" and p[1] == "0.0.0.0":
                return p[2]
    except Exception:
        pass
    return None


# ---------- รีเฟรชเรตจอ ----------
# เจอจริง: จอโน้ตบุ๊กรองรับ 165 Hz แต่ Windows ตั้งไว้ 60 → เกมวาด 120 FPS ก็เห็นแค่ 60 (ปรับ Frame Rate Cap ในเกมไปก็ไม่ต่าง)
class _DEVMODE(ctypes.Structure):
    _fields_ = [("dmDeviceName", wintypes.WCHAR * 32), ("dmSpecVersion", wintypes.WORD), ("dmDriverVersion", wintypes.WORD),
                ("dmSize", wintypes.WORD), ("dmDriverExtra", wintypes.WORD), ("dmFields", wintypes.DWORD),
                ("dmPositionX", ctypes.c_long), ("dmPositionY", ctypes.c_long), ("dmDisplayOrientation", wintypes.DWORD),
                ("dmDisplayFixedOutput", wintypes.DWORD), ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
                ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short), ("dmCollate", ctypes.c_short),
                ("dmFormName", wintypes.WCHAR * 32), ("dmLogPixels", wintypes.WORD), ("dmBitsPerPel", wintypes.DWORD),
                ("dmPelsWidth", wintypes.DWORD), ("dmPelsHeight", wintypes.DWORD), ("dmDisplayFlags", wintypes.DWORD),
                ("dmDisplayFrequency", wintypes.DWORD), ("dmICMMethod", wintypes.DWORD), ("dmICMIntent", wintypes.DWORD),
                ("dmMediaType", wintypes.DWORD), ("dmDitherType", wintypes.DWORD), ("dmReserved1", wintypes.DWORD),
                ("dmReserved2", wintypes.DWORD), ("dmPanningWidth", wintypes.DWORD), ("dmPanningHeight", wintypes.DWORD)]


DM_DISPLAYFREQUENCY = 0x400000
CDS_UPDATEREGISTRY, CDS_TEST = 0x1, 0x2
DISP_CHANGE_SUCCESSFUL = 0


def display_info():
    """(กว้าง, สูง, Hz ตอนนี้, [Hz ที่จอหลักรองรับที่ความละเอียดนี้])"""
    dm = _DEVMODE()
    dm.dmSize = ctypes.sizeof(_DEVMODE)
    if not u.EnumDisplaySettingsW(None, -1, ctypes.byref(dm)):       # ENUM_CURRENT_SETTINGS
        return None
    w, h, hz = dm.dmPelsWidth, dm.dmPelsHeight, dm.dmDisplayFrequency
    rates, i = set(), 0
    while u.EnumDisplaySettingsW(None, i, ctypes.byref(dm)):
        if dm.dmPelsWidth == w and dm.dmPelsHeight == h:
            rates.add(int(dm.dmDisplayFrequency))
        i += 1
    return w, h, int(hz), sorted(rates)


def set_refresh(hz):
    """เปลี่ยนรีเฟรชเรตจอหลัก (ความละเอียดเดิม) — คืน (สำเร็จไหม, ข้อความ) · ทดสอบก่อนด้วย CDS_TEST"""
    dm = _DEVMODE()
    dm.dmSize = ctypes.sizeof(_DEVMODE)
    if not u.EnumDisplaySettingsW(None, -1, ctypes.byref(dm)):
        return False, "อ่านค่าจอไม่ได้"
    dm.dmDisplayFrequency = int(hz)
    dm.dmFields = DM_DISPLAYFREQUENCY
    if u.ChangeDisplaySettingsExW(None, ctypes.byref(dm), None, CDS_TEST, None) != DISP_CHANGE_SUCCESSFUL:
        return False, f"จอไม่รับ {hz} Hz ที่ความละเอียดนี้"
    r = u.ChangeDisplaySettingsExW(None, ctypes.byref(dm), None, CDS_UPDATEREGISTRY, None)
    if r != DISP_CHANGE_SUCCESSFUL:
        return False, f"เปลี่ยนไม่ได้ (รหัส {r})"
    return True, f"จอเป็น {hz} Hz แล้ว"
