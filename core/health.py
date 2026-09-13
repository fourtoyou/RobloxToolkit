"""เช็คสุขภาพการติดตั้ง Roblox/Bloxstrap แล้วซ่อมได้ในคลิกเดียว"""
import glob
import json
import os
import subprocess
import winreg

from . import config

BS_EXE = os.path.join(config.BLOXSTRAP_DIR, "Bloxstrap.exe")
DESKTOP = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                         capture_output=True, text=True, creationflags=0x08000000).stdout.strip() or \
    os.path.join(os.environ["USERPROFILE"], "Desktop")
START = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs")
SHORTCUTS = [os.path.join(DESKTOP, "Roblox Player.lnk"), os.path.join(START, "Roblox", "Roblox Player.lnk"),
             os.path.join(START, "Roblox.lnk")]


def _reg_default(path):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
            return winreg.QueryValueEx(k, "")[0]
    except OSError:
        return None


def file_version(path):
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              f"(Get-Item '{path}').VersionInfo.ProductVersion"], capture_output=True, text=True,
                             timeout=15, creationflags=0x08000000).stdout.strip()
        return out or "?"
    except Exception:
        return "?"


def shortcut_target(path):
    try:
        ps = f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{path}'); $s.TargetPath + '|' + $s.Arguments"
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                             timeout=15, creationflags=0x08000000).stdout.strip()
        return out
    except Exception:
        return ""


LAUNCHERS = ("Bloxstrap", "Fishstrap", "Voidstrap", "Froststrap")


def find_launcher():
    """หาโปรแกรมเปิดเกมที่ใช้อยู่จริง — ดูจาก handler ที่ลงทะเบียนไว้ก่อน แล้วค่อยไล่หาโฟลเดอร์
    (วิธีเดียวกับที่ AntiAFK-RBX ใช้ — ครอบคลุม Bloxstrap และตัวแยกย่อยทุกตัว)

    คืน dict: {"name", "exe", "dir", "settings"} หรือ None
    """
    exe = ""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\roblox-player\DefaultIcon") as k:
            exe = (winreg.QueryValueEx(k, "")[0] or "").strip().strip('"').split(",")[0].strip('"')
    except OSError:
        pass
    def known(path):
        low = (path or "").lower()
        return next((n for n in LAUNCHERS if n.lower() in low), None)

    name = known(exe) if exe and os.path.exists(exe) else None
    if not name:                      # handler ชี้ไป Roblox ตรงๆ (Roblox ชอบแย่งคืน) → ไล่หาที่ติดตั้งไว้เอง
        for n in LAUNCHERS:
            p = os.path.join(config.LOCAL, n, n + ".exe")
            if os.path.exists(p):
                exe, name = p, n
                break
        else:
            return None
    d = os.path.dirname(exe)
    settings = next((os.path.join(d, f) for f in ("Settings.json", "AppSettings.json") if os.path.exists(os.path.join(d, f))), None)
    return {"name": name, "exe": exe, "dir": d, "settings": settings}


def check():
    """คืน list ของ (หัวข้อ, สถานะ ok/warn/bad, รายละเอียด)"""
    items = []
    bs = os.path.exists(BS_EXE)
    items.append(("Bloxstrap", "ok" if bs else "warn",
                  f"ติดตั้งแล้ว เวอร์ชัน {file_version(BS_EXE)}" if bs else "ไม่ได้ติดตั้ง (ไม่บังคับ แต่แนะนำ)"))
    for proto in ("roblox-player", "roblox"):
        cmd = _reg_default(rf"Software\Classes\{proto}\shell\open\command") or ""
        if not cmd:
            items.append((f"handler {proto}://", "bad", "ไม่มี — กด Play จากเว็บจะไม่เปิดเกม"))
        elif bs and "bloxstrap" not in cmd.lower():
            items.append((f"handler {proto}://", "warn", "ชี้ไป Roblox ตรงๆ ข้าม Bloxstrap (Roblox แย่ง handler ไป)"))
        else:
            items.append((f"handler {proto}://", "ok", "ผ่าน Bloxstrap" if bs else "ชี้ไป Roblox"))
    for p in SHORTCUTS:
        if not os.path.exists(p):
            continue
        tgt = shortcut_target(p)
        exe = tgt.split("|")[0]
        if not os.path.exists(exe):
            items.append((f"shortcut {os.path.basename(p)}", "bad", "ชี้ไปไฟล์ที่ไม่มีแล้ว (เสีย)"))
        elif bs and "bloxstrap" not in exe.lower():
            items.append((f"shortcut {os.path.basename(p)}", "warn", "ข้าม Bloxstrap"))
        else:
            items.append((f"shortcut {os.path.basename(p)}", "ok", os.path.basename(exe)))
    vers = glob.glob(os.path.join(config.LOCAL, "Roblox", "Versions", "version-*"))
    store = glob.glob(os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "WindowsApps", "ROBLOXCorporation.Roblox*"))
    lz = find_launcher()
    if lz:
        items.append((f"ตัวเปิดเกม: {lz['name']}", "ok", os.path.dirname(lz["exe"]) + ("  · มีไฟล์ตั้งค่า" if lz["settings"] else "")))
    else:
        items.append(("ตัวเปิดเกม", "warn", "ไม่พบ Bloxstrap / Fishstrap / Voidstrap / Froststrap — เปิดเกมผ่าน Roblox ตรงๆ"))
    items.append(("Roblox client", "ok" if vers or store else "bad",
                  (f"{len(vers)} เวอร์ชันปกติ" if vers else "") + (" + " if vers and store else "") + ("เวอร์ชัน Microsoft Store" if store else "") or "ไม่พบ"))
    running = running_flavor()
    if running == "store":
        items.append(("Roblox ที่เปิดอยู่", "warn", "เวอร์ชัน Microsoft Store — Bloxstrap ไม่มีผลกับตัวนี้ (FPS unlock/ตั้งค่าใน Bloxstrap ไม่ทำงาน) ถ้าจะใช้ Bloxstrap ให้เปิดเกมผ่าน Bloxstrap แทน"))
    elif running == "normal":
        items.append(("Roblox ที่เปิดอยู่", "ok", "เวอร์ชันปกติ (ผ่าน Bloxstrap ได้)"))
    from .win import proc_mem_mb, proc_start_epoch, procs_named, roblox_pids
    import time as _t
    zomb = [p for p in procs_named("RobloxPlayerBeta.exe") if p not in roblox_pids() and (proc_start_epoch(p) or _t.time()) < _t.time() - 300]
    if zomb:
        items.append(("Roblox ค้างเบื้องหลัง", "warn", f"{len(zomb)} โปรเซสไม่มีหน้าต่าง กิน RAM {sum(proc_mem_mb(p) for p in zomb):.0f} MB — Watchdog จะปิดให้ (ถ้าเปิดไว้)"))
    logs = []
    for d in config.LOG_DIRS:
        logs += glob.glob(os.path.join(d, "*_Player_*.log"))
    total = sum(os.path.getsize(p) for p in logs) / 1e6
    items.append(("log ของ Roblox", "warn" if total > 500 else "ok", f"{len(logs)} ไฟล์ {total:.0f} MB"
                  + (" — เยอะแล้ว ล้างได้" if total > 500 else "")))
    return items


