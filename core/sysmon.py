"""มอนิเตอร์เครื่อง — CPU / RAM / GPU / อุณหภูมิ / ดิสก์ / แบต + เตือนเมื่อร้อนหรือแรมจะเต็ม

ทำไมต้องมี: เครื่องนี้เปิด Anti-AFK ทิ้งไว้ทีละ 10+ ชั่วโมง ถ้า GPU ร้อนค้างหรือแรมเต็ม
Roblox จะแครชหรือเครื่องหน่วงโดยไม่มีใครรู้ ตัวนี้เฝ้าให้แล้วเด้งเตือน

อ่านอะไรได้จริงบนเครื่องนี้ (เช็คมาแล้ว):
- CPU% / RAM / ดิสก์ / แบต  -> psutil
- GPU: การใช้งาน, อุณหภูมิ, VRAM, ไฟที่กิน -> nvidia-smi
- อุณหภูมิ CPU: อ่านไม่ได้ (โน้ตบุ๊กผู้บริโภคทั่วไปไม่เปิดให้ WMI อ่าน) จึงไม่แสดง
"""
import os
import subprocess
import threading
import time
from collections import deque

from . import config

NO_WINDOW = 0x08000000
GPU_Q = "utilization.gpu,temperature.gpu,memory.used,memory.total,power.draw,clocks.sm"


