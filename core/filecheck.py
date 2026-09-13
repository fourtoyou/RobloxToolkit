"""ตรวจไฟล์ .exe ก่อนรัน: ลายเซ็น, hash, ถูกแพ็คด้วยอะไร, string น่าสงสัย
ไม่ได้แทนแอนตี้ไวรัส — แต่จับ stealer ที่ทำลวกๆ (ส่วนใหญ่) ได้ และให้ hash ไปเช็ค VirusTotal ต่อ"""
import hashlib
import math
import os
import re
import struct
import subprocess

# (pattern, คะแนน, คำอธิบาย)
SUSPICIOUS = [
    (rb"discord(?:app)?\.com/api/webhooks", 40, "ส่งข้อมูลออกทาง Discord webhook (สัญลักษณ์ stealer อันดับ 1)"),
    (rb"\.ROBLOSECURITY", 40, "อ้างถึง cookie ล็อกอิน Roblox โดยตรง"),
    (rb"api\.telegram\.org/bot", 35, "ส่งข้อมูลออกทาง Telegram bot"),
    (rb"Login Data|\\Cookies\b|Local State|Web Data", 30, "อ่านไฟล์รหัสผ่าน/cookie ของเบราว์เซอร์"),
    (rb"leveldb|Local Storage\\leveldb", 25, "อ่าน token ของ Discord desktop"),
    (rb"CryptUnprotectData|DPAPI", 20, "ถอดรหัสข้อมูลที่เบราว์เซอร์เข้ารหัสไว้"),
    (rb"SetWindowsHookEx|GetAsyncKeyState", 15, "ดักคีย์บอร์ด (keylogger) — บางโปรแกรมมาโครก็ใช้"),
    (rb"api\.ipify\.org|ip-api\.com|ipinfo\.io", 10, "เช็ค IP เครื่อง (มักใช้ประกอบรายงานของ stealer)"),
    (rb"CreateRemoteThread|VirtualAllocEx|WriteProcessMemory", 20, "ฉีดโค้ดเข้าโปรเซสอื่น"),
    (rb"powershell(?:\.exe)?\s+-(?:enc|e|w hidden|nop)", 25, "รัน PowerShell ซ่อนหน้าต่าง/เข้ารหัสคำสั่ง"),
    (rb"schtasks|CurrentVersion\\Run", 10, "ตั้งตัวเองให้เปิดกับ Windows"),
    (rb"vssadmin|bcdedit|wbadmin", 30, "ลบ shadow copy (ransomware)"),
    (rb"anonfiles|gofile\.io|pastebin\.com/raw|transfer\.sh", 15, "โหลด/ส่งไฟล์ผ่านเว็บฝากไฟล์นิรนาม"),
    (rb"wallet\.dat|Exodus|MetaMask|Electrum", 25, "หาไฟล์กระเป๋าคริปโต"),
    (rb"taskkill.*(?:Defender|MsMpEng)|Set-MpPreference|DisableRealtimeMonitoring", 35, "พยายามปิด Windows Defender"),
]

PACKERS = [
    (rb"PyInstaller|_MEIPASS|pyi-windows-manifest", "PyInstaller (Python) — โค้ดจริงถูกบีบอัดไว้ข้างใน มองไม่เห็นด้วยการสแกน string"),
    (rb"Nuitka", "Nuitka (Python compiled)"),
    (rb"UPX0|UPX1|UPX!", "UPX packed — ถูกบีบอัด สแกน string ไม่เจออะไร"),
    (rb"AutoIt v3|AU3!", "AutoIt script"),
    (rb"Electron|node\.dll|electron\.asar", "Electron (เว็บแอป)"),
    (rb"Inno Setup", "Inno Setup installer"),
    (rb"Nullsoft Install System|NSIS", "NSIS installer"),
    (rb"mscoree\.dll|_CorExeMain", ".NET (C#)"),
    (rb"Go build ID|go\.buildid", "Go"),
    (rb"rustc version|\.rs\x00|panicked at", "Rust"),
    (rb"MSVCP\d+\.dll|VCRUNTIME", "C/C++ (Visual Studio)"),
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def entropy(data):
    if not data:
        return 0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    n = len(data)
    return -sum(c / n * math.log2(c / n) for c in freq if c)


def signature(path):
    """ใช้ Get-AuthenticodeSignature ของ Windows เอง"""
    try:
        ps = ("$s=Get-AuthenticodeSignature -LiteralPath '{}'; "
              "Write-Output $s.Status; Write-Output ($s.SignerCertificate.Subject); "
              "Write-Output ($s.SignerCertificate.NotAfter)").format(path.replace("'", "''"))
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                             timeout=30, creationflags=0x08000000).stdout.strip().splitlines()
        status = out[0].strip() if out else "Unknown"
        subject = out[1].strip() if len(out) > 1 else ""
        m = re.search(r"CN=([^,]+)", subject)
        return {"status": status, "signer": m.group(1).strip('"') if m else subject}
    except Exception as e:
        return {"status": "Error", "signer": str(e)}


