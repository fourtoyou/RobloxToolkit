"""ตารางเวลา — สั่งให้ทำอะไรซ้ำทุกวันตามเวลาที่ตั้ง

ต่างจาก "ตั้งเวลา" ในหน้า Anti-AFK ตรงที่อันนั้นนับถอยหลังครั้งเดียวแล้วจบ
อันนี้ทำซ้ำทุกวันจนกว่าจะลบทิ้ง เช่น 23:00 เริ่ม Anti-AFK · 07:00 ปิด Roblox

เก็บใน settings.json เป็น [{"time": "23:00", "action": "...", "on": true}]
"""
import threading
import time
from datetime import datetime

from . import config

ACTIONS = ("เริ่ม Anti-AFK", "หยุด Anti-AFK", "เปิดเกมล่าสุด", "รีเซ็ตตัวละคร", "ย้ายไปเซิร์ฟเงียบ",
           "ปิด Roblox", "ปิด Roblox + Sleep เครื่อง", "ปิดเครื่อง")


def valid_time(txt):
    """รับ '23:00' / '2300' / '9:5' → คืน 'HH:MM' หรือ None"""
    t = (txt or "").strip().replace(".", ":")
    if ":" not in t and t.isdigit() and len(t) in (3, 4):
        t = t[:-2] + ":" + t[-2:]
    try:
        h, m = t.split(":")
        h, m = int(h), int(m)
        if 0 <= h < 24 and 0 <= m < 60:
            return f"{h:02d}:{m:02d}"
    except ValueError:
        pass
    return None


class Scheduler(threading.Thread):
    """เช็คทุก 20 วิ · ยิงงานเมื่อถึงนาทีที่ตั้งไว้ (กันยิงซ้ำในนาทีเดียวกัน)"""

    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.fired = {}          # "index|YYYY-MM-DD HH:MM" -> True

    def jobs(self):
        return self.app.cfg.get("schedule") or []

    def run(self):
        while True:
            try:
                self.tick()
            except Exception as e:
                config.dbg(f"scheduler: {e}")
            time.sleep(20)

    def tick(self):
        now = datetime.now()
        stamp = now.strftime("%Y-%m-%d %H:%M")
        for i, job in enumerate(self.jobs()):
            if not job.get("on", True) or job.get("time") != now.strftime("%H:%M"):
                continue
            key = f"{i}|{stamp}"
            if self.fired.get(key):
                continue
            self.fired[key] = True
            if len(self.fired) > 200:
                self.fired = {key: True}
            self.app.ui(lambda j=job: self.app.run_scheduled(j))

    def next_job(self):
        """งานถัดไปที่จะทำ — (เวลา, สิ่งที่ทำ, อีกกี่นาที) หรือ None"""
        now = datetime.now()
        best = None
        for job in self.jobs():
            if not job.get("on", True):
                continue
            t = valid_time(job.get("time"))
            if not t:
                continue
            h, m = (int(x) for x in t.split(":"))
            mins = (h * 60 + m) - (now.hour * 60 + now.minute)
            if mins <= 0:
                mins += 1440          # เลยเวลาวันนี้แล้ว → รอบพรุ่งนี้
            if best is None or mins < best[2]:
                best = (t, job.get("action"), mins)
        return best