def running_flavor():
    """Roblox ที่เปิดอยู่ตอนนี้เป็นตัวไหน: "store" (Microsoft Store/RobloxGDK) · "normal" · None ถ้าไม่ได้เปิด"""
    from .win import proc_path, roblox_pids
    paths = [proc_path(p).lower() for p in roblox_pids()]
    if not paths:
        return None
    return "store" if any(("windowsapps" in p or "xboxgames" in p or "robloxgdk" in p) for p in paths) else "normal"


def fix_bloxstrap():
    """ลงทะเบียน handler + shortcut ให้ผ่าน Bloxstrap (ทำเหมือน WindowsRegistry.RegisterPlayer ของ Bloxstrap)"""
    if not os.path.exists(BS_EXE):
        return "ไม่พบ Bloxstrap"
    cmd = f'"{BS_EXE}" -player "%1"'
    for proto in ("roblox", "roblox-player"):
        base = rf"Software\Classes\{proto}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as k:
            try:
                winreg.QueryValueEx(k, "")
            except OSError:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "URL: Roblox Protocol")
                winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\DefaultIcon") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, BS_EXE)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)
    fixed = 0
    for p in SHORTCUTS:
        if os.path.exists(p):
            ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{p}'); $s.TargetPath='{BS_EXE}'; "
                  f"$s.Arguments='-player'; $s.IconLocation='{BS_EXE},0'; $s.WorkingDirectory='{config.BLOXSTRAP_DIR}'; $s.Save()")
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=15,
                           creationflags=0x08000000)
            fixed += 1
    return f"ลงทะเบียน roblox:// + roblox-player:// และแก้ shortcut {fixed} อันให้ผ่าน Bloxstrap แล้ว"


def clean_logs(keep_days=7):
    import time
    n = 0
    for p in [f for d in config.LOG_DIRS for f in glob.glob(os.path.join(d, "*.log"))]:
        if time.time() - os.path.getmtime(p) > keep_days * 86400:
            try:
                os.remove(p)
                n += 1
            except OSError:
                pass
    return n


# ---------- เปิดอัตโนมัติ ----------
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_get():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, config.APP_NAME)
            return True
    except OSError:
        return False


def autostart_set(on):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, config.APP_NAME, 0, winreg.REG_SZ, config.exe_path() + " --tray")
        else:
            try:
                winreg.DeleteValue(k, config.APP_NAME)
            except OSError:
                pass


def bloxstrap_integration_set(on):
    """ให้ Bloxstrap เปิด Toolkit ตอนเข้าเกม และปิดตอนออกเกม (Custom Integrations)"""
    p = os.path.join(config.BLOXSTRAP_DIR, "Settings.json")
    if not os.path.exists(p):
        return "ไม่พบ Bloxstrap"
    with open(p, encoding="utf-8") as f:
        s = json.load(f)
    lst = [i for i in s.get("CustomIntegrations", []) if i.get("Name") != config.APP_NAME]
    if on:
        exe = config.exe_path()
        loc, args = (exe, "--afk") if exe.lower().endswith(".exe") else (exe.split('" "')[0].strip('"'), exe.split('" ', 1)[1] + " --afk")
        lst.append({"Name": config.APP_NAME, "Location": loc, "LaunchArgs": args, "AutoClose": True})
    s["CustomIntegrations"] = lst
    with open(p, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    return "ตั้งให้ Bloxstrap เปิด Toolkit (เริ่ม Anti-AFK ทันที) ทุกครั้งที่เข้าเกม และปิดเมื่อออกเกม" if on else "ยกเลิกแล้ว"


def bloxstrap_integration_get():
    p = os.path.join(config.BLOXSTRAP_DIR, "Settings.json")
    try:
        with open(p, encoding="utf-8") as f:
            return any(i.get("Name") == config.APP_NAME for i in json.load(f).get("CustomIntegrations", []))
    except Exception:
        return False
