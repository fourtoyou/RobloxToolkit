"""รับคำสั่งจาก Discord bot (หรือโปรแกรมอื่น) ผ่านไฟล์ใน %USERPROFILE%\\.robloxtoolkit\\cmd\\*.json
บอทเขียน {"id":..,"cmd":"screenshot"} → Toolkit ทำ → เขียนผลที่ res\\<id>.json (+ รูป .png)
คำสั่ง: screenshot · afk_start · afk_stop · launch(place, job) · hide · unhide · status
        timer(minutes, action) · timer_cancel · power(action: sleep|shutdown|close_roblox|cancel) · log(n) · quit
        quiet (ย้ายไปเซิร์ฟที่คนน้อยสุด) · serverinfo · analytics(days) · reset · fps(limit)"""
import ctypes
import glob
import json
import os
import sys
import threading
import time
from ctypes import wintypes

from . import config
from .win import roblox_pids, roblox_windows, u

CMD_DIR = os.path.join(config.DATA_DIR, "cmd")
RES_DIR = os.path.join(config.DATA_DIR, "res")
PW_RENDERFULLCONTENT = 2


class RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]


# handle บน 64-bit เป็นเลข 64 บิต — ต้องบอก ctypes ไม่ให้ตัดเป็น int 32 บิต ไม่งั้นพังแบบสุ่ม
gdi32 = ctypes.windll.gdi32
u.IsIconic.argtypes = [wintypes.HWND]
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
u.GetWindowDC.argtypes = [wintypes.HWND]
u.GetWindowDC.restype = wintypes.HDC
u.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
u.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
u.PrintWindow.restype = wintypes.BOOL
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                            ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]


def grab_window(hwnd):
    """จับภาพหน้าต่าง (แม้ถูกบัง) ด้วย PrintWindow — คืน (PIL.Image หรือ None, ข้อความ)"""
    from PIL import Image
    if u.IsIconic(hwnd):
        return None, "Roblox ถูกย่ออยู่ — ถ่ายไม่ได้ (ใช้โหมดซ่อนแทนการย่อจะถ่ายได้)"
    r = RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.r - r.l, r.b - r.t
    if w < 10 or h < 10:
        return None, "หน้าต่างเล็กเกินไป"
    hdc = u.GetWindowDC(hwnd)
    gdi = gdi32
    mdc = gdi.CreateCompatibleDC(hdc)
    bmp = gdi.CreateCompatibleBitmap(hdc, w, h)
    gdi.SelectObject(mdc, bmp)
    ok = u.PrintWindow(hwnd, mdc, PW_RENDERFULLCONTENT)

    class BMI(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]
    bmi = BMI()
    bmi.biSize, bmi.biWidth, bmi.biHeight, bmi.biPlanes, bmi.biBitCount = ctypes.sizeof(BMI), w, -h, 1, 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    gdi.DeleteObject(bmp)
    gdi.DeleteDC(mdc)
    u.ReleaseDC(hwnd, hdc)
    img = Image.frombuffer("RGB", (w, h), buf.raw, "raw", "BGRX", 0, 1)
    if not ok or img.getbbox() is None:
        return None, "จับภาพไม่ได้ (หน้าต่างไม่ได้วาดอะไร)"
    return img, ""


def screenshot_window(hwnd, path):
    """จับภาพหน้าต่างลงไฟล์ PNG — คืน (ok, path/ข้อความ)"""
    img, msg = grab_window(hwnd)
    if img is None:
        return False, msg
    if img.width > 1280:
        img = img.resize((1280, int(img.height * 1280 / img.width)))
    img.save(path, "PNG", optimize=True)
    return True, path


