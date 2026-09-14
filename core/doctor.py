"""หมอเครื่อง — ตรวจทีเดียวว่า "ทำไมเกมไม่ลื่น" แล้วบอกวิธีแก้ที่ทำได้จริง

รวมทุกบทเรียนที่เจอกับเครื่องจริง (2026-09-14):
- จอรองรับ 165 Hz แต่ Windows ตั้ง 60 → เกมวาด 120 FPS ก็เห็นแค่ 60 (ตัวการใหญ่สุด ไม่มีใครสังเกต)
- FastFlag เขียนไว้ที่ตัวปกติ แต่ผู้ใช้เล่นตัว Microsoft Store → ไม่เคยมีผล
- เน็ตมือถือ/hotspot: อะไรอัปโหลดนิดเดียว ping พุ่ง (OneDrive/แบ็กอัปรูป)
- เซิร์ฟที่ Roblox สุ่มให้อยู่ไกล (โตเกียว/เมกา) ทั้งที่สิงคโปร์มี
- RAM 89% จาก Chrome → CPU สะดุด
แต่ละข้อคืน dict: key, level (ok/warn/bad/info), title, detail, fix (ชื่อ action ให้ UI ทำปุ่ม) หรือ None
"""
import glob
import os
import re
import subprocess
import time

from . import config, fastflag
from .win import display_info, roblox_pids, proc_path

NO_WINDOW = 0x08000000


def _wifi():
    """(ssid, signal%) หรือ None ถ้าไม่ได้ใช้ Wi-Fi"""
    try:
        out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=5,
                             creationflags=NO_WINDOW).stdout
    except Exception:
        return None
    ssid = re.search(r"^\s*SSID\s*:\s*(.+)$", out, re.M)
    sig = re.search(r"Signal\s*:\s*(\d+)%", out)
    if not ssid:
        return None
    return ssid.group(1).strip(), int(sig.group(1)) if sig else None


def _active_link():
    """คำอธิบายของการ์ดเน็ตที่ใช้ออกอินเทอร์เน็ตอยู่ (ไม่ใช่ Wi-Fi) หรือ None"""
    try:
        ps = ("(Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.Name -notmatch 'Loopback|Bluetooth' } "
              "| Sort-Object -Property ifIndex | Select-Object -First 1 -ExpandProperty InterfaceDescription)")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=8,
                             creationflags=NO_WINDOW).stdout.strip()
        return out or None
    except Exception:
        return None


def _gpu_has_roblox():
    """True/False ว่า nvidia-smi เห็น RobloxPlayerBeta ใช้การ์ด NVIDIA อยู่ · None ถ้าไม่มี nvidia-smi"""
    try:
        out = subprocess.run(["nvidia-smi", "--query-compute-apps=process_name", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=6, creationflags=NO_WINDOW)
        if out.returncode != 0:
            return None
        if "RobloxPlayerBeta" in out.stdout:
            return True
        # โหมด WDDM บางเครื่องไม่ลิสต์ใน compute-apps → ดูตารางเต็ม
        full = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=6, creationflags=NO_WINDOW).stdout
        return "RobloxPlayerBeta" in full
    except Exception:
        return None


def _newest_log():
    files = []
    for d in config.LOG_DIRS:
        files += glob.glob(os.path.join(d, "*_Player_*.log"))
    return max(files, key=os.path.getmtime) if files else None


