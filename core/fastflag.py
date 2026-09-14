"""FastFlag — สวิตช์ภายในของ Roblox เอง (ลดกราฟิกเพื่อ FPS)

Roblox อ่านไฟล์นี้ตอนเปิดเกม:
    ...\\Roblox\\Versions\\version-xxxx\\ClientSettings\\ClientAppSettings.json

Bloxstrap/Fishstrap ก็แค่ก๊อปไฟล์นี้ใส่ให้ตอนเปิดเกม — เราเขียนเองตรงๆ ได้เลย
ข้อดีคือทำงานไม่ว่าจะเปิดเกมทางไหน ไม่ต้องพึ่ง launcher (ที่ Roblox ชอบแย่ง handler คืน)

สำคัญ — allowlist (29 ก.ย. 2025):
Roblox ประกาศว่าตัวเกมจะ "อ่านเฉพาะ flag ที่อยู่ในลิสต์อนุญาต" ที่เหลือถูกเมินเงียบๆ
เพราะงั้นลิสต์ FastFlag เก่าๆ ตามเว็บ (ปิดเงา ปิด PostFx ปลดล็อก FPS ปิด telemetry)
ใส่ไปก็ไม่มีผลอะไรเลย — ไฟล์นี้เลยเก็บแต่ตัวที่อยู่ใน allowlist จริง
แล้วมีตัวเช็คเตือนถ้าผู้ใช้พิมพ์ flag ที่ Roblox ปิดไปแล้ว
ที่มา: devforum.roblox.com/t/allowlist-for-local-client-configuration-via-fast-flags/3966569

ข้อจำกัดอื่นที่ต้องบอกผู้ใช้:
- เวอร์ชัน Microsoft Store/Xbox app ใช้ได้เหมือนกัน: เกมอยู่ที่ <drive>:\\XboxGames\\Roblox\\Content (เขียนได้ ไม่ใช่ WindowsApps)
  โปรแกรมเขียนไฟล์ให้ทั้งสองแบบพร้อมกัน — เคยเข้าใจผิดว่าตัว Store ตั้งไม่ได้จนถึง v2.11
- Roblox อัปเดต = โฟลเดอร์เวอร์ชันใหม่ ต้องเขียนใส่ใหม่ (เรามีปุ่ม/เช็คตอนเปิดโปรแกรมให้)
- ต้องปิด-เปิดเกมใหม่ ค่าถึงจะมีผล
- FastFlag ไม่ใช่การโกง เป็นค่าตั้งของ Roblox เอง แต่ใส่มั่วอาจทำเกมพัง (มีปุ่มล้างทิ้ง)
"""
import glob
import json
import os

from . import config

SUB = os.path.join("ClientSettings", "ClientAppSettings.json")

# flag ที่ Roblox ยอมให้ตั้งเองได้ (ประกาศ 29 ก.ย. 2025) — นอกลิสต์นี้ใส่ไปก็ไม่มีผล
ALLOWLIST = {
    # geometry
    "DFIntCSGLevelOfDetailSwitchingDistance",
    "DFIntCSGLevelOfDetailSwitchingDistanceL12",
    "DFIntCSGLevelOfDetailSwitchingDistanceL23",
    "DFIntCSGLevelOfDetailSwitchingDistanceL34",
    # rendering
    "FFlagHandleAltEnterFullscreenManually",
    "DFFlagTextureQualityOverrideEnabled",
    "DFIntTextureQualityOverride",
    "FIntDebugForceMSAASamples",
    "DFFlagDisableDPIScale",
    "FFlagDebugGraphicsPreferD3D11",
    "FFlagDebugSkyGray",
    "DFFlagDebugPauseVoxelizer",
    "DFIntDebugFRMQualityLevelOverride",
    "FIntFRMMaxGrassDistance",
    "FIntFRMMinGrassDistance",
    "FFlagDebugGraphicsPreferVulkan",
    "FFlagDebugGraphicsPreferOpenGL",
    # ui
    "FIntGrassMovementReducedMotionFactor",
}