def gpu_read():
    """คืน dict ของ GPU หรือ None ถ้าไม่มีการ์ด NVIDIA / อ่านไม่ได้"""
    try:
        out = subprocess.run(["nvidia-smi", f"--query-gpu={GPU_Q}", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=6, creationflags=NO_WINDOW).stdout.strip()
        util, temp, used, total, power, clock = [x.strip() for x in out.splitlines()[0].split(",")]

        def num(v):
            try:
                return float(v)
            except ValueError:
                return None
        return {"util": num(util), "temp": num(temp), "mem_used": num(used), "mem_total": num(total),
                "power": num(power), "clock": num(clock)}
    except Exception:
        return None


def top_processes(n=6, by="ram"):
    """โปรเซสที่กินทรัพยากรมากสุด — [(ชื่อ, MB, cpu%)]"""
    import psutil
    rows = []
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            rows.append([p.info["name"] or "?", p.info["memory_info"].rss / 1048576, p.pid])
        except Exception:
            pass
    rows.sort(key=lambda r: -r[1])
    return rows[:n]


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


def ollama_loaded():
    """โมเดลที่ค้างอยู่ในหน่วยความจำตอนนี้ — [(ชื่อ, ไบต์)] · [] ถ้าไม่มี/Ollama ไม่ได้รัน"""
    try:
        import requests
        d = requests.get(f"{OLLAMA_URL}/api/ps", timeout=4).json()
        return [(m.get("name") or m.get("model"), m.get("size") or 0) for m in d.get("models", [])]
    except Exception:
        return []


def ollama_unload(model):
    """สั่งให้ Ollama คายโมเดลออกจาก VRAM/RAM ทันที (keep_alive=0) — โหลดกลับเองตอนใช้ครั้งหน้า"""
    try:
        import requests
        requests.post(f"{OLLAMA_URL}/api/generate", json={"model": model, "keep_alive": 0}, timeout=15)
        return True
    except Exception:
        return False


def unload_all():
    """คายทุกโมเดล — คืน (จำนวนที่คาย, MB ที่คืนมา)"""
    before = gpu_read() or {}
    models = ollama_loaded()
    n = sum(1 for m, _ in models if ollama_unload(m))
    if n:
        time.sleep(2)
    after = gpu_read() or {}
    freed = (before.get("mem_used") or 0) - (after.get("mem_used") or 0)
    return n, max(0, freed)


class SysMonitor(threading.Thread):
    """เก็บค่าทุก 2 วิ · เก็บย้อนหลัง ~20 นาที · เตือนเมื่อร้อน/แรมตึงติดต่อกันนานพอ"""
    EVERY = 2
    KEEP = 600                       # 600 * 2 วิ = 20 นาที

    def __init__(self, log, on_event, cfg):
        super().__init__(daemon=True)
        self.log, self.emit, self.cfg = log, on_event, cfg
        self.hist = deque(maxlen=self.KEEP)
        self.cur = {}
        self.gpu_ok = True
        self._hot_since = self._ram_since = None
        self._last_alert = {}
        self._game_was = False
        self.freed_mb = 0
        self._net_prev = None            # (t, bytes_sent, bytes_recv) สำหรับคิด Mbps
        self._up_since = None
        self._od_paused = False          # เราเป็นคนหยุด OneDrive ไว้ไหม (จะได้เปิดคืนถูกตัว)

    # ---------- อ่านค่า ----------
    def sample(self):
        import psutil
        vm = psutil.virtual_memory()
        d = {"t": time.time(), "cpu": psutil.cpu_percent(interval=None),
             "ram": vm.percent, "ram_used": vm.used / 2 ** 30, "ram_total": vm.total / 2 ** 30}
        g = gpu_read() if self.gpu_ok else None
        if g is None and self.gpu_ok and not self.hist:
            self.gpu_ok = False      # ไม่มีการ์ด/อ่านไม่ได้ตั้งแต่แรก เลิกเรียกซ้ำ
        if g:
            d.update(gpu=g["util"], gpu_temp=g["temp"], vram=g["mem_used"], vram_total=g["mem_total"],
                     gpu_power=g["power"], gpu_clock=g["clock"])
        try:
            b = psutil.sensors_battery()
            if b:
                d.update(battery=b.percent, plugged=b.power_plugged)
        except Exception:
            pass
        try:
            import shutil
            du = shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
            d.update(disk_free=du.free / 2 ** 30, disk_total=du.total / 2 ** 30)
        except Exception:
            pass
        try:
            io = psutil.net_io_counters()
            now = time.time()
            if self._net_prev:
                dt = max(0.001, now - self._net_prev[0])
                d["up_mbps"] = (io.bytes_sent - self._net_prev[1]) * 8 / dt / 1e6
                d["down_mbps"] = (io.bytes_recv - self._net_prev[2]) * 8 / dt / 1e6
            self._net_prev = (now, io.bytes_sent, io.bytes_recv)
        except Exception:
            pass
        return d

    def run(self):
        while True:
            try:
                self.cur = self.sample()
                self.hist.append(self.cur)
                self.check()
            except Exception as e:
                config.dbg(f"sysmon: {e}")
            time.sleep(self.EVERY)

    # ---------- กราฟ ----------
    def series(self, key, seconds=600):
        since = time.time() - seconds
        return [(r["t"], r.get(key)) for r in self.hist if r["t"] >= since]

    def avg(self, key, seconds=60):
        vals = [v for _, v in self.series(key, seconds) if v is not None]
        return sum(vals) / len(vals) if vals else None

    # ---------- เตือน ----------
    def _alert(self, kind, title, body, level=0xFFC857, cooldown=900):
        if time.time() - self._last_alert.get(kind, 0) < cooldown:
            return
        self._last_alert[kind] = time.time()
        self.emit("sys_alert", {"kind": kind, "title": title, "body": body, "color": level})

    # ---------- เน็ตนิ่งตอนเล่น (เน็ตมือถือ/hotspot: อัปโหลดหนัก = ping พุ่ง) ----------
    def net_tick(self, now):
        from .win import roblox_pids
        in_game = bool(roblox_pids())
        up = self.avg("up_mbps", 20)
        limit = self.cfg.get("upload_alert_mbps", 3) or 3
        if in_game and up is not None and up >= limit:
            self._up_since = self._up_since or now
            if now - self._up_since >= 15:
                hogs = ", ".join(net_hogs()) or "ดูไม่ออก"
                self._alert("upload_hog", f"มีอะไรอัปโหลดอยู่ {up:.1f} Mbps",
                            f"เน็ตมือถือ/hotspot อัปโหลดหนักแล้ว ping จะพุ่ง เกมกระตุก — ตัวที่ต่อเน็ตเยอะสุดตอนนี้: {hogs}", 0xFFC857, cooldown=600)
        else:
            self._up_since = None
        # หยุด OneDrive ตอนเกมเปิด (opt-in) แล้วเปิดคืนตอนเกมปิด
        if self.cfg.get("pause_onedrive"):
            if in_game and not self._od_paused and onedrive_running():
                if onedrive_pause():
                    self._od_paused = True
                    self.log("☁ หยุด OneDrive ชั่วคราวระหว่างเกมเปิด (จะเปิดคืนเมื่อปิดเกม)")
            elif not in_game and self._od_paused:
                onedrive_resume()
                self._od_paused = False
                self.log("☁ เปิด OneDrive กลับแล้ว")
        elif self._od_paused:            # ผู้ใช้ปิดสวิตช์กลางคัน → คืนสภาพ
            onedrive_resume()
            self._od_paused = False

    def game_mode_tick(self):
        """เปิด Roblox = คายโมเดล AI ให้เกมใช้ VRAM เต็มที่ (Ollama โหลดกลับเองตอนบอทต้องใช้)"""
        if not self.cfg.get("game_mode"):
            self._game_was = False
            return
        from .win import roblox_pids
        running = bool(roblox_pids())
        if running and not self._game_was:
            self._game_was = True
            loaded = ollama_loaded()
            if loaded:
                n, freed = unload_all()
                self.freed_mb = freed
                self.log(f"🎮 โหมดเล่นเกม: คายโมเดล AI {n} ตัว คืน VRAM ให้เกม {freed:.0f} MB")
                self.emit("game_mode", {"freed": freed, "models": n})
        elif not running:
            self._game_was = False

    def check(self):
        try:
            self.game_mode_tick()
        except Exception as e:
            config.dbg(f"game_mode: {e}")
        if not self.cfg.get("sys_alerts", True):
            return
        now = time.time()
        temp = self.cur.get("gpu_temp")
        limit = self.cfg.get("gpu_temp_limit", 85)
        if temp is not None and temp >= limit:
            self._hot_since = self._hot_since or now
            if now - self._hot_since >= 120:     # ร้อนค้างเกิน 2 นาทีถึงเตือน กันเด้งตอนโหลดเกม
                self._alert("gpu_hot", f"GPU ร้อน {temp:.0f}°C",
                            f"ร้อนเกิน {limit}°C ติดต่อกัน {int((now - self._hot_since) / 60)} นาที — "
                            "เช็คว่าช่องลมโดนบังไหม หรือลดกราฟิกในเกมลง", 0xFF5D7A)
        else:
            self._hot_since = None
        ram = self.cur.get("ram")
        if ram is not None and ram >= self.cfg.get("ram_limit", 92):
            self._ram_since = self._ram_since or now
            if now - self._ram_since >= 120:
                top = ", ".join(f"{n} {mb / 1024:.1f} GB" for n, mb, _ in top_processes(3))
                self._alert("ram_full", f"แรมเกือบเต็ม {ram:.0f}%",
                            f"ใช้ไป {self.cur['ram_used']:.1f}/{self.cur['ram_total']:.0f} GB · กินเยอะสุด: {top}", 0xFF5D7A)
        else:
            self._ram_since = None
        free = self.cur.get("disk_free")
        if free is not None and free < 5:
            self._alert("disk_low", f"ดิสก์เหลือน้อย {free:.1f} GB",
                        "เหลือไม่ถึง 5 GB — Roblox อาจโหลดเกมไม่ได้ ลองล้าง log ในหน้าสุขภาพระบบ", 0xFF5D7A, cooldown=7200)
        self.net_tick(now)


# ---------- ตัวช่วยเน็ต ----------
def net_hogs(n=3):
    """โปรเซสที่ต่อเน็ตเยอะสุด (ประมาณการตัวต้องสงสัยเวลาอัปโหลดหนัก — Windows ไม่บอก bandwidth ต่อโปรเซส)"""
    import psutil
    from collections import Counter
    c = Counter()
    try:
        for con in psutil.net_connections(kind="inet"):
            if con.status == "ESTABLISHED" and con.pid:
                c[con.pid] += 1
    except Exception:
        return []
    out = []
    for pid, cnt in c.most_common(12):
        try:
            name = psutil.Process(pid).name()
        except Exception:
            continue
        if name.lower() in ("robloxplayerbeta.exe", "system", "svchost.exe", "robloxtoolkit.exe"):
            continue
        out.append(f"{name} ({cnt})")
        if len(out) >= n:
            break
    return out


def onedrive_exe():
    for p in (os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Microsoft OneDrive", "OneDrive.exe"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "OneDrive", "OneDrive.exe")):
        if os.path.exists(p):
            return p
    return None


def onedrive_running():
    import psutil
    return any(p.info["name"] and p.info["name"].lower() == "onedrive.exe" for p in psutil.process_iter(["name"]))


def onedrive_pause():
    """OneDrive ไม่มีคำสั่ง pause จากข้างนอก — วิธีเดียวที่ปลอดภัยคือสั่งปิดแบบสุภาพ (/shutdown) แล้วเปิดคืนทีหลัง"""
    exe = onedrive_exe()
    if not exe:
        return False
    try:
        subprocess.Popen([exe, "/shutdown"], creationflags=NO_WINDOW)
        return True
    except OSError:
        return False


def onedrive_resume():
    exe = onedrive_exe()
    if exe:
        try:
            subprocess.Popen([exe, "/background"], creationflags=NO_WINDOW)
        except OSError:
            pass
