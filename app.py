"""Roblox Toolkit — Anti-AFK · สถิติการเล่น · เช็คเน็ต · ตรวจไฟล์ · สุขภาพระบบ
รัน:  python app.py            (เปิดหน้าต่าง)
      python app.py --tray     (เริ่มแบบซ่อนใน tray)
      python app.py --afk      (เริ่ม Anti-AFK ทันที — Bloxstrap integration ใช้อันนี้)
"""
import os
import queue
import sys
from collections import deque
import threading
import time
import webbrowser
from tkinter import filedialog

import customtkinter as ctk

from core import analytics, bridge, charts, clicker, config, doctor, filecheck, health, ipc, launcher, macro, notify, schedule, screenwatch, servers, session, sysmon, updater
from core import fastflag, fpscap, ui
from core.antiafk import Engine, reason_text
from core.history import History, fmt_dur, fmt_reason
from core import netmon
from core.netmon import TARGETS, NetMonitor
from core.overlay import Overlay
from core.watchdog import Watchdog
from core.win import VK_F4, VK_F5, VK_F6, VK_F7, VK_F8, VK_F9, SW_MINIMIZE, display_info, dpi_aware, hotkey_loop, kill_pid, roblox_pids, roblox_windows, set_refresh, u
from core.ipc import grab_window

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None

dpi_aware()
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")
ui.install()

# สี/ฟอนต์ทั้งหมดอยู่ที่ core/ui.py — แก้ที่นั้นที่เดียวเปลี่ยนทั้งโปรแกรม
from core.ui import (ACC, ACC2, ACC3, BAD, BADBG, BADT, BG, BTN, BTNH, CARD, CARD2, DANGER, DANGERH, DIM,
                     F, FB, FBIG, FH, FH2, FH3, FHUGE, FMB, FS, FSB, FTINY, FTITLE, INFO, INK, LINE, MONO,
                     OKBG, SIDE, TXT, TXT2, WARN, YEL)

LEVEL_COLOR = {"green": ACC, "yellow": YEL, "orange": WARN, "red": BAD, "gray": DIM, "ok": ACC, "warn": WARN, "bad": BAD}
STORE_PY = "WindowsApps" in sys.executable and not getattr(sys, "frozen", False)


def tray_image(running):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, 62, 62), fill=(46, 230, 168, 255) if running else (110, 110, 130, 255))
    d.ellipse((20, 20, 44, 44), fill=(18, 18, 26, 255))
    return img


class Page(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

    def on_show(self):
        pass


# =====================================================================
class WatchPage(Page):
    """👁 เฝ้าจอ — OCR หน้าต่างเกมหาคำที่ตั้งไว้ (ชื่อไข่/ของหายาก) แล้วแจ้งเตือน ไม่ต้องนั่งเฝ้า/ไม่ต้องรีเซิร์ฟ"""

    def __init__(self, master, app):
        super().__init__(master, app)
        c = app.cfg
        ui.head(self, "เฝ้าจอ — เตือนเมื่อเห็นคำที่ต้องการบนจอเกม",
                "ถ่ายหน้าต่าง Roblox ทุกไม่กี่วิ แล้วให้ Windows อ่านตัวหนังสือ (OCR) · เจอชื่อไข่/ของหายากที่ตั้งไว้ → เสียง + แจ้งเตือน + ส่งรูปเข้า Discord · ไม่แตะตัวเกม", "👁")
        top = ui.card(self)
        top.pack(fill="x", padx=20, pady=(6, 8))
        self.v_on = ctk.BooleanVar(value=bool(c.get("watch_on")))
        ui.switch_row(top, "เปิดเฝ้าจอ", self.v_on, "ทำงานตอนมีหน้าต่าง Roblox เท่านั้น · ถ้าย่อหน้าต่างจะถ่ายไม่ได้ — ใช้ปุ่ม 'ซ่อน' ในหน้า Anti-AFK แทนการย่อ", cmd=self.apply, pady=(10, 2))
        row = ui.row(top)
        row.pack(fill="x", padx=16, pady=(4, 10))
        ctk.CTkLabel(row, text="ทุก", font=F).pack(side="left")
        self.v_iv = ctk.StringVar(value=str(c.get("watch_interval", 8)))
        ctk.CTkEntry(row, textvariable=self.v_iv, width=50, font=F, justify="center").pack(side="left", padx=6)
        ctk.CTkLabel(row, text="วิ   ·   เจอคำเดิมซ้ำ เตือนอีกครั้งหลัง", font=F).pack(side="left")
        self.v_cd = ctk.StringVar(value=str(c.get("watch_cooldown", 120)))
        ctk.CTkEntry(row, textvariable=self.v_cd, width=60, font=F, justify="center").pack(side="left", padx=6)
        ctk.CTkLabel(row, text="วิ", font=F).pack(side="left")
        self.v_beep = ctk.BooleanVar(value=c.get("watch_beep", True))
        ctk.CTkSwitch(row, text="เสียงเตือน", variable=self.v_beep, font=F, command=self.apply).pack(side="right")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        left = ui.card(body)
        left.pack(side="left", fill="both", expand=True)
        ui.title(left, "คำที่ต้องการ (บรรทัดละคำ · ไม่สนตัวพิมพ์เล็ก-ใหญ่)")
        ui.note(left, "ตัวอย่างสำหรับ Steal An Egg: ชื่อระดับความหายาก หรือชื่อไข่ตัวที่อยากได้ — ดูคำที่อ่านได้จริงจากปุ่ม 'อ่านจอตอนนี้' แล้วก๊อปมาใส่")
        self.t_words = ctk.CTkTextbox(left, font=F, height=180)
        self.t_words.pack(fill="both", expand=True, padx=14, pady=(4, 6))
        self.t_words.insert("1.0", "\n".join(c.get("watch_words") or []))
        ctk.CTkButton(left, text="💾 บันทึกคำ", font=FB, height=32, command=self.apply).pack(anchor="w", padx=14, pady=(0, 12))

        right = ui.card(body, width=420)
        right.pack(side="left", fill="both", padx=(10, 0))
        right.pack_propagate(False)
        ui.title(right, "สถานะ")
        self.l_state = ctk.CTkLabel(right, text="", font=F, text_color=DIM, justify="left", anchor="w", wraplength=380)
        self.l_state.pack(fill="x", padx=14)
        ctk.CTkButton(right, text="🔍 อ่านจอตอนนี้ (ดูว่า OCR เห็นอะไร)", font=FB, height=32, command=self.read_now).pack(anchor="w", padx=14, pady=(8, 4))
        self.t_seen = ctk.CTkTextbox(right, font=FS, height=150, text_color=TXT2)
        self.t_seen.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        ui.title(right, "เจอล่าสุด")
        self.t_hits = ctk.CTkTextbox(right, font=FS, height=110, text_color=TXT2)
        self.t_hits.pack(fill="x", padx=14, pady=(0, 6))
        ctk.CTkButton(right, text="📂 เปิดโฟลเดอร์รูปที่เจอ", font=FS, height=28, fg_color=BTN, hover_color=BTNH,
                      command=lambda: os.startfile(screenwatch.DIR)).pack(anchor="w", padx=14, pady=(0, 12))

    def apply(self):
        words = [w.strip() for w in self.t_words.get("1.0", "end").splitlines() if w.strip()]
        try:
            iv, cd = int(self.v_iv.get()), int(self.v_cd.get())
        except ValueError:
            iv, cd = 8, 120
        self.app.cfg["watch_beep"] = self.v_beep.get()
        self.app.watch.configure(on=self.v_on.get(), words=words, interval=iv, cooldown=cd)
        self.app.log(f"👁 เฝ้าจอ: {'เปิด' if self.v_on.get() else 'ปิด'} · {len(words)} คำ · ทุก {self.app.watch.interval} วิ")
        self.refresh()

    def read_now(self):
        self.t_seen.delete("1.0", "end")
        self.t_seen.insert("1.0", "กำลังอ่าน...")

        def work():
            try:
                lines, _ = self.app.watch.read_once()
                self.app.watch.last_text, self.app.watch.last_at, self.app.watch.last_err = lines, time.time(), None
                txt = "\n".join(lines) if lines else "(ไม่เจอตัวหนังสือที่อ่านได้)"
            except Exception as e:
                txt = f"อ่านไม่ได้: {e}"
            self.app.ui(lambda: (self.t_seen.delete("1.0", "end"), self.t_seen.insert("1.0", txt), self.refresh()))
        threading.Thread(target=work, daemon=True).start()

    def refresh(self):
        w = self.app.watch
        self.v_on.set(w.enabled)
        if not w.enabled:
            st, col = "○ ปิดอยู่", DIM
        elif w.last_err:
            st, col = f"⚠ {w.last_err}", WARN
        elif w.last_at:
            rs = ""
            if w.reset_at:
                d = int(w.reset_at - time.time())
                rs = f" · 🔥 ช่วงรีเซ็ต สแกนถี่" if -5 <= -d <= 45 else (f" · รีเซ็ตเกมอีก {d // 60}:{d % 60:02d}" if d > 0 else "")
            st, col = f"● กำลังเฝ้า · อ่านล่าสุด {int(time.time() - w.last_at)} วิที่แล้ว ({w.last_ms} ms) · สแกนแล้ว {w.scans} ครั้ง · {len(w.words)} คำ{rs}", ACC
        else:
            st, col = "● กำลังเริ่ม...", ACC
        self.l_state.configure(text=st, text_color=col)
        self.t_hits.delete("1.0", "end")
        self.t_hits.insert("1.0", "\n".join(f"{time.strftime('%H:%M:%S', time.localtime(h['t']))}  {h['word']}  —  {h['line']}" for h in list(w.hits)[:8]) or "ยังไม่เจอ")

    def on_show(self):
        self.refresh()

    def tick(self):
        self.refresh()


# =====================================================================
class HomePage(Page):
    """หน้าแรก — บอกสถานะด้วยภาษาคน + ปุ่มโหมดสำเร็จรูปที่ตั้งค่าให้ครบในคลิกเดียว

    เหตุผลที่ต้องมี: โปรแกรมโตจนมี 10 หน้า สวิตช์เป็นสิบ ถ้าไม่มีทางลัดคนจะไม่กล้าใช้
    """

    # ชื่อโหมด -> (ไอคอน, คำอธิบาย, ค่าที่จะตั้ง, สิ่งที่ต้องทำเพิ่ม)
    PRESETS = [
        ("ฟาร์มทั้งคืน", "🌙", "ทิ้งไว้ข้ามคืน — ซ่อนเกม ปิดเสียง หรี่ FPS เหลือ 5 ต่อเน็ตเองถ้าหลุด",
         {"invisible": True, "wait_idle": True, "auto_rejoin": True, "watchdog": True, "crash_relaunch": True,
          "fps_cap_on": True, "fps_cap": 5, "fps_unlock_focus": True, "automute": True, "game_mode": True,
          "notify_disconnect": True, "notify_rejoin": True, "sys_alerts": True}, "afk_hide"),
        ("ฟาร์มแบบดูไปด้วย", "👀", "เล่นอย่างอื่นไปด้วย — ไม่ซ่อนเกม ไม่หรี่ FPS ยังได้ยินเสียง",
         {"invisible": True, "wait_idle": True, "auto_rejoin": True, "watchdog": True,
          "fps_cap_on": False, "automute": False, "game_mode": False}, "afk_only"),
        ("เล่นเองปกติ", "🎮", "หยุดทุกอย่าง คืนเสียง คืน FPS เอาหน้าต่างกลับมา",
         {"fps_cap_on": False, "automute": False, "game_mode": False}, "stop_all"),
        ("เลิกเล่น ปิดเกม", "💤", "หยุด Anti-AFK แล้วปิด Roblox ให้เรียบร้อย",
         {"fps_cap_on": False, "automute": False}, "close_game"),
    ]

    def __init__(self, master, app):
        super().__init__(master, app)
        ctk.CTkLabel(self, text=f"Roblox Toolkit", font=FTITLE, text_color=ACC).pack(anchor="w", padx=22, pady=(16, 0))
        ctk.CTkLabel(self, text="เลือกโหมดที่ตรงกับที่จะทำ แล้วกดปุ่มเดียวจบ — ปรับละเอียดได้ที่เมนูด้านซ้าย",
                     font=FS, text_color=DIM).pack(anchor="w", padx=22)

        st = ctk.CTkFrame(self, fg_color=CARD, corner_radius=14)
        st.pack(fill="x", padx=20, pady=12)
        self.l_big = ctk.CTkLabel(st, text="กำลังตรวจสอบ...", font=FH3, justify="left")
        self.l_big.pack(anchor="w", padx=18, pady=(14, 2))
        self.l_sub = ctk.CTkLabel(st, text="", font=F, text_color=DIM, justify="left")
        self.l_sub.pack(anchor="w", padx=18, pady=(0, 14))

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=20)
        grid.grid_columnconfigure((0, 1), weight=1, uniform="p")
        grid.grid_rowconfigure((0, 1), weight=1, uniform="q")
        self.cards, self.btns = {}, {}
        for i, (name, icon, desc, _, _) in enumerate(self.PRESETS):
            f = ctk.CTkFrame(grid, fg_color=CARD, corner_radius=14, border_width=2, border_color=CARD)
            f.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
            ctk.CTkLabel(f, text=f"{icon}  {name}", font=FH3).pack(anchor="w", padx=16, pady=(14, 2))
            ctk.CTkLabel(f, text=desc, font=FS, text_color=DIM, justify="left", wraplength=330).pack(anchor="w", padx=16)
            b = ctk.CTkButton(f, text="ใช้โหมดนี้", height=38, font=FB, fg_color=BTN, hover_color=BTNH,
                              command=lambda n=name: self.apply(n))
            b.pack(fill="x", padx=16, pady=(10, 16), side="bottom")
            self.cards[name], self.btns[name] = f, b

        # ---------- สรุปวันนี้ ----------
        stat = ctk.CTkFrame(self, fg_color=CARD, corner_radius=14)
        stat.pack(fill="x", padx=20, pady=(0, 10), before=grid)
        stat.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="s")
        self.stats = {}
        for i, (key, label) in enumerate((("play", "เล่นวันนี้"), ("rounds", "จำนวนรอบ"),
                                          ("drop", "หลุดวันนี้"), ("next", "คิวถัดไป"))):
            cell = ctk.CTkFrame(stat, fg_color="transparent")
            cell.grid(row=0, column=i, sticky="nsew", pady=(12, 10))
            v = ctk.CTkLabel(cell, text="—", font=FH3, text_color=TXT)
            v.pack()
            ctk.CTkLabel(cell, text=label, font=FS, text_color=DIM).pack()
            self.stats[key] = v
        self._stat_at = 0

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(4, 14))
        ctk.CTkButton(row, text="📸 ถ่ายรูปเกมส่งเข้า Discord", font=F, height=34, fg_color=BTN, hover_color=BTNH,
                      command=self.snap).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="🔀 ย้ายไปเซิร์ฟคนน้อย", font=F, height=34, fg_color=BTN, hover_color=BTNH,
                      command=self.quiet).pack(side="left", padx=8)
        ctk.CTkButton(row, text="🔄 รีเซ็ตตัวละคร", font=F, height=34, fg_color=BTN, hover_color=BTNH,
                      command=lambda: threading.Thread(target=app.eng.reset_character, daemon=True).start()).pack(side="left", padx=8)
        ctk.CTkButton(row, text="🩺 ทำไมไม่ลื่น? ตรวจเลย", font=FB, height=34, command=self.doctor).pack(side="left", padx=8)
        self.l_hint = ctk.CTkLabel(self, text="", font=FS, text_color=DIM)
        self.l_hint.pack(anchor="w", padx=22, pady=(0, 10))

    # ---------- หมอเครื่อง ----------
    def trim_ram(self):
        n, freed, b, a = sysmon.trim_ram()
        msg = f"คืนแรมแล้ว: {n} โปรเซส · ว่างเพิ่ม {freed:.0f} MB ({b:.0f}% → {a:.0f}%)"
        self.app.log("🧹 " + msg)
        self.app.game_events.insert(0, (time.time(), msg))
        notify.toast("คืนแรม", msg + " · ผลชั่วคราว — โปรแกรมอื่นจะค่อยๆ ใช้คืน")

    def doctor(self):
        app = self.app
        win = ctk.CTkToplevel(app)
        win.title("ทำไมเกมไม่ลื่น?")
        win.geometry("760x560")
        win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="🩺 กำลังตรวจ...", font=FH2, text_color=TXT).pack(anchor="w", padx=20, pady=(16, 4))
        body = ctk.CTkScrollableFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        ICON = {"ok": ("✅", ACC), "warn": ("⚠", WARN), "bad": ("❌", BAD), "info": ("ℹ", INFO)}
        FIX = {"hz": ("ใช้ Hz สูงสุด", lambda: app.pages["flag"].max_hz()),
               "ff": ("ตั้ง FastFlag แนะนำ", lambda: (app.show("flag"), app.pages["flag"].recommend())),
               "pri": ("เปิด High priority", lambda: (app.pages["flag"].v_pri.set(True), app.pages["flag"].set_pri())),
               "bb": ("ไปหน้าเน็ต", lambda: app.show("net")),
               "od": ("เปิดหยุด OneDrive", lambda: (app.cfg.__setitem__("pause_onedrive", True), config.save(app.cfg), app.pages["net"].v_od.set(True))),
               "gpu": ("เปิดหน้าตั้งค่า Windows", lambda: os.startfile("ms-settings:display-advancedgraphics")),
               "ram": ("คืนแรม (ชั่วคราว)", lambda: threading.Thread(target=self.trim_ram, daemon=True).start()),
               "auto": ("เปิดพร้อม Windows", lambda: (health.autostart_set(True), app.log("ตั้งค่าเปิดพร้อม Windows แล้ว")))}

        def show(items, summary):
            for w in win.winfo_children():
                if isinstance(w, ctk.CTkLabel):
                    w.configure(text=f"🩺 {summary}")
            for it in items:
                ic, col = ICON.get(it["level"], ("•", DIM))
                card = ctk.CTkFrame(body, fg_color=CARD, corner_radius=12)
                card.pack(fill="x", pady=3)
                top = ui.row(card)
                top.pack(fill="x", padx=12, pady=(8, 0))
                ctk.CTkLabel(top, text=f"{ic}  {it['title']}", font=FB, text_color=col, anchor="w").pack(side="left")
                if it.get("fix") in FIX and it["level"] != "ok":
                    label, fn = FIX[it["fix"]]
                    ctk.CTkButton(top, text=label, width=150, height=28, font=FS,
                                  command=lambda fn=fn, c=card: (fn(), c.configure(border_width=2, border_color=ACC))).pack(side="right")
                if it.get("detail"):
                    ctk.CTkLabel(card, text=it["detail"], font=FS, text_color=DIM, justify="left", wraplength=640, anchor="w").pack(fill="x", padx=14, pady=(0, 8))
                else:
                    ctk.CTkLabel(card, text="", height=4).pack()

        def work():
            try:
                items, summary = doctor.run(app)
            except Exception as e:
                items, summary = [dict(key="err", level="bad", title=f"ตรวจไม่ได้: {e}", detail="", fix=None)], "ตรวจไม่สำเร็จ"
            app.ui(lambda: show(items, summary))
        threading.Thread(target=work, daemon=True).start()

    # ---------- ปุ่มด่วน ----------
    def snap(self):
        def work():
            from core import ipc as _ipc
            wins = roblox_windows(True) + [h for h in self.app.eng.hidden if u.IsWindow(h)]
            if not wins:
                return self.app.log("ไม่เจอหน้าต่าง Roblox")
            path = os.path.join(config.DATA_DIR, "snap.png")
            ok, msg = _ipc.screenshot_window(wins[0], path)
            if not ok:
                return self.app.log(f"ถ่ายไม่ได้: {msg}")
            if self.app.cfg["webhook_url"]:
                session.webhook_image(self.app.cfg["webhook_url"], open(path, "rb").read(), "📸 หน้าจอตอนนี้", "snap.png")
                self.app.log("ส่งรูปเข้า Discord แล้ว")
            else:
                self.app.ui(lambda: os.startfile(path))
                self.app.log("ยังไม่ได้ตั้ง webhook — เปิดรูปให้ดูแทน")
        threading.Thread(target=work, daemon=True).start()

    def quiet(self):
        cur = self.app.eng.watcher.current
        place = cur.get("place") or self.app.eng.last_place
        if not place:
            return self.app.log("ยังไม่รู้ว่าอยู่เกมไหน — เข้าเกมก่อน")
        self.app.swatch.go(place, exclude=cur.get("job"))

    # ---------- โหมดสำเร็จรูป ----------
    def apply(self, name):
        preset = next(p for p in self.PRESETS if p[0] == name)
        _, _, _, values, extra = preset
        app = self.app
        app.sync_cfg()
        app.cfg.update(values)
        config.save(app.cfg)
        app.apply_cfg_to_engine()
        app.cfg["last_preset"] = name
        app.log(f"⚡ เปลี่ยนเป็นโหมด: {name}")

        if extra == "afk_hide":
            if not app.eng.running:
                app.eng.start(app.cfg["immediate"])
            threading.Thread(target=self.hide_later, daemon=True).start()
        elif extra == "afk_only":
            app.eng.unhide_all()
            if not app.eng.running:
                app.eng.start(app.cfg["immediate"])
        elif extra == "stop_all":
            app.eng.stop()
            app.eng.unhide_all()
        elif extra == "close_game":
            app.eng.stop()
            app.power("close_roblox", "โหมดเลิกเล่น")
        threading.Thread(target=lambda: fpscap.set_roblox_muted(app.cfg["automute"]), daemon=True).start()
        app.refresh_all_pages()

    def hide_later(self):
        """ย่อแล้วซ่อนหน้าต่างเกมให้ (ต้องรอให้ Anti-AFK กดครั้งแรกเสร็จก่อน)"""
        time.sleep(2)
        for h in roblox_windows(True):
            u.ShowWindow(h, SW_MINIMIZE)
        time.sleep(0.6)
        n = self.app.eng.hide_minimized()
        self.app.log(f"ซ่อนหน้าต่างเกมแล้ว ({n})" if n else "ไม่มีหน้าต่างให้ซ่อน (เปิดเกมก่อน)")

    # ---------- สถานะ ----------
    def tick(self):
        app, e, c = self.app, self.app.eng, self.app.cfg
        cur = e.watcher.current
        game = app.place_name(cur.get("place")) if cur.get("in_game") else None
        if e.rejoining:
            head, col = "🔄  กำลังต่อกลับเข้าเกม...", WARN
        elif e.running:
            nxt = max(0, int(e.next_at - time.time()))
            head, col = f"🟢  Anti-AFK ทำงานอยู่ · กดอีกครั้งใน {nxt // 60}:{nxt % 60:02d}", ACC
        elif game:
            head, col = "⚪  อยู่ในเกมแต่ Anti-AFK ปิดอยู่", DIM
        else:
            head, col = "⚪  ยังไม่ได้เริ่ม", DIM
        self.l_big.configure(text=head, text_color=col)

        bits = [f"🎮 {game}" if game else "🎮 ยังไม่ได้อยู่ในเกม"]
        sw = app.swatch
        if sw.players is not None:
            bits.append(f"👥 {sw.players}/{sw.maxp} คนในเซิร์ฟ")
        st = app.net.stats("อินเทอร์เน็ต", 60) or {}
        if st.get("avg") is not None:
            bits.append(f"📶 {int(st['avg'])} ms" + (f" · หาย {st['loss']:.0f}%" if st.get("loss") else ""))
        sysc = app.sys.cur
        if sysc.get("gpu_temp") is not None:
            bits.append(f"🌡 GPU {sysc['gpu_temp']:.0f}°C")
        if sysc.get("ram") is not None:
            bits.append(f"💾 RAM {sysc['ram']:.0f}%")
        if c["fps_cap_on"]:
            bits.append(f"🐢 จำกัด {c['fps_cap']} FPS" + (" (กำลังหรี่)" if app.fps.capping else ""))
        if e.hidden:
            bits.append(f"🙈 ซ่อน {len(e.hidden)} หน้าต่าง")
        nx = app.sched.next_job()
        if nx:
            bits.append(f"🔁 {nx[0]} → {nx[1]}")
        self.l_sub.configure(text="   ·   ".join(bits))

        if time.time() - self._stat_at > 10:
            self._stat_at = time.time()
            try:
                if app.hist.loading:
                    self.stats["play"].configure(text="...")
                else:
                    sm = app.hist.summary(1)
                    self.stats["play"].configure(text=fmt_dur(sm["total"]) if sm["total"] else "—")
                    self.stats["rounds"].configure(text=str(sm["sessions"]))
                    self.stats["drop"].configure(text=str(len(sm["disconnects"])),
                                                 text_color=BAD if sm["disconnects"] else TXT)
                nj = app.sched.next_job()
                self.stats["next"].configure(text=(f"{nj[0]}  {nj[1]}" if nj else "—"),
                                             font=FB if nj else FH3)
            except Exception as ex:
                config.dbg(f"home stats: {ex}")

        last = c.get("last_preset")
        for name, f in self.cards.items():
            on = name == last
            f.configure(border_color=ACC if on else CARD)
            self.btns[name].configure(fg_color=ACC2 if on else BTN, hover_color=ACC3 if on else BTNH,
                                      text="●  กำลังใช้โหมดนี้" if on else "ใช้โหมดนี้")
        self.l_hint.configure(text=f"โหมดล่าสุดที่ใช้: {last}" if last else "เคล็ดลับ: F8 เริ่ม/หยุด Anti-AFK ได้จากทุกที่ · F6 ออโต้คลิก · F9 overlay")