# flag ดังๆ ที่คนยังก๊อปกันอยู่ แต่ Roblox ปิดไปแล้ว — อธิบายให้ผู้ใช้เข้าใจว่าทำไมไม่เวิร์ก
BLOCKED_WHY = {
    "DFIntTaskSchedulerTargetFps": "ปลดล็อก FPS ทาง FastFlag ถูกปิดแล้ว — ตั้งในเกม Settings → Frame Rate ได้สูงสุด 240",
    "FFlagTaskSchedulerLimitTargetFpsTo240": "ถูกปิดพร้อมกับ flag ปลดล็อก FPS",
    "FFlagDisablePostFx": "ปิดเอฟเฟกต์ภาพทาง FastFlag ไม่ได้แล้ว — ใช้ 'ลดคุณภาพการเรนเดอร์' แทน",
    "FIntRenderShadowIntensity": "ปิดเงาทาง FastFlag ไม่ได้แล้ว — ใช้ 'หยุดคำนวณแสงใหม่' แทน",
    "FFlagDebugSSAOForce": "ไม่อยู่ในลิสต์อนุญาตแล้ว",
    "FFlagGlobalWindActivated": "ไม่อยู่ในลิสต์อนุญาตแล้ว",
    "FFlagGlobalWindRendering": "ไม่อยู่ในลิสต์อนุญาตแล้ว",
    "FFlagDebugDisableTelemetryEphemeralCounter": "ปิด telemetry ทาง FastFlag ไม่ได้แล้ว",
    "FFlagDebugDisableTelemetryV2Event": "ปิด telemetry ทาง FastFlag ไม่ได้แล้ว",
    "FFlagAdServiceEnabled": "ปิดโฆษณาในเกมทาง FastFlag ไม่ได้แล้ว",
    "DFFlagDebugRenderForceTechnologyVoxel": "บังคับระบบแสงแบบเก่าไม่ได้แล้ว",
    "FFlagFontMigration2": "ไม่อยู่ในลิสต์อนุญาตแล้ว",
}

# ---------- ระดับความแรง (ใช้แค่ flag ที่อยู่ใน allowlist) ----------
# (ชื่อ, ไอคอน, สิ่งที่ได้, สิ่งที่เสีย, flags)
LEVELS = [
    ("ปิด", "🚫", "ภาพเดิมของ Roblox 100%", "ไม่มีอะไรเปลี่ยน", {}),
    ("เบา", "🍃", "ลื่นขึ้นหน่อย ภาพยังสวยเหมือนเดิม",
     "เงา/แสงจะไม่อัปเดตตามของที่ขยับ · หญ้าไม่โยกตามลม",
     {"DFFlagDebugPauseVoxelizer": "True",
      "FIntGrassMovementReducedMotionFactor": "0"}),
    ("กลาง", "⚡", "ลื่นขึ้นชัด เหมาะกับเล่นจริงจังทุกวัน",
     "พื้นผิวเบลอลง · ขอบของจะหยัก (ไม่มี AA) · หญ้าเห็นแค่ใกล้ๆ",
     {"DFFlagDebugPauseVoxelizer": "True",
      "FIntGrassMovementReducedMotionFactor": "0",
      "DFFlagTextureQualityOverrideEnabled": "True",
      "DFIntTextureQualityOverride": "2",
      "FIntDebugForceMSAASamples": "1",
      "FIntFRMMaxGrassDistance": "40",
      "FIntFRMMinGrassDistance": "0"}),
    ("แรง", "🔥", "เน้น FPS — เหมาะกับตอนฟาร์มหรือเกมคนเยอะ",
     "ภาพหยาบลงเห็นได้ชัด · ของไกลๆ กลายเป็นทรงหยาบ · ไม่มีหญ้า",
     {"DFFlagDebugPauseVoxelizer": "True",
      "FIntGrassMovementReducedMotionFactor": "0",
      "DFFlagTextureQualityOverrideEnabled": "True",
      "DFIntTextureQualityOverride": "1",
      "FIntDebugForceMSAASamples": "1",
      "FIntFRMMaxGrassDistance": "0",
      "FIntFRMMinGrassDistance": "0",
      "DFIntDebugFRMQualityLevelOverride": "5",
      "DFIntCSGLevelOfDetailSwitchingDistance": "100",
      "DFIntCSGLevelOfDetailSwitchingDistanceL12": "200",
      "DFIntCSGLevelOfDetailSwitchingDistanceL23": "300",
      "DFIntCSGLevelOfDetailSwitchingDistanceL34": "400"}),
    ("โหดสุด", "💀", "ลื่นสุดที่ FastFlag ทำได้ — เอาไว้ทิ้งฟาร์ม/เครื่องอืด",
     "ภาพแตกเลย · ท้องฟ้าเป็นสีเทาเรียบ · เล่นเกมที่ต้องดูรายละเอียดจะลำบาก",
     {"DFFlagDebugPauseVoxelizer": "True",
      "FIntGrassMovementReducedMotionFactor": "0",
      "DFFlagTextureQualityOverrideEnabled": "True",
      "DFIntTextureQualityOverride": "0",
      "FIntDebugForceMSAASamples": "1",
      "FIntFRMMaxGrassDistance": "0",
      "FIntFRMMinGrassDistance": "0",
      "DFIntDebugFRMQualityLevelOverride": "1",
      "FFlagDebugSkyGray": "True",
      "DFIntCSGLevelOfDetailSwitchingDistance": "50",
      "DFIntCSGLevelOfDetailSwitchingDistanceL12": "100",
      "DFIntCSGLevelOfDetailSwitchingDistanceL23": "150",
      "DFIntCSGLevelOfDetailSwitchingDistanceL34": "200"}),
]
LEVEL_NAMES = [lv[0] for lv in LEVELS]