class CommandServer(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        os.makedirs(CMD_DIR, exist_ok=True)
        os.makedirs(RES_DIR, exist_ok=True)
        for f in glob.glob(os.path.join(CMD_DIR, "*.json")):  # ล้างคำสั่งค้าง
            try:
                os.remove(f)
            except OSError:
                pass

    def run(self):
        config.dbg("ipc server started, CMD_DIR=" + CMD_DIR)
        while True:
            try:
                for f in sorted(glob.glob(os.path.join(CMD_DIR, "*.json"))):
                    try:
                        with open(f, encoding="utf-8") as fh:
                            cmd = json.load(fh)
                    except Exception:
                        cmd = None
                    try:
                        os.remove(f)
                    except OSError:
                        pass
                    if cmd:
                        self.handle(cmd)
                # ลบผลลัพธ์เก่ากว่า 10 นาที
                for f in glob.glob(os.path.join(RES_DIR, "*")):
                    if time.time() - os.path.getmtime(f) > 600:
                        try:
                            os.remove(f)
                        except OSError:
                            pass
            except Exception as e:
                import traceback
                config.dbg("ipc error: " + traceback.format_exc())
                self.app.log(f"ipc: {e}")
            time.sleep(1)

    def reply(self, cmd, **data):
        data.setdefault("ok", True)
        data["at"] = time.time()
        if cmd.get("_direct"):          # เรียกตรงจาก bridge (HTTP) — คืนค่ากลับไปเลย ไม่ต้องเขียนไฟล์
            return data
        tmp = os.path.join(RES_DIR, f"{cmd['id']}.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(RES_DIR, f"{cmd['id']}.json"))
        return data

    def handle(self, cmd):
        app, eng = self.app, self.app.eng
        c = cmd.get("cmd")
        app.log(f"📡 คำสั่งจาก {cmd.get('_from', 'Discord')}: {c}")
        if c == "watch":
            # เฝ้าจอ: {on, words:[..], interval, cooldown} → ตั้งค่า · ไม่ส่งอะไร = แค่ดูสถานะ
            w = app.watch
            if any(k in cmd for k in ("on", "words", "interval", "cooldown")):
                w.configure(on=cmd.get("on"), words=cmd.get("words"), interval=cmd.get("interval"), cooldown=cmd.get("cooldown"))
                app.ui(app.pages["watch"].refresh)
            return self.reply(cmd, **w.status())
        if c == "watch_text":
            try:
                lines, path = app.watch.read_once()
                app.watch.last_text, app.watch.last_at, app.watch.last_err = lines, time.time(), None
                return self.reply(cmd, lines=lines, image=path)
            except Exception as e:
                return self.reply(cmd, ok=False, msg=str(e))
        if c == "ram":
            from .sysmon import top_apps
            cur = app.sys.cur
            return self.reply(cmd, percent=cur.get("ram"), used=cur.get("ram_used"), total=cur.get("ram_total"),
                              apps=[{"name": n, "mb": round(mb), "procs": k} for n, mb, k in top_apps(6)])
        if c == "trim_ram":
            from .sysmon import trim_ram
            n, freed, b, a = trim_ram()
            msg = f"คืนแรมแล้ว: {n} โปรเซส · ว่างเพิ่ม {freed:.0f} MB ({b:.0f}% → {a:.0f}%)"
            app.log("🧹 " + msg)
            app.game_events.insert(0, (time.time(), msg))
            return self.reply(cmd, msg=msg, procs=n, freed_mb=round(freed), before=b, after=a)
        if c == "doctor":
            from . import doctor as _doc
            items, summary = _doc.run(app)
            return self.reply(cmd, summary=summary, items=[{k: v for k, v in it.items() if k != "fix"} for it in items])
        if c == "netcheck":
            from . import netmon as _nm
            r = _nm.bufferbloat_test()
            app.cfg["bufferbloat"] = r
            config.save(app.cfg)
            app.ui(lambda: app.pages["net"].render_bb(r))
            return self.reply(cmd, **{k: r[k] for k in ("grade", "level", "extra", "up_mbps", "advice")},
                              idle=r["idle"]["avg"], loaded=r["up"]["avg"], loaded_max=r["up"]["max"], jitter=r["up"]["jitter"])
        if c == "regions":
            from . import netmon as _nm
            res = _nm.probe_regions()
            app.cfg["region_probe"], app.cfg["region_probe_at"] = res, time.time()
            config.save(app.cfg)
            app.ui(lambda: app.pages["net"].render_probe(res, time.time()))
            return self.reply(cmd, regions=res)
        if c == "update":
            # เช็ค/ติดตั้งเวอร์ชันใหม่จาก GitHub — สั่งได้จาก Discord (/update) และส่วนขยาย
            from . import updater
            repo = app.cfg.get("update_repo") or config.DEFAULT_REPO
            try:
                info = updater.check(repo)
            except Exception as e:
                return self.reply(cmd, ok=False, msg=f"เช็คไม่ได้: {e}")
            base = dict(current=config.VERSION, latest=info["ver"], newer=info["newer"], has_file=bool(info["url"]), sha=bool(info["sha256"]))
            if not info["newer"]:
                return self.reply(cmd, msg=f"เป็นเวอร์ชันล่าสุดแล้ว (v{config.VERSION})", **base)
            if not cmd.get("install"):
                return self.reply(cmd, msg=f"มีเวอร์ชันใหม่ v{info['ver']} (ตอนนี้ v{config.VERSION})", **base)
            if not info["url"]:
                return self.reply(cmd, ok=False, msg="release ยังไม่มีไฟล์ .exe (GitHub Actions อาจกำลัง build อยู่)", **base)
            if not getattr(sys, "frozen", False):
                return self.reply(cmd, ok=False, msg="รันจากซอร์สอยู่ — ใช้ git pull แทน", **base)

            def work():
                try:
                    updater.download(info["url"], updater.staging_path(), info["size"], info["sha256"])
                    app.log(f"⬆ โหลด v{info['ver']} เสร็จ ตรวจ SHA256 ผ่าน — ปิดเพื่อติดตั้งแล้วเปิดใหม่")
                    updater.install_and_restart(updater.staging_path())
                    app.ui(app.on_close)
                    time.sleep(1.5)
                    os._exit(0)
                except Exception as e:
                    app.log(f"อัปเดตไม่สำเร็จ: {e}")
            threading.Thread(target=work, daemon=True).start()
            return self.reply(cmd, msg=f"กำลังโหลด v{info['ver']} — ตรวจไฟล์เสร็จจะปิดแล้วเปิดใหม่เอง (ราว 1 นาที)", **base)
        if c == "join":
            # เข้าเซิร์ฟที่เลือกจากส่วนขยาย — ถ้าเกมเปิดอยู่ใช้ hop (ปิดแล้วเปิดใหม่เข้าเซิร์ฟนั้น) ไม่งั้นเปิดตรงๆ
            place, job = cmd.get("place"), cmd.get("job")
            if not place:
                return self.reply(cmd, ok=False, msg="ไม่รู้ว่าเกมไหน")
            if eng.rejoining:
                return self.reply(cmd, ok=False, msg="กำลังต่อเกมอยู่ รอสักครู่")
            # จำไว้ว่าอยากไปเซิร์ฟไหน — app จะเทียบกับ log ตอนเกมเข้าจริง แล้วบอกผลใน status.json (join_result) + แจ้งเตือน
            app.join_want = {"place": str(place), "job": (job or "").lower() or None, "at": time.time(), "src": cmd.get("_from", "Discord")}
            app.join_result = None
            if roblox_pids():
                eng.rejoining = True
                threading.Thread(target=eng.hop, args=(place, lambda: job), daemon=True).start()
                how = "ปิดเกมแล้วเปิดใหม่เข้าเซิร์ฟที่เลือก"
            else:
                from . import launcher
                launcher.launch(place, job)
                how = "เปิดเกมเข้าเซิร์ฟที่เลือก"
            if cmd.get("afk") and not eng.running:
                app.ui(lambda: (eng.start(app.cfg["immediate"]), app.log("เริ่ม Anti-AFK (จากส่วนขยาย)")))
                how += " + เริ่ม Anti-AFK"
            return self.reply(cmd, msg=how)
        if c == "screenshot":
            wins = roblox_windows(True) + [h for h in eng.hidden if u.IsWindow(h)]
            if not wins:
                return self.reply(cmd, ok=False, msg="ไม่เจอหน้าต่าง Roblox")
            path = os.path.join(RES_DIR, f"{cmd['id']}.png")
            ok, msg = screenshot_window(wins[0], path)
            return self.reply(cmd, ok=ok, msg=msg, image=path if ok else None, hidden=wins[0] in eng.hidden)
        if c == "afk_start":
            app.ui(lambda: (eng.start(app.cfg["immediate"]), app.log("เริ่ม Anti-AFK (จาก Discord)")))
            return self.reply(cmd, msg="เริ่ม Anti-AFK แล้ว")
        if c == "afk_stop":
            app.ui(lambda: (eng.stop(), app.log("หยุด Anti-AFK (จาก Discord)")))
            return self.reply(cmd, msg="หยุด Anti-AFK แล้ว")
        if c == "hide":
            n = eng.hide_minimized()
            return self.reply(cmd, msg=f"ซ่อน {n} หน้าต่าง" if n else "ไม่มี Roblox ที่ย่ออยู่ให้ซ่อน")
        if c == "unhide":
            return self.reply(cmd, msg=f"เอากลับมา {eng.unhide_all()} หน้าต่าง")
        if c == "launch":
            from . import launcher
            if cmd.get("job"):
                launcher.launch(cmd.get("place"), cmd.get("job"))
                return self.reply(cmd, msg=f"เปิดเกม {cmd.get('place')} เข้าเซิร์ฟที่ระบุ")
            launcher.launch_best(cmd.get("place"), app.log)      # ไม่ระบุเซิร์ฟ → เลือกเซิร์ฟที่ว่างและ ping ต่ำสุดให้
            return self.reply(cmd, msg=f"เปิดเกม {app.place_name(cmd.get('place'))} (เลือกเซิร์ฟ ping ต่ำสุดให้)")
        if c == "status":
            sw = app.swatch
            return self.reply(cmd, running=eng.running, hidden=len(eng.hidden), windows=len(roblox_windows(True)),
                              timer_end=app.timer_end, timer_action=app.timer_action, version=config.VERSION,
                              players=sw.players, max_players=sw.maxp, quiet=sw.quiet)
        if c == "serverinfo":
            sw = app.swatch
            from . import servers as _srv
            return self.reply(cmd, players=sw.players, max_players=sw.maxp, quiet=sw.quiet, ping=sw.ping,
                              seen=sw.seen, sample=sw.sample, limited=_srv.limited(),
                              auto_hop=app.cfg["auto_hop"], hop_over=app.cfg["hop_over"], hops=sw.hops)
        if c == "insights":
            from . import analytics as _an
            days = max(1, min(int(cmd.get("days", 30) or 30), 3650))
            if not app.hist.sessions:
                app.hist.scan()
            s_ = app.hist.summary(days)
            return self.reply(cmd, days=days, total=s_["total"], sessions=s_["sessions"],
                              tips=[[ic, tx] for ic, tx in _an.insights(app.hist.sessions, app.hist.name, days, app.net.dc_map)])
        if c == "analytics":
            from . import charts
            days = max(1, min(int(cmd.get("days", 30) or 30), 3650))
            if not app.hist.sessions:
                app.hist.scan()
            path = os.path.join(RES_DIR, f"{cmd['id']}.png")
            with open(path, "wb") as f:
                f.write(charts.analytics_card(app.hist, days))
            s = app.hist.summary(days)
            return self.reply(cmd, image=path, days=days, total=s["total"], sessions=s["sessions"],
                              disconnects=len(s["disconnects"]), archive=len(app.hist.sessions))
        if c == "sysinfo":
            m = app.sys
            from . import sysmon as _sm
            return self.reply(cmd, cur=m.cur, avg5={k: m.avg(k, 300) for k in ("cpu", "ram", "gpu", "gpu_temp")},
                              minutes=len(m.hist) * m.EVERY // 60, top=[(n, round(mb)) for n, mb, _ in _sm.top_processes(5)])
        if c == "reset":
            n = eng.reset_character()
            return self.reply(cmd, msg=f"สั่งรีเซ็ตตัวละคร {n} หน้าต่างแล้ว" if n else "ไม่เจอหน้าต่าง Roblox", windows=n)
        if c == "fps":
            lim = cmd.get("limit")
            if lim is not None:
                app.cfg["fps_cap_on"] = int(lim) > 0
                if int(lim) > 0:
                    app.cfg["fps_cap"] = int(lim)
                config.save(app.cfg)
                app.ui(lambda: app.pages["sys"].reload_fps())
            return self.reply(cmd, on=app.cfg["fps_cap_on"], limit=app.cfg["fps_cap"], capping=app.fps.capping,
                              msg=(f"จำกัด FPS ที่ {app.cfg['fps_cap']} แล้ว" if app.cfg["fps_cap_on"] else "ปิดการจำกัด FPS แล้ว"))
        if c == "quiet":
            cur = eng.watcher.current
            place = cmd.get("place") or cur.get("place") or eng.last_place
            if not place:
                return self.reply(cmd, ok=False, msg="ยังไม่รู้ว่าเล่นเกมไหนอยู่ — เข้าเกมก่อน")
            if eng.rejoining:
                return self.reply(cmd, ok=False, msg="กำลังต่อเกมอยู่ รอสักครู่")
            app.swatch.go(place, exclude=cur.get("job"))
            return self.reply(cmd, msg="กำลังหาเซิร์ฟที่คนน้อยสุดแล้วย้ายให้ (ประมาณ 1 นาที)")
        if c == "timer":
            try:
                mins = max(1, int(float(cmd.get("minutes", 0))))
            except (TypeError, ValueError):
                return self.reply(cmd, ok=False, msg="จำนวนนาทีไม่ถูกต้อง")
            act = cmd.get("action") or "หยุด Anti-AFK"
            if act not in app.TIMER_ACTIONS:
                return self.reply(cmd, ok=False, msg="action ต้องเป็น: " + " / ".join(app.TIMER_ACTIONS))
            app.ui(lambda: app.set_timer(mins, act))
            return self.reply(cmd, msg=f"ตั้งเวลาแล้ว: อีก {mins} นาที → {act}", timer_end=time.time() + mins * 60)
        if c == "timer_cancel":
            had = bool(app.timer_end)
            app.ui(lambda: app.set_timer(0, None))
            return self.reply(cmd, msg="ยกเลิกตั้งเวลาแล้ว" if had else "ไม่มีตั้งเวลาค้างอยู่")
        if c == "power":
            act = cmd.get("action")
            if act not in ("sleep", "shutdown", "close_roblox", "cancel"):
                return self.reply(cmd, ok=False, msg="action ต้องเป็น sleep / shutdown / close_roblox / cancel")
            app.ui(lambda: app.power(act, "Discord"))
            return self.reply(cmd, msg={"sleep": "กำลังปิด Roblox แล้ว Sleep เครื่อง", "shutdown": "กำลังปิด Roblox แล้วปิดเครื่องใน 30 วิ (ยกเลิกได้ด้วย power cancel)",
                                        "close_roblox": "ปิด Roblox แล้ว", "cancel": "ยกเลิกการปิดเครื่องแล้ว"}[act])
        if c == "log":
            n = max(1, min(int(cmd.get("n", 20) or 20), 100))
            return self.reply(cmd, lines=list(app.log_lines)[-n:])
        if c == "quit":
            app.ui(app.on_close)
            return self.reply(cmd, msg="กำลังปิด Toolkit")
        return self.reply(cmd, ok=False, msg=f"ไม่รู้จักคำสั่ง {c}")