# =====================================================================
class AfkPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)
        e, c = app.eng, app.cfg
        self.v_delay = ctk.IntVar(value=min(c["delay"], 900))
        self.v_action = ctk.StringVar(value=c["action"])
        self.vars = {k: ctk.BooleanVar(value=c[k]) for k in ("wait_idle", "auto_rejoin", "invisible", "immediate")}

        ctk.CTkLabel(self, text="ANTI-AFK", font=FH, text_color=ACC).pack(anchor="w", padx=20, pady=(16, 0))
        ctk.CTkLabel(self, text="F8 = เริ่ม/หยุด จากทุกที่", font=FS, text_color=DIM).pack(anchor="w", padx=20)

        # แบ่ง 2 คอลัมน์ ไม่งั้นเนื้อหายาวเกินจอ (ซ้าย = ควบคุม · ขวา = เวลา/ตาราง/log)
        cols = ctk.CTkFrame(self, fg_color="transparent")
        cols.pack(fill="both", expand=True, padx=16, pady=(10, 12))
        cols.grid_columnconfigure((0, 1), weight=1, uniform="c")
        cols.grid_rowconfigure(0, weight=1)
        colL = ctk.CTkFrame(cols, fg_color="transparent")
        colL.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        colR = ctk.CTkFrame(cols, fg_color="transparent")
        colR.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        card = ctk.CTkFrame(colL, fg_color=CARD, corner_radius=14)
        card.pack(fill="x")
        self.l_found = ctk.CTkLabel(card, text="GAME: ...", font=FB)
        self.l_found.pack(pady=(14, 0))
        self.l_state = ctk.CTkLabel(card, text="SYSTEM: หยุด", font=FB, text_color=DIM)
        self.l_state.pack()
        self.btn = ctk.CTkButton(card, text="เริ่มทำงาน", font=FH3, height=52, width=260,
                                 fg_color="transparent", border_width=2, border_color=ACC, text_color=ACC,
                                 hover_color=OKBG, command=app.toggle_afk)
        self.btn.pack(pady=10)
        self.l_next = ctk.CTkLabel(card, text="", font=FS, text_color=DIM)
        self.l_next.pack(pady=(0, 10))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 6))
        self.l_delay = ctk.CTkLabel(row, text="", font=F)
        self.l_delay.pack(side="left")
        ctk.CTkSlider(card, from_=60, to=900, number_of_steps=28, variable=self.v_delay, command=lambda _: self.upd_delay()).pack(fill="x", padx=20)
        self.upd_delay()

        r2 = ctk.CTkFrame(card, fg_color="transparent")
        r2.pack(pady=8)
        ctk.CTkLabel(r2, text="ทำอะไร:", font=F).pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(r2, text="กระโดด (Space)", value="jump", variable=self.v_action, command=app.sync_cfg, font=F).pack(side="left", padx=6)
        ctk.CTkRadioButton(r2, text="ซูมกล้อง (I/O) ไม่ขยับตัว", value="camera", variable=self.v_action, command=app.sync_cfg, font=F).pack(side="left", padx=6)

        g = ctk.CTkFrame(card, fg_color="transparent")
        g.pack(pady=(0, 10))
        labels = {"wait_idle": "รอให้คุณว่างมือก่อนกด (3 วิ)", "auto_rejoin": "ต่อใหม่อัตโนมัติเมื่อหลุด",
                  "invisible": "ล่องหนตอนเด้งขึ้นมา", "immediate": "กดทันทีตอนเริ่ม"}
        for i, (k, t) in enumerate(labels.items()):
            ctk.CTkSwitch(g, text=t, variable=self.vars[k], command=app.sync_cfg, font=F).grid(row=i // 2, column=i % 2, sticky="w", padx=12, pady=3)

        hide = ctk.CTkFrame(colL, fg_color=CARD, corner_radius=14)
        hide.pack(fill="x", pady=(8, 0))
        hr = ctk.CTkFrame(hide, fg_color="transparent")
        hr.pack(fill="x", padx=14, pady=(10, 2))
        ctk.CTkLabel(hr, text="โหมดซ่อน — เร็วสุด ไม่กระพริบเลย: ย่อ Roblox ก่อน แล้วกดซ่อน", font=FS, text_color=DIM).pack(side="left")
        self.l_hidden = ctk.CTkLabel(hr, text="ซ่อนอยู่: 0", font=FS, text_color=DIM)
        self.l_hidden.pack(side="right")
        hb = ctk.CTkFrame(hide, fg_color="transparent")
        hb.pack(fill="x", padx=14, pady=(2, 12))
        ctk.CTkButton(hb, text="ซ่อนเกม", command=self.hide, font=F, height=34).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(hb, text="เอากลับมา", fg_color=BTN, hover_color=BTNH, command=self.unhide, font=F, height=34).pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(hb, text="🔄 รีเซ็ตตัวละคร", font=F, height=34, fg_color=BTN, hover_color=BTNH,
                      command=lambda: threading.Thread(target=app.eng.reset_character, daemon=True).start()).pack(side="left", fill="x", expand=True, padx=(4, 0))

        srv = ctk.CTkFrame(colL, fg_color=CARD, corner_radius=14)
        srv.pack(fill="x", pady=(8, 0))
        self.l_srv = ctk.CTkLabel(srv, text="🌐 เซิร์ฟ: —", font=F, justify="left", anchor="w", wraplength=430)
        self.l_srv.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkButton(srv, text="🔀  ย้ายไปเซิร์ฟที่คนน้อยสุด", font=F, height=34, command=self.go_quiet).pack(fill="x", padx=14, pady=(0, 12))

        tm = ctk.CTkFrame(colR, fg_color=CARD, corner_radius=14)
        tm.pack(fill="x")
        row = ctk.CTkFrame(tm, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(10, 2))
        ctk.CTkLabel(row, text="⏰  ตั้งเวลา: อีก", font=FB).pack(side="left")
        self.v_tmin = ctk.StringVar(value="60")
        ctk.CTkEntry(row, textvariable=self.v_tmin, width=54, font=F, justify="center").pack(side="left", padx=6)
        ctk.CTkLabel(row, text="นาที แล้วให้…", font=F).pack(side="left")
        self.l_timer = ctk.CTkLabel(row, text="", font=FS, text_color=DIM)
        self.l_timer.pack(side="right")
        row = ctk.CTkFrame(tm, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(2, 12))
        self.v_taction = ctk.StringVar(value="หยุด Anti-AFK")
        ctk.CTkOptionMenu(row, values=list(App.TIMER_ACTIONS), variable=self.v_taction, font=F).pack(side="left", fill="x", expand=True)
        self.bt_timer = ctk.CTkButton(row, text="เริ่มนับ", width=92, font=F, command=self.toggle_timer)
        self.bt_timer.pack(side="left", padx=(8, 0))

        sc = ctk.CTkFrame(colR, fg_color=CARD, corner_radius=14)
        sc.pack(fill="x", pady=(8, 0))
        row = ctk.CTkFrame(sc, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(8, 2))
        ctk.CTkLabel(row, text="🔁  ตารางเวลา (ทำซ้ำทุกวัน)", font=FB).pack(side="left")
        # ชื่อ l_sched ห้ามซ้ำกับ l_next ของการ์ดหลัก ไม่งั้นตัวหลังทับตัวแรก (บั๊กเดิม)
        self.l_sched = ctk.CTkLabel(sc, text="", font=FS, text_color=DIM, justify="left", wraplength=420)
        self.l_sched.pack(anchor="w", padx=14, pady=(0, 2))
        row = ctk.CTkFrame(sc, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkLabel(row, text="เวลา", font=F).pack(side="left")
        self.e_sctime = ctk.CTkEntry(row, width=62, font=F, justify="center", placeholder_text="23:00")
        self.e_sctime.pack(side="left", padx=6)
        self.v_scact = ctk.StringVar(value=schedule.ACTIONS[0])
        ctk.CTkOptionMenu(row, values=list(schedule.ACTIONS), variable=self.v_scact, font=F).pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(row, text="+ เพิ่ม", width=72, font=F, command=self.add_job).pack(side="left")
        self.sc_list = ctk.CTkFrame(sc, fg_color="transparent")
        self.sc_list.pack(fill="x", padx=14, pady=(0, 8))

        bottom = ctk.CTkFrame(colR, fg_color="transparent")
        bottom.pack(fill="both", expand=True, pady=(8, 0))
        self.log = ctk.CTkTextbox(bottom, height=150, font=MONO, fg_color=INK, text_color=DIM)
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")
        # พรีวิวย้ายมาอยู่คอลัมน์ซ้าย ใต้การ์ดควบคุม จะได้ไม่เบียดกับ log
        pv = ctk.CTkFrame(colL, fg_color=CARD, corner_radius=14, height=196)
        pv.pack(fill="x", pady=(8, 0))
        pv.pack_propagate(False)
        self.v_preview = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(pv, text="👁 พรีวิวหน้าจอ Roblox", variable=self.v_preview, font=FS, command=self.tick_preview).pack(anchor="w", padx=10, pady=(8, 2))
        self.l_preview = ctk.CTkLabel(pv, text="เปิดสวิตช์เพื่อดูหน้าจอเกม\n(เห็นแม้ตอนซ่อนหน้าต่างอยู่)", font=FS, text_color=DIM, justify="center")
        self.l_preview.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._pv_img = None
        self._pv_last = 0

    def apply_mute(self, mute):
        ok, n = fpscap.set_roblox_muted(mute)
        if ok and n:
            self.log(f"🔇 ปิดเสียง Roblox แล้ว ({n})" if mute else f"🔊 เปิดเสียง Roblox คืนแล้ว ({n})")
        elif not ok:
            self.log("ปิดเสียงไม่ได้ (ต้องมี pycaw — ลง build ใหม่)")

    # ---------- ตารางเวลา ----------
    def add_job(self):
        t = schedule.valid_time(self.e_sctime.get())
        if not t:
            return self.app.log("ใส่เวลาแบบ 23:00 นะ")
        jobs = self.app.cfg.setdefault("schedule", [])
        if len(jobs) >= 12:
            return self.app.log("ตั้งได้สูงสุด 12 รายการ")
        jobs.append({"time": t, "action": self.v_scact.get(), "on": True})
        jobs.sort(key=lambda j: j["time"])
        config.save(self.app.cfg)
        self.app.log(f"🔁 ตั้งไว้แล้ว: ทุกวัน {t} → {self.v_scact.get()}")
        self.refresh_jobs()

    def del_job(self, job):
        jobs = self.app.cfg.get("schedule") or []
        if job in jobs:
            jobs.remove(job)
            config.save(self.app.cfg)
            self.app.log(f"ลบตารางเวลา {job['time']} แล้ว")
        self.refresh_jobs()

    def toggle_job(self, job, var):
        job["on"] = var.get()
        config.save(self.app.cfg)
        self.refresh_jobs()

    def refresh_jobs(self):
        for w in self.sc_list.winfo_children():
            w.destroy()
        jobs = self.app.cfg.get("schedule") or []
        if not jobs:
            return ctk.CTkLabel(self.sc_list, text="ยังไม่ได้ตั้ง — ใส่เวลาแล้วเลือกว่าจะให้ทำอะไร เช่น ทุกวัน 23:00 เริ่ม Anti-AFK",
                                font=FS, text_color=DIM).pack(anchor="w")
        for job in list(jobs):
            r = ctk.CTkFrame(self.sc_list, fg_color="transparent")
            r.pack(fill="x", pady=1)
            v = ctk.BooleanVar(value=job.get("on", True))
            ctk.CTkSwitch(r, text="", width=38, variable=v, command=lambda j=job, vv=v: self.toggle_job(j, vv)).pack(side="left")
            ctk.CTkLabel(r, text=job["time"], font=FB, width=52, text_color=ACC if job.get("on", True) else DIM).pack(side="left")
            ctk.CTkLabel(r, text="→  " + job["action"], font=F, text_color=TXT2 if job.get("on", True) else DIM).pack(side="left")
            ctk.CTkButton(r, text="ลบ", width=40, height=24, font=FS, fg_color=DANGER, hover_color=DANGERH,
                          command=lambda j=job: self.del_job(j)).pack(side="right")

    def toggle_timer(self):
        app = self.app
        if app.timer_end:
            return app.set_timer(0, None)
        try:
            mins = max(1, int(float(self.v_tmin.get())))
        except ValueError:
            return app.log("ใส่จำนวนนาทีเป็นตัวเลข")
        app.set_timer(mins, self.v_taction.get())

    def tick_preview(self):
        """อัปเดตภาพพรีวิวทุก 2 วิ (เฉพาะตอนเปิดสวิตช์และอยู่หน้านี้)"""
        if not self.v_preview.get():
            return self._pv_text("เปิดสวิตช์เพื่อดูหน้าจอเกม\n(เห็นแม้ตอนซ่อนหน้าต่างอยู่)")
        if time.time() - self._pv_last < 2:
            return
        self._pv_last = time.time()
        e = self.app.eng
        wins = roblox_windows(True) + [h for h in e.hidden if u.IsWindow(h)]
        if not wins:
            return self._pv_text("ไม่เจอหน้าต่าง Roblox")
        img, msg = grab_window(wins[0])
        if img is None:
            return self._pv_text(msg)
        w = 280
        img = img.resize((w, max(1, int(img.height * w / img.width))))
        self._pv_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
        self.l_preview.configure(image=self._pv_img, text="")

    def _pv_text(self, msg):
        if self._pv_img is not None:      # tkinter ต้องส่ง image="" ถึงจะเอารูปออก (None = ไม่เปลี่ยน)
            self._pv_img = None
            self.l_preview.configure(image="")
        self.l_preview.configure(text=msg)

    def go_quiet(self):
        app = self.app
        cur = app.eng.watcher.current
        place = cur.get("place") or app.eng.last_place
        if not place:
            return app.log("ยังไม่รู้ว่าอยู่เกมไหน — เข้าเกมก่อนแล้วลองใหม่")
        app.log("กำลังหาเซิร์ฟที่คนน้อยสุด แล้วจะย้ายให้ (Roblox จะถูกปิดแล้วเปิดใหม่)")
        app.swatch.go(place, exclude=cur.get("job"))

    def upd_delay(self):
        d = int(self.v_delay.get())
        # Roblox เตะที่ไม่ขยับ 20 นาที · เผื่อเวลา "รอให้คุณว่างมือ" อีก 2 นาที → ปลอดภัยถ้าไม่เกิน 15 นาที
        left = 20 - (d + 120) / 60
        self.l_delay.configure(text=f"DELAY: {d} วิ  (~{d // 60} นาที)   ·   Roblox เตะที่ 20 นาที → เหลือกันชน {left:.0f} นาที",
                               text_color=ACC if left >= 3 else WARN)
        self.app.eng.delay = d
        self.app.cfg["delay"] = d

    def hide(self):
        n = self.app.eng.hide_minimized()
        self.app.log(f"ซ่อน {n} หน้าต่าง" if n else "ไม่เจอ Roblox ที่ย่ออยู่ — ย่อ Roblox ก่อนแล้วกดใหม่")

    def unhide(self):
        self.app.log(f"เอากลับมา {self.app.eng.unhide_all()} หน้าต่าง")

    def append_log(self, s):
        self.log.configure(state="normal")
        self.log.insert("end", time.strftime("%H:%M:%S ") + s + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def tick(self):
        e = self.app.eng
        n, h = len(roblox_windows(True)), len(e.hidden)
        cur = e.watcher.current
        try:
            self.tick_preview()
        except Exception as ex:
            self._pv_text(f"พรีวิวไม่ได้: {ex}")
        game = self.app.place_name(cur["place"]) if cur.get("in_game") and cur.get("place") else None
        if n or h:
            self.l_found.configure(text=f"GAME: {game or 'เจอ Roblox'}  ·  {n} หน้าต่าง" + (f" + ซ่อน {h}" if h else ""), text_color=ACC)
        else:
            self.l_found.configure(text="GAME: ยังไม่เจอ Roblox", text_color=BAD)
        self.l_hidden.configure(text=f"ซ่อนอยู่: {h}")
        sw, mx = self.app.swatch, self.app.cfg["hop_over"]
        wait = servers.limited()
        if not self.app.cfg["watch_players"]:
            self.l_srv.configure(text="🌐 เฝ้าเซิร์ฟ: ปิดอยู่ (เปิดได้ในหน้าตั้งค่า)", text_color=DIM)
        elif sw.players is not None:
            q = f"  ·  เงียบสุดที่หาได้ {sw.quiet} คน" if sw.quiet is not None else ""
            dcl = self.app.net.dc_label(self.app.eng.watcher.current.get("dc"), sw.ping)
            self.l_srv.configure(text=f"🌐 เซิร์ฟนี้: {sw.players}/{sw.maxp} คน · ping {sw.ping} ms{q}" + (f"  ·  {dcl.split(' · ', 1)[1]}" if dcl else ""),
                                 text_color=BAD if sw.players >= (sw.maxp or 32) * 0.8 else (WARN if sw.players > mx else ACC))
        elif sw.quiet is not None:
            self.l_srv.configure(text=f"🌐 เซิร์ฟเรา: ดูไม่ได้ (เกมใหญ่ ดูได้ทีละ {sw.sample} เซิร์ฟ)  ·  เงียบสุดที่หาได้ {sw.quiet}/{sw.maxp} คน",
                                 text_color=WARN)
        elif sw.sample:
            self.l_srv.configure(text=f"🌐 เกมนี้เซิร์ฟละ {sw.maxp} คน และเต็มหมดทุกเซิร์ฟที่ดูได้ ({sw.sample}) — ย้ายไปไหนก็ไม่ว่างกว่านี้",
                                 text_color=WARN)
        elif wait:
            self.l_srv.configure(text=f"🌐 Roblox จำกัดการเรียกข้อมูลเซิร์ฟ — ลองใหม่ในอีก {wait} วิ", text_color=DIM)
        else:
            self.l_srv.configure(text="🌐 เซิร์ฟ: ยังไม่รู้ (เข้าเกมแล้วรอไม่เกิน 1 นาที)", text_color=DIM)
        if e.rejoining:
            self.l_state.configure(text="SYSTEM: กำลังต่อใหม่...", text_color=WARN)
        elif e.running:
            self.l_state.configure(text="SYSTEM: ทำงานอยู่", text_color=ACC)
        else:
            self.l_state.configure(text="SYSTEM: หยุด", text_color=DIM)
        nx = self.app.sched.next_job()
        if nx:
            t, act, mins = nx
            self.l_sched.configure(text=f"ถัดไป: {t} → {act} (อีก {mins // 60} ชม. {mins % 60} นาที)" if mins >= 60 else f"ถัดไป: {t} → {act} (อีก {mins} นาที)")
        else:
            self.l_sched.configure(text="ยังไม่ได้ตั้งตารางเวลา")
        if self.app.timer_end:
            r = max(0, int(self.app.timer_end - time.time()))
            self.l_timer.configure(text=f"เหลือ {r // 60:02d}:{r % 60:02d} → {self.app.timer_action}", text_color=WARN)
            self.bt_timer.configure(text="ยกเลิก")
        else:
            self.l_timer.configure(text="")
            self.bt_timer.configure(text="เริ่มนับ")
        if e.running:
            r = max(0, int(e.next_at - time.time()))
            self.l_next.configure(text=f"กดครั้งถัดไปใน {r // 60:02d}:{r % 60:02d}  ·  กดไปแล้ว {e.poke_count} ครั้ง")
            self.btn.configure(text="หยุด", border_color=BAD, text_color=BAD)
        else:
            self.l_next.configure(text="")
            self.btn.configure(text="เริ่มทำงาน", border_color=ACC, text_color=ACC)


# =====================================================================
class ClickPage(Page):
    """ออโต้คลิก / กดปุ่มรัว — F6 เริ่ม-หยุด · F7 เก็บตำแหน่งที่เมาส์ชี้"""

    def __init__(self, master, app):
        super().__init__(master, app)
        c = app.cfg
        ctk.CTkLabel(self, text="ออโต้คลิก", font=FH, text_color=ACC).pack(anchor="w", padx=20, pady=(14, 0))
        ctk.CTkLabel(self, text="F6 = เริ่ม/หยุด  ·  F7 = เก็บตำแหน่งที่เมาส์ชี้อยู่", font=FS, text_color=DIM).pack(anchor="w", padx=20)

        warn = ctk.CTkFrame(self, fg_color=BADBG, corner_radius=10, border_width=1, border_color=BAD)
        warn.pack(fill="x", padx=20, pady=(8, 0))
        ctk.CTkLabel(warn, text="⚠  เกมแนวคลิกเกอร์/ซิมูเลเตอร์หลายเกมมีระบบจับการคลิกอัตโนมัติ ถ้าจับได้ = โดนแบนเกมนั้น · การสุ่มจังหวะไม่ได้การันตีอะไร",
                     font=FS, text_color=BADT, justify="left").pack(anchor="w", padx=12, pady=6)

        top = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        top.pack(fill="x", padx=20, pady=8)
        self.btn = ctk.CTkButton(top, text="เริ่มคลิก (F6)", font=FMB, height=46, width=210,
                                 fg_color="transparent", border_width=2, border_color=ACC, text_color=ACC,
                                 hover_color=OKBG, command=lambda: app.click.toggle())
        self.btn.pack(side="left", padx=14, pady=10)
        self.l_stat = ctk.CTkLabel(top, text="", font=FS, text_color=DIM, justify="left")
        self.l_stat.pack(side="left", padx=10)

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        # ---------- ความเร็ว ----------
        sp = self.card(body, "ความเร็ว")
        self.v_cps = ctk.IntVar(value=c["click_cps"])
        self.l_cps = ctk.CTkLabel(sp, text="", font=F)
        self.l_cps.pack(anchor="w", padx=16)
        ctk.CTkSlider(sp, from_=1, to=100, number_of_steps=99, variable=self.v_cps,
                      command=lambda _: self.upd_cps()).pack(fill="x", padx=16, pady=(0, 6))
        r = ctk.CTkFrame(sp, fg_color="transparent")
        r.pack(anchor="w", padx=16, pady=(0, 4))
        ctk.CTkLabel(r, text="หรือระบุช่วงเวลาเองเป็น", font=F).pack(side="left")
        self.e_ms = self.entry(r, c["click_interval_ms"], 60)
        ctk.CTkLabel(r, text="ms  (0 = ใช้สไลเดอร์ข้างบน · 1 ms ≈ 1000 ครั้ง/วิ เท่า OP Auto Clicker)", font=FS, text_color=DIM).pack(side="left", padx=4)
        r = ctk.CTkFrame(sp, fg_color="transparent")
        r.pack(anchor="w", padx=16, pady=(0, 10))
        ctk.CTkLabel(r, text="สุ่มจังหวะระหว่าง", font=F).pack(side="left")
        self.e_rmin = self.entry(r, c["click_rand_min"], 50)
        ctk.CTkLabel(r, text="–", font=F).pack(side="left", padx=4)
        self.e_rmax = self.entry(r, c["click_rand_max"], 50)
        ctk.CTkLabel(r, text="% ของจังหวะปกติ  (ตั้งเท่ากันทั้งคู่ = ไม่สุ่ม เป๊ะเหมือนหุ่นยนต์)", font=FS, text_color=DIM).pack(side="left", padx=6)

        # ---------- กดอะไร ----------
        wt = self.card(body, "กดอะไร")
        r = ctk.CTkFrame(wt, fg_color="transparent")
        r.pack(anchor="w", padx=16, pady=(0, 6))
        self.v_mode = ctk.StringVar(value=c["click_mode"])
        ctk.CTkRadioButton(r, text="เมาส์", value="mouse", variable=self.v_mode, command=app.sync_cfg, font=F).pack(side="left")
        self.v_btn = ctk.StringVar(value=c["click_button"])
        ctk.CTkOptionMenu(r, values=["left", "right", "middle"], variable=self.v_btn, command=lambda _: app.sync_cfg(), font=F, width=88).pack(side="left", padx=6)
        self.v_type = ctk.StringVar(value={1: "คลิกเดี่ยว", 2: "ดับเบิลคลิก", 3: "ทริปเปิลคลิก"}[c["click_type"]])
        ctk.CTkOptionMenu(r, values=["คลิกเดี่ยว", "ดับเบิลคลิก", "ทริปเปิลคลิก"], variable=self.v_type,
                          command=lambda _: app.sync_cfg(), font=F, width=120).pack(side="left", padx=6)
        ctk.CTkRadioButton(r, text="ปุ่มคีย์บอร์ด", value="key", variable=self.v_mode, command=app.sync_cfg, font=F).pack(side="left", padx=(18, 4))
        self.e_key = self.entry(r, c["click_key"], 64)
        ctk.CTkLabel(r, text="(e, f, space, 1-9, f1-f12)", font=FS, text_color=DIM).pack(side="left", padx=4)

        # ---------- เริ่มยังไง ----------
        tg = self.card(body, "เริ่มยังไง")
        r = ctk.CTkFrame(tg, fg_color="transparent")
        r.pack(anchor="w", padx=16, pady=(0, 10))
        self.v_trig = ctk.StringVar(value=c["click_trigger"])
        ctk.CTkRadioButton(r, text="กด F6 ติด–ดับ", value="toggle", variable=self.v_trig, command=app.sync_cfg, font=F).pack(side="left")
        ctk.CTkRadioButton(r, text="กดปุ่มค้างถึงจะคลิก →", value="hold", variable=self.v_trig, command=app.sync_cfg, font=F).pack(side="left", padx=(18, 4))
        self.e_hold = self.entry(r, c["click_hold_key"], 74)
        ctk.CTkLabel(r, text="(mouse1 = คลิกซ้าย, mouse4/5 = ปุ่มข้าง, หรือปุ่มคีย์บอร์ด)", font=FS, text_color=DIM).pack(side="left", padx=4)

        # ---------- ตำแหน่ง ----------
        pt = self.card(body, "คลิกตรงไหน")
        r = ctk.CTkFrame(pt, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkButton(r, text="📍 เก็บตำแหน่งเมาส์ (F7)", width=190, font=F, command=lambda: app.click.add_point()).pack(side="left")
        ctk.CTkButton(r, text="ล้างจุดทั้งหมด", width=120, font=F, fg_color=BTN, hover_color=BTNH, command=self.clear_points).pack(side="left", padx=8)
        self.v_restore = ctk.BooleanVar(value=c["click_restore_cursor"])
        ctk.CTkSwitch(r, text="เอาเมาส์กลับที่เดิมหลังคลิก", variable=self.v_restore, command=app.sync_cfg, font=FS).pack(side="left", padx=10)
        self.l_points = ctk.CTkLabel(pt, text="", font=FS, text_color=DIM, justify="left")
        self.l_points.pack(anchor="w", padx=16, pady=(0, 10))

        # ---------- เบรก ----------
        br = self.card(body, "เบรกกันพัง")
        self.vars = {"click_only_roblox": ctk.BooleanVar(value=c["click_only_roblox"])}
        ctk.CTkSwitch(br, text="คลิกเฉพาะตอนที่หน้าต่าง Roblox โฟกัสอยู่ (แนะนำให้เปิด กันเผลอคลิกรัวใส่โปรแกรมอื่น)",
                      variable=self.vars["click_only_roblox"], font=F, command=app.sync_cfg).pack(anchor="w", padx=16, pady=2)
        r = ctk.CTkFrame(br, fg_color="transparent")
        r.pack(anchor="w", padx=16, pady=(4, 4))
        ctk.CTkLabel(r, text="หยุดเองหลัง", font=F).pack(side="left")
        self.e_min = self.entry(r, c["click_max_min"], 52)
        ctk.CTkLabel(r, text="นาที  หรือครบ", font=F).pack(side="left")
        self.e_max = self.entry(r, c["click_max_clicks"], 74)
        ctk.CTkLabel(r, text="ครั้ง   (0 = ไม่จำกัด)", font=F).pack(side="left")
        r = ctk.CTkFrame(br, fg_color="transparent")
        r.pack(anchor="w", padx=16, pady=(0, 10))
        ctk.CTkLabel(r, text="รัวเป็นชุด: คลิก", font=F).pack(side="left")
        self.e_burst = self.entry(r, c["click_burst"], 52)
        ctk.CTkLabel(r, text="ครั้ง แล้วพัก", font=F).pack(side="left")
        self.e_bpause = self.entry(r, c["click_burst_pause"], 52)
        ctk.CTkLabel(r, text="วินาที   (0 = รัวไม่หยุด)", font=F).pack(side="left")

        # ---------- อัดมาโคร ----------
        mc = self.card(body, "🎬 อัดมาโคร — อัดเมาส์+ปุ่มพร้อมจังหวะเวลา แล้วเล่นซ้ำ (F4 อัด · F5 เล่น)")
        r = ctk.CTkFrame(mc, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=(0, 6))
        self.bt_rec = ctk.CTkButton(r, text="● เริ่มอัด (F4)", width=140, font=F, fg_color=DANGER, hover_color=DANGERH,
                                    command=lambda: app.toggle_record())
        self.bt_rec.pack(side="left")
        self.bt_play = ctk.CTkButton(r, text="▶ เล่น (F5)", width=110, font=F, command=lambda: app.play_macro())
        self.bt_play.pack(side="left", padx=6)
        self.v_macro = ctk.StringVar(value="")
        self.opt_macro = ctk.CTkOptionMenu(r, values=["—"], variable=self.v_macro, font=F, width=170, command=lambda _: self.show_macro())
        self.opt_macro.pack(side="left", padx=6)
        ctk.CTkButton(r, text="ลบ", width=46, font=F, fg_color=DANGER, hover_color=DANGERH,
                      command=self.del_macro).pack(side="left")
        r = ctk.CTkFrame(mc, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(r, text="วน", font=F).pack(side="left")
        self.e_loops = self.entry(r, c["macro_loops"], 48)
        ctk.CTkLabel(r, text="รอบ (0 = ไม่หยุด)   ความเร็ว", font=F).pack(side="left")
        self.e_speed = self.entry(r, c["macro_speed"], 48)
        ctk.CTkLabel(r, text="x", font=F).pack(side="left")
        self.v_mroblox = ctk.BooleanVar(value=c["macro_only_roblox"])
        ctk.CTkSwitch(r, text="เล่นเฉพาะตอนอยู่ในหน้าต่าง Roblox", variable=self.v_mroblox, command=app.sync_cfg, font=FS).pack(side="left", padx=12)
        self.l_macro = ctk.CTkLabel(mc, text="", font=FS, text_color=DIM, justify="left")
        self.l_macro.pack(anchor="w", padx=16, pady=(0, 10))

        # ---------- โปรไฟล์ ----------
        pf = self.card(body, "โปรไฟล์ (ชุดตั้งค่าต่อเกม)")
        r = ctk.CTkFrame(pf, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=(0, 10))
        self.v_prof = ctk.StringVar(value="")
        self.opt_prof = ctk.CTkOptionMenu(r, values=["—"], variable=self.v_prof, font=F, width=190)
        self.opt_prof.pack(side="left")
        ctk.CTkButton(r, text="โหลด", width=70, font=F, command=self.load_profile).pack(side="left", padx=5)
        self.e_prof = ctk.CTkEntry(r, width=140, font=F, placeholder_text="ตั้งชื่อแล้วกดบันทึก")
        self.e_prof.pack(side="left", padx=(12, 5))
        ctk.CTkButton(r, text="บันทึก", width=70, font=F, command=self.save_profile).pack(side="left")
        ctk.CTkButton(r, text="ลบ", width=50, font=F, fg_color=DANGER, hover_color=DANGERH, command=self.del_profile).pack(side="left", padx=5)
        self.upd_cps()
        self.refresh_points()
        self.refresh_profiles()
        self.refresh_macros()

    # ---------- helper ----------
    def card(self, parent, title):
        ctk.CTkLabel(parent, text=title, font=FB, text_color=TXT2).pack(anchor="w", padx=8, pady=(8, 2))
        f = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12)
        f.pack(fill="x", padx=6)
        ctk.CTkLabel(f, text="", height=2).pack()
        return f

    def entry(self, parent, value, width):
        e = ctk.CTkEntry(parent, width=width, font=F, justify="center")
        e.insert(0, str(value))
        e.pack(side="left", padx=5)
        return e

    def upd_cps(self):
        n = int(self.v_cps.get())
        self.app.cfg["click_cps"] = n
        try:
            ms = float(self.e_ms.get())
        except (ValueError, AttributeError):
            ms = 0
        if ms > 0:
            self.l_cps.configure(text=f"กำลังใช้ค่าที่ระบุเอง: ทุก {ms:g} ms  (~{1000 / ms:.0f} ครั้ง/วิ)  ·  สไลเดอร์ถูกข้าม", text_color=WARN)
            return
        hint = "  ·  คนกดเร็วสุดราวๆ 10-14 ครั้ง/วิ" if n > 14 else ""
        if n > 60:
            hint += "  ·  เกมอ่านอินพุตทีละเฟรม 60 fps รับได้จริงราว 60 ครั้ง/วิ ที่เกินมักถูกทิ้ง"
        self.l_cps.configure(text=f"ความเร็ว: {n} ครั้ง/วินาที{hint}", text_color=WARN if n > 14 else TXT2)

    def clear_points(self):
        self.app.cfg["click_points"].clear()
        self.app.log("ล้างจุดที่ล็อกไว้แล้ว — กลับไปคลิกตามเคอร์เซอร์")
        self.refresh_points()

    def refresh_points(self):
        pts = self.app.cfg["click_points"]
        if not pts:
            self.l_points.configure(text="ยังไม่ได้ล็อกจุด — คลิกตรงที่เคอร์เซอร์อยู่ (เอาเมาส์ไปวางตรงปุ่มในเกมแล้วกด F7 เพื่อล็อก)")
        else:
            txt = "  ".join(f"{i + 1}({x},{y})" for i, (x, y) in enumerate(pts[:10]))
            self.l_points.configure(text=f"ล็อกไว้ {len(pts)} จุด — จะวนคลิกทีละจุด:  {txt}" + ("  ..." if len(pts) > 10 else ""))

    def refresh_macros(self):
        names = macro.macro_list()
        self.opt_macro.configure(values=names or ["—"])
        if names and self.v_macro.get() not in names:
            self.v_macro.set(names[0])
        self.show_macro()

    def show_macro(self):
        name = self.v_macro.get()
        if not name or name == "—":
            return self.l_macro.configure(text="ยังไม่มีมาโคร — กด F4 (หรือปุ่มอัด) แล้วทำสิ่งที่อยากให้ทำซ้ำ จากนั้นกด F4 อีกทีเพื่อหยุด")
        i = macro.macro_info(name)
        self.l_macro.configure(text=f"'{name}' — ยาว {i['seconds']:.1f} วินาที · {i['events']} เหตุการณ์ · คลิก {i['clicks']} ครั้ง · กดปุ่ม {i['keys']} ครั้ง")

    def del_macro(self):
        name = self.v_macro.get()
        if name and name != "—":
            macro.macro_delete(name)
            self.app.log(f"ลบมาโคร '{name}' แล้ว")
            self.refresh_macros()

    def refresh_profiles(self):
        names = sorted(clicker.load_profiles())
        self.opt_prof.configure(values=names or ["—"])
        if names and self.v_prof.get() not in names:
            self.v_prof.set(names[0])

    def save_profile(self):
        name = self.e_prof.get().strip()
        if not name:
            return self.app.log("ใส่ชื่อโปรไฟล์ก่อนกดบันทึก")
        self.app.sync_cfg()
        clicker.save_profile(name, self.app.cfg)
        self.app.log(f"บันทึกโปรไฟล์ '{name}' แล้ว")
        self.refresh_profiles()
        self.v_prof.set(name)

    def load_profile(self):
        name = self.v_prof.get()
        data = clicker.load_profiles().get(name)
        if not data:
            return self.app.log("ยังไม่มีโปรไฟล์นั้น")
        self.app.cfg.update(data)
        config.save(self.app.cfg)
        self.reload_widgets()
        self.app.log(f"โหลดโปรไฟล์ '{name}' แล้ว — {self.app.click.describe()}")

    def del_profile(self):
        name = self.v_prof.get()
        clicker.delete_profile(name)
        self.app.log(f"ลบโปรไฟล์ '{name}' แล้ว")
        self.refresh_profiles()

    def reload_widgets(self):
        c = self.app.cfg
        self.v_cps.set(c["click_cps"])
        self.v_mode.set(c["click_mode"])
        self.v_btn.set(c["click_button"])
        self.v_trig.set(c["click_trigger"])
        self.v_type.set({1: "คลิกเดี่ยว", 2: "ดับเบิลคลิก", 3: "ทริปเปิลคลิก"}[c["click_type"]])
        self.v_restore.set(c["click_restore_cursor"])
        self.vars["click_only_roblox"].set(c["click_only_roblox"])
        for e, v in ((self.e_key, c["click_key"]), (self.e_hold, c["click_hold_key"]), (self.e_ms, c["click_interval_ms"]), (self.e_rmin, c["click_rand_min"]),
                     (self.e_rmax, c["click_rand_max"]), (self.e_min, c["click_max_min"]), (self.e_max, c["click_max_clicks"]),
                     (self.e_burst, c["click_burst"]), (self.e_bpause, c["click_burst_pause"])):
            e.delete(0, "end")
            e.insert(0, str(v))
        self.upd_cps()
        self.refresh_points()

    def tick(self):
        app = self.app
        self.bt_rec.configure(text="⏹ หยุดอัด (F4)" if app.rec else "● เริ่มอัด (F4)")
        self.bt_play.configure(text=("⏹ หยุด (F5)" if app.mplay else "▶ เล่น (F5)"),
                               fg_color=BAD if app.mplay else [ACC2, ACC2])
        cl = self.app.click
        if cl.running:
            dur = max(0.001, time.time() - cl.started_at)
            self.btn.configure(text="หยุด (F6)", border_color=BAD, text_color=BAD)
            note = {"focus": "  ·  ⏸ รออยู่ที่หน้าต่าง Roblox", "hold": f"  ·  ⏸ รอกด {self.app.cfg['click_hold_key']} ค้าง"}.get(cl.paused_reason, "")
            self.l_stat.configure(text=f"คลิกไปแล้ว {cl.clicks} ครั้ง · {cl.clicks / dur:.1f} ครั้ง/วิ จริง · {int(dur)} วิ{note}",
                                  text_color=WARN if cl.paused_reason else ACC)
        else:
            self.btn.configure(text="เริ่มคลิก (F6)", border_color=ACC, text_color=ACC)
            self.l_stat.configure(text=(f"ครั้งล่าสุด: {cl.clicks} ครั้ง" if cl.clicks else "") + "\n" + cl.describe(), text_color=DIM)


# =====================================================================
class SysPage(Page):
    """มอนิเตอร์เครื่อง — CPU / RAM / GPU / อุณหภูมิ + เตือนเมื่อร้อนหรือแรมตึง"""

    CARDS = [("cpu", "CPU", "%"), ("ram", "RAM", "%"), ("gpu", "GPU", "%"), ("gpu_temp", "GPU อุณหภูมิ", "°C")]

    def __init__(self, master, app):
        super().__init__(master, app)
        ctk.CTkLabel(self, text="มอนิเตอร์เครื่อง", font=FH, text_color=ACC).pack(anchor="w", padx=20, pady=(16, 0))
        ctk.CTkLabel(self, text="เฝ้าให้ตอนเปิด Anti-AFK ทิ้งไว้นานๆ — ร้อนค้างหรือแรมจะเต็มจะเด้งเตือน (อุณหภูมิ CPU อ่านไม่ได้บนโน้ตบุ๊กรุ่นนี้)",
                     font=FS, text_color=DIM).pack(anchor="w", padx=20)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=10)
        self.big = {}
        for key, title, unit in self.CARDS:
            f = ctk.CTkFrame(row, fg_color=CARD, corner_radius=12)
            f.pack(side="left", fill="both", expand=True, padx=4)
            ctk.CTkLabel(f, text=title, font=FS, text_color=DIM).pack(pady=(10, 0))
            v = ctk.CTkLabel(f, text="—", font=FBIG)
            v.pack()
            sub = ctk.CTkLabel(f, text="", font=FS, text_color=DIM)
            sub.pack(pady=(0, 10))
            self.big[key] = (v, sub, unit)

        gf = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        gf.pack(fill="x", padx=20)
        ctk.CTkLabel(gf, text="20 นาทีล่าสุด   —   เขียว CPU · ฟ้า RAM · ส้ม GPU · แดง อุณหภูมิ GPU", font=FS, text_color=DIM).pack(anchor="w", padx=14, pady=(8, 0))
        self.canvas = ctk.CTkCanvas(gf, height=150, bg=INK, highlightthickness=0)
        self.canvas.pack(fill="x", padx=14, pady=10)

        fc = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        fc.pack(fill="x", padx=20, pady=(10, 0))
        r = ctk.CTkFrame(fc, fg_color="transparent")
        r.pack(fill="x", padx=14, pady=(8, 2))
        self.v_fps = ctk.BooleanVar(value=app.cfg["fps_cap_on"])
        ctk.CTkSwitch(r, text="🐢 จำกัด FPS ของ Roblox ตอนไม่ได้ดูจอ เหลือ", variable=self.v_fps, font=F, command=app.sync_cfg).pack(side="left")
        self.v_fpsn = ctk.StringVar(value=str(app.cfg["fps_cap"]))
        ctk.CTkOptionMenu(r, values=[str(x) for x in fpscap.PRESETS], variable=self.v_fpsn, command=lambda _: app.sync_cfg(), font=F, width=70).pack(side="left", padx=6)
        ctk.CTkLabel(r, text="FPS", font=F).pack(side="left")
        self.l_fps = ctk.CTkLabel(r, text="", font=FS, text_color=DIM)
        self.l_fps.pack(side="left", padx=12)
        r = ctk.CTkFrame(fc, fg_color="transparent")
        r.pack(fill="x", padx=14, pady=(0, 4))
        self.v_unlock = ctk.BooleanVar(value=app.cfg["fps_unlock_focus"])
        ctk.CTkSwitch(r, text="ปลดล็อกทันทีเมื่อกลับไปคลิกที่หน้าต่างเกม (แนะนำให้เปิด)", variable=self.v_unlock, font=FS, command=app.sync_cfg).pack(side="left")
        self.v_mute = ctk.BooleanVar(value=app.cfg["automute"])
        ctk.CTkSwitch(fc, text="🔇 ปิดเสียง Roblox อัตโนมัติตอน Anti-AFK ทำงาน (เปิดเสียงคืนเมื่อหยุด)",
                      variable=self.v_mute, font=FS, command=app.sync_cfg).pack(anchor="w", padx=16, pady=(0, 4))
        ctk.CTkLabel(fc, text="วิธีจำกัด FPS: หยุด-ปลุกเธรดของเกมเป็นจังหวะ ไม่ได้แก้ไฟล์เกม · เกมจะยังออนไลน์อยู่แค่วาดภาพช้าลง · ประหยัด GPU/ไฟ/ความร้อนมาก",
                     font=FS, text_color=DIM, justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        bot = ctk.CTkFrame(self, fg_color="transparent")
        bot.pack(fill="both", expand=True, padx=20, pady=(10, 12))
        left = ctk.CTkFrame(bot, fg_color=CARD, corner_radius=12)
        left.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(left, text="กินแรมมากสุด", font=FB).pack(anchor="w", padx=14, pady=(10, 2))
        self.l_top = ctk.CTkLabel(left, text="", font=MONO, text_color=TXT2, justify="left")
        self.l_top.pack(anchor="w", padx=14, pady=(0, 10))
        right = ctk.CTkFrame(bot, fg_color=CARD, corner_radius=12, width=330)
        right.pack(side="left", fill="y", padx=(10, 0))
        right.pack_propagate(False)
        ctk.CTkLabel(right, text="อื่นๆ", font=FB).pack(anchor="w", padx=14, pady=(10, 2))
        self.l_misc = ctk.CTkLabel(right, text="", font=F, text_color=TXT2, justify="left")
        self.l_misc.pack(anchor="w", padx=14)
        self.v_game = ctk.BooleanVar(value=app.cfg["game_mode"])
        ctk.CTkSwitch(right, text="โหมดเล่นเกม: เปิด Roblox แล้วคายโมเดล AI คืน VRAM", variable=self.v_game,
                      font=FS, command=app.sync_cfg).pack(anchor="w", padx=14, pady=(8, 0))
        ctk.CTkButton(right, text="คายโมเดล AI ตอนนี้", width=170, font=FS, fg_color=BTN, hover_color=BTNH,
                      command=self.free_now).pack(anchor="w", padx=14, pady=(4, 2))
        self.v_alerts = ctk.BooleanVar(value=app.cfg["sys_alerts"])
        ctk.CTkSwitch(right, text="เตือนเมื่อร้อน/แรมตึง", variable=self.v_alerts, font=FS, command=app.sync_cfg).pack(anchor="w", padx=14, pady=(10, 4))
        self.v_trim = ctk.BooleanVar(value=app.cfg.get("auto_trim_ram", False))
        ctk.CTkSwitch(right, text=f"คืนแรมอัตโนมัติเมื่อแรม ≥ {app.cfg.get('ram_limit', 92)}% ตอนเล่นเกม (ไม่เกินทุก 10 นาที)", variable=self.v_trim,
                      font=FS, command=app.sync_cfg).pack(anchor="w", padx=14, pady=(0, 4))
        r2 = ctk.CTkFrame(right, fg_color="transparent")
        r2.pack(anchor="w", padx=14)
        ctk.CTkLabel(r2, text="เตือนเมื่อ GPU เกิน", font=FS).pack(side="left")
        self.e_temp = ctk.CTkEntry(r2, width=44, font=FS, justify="center")
        self.e_temp.insert(0, str(app.cfg["gpu_temp_limit"]))
        self.e_temp.pack(side="left", padx=4)
        ctk.CTkLabel(r2, text="°C", font=FS).pack(side="left")
        self._last_top = 0

    def tick(self):
        m = self.app.sys
        c = m.cur
        if not c:
            return
        for key, (lab, sub, unit) in self.big.items():
            v = c.get(key)
            if v is None:
                lab.configure(text="—", text_color=DIM)
                sub.configure(text="ไม่มีข้อมูล")
                continue
            hot = (key == "gpu_temp" and v >= self.app.cfg["gpu_temp_limit"]) or (key == "ram" and v >= self.app.cfg["ram_limit"]) or (key != "gpu_temp" and v >= 90)
            warm = v >= 75 and not hot
            lab.configure(text=f"{v:.0f}{unit}", text_color=BAD if hot else (WARN if warm else ACC))
            if key == "ram":
                sub.configure(text=f"{c['ram_used']:.1f} / {c['ram_total']:.0f} GB")
            elif key == "gpu" and c.get("vram"):
                sub.configure(text=f"VRAM {c['vram'] / 1024:.1f}/{c['vram_total'] / 1024:.0f} GB")
            elif key == "gpu_temp" and c.get("gpu_power"):
                sub.configure(text=f"{c['gpu_power']:.0f} W · {c.get('gpu_clock', 0):.0f} MHz")
            else:
                a = m.avg(key, 300)
                sub.configure(text=f"เฉลี่ย 5 นาที {a:.0f}{unit}" if a is not None else "")
        self.draw()
        if time.time() - self._last_top > 5:
            self._last_top = time.time()
            try:
                rows = sysmon.top_processes(6)
                self.l_top.configure(text="\n".join(f"{n[:26]:<26} {mb / 1024:>5.2f} GB" for n, mb, _ in rows))
            except Exception:
                pass
        misc = []
        if c.get("battery") is not None:
            misc.append(("🔌 " if c.get("plugged") else "🔋 ") + f"แบต {c['battery']:.0f}%")
        if c.get("disk_free") is not None:
            misc.append(f"💾 ดิสก์ว่าง {c['disk_free']:.0f} / {c['disk_total']:.0f} GB")
        if c.get("gpu_power") is not None:
            misc.append(f"⚡ GPU กินไฟ {c['gpu_power']:.0f} W")
        misc.append(f"⏱ เก็บข้อมูลมา {len(m.hist) * m.EVERY // 60} นาที")
        cap = self.app.fps
        self.l_fps.configure(text=("🐢 กำลังจำกัดอยู่" if cap.capping else ("พักชั่วคราว" if cap.paused else "รอจังหวะ")) if self.app.cfg["fps_cap_on"] else "",
                             text_color=WARN if cap.capping else DIM)
        self.l_misc.configure(text="\n\n".join(misc))

    def reload_fps(self):
        c = self.app.cfg
        self.v_fps.set(c["fps_cap_on"])
        self.v_fpsn.set(str(c["fps_cap"]))

    def free_now(self):
        def work():
            n, freed = sysmon.unload_all()
            self.app.log(f"คายโมเดล AI {n} ตัว — คืน VRAM {freed:.0f} MB" if n else "ไม่มีโมเดล AI ค้างอยู่ (หรือ Ollama ไม่ได้เปิด)")
        threading.Thread(target=work, daemon=True).start()

    def draw(self):
        cv, m = self.canvas, self.app.sys
        cv.delete("all")
        w = max(cv.winfo_width(), 200)
        h = 150
        for frac in (0.25, 0.5, 0.75):
            cv.create_line(0, h * frac, w, h * frac, fill=CARD2)
        for key, col, mx in (("cpu", ACC, 100), ("ram", INFO, 100), ("gpu", WARN, 100), ("gpu_temp", BAD, 100)):
            pts = [(t, v) for t, v in m.series(key, 1200) if v is not None]
            if len(pts) < 2:
                continue
            step = w / max(1, len(pts) - 1)
            coords = []
            for i, (_, v) in enumerate(pts):
                coords += [i * step, h - (min(v, mx) / mx) * (h - 6) - 3]
            cv.create_line(*coords, fill=col, width=2, smooth=True)


# =====================================================================
class AnalyticsPage(Page):
    """วิเคราะห์พฤติกรรมการเล่นจากคลังประวัติ — heatmap, ชั่วโมงที่เล่น, เกม, สาเหตุหลุด, ข้อสังเกต"""

    def __init__(self, master, app):
        super().__init__(master, app)
        self.imgs = {}
        self.built = False
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(head, text="วิเคราะห์การเล่น", font=FH, text_color=ACC).pack(side="left")
        ctk.CTkButton(head, text="📤 แชร์การ์ด", width=110, font=F, fg_color=BTN, hover_color=BTNH,
                      command=self.share).pack(side="right", padx=(6, 0))
        ctk.CTkButton(head, text="โหลดใหม่", width=90, font=F, command=lambda: self.build(True)).pack(side="right", padx=6)
        self.seg = ctk.CTkSegmentedButton(head, values=["7 วัน", "30 วัน", "90 วัน", "ทั้งหมด"], command=lambda _: self.build(), font=F)
        self.seg.set("30 วัน")
        self.seg.pack(side="right", padx=8)
        self.l_note = ctk.CTkLabel(self, text="", font=FS, text_color=DIM, justify="left")
        self.l_note.pack(anchor="w", padx=20)

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=14, pady=(4, 10))
        self.ins = ctk.CTkFrame(self.body, fg_color=CARD, corner_radius=12)
        self.ins.pack(fill="x", padx=6, pady=(0, 10))
        self.l_heat = ctk.CTkLabel(self.body, text="")
        self.l_heat.pack(padx=6, pady=4)
        self.l_hour = ctk.CTkLabel(self.body, text="")
        self.l_hour.pack(padx=6, pady=4)
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", padx=6, pady=4)
        self.l_games = ctk.CTkLabel(row, text="")
        self.l_games.pack(side="left")
        self.l_reason = ctk.CTkLabel(row, text="")
        self.l_reason.pack(side="left", padx=(12, 0))

    def days(self):
        return {"7 วัน": 7, "30 วัน": 30, "90 วัน": 90, "ทั้งหมด": 3650}[self.seg.get()]

    def on_show(self):
        if not self.built:
            self.build()

    def build(self, rescan=False):
        self.built = True
        self.l_note.configure(text="กำลังคำนวณ...")

        def work():
            try:
                app, d = self.app, self.days()
                if rescan or not app.hist.sessions:
                    app.hist.scan()
                sess = app.hist.sessions
                s = app.hist.summary(d)
                pics = {
                    "heat": charts.heatmap(analytics.heat(sess, min(d, 28)), w=820, h=220),
                    "hour": charts.hour_bars(analytics.hourly(sess, d), w=820, h=190),
                    "games": charts.game_bars(s["games"], app.hist.name, w=404, h=230),
                    "reason": charts.reason_bars(analytics.disconnects(sess, d)["by_reason"], w=404, h=230),
                }
                tips = analytics.insights(sess, app.hist.name, d, app.net.dc_map)
                note = (f"คลังประวัติของโปรแกรม: {len(sess)} เซสชัน "
                        f"(เก็บเองถาวร — log ของ Roblox ถูกลบทิ้งเองเรื่อยๆ ข้อมูลเก่าจึงจะค่อยๆ สะสมจากนี้)")
                app.ui(lambda: self.show(pics, tips, note))
            except Exception as e:
                import traceback
                config.dbg("analytics: " + traceback.format_exc())
                self.app.ui(lambda: self.l_note.configure(text=f"คำนวณไม่ได้: {e}"))

        threading.Thread(target=work, daemon=True).start()

    def show(self, pics, tips, note):
        for key, lb in (("heat", self.l_heat), ("hour", self.l_hour), ("games", self.l_games), ("reason", self.l_reason)):
            im = pics[key]
            self.imgs[key] = ctk.CTkImage(light_image=im, dark_image=im, size=im.size)
            lb.configure(image=self.imgs[key], text="")
        for w in self.ins.winfo_children():
            w.destroy()
        for icon, txt in tips:
            r = ctk.CTkFrame(self.ins, fg_color="transparent")
            r.pack(fill="x", padx=14, pady=3)
            ctk.CTkLabel(r, text=icon, font=F, width=26).pack(side="left")
            ctk.CTkLabel(r, text=txt, font=F, text_color=TXT, justify="left", anchor="w").pack(side="left", fill="x", expand=True)
        self.l_note.configure(text=note)

    def share(self):
        def work():
            try:
                png = charts.analytics_card(self.app.hist, self.days())
                out = os.path.join(config.DATA_DIR, "analytics.png")
                open(out, "wb").write(png)
                if self.app.cfg["webhook_url"]:
                    session.webhook_image(self.app.cfg["webhook_url"], png, f"📈 สรุปการเล่น {self.days()} วัน", "analytics.png")
                    self.app.log("ส่งการ์ดวิเคราะห์เข้า Discord แล้ว")
                self.app.ui(lambda: os.startfile(out))
            except Exception as e:
                self.app.log(f"ทำการ์ดไม่ได้: {e}")

        threading.Thread(target=work, daemon=True).start()


# =====================================================================
class StatsPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.period = None
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(head, text="สถิติการเล่น", font=FH, text_color=ACC).pack(side="left")
        ctk.CTkButton(head, text="โหลดใหม่", width=90, font=F, command=lambda: self.load(True)).pack(side="right")
        ctk.CTkButton(head, text="📤 แชร์การ์ดสัปดาห์", width=150, font=F, fg_color=BTN, hover_color=BTNH, command=self.share).pack(side="right", padx=6)
        self.seg = ctk.CTkSegmentedButton(head, values=["วันนี้", "7 วัน", "30 วัน", "ทั้งหมด"], command=lambda _: self.render(), font=F)
        self.seg.set("7 วัน")
        self.seg.pack(side="right", padx=10)
        self.l_sum = ctk.CTkLabel(self, text="กำลังอ่าน log ของ Roblox...", font=F, text_color=DIM)
        self.l_sum.pack(anchor="w", padx=20)
        self.canvas = ctk.CTkCanvas(self, height=120, bg=INK, highlightthickness=0)
        self.canvas.pack(fill="x", padx=20, pady=8)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        body.grid_columnconfigure((0, 1), weight=1, uniform="a")
        body.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(body, text="เกมที่เล่นมากสุด", font=FB).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(body, text="ประวัติการหลุด", font=FB).grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.games = ctk.CTkScrollableFrame(body, fg_color=CARD, corner_radius=12)
        self.games.grid(row=1, column=0, sticky="nsew", pady=4)
        self.disc = ctk.CTkScrollableFrame(body, fg_color=CARD, corner_radius=12)
        self.disc.grid(row=1, column=1, sticky="nsew", padx=(10, 0), pady=4)
        self.loaded = False

    def on_show(self):
        if not self.loaded:
            self.load()

    def load(self, force=False):
        if self.app.hist.loading:
            return
        self.l_sum.configure(text="กำลังอ่าน log ของ Roblox...")

        def work():
            self.app.hist.scan(progress=lambda d, t: self.app.ui(lambda: self.l_sum.configure(text=f"อ่าน log {d}/{t}")))
            self.loaded = True
            self.app.ui(self.render)
            places = [g["place"] for g in self.app.hist.summary()["games"][:30]]
            self.app.hist.resolve_names(places, done=lambda: self.app.ui(self.render))

        threading.Thread(target=work, daemon=True).start()

    def share(self):
        """วาดการ์ดสถิติ 7 วัน → บันทึก PNG + ส่ง webhook ถ้าตั้งไว้"""
        def work():
            try:
                png = session.weekly_card(self.app.hist.summary(7), self.app.hist.name, self.app.hist.daily(7))
                out = os.path.join(config.DATA_DIR, "weekly.png")
                open(out, "wb").write(png)
                if self.app.cfg["webhook_url"]:
                    session.webhook_image(self.app.cfg["webhook_url"], png, "📊 สถิติ 7 วันของฉัน", "weekly.png")
                    self.app.log("ส่งการ์ดสถิติเข้า Discord แล้ว")
                self.app.ui(lambda: os.startfile(out))
            except Exception as e:
                self.app.log(f"ทำการ์ดไม่ได้: {e}")
        threading.Thread(target=work, daemon=True).start()

    def render(self):
        days = {"วันนี้": 1, "7 วัน": 7, "30 วัน": 30, "ทั้งหมด": None}[self.seg.get()]
        s = self.app.hist.summary(days)
        self.l_sum.configure(text=f"รวม {fmt_dur(s['total'])}  ·  {s['sessions']} เซสชัน  ·  หลุด {len(s['disconnects'])} ครั้ง"
                                  + ("  ·  " + time.strftime("%d/%m/%Y") if days == 1 else ""), text_color=TXT)
        for w in self.games.winfo_children() + self.disc.winfo_children():
            w.destroy()
        top = s["games"][:12]
        mx = top[0]["seconds"] if top else 1
        for g in top:
            f = ctk.CTkFrame(self.games, fg_color="transparent")
            f.pack(fill="x", padx=8, pady=3)
            ctk.CTkLabel(f, text=self.app.hist.name(g["place"])[:34], font=F, anchor="w").pack(side="left")
            ctk.CTkLabel(f, text=f"{fmt_dur(g['seconds'])} · {g['sessions']}x", font=FS, text_color=DIM).pack(side="right")
            pb = ctk.CTkProgressBar(self.games, height=6, progress_color=ACC)
            pb.set(g["seconds"] / mx)
            pb.pack(fill="x", padx=8)
        for d in s["disconnects"][:40]:
            f = ctk.CTkFrame(self.disc, fg_color="transparent")
            f.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(f, text=time.strftime("%d/%m %H:%M", time.localtime(d["end"])), font=FS, text_color=DIM, width=90, anchor="w").pack(side="left")
            ctk.CTkLabel(f, text=fmt_reason(d["reason"]), font=F, text_color=WARN if d["reason"] == 278 else BAD, anchor="w").pack(side="left", padx=6)
            ctk.CTkLabel(f, text=self.app.hist.name(d["place"])[:22], font=FS, text_color=DIM, anchor="e").pack(side="right")
        self.draw_daily()

    def draw_daily(self):
        c = self.canvas
        c.delete("all")
        data = self.app.hist.daily(14)
        w = c.winfo_width() or 800
        h = 120
        mx = max([sec for _, sec in data] + [3600])
        bw = (w - 40) / len(data)
        for i, (d, sec) in enumerate(data):
            x0 = 20 + i * bw + 4
            bh = (sec / mx) * (h - 34)
            c.create_rectangle(x0, h - 20 - bh, x0 + bw - 8, h - 20, fill=ACC if i == len(data) - 1 else ACC2, outline="")
            c.create_text(x0 + (bw - 8) / 2, h - 10, text=d.strftime("%d/%m"), fill=DIM, font=FTINY)
            if sec > 0:
                c.create_text(x0 + (bw - 8) / 2, h - 26 - bh, text=f"{sec / 3600:.1f}", fill=TXT, font=FTINY)
        c.create_text(20, 10, text="ชั่วโมงที่เล่นต่อวัน (14 วัน)", fill=DIM, font=FS, anchor="w")


# =====================================================================
class NetPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)
        ctk.CTkLabel(self, text="คุณภาพเน็ต", font=FH, text_color=ACC).pack(anchor="w", padx=20, pady=(16, 0))
        ctk.CTkLabel(self, text="เซิร์ฟเกม Roblox ไม่ตอบ ping — เลยวัด 3 จุดเพื่อแยกว่าปัญหาอยู่ที่ Wi-Fi, ISP หรือปลายทาง", font=FS, text_color=DIM).pack(anchor="w", padx=20)
        self.banner = ctk.CTkLabel(self, text="กำลังวัด...", font=FB, fg_color=CARD, corner_radius=10, height=44)
        self.banner.pack(fill="x", padx=20, pady=10)
        self.rows = {}
        for name, _ in TARGETS:
            f = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
            f.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(f, text=name, font=FB, width=110, anchor="w").pack(side="left", padx=12, pady=10)
            lab = ctk.CTkLabel(f, text="...", font=F, text_color=DIM, width=300, anchor="w")
            lab.pack(side="left")
            cv = ctk.CTkCanvas(f, height=40, width=260, bg=CARD, highlightthickness=0)
            cv.pack(side="right", padx=12)
            self.rows[name] = (lab, cv)
        self.l_server = ctk.CTkLabel(self, text="", font=F, text_color=DIM)
        self.l_server.pack(anchor="w", padx=20, pady=(8, 0))

        # ---------- ระยะทางถึงภูมิภาคเซิร์ฟ ----------
        rg = ui.card(self)
        rg.pack(fill="x", padx=20, pady=(8, 0))
        rh = ui.row(rg)
        rh.pack(fill="x", padx=14, pady=(10, 2))
        ctk.CTkLabel(rh, text="🌍 เล่นเซิร์ฟนอกลื่นแค่ไหน — ระยะทางเน็ตจากบ้านไปแต่ละภูมิภาค", font=FB).pack(side="left")
        self.bt_probe = ui.ghost(rh, "วัดตอนนี้ (~15 วิ)", self.probe, width=140, height=30)
        self.bt_probe.pack(side="right")
        ui.note(rg, "ping ไป host ทดสอบในเมืองเดียวกับที่ Roblox ตั้งเซิร์ฟ (เซิร์ฟเกมบล็อก ping ตรง) · ระยะทางลดไม่ได้ด้วยการจูน "
                    "— ไทย→US ต่ำสุดตามฟิสิกส์ราว 180-220 ms · ที่จูนได้จริงคือ 'แพ็กเก็ตหาย/jitter' "
                    "· ถ้าลอง VPN/GPN ให้กดวัดก่อนและหลัง แล้วดูว่าดีขึ้นจริงไหม", wraplength=760).pack(anchor="w", padx=16)
        self.l_probe = ctk.CTkLabel(rg, text="", font=FS, text_color=DIM, anchor="w")
        self.l_probe.pack(fill="x", padx=16, pady=(4, 0))
        self.probe_box = ui.row(rg)
        self.probe_box.pack(fill="x", padx=14, pady=(2, 10))
        self.probe_rows = []
        self.render_probe(app.cfg.get("region_probe"), app.cfg.get("region_probe_at"))

        # ---------- เน็ตนิ่งตอนโหลดหนักไหม ----------
        bb = ui.card(self)
        bb.pack(fill="x", padx=20, pady=(8, 0))
        bh = ui.row(bb)
        bh.pack(fill="x", padx=14, pady=(10, 2))
        ctk.CTkLabel(bh, text="🛜 เน็ตนิ่งตอนมีอะไรอัปโหลดไหม (bufferbloat)", font=FB).pack(side="left")
        self.l_updown = ctk.CTkLabel(bh, text="", font=FS, text_color=DIM)
        self.l_updown.pack(side="left", padx=12)
        self.bt_bb = ui.ghost(bh, "ทดสอบ (~15 วิ)", self.bufferbloat, width=120, height=30)
        self.bt_bb.pack(side="right")
        self.v_od = ctk.BooleanVar(value=bool(app.cfg.get("pause_onedrive")))
        ctk.CTkSwitch(bh, text="หยุด OneDrive ตอนเกมเปิด", variable=self.v_od, font=FS,
                      command=lambda: (app.cfg.__setitem__("pause_onedrive", self.v_od.get()), config.save(app.cfg))).pack(side="right", padx=10)
        self.l_bb = ctk.CTkLabel(bb, text="", font=F, justify="left", anchor="w", wraplength=760)
        self.l_bb.pack(fill="x", padx=16, pady=(2, 10))
        self.render_bb(app.cfg.get("bufferbloat"))

        ctk.CTkLabel(self, text="เหตุการณ์ล่าสุด (เน็ตหลุด / หลุดจากเกม)", font=FB).pack(anchor="w", padx=20, pady=(8, 2))
        self.events = ctk.CTkTextbox(self, font=MONO, fg_color=INK, text_color=DIM)
        self.events.pack(fill="both", expand=True, padx=20, pady=(0, 12))

    def probe(self):
        self.bt_probe.configure(state="disabled", text="กำลังวัด...")
        prev = self.app.cfg.get("region_probe")

        def prog(i, n, name):
            self.app.ui(lambda: self.l_probe.configure(text=f"กำลังวัด {name} ({i + 1}/{n})" if name else ""))

        def work():
            res = netmon.probe_regions(progress=prog)
            self.app.cfg["region_probe"], self.app.cfg["region_probe_at"] = res, time.time()
            config.save(self.app.cfg)
            self.app.ui(lambda: (self.render_probe(res, time.time(), prev), self.bt_probe.configure(state="normal", text="วัดอีกครั้ง")))
        threading.Thread(target=work, daemon=True).start()

    def bufferbloat(self):
        self.bt_bb.configure(state="disabled", text="กำลังทดสอบ...")

        def work():
            r = netmon.bufferbloat_test(progress=lambda t: self.app.ui(lambda: self.l_bb.configure(text=t, text_color=DIM)))
            self.app.cfg["bufferbloat"] = r
            config.save(self.app.cfg)
            self.app.ui(lambda: (self.render_bb(r), self.bt_bb.configure(state="normal", text="ทดสอบอีกครั้ง")))
        threading.Thread(target=work, daemon=True).start()

    def render_bb(self, r):
        if not r:
            return self.l_bb.configure(text="ยังไม่เคยทดสอบ — เน็ตมือถือ/hotspot มักมีอาการนี้: พออะไรอัปโหลด ping จะพุ่งทั้งที่ความเร็วยังเหลือ", text_color=DIM)
        col = LEVEL_COLOR.get(r["level"], DIM)
        idle, up = r["idle"], r["up"]
        self.l_bb.configure(text=f"เกรด {r['grade']}  ·  ว่าง {idle['avg']:.0f} ms → ตอนอัปโหลด {up['avg']:.0f} ms (สูงสุด {up['max']:.0f}, jitter {up['jitter']:.0f}) "
                                 f"ที่ {r['up_mbps']:.0f} Mbps  ·  {time.strftime('%d/%m %H:%M', time.localtime(r['at']))}\n{r['advice']}", text_color=col)

    def render_probe(self, res, at=None, prev=None):
        for w in self.probe_box.winfo_children():
            w.destroy()
        if not res:
            return ctk.CTkLabel(self.probe_box, text="ยังไม่เคยวัด — กดปุ่มด้านขวา", font=FS, text_color=DIM).pack(anchor="w", padx=2)
        before = {r["name"]: r["avg"] for r in (prev or [])}
        grid = ui.row(self.probe_box)
        grid.pack(fill="x")
        for i, r in enumerate(res):
            col = LEVEL_COLOR.get(r["level"], DIM)
            cell = ui.row(grid)
            cell.grid(row=i // 2, column=i % 2, sticky="w", padx=(2, 18), pady=1)
            ms = f"{r['avg']:.0f} ms" if r["avg"] is not None else "ไม่ตอบ"
            delta = ""
            if r["avg"] is not None and before.get(r["name"]) is not None:
                d = r["avg"] - before[r["name"]]
                delta = f"  ({'+' if d >= 0 else ''}{d:.0f} จากครั้งก่อน)"
            ctk.CTkLabel(cell, text=f"{r['name']:<16}", font=F, width=150, anchor="w").pack(side="left")
            ctk.CTkLabel(cell, text=ms, font=FB, width=70, anchor="w", text_color=col).pack(side="left")
            ctk.CTkLabel(cell, text=f"{r['verdict']}{delta}" + (f"  · หาย {r['loss']:.0f}%" if r["loss"] else "") + (f"  · jitter {r['jitter']:.0f}" if r.get("jitter") and r["jitter"] >= 10 else ""),
                         font=FS, text_color=DIM if r["level"] != "red" else BAD, anchor="w").pack(side="left")
        if at:
            self.l_probe.configure(text=f"วัดล่าสุด {time.strftime('%d/%m %H:%M', time.localtime(at))}")

    def tick(self):
        nm = self.app.net
        txt, lvl = nm.verdict()
        self.banner.configure(text=txt, text_color=LEVEL_COLOR.get(lvl, DIM))
        for name, (lab, cv) in self.rows.items():
            st = nm.stats(name, 60)
            ip = nm.ips.get(name) or "?"
            if not st or st["avg"] is None:
                lab.configure(text=f"{ip}  ·  ไม่ตอบ" if st else f"{ip}  ·  ...", text_color=BAD if st else DIM)
            else:
                col = ACC if st["loss"] < 2 and st["avg"] < 80 else WARN if st["loss"] < 10 else BAD
                lab.configure(text=f"{ip}  ·  {st['avg']:.0f} ms (สูงสุด {st['max']})  ·  หาย {st['loss']:.0f}%  ·  jitter {st.get('jitter', 0):.0f}", text_color=col)
            cv.delete("all")
            pts = nm.series(name, 120)
            if pts:
                mx = max([r for _, r in pts if r is not None] + [50])
                w = 260 / max(1, len(pts))
                for i, (_, r) in enumerate(pts):
                    x = i * w
                    if r is None:
                        cv.create_rectangle(x, 0, x + max(w, 1), 40, fill=BAD, outline="")
                    else:
                        hgt = 36 * r / mx
                        cv.create_rectangle(x, 40 - hgt, x + max(w, 1), 40, fill=ACC, outline="")
        sc = self.app.sys.cur
        if sc.get("up_mbps") is not None:
            self.l_updown.configure(text=f"ตอนนี้ ↑ {sc['up_mbps']:.1f}  ↓ {sc['down_mbps']:.1f} Mbps",
                                    text_color=WARN if sc["up_mbps"] >= (self.app.cfg.get("upload_alert_mbps") or 3) else DIM)
        if nm.server:
            reg = f"  ·  {nm.server_region}" if nm.server_region else ""
            dc = self.app.eng.watcher.current.get("dc")
            dcl = nm.dc_label(dc, self.app.swatch.ping)
            self.l_server.configure(text=f"เซิร์ฟที่เล่นอยู่: {nm.server[0]}:{nm.server[1]}{reg}" + (f"  ·  DC {dc}" if dc is not None else "") + (f"  ·  {dcl}" if dcl else ""))
        else:
            self.l_server.configure(text="ยังไม่ได้อยู่ในเกม")
        lines = [f"{time.strftime('%d/%m %H:%M:%S', time.localtime(t))}  {s}" for t, s in list(nm.events)[:15]]
        lines += [f"{time.strftime('%d/%m %H:%M:%S', time.localtime(t))}  {s}" for t, s in self.app.game_events[:15]]
        lines.sort(reverse=True)
        self.events.configure(state="normal")
        self.events.delete("1.0", "end")
        self.events.insert("end", "\n".join(lines) or "ยังไม่มีเหตุการณ์")
        self.events.configure(state="disabled")


# =====================================================================
class FilePage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)
        ctk.CTkLabel(self, text="ตรวจไฟล์ก่อนรัน", font=FH, text_color=ACC).pack(anchor="w", padx=20, pady=(16, 0))
        ctk.CTkLabel(self, text="เช็คลายเซ็น · ถูกแพ็คด้วยอะไร · string ของ stealer · SHA-256 สำหรับ VirusTotal  (ไม่แทนแอนตี้ไวรัส)", font=FS, text_color=DIM).pack(anchor="w", padx=20)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=10)
        self.entry = ctk.CTkEntry(row, placeholder_text="วาง path ของไฟล์ .exe หรือกดเลือกไฟล์", font=F)
        self.entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="เลือกไฟล์...", width=110, font=F, command=self.pick).pack(side="left", padx=6)
        ctk.CTkButton(row, text="ตรวจ", width=80, font=F, command=self.check).pack(side="left")
        ctk.CTkButton(row, text="สแกน Downloads", width=130, font=F, fg_color=BTN, hover_color=BTNH, command=self.scan_downloads).pack(side="left", padx=6)
        self.banner = ctk.CTkLabel(self, text="", font=FB, fg_color=CARD, corner_radius=10, height=44)
        self.banner.pack(fill="x", padx=20)
        self.out = ctk.CTkTextbox(self, font=MONO, fg_color=INK, text_color=TXT2)
        self.out.pack(fill="both", expand=True, padx=20, pady=10)
        b = ctk.CTkFrame(self, fg_color="transparent")
        b.pack(fill="x", padx=20, pady=(0, 12))
        self.bt_vt = ctk.CTkButton(b, text="เปิดใน VirusTotal", font=F, state="disabled", command=self.open_vt)
        self.bt_vt.pack(side="left")
        self.bt_copy = ctk.CTkButton(b, text="คัดลอก SHA-256", font=F, fg_color=BTN, hover_color=BTNH, state="disabled", command=self.copy_sha)
        self.bt_copy.pack(side="left", padx=6)
        self.res = None

    def pick(self):
        p = filedialog.askopenfilename(filetypes=[("โปรแกรม", "*.exe *.dll *.scr *.bat *.cmd *.ps1 *.msi"), ("ทุกไฟล์", "*.*")])
        if p:
            self.entry.delete(0, "end")
            self.entry.insert(0, p)
            self.check()

    def write(self, s):
        self.out.configure(state="normal")
        self.out.delete("1.0", "end")
        self.out.insert("end", s)
        self.out.configure(state="disabled")

    def check(self):
        p = self.entry.get().strip().strip('"')
        if not os.path.isfile(p):
            self.banner.configure(text="ไม่พบไฟล์", text_color=BAD)
            return
        self.banner.configure(text="กำลังตรวจ...", text_color=DIM)
        self.write("")

        def work():
            r = filecheck.analyze(p)
            self.app.ui(lambda: self.show(r))

        threading.Thread(target=work, daemon=True).start()

    def show(self, r):
        self.res = r
        self.banner.configure(text=r["verdict"], text_color=LEVEL_COLOR[r["level"]])
        sig = r["signature"]
        pe = r["pe"]
        lines = [f"ไฟล์        {r['name']}  ({r['size'] / 1e6:.1f} MB)",
                 f"SHA-256     {r['sha256']}",
                 f"ลายเซ็น     {sig['status']}" + (f"  โดย {sig['signer']}" if sig["signer"] else "") + ("" if sig["status"] == "Valid" else "  (ไม่มี/ไม่ถูกต้อง — โปรแกรมฟรีทั่วไปมักไม่มี แต่ก็เป็นจุดที่มัลแวร์ไม่มีเช่นกัน)"),
                 f"ชนิด        {'PE ' + pe['arch'] if pe['is_pe'] else 'ไม่ใช่ไฟล์โปรแกรม Windows'}" + (f"  คอมไพล์ {time.strftime('%Y-%m-%d', time.localtime(pe['compiled']))}" if pe.get("compiled") else ""),
                 f"สร้างด้วย   {', '.join(r['packers']) or 'ไม่ทราบ'}",
                 f"entropy     {r['entropy']:.2f} / 8.00" + ("  (สูง = ถูกบีบอัด/เข้ารหัส มองข้างในไม่เห็น)" if r["entropy"] > 7.2 else ""),
                 "", f"สิ่งที่พบ ({len(r['findings'])}):  คะแนนความเสี่ยง {r['score']}"]
        for f in r["findings"]:
            lines.append(f"  [{f['score']:>2}] {f['desc']}   ←  \"{f['sample']}\" x{f['count']}")
        if not r["findings"]:
            lines.append("  ไม่พบ string น่าสงสัย" + ("  (แต่ไฟล์ถูกแพ็ค — ข้างในอาจมีอะไรก็ได้)" if r["entropy"] > 7.2 else ""))
        lines += ["", "ขั้นต่อไป: กด 'เปิดใน VirusTotal' — ถ้าไฟล์เคยมีคนอัปโหลด จะเห็นผลจาก 70 แอนตี้ไวรัสทันที ถ้ายังไม่เคย ให้อัปโหลดเอง"]
        self.write("\n".join(lines))
        self.bt_vt.configure(state="normal")
        self.bt_copy.configure(state="normal")

    def open_vt(self):
        if self.res:
            webbrowser.open(filecheck.virustotal_url(self.res["sha256"]))

    def copy_sha(self):
        if self.res:
            self.clipboard_clear()
            self.clipboard_append(self.res["sha256"])

    def scan_downloads(self):
        d = os.path.join(os.environ["USERPROFILE"], "Downloads")
        files = sorted([os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith((".exe", ".scr", ".msi", ".bat", ".cmd"))],
                       key=os.path.getmtime, reverse=True)[:40]
        self.banner.configure(text=f"กำลังสแกน {len(files)} ไฟล์ใน Downloads...", text_color=DIM)
        self.write("")

        def work():
            out = []
            for i, p in enumerate(files):
                try:
                    r = filecheck.analyze(p)
                    mark = {"green": "✅", "yellow": "🟡", "orange": "🟠", "red": "🔴"}[r["level"]]
                    out.append(f"{mark} {r['name'][:45]:<45} {r['verdict']}")
                except Exception as e:
                    out.append(f"❔ {os.path.basename(p)[:45]:<45} อ่านไม่ได้: {e}")
                self.app.ui(lambda t="\n".join(out), n=i + 1: (self.write(t), self.banner.configure(text=f"สแกนแล้ว {n}/{len(files)}")))
            self.app.ui(lambda: self.banner.configure(text=f"สแกน Downloads เสร็จ ({len(files)} ไฟล์) — คลิกไฟล์ที่สงสัยแล้ววาง path ด้านบนเพื่อดูรายละเอียด", text_color=ACC))

        threading.Thread(target=work, daemon=True).start()


