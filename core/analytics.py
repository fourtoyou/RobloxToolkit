"""วิเคราะห์พฤติกรรมการเล่นจาก log ทั้งหมด — ชั่วโมงที่เล่น, วันในสัปดาห์, heatmap, สาเหตุที่หลุด, ข้อสังเกต

ทุกฟังก์ชันรับ list ของ session dict จาก history.py: {start, end, place, job, reason}
reason: None/0 = ต่อเนื่อง/วาร์ป · -1 = ปิดเกม/ค้าง · 285 = ออกเอง · ที่เหลือ = หลุดจริง
"""
import time
from collections import Counter, defaultdict
from datetime import datetime

DAYS_TH = ["จันทร์", "อังคาร", "พุธ", "พฤหัส", "ศุกร์", "เสาร์", "อาทิตย์"]
REAL_DISC = lambda r: r not in (None, 0, -1, 285)   # noqa: E731


def _slices(s):
    """ตัดเซสชันเป็นชิ้นๆ ตามชั่วโมง → (เวลาเริ่มของชิ้น, วินาที) เพื่อกระจายลงถังได้ถูกต้อง"""
    t = s["start"]
    while t < s["end"]:
        nxt = (t // 3600 + 1) * 3600
        yield t, min(s["end"], nxt) - t
        t = nxt


def _recent(sessions, days):
    since = time.time() - days * 86400 if days else 0
    return [s for s in sessions if s["end"] >= since]


def hourly(sessions, days=30):
    """วินาทีที่เล่น แยกตามชั่วโมงของวัน (0-23)"""
    out = [0.0] * 24
    for s in _recent(sessions, days):
        for t, dur in _slices(s):
            out[datetime.fromtimestamp(t).hour] += dur
    return out


def weekday(sessions, days=90):
    """วินาทีที่เล่น แยกตามวันในสัปดาห์ (0=จันทร์) + จำนวนวันจริงที่นับได้ (ไว้หาค่าเฉลี่ย)"""
    out, seen = [0.0] * 7, defaultdict(set)
    for s in _recent(sessions, days):
        for t, dur in _slices(s):
            d = datetime.fromtimestamp(t)
            out[d.weekday()] += dur
            seen[d.weekday()].add(d.date())
    return out, {k: len(v) for k, v in seen.items()}


def heat(sessions, days=28):
    """ตาราง 7x24 (วันในสัปดาห์ x ชั่วโมง) — วินาทีที่เล่น"""
    grid = [[0.0] * 24 for _ in range(7)]
    for s in _recent(sessions, days):
        for t, dur in _slices(s):
            d = datetime.fromtimestamp(t)
            grid[d.weekday()][d.hour] += dur
    return grid


def disconnects(sessions, days=30):
    """สรุปการหลุด: ต่อสาเหตุ / ต่อชั่วโมง / ต่อเกม"""
    by_reason, by_hour, by_game = Counter(), [0] * 24, Counter()
    for s in _recent(sessions, days):
        if not REAL_DISC(s["reason"]):
            continue
        by_reason[s["reason"]] += 1
        by_hour[datetime.fromtimestamp(s["end"]).hour] += 1
        by_game[s["place"]] += 1
    return {"by_reason": by_reason, "by_hour": by_hour, "by_game": by_game, "total": sum(by_reason.values())}


def streak(sessions):
    """เล่นติดกันกี่วันจนถึงวันนี้"""
    days = {datetime.fromtimestamp(t).date() for s in sessions for t, _ in _slices(s)}
    if not days:
        return 0
    today = datetime.now().date()
    n, d = 0, today
    if d not in days:                       # ยังไม่ได้เล่นวันนี้ → เริ่มนับจากเมื่อวาน
        d = today.fromordinal(today.toordinal() - 1)
    while d in days:
        n += 1
        d = d.fromordinal(d.toordinal() - 1)
    return n


def sessions_stats(sessions, days=30):
    """ความยาวเซสชัน: เฉลี่ย / ยาวสุด / จำนวน"""
    lst = _recent(sessions, days)
    if not lst:
        return {"count": 0, "avg": 0, "longest": None}
    durs = [s["end"] - s["start"] for s in lst]
    return {"count": len(lst), "avg": sum(durs) / len(durs), "longest": max(lst, key=lambda s: s["end"] - s["start"])}


def server_distance(sessions, dc_map, days=30):
    """เวลาเล่นแยกตามระยะเซิร์ฟ (จาก DC ที่จำ ping ไว้) — คืน dict(near, mid, far, unknown เป็นวินาที) + top DC"""
    out = {"near": 0.0, "mid": 0.0, "far": 0.0, "unknown": 0.0}
    per_dc = Counter()
    for s in _recent(sessions, days):
        dur = max(0.0, s["end"] - s["start"])
        info = (dc_map or {}).get(str(s.get("dc"))) if s.get("dc") is not None else None
        p = (info or {}).get("ping")
        if p is None:
            out["unknown"] += dur
        else:
            out["near" if p <= 70 else "mid" if p <= 150 else "far"] += dur
            per_dc[s["dc"]] += dur
    return out, per_dc


def drop_causes(days=30):
    """สาเหตุหลุดจาก drops.json (Toolkit วิเคราะห์ตอนหลุด ตั้งแต่ v2.17)"""
    from . import config
    cut = time.time() - days * 86400
    c = Counter()
    for d in config.load_drops():
        if d.get("t", 0) >= cut and d.get("reason") != 285:
            c[d.get("cause_short") or "?"] += 1
    return c


def insights(sessions, name_fn=lambda p: p, days=30, dc_map=None):
    """ข้อสังเกตเป็นภาษาคน — คืน list ของ (ไอคอน, ข้อความ)"""
    out = []
    lst = _recent(sessions, days)
    if not lst:
        return [("📭", f"ยังไม่มีข้อมูลใน {days} วันล่าสุด")]
    from .history import fmt_dur, fmt_reason

    # เซิร์ฟไกล/ใกล้ — ข้อสังเกตที่ทำอะไรต่อได้จริง (ต่างกันได้ 70 ms ต่อทุกการกระทำ)
    if dc_map:
        dist, per_dc = server_distance(sessions, dc_map, days)
        known = dist["near"] + dist["mid"] + dist["far"]
        if known >= 600:
            far = dist["mid"] + dist["far"]
            if far / known >= 0.3:
                top = per_dc.most_common(1)[0][0] if per_dc else None
                tp = (dc_map.get(str(top)) or {}).get("ping")
                out.append(("🌏", f"{far / known * 100:.0f}% ของเวลาเล่น ({fmt_dur(far)}) อยู่บนเซิร์ฟกลาง/ไกล" + (f" — บ่อยสุด DC {top} ~{tp} ms" if tp else "")
                            + " · ส่วนขยาย Chrome ตั้ง 'ping ต่ำก่อน' แล้วกด ⚡ จะได้สิงคโปร์ ~35 ms"))
            else:
                out.append(("🌏", f"{dist['near'] / known * 100:.0f}% ของเวลาเล่นอยู่บนเซิร์ฟใกล้ (≤70 ms) — ดีแล้ว"))
    dcs = drop_causes(days)
    if dcs:
        top_c = dcs.most_common(1)[0]
        out.append(("🔎", f"หลุดที่วิเคราะห์สาเหตุได้ {sum(dcs.values())} ครั้ง — บ่อยสุด: {top_c[0]} ({top_c[1]} ครั้ง)"
                    + {"สาย/Wi-Fi หลุด": " → เช็คสาย USB/ระยะจากมือถือ", "มือถือหลุดจากเสา": " → ขยับมือถือหาสัญญาณ/ล็อก 4G",
                       "เน็ตสะดุด": " → อย่าให้อะไรอัปโหลดตอนเล่น", "ฝั่งเซิร์ฟ": " → ไม่ใช่ความผิดเครื่องเรา"}.get(top_c[0], "")))

    wd, seen = weekday(sessions, days)
    if any(wd):
        avg = [(wd[i] / seen[i] if seen.get(i) else 0) for i in range(7)]
        best = max(range(7), key=lambda i: avg[i])
        if avg[best]:
            out.append(("📅", f"วัน{DAYS_TH[best]}เล่นหนักสุด — เฉลี่ยวันละ {fmt_dur(avg[best])}"))

    hrs = hourly(sessions, days)
    if any(hrs):
        peak = max(range(24), key=lambda h: hrs[h])
        night = sum(hrs[0:6])
        out.append(("🕐", f"ชั่วโมงที่เล่นบ่อยสุดคือ {peak:02d}:00 น. ({fmt_dur(hrs[peak])} รวม {days} วัน)"))
        if night > sum(hrs) * 0.25:
            out.append(("🌙", f"เล่นดึก (เที่ยงคืน–6 โมงเช้า) ไปแล้ว {fmt_dur(night)} = {night / sum(hrs) * 100:.0f}% ของเวลาเล่นทั้งหมด"))

    st = sessions_stats(sessions, days)
    if st["longest"]:
        L = st["longest"]
        out.append(("⏱", f"เซสชันยาวสุด {fmt_dur(L['end'] - L['start'])} ({name_fn(L['place'])}) เมื่อ {datetime.fromtimestamp(L['start']).strftime('%d/%m %H:%M')}"))
        out.append(("📊", f"{st['count']} เซสชันใน {days} วัน — เฉลี่ยครั้งละ {fmt_dur(st['avg'])}"))

    dc = disconnects(sessions, days)
    if dc["total"]:
        top_r = dc["by_reason"].most_common(1)[0]
        out.append(("⚠", f"หลุด {dc['total']} ครั้ง — สาเหตุอันดับ 1 คือ {fmt_reason(top_r[0])} ({top_r[1]} ครั้ง)"))
        ph = max(range(24), key=lambda h: dc["by_hour"][h])
        if dc["by_hour"][ph] >= 3:
            out.append(("📉", f"หลุดบ่อยสุดช่วง {ph:02d}:00 น. ({dc['by_hour'][ph]} ครั้ง) — ถ้าเน็ตบ้านคนใช้เยอะช่วงนี้ก็ตรงกัน"))
        tg = dc["by_game"].most_common(1)[0]
        if tg[1] >= 3:
            out.append(("🎮", f"เกมที่หลุดบ่อยสุด: {name_fn(tg[0])} ({tg[1]} ครั้ง)"))
    else:
        out.append(("✅", f"ไม่หลุดเลยใน {days} วันล่าสุด"))

    sk = streak(sessions)
    if sk >= 2:
        out.append(("🔥", f"เล่นติดกันมาแล้ว {sk} วัน"))
    return out
