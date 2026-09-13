"""กราฟสำหรับหน้าวิเคราะห์ — วาดเองด้วย PIL (ไม่ใช้ matplotlib จะได้ไม่ทำให้ .exe บวม)

ทุกฟังก์ชันคืน PIL.Image (RGB) ขนาดตามที่ขอ · ข้อความไทยวาดด้วย GDI (core.gditext)
"""
import io
from datetime import datetime

from PIL import Image, ImageDraw

from .analytics import DAYS_TH
from .gditext import draw_text, text_width
from .history import fmt_dur

BG = (18, 18, 28)
CARD = (28, 28, 40)
ACC = (46, 230, 168)
DIM = (138, 138, 160)
TXT = (235, 235, 245)
WARN = (255, 200, 87)
BAD = (255, 93, 122)


def _canvas(w, h, bg=BG):
    return Image.new("RGBA", (w, h), bg + (255,))


def _mix(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def hour_bars(hours, w=880, h=200, title="เวลาที่เล่น แยกตามชั่วโมงของวัน"):
    """24 แท่ง — ชั่วโมงไหนเล่นเยอะสุด"""
    img = _canvas(w, h)
    d = ImageDraw.Draw(img)
    draw_text(img, (16, 10), title, 17, TXT, bold=True)
    top, bot, left = 42, h - 28, 16
    gw = w - left * 2
    mx = max(hours) or 1
    bw = gw / 24
    peak = max(range(24), key=lambda i: hours[i])
    for i, v in enumerate(hours):
        bh = int((v / mx) * (bot - top))
        x = left + i * bw
        col = ACC if i == peak else _mix((52, 58, 78), ACC, v / mx * 0.75)
        d.rounded_rectangle((x + 2, bot - bh, x + bw - 3, bot), radius=3, fill=col + (255,))
        if i % 3 == 0:
            draw_text(img, (x + bw / 2, bot + 5), f"{i:02d}", 12, DIM, anchor="center")
    draw_text(img, (w - 16, 14), f"สูงสุด {fmt_dur(mx)} ที่ {peak:02d}:00 น.", 14, DIM, anchor="right")
    return img.convert("RGB")


def heatmap(grid, w=880, h=230, title="ช่วงเวลาที่เล่นบ่อย (วัน × ชั่วโมง)"):
    """ตาราง 7x24 — เข้ม = เล่นเยอะ"""
    img = _canvas(w, h)
    d = ImageDraw.Draw(img)
    draw_text(img, (16, 10), title, 17, TXT, bold=True)
    lx, top = 74, 44
    cw = (w - lx - 16) / 24
    ch = (h - top - 24) / 7
    mx = max((max(r) for r in grid), default=0) or 1
    for r in range(7):
        y = top + r * ch
        draw_text(img, (lx - 10, y + ch / 2 - 9), DAYS_TH[r], 13, DIM, anchor="right")
        for c in range(24):
            v = grid[r][c] / mx
            col = (30, 30, 44) if v <= 0 else _mix((26, 54, 48), ACC, min(1, v ** 0.6))
            d.rounded_rectangle((lx + c * cw + 1, y + 1, lx + (c + 1) * cw - 2, y + ch - 2), radius=2, fill=col + (255,))
    for c in range(0, 24, 3):
        draw_text(img, (lx + c * cw + cw / 2, h - 20), f"{c:02d}", 12, DIM, anchor="center")
    return img.convert("RGB")


def game_bars(games, name_fn, w=430, h=230, title="เกมที่เล่นมากสุด"):
    img = _canvas(w, h)
    d = ImageDraw.Draw(img)
    draw_text(img, (16, 10), title, 17, TXT, bold=True)
    top = games[:max(1, (h - 46) // 37)]
    if not top:
        draw_text(img, (16, 50), "ยังไม่มีข้อมูล", 15, DIM)
        return img.convert("RGB")
    mx = top[0]["seconds"] or 1
    y = 44
    for i, g in enumerate(top):
        nm = name_fn(g["place"]) or f"place {g['place']}"
        draw_text(img, (16, y), nm, 14, TXT, max_w=w - 120)
        dur = fmt_dur(g["seconds"])
        draw_text(img, (w - 16, y), dur, 13, DIM, anchor="right")
        bw = int((g["seconds"] / mx) * (w - 32))
        d.rounded_rectangle((16, y + 20, 16 + max(bw, 3), y + 27), radius=4,
                            fill=(_mix((52, 58, 78), ACC, 1 - i * 0.16)) + (255,))
        y += 37
    return img.convert("RGB")


def daily_bars(daily, w=430, h=230, title="เวลาเล่นรายวัน"):
    img = _canvas(w, h)
    d = ImageDraw.Draw(img)
    draw_text(img, (16, 10), title, 17, TXT, bold=True)
    top, bot, left = 46, h - 30, 16
    mx = max([s for _, s in daily] + [1])
    bw = (w - left * 2) / max(len(daily), 1)
    for i, (day, sec) in enumerate(daily):
        bh = int((sec / mx) * (bot - top))
        x = left + i * bw
        last = i == len(daily) - 1
        d.rounded_rectangle((x + 2, bot - bh, x + bw - 3, bot), radius=3,
                            fill=(ACC if last else (60, 140, 110)) + (255,))
        if len(daily) <= 14 or i % 2 == 0:
            draw_text(img, (x + bw / 2, bot + 6), day.strftime("%d"), 11, DIM, anchor="center")
    draw_text(img, (w - 16, 16), f"สูงสุด {fmt_dur(mx)}", 13, DIM, anchor="right")
    return img.convert("RGB")


def reason_bars(by_reason, w=430, h=230, title="สาเหตุที่หลุด"):
    from .history import fmt_reason
    img = _canvas(w, h)
    d = ImageDraw.Draw(img)
    draw_text(img, (16, 10), title, 17, TXT, bold=True)
    items = by_reason.most_common(max(1, (h - 46) // 37))
    if not items:
        draw_text(img, (16, 50), "ไม่หลุดเลย 🎉", 15, ACC)
        return img.convert("RGB")
    mx = items[0][1]
    y = 44
    for code, n in items:
        draw_text(img, (16, y), fmt_reason(code), 14, TXT, max_w=w - 90)
        draw_text(img, (w - 16, y), f"{n} ครั้ง", 13, DIM, anchor="right")
        bw = int((n / mx) * (w - 32))
        d.rounded_rectangle((16, y + 20, 16 + max(bw, 3), y + 27), radius=4, fill=BAD + (255,))
        y += 37
    return img.convert("RGB")


def analytics_card(hist, days=30):
    """การ์ดใหญ่รวมทุกอย่าง สำหรับแชร์เข้า Discord → PNG bytes"""
    from . import analytics as an
    s = hist.summary(days)
    sess = hist.sessions
    W, H = 1000, 760
    img = _canvas(W, H)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 8, H), fill=ACC + (255,))
    draw_text(img, (36, 28), f"สรุปการเล่น {days} วันล่าสุด", 15, ACC, bold=True)
    draw_text(img, (36, 50), fmt_dur(s["total"]), 42, TXT, bold=True)
    st = an.sessions_stats(sess, days)
    draw_text(img, (36, 104), f"{s['sessions']} เซสชัน · เฉลี่ยครั้งละ {fmt_dur(st['avg'])} · หลุด {len(s['disconnects'])} ครั้ง"
                              f" · เล่นติดกัน {an.streak(sess)} วัน", 17, (190, 190, 205))
    draw_text(img, (W - 36, 34), datetime.now().strftime("%d/%m/%Y %H:%M"), 14, DIM, anchor="right")

    def paste(im, xy):
        img.paste(im.convert("RGBA"), xy)

    paste(heatmap(an.heat(sess, min(days, 28)), w=W - 72, h=220), (36, 140))
    paste(hour_bars(an.hourly(sess, days), w=W - 72, h=180), (36, 372))
    paste(game_bars(s["games"], hist.name, w=(W - 84) // 2, h=190), (36, 562))
    paste(reason_bars(an.disconnects(sess, days)["by_reason"], w=(W - 84) // 2, h=190), (36 + (W - 84) // 2 + 12, 562))
    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()