# =====================================================================
class GamesPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(head, text="เกมโปรด", font=FH, text_color=ACC).pack(side="left")
        ctk.CTkButton(head, text="รีเฟรช", width=90, font=F, command=self.refresh).pack(side="right")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 8))
        self.entry = ctk.CTkEntry(row, placeholder_text="วาง placeId หรือลิงก์เกม เพื่อเพิ่ม", font=F)
        self.entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="เพิ่ม", width=80, font=F, command=self.add).pack(side="left", padx=6)
        self.l_last = ctk.CTkLabel(self, text="", font=FS, text_color=DIM)
        self.l_last.pack(anchor="w", padx=20)
        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list.pack(fill="both", expand=True, padx=12, pady=8)
        self.icons = {}
        self.loaded = False

    def on_show(self):
        if not self.loaded:
            self.refresh()

    def add(self):
        place = launcher.parse_place(self.entry.get())
        if not place:
            return self.app.log("ใส่ placeId หรือลิงก์เกมก่อน")
        launcher.add_fav(place)
        self.entry.delete(0, "end")
        self.refresh()

    def refresh(self):
        favs = launcher.load_favs()
        if not favs:  # ครั้งแรก: ดึงจากเกมที่เล่นบ่อย (ต้องสแกน log ก่อนถ้ายังไม่ได้ทำ)
            if not self.app.hist.sessions and not self.app.hist.loading:
                self.l_last.configure(text="กำลังอ่านประวัติการเล่นเพื่อหาเกมที่เล่นบ่อย...")

                def scan():
                    self.app.hist.scan()
                    self.app.ui(self.refresh)
                threading.Thread(target=scan, daemon=True).start()
                return
            for g in self.app.hist.summary(30)["games"][:6]:
                launcher.add_fav(g["place"], self.app.hist.name(g["place"]))
            favs = launcher.load_favs()
        self.loaded = True
        for w in self.list.winfo_children():
            w.destroy()
        eng = self.app.eng
        if eng.last_place:
            self.l_last.configure(text=f"เซิร์ฟล่าสุด: {self.app.place_name(eng.last_place)}  ·  job {str(eng.last_job)[:8]}…" if eng.last_job else "")
        for fav in favs:
            self.card(fav)

        def work():
            for fav in favs:
                info = launcher.game_info(fav["place"])
                if info["name"] and fav["name"].startswith("place "):
                    fav["name"] = info["name"]
                    launcher.save_favs(favs)
                    self.app.hist.cache["names"][fav["place"]] = info["name"]
                icon = session.game_icon(fav["place"])
                self.app.ui(lambda f=fav, i=info, ic=icon: self.fill(f, i, ic))
        threading.Thread(target=work, daemon=True).start()

    def card(self, fav):
        f = ctk.CTkFrame(self.list, fg_color=CARD, corner_radius=12)
        f.pack(fill="x", padx=8, pady=5)
        f.columnconfigure(1, weight=1)
        img = ctk.CTkLabel(f, text="🎮", font=FHUGE, width=72, height=72)
        img.grid(row=0, column=0, rowspan=2, padx=12, pady=10)
        name = ctk.CTkLabel(f, text=fav["name"], font=FB, anchor="w")
        name.grid(row=0, column=1, sticky="w", pady=(12, 0))
        meta = ctk.CTkLabel(f, text="กำลังโหลด...", font=FS, text_color=DIM, anchor="w")
        meta.grid(row=1, column=1, sticky="w", pady=(0, 12))
        btns = ctk.CTkFrame(f, fg_color="transparent")
        btns.grid(row=0, column=2, rowspan=2, padx=12)
        place = fav["place"]
        ctk.CTkButton(btns, text="▶ เข้าเกม", width=96, font=F, command=lambda: (launcher.launch(place), self.app.log(f"เปิดเกม {fav['name']}"))).pack(side="left", padx=3)
        ctk.CTkButton(btns, text="📶 ping ต่ำสุด", width=110, font=F, fg_color=BTN, hover_color=BTNH,
                      command=lambda: launcher.launch_best(place, self.app.log)).pack(side="left", padx=3)
        eng = self.app.eng
        if eng.last_place == place and eng.last_job:
            ctk.CTkButton(btns, text="↩ เซิร์ฟล่าสุด", width=110, font=F, fg_color=BTN, hover_color=BTNH,
                          command=lambda: (launcher.launch(place, eng.last_job), self.app.log("กลับเซิร์ฟล่าสุด"))).pack(side="left", padx=3)
        ctk.CTkButton(btns, text="✕", width=32, font=F, fg_color="transparent", hover_color=BADBG, text_color=DIM,
                      command=lambda: (launcher.remove_fav(place), self.refresh())).pack(side="left", padx=3)
        self.icons[place] = (img, name, meta)

    def fill(self, fav, info, icon_bytes):
        w = self.icons.get(fav["place"])
        if not w:
            return
        img, name, meta = w
        if info["name"]:
            name.configure(text=info["name"])
        if info["playing"] is not None:
            meta.configure(text=f"🟢 {info['playing']:,} คนกำลังเล่น  ·  {info['visits']:,} visits  ·  {info['creator'] or ''}")
        else:
            meta.configure(text="โหลดข้อมูลไม่ได้")
        if icon_bytes:
            try:
                import io
                from PIL import Image
                im = Image.open(io.BytesIO(icon_bytes)).convert("RGBA").resize((72, 72))
                cimg = ctk.CTkImage(light_image=im, dark_image=im, size=(72, 72))
                img.configure(image=cimg, text="")
                img.image = cimg
            except Exception:
                pass


