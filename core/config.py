"""à¸„à¹ˆà¸²à¸•à¸±à¹‰à¸‡ + path à¸à¸¥à¸²à¸‡à¸‚à¸­à¸‡à¹‚à¸›à¸£à¹à¸à¸£à¸¡"""
import json
import os
import sys

APP_NAME = "RobloxToolkit"
VERSION = "2.9.10"
DEFAULT_REPO = "fourtoyou/RobloxToolkit"   # GitHub à¸—à¸µà¹ˆà¸›à¸¥à¹ˆà¸­à¸¢ Release (à¸­à¸±à¸›à¹€à¸”à¸•à¸­à¸±à¸•à¹‚à¸™à¸¡à¸±à¸•à¸´à¸­à¹ˆà¸²à¸™à¸ˆà¸²à¸à¸—à¸µà¹ˆà¸™à¸µà¹ˆ)
LOCAL = os.environ.get("LOCALAPPDATA", ".")
# à¹€à¸à¹‡à¸šà¸‚à¹‰à¸­à¸¡à¸¹à¸¥à¹„à¸§à¹‰à¸™à¸­à¸ AppData\Local à¹€à¸žà¸£à¸²à¸° Python à¸ˆà¸²à¸ Microsoft Store à¸ˆà¸³à¸¥à¸­à¸‡ (virtualize) à¹‚à¸Ÿà¸¥à¹€à¸”à¸­à¸£à¹Œà¸™à¸±à¹‰à¸™
# à¸—à¸³à¹ƒà¸«à¹‰ Discord bot (à¸£à¸±à¸™à¸”à¹‰à¸§à¸¢ Python) à¸à¸±à¸š Toolkit (.exe) à¸¡à¸­à¸‡à¹€à¸«à¹‡à¸™à¹„à¸Ÿà¸¥à¹Œà¸„à¸™à¸¥à¸°à¸Šà¸¸à¸”
DATA_DIR = os.path.join(os.environ.get("USERPROFILE", LOCAL), ".robloxtoolkit")
OLD_DATA_DIR = os.path.join(LOCAL, APP_NAME)


def _migrate():
    """à¸¢à¹‰à¸²à¸¢à¸‚à¹‰à¸­à¸¡à¸¹à¸¥à¸ˆà¸²à¸à¸—à¸µà¹ˆà¹€à¸à¹ˆà¸² (%LOCALAPPDATA%/RobloxToolkit) à¸¡à¸²à¸—à¸µà¹ˆà¹ƒà¸«à¸¡à¹ˆà¸„à¸£à¸±à¹‰à¸‡à¹€à¸”à¸µà¸¢à¸§"""
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
STATUS_PATH = os.path.join(DATA_DIR, "status.json")      # à¹ƒà¸«à¹‰ Discord bot / à¹‚à¸›à¸£à¹à¸à¸£à¸¡à¸­à¸·à¹ˆà¸™à¸­à¹ˆà¸²à¸™
CACHE_PATH = os.path.join(DATA_DIR, "cache.json")        # à¸Šà¸·à¹ˆà¸­à¹€à¸à¸¡, à¸ªà¸–à¸´à¸•à¸´à¸—à¸µà¹ˆ parse à¹à¸¥à¹‰à¸§
# Roblox à¸›à¸à¸•à¸´/Bloxstrap à¹€à¸‚à¸µà¸¢à¸™ log à¸—à¸µà¹ˆ Roblox\logs Â· à¹€à¸§à¸­à¸£à¹Œà¸Šà¸±à¸™ Microsoft Store (RobloxGDK) à¹€à¸‚à¸µà¸¢à¸™à¸—à¸µà¹ˆ RobloxPCGDK\logs
LOG_DIRS = [os.path.join(LOCAL, "Roblox", "logs"), os.path.join(LOCAL, "RobloxPCGDK", "logs")]
BLOXSTRAP_DIR = os.path.join(LOCAL, "Bloxstrap")

