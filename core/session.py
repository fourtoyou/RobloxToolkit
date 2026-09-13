"""สรุปหลังเล่น (Session Recap): เมื่อออก/หลุดจากเกม → การ์ดรูปสรุป + toast + ส่ง Discord webhook
+ การ์ดสถิติรายสัปดาห์แชร์ได้"""
import io
import json
import os
import threading
import time

from PIL import Image, ImageDraw, ImageFilter

from . import config
from .gditext import draw_text, text_width

W, H = 900, 300
ACC = (46, 230, 168)
_icon_cache = {}


def fmt_dur(sec):
    sec = int(sec)
    h, m = sec // 3600, (sec % 3600) // 60
    return f"{h} ชม. {m} นาที" if h else f"{m} นาที"


def game_icon(place):
    """ไอคอนเกมจาก Roblox (cache ในดิสก์)"""
    if place in _icon_cache:
        return _icon_cache[place]
    cache_dir = os.path.join(config.DATA_DIR, "icons")
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{place}.png")
    if os.path.exists(path):
        _icon_cache[place] = open(path, "rb").read()
        return _icon_cache[place]
    try:
        import requests
        uid = requests.get(f"https://apis.roblox.com/universes/v1/places/{place}/universe", timeout=6).json().get("universeId")
        d = requests.get(f"https://thumbnails.roblox.com/v1/games/icons?universeIds={uid}&size=256x256&format=Png", timeout=6).json()
        url = d["data"][0]["imageUrl"]
        data = requests.get(url, timeout=8).content
        open(path, "wb").write(data)
        _icon_cache[place] = data
    except Exception:
        _icon_cache[place] = None
    return _icon_cache[place]


