"""วัดคุณภาพเน็ตต่อเนื่อง: gateway (เร้าเตอร์) / 1.1.1.1 (อินเทอร์เน็ต) / roblox.com
เซิร์ฟเกม Roblox บล็อก ICMP เลยวัดตรงไม่ได้ — ใช้ 3 จุดนี้แยกว่าปัญหาอยู่ที่ Wi-Fi, ISP หรือปลายทาง"""
import collections
import socket
import threading
import time

from .win import default_gateway, ping

TARGETS = [("เร้าเตอร์", None), ("อินเทอร์เน็ต", "1.1.1.1"), ("roblox.com", "www.roblox.com")]
KEEP = 300  # เก็บ 300 จุด (5 นาทีที่ 1 วิ/จุด)


class NetMonitor(threading.Thread):
    def __init__(self, interval=1.0):
        super().__init__(daemon=True)
        self.interval = interval
        self.hist = {name: collections.deque(maxlen=KEEP) for name, _ in TARGETS}
        self.ips = {}
        self.events = collections.deque(maxlen=200)   # (time, text) ช่วงที่แพ็กเก็ตหาย
        self.server = None
        self.server_region = None
        self.enabled = True
        self._resolve()

    def _resolve(self):
        gw = default_gateway()
        self.ips["เร้าเตอร์"] = gw
        self.ips["อินเทอร์เน็ต"] = "1.1.1.1"
        try:
            self.ips["roblox.com"] = socket.gethostbyname("www.roblox.com")
        except Exception:
            self.ips["roblox.com"] = None

    def run(self):
        bad_since = None
        n = 0
        while True:
            if not self.enabled:
                time.sleep(1)
                continue
            n += 1
            if n % 300 == 0:
                self._resolve()
            lost_all = True
            for name, _ in TARGETS:
                ip = self.ips.get(name)
                rtt = ping(ip, 900) if ip else None
                self.hist[name].append((time.time(), rtt))
                if rtt is not None and name != "เร้าเตอร์":
                    lost_all = False
            if lost_all and self.ips.get("อินเทอร์เน็ต"):
                if bad_since is None:
                    bad_since = time.time()
            elif bad_since is not None:
                dur = time.time() - bad_since
                if dur >= 3:
                    self.events.appendleft((bad_since, f"เน็ตหลุด {int(dur)} วิ"))
                bad_since = None
            time.sleep(self.interval)

    def stats(self, name, window=60):
        pts = [r for t, r in self.hist[name] if t >= time.time() - window]
        if not pts:
            return None
        ok = [r for r in pts if r is not None]
        loss = 100 * (1 - len(ok) / len(pts))
        if not ok:
            return {"avg": None, "max": None, "loss": loss, "n": len(pts)}
        return {"avg": sum(ok) / len(ok), "max": max(ok), "min": min(ok), "loss": loss, "n": len(pts),
                "jitter": (sum(abs(ok[i] - ok[i - 1]) for i in range(1, len(ok))) / max(1, len(ok) - 1))}

    def series(self, name, window=120):
        return [(t, r) for t, r in self.hist[name] if t >= time.time() - window]

    def set_server(self, ip, port, lookup_region=True):
        self.server = (ip, port)
        self.server_region = None
        if lookup_region:
            threading.Thread(target=self._region, args=(ip,), daemon=True).start()

    def _region(self, ip):
        # วิธีเดียวกับ Bloxstrap (ipinfo.io) — ส่งแค่ IP ของเซิร์ฟเกม ไม่ใช่ IP เรา
        try:
            import requests
            d = requests.get(f"https://ipinfo.io/{ip}/json", timeout=6).json()
            self.server_region = f"{d.get('city', '?')}, {d.get('country', '?')}"
        except Exception:
            self.server_region = "ไม่ทราบ"

    def verdict(self):
        """สรุปเป็นภาษาคน"""
        r = self.stats("เร้าเตอร์", 60)
        i = self.stats("อินเทอร์เน็ต", 60)
        if not i:
            return "กำลังวัด...", "gray"
        if i["loss"] >= 50:
            if r and r["loss"] < 10:
                return "เน็ตบ้านออกอินเทอร์เน็ตไม่ได้ (เร้าเตอร์ตอบ แต่ข้างนอกไม่ตอบ)", "red"
            return "หลุดจากเร้าเตอร์ (Wi-Fi/สาย)", "red"
        if i["loss"] >= 5 or (r and r["loss"] >= 5):
            return f"แพ็กเก็ตหาย {i['loss']:.0f}% — เล่นแล้วอาจกระตุก/หลุด", "orange"
        if r and r["avg"] and r["avg"] > 30:
            return f"Wi-Fi ช้า (ถึงเร้าเตอร์ {r['avg']:.0f} ms) ลองย้ายใกล้เร้าเตอร์/ใช้สาย", "orange"
        if i["avg"] and i["avg"] > 120:
            return f"อินเทอร์เน็ตช้า ({i['avg']:.0f} ms)", "orange"
        return f"เน็ตปกติ ({i['avg']:.0f} ms, jitter {i.get('jitter', 0):.0f} ms)", "green"
