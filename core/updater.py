"""อัปเดตอัตโนมัติจาก GitHub Releases

ทางเดิน: GitHub Actions (.github/workflows/release.yml) build .exe ทุกครั้งที่ push tag v*
→ แนบไฟล์ RobloxToolkit.exe + เขียน SHA256 ไว้ใน release notes
→ โปรแกรมเช็ค releases/latest → ถ้าใหม่กว่า ดาวน์โหลด → เช็คขนาด + SHA256 + header MZ
→ .exe ที่รันอยู่ทับตัวเองไม่ได้ เลยปล่อย .bat รอให้เราปิดก่อน แล้วก๊อปทับ แล้วเปิดใหม่

กันไว้: ไม่ยอมติดตั้งถ้า SHA256 ใน release notes ไม่ตรงกับไฟล์ที่โหลดมา (กันไฟล์โดนแก้กลางทาง)
"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile

import requests

from . import config

ASSET = "RobloxToolkit.exe"
UA = {"User-Agent": "RobloxToolkit", "Accept": "application/vnd.github+json"}


def parse_ver(s):
    nums = [int(x) for x in re.findall(r"\d+", s or "")[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def check(repo, timeout=10):
    """ดู release ล่าสุด — คืน dict {tag, ver, newer, url, size, sha256, notes, html}"""
    r = requests.get(f"https://api.github.com/repos/{repo}/releases/latest", timeout=timeout, headers=UA)
    if r.status_code == 404:
        raise RuntimeError("ไม่เจอ release ใน repo นี้ — ยังไม่ได้ปล่อยเวอร์ชันแรก หรือชื่อ repo ผิด")
    if r.status_code == 403:
        raise RuntimeError("GitHub จำกัดการเรียก (ลองใหม่ในอีกสักครู่)")
    r.raise_for_status()
    d = r.json()
    tag = d.get("tag_name", "")
    asset = next((a for a in d.get("assets", []) if a.get("name") == ASSET), None)
    body = d.get("body") or ""
    m = re.search(r"SHA256[:\s`]*([0-9a-fA-F]{64})", body)
    return {
        "tag": tag,
        "ver": ".".join(map(str, parse_ver(tag))),
        "newer": parse_ver(tag) > parse_ver(config.VERSION),
        "url": asset.get("browser_download_url") if asset else None,
        "size": asset.get("size") if asset else None,
        "sha256": m.group(1).lower() if m else None,
        "notes": body[:1500],
        "html": d.get("html_url"),
    }


def download(url, dest, size=None, sha256=None, progress=None):
    """โหลดไฟล์ + ตรวจ (ขนาด / SHA256 / เป็น .exe จริง) — คืน sha256 ของไฟล์ที่ได้"""
    tmp = dest + ".part"
    h = hashlib.sha256()
    got = 0
    with requests.get(url, stream=True, timeout=30, headers={"User-Agent": "RobloxToolkit"}) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or size or 0)
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
                h.update(chunk)
                got += len(chunk)
                if progress and total:
                    progress(got / total)
    if size and got != size:
        os.remove(tmp)
        raise RuntimeError(f"ขนาดไฟล์ไม่ตรง (ได้ {got:,} ควรเป็น {size:,}) — โหลดไม่ครบ")
    if sha256 and h.hexdigest() != sha256:
        os.remove(tmp)
        raise RuntimeError("SHA256 ไม่ตรงกับที่ประกาศไว้ — ไฟล์อาจถูกแก้ระหว่างทาง ไม่ติดตั้ง")
    with open(tmp, "rb") as f:
        head = f.read(2)
    if head != b"MZ":                 # ต้องปิดไฟล์ก่อนลบ ไม่งั้น Windows ไม่ให้ลบ (WinError 32)
        os.remove(tmp)
        raise RuntimeError("ไฟล์ที่ได้ไม่ใช่โปรแกรม Windows")
    os.replace(tmp, dest)
    return h.hexdigest()


def staging_path():
    return os.path.join(tempfile.gettempdir(), "RobloxToolkit-update.exe")


def install_and_restart(new_exe):
    """ปล่อย .bat ที่รอให้โปรเซสนี้ปิด → ก๊อปไฟล์ใหม่ทับ → เปิดโปรแกรมใหม่ (ผู้เรียกต้องปิดโปรแกรมเองหลังจากนี้)"""
    if not getattr(sys, "frozen", False):
        raise RuntimeError("รันจากซอร์สอยู่ — ใช้ git pull แทน")
    cur = sys.executable
    # PyInstaller --onefile มี 2 โปรเซส: bootloader (แม่) ถือไฟล์ .exe ไว้จนกว่าจะปิด + python (ลูก) ที่รันโค้ดนี้
    # ต้องรอทั้งคู่ ไม่งั้นก๊อปทับไม่ได้ (เจอจริงตอนทดสอบ 2.9.3→2.9.4: "FAILED (N=1)")
    pids = [os.getpid()]
    try:
        pids.append(os.getppid())
    except Exception:
        pass
    bat = os.path.join(tempfile.gettempdir(), "rtk_update.bat")
    log = os.path.join(tempfile.gettempdir(), "rtk_update.log")
    wait_lines = []
    for p in pids:
        wait_lines += [f'tasklist /NH /FI "PID eq {p}" 2>nul | findstr /C:" {p} " >nul', "if not errorlevel 1 goto again"]
    # ห้ามใช้ timeout.exe — ไม่มีคอนโซลจริงมันพังทันที ใช้ ping หน่วงเวลาแทน · ห้ามใช้บล็อก ( ) เพราะ %N% ในบล็อกไม่ขยาย
    script = "\r\n".join([
        "@echo off",
        f'echo [%date% %time%] wait pids {" ".join(map(str, pids))} >> "{log}"',
        "set N=0",
        "set C=0",
        ":wait",
        *wait_lines,
        "goto go",
        ":again",
        "set /a N+=1",
        "if %N% GEQ 120 goto fail",
        "ping -n 2 127.0.0.1 >nul",
        "goto wait",
        ":go",
        f'copy /y "{cur}" "{cur}.old" >nul',
        ":copy",
        "set /a C+=1",
        f'copy /y "{new_exe}" "{cur}" >nul && goto started',
        f'echo [%date% %time%] copy retry %C% (ไฟล์ยังถูกถือไว้ / OneDrive) >> "{log}"',
        "if %C% GEQ 40 goto fail",
        "ping -n 2 127.0.0.1 >nul",
        "goto copy",
        ":started",
        f'del /q "{new_exe}" >nul 2>&1',
        f'echo [%date% %time%] starting new exe >> "{log}"',
        f'start "" "{cur}"',
        f'del /q "{cur}.old" >nul 2>&1',
        f'echo [%date% %time%] done >> "{log}"',
        "exit",
        ":fail",
        f'echo [%date% %time%] FAILED (N=%N% C=%C%) restoring >> "{log}"',
        f'if exist "{cur}.old" copy /y "{cur}.old" "{cur}" >nul',
        f'del /q "{cur}.old" >nul 2>&1',
        f'start "" "{cur}"',
        "exit",
        "",
    ])
    with open(bat, "w", encoding="ascii", errors="replace") as f:
        f.write(script)
    # CREATE_NO_WINDOW อย่างเดียว (cmd ได้คอนโซลซ่อนของตัวเอง อยู่ต่อได้หลังเราปิด) — ห้ามใส่ DETACHED_PROCESS
    CREATE_NO_WINDOW = 0x08000000
    subprocess.Popen(["cmd.exe", "/c", bat], creationflags=CREATE_NO_WINDOW, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return bat