# =====================================================================
class HistoryPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(head, text="ประวัติเซสชัน", font=FH, text_color=ACC).pack(side="left")
        ctk.CTkButton(head, text="โหลดใหม่", width=90, font=F, command=self.render).pack(side="right")
        ctk.CTkLabel(self, text="50 เซสชันล่าสุด · กด 🖼 เพื่อดูการ์ดสรุปของเซสชันนั้น", font=FS, text_color=DIM).pack(anchor="w", padx=20)
        self.list = ctk.CTkScrollableFrame(self, fg_color=CARD, corner_radius=12)
        self.list.pack(fill="both", expand=True, padx=20, pady=10)

    def on_show(self):
        if not self.app.hist.sessions and not self.app.hist.loading:
            threading.Thread(target=lambda: (self.app.hist.scan(), self.app.ui(self.render)), daemon=True).start()
        else:
            self.render()

    def render(self):
        for w in self.list.winfo_children():
            w.destroy()
        with self.app.hist.lock:
            sessions = list(self.app.hist.sessions)[-50:][::-1]
        if not sessions:
            ctk.CTkLabel(self.list, text="ยังไม่มีข้อมูล", font=F, text_color=DIM).pack(pady=20)
            return
        last_day = None
        for sess in sessions:
            day = time.strftime("%d/%m/%Y", time.localtime(sess["start"]))
            if day != last_day:
                ctk.CTkLabel(self.list, text=day, font=FB, text_color=ACC, anchor="w").pack(fill="x", padx=10, pady=(10, 2))
                last_day = day
            f = ctk.CTkFrame(self.list, fg_color="transparent")
            f.pack(fill="x", padx=10, pady=1)
            ctk.CTkLabel(f, text=f"{time.strftime('%H:%M', time.localtime(sess['start']))}–{time.strftime('%H:%M', time.localtime(sess['end']))}", font=FS, text_color=DIM, width=110, anchor="w").pack(side="left")
            ctk.CTkLabel(f, text=self.app.hist.name(sess["place"])[:36], font=F, anchor="w", width=300).pack(side="left")
            ctk.CTkLabel(f, text=fmt_dur(sess["end"] - sess["start"]), font=FS, text_color=TXT, width=100, anchor="w").pack(side="left")
            r = sess["reason"]
            ctk.CTkLabel(f, text=fmt_reason(r), font=FS, text_color=BAD if r not in (None, 0, -1, 285) else DIM, anchor="w", width=160).pack(side="left")
            ctk.CTkButton(f, text="🖼", width=36, height=26, font=FS, fg_color=CARD2, hover_color=BTN, command=lambda s_=sess: self.card(s_)).pack(side="right")

    def card(self, sess):
        def work():
            try:
                png = session.recap_card(self.app.hist.name(sess["place"]), sess["place"], sess["end"] - sess["start"], sess["start"], sess["end"],
                                         0 if sess["reason"] in (None, 0, -1, 285) else 1, fmt_reason(sess["reason"]), 0, 0, 0)
                out = os.path.join(config.DATA_DIR, "recap_view.png")
                open(out, "wb").write(png)
                self.app.ui(lambda: os.startfile(out))
            except Exception as e:
                self.app.log(f"การ์ด: {e}")
        threading.Thread(target=work, daemon=True).start()


