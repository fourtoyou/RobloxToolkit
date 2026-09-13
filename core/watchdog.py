"""Watchdog: ตรวจ Roblox ค้าง (หน้าต่างไม่ตอบสนอง) นานเกินกำหนด → ปิดแล้วเปิดกลับเซิร์ฟเดิม
และตรวจว่า Roblox ปิดไป (เพื่อจบเซสชัน/สรุป)"""
import ctypes
import threading
import time

from .win import hwnd_pid, idle_seconds, kill_pid, proc_mem_mb, proc_start_epoch, procs_named, roblox_pids, roblox_windows, u

u.IsHungAppWindow.restype = ctypes.c_bool


class Watchdog(threading.Thread):
    def __init__(self, engine, log, on_event, hang_seconds=30):
        super().__init__(daemon=True)
        self.eng = engine
        self.log = log
        self.emit = on_event
        self.hang_seconds = hang_seconds
        self.enabled = True
        self.hung_since = {}
        self.had_roblox = False
        self.last_fix = 0
        self.crash_relaunch = True
        self.last_zombie_check = 0
        self.zombies_killed = 0

    def run(self):
        while True:
            try:
                self.tick()
            except Exception as e:
                self.log(f"watchdog: {e}")
            time.sleep(5)

    def zombie_check(self, max_age=300):
        """RobloxPlayerBeta.exe ที่ไม่มีหน้าต่างเลยนานเกิน max_age วิ = ค้างเบื้องหลัง (กิน RAM เป็น GB ได้) → ปิดทิ้ง"""
        if not self.enabled or self.eng.rejoining or time.time() - self.last_zombie_check < 60:
            return
        self.last_zombie_check = time.time()
        with_window = roblox_pids()
        for pid in procs_named("RobloxPlayerBeta.exe"):
            if pid in with_window:
                continue
            st = proc_start_epoch(pid)
            if st is None or time.time() - st < max_age:
                continue
            mb = proc_mem_mb(pid)
            kill_pid(pid)
            self.zombies_killed += 1
            self.log(f"🧹 ปิด Roblox ที่ค้างเบื้องหลัง (pid {pid} ไม่มีหน้าต่างมา {int((time.time() - st) / 60)} นาที กิน RAM {mb:.0f} MB)")
            self.emit("zombie", {"pid": pid, "mb": mb, "minutes": int((time.time() - st) / 60)})

    def tick(self):
        self.zombie_check()
        wins = roblox_windows(True) + list(self.eng.hidden)
        wins = [h for h in wins if u.IsWindow(h)]
        # Roblox ปิดไปทั้งหมด → แจ้งจบเซสชัน
        if self.had_roblox and not wins:
            self.had_roblox = False
            eng = self.eng
            # หายไปโดยไม่มี "Sending disconnect" ใน log + คนไม่ได้แตะเครื่อง + Anti-AFK ทำงานอยู่ → น่าจะแครช ไม่ใช่กดปิดเอง
            crashed = (eng.running and eng.session_start is not None and time.time() - eng.last_disconnect_at > 20
                       and idle_seconds() >= 8 and eng.last_place and not eng.rejoining)
            eng.session_start = None
            self.emit("roblox_closed", {"crashed": bool(crashed)})
            if crashed and self.crash_relaunch and eng.auto_rejoin and time.time() - self.last_fix > 120:
                self.last_fix = time.time()
                self.log("⚠ Roblox ปิดตัวเองระหว่าง Anti-AFK (แครช?) → เปิดกลับเซิร์ฟเดิม")
                self.emit("crash", {"place": eng.last_place})
                eng.rejoining = True
                threading.Thread(target=eng.rejoin, args=(0, eng.last_place, eng.last_job, None), kwargs={"force": True}, daemon=True).start()
            return
        elif wins:
            self.had_roblox = True
        if not self.enabled or self.eng.rejoining:
            return
        now = time.time()
        for h in wins:
            if u.IsHungAppWindow(h):
                self.hung_since.setdefault(h, now)
                dur = now - self.hung_since[h]
                if dur >= self.hang_seconds and now - self.last_fix > 120:
                    self.last_fix = now
                    self.log(f"⚠ Roblox ค้างมา {int(dur)} วิ → ปิดแล้วเปิดกลับเซิร์ฟเดิม")
                    self.emit("hang", {"seconds": int(dur)})
                    place, job = self.eng.last_place, self.eng.last_job
                    self.hung_since.pop(h, None)
                    if place:
                        self.eng.rejoining = True
                        threading.Thread(target=self.eng.rejoin, args=(0, place, job, None), kwargs={"force": True}, daemon=True).start()
                    else:
                        from .win import kill_pid
                        kill_pid(hwnd_pid(h))
            else:
                self.hung_since.pop(h, None)