# ---------- ตัวเร่งกราฟิก (API) ----------
APIS = {
    "อัตโนมัติ": {},
    "DirectX 11": {"FFlagDebugGraphicsPreferD3D11": "True"},
    "Vulkan (ลองก่อน — บางเครื่องลื่นขึ้นเยอะ)": {"FFlagDebugGraphicsPreferVulkan": "True"},
    "OpenGL (ทางเลือกสุดท้าย)": {"FFlagDebugGraphicsPreferOpenGL": "True"},
}
API_NAMES = list(APIS)

# ---------- สวิตช์เสริม ----------
# key -> (ชื่อ, คำอธิบาย, flags)
EXTRAS = {
    "sky": ("ท้องฟ้าเรียบ", "เอา skybox ออก เหลือสีเทา — ได้ FPS เพิ่มอีกนิด ภาพจะดูโล่งๆ",
            {"FFlagDebugSkyGray": "True"}),
    "nograss": ("ปิดหญ้าทั้งหมด", "เกมที่มีทุ่งหญ้าเยอะ (ฟาร์ม/เอาชีวิตรอด) จะลื่นขึ้นชัด",
                {"FIntFRMMaxGrassDistance": "0", "FIntFRMMinGrassDistance": "0"}),
    "noaa": ("ปิดลบรอยหยัก (AA)", "ขอบของจะหยักขึ้นแต่การ์ดจอทำงานน้อยลง",
             {"FIntDebugForceMSAASamples": "1"}),
    "sharp": ("ภาพคมเต็มความละเอียดจอ", "ปิดการย่อตามสเกลจอ (Windows 125%) — คมขึ้นแต่หนักขึ้น ไม่ใช่ตัวเพิ่ม FPS",
              {"DFFlagDisableDPIScale": "True"}),
    "altenter": ("แก้ Alt+Enter ค้าง", "ให้ Roblox จัดการสลับเต็มจอเอง แก้อาการจอดำ/ค้างตอนกด Alt+Enter",
                 {"FFlagHandleAltEnterFullscreenManually": "True"}),
}