# =====================================================================
class FlagPage(Page):
    """FastFlag — เขียน ClientAppSettings.json ให้ Roblox เอง ไม่ต้องพึ่ง Bloxstrap

    ทำใหม่ตาม allowlist ของ Roblox (29 ก.ย. 2025): flag ที่ไม่อยู่ในลิสต์ ใส่ไปก็ถูกเมิน
    เลยเหลือ "ระดับความแรง 5 ระดับ + ตัวเร่งกราฟิก + สวิตช์เสริม" แทนการติ๊กชุดมั่วๆ
    แล้วเตือนทันทีถ้าผู้ใช้พิมพ์ flag ที่ตายแล้ว (พวกลิสต์เก่าตามเว็บ)
    """

    def __init__(self, master, app):
        super().__init__(master, app)
        c = app.cfg
        right = ui.head(self, "FastFlag — ปรับความลื่นของเกม",
                        "สวิตช์ภายในของ Roblox เอง (ตัวเดียวกับที่ Bloxstrap ตั้งให้) · ไม่ใช่โปรแกรมโกง · กดล้างคืนได้ทุกเมื่อ", "⚡")
        ui.ghost(right, "⟳  เช็คใหม่", self.refresh, width=108).pack(side="right")

        box = ui.card(self)
        box.pack(fill="x", padx=22, pady=(2, 10))
        self.l_state = ctk.CTkLabel(box, text="กำลังตรวจ...", font=FB, justify="left", anchor="w")
        self.l_state.pack(fill="x", padx=16, pady=(12, 0))
        self.l_state2 = ctk.CTkLabel(box, text="", font=FS, text_color=DIM, justify="left", anchor="w", wraplength=700)
        self.l_state2.pack(fill="x", padx=16, pady=(2, 12))

        # แถบปุ่มล่าง — ต้อง pack ก่อนตัว body ที่ expand=True
        bar = ctk.CTkFrame(self, fg_color=CARD2, corner_radius=0)
        bar.pack(fill="x", side="bottom")
        inner = ui.row(bar)
        inner.pack(fill="x", padx=20, pady=12)
        ui.big(inner, "✅  ใช้ค่านี้", self.apply, width=140).pack(side="left")
        ui.tip(ui.ghost(inner, "⚡  ตั้งให้เร็ว (แนะนำ)", self.recommend, height=42, width=176), "ตั้งระดับ 'แรง' + ปิดหญ้า + ปิดลบรอยหยัก + ให้เกมได้ CPU ก่อน แล้วเขียนให้เลย").pack(side="left", padx=8)
        ui.danger_btn(inner, "🗑  ล้างทั้งหมด", self.clear, height=42, width=134).pack(side="left")
        self.v_auto = ctk.BooleanVar(value=c.get("ff_auto", True))
        ctk.CTkSwitch(inner, text="ใส่ให้ใหม่เองเมื่อ Roblox อัปเดต", variable=self.v_auto, font=FS,
                      command=self.set_auto).pack(side="right", padx=(10, 0))
        self.l_cnt = ctk.CTkLabel(inner, text="", font=FS, text_color=DIM)
        self.l_cnt.pack(side="right", padx=12)

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14)

        # ---------- 1 · ระดับความแรง ----------
        lv = ui.card(body)
        lv.pack(fill="x", padx=6, pady=(0, 10))
        ui.title(lv, "1 · แรงแค่ไหน")
        self.disp = {f"{ic}  {nm}": nm for nm, ic, _g, _l, _f in fastflag.LEVELS}
        self.rdisp = {v: k for k, v in self.disp.items()}
        cur_lv = c.get("ff_level") if c.get("ff_level") in self.rdisp else "ปิด"
        self.v_level = ctk.StringVar(value=self.rdisp[cur_lv])
        ctk.CTkSegmentedButton(lv, values=list(self.disp), variable=self.v_level, font=FB, height=44,
                               command=lambda _=None: self.on_pick()).pack(fill="x", padx=14, pady=(2, 10))
        self.l_gain = ctk.CTkLabel(lv, text="", font=F, text_color=ACC, justify="left", anchor="w", wraplength=660)
        self.l_gain.pack(fill="x", padx=16)
        self.l_lose = ctk.CTkLabel(lv, text="", font=FS, text_color=WARN, justify="left", anchor="w", wraplength=660)
        self.l_lose.pack(fill="x", padx=16, pady=(3, 14))

        # ---------- 2 · ตัวเร่งกราฟิก ----------
        ap = ui.card(body)
        ap.pack(fill="x", padx=6, pady=(0, 10))
        ui.title(ap, "2 · ตัวเร่งกราฟิก")
        r = ui.row(ap)
        r.pack(fill="x", padx=14, pady=(0, 2))
        self.v_api = ctk.StringVar(value=c.get("ff_api") if c.get("ff_api") in fastflag.APIS else fastflag.API_NAMES[0])
        ctk.CTkOptionMenu(r, values=fastflag.API_NAMES, variable=self.v_api, font=F, width=340,
                          command=lambda _=None: self.on_pick()).pack(side="left")
        ui.note(ap, "การ์ดจอ NVIDIA หลายรุ่นลื่นขึ้นกับ Vulkan (ลองก่อนได้เลย) · ถ้าเปิดเกมแล้วจอดำหรือเด้ง ให้กลับมาเลือก DirectX 11 หรือกดล้างทั้งหมด",
                wraplength=680).pack(anchor="w", padx=16, pady=(4, 14))

        # ---------- 3 · สวิตช์เสริม ----------
        ex = ui.card(body)
        ex.pack(fill="x", padx=6, pady=(0, 10))
        ui.title(ex, "3 · เพิ่มเติม (ไม่ติ๊กก็ได้)")
        have = c.get("ff_extras") or []
        self.v_ex = {}
        for key, (label, hint, _f) in fastflag.EXTRAS.items():
            v = ctk.BooleanVar(value=key in have)
            self.v_ex[key] = v
            ui.switch_row(ex, label, v, hint, cmd=self.on_pick)
        ctk.CTkLabel(ex, text="", height=6).pack()

        # ---------- 4 · เร่งแบบไม่ใช้ FastFlag ----------
        pr = ui.card(body)
        pr.pack(fill="x", padx=6, pady=(0, 10))
        ui.title(pr, "4 · เร่งเพิ่มแบบไม่ใช้ FastFlag")
        self.v_pri = ctk.BooleanVar(value=bool(c.get("ff_priority")))
        ui.switch_row(pr, "ให้ Roblox ได้ CPU ก่อนโปรแกรมอื่น (High priority)", self.v_pri,
                      "ยก priority ของโปรเซสเกม → Windows แบ่ง CPU ให้เกมก่อน Chrome/Discord "
                      "ไม่ยุ่งกับข้อมูลในเกมเลย และโปรแกรมจะคอยตั้งให้ใหม่ทุกครั้งที่เปิดเกม", cmd=self.set_pri)
        self.l_pri = ctk.CTkLabel(pr, text="", font=FS, text_color=DIM, anchor="w")
        self.l_pri.pack(fill="x", padx=(68, 16))
        hzr = ui.row(pr)
        hzr.pack(fill="x", padx=16, pady=(10, 0))
        self.l_hz = ctk.CTkLabel(hzr, text="", font=F, anchor="w", justify="left", wraplength=560)
        self.l_hz.pack(side="left")
        self.bt_hz = ui.ghost(hzr, "", self.max_hz, width=130, height=30)
        self.refresh_hz()
        ui.note(pr, "ℹ ปลดล็อก FPS ทาง FastFlag ใช้ไม่ได้แล้ว (Roblox ปิดตั้งแต่ 29 ก.ย. 2025) — ตั้งในเกมเอง: ESC → Settings → Frame Rate "
                    "เลือกได้ถึง 240 · ถ้าอยาก 'หรี่' FPS ตอนทิ้งฟาร์มไว้ ใช้หน้า 🖥 เครื่อง",
                wraplength=680).pack(anchor="w", padx=16, pady=(8, 14))

        # ---------- 5 · ขั้นสูง ----------
        adv = ui.card(body)
        adv.pack(fill="x", padx=6, pady=(0, 10))
        r = ui.row(adv)
        r.pack(fill="x", padx=14, pady=(12, 0))
        ctk.CTkLabel(r, text="5 · พิมพ์ flag เอง (ขั้นสูง)", font=FB).pack(side="left")
        self.bt_adv = ui.ghost(r, "เปิด", self.toggle_adv, width=72, height=28)
        self.bt_adv.pack(side="right")
        self.adv_box = ui.row(adv)
        self.t_custom = ctk.CTkTextbox(self.adv_box, height=92, font=MONO)
        self.t_custom.pack(fill="x", pady=(8, 4))
        self.t_custom.insert("1.0", c.get("ff_custom") or "")
        ui.note(self.adv_box, 'รูปแบบ: { "ชื่อflag": "ค่า" } — ถ้าใส่ flag ที่ Roblox ไม่อนุญาต โปรแกรมจะบอกให้ (ลิสต์เก่าตามเว็บส่วนใหญ่ใช้ไม่ได้แล้ว)',
                 wraplength=660).pack(anchor="w")
        ui.ghost(self.adv_box, "ตรวจที่พิมพ์", self.on_pick, width=110, height=28).pack(anchor="w", pady=(6, 0))
        self.adv_open = False
        ctk.CTkLabel(adv, text="", height=8).pack()

        self.l_warn = ctk.CTkLabel(body, text="", font=FS, text_color=WARN, justify="left", anchor="w", wraplength=700)
        self.l_warn.pack(fill="x", padx=22, pady=(0, 6))
        self.l_now = ctk.CTkLabel(body, text="", font=MONO, text_color=DIM, justify="left", anchor="w", wraplength=700)
        self.l_now.pack(fill="x", padx=22, pady=(0, 16))
        if (c.get("ff_custom") or "").strip():
            self.toggle_adv()

    # ---------- ตัวช่วย ----------
    def toggle_adv(self):
        self.adv_open = not self.adv_open
        if self.adv_open:
            self.adv_box.pack(fill="x", padx=14, pady=(0, 4))
            self.bt_adv.configure(text="ซ่อน")
        else:
            self.adv_box.pack_forget()
            self.bt_adv.configure(text="เปิด")

    def level_name(self):
        return self.disp.get(self.v_level.get(), "ปิด")

    def gather(self):
        return fastflag.build(self.level_name(), self.v_api.get(),
                              [k for k, v in self.v_ex.items() if v.get()],
                              self.t_custom.get("1.0", "end"))

    def on_show(self):
        self.refresh()
        self.on_pick()
        self.refresh_hz()

    def on_pick(self):
        """อัปเดตคำอธิบาย/คำเตือนทุกครั้งที่เปลี่ยนตัวเลือก (ยังไม่เขียนไฟล์)"""
        i = fastflag.level_index(self.level_name())
        _nm, _ic, gain, lose, _f = fastflag.LEVELS[i]
        self.l_gain.configure(text="✔  " + gain)
        self.l_lose.configure(text=("✖  " + lose) if i else "")
        flags, err, bad = self.gather()
        if err:
            self.l_warn.configure(text="⚠  " + err, text_color=BAD)
        elif bad:
            self.l_warn.configure(text="⚠  Roblox จะเมิน flag เหล่านี้ (ใส่ได้แต่ไม่มีผล):   "
                                       + "     ".join(f"{k} — {why}" for k, why in bad), text_color=WARN)
        else:
            self.l_warn.configure(text="")
        live = len([k for k in flags if k in fastflag.ALLOWLIST])
        self.l_cnt.configure(text=f"จะเขียน {len(flags)} flag (ใช้ได้จริง {live})" if flags else "ยังไม่ได้เลือกอะไร")

    def refresh(self):
        flags, _vdir = fastflag.current()
        dirs = fastflag.version_dirs()
        if not dirs:
            self.l_state.configure(text="⚠   ไม่เจอ Roblox ในเครื่อง", text_color=WARN)
            self.l_state2.configure(text="ไม่พบทั้งตัวปกติ (%LOCALAPPDATA%\\Roblox\\Versions) และตัว Microsoft Store (XboxGames\\Roblox) — ลง Roblox ก่อน")
        elif flags:
            live = len([k for k in flags if k in fastflag.ALLOWLIST])
            dead = len(flags) - live
            self.l_state.configure(text=f"🟢   มี FastFlag อยู่ {len(flags)} ตัว · ใช้ได้จริง {live} ตัว"
                                        + (f" · ถูกเมิน {dead} ตัว" if dead else ""), text_color=ACC)
            ns = sum(1 for d in dirs if fastflag.is_store(d))
            self.l_state2.configure(text=f"เจอ Roblox {len(dirs) - ns} ตัวปกติ + {ns} ตัว Microsoft Store (ใส่ให้ทุกตัว) · แก้แล้วต้องปิด-เปิดเกมใหม่ค่าถึงจะมีผล"
                                         + ("  ·  ตัวที่เปิดอยู่ตอนนี้: Microsoft Store" if fastflag.is_store(_vdir or "x") and _vdir else ""))
        else:
            self.l_state.configure(text="⚪   ยังไม่ได้ตั้ง FastFlag", text_color=DIM)
            self.l_state2.configure(text=f"เจอ Roblox {len(dirs)} เวอร์ชัน — เลือกระดับแล้วกด 'ใช้ค่านี้' โปรแกรมจะใส่ให้ทุกเวอร์ชัน")
        pri = fpscap.roblox_priority()
        name = {"high": "High (สูง)", "above": "Above normal", "normal": "ปกติ"}.get(pri)
        self.l_pri.configure(text=("ตอนนี้ Roblox อยู่ที่ priority: " + name) if name else "ยังไม่ได้เปิดเกม — จะตั้งให้ตอนเปิด")
        self.l_now.configure(text=("ที่มีผลอยู่ตอนนี้:   " + "     ".join(f"{k}={v}" for k, v in flags.items())) if flags else "")

    def refresh_hz(self):
        info = display_info()
        self.bt_hz.pack_forget()
        if not info:
            return self.l_hz.configure(text="🖥 อ่านค่าจอไม่ได้", text_color=DIM)
        w, h, hz, rates = info
        top = max(rates) if rates else hz
        if top > hz:
            self.l_hz.configure(text=f"🖥 จอตั้งอยู่ที่ {hz} Hz แต่รองรับถึง {top} Hz — เกมวาดกี่ FPS ก็เห็นแค่ {hz} ภาพ/วิ (นี่คือตัวที่ทำให้ 'ไม่ลื่น' มากกว่า FastFlag)",
                               text_color=WARN)
            self.bt_hz.configure(text=f"ใช้ {top} Hz")
            self.bt_hz.pack(side="right")
        else:
            self.l_hz.configure(text=f"🖥 จอ {w}x{h} @ {hz} Hz (สูงสุดที่รองรับแล้ว)", text_color=DIM)

    def max_hz(self):
        info = display_info()
        if not info:
            return
        top = max(info[3])
        ok, msg = set_refresh(top)
        self.app.log(("🖥 " if ok else "⚠ ") + msg + (" — ถ้าจอไม่แสดงผล ให้กด Win+Ctrl+Shift+B หรือรอ Windows คืนค่าเอง" if ok else ""))
        if ok:
            notify.toast("รีเฟรชเรตจอ", f"{msg} · ใช้แบตมากขึ้นนิดหน่อยตอนไม่เสียบสาย")
        self.refresh_hz()

    # ---------- ปุ่ม ----------
    def apply(self):
        flags, err, bad = self.gather()
        if err:
            return self.app.log("⚠ " + err)
        c = self.app.cfg
        c["ff_level"], c["ff_api"] = self.level_name(), self.v_api.get()
        c["ff_extras"] = [k for k, v in self.v_ex.items() if v.get()]
        c["ff_custom"] = self.t_custom.get("1.0", "end").strip()
        config.save(c)
        if not flags:
            n = fastflag.clear()
            self.app.log(f"เลือกระดับ 'ปิด' — ล้าง FastFlag ออกให้แล้ว ({n} เวอร์ชัน)")
        else:
            n, msg = fastflag.write(flags)
            self.app.log(f"⚡ ตั้ง FastFlag ระดับ '{self.level_name()}' {len(flags)} ตัว — {msg}")
            if n:
                notify.toast("FastFlag", f"ตั้ง {len(flags)} ตัวแล้ว — ปิด-เปิด Roblox ใหม่ค่าถึงจะมีผล")
        if bad:
            self.app.log(f"⚠ มี {len(bad)} flag ที่ Roblox ไม่อนุญาตให้ตั้งเอง — เขียนลงไปแล้วแต่เกมจะไม่สนใจ")
        self.refresh()
        self.on_pick()

    def recommend(self):
        """ตั้งค่าที่ได้ FPS เยอะสุดโดยยังเล่นเกมรู้เรื่อง"""
        self.v_level.set(self.rdisp["แรง"])
        self.v_api.set(fastflag.API_NAMES[0])
        for k, v in self.v_ex.items():
            v.set(k in ("nograss", "noaa"))
        self.v_pri.set(True)
        self.set_pri()
        self.apply()
        self.app.log("⚡ ใช้ค่าแนะนำแล้ว: ระดับแรง + ปิดหญ้า + ปิดลบรอยหยัก + ให้เกมได้ CPU ก่อน · อยากลื่นกว่านี้ลองระดับ 'โหดสุด' หรือสลับเป็น Vulkan")

    def clear(self):
        n = fastflag.clear()
        self.v_level.set(self.rdisp["ปิด"])
        self.v_api.set(fastflag.API_NAMES[0])
        for v in self.v_ex.values():
            v.set(False)
        self.t_custom.delete("1.0", "end")
        c = self.app.cfg
        c["ff_level"], c["ff_api"], c["ff_extras"], c["ff_custom"] = "ปิด", fastflag.API_NAMES[0], [], ""
        config.save(c)
        self.app.log(f"🗑 ล้าง FastFlag แล้ว ({n} เวอร์ชัน) — ปิด-เปิดเกมใหม่จะกลับเป็นค่าเดิมของ Roblox")
        self.refresh()
        self.on_pick()

    def set_pri(self):
        c = self.app.cfg
        c["ff_priority"] = self.v_pri.get()
        config.save(c)

        def work():
            on = c["ff_priority"]
            _ok, n = fpscap.set_roblox_priority("high" if on else "normal")
            if n:
                self.app.log(f"⚡ ตั้ง priority ของ Roblox เป็น {'High' if on else 'ปกติ'} แล้ว ({n} โปรเซส)")
            else:
                self.app.log("ยังไม่ได้เปิดเกม — จะตั้ง priority ให้ตอนเปิดเกม" if on else "ปิดการยก priority แล้ว")
            self.app.ui(self.refresh)
        threading.Thread(target=work, daemon=True).start()

    def set_auto(self):
        self.app.cfg["ff_auto"] = self.v_auto.get()
        config.save(self.app.cfg)


