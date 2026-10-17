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
