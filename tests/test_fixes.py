"""เช็คการแก้จากรายงาน audit 2026-10-17 — รัน: python tests/test_fixes.py (ไม่แตะไฟล์จริงของผู้ใช้)"""
import json
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config, launcher, updater  # noqa: E402

# 1) write_json: เขียนสำเร็จ + ไม่ทิ้งไฟล์ .tmp + หลายเธรดพร้อมกันไฟล์ยังเป็น JSON ที่อ่านได้
d = tempfile.mkdtemp()
p = os.path.join(d, "s.json")
config.write_json(p, {"a": "ไทย"}, indent=2)
assert json.load(open(p, encoding="utf-8")) == {"a": "ไทย"}
ts = [threading.Thread(target=lambda i=i: [config.write_json(p, {"n": i, "pad": "x" * 5000}) for _ in range(50)]) for i in range(8)]
[t.start() for t in ts]
[t.join() for t in ts]
assert "n" in json.load(open(p, encoding="utf-8")) and os.listdir(d) == ["s.json"]
# ถ้าเขียนพังกลางทาง (json.dump ล้ม) ไฟล์เดิมต้องยังอยู่ครบ
try:
    config.write_json(p, {"bad": object()})
except TypeError:
    pass
assert "n" in json.load(open(p, encoding="utf-8"))

# 3) updater: release ไม่มี SHA256 ต้องไม่ติดตั้ง (เช็คก่อนแตะเน็ต)
try:
    updater.download("https://invalid.example/x.exe", os.path.join(d, "x.exe"), 10, None)
    raise SystemExit("FAIL: download without sha256 should raise")
except RuntimeError as e:
    assert "SHA256" in str(e)

# 8) launcher.clean_ids: รับของจริง ปฏิเสธพารามิเตอร์แปลก
assert launcher.clean_ids(1818, None) == ("1818", None)
assert launcher.clean_ids("18852831741", "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE") == ("18852831741", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
for bad in [("1&launchData=abc", None), ("123abc", None), ("", None), (None, None), ("²", None),
            ("123", "x&y=1"), ("123", "short"), ("123", "g" * 36)]:
    assert launcher.clean_ids(*bad) is None, bad

# 8b) ด่านจริงใน ipc.handle: ค่าแปลกถูกปฏิเสธก่อนเปิดเกม / ค่าดีถูกส่งต่อแบบ normalize / update ไม่มี SHA256 ตอบ ok=False ทันที
import types  # noqa: E402
from core import ipc  # noqa: E402

calls = []
launcher.launch = lambda p, j=None: calls.append(("launch", p, j))
launcher.launch_best = lambda p, log=None: calls.append(("best", p))
ipc.roblox_pids = lambda: []
app = types.SimpleNamespace(log=lambda s: None, eng=types.SimpleNamespace(rejoining=False, running=True), place_name=str,
                            join_want=None, join_result=None, cfg={})
srv = ipc.CommandServer.__new__(ipc.CommandServer)      # ข้าม __init__ (มันลบคำสั่งค้างใน cmd/ จริง)
srv.app = app


def run(**c):
    return srv.handle({**c, "id": "t", "_direct": True})


for b in [dict(cmd="join", place="1&launchData=x"), dict(cmd="join", place="123", job="zz&y=1"), dict(cmd="launch", place="12ab"),
          dict(cmd="launch", place=""), dict(cmd="launch", place="5", job="x")]:
    assert run(**b)["ok"] is False, b
assert calls == []
assert run(cmd="join", place=1818, job="AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE")["ok"] and calls[-1] == ("launch", "1818", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
assert run(cmd="launch", place="1818")["ok"] and calls[-1] == ("best", "1818")
updater.check = lambda repo: dict(ver="9.9.9", newer=True, url="u", size=1, sha256=None)
r = run(cmd="update", install=True)
assert r["ok"] is False and "SHA256" in r["msg"], r

print("OK: write_json / updater sha guard / clean_ids / ipc wiring")

# fpscap: release() ระหว่างลูปหยุด-ปลุก ต้องไม่เหลือเธรดค้าง suspend (ปิด Toolkit แล้วเกมค้าง)
import threading as _th, time as _tm  # noqa: E402,E401
from core import fpscap  # noqa: E402
_cnt = {}
def _sus(h): _cnt[h] = _cnt.get(h, 0) + 1; return _cnt[h] - 1
def _res(h): prev = _cnt.get(h, 0); _cnt[h] = max(0, prev - 1); return prev
fpscap.k = type("K", (), {"SuspendThread": staticmethod(_sus), "ResumeThread": staticmethod(_res), "CloseHandle": staticmethod(lambda h: 1)})()
_c = fpscap.FpsCapper(lambda *a: None, {"fps_cap_on": True, "fps_cap": 5})
_c.should_cap = lambda: not _c.paused
_c.refresh_handles = lambda: None
_c.handles = [11, 22]
_th.Thread(target=_c.run, daemon=True).start()
for _ in range(20):
    _tm.sleep(0.07)
    _c.paused = True
    _c.release()
    assert all(v == 0 for v in _cnt.values()), f"เธรดค้าง suspend: {_cnt}"
    _c.handles, _c.paused = [11, 22], False
print("OK: fpscap release leaves nothing suspended")

# macro: ปุ่มที่กดค้างต้องถูกปล่อยตอนจบ (ไม่ส่งอินพุตจริง — แทน _send)
from core import macro  # noqa: E402
_sent = []
macro._send = lambda i: _sent.append((i.u.ki.wVk, bool(i.u.ki.dwFlags & 2)))
macro.roblox_windows = lambda *a: {1}
macro.u = type("U", (), {"GetForegroundWindow": staticmethod(lambda: 1)})()
_p = macro.Player([(0, "key", 0x57, False)], lambda m: None, lambda n: None)
_p.run()
assert (0x57, False) in _sent and _sent[-1] == (0x57, True), _sent
print("OK: macro releases held keys")

# sysmon: เริ่มใหม่ตอน OneDrive ดับ + สวิตช์เปิด → ถือว่าเราปิดไว้ (เปิดคืนได้)
from core import sysmon  # noqa: E402
sysmon.onedrive_running = lambda: False
assert sysmon.SysMonitor(lambda *a: None, lambda *a: None, {"pause_onedrive": True})._od_paused is True
assert sysmon.SysMonitor(lambda *a: None, lambda *a: None, {})._od_paused is False
print("OK: onedrive resume after restart")