# =====================================================================
class HealthPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(head, text="สุขภาพระบบ", font=FH, text_color=ACC).pack(side="left")
        ctk.CTkButton(head, text="เช็คใหม่", width=90, font=F, command=self.refresh).pack(side="right")
        if STORE_PY:
            ctk.CTkLabel(self, text="⚠ กำลังรันจาก Python ของ Microsoft Store — ค่า registry ที่เห็นอาจไม่ใช่ของจริง (registry จำลอง) ใช้ .exe ที่ build แล้วเพื่อผลที่ถูกต้อง",
                         font=FS, text_color=WARN, wraplength=760, justify="left").pack(anchor="w", padx=20)
        self.list = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        self.list.pack(fill="x", padx=20, pady=8)
        b = ctk.CTkFrame(self, fg_color="transparent")
        b.pack(fill="x", padx=20)
        ctk.CTkButton(b, text="ซ่อมตัวเปิดเกม (handler + shortcut)", font=F, command=self.fix).pack(side="left")
        ctk.CTkButton(b, text="ล้าง log เก่ากว่า 7 วัน", font=F, fg_color=BTN, hover_color=BTNH, command=self.clean).pack(side="left", padx=6)
        self.v_auto = ctk.BooleanVar(value=health.autostart_get())
        self.v_bs = ctk.BooleanVar(value=health.bloxstrap_integration_get())
        ctk.CTkSwitch(self, text="เปิด Toolkit พร้อม Windows (ซ่อนใน tray)", variable=self.v_auto, font=F, command=self.toggle_auto).pack(anchor="w", padx=24, pady=(14, 4))
        ctk.CTkSwitch(self, text="ให้ Bloxstrap เปิด Toolkit + เริ่ม Anti-AFK ทุกครั้งที่เข้าเกม และปิดเมื่อออกเกม", variable=self.v_bs, font=F, command=self.toggle_bs).pack(anchor="w", padx=24, pady=4)
        self.msg = ctk.CTkLabel(self, text="", font=F, text_color=DIM, wraplength=760, justify="left")
        self.msg.pack(anchor="w", padx=20, pady=10)

    def on_show(self):
        self.refresh()

    def refresh(self):
        for w in self.list.winfo_children():
            w.destroy()
        for title, lvl, detail in health.check():
            f = ctk.CTkFrame(self.list, fg_color="transparent")
            f.pack(fill="x", padx=10, pady=3)
            ctk.CTkLabel(f, text="●", font=FB, text_color=LEVEL_COLOR[lvl], width=20).pack(side="left")
            ctk.CTkLabel(f, text=title, font=FB, width=220, anchor="w").pack(side="left")
            ctk.CTkLabel(f, text=detail, font=F, text_color=DIM, anchor="w").pack(side="left")

    def fix(self):
        self.msg.configure(text=health.fix_bloxstrap())
        self.refresh()

    def clean(self):
        self.msg.configure(text=f"ลบ log เก่า {health.clean_logs(7)} ไฟล์")
        self.refresh()

    def toggle_auto(self):
        try:
            health.autostart_set(self.v_auto.get())
            self.msg.configure(text="ตั้งค่าเปิดพร้อม Windows แล้ว" if self.v_auto.get() else "ยกเลิกเปิดพร้อม Windows แล้ว")
        except Exception as e:
            self.msg.configure(text=f"ตั้งไม่ได้: {e}")

    def toggle_bs(self):
        self.msg.configure(text=health.bloxstrap_integration_set(self.v_bs.get()))


# =====================================================================
class SettingsPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)
        c = app.cfg
        ctk.CTkLabel(self, text="ตั้งค่า", font=FH, text_color=ACC).pack(anchor="w", padx=22, pady=(18, 6))
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14)
        card = ctk.CTkFrame(body, fg_color=CARD, corner_radius=14)
        card.pack(fill="x", padx=6)
        ctk.CTkLabel(card, text="แจ้งเตือนเข้า Discord (webhook)", font=FB).pack(anchor="w", padx=14, pady=(12, 0))
        ctk.CTkLabel(card, text="Discord → ตั้งค่าห้อง → Integrations → Webhooks → New → Copy URL แล้ววางที่นี่ (URL นี้เก็บในเครื่องคุณเท่านั้น)", font=FS, text_color=DIM).pack(anchor="w", padx=14)
        r = ctk.CTkFrame(card, fg_color="transparent")
        r.pack(fill="x", padx=14, pady=6)
        self.e_hook = ctk.CTkEntry(r, font=F, show="•")
        self.e_hook.insert(0, c["webhook_url"])
        self.e_hook.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(r, text="ทดสอบ", width=80, font=F, command=self.test_hook).pack(side="left", padx=6)
        self.vars = {k: ctk.BooleanVar(value=c[k]) for k in ("notify_disconnect", "notify_rejoin", "notify_recap", "show_server_region", "start_afk_on_launch", "top", "watchdog", "crash_relaunch", "adaptive_delay", "watch_players", "auto_hop", "overlay")}
        for k, t in [("notify_disconnect", "แจ้งเมื่อหลุดจากเกม"), ("notify_rejoin", "แจ้งเมื่อต่อใหม่สำเร็จ/ล้มเหลว"),
                     ("notify_recap", "ส่งการ์ดสรุปหลังเล่นจบแต่ละเซสชัน (toast + Discord)"),
                     ("show_server_region", "แสดงที่ตั้งเซิร์ฟ (ถาม ipinfo.io ด้วย IP ของเซิร์ฟ — วิธีเดียวกับ Bloxstrap)"),
                     ("start_afk_on_launch", "เริ่ม Anti-AFK ทันทีเมื่อเปิดโปรแกรม"), ("top", "หน้าต่างอยู่บนสุดเสมอ"),
                     ("watchdog", "Watchdog: ถ้า Roblox ค้าง (ไม่ตอบสนอง) เกิน 30 วิ ให้ปิดแล้วเปิดกลับเซิร์ฟเดิม"),
                     ("crash_relaunch", "ถ้า Roblox ปิดตัวเอง/แครชระหว่าง Anti-AFK (ไม่ได้กดปิดเอง) ให้เปิดกลับเซิร์ฟเดิม"),
                     ("watch_players", "เฝ้าจำนวนคนในเซิร์ฟที่เล่นอยู่ (ถาม Roblox API ทุก 45 วิ)"),
                     ("auto_hop", "ย้ายไปเซิร์ฟที่คนน้อยสุดเองเมื่อคนเยอะเกิน — ทำเฉพาะตอน Anti-AFK ทำงานและไม่ได้แตะเครื่องมา 1 นาที"),
                     ("adaptive_delay", "ถ้าโดนเตะ idle ทั้งที่ Anti-AFK ทำงานอยู่ ให้ลดช่วงเวลากดลงอัตโนมัติ (-30%)"),
                     ("overlay", "Overlay มุมจอตอนเล่น (ping / เวลาเล่น / Anti-AFK) — F9 เปิด/ปิด")]:
            ctk.CTkSwitch(card, text=t, variable=self.vars[k], font=F, command=app.sync_cfg).pack(anchor="w", padx=14, pady=3)
        rowh = ctk.CTkFrame(card, fg_color="transparent")
        rowh.pack(anchor="w", padx=14, pady=(2, 4))
        ctk.CTkLabel(rowh, text="ย้ายเมื่อคนในเซิร์ฟเกิน", font=F).pack(side="left", padx=(0, 6))
        self.e_hopover = ctk.CTkEntry(rowh, width=50, font=F, justify="center")
        self.e_hopover.insert(0, str(c["hop_over"]))
        self.e_hopover.pack(side="left")
        ctk.CTkLabel(rowh, text="คน  ·  เลือกเฉพาะเซิร์ฟ ping ไม่เกิน", font=F).pack(side="left", padx=6)
        self.e_hopping = ctk.CTkEntry(rowh, width=50, font=F, justify="center")
        self.e_hopping.insert(0, str(c["hop_max_ping"]))
        self.e_hopping.pack(side="left")
        ctk.CTkLabel(rowh, text="ms", font=F).pack(side="left", padx=4)

        rowc = ctk.CTkFrame(card, fg_color="transparent")
        rowc.pack(anchor="w", padx=14, pady=(2, 4))
        ctk.CTkLabel(rowc, text="ตำแหน่ง overlay:", font=F).pack(side="left", padx=(0, 8))
        self.v_corner = ctk.StringVar(value=c["overlay_corner"])
        ctk.CTkOptionMenu(rowc, values=["top-right", "top-left", "bottom-right", "bottom-left"], variable=self.v_corner, command=lambda _: app.sync_cfg(), font=F, width=140).pack(side="left")
        ctk.CTkLabel(card, text="", height=6).pack()
        ext = ctk.CTkFrame(body, fg_color=CARD, corner_radius=14)
        ext.pack(fill="x", padx=6, pady=(12, 0))
        ui.title(ext, "🧩 ส่วนขยาย Chrome (Roblox Server Finder)")
        ui.note(ext, "จับคู่ครั้งเดียว: กดไอคอนส่วนขยายใน Chrome → ช่อง \"เชื่อมกับ Toolkit\" → พิมพ์รหัสนี้  ·  รหัสใช้ได้ครั้งเดียว หมดอายุใน 10 นาที",
                wraplength=700).pack(anchor="w", padx=16)
        er = ui.row(ext)
        er.pack(fill="x", padx=14, pady=(6, 12))
        self.l_code = ctk.CTkLabel(er, text="", font=("Consolas", 26, "bold"), text_color=ACC)
        self.l_code.pack(side="left", padx=(2, 14))
        ui.ghost(er, "สร้างรหัสใหม่", self.new_code, width=110).pack(side="left")
        ui.danger_btn(er, "ยกเลิกการจับคู่ทั้งหมด", self.unpair, width=170).pack(side="left", padx=8)
        self.l_pair = ctk.CTkLabel(er, text="", font=FS, text_color=DIM)
        self.l_pair.pack(side="left", padx=6)

        info = ctk.CTkFrame(body, fg_color=CARD, corner_radius=14)
        info.pack(fill="x", padx=6, pady=12)
        ctk.CTkLabel(info, text=f"Roblox Toolkit v{config.VERSION}", font=FB).pack(anchor="w", padx=14, pady=(12, 0))
        ctk.CTkLabel(info, text=f"ข้อมูล/ตั้งค่าเก็บที่ {config.DATA_DIR}\nโปรแกรมไม่ส่งข้อมูลออกนอกเครื่อง ยกเว้น: ชื่อเกม (Roblox API), ที่ตั้งเซิร์ฟ (ipinfo ถ้าเปิด), และ webhook ที่คุณตั้งเอง",
                     font=FS, text_color=DIM, justify="left").pack(anchor="w", padx=14, pady=(2, 8))
        extra = ctk.CTkFrame(card, fg_color="transparent")
        extra.pack(anchor="w", padx=14, pady=(2, 6))
        self.v_multi = ctk.BooleanVar(value=c["multi_instance"])
        ctk.CTkSwitch(extra, text="เปิด Roblox ได้หลายหน้าต่างพร้อมกัน (หลายบัญชี)", variable=self.v_multi, font=F, command=app.sync_cfg).pack(anchor="w")
        ctk.CTkLabel(extra, text="จองชื่อที่ Roblox ใช้กันเปิดซ้ำไว้ — ต้องเปิดก่อนแล้วค่อยเปิดเกมตัวที่สอง",
                     font=FS, text_color=DIM).pack(anchor="w", padx=44)
        io = ctk.CTkFrame(card, fg_color="transparent")
        io.pack(anchor="w", padx=14, pady=(4, 8))
        ctk.CTkButton(io, text="⬆ ส่งออกค่าตั้งทั้งหมด", width=170, font=F, fg_color=BTN, hover_color=BTNH, command=self.export_cfg).pack(side="left")
        ctk.CTkButton(io, text="⬇ นำเข้าค่าตั้ง", width=140, font=F, fg_color=BTN, hover_color=BTNH, command=self.import_cfg).pack(side="left", padx=8)
        self.l_io = ctk.CTkLabel(io, text="", font=FS, text_color=DIM)
        self.l_io.pack(side="left", padx=6)

        rr = ctk.CTkFrame(info, fg_color="transparent")
        rr.pack(anchor="w", padx=14, pady=(0, 12))
        ctk.CTkButton(rr, text="เปิดโฟลเดอร์ข้อมูล", font=F, fg_color=BTN, hover_color=BTNH, command=lambda: os.startfile(config.DATA_DIR) if os.path.isdir(config.DATA_DIR) else None).pack(side="left")
        self.e_repo = ctk.CTkEntry(rr, font=F, width=220, placeholder_text="GitHub repo เช่น user/RobloxToolkit")
        self.e_repo.insert(0, c["update_repo"])
        self.e_repo.pack(side="left", padx=(12, 6))
        ctk.CTkButton(rr, text="เช็คอัปเดต", width=100, font=F, command=self.check_update).pack(side="left")
        self.bt_install = ctk.CTkButton(rr, text="⬇ ติดตั้งเวอร์ชันใหม่", width=150, font=FB, command=self.install_update)
        self.upd_info = None
        ur = ui.row(body)
        ur.pack(fill="x", padx=22, pady=(0, 10))
        self.l_upd = ctk.CTkLabel(ur, text="", font=F, text_color=DIM, justify="left", wraplength=600)
        self.l_upd.pack(side="left")
        self.v_autoupd = ctk.BooleanVar(value=c.get("auto_update", True))
        ctk.CTkSwitch(ur, text="เช็คเวอร์ชันใหม่เองวันละครั้ง", variable=self.v_autoupd, font=FS,
                      command=lambda: (c.__setitem__("auto_update", self.v_autoupd.get()), config.save(c))).pack(side="right")

    def on_show(self):
        self.refresh_pair()

    def refresh_pair(self):
        b = self.app.bridge
        self.l_code.configure(text=b.code if b.code_valid() else "หมดอายุ", text_color=ACC if b.code_valid() else DIM)
        n = len(b.tokens())
        seen = time.time() - b.last_seen
        st = f"จับคู่แล้ว {n} ตัว" if n else "ยังไม่ได้จับคู่"
        if n and b.last_seen:
            st += " · ติดต่อล่าสุด " + (f"{int(seen)} วิที่แล้ว" if seen < 90 else f"{int(seen // 60)} นาทีที่แล้ว")
        if b.error:
            st = f"⚠ เปิดพอร์ต {bridge.PORT} ไม่ได้: {b.error}"
        self.l_pair.configure(text=st)

    def new_code(self):
        self.app.bridge.new_code()
        self.refresh_pair()

    def unpair(self):
        n = self.app.bridge.unpair_all()
        self.app.log(f"🧩 ยกเลิกการจับคู่ส่วนขยายแล้ว ({n})")
        self.refresh_pair()

    def export_cfg(self):
        self.app.sync_cfg()
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="RobloxToolkit-settings.json",
                                            filetypes=[("ไฟล์ค่าตั้ง", "*.json")])
        if not path:
            return
        try:
            import json
            data = dict(self.app.cfg)
            data.pop("webhook_url", None)      # ไม่ส่งออก URL ลับไปกับไฟล์
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"version": config.VERSION, "settings": data}, f, ensure_ascii=False, indent=2)
            self.l_io.configure(text="ส่งออกแล้ว (ไม่รวม webhook)", text_color=ACC)
        except Exception as e:
            self.l_io.configure(text=f"ส่งออกไม่ได้: {e}", text_color=BAD)

    def import_cfg(self):
        path = filedialog.askopenfilename(filetypes=[("ไฟล์ค่าตั้ง", "*.json")])
        if not path:
            return
        try:
            import json
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            got = data.get("settings", data)
            n = 0
            for k, v in got.items():
                if k in config.DEFAULTS and k != "webhook_url":
                    self.app.cfg[k] = v
                    n += 1
            config.save(self.app.cfg)
            self.l_io.configure(text=f"นำเข้า {n} ค่า — ปิดเปิดโปรแกรมใหม่ให้ครบทุกหน้า", text_color=ACC)
            self.app.log(f"นำเข้าค่าตั้ง {n} รายการจากไฟล์แล้ว")
        except Exception as e:
            self.l_io.configure(text=f"นำเข้าไม่ได้: {e}", text_color=BAD)

    def test_hook(self):
        self.app.sync_cfg()
        notify.discord(self.app.cfg["webhook_url"], "ทดสอบจาก Roblox Toolkit", "ถ้าเห็นข้อความนี้ แปลว่าตั้งค่าถูกต้อง ✓")

    def check_update(self, silent=False):
        """ดู release ล่าสุดบน GitHub — ถ้าใหม่กว่าโชว์ปุ่มติดตั้ง (silent = เช็คเองตอนเปิดโปรแกรม)"""
        self.app.sync_cfg()
        repo = self.app.cfg["update_repo"].strip()
        if not repo:
            if not silent:
                self.l_upd.configure(text="ยังไม่ได้ตั้ง repo — ใส่เป็น ชื่อGitHub/RobloxToolkit แล้วกดเช็คอีกครั้ง", text_color=DIM)
            return
        if not silent:
            self.l_upd.configure(text="กำลังเช็ค...", text_color=DIM)

        def work():
            try:
                info = updater.check(repo)
            except Exception as e:
                if not silent:
                    self.app.ui(lambda: self.l_upd.configure(text=f"เช็คไม่ได้: {e}", text_color=WARN))
                return
            self.app.cfg["update_checked"] = time.time()
            config.save(self.app.cfg)

            def show():
                if info["newer"] and info["url"]:
                    self.upd_info = info
                    self.l_upd.configure(text=f"มีเวอร์ชันใหม่ v{info['ver']} (ตอนนี้ v{config.VERSION})"
                                              + ("  ·  มี SHA256 ให้ตรวจ ✓" if info["sha256"] else "  ·  ⚠ release นี้ไม่มี SHA256"), text_color=ACC)
                    self.bt_install.pack(side="left", padx=(8, 0))
                    if silent:
                        self.app.log(f"⬆ มี Roblox Toolkit เวอร์ชันใหม่ v{info['ver']} — หน้าตั้งค่า → ติดตั้งเวอร์ชันใหม่")
                        notify.toast("Roblox Toolkit", f"มีเวอร์ชันใหม่ v{info['ver']} — ไปหน้าตั้งค่าเพื่อติดตั้ง")
                elif info["newer"]:
                    self.l_upd.configure(text=f"มี v{info['ver']} แต่ release ยังไม่มีไฟล์ .exe (Actions อาจกำลัง build อยู่)", text_color=WARN)
                elif not silent:
                    self.l_upd.configure(text=f"เป็นเวอร์ชันล่าสุดแล้ว (v{config.VERSION})", text_color=ACC)
            self.app.ui(show)

        threading.Thread(target=work, daemon=True).start()

    def install_update(self):
        info = self.upd_info
        if not info:
            return
        if not getattr(sys, "frozen", False):
            return self.l_upd.configure(text="รันจากซอร์สอยู่ — ใช้ git pull แทน (ตัว .exe ถึงจะอัปเดตเองได้)", text_color=WARN)
        self.bt_install.configure(state="disabled", text="กำลังโหลด...")

        def prog(p):
            self.app.ui(lambda: self.bt_install.configure(text=f"กำลังโหลด {p * 100:.0f}%"))

        def work():
            dest = updater.staging_path()
            try:
                updater.download(info["url"], dest, info["size"], info["sha256"], prog)
                self.app.log(f"⬆ โหลด v{info['ver']} เสร็จ ตรวจ SHA256 ผ่าน — กำลังปิดเพื่อติดตั้งแล้วเปิดใหม่")
                updater.install_and_restart(dest)
            except Exception as e:
                self.app.ui(lambda: (self.l_upd.configure(text=f"ติดตั้งไม่ได้: {e}", text_color=BAD),
                                     self.bt_install.configure(state="normal", text="⬇ ติดตั้งเวอร์ชันใหม่")))
                return
            self.app.ui(self.app.on_close)
            time.sleep(1.5)
            os._exit(0)          # เผื่อ on_close ค้าง — .bat กำลังรอเราปิดอยู่

        threading.Thread(target=work, daemon=True).start()


