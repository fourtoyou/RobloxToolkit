"""สะพานเชื่อมส่วนขยาย Chrome (Roblox Server Finder) กับ Toolkit — HTTP เล็กๆ บน 127.0.0.1 เท่านั้น

ทำไมไม่ใช้ Native Messaging: ต้องลงทะเบียน registry + ผูกกับ extension ID ที่เปลี่ยนได้
HTTP บนเครื่องตัวเองง่ายกว่าและใช้ได้กับทุกเบราว์เซอร์ แต่ต้องกันเว็บแปลกๆ ยิงมาด้วย:

1. ฟังแค่ 127.0.0.1 (นอกเครื่องเข้าไม่ได้)
2. เช็ค Host header — กัน DNS rebinding (evil.com ที่ชี้มา 127.0.0.1 จะส่ง Host: evil.com)
3. ทุกคำสั่งต้องมี header X-RTK-Token → เบราว์เซอร์จะ preflight (OPTIONS) ก่อนเสมอ
   และเราตอบ CORS ให้เฉพาะ origin chrome-extension:// / moz-extension:// เท่านั้น
   → เว็บธรรมดายิงไม่ผ่านตั้งแต่ preflight
4. token ได้มาจากการ "จับคู่" ด้วยรหัส 6 หลักที่โชว์ในหน้าตั้งค่าของ Toolkit (ครั้งเดียว)
   เก็บใน settings.json → bridge_tokens · ยกเลิกได้จากหน้าตั้งค่า
"""
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config

PORT = 47831
HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
PAIR_TTL = 600            # รหัสจับคู่อยู่ได้ 10 นาที แล้วต้องกดสร้างใหม่


