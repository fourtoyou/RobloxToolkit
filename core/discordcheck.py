"""Discord ล่มหรือเน็ตเรา? — เช็ค gateway ของ Discord ตรงๆ (ตัวที่แอป/บอทต้องต่อค้างไว้)
เจอจริง 2026-09-15 21:17: เว็บ discord.com เปิดได้ แต่ wss://gateway.discord.gg ตอบ 502/503 → แอปค้างหน้าโหลด, บอทหลุดซ้ำ
ใช้แค่ stdlib (TLS + HTTP Upgrade) เพราะ exe ไม่ได้แพ็ก websocket/aiohttp"""
import socket
import ssl
import time

HOST = "gateway.discord.gg"


def gateway(timeout=6):
    """คืน (ok, สถานะ HTTP หรือข้อความ error, ms) — 101 = ปกติ · 502/503 = ล่มฝั่ง Discord · error = ต่อไม่ได้ (เน็ตเรา/DNS)"""
    t0 = time.perf_counter()
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((HOST, 443), timeout=timeout) as s:
            with ctx.wrap_socket(s, server_hostname=HOST) as ts:
                ts.sendall(b"GET /?v=10&encoding=json HTTP/1.1\r\nHost: " + HOST.encode() + b"\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\nUser-Agent: RobloxToolkit\r\n\r\n")
                ts.settimeout(timeout)
                line = ts.recv(512).split(b"\r\n")[0].decode("ascii", "ignore")
        ms = (time.perf_counter() - t0) * 1000
        parts = line.split()
        code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        return code == 101, code, ms
    except Exception as e:
        return False, f"{type(e).__name__}", (time.perf_counter() - t0) * 1000


def probe(n=3):
    """ลอง n ครั้ง — คืน dict: ok_n, codes, verdict ('ok' / 'discord_down' / 'unreachable')"""
    codes = []
    for _ in range(n):
        ok, code, ms = gateway()
        codes.append(code)
        if ok and n > 1:
            break
    ok_n = sum(1 for c in codes if c == 101)
    if ok_n:
        verdict = "ok"
    elif any(isinstance(c, int) and c >= 500 for c in codes):
        verdict = "discord_down"
    else:
        verdict = "unreachable"
    return {"ok_n": ok_n, "codes": codes, "verdict": verdict}


def status_page(timeout=6):
    """discordstatus.com — คืน (indicator, ชื่อ incident ที่เปิดอยู่ หรือ None) · ปกติอัปเดตช้ากว่าของจริงหลายนาที"""
    try:
        import requests
        d = requests.get("https://discordstatus.com/api/v2/summary.json", timeout=timeout).json()
        inc = [i["name"] for i in d.get("incidents", []) if i.get("status") not in ("resolved", "postmortem")]
        return d.get("status", {}).get("indicator", "?"), (inc[0] if inc else None)
    except Exception:
        return None, None


def app_connected():
    """(Discord.exe เปิดอยู่ไหม, จำนวน TCP connection ที่ต่ออยู่) — แอปเปิดแต่ 0 connection นานๆ = ต่อ Discord ไม่ได้"""
    import psutil
    pids = {p.info["pid"] for p in psutil.process_iter(["pid", "name"]) if (p.info["name"] or "").lower() == "discord.exe"}
    if not pids:
        return False, 0
    n = 0
    try:
        for con in psutil.net_connections(kind="inet"):
            if con.pid in pids and con.status == "ESTABLISHED":
                n += 1
    except Exception:
        return True, -1
    return True, n


def explain(verdict, code=None):
    return {"ok": "Discord ปกติ",
            "discord_down": f"Discord ล่มฝั่งเขา (gateway ตอบ {code}) — ไม่ใช่เน็ตคุณ รอเฉยๆ เดี๋ยวแอปต่อเอง",
            "unreachable": "ต่อ Discord ไม่ได้เลยจากเครื่องนี้ — เน็ต/DNS ของเรา"}.get(verdict, "?")