def run(app=None):
    """ตรวจทุกข้อ — คืน (รายการ, สรุปสั้น)"""
    out = []
    pids = roblox_pids()
    running = bool(pids)
    exe = proc_path(next(iter(pids))) if pids else None
    store = bool(exe) and fastflag.is_store(os.path.dirname(exe))

    # 1) รีเฟรชเรตจอ
    info = display_info()
    if info:
        w, h, hz, rates = info
        top = max(rates) if rates else hz
        if top > hz:
            out.append(dict(key="hz", level="bad", title=f"จอตั้งอยู่ที่ {hz} Hz แต่รองรับ {top} Hz",
                            detail=f"เกมวาดกี่ FPS ก็เห็นแค่ {hz} ภาพ/วิ — เรื่องนี้ตัวเดียวทำให้ 'ไม่ลื่น' มากกว่าทุกอย่าง", fix="hz"))
        else:
            out.append(dict(key="hz", level="ok", title=f"จอ {hz} Hz (สูงสุดที่รองรับ)", detail=f"{w}x{h}", fix=None))

    # 2) เกมใช้การ์ดจอแยกไหม
    if running:
        g = _gpu_has_roblox()
        if g is True:
            out.append(dict(key="gpu", level="ok", title="Roblox ใช้การ์ดจอ NVIDIA อยู่", detail="", fix=None))
        elif g is False:
            out.append(dict(key="gpu", level="bad", title="Roblox ไม่ได้ใช้การ์ดจอ NVIDIA",
                            detail="กำลังวิ่งบนการ์ดจอออนบอร์ด — FPS หายไปหลายเท่า ตั้งใน Windows: Settings → Display → Graphics → Roblox → High performance", fix="gpu"))

    # 3) FastFlag มีผลกับตัวที่เล่นจริงไหม
    if running:
        d = os.path.dirname(exe)
        has = bool(fastflag.read(d))
        log = _newest_log()
        loaded = False
        if log:
            try:
                with open(log, "rb") as f:
                    f.seek(0)
                    loaded = b"LoadClientSettingsFromLocal" in f.read(400_000)
            except OSError:
                pass
        flavor = "Microsoft Store" if store else "ตัวปกติ"
        if has and loaded:
            out.append(dict(key="ff", level="ok", title=f"FastFlag มีผลกับเกมที่เปิดอยู่ ({flavor})", detail=f"{len(fastflag.read(d))} flag โหลดแล้ว", fix=None))
        elif has:
            out.append(dict(key="ff", level="warn", title="FastFlag เขียนไว้แล้วแต่เกมยังไม่ได้โหลด", detail="ต้องปิด-เปิดเกมใหม่ค่าถึงจะมีผล", fix=None))
        else:
            out.append(dict(key="ff", level="info", title=f"ยังไม่ได้ตั้ง FastFlag ให้ตัวที่เปิดอยู่ ({flavor})", detail="หน้า FastFlag → ตั้งให้เร็ว (แนะนำ)", fix="ff"))

    # 4) priority
    cfg = app.cfg if app else config.load()
    if not cfg.get("ff_priority"):
        out.append(dict(key="pri", level="info", title="ยังไม่ได้ให้ Roblox ได้ CPU ก่อนโปรแกรมอื่น", detail="หน้า FastFlag ข้อ 4 → เปิดสวิตช์ High priority", fix="pri"))

    # 5) เน็ต: hotspot/Wi-Fi · bufferbloat · อัปโหลดตอนนี้
    wifi = _wifi()
    if wifi:
        ssid, sig = wifi
        phone = re.search(r"(?i)iphone|galaxy|s2\d|s3\d|pixel|ของ|hotspot|redmi|oppo|vivo", ssid)
        lvl = "warn" if (phone or (sig is not None and sig < 70)) else "ok"
        det = (f"สัญญาณ {sig}%" if sig is not None else "") + (" · เป็น hotspot มือถือ — ถ้าเสียบสาย USB tethering แทน Wi-Fi จะนิ่งขึ้น" if phone else "")
        out.append(dict(key="wifi", level=lvl, title=f"เน็ตผ่าน Wi-Fi '{ssid}'", detail=det.strip(" ·"), fix=None))
    else:
        link = _active_link()
        if link:
            if re.search(r"(?i)usb.*(ndis|rndis|mobile)|remote ndis|tether", link):
                out.append(dict(key="link", level="ok", title="เน็ตผ่านสาย USB จากมือถือ (tethering)", detail="นิ่งกว่า Wi-Fi hotspot — ดีแล้ว", fix=None))
            else:
                out.append(dict(key="link", level="ok", title="เน็ตผ่านสาย LAN", detail=link, fix=None))
    bb = cfg.get("bufferbloat")
    if not bb:
        out.append(dict(key="bb", level="info", title="ยังไม่เคยทดสอบว่าเน็ตนิ่งตอนอัปโหลดไหม", detail="หน้าเน็ต → ทดสอบ (~15 วิ)", fix="bb"))
    elif bb.get("grade") in ("C", "D", "F"):
        out.append(dict(key="bb", level="warn", title=f"เน็ตสะดุดตอนมีอะไรอัปโหลด (เกรด {bb['grade']})", detail=bb.get("advice", ""), fix="bb"))
    else:
        out.append(dict(key="bb", level="ok", title=f"เน็ตนิ่งตอนอัปโหลด (เกรด {bb['grade']})", detail="", fix=None))
    if app:
        up = app.sys.cur.get("up_mbps")
        if up is not None and up >= (cfg.get("upload_alert_mbps") or 3):
            from .sysmon import net_hogs
            out.append(dict(key="up", level="warn", title=f"ตอนนี้มีอะไรอัปโหลดอยู่ {up:.1f} Mbps", detail="ตัวต้องสงสัย: " + (", ".join(net_hogs()) or "-"), fix=None))
    if not cfg.get("pause_onedrive"):
        from .sysmon import onedrive_exe
        if onedrive_exe():
            out.append(dict(key="od", level="info", title="OneDrive ยังทำงานตอนเล่นเกม", detail="Desktop อยู่ใน OneDrive ทุกไฟล์ที่เซฟ = อัปโหลด · หน้าเน็ต → เปิด 'หยุด OneDrive ตอนเกมเปิด'", fix="od"))

    # 6) เซิร์ฟที่เล่นอยู่
    if app and running:
        sw = app.swatch
        cur = app.eng.watcher.current
        if cur.get("in_game") and sw.ping is not None:
            if sw.ping > 150:
                out.append(dict(key="srv", level="warn", title=f"เซิร์ฟที่เล่นอยู่ไกล (~{sw.ping} ms)",
                                detail="ส่วนขยาย Chrome ตั้ง 'ping ≤ 100' แล้วกด 'เข้า' จะได้เซิร์ฟสิงคโปร์ · หรือปุ่ม ย้ายไปเซิร์ฟเงียบ", fix=None))
            else:
                out.append(dict(key="srv", level="ok", title=f"เซิร์ฟที่เล่นอยู่ใกล้ (~{sw.ping} ms)", detail="", fix=None))

    # 7) RAM / แบต
    if app:
        c = app.sys.cur
        if c.get("ram") is not None and c["ram"] >= 85:
            from .sysmon import fmt_apps, top_apps
            out.append(dict(key="ram", level="warn", title=f"แรมใช้ไป {c['ram']:.0f}%",
                            detail="เกิน 85% CPU จะสะดุดจากการสลับหน่วยความจำ · กินเยอะสุด: " + fmt_apps(top_apps(3))
                                   + " · ปิดโปรแกรมที่ไม่ใช้ตอนเล่น หรือกด 'คืนแรม' (ชั่วคราว)", fix="ram"))
        if c.get("plugged") is False:
            out.append(dict(key="bat", level="warn", title="ไม่ได้เสียบสายชาร์จ", detail="โน้ตบุ๊กลดความเร็ว CPU/GPU ตอนใช้แบต — เสียบสายตอนเล่น", fix=None))

    if not running:
        out.append(dict(key="game", level="info", title="Roblox ยังไม่ได้เปิด", detail="เปิดเกมแล้วตรวจอีกครั้งจะได้ครบทุกข้อ (การ์ดจอ/FastFlag/เซิร์ฟ)", fix=None))

    bad = sum(1 for x in out if x["level"] == "bad")
    warn = sum(1 for x in out if x["level"] == "warn")
    if bad:
        summary = f"เจอปัญหาใหญ่ {bad} ข้อ" + (f" + ควรแก้ {warn}" if warn else "")
    elif warn:
        summary = f"ไม่มีปัญหาใหญ่ · ควรแก้ {warn} ข้อ"
    else:
        summary = "เครื่องพร้อมเล่น ไม่มีอะไรต้องแก้"
    return out, summary
