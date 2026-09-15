"""ค่าตั้ง + path กลางของโปรแกรม"""
import json
import os
import time
import sys

APP_NAME = "RobloxToolkit"
VERSION = "2.17.1"
DEFAULT_REPO = "fourtoyou/RobloxToolkit"   # GitHub ที่ปล่อย Release (อัปเดตอัตโนมัติอ่านจากที่นี่)
LOCAL = os.environ.get("LOCALAPPDATA", ".")
# เก็บข้อมูลไว้นอก AppData\Local เพราะ Python จาก Microsoft Store จำลอง (virtualize) โฟลเดอร์นั้น
# ทำให้ Discord bot (รันด้วย Python) กับ Toolkit (.exe) มองเห็นไฟล์คนละชุด
DATA_DIR = os.path.join(os.environ.get("USERPROFILE", LOCAL), ".robloxtoolkit")
OLD_DATA_DIR = os.path.join(LOCAL, APP_NAME)


def _migrate():
    """ย้ายข้อมูลจากที่เก่า (%LOCALAPPDATA%/RobloxToolkit) มาที่ใหม่ครั้งเดียว"""
    try:
        if os.path.isdir(OLD_DATA_DIR) and not os.path.exists(os.path.join(DATA_DIR, "settings.json")):
            import shutil
            os.makedirs(DATA_DIR, exist_ok=True)
            for name in os.listdir(OLD_DATA_DIR):
                src = os.path.join(OLD_DATA_DIR, name)
                dst = os.path.join(DATA_DIR, name)
                if name in ("cmd", "res") or os.path.exists(dst):
                    continue
                (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)
    except Exception:
        pass


_migrate()
CFG_PATH = os.path.join(DATA_DIR, "settings.json")
STATUS_PATH = os.path.join(DATA_DIR, "status.json")      # ให้ Discord bot / โปรแกรมอื่นอ่าน
CACHE_PATH = os.path.join(DATA_DIR, "cache.json")        # ชื่อเกม, สถิติที่ parse แล้ว
# Roblox ปกติ/Bloxstrap เขียน log ที่ Roblox\logs · เวอร์ชัน Microsoft Store (RobloxGDK) เขียนที่ RobloxPCGDK\logs
LOG_DIRS = [os.path.join(LOCAL, "Roblox", "logs"), os.path.join(LOCAL, "RobloxPCGDK", "logs")]
BLOXSTRAP_DIR = os.path.join(LOCAL, "Bloxstrap")

