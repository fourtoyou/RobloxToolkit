"""FastFlag — สวิตช์ภายในของ Roblox เอง (ปลดล็อก FPS, ลดกราฟิก ฯลฯ)

Roblox อ่านไฟล์นี้ตอนเปิดเกม:
    ...\\Roblox\\Versions\\version-xxxx\\ClientSettings\\ClientAppSettings.json

Bloxstrap/Fishstrap ก็แค่ก๊อปไฟล์นี้ใส่ให้ตอนเปิดเกม — เราเขียนเองตรงๆ ได้เลย
ข้อดีคือทำงานไม่ว่าจะเปิดเกมทางไหน ไม่ต้องพึ่ง launcher (ที่ Roblox ชอบแย่ง handler คืน)

ข้อจำกัดที่ต้องบอกผู้ใช้:
- ใช้ได้กับ Roblox เวอร์ชันปกติเท่านั้น · เวอร์ชัน Microsoft Store/Xbox อยู่ใน WindowsApps ซึ่งเขียนไม่ได้
- Roblox อัปเดต = โฟลเดอร์เวอร์ชันใหม่ ต้องเขียนใส่ใหม่ (เรามีปุ่ม/เช็คตอนเปิดโปรแกรมให้)
- ต้องปิด-เปิดเกมใหม่ ค่าถึงจะมีผล
- FastFlag ไม่ใช่การโกง เป็นค่าตั้งของ Roblox เอง แต่ใส่มั่วอาจทำเกมพัง (มีปุ่มล้างทิ้ง)
"""
import glob
import json
import os

from . import config

SUB = os.path.join("ClientSettings", "ClientAppSettings.json")

# ชุดสำเร็จรูป — คัดเฉพาะตัวที่คนใช้กันแพร่หลายและไม่ทำให้เล่นไม่ได้
# (ไม่เอาพวกซ่อน UI / ตัดระยะมองเห็น เพราะทำให้เล่นเกมไม่รู้เรื่อง)
PRESETS = {
    "เร็วสุด (ลดกราฟิกแรง)": {
        "DFIntDebugFRMQualityLevelOverride": "1",
        "FFlagDisablePostFx": "True",
        "FIntRenderShadowIntensity": "0",
        "DFFlagDebugPauseVoxelizer": "True",
        "FIntFRMMaxGrassDistance": "0",
        "FIntFRMMinGrassDistance": "0",
        "DFFlagTextureQualityOverrideEnabled": "True",
        "DFIntTextureQualityOverride": "0",
        "FFlagGlobalWindActivated": "False",
    },
    "ปิดเงาอย่างเดียว (ภาพยังสวย)": {
        "FIntRenderShadowIntensity": "0",
        "DFFlagDebugPauseVoxelizer": "True",
        "FFlagDebugSSAOForce": "False",
    },
    "ปิดโฆษณา + การเก็บข้อมูล": {
        "FFlagDebugDisableTelemetryEphemeralCounter": "True",
        "FFlagDebugDisableTelemetryV2Event": "True",
        "FFlagAdServiceEnabled": "False",
    },
}
FPS_FLAG = "DFIntTaskSchedulerTargetFps"
FPS_CHOICES = ("ไม่ตั้ง", "60", "75", "120", "144", "165", "240", "ไม่จำกัด")


def fps_value(choice):
    if choice == "ไม่จำกัด":
        return "9999"
    return choice if choice.isdigit() else None


def version_dirs():
    """โฟลเดอร์เวอร์ชันของ Roblox ที่เป็นตัวเล่นเกม (มี RobloxPlayerBeta.exe)"""
    out = []
    for d in glob.glob(os.path.join(config.LOCAL, "Roblox", "Versions", "version-*")):
        if os.path.exists(os.path.join(d, "RobloxPlayerBeta.exe")):
            out.append(d)
    return sorted(out, key=os.path.getmtime, reverse=True)


def running_dir():
    """โฟลเดอร์ของ Roblox ที่กำลังเปิดอยู่ (ถ้าเปิดอยู่)"""
    from .win import proc_path, roblox_pids
    for pid in roblox_pids():
        p = proc_path(pid)
        if p:
            return os.path.dirname(p)
    return None


def read(vdir):
    try:
        with open(os.path.join(vdir, SUB), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def current():
    """flag ที่มีผลอยู่จริงตอนนี้ — ดูจากเวอร์ชันที่รันอยู่ก่อน ถ้าไม่ได้รันก็เอาตัวใหม่สุด"""
    d = running_dir()
    if d and os.path.exists(os.path.join(d, SUB)):
        return read(d), d
    for v in version_dirs():
        f = read(v)
        if f:
            return f, v
    vs = version_dirs()
    return {}, (vs[0] if vs else None)


def write(flags):
    """เขียนลงทุกเวอร์ชันที่เจอ (เผื่อ Roblox สลับเวอร์ชัน) — คืน (จำนวนที่เขียนได้, ข้อความ)"""
    dirs = version_dirs()
    if not dirs:
        return 0, "ไม่เจอโฟลเดอร์ Roblox เวอร์ชันปกติ (เวอร์ชัน Microsoft Store ตั้ง FastFlag ไม่ได้)"
    n = 0
    for d in dirs:
        try:
            p = os.path.join(d, SUB)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(flags, f, ensure_ascii=False, indent=2)
            os.replace(tmp, p)
            n += 1
        except OSError as e:
            config.dbg(f"fastflag write {d}: {e}")
    return n, (f"เขียน {n}/{len(dirs)} เวอร์ชันแล้ว — ปิด-เปิด Roblox ใหม่ค่าถึงจะมีผล" if n else "เขียนไม่ได้ (สิทธิ์ไม่พอ?)")


def clear():
    """ลบ FastFlag ทั้งหมดออก (กู้คืนเวลาใส่แล้วเกมพัง)"""
    n = 0
    for d in version_dirs():
        p = os.path.join(d, SUB)
        if os.path.exists(p):
            try:
                os.remove(p)
                n += 1
            except OSError:
                pass
    return n


def build(preset_names, fps_choice, custom_text):
    """รวมชุดที่เลือก + FPS + ที่พิมพ์เอง → dict เดียว (คืน (flags, ข้อความ error))"""
    flags = {}
    for name in preset_names:
        flags.update(PRESETS.get(name, {}))
    v = fps_value(fps_choice)
    if v:
        flags[FPS_FLAG] = v
    txt = (custom_text or "").strip()
    if txt:
        try:
            extra = json.loads(txt)
            if not isinstance(extra, dict):
                return flags, "ช่องพิมพ์เองต้องเป็น JSON แบบ { \"ชื่อflag\": \"ค่า\" }"
            flags.update({k: str(v) for k, v in extra.items()})
        except json.JSONDecodeError as e:
            return flags, f"JSON ในช่องพิมพ์เองผิด: {e.msg} (บรรทัด {e.lineno})"
    return flags, None