def _base(icon_bytes, accent=ACC):
    if icon_bytes:
        art = Image.open(io.BytesIO(icon_bytes)).convert("RGB")
        bg = art.resize((W, W)).crop((0, (W - H) // 2, W, (W - H) // 2 + H)).filter(ImageFilter.GaussianBlur(26))
        bg = Image.blend(bg, Image.new("RGB", (W, H), (12, 12, 18)), 0.55).convert("RGBA")
    else:
        art = None
        bg = Image.new("RGBA", (W, H), (18, 18, 28, 255))
    ImageDraw.Draw(bg).rectangle((0, 0, 8, H), fill=accent + (255,))
    return bg, art


def _rounded(img, r):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.size[0] - 1, img.size[1] - 1), radius=r, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def recap_card(game, place, duration, start, end, disconnects, reason_text, net_avg, net_loss, pokes):
    """การ์ดสรุป 1 เซสชัน → PNG bytes"""
    bg, art = _base(game_icon(place))
    if art:
        bg.alpha_composite(_rounded(art.resize((200, 200)), 22), (40, 50))
    x0 = 280
    draw_text(bg, (x0, 36), "S E S S I O N   R E C A P", 16, ACC, bold=True)
    draw_text(bg, (x0, 62), game, 36, (255, 255, 255), bold=True, max_w=W - x0 - 40)
    draw_text(bg, (x0, 112), f"{time.strftime('%H:%M', time.localtime(start))} – {time.strftime('%H:%M', time.localtime(end))}  ·  {time.strftime('%d/%m/%Y', time.localtime(end))}", 20, (190, 190, 205))
    # สถิติ 4 ช่อง
    stats = [("เวลาเล่น", fmt_dur(duration)), ("จบเพราะ", reason_text),
             ("เน็ตเฉลี่ย", f"{net_avg:.0f} ms · หาย {net_loss:.0f}%" if net_avg else "—"), ("Anti-AFK กด", f"{pokes} ครั้ง")]
    cw = (W - x0 - 40) // 2
    for i, (k, v) in enumerate(stats):
        cx = x0 + (i % 2) * cw
        cy = 160 + (i // 2) * 62
        draw_text(bg, (cx, cy), k, 16, (150, 150, 168))
        draw_text(bg, (cx, cy + 22), v, 24, (255, 255, 255) if k != "จบเพราะ" or "ออกเอง" in v else (255, 93, 122), bold=True, max_w=cw - 16)
    out = io.BytesIO()
    bg.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()


def weekly_card(summary, name_fn, daily):
    """การ์ดสถิติ 7 วัน: เวลารวม, กราฟรายวัน, เกม Top 3 → PNG bytes"""
    top = summary["games"][:3]
    icon = game_icon(top[0]["place"]) if top else None
    bg, art = _base(icon)
    if art:
        bg.alpha_composite(_rounded(art.resize((120, 120)), 18), (40, 40))
    draw_text(bg, (180, 40), "W E E K L Y   S T A T S", 16, ACC, bold=True)
    draw_text(bg, (180, 64), fmt_dur(summary["total"]), 40, (255, 255, 255), bold=True)
    draw_text(bg, (180, 116), f"{summary['sessions']} เซสชัน  ·  หลุด {len(summary['disconnects'])} ครั้ง  ·  7 วันล่าสุด", 18, (190, 190, 205))
    # กราฟรายวัน
    d = ImageDraw.Draw(bg)
    gx, gy, gw, gh = 40, 180, 380, 90
    mx = max([s for _, s in daily] + [3600])
    bw = gw / len(daily)
    for i, (day, sec) in enumerate(daily):
        h = int((sec / mx) * (gh - 20))
        x = gx + i * bw + 6
        d.rounded_rectangle((x, gy + gh - 18 - h, x + bw - 12, gy + gh - 18), radius=5, fill=ACC + (255,) if i == len(daily) - 1 else (60, 140, 110, 255))
        draw_text(bg, (x + (bw - 12) / 2, gy + gh - 14), day.strftime("%a"), 13, (150, 150, 168), anchor="center")
    # Top 3
    tx = 460
    draw_text(bg, (tx, 176), "เล่นมากสุด", 16, (150, 150, 168))
    for i, g in enumerate(top):
        y = 200 + i * 32
        draw_text(bg, (tx, y), f"{i + 1}.", 20, ACC, bold=True)
        draw_text(bg, (tx + 28, y), name_fn(g["place"]), 20, (255, 255, 255), max_w=260)
        draw_text(bg, (W - 40, y + 2), fmt_dur(g["seconds"]), 17, (190, 190, 205), anchor="right")
    out = io.BytesIO()
    bg.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()


def webhook_image(url, png_bytes, text="", filename="card.png"):
    """ส่งรูปเข้า Discord webhook (multipart)"""
    if not url or "discord" not in url:
        return

    def _send():
        try:
            import requests
            requests.post(url, data={"payload_json": json.dumps({"content": text, "username": "Roblox Toolkit"})},
                          files={"file": (filename, png_bytes, "image/png")}, timeout=15)
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()


class SessionTracker:
    """จับเวลาเซสชันปัจจุบัน + นับหลุด/poke ระหว่างเซสชัน"""

    def __init__(self):
        self.start = None
        self.place = None
        self.disconnects = 0
        self.pokes = 0
        self.pings = []

    def begin(self, place):
        self.start, self.place, self.disconnects, self.pokes, self.pings = time.time(), place, 0, 0, []

    def sample_ping(self, ms):
        if self.start and ms is not None:
            self.pings.append(ms)

    def end(self):
        if not self.start:
            return None
        dur = time.time() - self.start
        out = {"place": self.place, "start": self.start, "end": time.time(), "duration": dur, "disconnects": self.disconnects,
               "pokes": self.pokes, "net_avg": sum(self.pings) / len(self.pings) if self.pings else 0,
               "net_loss": 0}
        self.start = None
        return out if dur >= 60 else None  # เซสชันสั้นกว่า 1 นาที ไม่ต้องสรุป