def pe_info(data):
    info = {"is_pe": False, "dotnet": False, "arch": "?", "compiled": None}
    if data[:2] != b"MZ" or len(data) < 0x40:
        return info
    try:
        e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
        if data[e_lfanew:e_lfanew + 4] != b"PE\x00\x00":
            return info
        info["is_pe"] = True
        machine, _, ts = struct.unpack_from("<HHI", data, e_lfanew + 4)
        info["arch"] = {0x14C: "x86 (32-bit)", 0x8664: "x64", 0xAA64: "ARM64"}.get(machine, hex(machine))
        info["compiled"] = ts
        opt = e_lfanew + 24
        magic = struct.unpack_from("<H", data, opt)[0]
        dd = opt + (0x70 if magic == 0x20B else 0x60)  # data directories
        clr_rva, clr_size = struct.unpack_from("<II", data, dd + 14 * 8)
        info["dotnet"] = clr_rva != 0 and clr_size != 0
    except Exception:
        pass
    return info


def analyze(path):
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        data = f.read()
    res = {"path": path, "name": os.path.basename(path), "size": size, "sha256": sha256(path),
           "signature": signature(path), "pe": pe_info(data), "entropy": entropy(data[: 4 << 20]),
           "packers": [], "findings": [], "score": 0}
    for pat, desc in PACKERS:
        if re.search(pat, data):
            res["packers"].append(desc)
    if res["pe"]["dotnet"] and not any(".NET" in p for p in res["packers"]):
        res["packers"].append(".NET (C#)")
    for pat, score, desc in SUSPICIOUS:
        hits = re.findall(pat, data)
        if hits:
            sample = hits[0].decode("latin-1", "ignore")[:60]
            res["findings"].append({"desc": desc, "score": score, "sample": sample, "count": len(hits)})
            res["score"] += score
    # ตัดสิน
    sig_ok = res["signature"]["status"] == "Valid"
    signer = res["signature"].get("signer") or "?"
    packed_blind = any("มองไม่เห็น" in p or "สแกน string ไม่เจอ" in p for p in res["packers"]) or res["entropy"] > 7.6
    res["raw_score"] = res["score"]
    # ไฟล์ที่เซ็นถูกต้อง = รู้ว่าใครเป็นคนทำและตามตัวได้ · โปรแกรมใหญ่ๆ (Go/Rust/Electron) มักมีชื่อ API
    # อย่าง WriteProcessMemory ติดมาในไฟล์เฉยๆ โดยไม่ได้ใช้ทำอะไรร้าย → ลดน้ำหนักคะแนนจาก string ลง
    if sig_ok:
        res["score"] = int(res["score"] * 0.25)
        if res["raw_score"] >= 40:
            res["verdict"] = (f"มีลายเซ็นถูกต้องจาก {signer} — แต่ข้างในมีคำที่มักเจอในโปรแกรมไม่ดีด้วย "
                              "(โปรแกรมใหญ่ๆ มักมีติดมาเฉยๆ) ถ้าไม่ได้โหลดจากเว็บทางการ ลองเช็ค VirusTotal")
            res["level"] = "yellow"
        elif res["raw_score"] >= 15:
            res["verdict"], res["level"] = f"ดูปลอดภัย (มีลายเซ็นจาก {signer}) — มีคำน่าสงสัยเล็กน้อยแต่ไม่ผิดปกติ", "green"
        else:
            res["verdict"], res["level"] = f"ดูปลอดภัย (มีลายเซ็นจาก {signer})", "green"
    elif res["score"] >= 40:
        res["verdict"], res["level"] = "อันตราย — อย่ารัน", "red"
    elif res["score"] >= 15:
        res["verdict"], res["level"] = "น่าสงสัย — เช็ค VirusTotal ก่อน", "orange"
    elif packed_blind:
        res["verdict"], res["level"] = "มองข้างในไม่เห็น (ถูกแพ็ค) + ไม่มีลายเซ็น — เช็ค VirusTotal ก่อนรัน", "orange"
    else:
        res["verdict"], res["level"] = "ไม่พบอะไรน่าสงสัย แต่ไม่มีลายเซ็น — ระวังไว้ก่อน", "yellow"
    if res["signature"]["status"] not in ("Valid", "NotSigned", "", None):
        res["verdict"] = f"⚠ ลายเซ็นมีปัญหา ({res['signature']['status']}) — " + res["verdict"]
        res["level"] = "red" if res["level"] in ("green", "yellow") else res["level"]
    return res


def virustotal_url(sha):
    return f"https://www.virustotal.com/gui/file/{sha}"