DEFAULTS = {
    "delay": 600, "action": "jump", "invisible": True, "immediate": True,
    "wait_idle": True, "auto_rejoin": True, "top": False,
    "webhook_url": "", "notify_disconnect": True, "notify_rejoin": True,
    "show_server_region": True, "autostart": False, "start_afk_on_launch": False,
    "update_repo": DEFAULT_REPO,
    "auto_update": True, "update_checked": 0,
    "region_probe": None,
    "upload_alert_mbps": 3, "pause_onedrive": False, "bufferbloat": None,   # เน็ตนิ่งตอนเล่น (hotspot)   # ผลวัดภูมิภาคครั้งล่าสุด (ไว้เทียบก่อน-หลังลอง VPN/GPN)   # เช็ค release ใหม่เองวันละครั้ง
    "watchdog": True, "hang_seconds": 30, "notify_recap": True,
    "overlay": False, "overlay_corner": "top-right",
    # ออโต้คลิก
    "click_cps": 10, "click_mode": "mouse", "click_button": "left", "click_key": "e", "click_vk": 0x45,
    "click_type": 1,                       # 1=คลิกเดี่ยว 2=ดับเบิล 3=ทริปเปิล
    "click_trigger": "toggle",             # toggle = กด F6 ติด-ดับ · hold = กดปุ่มค้างถึงจะคลิก
    "click_hold_key": "mouse1", "click_hold_vk": 0x01,
    "click_interval_ms": 0,                # >0 = ระบุช่วงเวลาเองเป็นมิลลิวินาที (ชนะค่า cps)
    "click_rand_min": 85, "click_rand_max": 130,   # สุ่มช่วงเวลาเป็น % ของจังหวะฐาน
    "click_points": [], "click_restore_cursor": True,
    "click_burst": 0, "click_burst_pause": 1.0,
    "macro_loops": 1, "macro_speed": 1.0, "macro_only_roblox": True,
    "last_preset": "", "seen_home": False,
    # FastFlag — ff_level/ff_api/ff_extras คือแบบใหม่ · ff_presets/ff_fps เก็บไว้ให้ migrate ของเก่า
    "ff_level": "ปิด", "ff_api": "อัตโนมัติ", "ff_extras": [], "ff_priority": False,
    "ff_presets": [], "ff_fps": "ไม่ตั้ง", "ff_custom": "", "ff_auto": True, "ff_migrated": False,
    "bridge_tokens": [],   # token ของส่วนขยาย Chrome ที่จับคู่แล้ว (core/bridge.py)
    "schedule": [],   # ตารางเวลาทำซ้ำทุกวัน [{"time":"23:00","action":"เริ่ม Anti-AFK","on":True}]
    "click_only_roblox": True, "click_max_min": 0, "click_max_clicks": 0,
    "sys_alerts": True, "gpu_temp_limit": 85, "ram_limit": 92, "auto_trim_ram": False,
    "fps_cap_on": False, "fps_cap": 5, "fps_unlock_focus": True,   # จำกัด FPS ตอนไม่ได้โฟกัสเกม
    "automute": False,          # ปิดเสียง Roblox ตอน Anti-AFK ทำงาน
    "multi_instance": False,    # เปิด Roblox ได้หลายหน้าต่าง
    "game_mode": False,   # เปิด Roblox เมื่อไหร่ ให้สั่ง Ollama คายโมเดล AI คืน VRAM ให้เกม
    "watch_players": True,    # เฝ้าจำนวนคนในเซิร์ฟที่เล่นอยู่ (ถาม Roblox API ทุก 45 วิ)
    "auto_hop": False,        # คนในเซิร์ฟเยอะเกิน → ย้ายไปเซิร์ฟที่คนน้อยสุด (เฉพาะตอน AFK และไม่ได้แตะเครื่อง)
    "hop_over": 12, "hop_max_ping": 150,
    "crash_relaunch": True,   # Roblox ปิดตัวเอง/แครชระหว่าง Anti-AFK → เปิดกลับเซิร์ฟเดิม
    "adaptive_delay": True,   # โดนเตะ idle ทั้งที่ Anti-AFK ทำงาน → ลดช่วงเวลากดให้เอง
}


def exe_path():
    """path ของตัวโปรแกรม (ถ้า build เป็น exe แล้วคือ .exe ถ้ารันจาก .py คือ python app.py)"""
    if getattr(sys, "frozen", False):
        return sys.executable
    return f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'


def load():
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
    return cfg


def save(cfg):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def write_status(d):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = STATUS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, STATUS_PATH)
    except Exception:
        pass


def load_cache():
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(c):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = CACHE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False)
        os.replace(tmp, CACHE_PATH)
    except Exception:
        pass


DEBUG_LOG = os.path.join(DATA_DIR, "debug.log")


DROPS_PATH = os.path.join(DATA_DIR, "drops.json")     # ประวัติหลุดจากเกม + สาเหตุที่วิเคราะห์ได้


def load_drops():
    try:
        with open(DROPS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def add_drop(d, keep_days=30):
    lst = [x for x in load_drops() if x.get("t", 0) >= time.time() - keep_days * 86400]
    lst.append(d)
    try:
        tmp = DROPS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(lst, f, ensure_ascii=False)
        os.replace(tmp, DROPS_PATH)
    except Exception:
        pass


def dbg(msg):
    """เขียน log ดีบักลงไฟล์ (ใช้หาเหตุที่เกิดเฉพาะตอนเป็น .exe)"""
    try:
        import time as _t
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(_t.strftime("%H:%M:%S ") + str(msg) + chr(10))
    except Exception:
        pass