DEFAULTS = {
    "delay": 600, "action": "jump", "invisible": True, "immediate": True,
    "wait_idle": True, "auto_rejoin": True, "top": False,
    "webhook_url": "", "notify_disconnect": True, "notify_rejoin": True,
    "show_server_region": True, "autostart": False, "start_afk_on_launch": False,
    "update_repo": DEFAULT_REPO,
    "auto_update": True, "update_checked": 0,   # à¹€à¸Šà¹‡à¸„ release à¹ƒà¸«à¸¡à¹ˆà¹€à¸­à¸‡à¸§à¸±à¸™à¸¥à¸°à¸„à¸£à¸±à¹‰à¸‡
    "watchdog": True, "hang_seconds": 30, "notify_recap": True,
    "overlay": False, "overlay_corner": "top-right",
    # à¸­à¸­à¹‚à¸•à¹‰à¸„à¸¥à¸´à¸
    "click_cps": 10, "click_mode": "mouse", "click_button": "left", "click_key": "e", "click_vk": 0x45,
    "click_type": 1,                       # 1=à¸„à¸¥à¸´à¸à¹€à¸”à¸µà¹ˆà¸¢à¸§ 2=à¸”à¸±à¸šà¹€à¸šà¸´à¸¥ 3=à¸—à¸£à¸´à¸›à¹€à¸›à¸´à¸¥
    "click_trigger": "toggle",             # toggle = à¸à¸” F6 à¸•à¸´à¸”-à¸”à¸±à¸š Â· hold = à¸à¸”à¸›à¸¸à¹ˆà¸¡à¸„à¹‰à¸²à¸‡à¸–à¸¶à¸‡à¸ˆà¸°à¸„à¸¥à¸´à¸
    "click_hold_key": "mouse1", "click_hold_vk": 0x01,
    "click_interval_ms": 0,                # >0 = à¸£à¸°à¸šà¸¸à¸Šà¹ˆà¸§à¸‡à¹€à¸§à¸¥à¸²à¹€à¸­à¸‡à¹€à¸›à¹‡à¸™à¸¡à¸´à¸¥à¸¥à¸´à¸§à¸´à¸™à¸²à¸—à¸µ (à¸Šà¸™à¸°à¸„à¹ˆà¸² cps)
    "click_rand_min": 85, "click_rand_max": 130,   # à¸ªà¸¸à¹ˆà¸¡à¸Šà¹ˆà¸§à¸‡à¹€à¸§à¸¥à¸²à¹€à¸›à¹‡à¸™ % à¸‚à¸­à¸‡à¸ˆà¸±à¸‡à¸«à¸§à¸°à¸à¸²à¸™
    "click_points": [], "click_restore_cursor": True,
    "click_burst": 0, "click_burst_pause": 1.0,
    "macro_loops": 1, "macro_speed": 1.0, "macro_only_roblox": True,
    "last_preset": "", "seen_home": False,
    # FastFlag â€” ff_level/ff_api/ff_extras à¸„à¸·à¸­à¹à¸šà¸šà¹ƒà¸«à¸¡à¹ˆ Â· ff_presets/ff_fps à¹€à¸à¹‡à¸šà¹„à¸§à¹‰à¹ƒà¸«à¹‰ migrate à¸‚à¸­à¸‡à¹€à¸à¹ˆà¸²
    "ff_level": "à¸›à¸´à¸”", "ff_api": "à¸­à¸±à¸•à¹‚à¸™à¸¡à¸±à¸•à¸´", "ff_extras": [], "ff_priority": False,
    "ff_presets": [], "ff_fps": "à¹„à¸¡à¹ˆà¸•à¸±à¹‰à¸‡", "ff_custom": "", "ff_auto": True, "ff_migrated": False,
    "bridge_tokens": [],   # token à¸‚à¸­à¸‡à¸ªà¹ˆà¸§à¸™à¸‚à¸¢à¸²à¸¢ Chrome à¸—à¸µà¹ˆà¸ˆà¸±à¸šà¸„à¸¹à¹ˆà¹à¸¥à¹‰à¸§ (core/bridge.py)
    "schedule": [],   # à¸•à¸²à¸£à¸²à¸‡à¹€à¸§à¸¥à¸²à¸—à¸³à¸‹à¹‰à¸³à¸—à¸¸à¸à¸§à¸±à¸™ [{"time":"23:00","action":"à¹€à¸£à¸´à¹ˆà¸¡ Anti-AFK","on":True}]
    "click_only_roblox": True, "click_max_min": 0, "click_max_clicks": 0,
    "sys_alerts": True, "gpu_temp_limit": 85, "ram_limit": 92,
    "fps_cap_on": False, "fps_cap": 5, "fps_unlock_focus": True,   # à¸ˆà¸³à¸à¸±à¸” FPS à¸•à¸­à¸™à¹„à¸¡à¹ˆà¹„à¸”à¹‰à¹‚à¸Ÿà¸à¸±à¸ªà¹€à¸à¸¡
    "automute": False,          # à¸›à¸´à¸”à¹€à¸ªà¸µà¸¢à¸‡ Roblox à¸•à¸­à¸™ Anti-AFK à¸—à¸³à¸‡à¸²à¸™
    "multi_instance": False,    # à¹€à¸›à¸´à¸” Roblox à¹„à¸”à¹‰à¸«à¸¥à¸²à¸¢à¸«à¸™à¹‰à¸²à¸•à¹ˆà¸²à¸‡
    "game_mode": False,   # à¹€à¸›à¸´à¸” Roblox à¹€à¸¡à¸·à¹ˆà¸­à¹„à¸«à¸£à¹ˆ à¹ƒà¸«à¹‰à¸ªà¸±à¹ˆà¸‡ Ollama à¸„à¸²à¸¢à¹‚à¸¡à¹€à¸”à¸¥ AI à¸„à¸·à¸™ VRAM à¹ƒà¸«à¹‰à¹€à¸à¸¡
    "watch_players": True,    # à¹€à¸à¹‰à¸²à¸ˆà¸³à¸™à¸§à¸™à¸„à¸™à¹ƒà¸™à¹€à¸‹à¸´à¸£à¹Œà¸Ÿà¸—à¸µà¹ˆà¹€à¸¥à¹ˆà¸™à¸­à¸¢à¸¹à¹ˆ (à¸–à¸²à¸¡ Roblox API à¸—à¸¸à¸ 45 à¸§à¸´)
    "auto_hop": False,        # à¸„à¸™à¹ƒà¸™à¹€à¸‹à¸´à¸£à¹Œà¸Ÿà¹€à¸¢à¸­à¸°à¹€à¸à¸´à¸™ â†’ à¸¢à¹‰à¸²à¸¢à¹„à¸›à¹€à¸‹à¸´à¸£à¹Œà¸Ÿà¸—à¸µà¹ˆà¸„à¸™à¸™à¹‰à¸­à¸¢à¸ªà¸¸à¸” (à¹€à¸‰à¸žà¸²à¸°à¸•à¸­à¸™ AFK à¹à¸¥à¸°à¹„à¸¡à¹ˆà¹„à¸”à¹‰à¹à¸•à¸°à¹€à¸„à¸£à¸·à¹ˆà¸­à¸‡)
    "hop_over": 12, "hop_max_ping": 150,
    "crash_relaunch": True,   # Roblox à¸›à¸´à¸”à¸•à¸±à¸§à¹€à¸­à¸‡/à¹à¸„à¸£à¸Šà¸£à¸°à¸«à¸§à¹ˆà¸²à¸‡ Anti-AFK â†’ à¹€à¸›à¸´à¸”à¸à¸¥à¸±à¸šà¹€à¸‹à¸´à¸£à¹Œà¸Ÿà¹€à¸”à¸´à¸¡
    "adaptive_delay": True,   # à¹‚à¸”à¸™à¹€à¸•à¸° idle à¸—à¸±à¹‰à¸‡à¸—à¸µà¹ˆ Anti-AFK à¸—à¸³à¸‡à¸²à¸™ â†’ à¸¥à¸”à¸Šà¹ˆà¸§à¸‡à¹€à¸§à¸¥à¸²à¸à¸”à¹ƒà¸«à¹‰à¹€à¸­à¸‡
}


def exe_path():
    """path à¸‚à¸­à¸‡à¸•à¸±à¸§à¹‚à¸›à¸£à¹à¸à¸£à¸¡ (à¸–à¹‰à¸² build à¹€à¸›à¹‡à¸™ exe à¹à¸¥à¹‰à¸§à¸„à¸·à¸­ .exe à¸–à¹‰à¸²à¸£à¸±à¸™à¸ˆà¸²à¸ .py à¸„à¸·à¸­ python app.py)"""
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


def dbg(msg):
    """à¹€à¸‚à¸µà¸¢à¸™ log à¸”à¸µà¸šà¸±à¸à¸¥à¸‡à¹„à¸Ÿà¸¥à¹Œ (à¹ƒà¸Šà¹‰à¸«à¸²à¹€à¸«à¸•à¸¸à¸—à¸µà¹ˆà¹€à¸à¸´à¸”à¹€à¸‰à¸žà¸²à¸°à¸•à¸­à¸™à¹€à¸›à¹‡à¸™ .exe)"""
    try:
        import time as _t
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(_t.strftime("%H:%M:%S ") + str(msg) + chr(10))
    except Exception:
        pass