# =====================================================================
class App(ctk.CTk):
    TIMER_ACTIONS = ("หยุด Anti-AFK", "ปิด Roblox", "ปิด Roblox + Sleep เครื่อง", "ปิดเครื่อง")
    # ("#", "ชื่อกลุ่ม") = หัวข้อคั่น ไม่ใช่ปุ่ม
    NAV = [("#", "ใช้งาน"), ("home", "🏠   หน้าแรก"), ("afk", "🎮   Anti-AFK"), ("games", "🚀   เกมโปรด"), ("click", "🖱   ออโต้คลิก"), ("watch", "👁   เฝ้าจอ"),
           ("#", "ความลื่น"), ("flag", "⚡   FastFlag"), ("sys", "🖥   เครื่อง"), ("net", "📶   เน็ต"),
           ("#", "ย้อนดู"), ("stats", "📊   สถิติ"), ("analytics", "📈   วิเคราะห์"), ("history", "🕘   ประวัติ"),
           ("#", "อื่นๆ"), ("file", "🛡   ตรวจไฟล์"), ("health", "🩺   สุขภาพระบบ"), ("settings", "⚙   ตั้งค่า")]

    def __init__(self, args):
        super().__init__()
        self.title("Roblox Toolkit")
        self.wm_minsize(900, 600)      # ขนาดจริงตั้งทีหลัง ตอนรู้แล้วว่าเนื้อหาต้องการเท่าไหร่ (fit_window)
        self.cfg = config.load()
        if fastflag.migrate(self.cfg):      # ผู้ใช้เคยติ๊กชุดแบบเก่าไว้ → แปลงเป็นระดับ
            config.save(self.cfg)
        if not self.cfg.get("update_repo"):   # ค่าเก่าเป็นช่องว่าง → ใช้ repo ทางการ
            self.cfg["update_repo"] = config.DEFAULT_REPO
        self.q = queue.Queue()
        self.log_lines = deque(maxlen=300)   # ให้ Discord bot ดึงไปดูได้ (/afk log)
        self.game_events = []
        self.join_want = None       # {"place","job","at","src"} — เซิร์ฟที่ส่วนขยาย/บอทสั่งให้เข้า รอเทียบกับ log
        self.join_result = None     # {"ok","msg","job","at"} — ผลล่าสุด (เขียนลง status.json ให้ส่วนขยาย/บอทอ่าน)
        self.last_ram_apps = None
        self.dc_learned = None      # (job, ping) ล่าสุดที่จำ DC ไปแล้ว — กันจำซ้ำทุก 5 วิ
        self.link_events = deque(maxlen=50)   # (t, "การ์ดเน็ต X หลุด") ใช้ตอนวินิจฉัยว่าหลุดเพราะอะไร
        self.hist = History()
        self.net = NetMonitor()
        self.net.dc_map = (config.load_cache() or {}).get("dc_map") or {}
        self.net.enabled = True
        self.net.start()
        self.eng = Engine(self.log, self.on_event)
        self.apply_cfg_to_engine()
        self.tray = None
        self.sess = session.SessionTracker()
        self.overlay = Overlay(self, self.cfg["overlay_corner"])
        self.fps = fpscap.FpsCapper(self.log, self.cfg)
        self.fps.start()
        self.eng.pre_poke = self.fps.pause
        self.eng.post_poke = self.fps.resume
        self.sys = sysmon.SysMonitor(self.log, self.on_event, self.cfg)
        self.sys.start()
        self.sched = schedule.Scheduler(self)
        self.rec = None          # ตัวอัดมาโครที่กำลังทำงาน
        self.mplay = None        # ตัวเล่นมาโครที่กำลังทำงาน
        self.click = clicker.Clicker(self.log, self.on_event, self.cfg)
        self.click.start()
        self.swatch = servers.ServerWatch(self.eng, self.log, self.on_event, self.cfg)
        self.swatch.start()
        self.dog = Watchdog(self.eng, self.log, self.on_event, self.cfg["hang_seconds"])
        self.dog.enabled = self.cfg["watchdog"]
        self.dog.start()
        self.timer_end, self.timer_action = None, None
        self.watch = screenwatch.ScreenWatch(self)
        self.watch.start()
        self.ipc = ipc.CommandServer(self)
        self.ipc.start()
        self.bridge = bridge.Bridge(self)      # ส่วนขยาย Chrome คุยผ่านตัวนี้
        self.bridge.start()
        config.dbg(f"app init ok v{config.VERSION}")

        self.side = ctk.CTkFrame(self, width=212, corner_radius=0, fg_color=SIDE)
        self.side.pack(side="left", fill="y")
        self.side.pack_propagate(False)
        brand = ctk.CTkFrame(self.side, fg_color="transparent")
        brand.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(brand, text="⬢", font=FH2, text_color=ACC).pack(side="left", padx=(0, 9))
        bx = ctk.CTkFrame(brand, fg_color="transparent")
        bx.pack(side="left")
        ctk.CTkLabel(bx, text="Roblox Toolkit", font=FH3, text_color=TXT).pack(anchor="w")
        ctk.CTkLabel(bx, text="v" + config.VERSION, font=FTINY, text_color=DIM).pack(anchor="w")
        # ปุ่มล่างต้อง pack ก่อนเมนู เพราะเมนู expand=True จะกินที่เหลือทั้งหมด
        ctk.CTkButton(self.side, text="ซ่อนลง tray", font=FS, height=30, fg_color=CARD, hover_color=CARD2,
                      text_color=TXT2, command=self.to_tray).pack(side="bottom", fill="x", padx=14, pady=(6, 12))
        self.l_mini = ctk.CTkLabel(self.side, text="", font=FS, text_color=DIM, justify="left")
        self.l_mini.pack(side="bottom", anchor="w", padx=18, pady=(4, 4))
        self.dot = ctk.CTkLabel(self.side, text="  ○  กำลังเริ่ม", font=FSB, text_color=DIM, fg_color=CARD,
                                corner_radius=999, height=28, anchor="w")
        self.dot.pack(side="bottom", fill="x", padx=14, pady=(8, 0))

        nav = ctk.CTkScrollableFrame(self.side, fg_color="transparent", scrollbar_button_color=SIDE,
                                     scrollbar_button_hover_color=BTN)
        nav.pack(fill="both", expand=True, padx=0, pady=0)
        self.navbtn = {}
        for key, text in self.NAV:
            if key == "#":
                ctk.CTkLabel(nav, text=text.upper(), font=FTINY, text_color=DIM).pack(anchor="w", padx=16, pady=(8, 2))
                continue
            wrap = ctk.CTkFrame(nav, fg_color="transparent")
            wrap.pack(fill="x", padx=6, pady=1)
            bar = ctk.CTkFrame(wrap, width=3, height=26, fg_color="transparent", corner_radius=3)
            bar.pack(side="left", fill="y", padx=(0, 5))
            b = ctk.CTkButton(wrap, text=text, anchor="w", font=F, height=30, corner_radius=9, fg_color="transparent",
                              hover_color=CARD, text_color=TXT2, command=lambda k=key: self.show(k))
            b.pack(side="left", fill="x", expand=True)
            self.navbtn[key] = (b, bar)

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(side="left", fill="both", expand=True)
        self.pages = {"home": HomePage(self.container, self), "afk": AfkPage(self.container, self), "games": GamesPage(self.container, self), "stats": StatsPage(self.container, self),
                      "analytics": AnalyticsPage(self.container, self), "click": ClickPage(self.container, self),
                      "sys": SysPage(self.container, self), "flag": FlagPage(self.container, self),
                      "history": HistoryPage(self.container, self), "net": NetPage(self.container, self), "file": FilePage(self.container, self),
                      "health": HealthPage(self.container, self), "settings": SettingsPage(self.container, self), "watch": WatchPage(self.container, self)}
        self.current = None
        self.show("home" if not self.cfg.get("seen_home") or True else "afk")
        self.fit_window()

        if self.cfg.get("multi_instance"):
            fpscap.multi_instance(True)
        self.sched.start()
        def _safe_reapply():
            try:
                self.reapply_flags()
            except Exception as e:
                config.dbg(f'reapply_flags: {e}')
        threading.Thread(target=_safe_reapply, daemon=True).start()
        if self.cfg.get("auto_update", True) and self.cfg.get("update_repo") and time.time() - self.cfg.get("update_checked", 0) > 86400:
            self.after(8000, lambda: self.pages["settings"].check_update(silent=True))
        self.pages["afk"].refresh_jobs()
        self.setup_tray()
        HK_NAME = {VK_F8: "F8", VK_F9: "F9", VK_F6: "F6", VK_F7: "F7", VK_F4: "F4", VK_F5: "F5"}
        threading.Thread(target=hotkey_loop, args=({VK_F8: lambda: self.ui(self.toggle_afk), VK_F9: lambda: self.ui(self.toggle_overlay),
                                                    VK_F6: lambda: self.ui(self.click.toggle), VK_F7: lambda: self.ui(self.click.add_point),
                                                    VK_F4: lambda: self.ui(self.toggle_record), VK_F5: lambda: self.ui(self.play_macro)},
                                                   lambda vk: self.log(f"⚠ ลงทะเบียนปุ่มลัด {HK_NAME.get(vk, vk)} ไม่ได้ (โปรแกรมอื่นใช้อยู่)")), daemon=True).start()
        if self.cfg["overlay"]:
            self.after(1200, self.overlay.show)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.attributes("-topmost", self.cfg["top"])
        if "--afk" in args or self.cfg["start_afk_on_launch"]:
            self.after(1500, lambda: self.eng.start(self.cfg["immediate"]))
        if "--tray" in args:
            self.after(300, self.to_tray)
        self.pump()
        self.tick()

    def fit_window(self):
        """ตั้งขนาดหน้าต่างให้พอดีกับหน้าที่ใหญ่ที่สุด แล้ววางกลางจอ

        อย่าใส่ตัวเลขตายตัว — สเกล DPI ของ customtkinter ไม่ตรงกันระหว่าง .py กับ .exe
        แต่ winfo_req* กับ geometry อยู่ในหน่วยเดียวกันเสมอ วัดเอาชัวร์กว่า
        """
        try:
            self.update_idletasks()
            need_w = self.side.winfo_reqwidth() + max(p.winfo_reqwidth() for p in self.pages.values()) + 12
            need_h = max(p.winfo_reqheight() for p in self.pages.values()) + 12
        except Exception as e:
            config.dbg(f"fit_window: {e}")
            need_w, need_h = 1120, 780
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        ww = max(900, min(need_w, int(sw * 0.92)))
        wh = max(600, min(need_h, int(sh * 0.90)))
        self.wm_geometry(f"{ww}x{wh}+{max(0, (sw - ww) // 2)}+{max(0, (sh - wh) // 2 - 20)}")
        config.dbg(f"window {ww}x{wh} · เนื้อหาต้องการ {need_w}x{need_h} · จอ {sw}x{sh}")

    def ui(self, fn):
        """เรียกจาก thread ไหนก็ได้ — fn จะถูกรันบน main thread"""
        self.q.put(fn)

    def pump(self):
        try:
            while True:
                self.q.get_nowait()()
        except queue.Empty:
            pass
        except Exception:
            pass
        self.after(40, self.pump)

    # ---------- nav ----------
    def show(self, key):
        if self.current:
            self.pages[self.current].pack_forget()
            b, bar = self.navbtn[self.current]
            b.configure(fg_color="transparent", text_color=TXT2, font=F)
            bar.configure(fg_color="transparent")
        self.current = key
        self.pages[key].pack(fill="both", expand=True)
        b, bar = self.navbtn[key]
        b.configure(fg_color=CARD, text_color=ACC, font=FB)
        bar.configure(fg_color=ACC)
        self.pages[key].on_show()

    # ---------- cfg ----------
    def sync_cfg(self):
        p = self.pages
        c = self.cfg
        a = p["afk"]
        c["delay"], c["action"] = int(a.v_delay.get()), a.v_action.get()
        for k, v in a.vars.items():
            c[k] = v.get()
        s = p["settings"]
        for k, v in s.vars.items():
            c[k] = v.get()
        c["webhook_url"] = s.e_hook.get().strip()
        c["update_repo"] = s.e_repo.get().strip()
        c["overlay_corner"] = s.v_corner.get()
        y = p["sys"]
        c["sys_alerts"] = y.v_alerts.get()
        c["auto_trim_ram"] = y.v_trim.get()
        c["game_mode"] = y.v_game.get()
        c["fps_cap_on"], c["fps_unlock_focus"], c["automute"] = y.v_fps.get(), y.v_unlock.get(), y.v_mute.get()
        try:
            c["fps_cap"] = int(y.v_fpsn.get())
        except ValueError:
            pass
        want_multi = s.v_multi.get()
        if want_multi != fpscap.multi_instance_on():
            ok = fpscap.multi_instance(want_multi)
            self.log(("เปิดหลายหน้าต่างได้แล้ว — เปิดเกมตัวที่สองได้เลย" if fpscap.multi_instance_owned() else
                      "Roblox เปิดอยู่เลยยังยึดกุญแจไม่ได้ — พอปิด Roblox ทุกจอครั้งหนึ่ง Toolkit จะยึดให้เอง (จะแจ้งเตือน) แล้วหลังจากนั้นเปิดกี่จอก็ได้") if ok and want_multi else
                     ("ยกเลิกโหมดหลายหน้าต่างแล้ว" if not want_multi else "จองไม่สำเร็จ (อาจมีโปรแกรมอื่นจองอยู่)"))
        c["multi_instance"] = fpscap.multi_instance_on()
        try:
            c["gpu_temp_limit"] = max(50, min(105, int(float(y.e_temp.get()))))
        except ValueError:
            pass
        k = p["click"]
        c["click_mode"], c["click_button"] = k.v_mode.get(), k.v_btn.get()
        c["click_cps"] = int(k.v_cps.get())
        c["click_trigger"] = k.v_trig.get()
        c["click_type"] = {"คลิกเดี่ยว": 1, "ดับเบิลคลิก": 2, "ทริปเปิลคลิก": 3}[k.v_type.get()]
        c["click_restore_cursor"] = k.v_restore.get()
        for key, var in k.vars.items():
            c[key] = var.get()
        c["macro_only_roblox"] = k.v_mroblox.get()
        for key, ent, lo, hi in (("macro_loops", k.e_loops, 0, 9999), ("macro_speed", k.e_speed, 0.1, 10.0)):
            try:
                c[key] = max(lo, min(hi, float(ent.get()) if key == "macro_speed" else int(float(ent.get()))))
            except ValueError:
                pass
        for ent, kname, kvk in ((k.e_key, "click_key", "click_vk"), (k.e_hold, "click_hold_key", "click_hold_vk")):
            vk = clicker.vk_of(ent.get())
            if vk:
                c[kname], c[kvk] = ent.get().strip().lower(), vk
        for key, ent, lo, hi in (("click_burst_pause", k.e_bpause, 0.0, 60.0), ("click_interval_ms", k.e_ms, 0.0, 5000.0)):
            try:
                c[key] = max(lo, min(hi, float(ent.get())))
            except ValueError:
                pass
        for key, ent, lo, hi in (("click_rand_min", k.e_rmin, 10, 300), ("click_rand_max", k.e_rmax, 10, 300),
                                 ("click_burst", k.e_burst, 0, 100000),
                                 ("click_max_min", k.e_min, 0, 1440), ("click_max_clicks", k.e_max, 0, 10 ** 7),
                                 ("hop_over", s.e_hopover, 1, 100), ("hop_max_ping", s.e_hopping, 20, 500)):
            try:
                c[key] = max(lo, min(hi, int(float(ent.get()))))
            except ValueError:
                pass
        self.overlay.corner = c["overlay_corner"]
        self.dog.enabled = c["watchdog"]
        if c["overlay"] and not self.overlay.visible:
            self.overlay.show()
        elif not c["overlay"] and self.overlay.visible:
            self.overlay.hide()
        self.apply_cfg_to_engine()
        self.attributes("-topmost", c["top"])
        config.save(c)

    def refresh_all_pages(self):
        """โหมดสำเร็จรูปเปลี่ยนค่าหลายอย่างพร้อมกัน — ต้องอัปเดตสวิตช์ในทุกหน้าให้ตรงด้วย"""
        c = self.cfg
        try:
            a = self.pages["afk"]
            for k, v in a.vars.items():
                v.set(c[k])
            st = self.pages["settings"]
            for k, v in st.vars.items():
                v.set(c[k])
            y = self.pages["sys"]
            y.v_fps.set(c["fps_cap_on"])
            y.v_fpsn.set(str(c["fps_cap"]))
            y.v_unlock.set(c["fps_unlock_focus"])
            y.v_mute.set(c["automute"])
            y.v_game.set(c["game_mode"])
            y.v_alerts.set(c["sys_alerts"])
            y.v_trim.set(c.get("auto_trim_ram", False))
        except Exception as ex:
            config.dbg(f"refresh_all_pages: {ex}")

    def apply_cfg_to_engine(self):
        e, c = self.eng, self.cfg
        e.delay, e.action, e.invisible = c["delay"], c["action"], c["invisible"]
        e.wait_idle, e.auto_rejoin = c["wait_idle"], c["auto_rejoin"]
        e.adaptive = c["adaptive_delay"]
        if hasattr(self, "dog"):
            self.dog.crash_relaunch = c["crash_relaunch"]

    # ---------- engine callbacks ----------
    def log(self, s):
        self.log_lines.append(time.strftime("%H:%M:%S ") + s)
        self.ui(lambda: self.pages["afk"].append_log(s))

    def place_name(self, place):
        return self.hist.name(place) if place else ""

    def toggle_overlay(self):
        on = self.overlay.toggle()
        self.cfg["overlay"] = on
        try:
            self.pages["settings"].vars["overlay"].set(on)
        except Exception:
            pass
        config.save(self.cfg)

    def finish_session(self, reason_txt):
        """จบเซสชัน → การ์ดสรุป (toast + webhook) """
        rec = self.sess.end()
        if not rec:
            return
        name = self.place_name(rec["place"])
        st = self.net.stats("อินเทอร์เน็ต", 3600) or {}
        self.game_events.insert(0, (time.time(), f"จบเซสชัน {name} · {fmt_dur(rec['duration'])}"))
        if not self.cfg["notify_recap"]:
            return

        def work():
            try:
                png = session.recap_card(name, rec["place"], rec["duration"], rec["start"], rec["end"], rec["disconnects"], reason_txt,
                                         rec["net_avg"], st.get("loss", 0), rec["pokes"])
                out = os.path.join(config.DATA_DIR, "recap.png")
                open(out, "wb").write(png)
                notify.toast(f"จบเซสชัน {name}", f"เล่น {fmt_dur(rec['duration'])} · {reason_txt}")
                session.webhook_image(self.cfg["webhook_url"], png, "", "recap.png")
            except Exception as e:
                self.log(f"recap: {e}")
        threading.Thread(target=work, daemon=True).start()

    def on_event(self, kind, d):
        c = self.cfg
        if kind == "hang":
            self.game_events.insert(0, (time.time(), f"Roblox ค้าง {d['seconds']} วิ → เปิดใหม่"))
            notify.discord(c["webhook_url"], "⚠ Roblox ค้าง", f"ไม่ตอบสนอง {d['seconds']} วิ — กำลังปิดแล้วเปิดกลับเซิร์ฟเดิม", 0xFFC857)
            return
        if kind == "roblox_closed":
            self.finish_session("Roblox ปิดตัวเอง (แครช?)" if d.get("crashed") else "ปิดเกม")
            return
        if kind == "crash":
            self.game_events.insert(0, (time.time(), "Roblox ปิดตัวเอง (แครช?) → เปิดกลับเซิร์ฟเดิม"))
            notify.toast("Roblox ปิดตัวเอง", "น่าจะแครช — กำลังเปิดกลับเซิร์ฟเดิม")
            notify.discord(c["webhook_url"], "⚠ Roblox ปิดตัวเอง (แครช?)", f"เกม: {self.place_name(d.get('place'))} — กำลังเปิดกลับเซิร์ฟเดิม", 0xFFC857)
            return
        if kind == "game_mode":
            self.game_events.insert(0, (time.time(), f"โหมดเล่นเกม: คืน VRAM {d['freed']:.0f} MB"))
            return
        if kind == "sys_alert":
            self.game_events.insert(0, (time.time(), d["title"]))
            self.log(f"⚠ {d['title']} — {d['body']}")
            notify.toast(d["title"], d["body"])
            notify.discord(c["webhook_url"], "⚠ " + d["title"], d["body"], d["color"])
            return
        if kind == "watch_hit":
            txt = f"👁 เจอ '{d['word']}' บนจอ: {d['line']}"
            self.game_events.insert(0, (time.time(), txt))
            self.log(txt)
            notify.toast(f"เจอ {d['word']}!", d["line"][:80])
            if c.get("watch_beep", True):
                threading.Thread(target=lambda: [u.MessageBeep(0x40), time.sleep(0.25), u.MessageBeep(0x40)], daemon=True).start()
            notify.discord_file(c["webhook_url"], f"👁 เจอ {d['word']}!", d["line"], d["image"], 0xFFC857)
            self.ui(self.pages["watch"].refresh)
            return
        if kind == "ram_trim":
            msg = f"คืนแรมอัตโนมัติ: {d['procs']} โปรเซส · ว่างเพิ่ม {d['freed']:.0f} MB ({d['before']:.0f}% → {d['after']:.0f}%)"
            self.game_events.insert(0, (time.time(), "🧹 " + msg))
            self.log("🧹 " + msg)
            return
        if kind == "link":
            txt = f"การ์ดเน็ต '{d['name']}' {'กลับมาแล้ว' if d['up'] else 'หลุด'}"
            self.link_events.appendleft((time.time(), txt))
            self.game_events.insert(0, (time.time(), ("🔌 " if d["up"] else "⚠ ") + txt))
            self.net.events.appendleft((time.time(), txt))
            self.log(("🔌 " if d["up"] else "⚠ ") + txt)
            return
        if kind == "click_points":
            self.ui(self.pages["click"].refresh_points)
            return
        if kind == "click_state":
            self.ui(self.refresh_tray)
            return
        if kind == "poke_failing":
            self.game_events.insert(0, (time.time(), "Anti-AFK กดไม่ติด — เสี่ยงโดนเตะ idle"))
            notify.toast("Anti-AFK กดไม่ติด", "กดไม่ติด 2 ครั้งติด กำลังลองใหม่ทุก 1 นาที — เช็คว่า Roblox ยังเปิดอยู่ไหม")
            notify.discord(c["webhook_url"], "⚠ Anti-AFK กดไม่ติด", "กดไม่ติด 2 ครั้งติดกัน กำลังลองใหม่ทุก 1 นาที (ปกติ Roblox เตะที่ไม่ขยับ 20 นาที)", 0xFFC857)
            return
        if kind == "players":
            return
        if kind == "hop_start":
            self.game_events.insert(0, (time.time(), f"ย้ายเซิร์ฟ: {d['from']} คน → เซิร์ฟที่มี {d['to']} คน"))
            notify.discord(c["webhook_url"], "🔀 ย้ายไปเซิร์ฟที่เงียบกว่า",
                           f"เซิร์ฟเดิมมี {d['from']} คนแล้ว → ย้ายไปเซิร์ฟที่มี {d['to']} คน (ping {d.get('ping')} ms)", 0x2EE6A8)
            return
        if kind == "hop":
            self.game_events.insert(0, (time.time(), "ย้ายเซิร์ฟสำเร็จ"))
            self.swatch.last_scan = 0
            return
        if kind == "hop_failed":
            self.game_events.insert(0, (time.time(), "ย้ายเซิร์ฟไม่สำเร็จ"))
            if self.join_want:
                self.set_join_result(False, "เข้าเซิร์ฟที่เลือกไม่ได้ (อาจเต็มไปก่อน) — กดหาเซิร์ฟใหม่")
            notify.toast("ย้ายเซิร์ฟไม่สำเร็จ", "เข้าเซิร์ฟที่เลือกไม่ได้ (อาจเต็มไปก่อน)")
            return
        if kind == "zombie":
            self.game_events.insert(0, (time.time(), f"ปิด Roblox ที่ค้างเบื้องหลัง (RAM {d['mb']:.0f} MB)"))
            return
        if kind == "adapt":
            self.cfg["delay"] = d["delay"]
            config.save(self.cfg)
            self.ui(lambda: (self.pages["afk"].v_delay.set(d["delay"]), self.pages["afk"].upd_delay()))
            notify.toast("ปรับ Anti-AFK", f"โดนเตะ idle ทั้งที่ทำงานอยู่ → กดถี่ขึ้นเป็นทุก {d['delay']} วิ")
            notify.discord(c["webhook_url"], "🔧 ปรับ Anti-AFK อัตโนมัติ", f"โดนเตะ idle ทั้งที่ Anti-AFK ทำงานอยู่ → ลดช่วงเวลากดเหลือทุก {d['delay']} วิ", 0xFFC857)
            return
        if kind == "poke":
            self.sess.pokes += d.get("count", 0) and 1
            return
        if kind == "join":
            self.sess.begin(d["place"])
            threading.Thread(target=self.hist.resolve_names, args=([d["place"]],), daemon=True).start()
            self.check_join(d)
        elif kind == "server":
            self.net.set_server(d["ip"], d["port"], c["show_server_region"])
        elif kind == "dc":
            self.net.server_dc = d["id"]
            known = self.net.dc_map.get(str(d["id"]))
            self.log(f"🏢 datacenter {d['id']}" + (f" — เคยเจอ {known.get('n')} ครั้ง {self.net.dc_label(d['id'])}" if known else " (ใหม่ ยังไม่รู้ ping)"))
        elif kind == "disconnect":
            cause = ""
            if d["reason"] != 285:
                self.sess.disconnects += 1
                # วิเคราะห์เน็ตเฉพาะตอนหลุดแบบ "การเชื่อมต่อหาย" — โดนเตะ/ล็อกอินที่อื่น/เซิร์ฟปิด สาเหตุคือรหัสนั้นเอง ไม่ใช่เน็ต
                if d["reason"] in (277, 266, 276, 260, 262):
                    cause, kind_ = self.net.diagnose_drop()
                else:
                    cause, kind_ = d["text"], "kick"
                links = [txt for t, txt in self.link_events if t >= time.time() - 120]
                wifi = self.sys.wifi
                extra = (" · " + ", ".join(links[:2]) if links else "") + (f" · Wi-Fi '{wifi[0]}' {wifi[1]}%" if wifi and wifi[1] is not None else "")
                short = {"link": "สาย/Wi-Fi หลุด", "isp": "มือถือหลุดจากเสา", "loss": "เน็ตสะดุด", "server": "ฝั่งเซิร์ฟ", "kick": d["text"], "gray": "?"}.get(kind_, "?")
                config.add_drop({"t": time.time(), "reason": d["reason"], "text": d["text"], "place": d.get("place"), "place_name": self.place_name(d.get("place")),
                                 "kind": kind_, "cause": cause + extra, "cause_short": short, "dc": self.eng.watcher.current.get("dc"),
                                 "wifi": wifi, "links": links[:3]})
                self.game_events.insert(0, (time.time(), f"หลุดจากเกม: {d['text']} ({self.place_name(d['place'])}) — {short}"))
                self.log(f"🔎 สาเหตุที่หลุด: {cause}{extra}")
            self.finish_session(d["text"])
            if d["reason"] != 285 and c["notify_disconnect"]:
                notify.toast("หลุดจากเกม", d["text"] + f" — {cause}" + (" — กำลังต่อใหม่" if c["auto_rejoin"] else ""))
                notify.discord(c["webhook_url"], "⚠ หลุดจากเกม", f"{d['text']} (code {d['reason']})\nสาเหตุ: {cause}{extra}\nเกม: {self.place_name(d['place'])}\n{'กำลังต่อใหม่อัตโนมัติ...' if c['auto_rejoin'] else ''}", 0xFF5D7A)
        elif kind == "rejoin":
            self.game_events.insert(0, (time.time(), f"ต่อใหม่สำเร็จ (ครั้งที่ {d['attempt']})"))
            if c["notify_rejoin"]:
                notify.discord(c["webhook_url"], "✓ กลับเข้าเกมแล้ว", f"เกม: {self.place_name(d['place'])} · ลอง {d['attempt']} ครั้ง")
        elif kind == "rejoin_failed":
            self.game_events.insert(0, (time.time(), "ต่อใหม่ไม่สำเร็จ"))
            if c["notify_rejoin"]:
                notify.toast("ต่อใหม่ไม่สำเร็จ", "ลอง 5 ครั้งแล้ว ต้องเข้าเองนะ")
                notify.discord(c["webhook_url"], "✗ ต่อใหม่ไม่สำเร็จ", f"เกม: {self.place_name(d['place'])} — ต้องเข้าเอง", 0xFF5D7A)
        elif kind == "state":
            self.ui(self.refresh_tray)
            if c["automute"]:
                threading.Thread(target=self.apply_mute, args=(bool(d.get("running")),), daemon=True).start()

    # ---------- ยืนยันว่าเข้าเซิร์ฟที่สั่งจริงไหม (ส่วนขยาย/บอทสั่ง join) ----------
    def set_join_result(self, ok, msg, job=None):
        want, self.join_want = self.join_want, None
        self.join_result = {"ok": ok, "msg": msg, "job": job, "wanted": (want or {}).get("job"), "at": time.time()}
        self.game_events.insert(0, (time.time(), ("✓ " if ok else "✗ ") + msg))
        self.log(("✓ " if ok else "⚠ ") + msg)
        notify.toast("เข้าเซิร์ฟที่เลือกแล้ว" if ok else "เข้าเซิร์ฟที่เลือกไม่ได้", msg)

    def check_join(self, d):
        want = self.join_want
        if not want:
            return
        job = (d.get("job") or "").lower()
        if str(d.get("place")) != want["place"]:
            return          # เข้าเกมอื่น (ผู้ใช้กดเองระหว่างรอ) — ไม่ใช่ผลของคำสั่ง
        name = self.place_name(want["place"])
        if not want["job"] or job == want["job"]:
            self.set_join_result(True, f"เข้าเซิร์ฟที่เลือกแล้ว — {name}", job)
            self.swatch.last_scan = 0
        else:
            self.set_join_result(False, f"เข้า {name} แล้วแต่ไม่ใช่เซิร์ฟที่เลือก (เต็มไปก่อน? Roblox สุ่มให้)", job)

    def toggle_afk(self):
        if self.eng.running:
            self.eng.stop()
            self.log("หยุดแล้ว")
        else:
            self.sync_cfg()
            self.eng.start(self.cfg["immediate"])
            self.log(f"เริ่ม — ทุก {self.eng.delay} วิ")
        u.MessageBeep(0)

    # ---------- tray ----------
    def setup_tray(self):
        if not pystray:
            return
        menu = pystray.Menu(
            pystray.MenuItem("แสดงหน้าต่าง", lambda: self.ui(self.show_win), default=True),
            pystray.MenuItem(lambda i: "หยุด Anti-AFK (F8)" if self.eng.running else "เริ่ม Anti-AFK (F8)", lambda: self.ui(self.toggle_afk)),
            pystray.MenuItem("ออก", lambda: self.ui(self.on_close)))
        self.tray = pystray.Icon("RobloxToolkit", tray_image(False), "Roblox Toolkit", menu)
        self.tray.run_detached()

    def refresh_tray(self):
        if self.tray:
            self.tray.icon = tray_image(self.eng.running)
            self.tray.title = "Roblox Toolkit — " + ("Anti-AFK ทำงานอยู่" if self.eng.running else "หยุด")

    def to_tray(self):
        if self.tray:
            self.withdraw()

    def show_win(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    # ---------- ตารางเวลา ----------
    def reapply_flags(self):
        """Roblox อัปเดต = โฟลเดอร์เวอร์ชันใหม่ ไม่มี FastFlag ติดไปด้วย — ใส่ให้ใหม่ตอนเปิดโปรแกรม"""
        time.sleep(4)
        c = self.cfg
        if not c.get("ff_auto"):
            return
        flags, err, _bad = fastflag.build(c.get("ff_level") or "ปิด", c.get("ff_api") or "อัตโนมัติ",
                                          c.get("ff_extras") or [], c.get("ff_custom", ""))
        if err or not flags:
            return
        if any(fastflag.read(d) != flags for d in fastflag.version_dirs()):
            n, msg = fastflag.write(flags)
            self.log(f"⚙ ใส่ FastFlag ให้เวอร์ชันใหม่อัตโนมัติ ({len(flags)} ตัว) — {msg}")

    def run_scheduled(self, job):
        act = job.get("action")
        self.log(f"🔁 ถึงเวลาตามตาราง {job.get('time')} → {act}")
        notify.toast("Roblox Toolkit", f"ตามตารางเวลา: {act}")
        self.game_events.insert(0, (time.time(), f"ตารางเวลา: {act}"))
        try:
            if act == "เริ่ม Anti-AFK":
                self.sync_cfg()
                self.eng.start(self.cfg["immediate"])
            elif act == "หยุด Anti-AFK":
                self.eng.stop()
            elif act == "เปิดเกมล่าสุด":
                place = self.eng.last_place or (self.eng.watcher.current or {}).get("place")
                if place:
                    launcher.launch(place, self.eng.last_job)
                else:
                    self.log("ยังไม่รู้ว่าเกมล่าสุดคือเกมไหน")
            elif act == "รีเซ็ตตัวละคร":
                threading.Thread(target=self.eng.reset_character, daemon=True).start()
            elif act == "ย้ายไปเซิร์ฟเงียบ":
                cur = self.eng.watcher.current
                place = cur.get("place") or self.eng.last_place
                if place:
                    self.swatch.go(place, exclude=cur.get("job"))
                else:
                    self.log("ยังไม่ได้อยู่ในเกม ข้ามการย้ายเซิร์ฟ")
            else:
                self.power({"ปิด Roblox": "close_roblox", "ปิด Roblox + Sleep เครื่อง": "sleep", "ปิดเครื่อง": "shutdown"}[act], "ตารางเวลา")
        except Exception as e:
            self.log(f"ทำตามตารางไม่สำเร็จ: {e}")

    # ---------- มาโคร ----------
    def toggle_record(self):
        try:
            self.fps.paused = True
            self.fps.release()          # สำคัญมาก ไม่ปล่อยเธรดคืน เกมจะค้างถาวร
            if self.cfg.get("automute"):
                fpscap.set_roblox_muted(False)
        except Exception:
            pass
        if self.rec:
            self.rec.stop()
            self.rec = None
            self.log("⏹ หยุดอัดแล้ว กำลังบันทึก...")
            return
        if self.mplay:
            return self.log("กำลังเล่นมาโครอยู่ กด F5 หยุดก่อน")
        self.sync_cfg()
        self.rec = macro.Recorder(self.on_recorded, ignore_vks=(VK_F4, VK_F5, VK_F6, VK_F7, VK_F8, VK_F9))
        self.rec.start()
        self.log("🎬 กำลังอัด... ทำสิ่งที่อยากให้ทำซ้ำ แล้วกด F4 อีกทีเพื่อหยุด")

    def on_recorded(self, events):
        """เรียกจากเธรดตัวอัด — เซฟแล้วรีเฟรชรายการ"""
        if len(events) < 2:
            return self.log("ไม่ได้อัดอะไรเลย (ไม่มีการขยับเมาส์หรือกดปุ่ม)")
        name = time.strftime("มาโคร %d-%m %H.%M")
        macro.macro_save(name, events)
        i = macro.macro_info(name)
        self.log(f"💾 บันทึก '{name}' — ยาว {i['seconds']:.1f} วิ · {i['events']} เหตุการณ์")
        self.ui(lambda: (self.pages["click"].refresh_macros(), self.pages["click"].v_macro.set(name), self.pages["click"].show_macro()))

    def play_macro(self):
        if self.mplay:
            self.mplay.stop()
            return self.log("⏹ สั่งหยุดมาโครแล้ว")
        if self.rec:
            return self.log("กำลังอัดอยู่ กด F4 หยุดก่อน")
        self.sync_cfg()
        name = self.pages["click"].v_macro.get()
        events = macro.macro_load(name) if name and name != "—" else []
        if not events:
            return self.log("ยังไม่มีมาโครให้เล่น — กด F4 อัดก่อน")
        c = self.cfg
        self.log(f"▶ เล่นมาโคร '{name}' {'วนไม่หยุด' if not c['macro_loops'] else str(c['macro_loops']) + ' รอบ'} ที่ความเร็ว {c['macro_speed']}x")
        self.mplay = macro.Player(events, self.log, self.on_macro_done, c["macro_loops"], c["macro_speed"], c["macro_only_roblox"])
        self.mplay.start()

    def on_macro_done(self, rounds):
        self.mplay = None
        self.log(f"⏹ มาโครจบแล้ว (เล่นไป {rounds} รอบ)")

    # ---------- timer / power ----------
    def set_timer(self, mins, action):
        """ตั้ง (mins > 0) หรือยกเลิก (mins = 0) ตัวตั้งเวลา — ใช้ทั้งจากหน้าจอและจาก Discord"""
        if not mins or not action:
            if self.timer_end:
                self.log("ยกเลิกตั้งเวลา")
            self.timer_end = self.timer_action = None
            return
        self.timer_end, self.timer_action = time.time() + mins * 60, action
        self.log(f"⏰ อีก {mins} นาที จะ: {action}")

    def power(self, act, source="ตั้งเวลา"):
        """sleep · shutdown · close_roblox · cancel — หยุด Anti-AFK, เอาหน้าต่างที่ซ่อนกลับมา, ปิด Roblox ก่อนเสมอ"""
        if act == "cancel":
            os.system("shutdown /a")
            return self.log(f"ยกเลิกการปิดเครื่อง ({source})")
        self.log(f"⚡ {act} ({source})")
        self.eng.stop()
        self.eng.unhide_all()
        for pid in roblox_pids():
            kill_pid(pid)
        if act == "sleep":
            self.after(3000, lambda: os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0"))
        elif act == "shutdown":
            self.after(3000, lambda: os.system("shutdown /s /t 30 /c \"Roblox Toolkit: ปิดเครื่อง (ยกเลิก: shutdown /a)\""))

    # ---------- loop ----------
    def run_timer_action(self):
        act, self.timer_end = self.timer_action, None
        self.log(f"⏰ ถึงเวลา: {act}")
        notify.toast("Roblox Toolkit", f"ถึงเวลาตั้งไว้: {act}")
        if act == "หยุด Anti-AFK":
            self.eng.stop()
        else:
            self.power({"ปิด Roblox": "close_roblox", "ปิด Roblox + Sleep เครื่อง": "sleep", "ปิดเครื่อง": "shutdown"}[act])

    def tick(self):
        try:
            if self.timer_end and time.time() >= self.timer_end:
                self.run_timer_action()
            if self.current in ("home", "afk", "net", "click", "sys", "watch"):
                self.pages[self.current].tick()
            e = self.eng
            cur = e.watcher.current
            st = self.net.stats("อินเทอร์เน็ต", 60) or {}
            self.l_mini.configure(text=f"เน็ต {st.get('avg') and int(st['avg']) or '-'} ms · หาย {st.get('loss', 0):.0f}%")
            if st.get("avg") is not None:
                self.sess.sample_ping(st["avg"])
            if e.rejoining:
                self.dot.configure(text="  ◌  กำลังต่อกลับเกม", text_color=WARN)
            elif e.running:
                self.dot.configure(text="  ●  Anti-AFK ทำงาน", text_color=ACC)
            elif self.click.running:
                self.dot.configure(text="  ●  ออโต้คลิกทำงาน", text_color=ACC)
            else:
                self.dot.configure(text="  ○  พักอยู่", text_color=DIM)
            # priority ตกกลับเป็นปกติทุกครั้งที่เปิดเกมใหม่ — ตั้งให้ใหม่เรื่อยๆ
            if self.join_want and not e.rejoining and time.time() - self.join_want["at"] > 90:
                self.set_join_result(False, "ยังไม่เห็นเกมเข้าเซิร์ฟใน 90 วิ — ถ้า Chrome ถาม 'เปิด Roblox?' ให้กดตกลง หรือรีเฟรชหน้าเว็บแล้วกดเข้าใหม่")
            if self.cfg.get("ff_priority") and int(time.time()) % 15 == 0:
                threading.Thread(target=fpscap.set_roblox_priority, args=("high",), daemon=True).start()
            if self.cfg.get("multi_instance") and int(time.time()) % 5 == 0 and fpscap.multi_instance_tick():
                self.log("🪟 ยึดกุญแจเปิดหลายจอได้แล้ว — ตอนนี้เปิด Roblox ตัวที่สองได้โดยตัวแรกไม่ปิด")
                notify.toast("เปิดหลายจอพร้อมแล้ว", "เปิด Roblox ตัวที่สองได้เลย ตัวแรกจะไม่ถูกปิด")
            if self.overlay.visible:
                nxt = max(0, int(e.next_at - time.time())) if e.running else 0
                l1 = (f"● AFK ทำงาน · ถัดไป {nxt // 60:02d}:{nxt % 60:02d}", ACC) if e.running else ("○ AFK หยุด (F8)", DIM)
                sp = self.swatch.ping if self.swatch.ping is not None else ((self.net.dc_map.get(str(cur.get("dc"))) or {}).get("ping") if cur.get("dc") is not None else None)
                l2 = (f"📶 {int(st['avg'])} ms · หาย {st.get('loss', 0):.0f}%" + (f" · เซิร์ฟ ~{sp}" if sp is not None and cur.get("in_game") else ""),
                      ACC if st.get("loss", 0) < 5 else BAD) if st.get("avg") is not None else ("📶 กำลังวัด", DIM)
                l3 = (f"🎮 {self.place_name(cur.get('place'))[:28]} · {fmt_dur(time.time() - self.sess.start)}", TXT) if cur.get("in_game") and self.sess.start else ("🎮 ไม่ได้อยู่ในเกม", DIM)
                sw = self.swatch
                l4 = ((f"👥 {sw.players}/{sw.maxp} คน" + (f" · เงียบสุด {sw.quiet}" if sw.quiet is not None else "") + f"  ·  {time.strftime('%H:%M')}",
                       BAD if sw.players >= (sw.maxp or 32) * 0.8 else (WARN if sw.players > self.cfg["hop_over"] else ACC))
                      if sw.players is not None else (time.strftime("%H:%M"), DIM))
                self.overlay.update([l1, l2, l3, l4], ACC if e.running else DIM)
            if int(time.time()) % 15 == 0:
                self.last_ram_apps = ([{"name": n, "mb": round(mb), "procs": k} for n, mb, k in sysmon.top_apps(3)]
                                      if (self.sys.cur.get("ram") or 0) >= 80 else None)
            if int(time.time()) % 5 == 0:
                if self.swatch.ping is not None and cur.get("dc") is not None and cur.get("in_game"):
                    key = (cur.get("job"), self.swatch.ping)
                    if key != self.dc_learned:
                        self.dc_learned = key
                        self.net.learn_dc(cur["dc"], self.swatch.ping, ip=(cur.get("server") or [None])[0], geo=self.net.server_region)
                if self.net.dc_dirty:
                    self.net.dc_dirty = False
                    cache = config.load_cache() or {}
                    cache["dc_map"] = self.net.dc_map
                    config.save_cache(cache)
                v, lvl = self.net.verdict()
                config.write_status({
                    "running": e.running, "next_poke": e.next_at, "poke_count": e.poke_count, "rejoining": e.rejoining,
                    "in_game": cur.get("in_game"), "place": cur.get("place") or self.eng.last_place, "job": cur.get("job") or self.eng.last_job, "place_name": self.place_name(cur.get("place") or self.eng.last_place),
                    "server": cur.get("server"), "region": self.net.server_region, "hidden": len(e.hidden),
                    "server_players": self.swatch.players, "server_max": self.swatch.maxp, "server_quiet": self.swatch.quiet,
                    "server_seen": self.swatch.seen, "server_sample": self.swatch.sample,
                    "server_ping": self.swatch.ping, "join_result": self.join_result, "join_pending": bool(self.join_want),
                    "dc": cur.get("dc"), "dc_label": self.net.dc_label(cur.get("dc"), self.swatch.ping),
                    "wifi": self.sys.wifi, "multi": {"on": fpscap.multi_instance_on(), "owned": fpscap.multi_instance_owned()},
                    "watch": self.watch.status(),
                    "ram_apps": self.last_ram_apps,
                    "clicking": self.click.running, "clicks": self.click.clicks,
                    "fps_cap": self.cfg["fps_cap"] if self.cfg["fps_cap_on"] else 0, "fps_capping": self.fps.capping,
                    "sys": {k: self.sys.cur.get(k) for k in ("cpu", "ram", "ram_used", "gpu", "gpu_temp", "vram", "gpu_power", "battery", "plugged", "disk_free", "up_mbps", "down_mbps")},
                    "net": {"avg": st.get("avg"), "loss": st.get("loss"), "verdict": v, "level": lvl},
                    "playtime_today": self.hist.summary(1)["total"] if not self.hist.loading else None,
                    "last_events": [(t, s) for t, s in self.game_events[:5]], "updated": time.time()})
        except Exception as ex:
            import traceback
            config.dbg("tick error: " + traceback.format_exc())
        self.after(1000, self.tick)

    def on_close(self):
        try:
            self.sync_cfg()
        except Exception:
            pass
        if self.rec:
            self.rec.stop()
        if self.mplay:
            self.mplay.stop()
        self.click.stop_clicking("ปิดโปรแกรม")
        self.eng.stop()
        if self.eng.hidden:
            self.eng.unhide_all()
        if self.tray:
            self.tray.stop()
        self.destroy()


if __name__ == "__main__":
    App(sys.argv[1:]).mainloop()