class Bridge(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.code = None
        self.code_at = 0
        self.fails = 0            # ใส่รหัสผิดติดกัน → รหัสเดิมใช้ไม่ได้
        self.server = None
        self.error = None
        self.last_seen = 0        # ครั้งล่าสุดที่ส่วนขยายติดต่อมา
        self.new_code()

    # ---------- จับคู่ ----------
    def new_code(self):
        self.code = f"{secrets.randbelow(900000) + 100000}"
        self.code_at = time.time()
        self.fails = 0
        return self.code

    def code_valid(self):
        return self.code and time.time() - self.code_at < PAIR_TTL and self.fails < 5

    def tokens(self):
        return self.app.cfg.setdefault("bridge_tokens", [])

    def pair(self, code):
        if not self.code_valid() or str(code).strip() != self.code:
            self.fails += 1
            return None
        tok = secrets.token_urlsafe(32)
        self.tokens().append({"token": tok, "at": time.time()})
        config.save(self.app.cfg)
        self.new_code()               # รหัสใช้ได้ครั้งเดียว
        self.app.log("🧩 ส่วนขยาย Chrome จับคู่กับ Toolkit แล้ว")
        return tok

    def unpair_all(self):
        n = len(self.tokens())
        self.app.cfg["bridge_tokens"] = []
        config.save(self.app.cfg)
        return n

    def authed(self, token):
        return bool(token) and any(t.get("token") == token for t in self.tokens())

    # ---------- เซิร์ฟเวอร์ ----------
    def run(self):
        bridge = self

        class H(BaseHTTPRequestHandler):
            server_version = "RobloxToolkit"
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):        # ไม่ต้องพ่นลง console
                pass

            # --- ตัวช่วยตอบ ---
            def cors(self):
                origin = self.headers.get("Origin", "")
                if origin.startswith(("chrome-extension://", "moz-extension://", "edge-extension://")):
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Access-Control-Allow-Headers", "Content-Type, X-RTK-Token")
                    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                    self.send_header("Access-Control-Max-Age", "600")
                    # Chrome ถือว่า 127.0.0.1 เป็น "private network" → preflight ต้องมี header นี้ด้วย
                    self.send_header("Access-Control-Allow-Private-Network", "true")
                    self.send_header("Vary", "Origin")

            def send(self, code, body=None, ctype="application/json; charset=utf-8"):
                data = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8"))
                self.send_response(code)
                self.cors()
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if data:
                    self.wfile.write(data)

            def guard(self):
                """เช็ค Host (กัน DNS rebinding) — คืน False ถ้าไม่ผ่านและตอบไปแล้ว"""
                if self.headers.get("Host", "") not in HOSTS:
                    self.send(403, {"ok": False, "error": "bad host"})
                    return False
                return True

            def body(self):
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > 65536:
                    return {}
                try:
                    return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                except Exception:
                    return {}

            def token_ok(self):
                if bridge.authed(self.headers.get("X-RTK-Token", "")):
                    bridge.last_seen = time.time()
                    return True
                self.send(401, {"ok": False, "error": "unpaired", "msg": "ยังไม่ได้จับคู่กับ Toolkit"})
                return False

            # --- routes ---
            def do_OPTIONS(self):
                if not self.guard():
                    return
                self.send(204)

            def do_GET(self):
                if not self.guard():
                    return
                path = self.path.split("?")[0]
                if path == "/ping":
                    return self.send(200, {"ok": True, "app": "RobloxToolkit", "version": config.VERSION,
                                           "paired": bridge.authed(self.headers.get("X-RTK-Token", ""))})
                if not self.token_ok():
                    return
                if path == "/status":
                    return self.send(200, bridge.status())
                if path == "/screen":
                    png, msg = bridge.screen()
                    if png is None:
                        return self.send(404, {"ok": False, "msg": msg})
                    return self.send(200, png, "image/png")
                self.send(404, {"ok": False, "error": "not found"})

            def do_POST(self):
                if not self.guard():
                    return
                path = self.path.split("?")[0]
                b = self.body()
                if path == "/pair":
                    tok = bridge.pair(b.get("code", ""))
                    if not tok:
                        return self.send(403, {"ok": False, "msg": "รหัสไม่ถูกหรือหมดอายุ — ดูรหัสใหม่ในหน้าตั้งค่าของ Toolkit"})
                    return self.send(200, {"ok": True, "token": tok, "version": config.VERSION})
                if not self.token_ok():
                    return
                if path == "/cmd":
                    if not isinstance(b, dict) or not b.get("cmd"):
                        return self.send(400, {"ok": False, "error": "no cmd"})
                    return self.send(200, bridge.command(b))
                self.send(404, {"ok": False, "error": "not found"})

        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", PORT), H)
            self.server.daemon_threads = True
            config.dbg(f"bridge listening on 127.0.0.1:{PORT}")
            self.server.serve_forever()
        except OSError as e:
            self.error = str(e)
            config.dbg(f"bridge: {e}")

    # ---------- งานจริง ----------
    def status(self):
        """สถานะเดียวกับที่บอทอ่านจาก status.json + log ท้ายๆ"""
        try:
            with open(config.STATUS_PATH, encoding="utf-8") as f:
                st = json.load(f)
        except Exception:
            st = {}
        st["ok"] = True
        st["log"] = list(self.app.log_lines)[-12:]
        st["version"] = config.VERSION
        return st

    def screen(self):
        from .ipc import grab_window
        from .win import roblox_windows, u
        import io
        eng = self.app.eng
        wins = roblox_windows(True) + [h for h in eng.hidden if u.IsWindow(h)]
        if not wins:
            return None, "ไม่เจอหน้าต่าง Roblox"
        img, msg = grab_window(wins[0])
        if img is None:
            return None, msg
        if img.width > 960:
            img = img.resize((960, int(img.height * 960 / img.width)))
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        return buf.getvalue(), ""

    def command(self, b):
        """ส่งต่อให้ตัวจัดการคำสั่งเดียวกับ Discord bot (ipc.handle) แต่ไม่เขียนไฟล์"""
        cmd = dict(b)
        cmd["id"] = "br-" + secrets.token_hex(4)
        cmd["_direct"] = True
        cmd["_from"] = "ส่วนขยาย Chrome"
        try:
            res = self.app.ipc.handle(cmd)
        except Exception as e:
            config.dbg(f"bridge cmd {b.get('cmd')}: {e}")
            return {"ok": False, "error": str(e)}
        if not isinstance(res, dict):
            return {"ok": False, "error": f"ไม่รู้จักคำสั่ง {b.get('cmd')}"}
        res.pop("image", None)          # path ในเครื่อง ไม่ต้องส่งออก
        return res