def store_dirs():
    r"""Roblox จาก Microsoft Store/Xbox app — <drive>:\XboxGames\Roblox\Content (+ โฟลเดอร์ของตัวที่รันอยู่ถ้าไม่ใช่แบบ Versions)"""
    out = []
    for drive in "CDEFGHIJ":
        d = f"{drive}:\\XboxGames\\Roblox\\Content"
        if os.path.exists(os.path.join(d, "RobloxPlayerBeta.exe")):
            out.append(d)
    try:
        rd = running_dir()
        if rd and os.path.exists(os.path.join(rd, "RobloxPlayerBeta.exe")) and "\\Versions\\" not in rd and rd not in out:
            out.append(rd)
    except Exception:
        pass
    return out


def is_store(d):
    return "\\Versions\\" not in (d or "")


def version_dirs():
    """ทุกที่ที่ต้องเขียน FastFlag: โฟลเดอร์ Versions ของตัวปกติ (ใหม่สุดก่อน) + ตัว Store/Xbox"""
    out = []
    for d in glob.glob(os.path.join(config.LOCAL, "Roblox", "Versions", "version-*")):
        if os.path.exists(os.path.join(d, "RobloxPlayerBeta.exe")):
            out.append(d)
    out = sorted(out, key=os.path.getmtime, reverse=True)
    return out + store_dirs()


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
        return 0, "ไม่เจอ Roblox ในเครื่อง (ทั้งตัวปกติและตัว Microsoft Store)"
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
    kinds = sum(1 for d in dirs if is_store(d))
    where = f"{len(dirs) - kinds} ตัวปกติ + {kinds} ตัว Store" if kinds else f"{len(dirs)} เวอร์ชัน"
    return n, (f"เขียน {n}/{len(dirs)} ที่แล้ว ({where}) — ปิด-เปิด Roblox ใหม่ค่าถึงจะมีผล" if n else "เขียนไม่ได้ (สิทธิ์ไม่พอ?)")


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


def ignored(flags):
    """flag ที่ Roblox จะเมิน — คืน [(ชื่อ, เหตุผล)]"""
    out = []
    for k in flags:
        if k in ALLOWLIST:
            continue
        out.append((k, BLOCKED_WHY.get(k, "ไม่อยู่ในลิสต์ที่ Roblox อนุญาตให้ตั้งเอง (ใส่ได้แต่ไม่มีผล)")))
    return out


def level_index(name):
    try:
        return LEVEL_NAMES.index(name)
    except ValueError:
        return 0


def build(level_name, api_name, extra_keys, custom_text):
    """รวมระดับ + API + สวิตช์เสริม + ที่พิมพ์เอง → (flags, error, ที่ถูกเมิน)

    ลำดับทับกัน: ระดับ → API → สวิตช์เสริม → ที่พิมพ์เอง (พิมพ์เองชนะทุกอย่าง)
    """
    flags = {}
    flags.update(LEVELS[level_index(level_name)][4])
    flags.update(APIS.get(api_name, {}))
    for k in (extra_keys or []):
        if k in EXTRAS:
            flags.update(EXTRAS[k][2])
    txt = (custom_text or "").strip()
    if txt:
        try:
            extra = json.loads(txt)
            if not isinstance(extra, dict):
                return flags, 'ช่องพิมพ์เองต้องเป็น JSON แบบ { "ชื่อflag": "ค่า" }', ignored(flags)
            flags.update({k: str(v) for k, v in extra.items()})
        except json.JSONDecodeError as e:
            return flags, f"JSON ในช่องพิมพ์เองผิด: {e.msg} (บรรทัด {e.lineno})", ignored(flags)
    return flags, None, ignored(flags)


def migrate(cfg):
    """ย้ายค่าตั้งแบบเก่า (ff_presets/ff_fps) มาเป็นระดับ 1-4 ครั้งเดียว"""
    if cfg.get("ff_migrated"):
        return False
    old = cfg.get("ff_presets") or []
    if old:
        cfg["ff_level"] = "แรง" if any("เร็วสุด" in o for o in old) else "เบา"
    cfg["ff_migrated"] = True
    return bool(old)
