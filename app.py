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

from core import analytics, charts, clicker, config, filecheck, health, ipc, launcher, macro, notify, schedule, servers, session, sysmon
from core import fpscap
from core.antiafk import Engine, reason_text
from core.history import History, fmt_dur, fmt_reason
from core.netmon import TARGETS, NetMonitor
from core.overlay import Overlay
from core.watchdog import Watchdog
from core.win import VK_F4, VK_F5, VK_F6, VK_F7, VK_F8, VK_F9, dpi_aware, hotkey_loop, kill_pid, roblox_pids, roblox_windows, u
from core.ipc import grab_window

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None

dpi_aware()
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

ACC, WARN, BAD, DIM, CARD = "#2ee6a8", "#ffc857", "#ff5d7a", "#8a8aa0", "#1c1c28"
F = ("Segoe UI", 13)
FB = ("Segoe UI", 13, "bold")
FH = ("Segoe UI", 20, "bold")
FS = ("Segoe UI", 11)
LEVEL_COLOR = {"green": ACC, "yellow": "#d6d65a", "orange": WARN, "red": BAD, "gray": DIM, "ok": ACC, "warn": WARN, "bad": BAD}
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
class AfkPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)
        e, c = app.eng, app.cfg
        self.v_delay = ctk.IntVar(value=min(c["delay"], 900))
        self.v_action = ctk.StringVar(value=c["action"])
        self.vars = {k: ctk.BooleanVar(value=c[k]) for k in ("wait_idle", "auto_rejoin", "invisible", "immediate")}

        ctk.CTkLabel(self, text="ANTI-AFK", font=FH, text_color=ACC).pack(anchor="w", padx=20, pady=(16, 0))
        ctk.CTkLabel(self, text="F8 = เริ่ม/หยุด จากทุกที่", font=FS, text_color=DIM).pack(anchor="w", padx=20)

        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        card.pack(fill="x", padx=20, pady=12)
        self.l_found = ctk.CTkLabel(card, text="GAME: ...", font=FB)
        self.l_found.pack(pady=(14, 0))
        self.l_state = ctk.CTkLabel(card, text="SYSTEM: หยุด", font=FB, text_color=DIM)
        self.l_state.pack()
        self.btn = ctk.CTkButton(card, text="เริ่มทำงาน", font=("Segoe UI", 16, "bold"), height=52, width=260,
                                 fg_color="transparent", border_width=2, border_color=ACC, text_color=ACC,
                                 hover_color="#1a2a24", command=app.toggle_afk)
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

        hide = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        hide.pack(fill="x", padx=20)
        ctk.CTkLabel(hide, text="โหมดซ่อน — เร็วสุด ไม่กระพริบเลย: ย่อ Roblox ก่อน แล้วกดซ่อน", font=FS, text_color=DIM).pack(pady=(10, 2))
        hb = ctk.CTkFrame(hide, fg_color="transparent")
        hb.pack(pady=(0, 10))
        ctk.CTkButton(hb, text="ซ่อน Roblox ที่ย่ออยู่", width=170, command=self.hide, font=F).pack(side="left", padx=6)
        ctk.CTkButton(hb, text="เอา Roblox กลับมา", width=170, fg_color="#3a3a4e", hover_color="#4a4a60", command=self.unhide, font=F).pack(side="left", padx=6)
        ctk.CTkButton(hb, text="🔄 รีเซ็ตตัวละคร", width=140, font=F, fg_color="#3a3a4e", hover_color="#4a4a60",
                      command=lambda: threading.Thread(target=app.eng.reset_character, daemon=True).start()).pack(side="left", padx=6)
        self.l_hidden = ctk.CTkLabel(hb, text="ซ่อนอยู่: 0", font=FS, text_color=DIM)
        self.l_hidden.pack(side="left", padx=10)

        srv = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        srv.pack(fill="x", padx=20, pady=(8, 0))
        sr = ctk.CTkFrame(srv, fg_color="transparent")
        sr.pack(fill="x", padx=14, pady=8)
        self.l_srv = ctk.CTkLabel(sr, text="🌐 เซิร์ฟ: —", font=F, justify="left")
        self.l_srv.pack(side="left")
        ctk.CTkButton(sr, text="🔀 ย้ายไปเซิร์ฟเงียบสุด", width=190, font=F, command=self.go_quiet).pack(side="right")

        tm = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        tm.pack(fill="x", padx=20, pady=(8, 0))
        row = ctk.CTkFrame(tm, fg_color="transparent")
        row.pack(pady=8)
        ctk.CTkLabel(row, text="⏰ ตั้งเวลา: อีก", font=F).pack(side="left", padx=(6, 4))
        self.v_tmin = ctk.StringVar(value="60")
        ctk.CTkEntry(row, textvariable=self.v_tmin, width=60, font=F, justify="center").pack(side="left")
        ctk.CTkLabel(row, text="นาที →", font=F).pack(side="left", padx=4)
        self.v_taction = ctk.StringVar(value="หยุด Anti-AFK")
        ctk.CTkOptionMenu(row, values=list(App.TIMER_ACTIONS), variable=self.v_taction, font=F, width=210).pack(side="left", padx=4)
        self.bt_timer = ctk.CTkButton(row, text="เริ่มนับ", width=90, font=F, command=self.toggle_timer)
        self.bt_timer.pack(side="left", padx=6)
        self.l_timer = ctk.CTkLabel(row, text="", font=FS, text_color=DIM)
        self.l_timer.pack(side="left", padx=6)

        sc = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        sc.pack(fill="x", padx=20, pady=(8, 0))
        row = ctk.CTkFrame(sc, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(8, 2))
        ctk.CTkLabel(row, text="🔁 ตารางเวลา (ทำซ้ำทุกวัน)", font=FB).pack(side="left")
        self.l_next = ctk.CTkLabel(row, text="", font=FS, text_color=DIM)
        self.l_next.pack(side="left", padx=10)
        row = ctk.CTkFrame(sc, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkLabel(row, text="เวลา", font=F).pack(side="left")
        self.e_sctime = ctk.CTkEntry(row, width=64, font=F, justify="center", placeholder_text="23:00")
        self.e_sctime.pack(side="left", padx=6)
        self.v_scact = ctk.StringVar(value=schedule.ACTIONS[0])
        ctk.CTkOptionMenu(row, values=list(schedule.ACTIONS), variable=self.v_scact, font=F, width=210).pack(side="left", padx=4)
        ctk.CTkButton(row, text="+ เพิ่ม", width=74, font=F, command=self.add_job).pack(side="left", padx=6)
        self.sc_list = ctk.CTkFrame(sc, fg_color="transparent")
        self.sc_list.pack(fill="x", padx=14, pady=(0, 8))

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="both", expand=True, padx=20, pady=12)
        self.log = ctk.CTkTextbox(bottom, height=150, font=("Consolas", 11), fg_color="#0c0c12", text_color=DIM)
        self.log.pack(side="left", fill="both", expand=True)
        self.log.configure(state="disabled")
        pv = ctk.CTkFrame(bottom, fg_color=CARD, corner_radius=12, width=300)
        pv.pack(side="left", fill="y", padx=(10, 0))
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
            ctk.CTkLabel(r, text="→  " + job["action"], font=F, text_color="#d0d0e0" if job.get("on", True) else DIM).pack(side="left")
            ctk.CTkButton(r, text="ลบ", width=40, height=24, font=FS, fg_color="#5a2a34", hover_color="#7a3a46",
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
            self.l_srv.configure(text=f"🌐 เซิร์ฟนี้: {sw.players}/{sw.maxp} คน · ping {sw.ping} ms{q}",
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
            self.l_next.configure(text=f"ถัดไป: {t} → {act} (อีก {mins // 60} ชม. {mins % 60} นาที)" if mins >= 60 else f"ถัดไป: {t} → {act} (อีก {mins} นาที)")
        else:
            self.l_next.configure(text="")
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

        warn = ctk.CTkFrame(self, fg_color="#2a1f1f", corner_radius=10, border_width=1, border_color=BAD)
        warn.pack(fill="x", padx=20, pady=(8, 0))
        ctk.CTkLabel(warn, text="⚠  เกมแนวคลิกเกอร์/ซิมูเลเตอร์หลายเกมมีระบบจับการคลิกอัตโนมัติ ถ้าจับได้ = โดนแบนเกมนั้น · การสุ่มจังหวะไม่ได้การันตีอะไร",
                     font=FS, text_color="#ffb3c0", justify="left").pack(anchor="w", padx=12, pady=6)

        top = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        top.pack(fill="x", padx=20, pady=8)
        self.btn = ctk.CTkButton(top, text="เริ่มคลิก (F6)", font=("Segoe UI", 15, "bold"), height=46, width=210,
                                 fg_color="transparent", border_width=2, border_color=ACC, text_color=ACC,
                                 hover_color="#1a2a24", command=lambda: app.click.toggle())
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
        ctk.CTkButton(r, text="ล้างจุดทั้งหมด", width=120, font=F, fg_color="#3a3a4e", hover_color="#4a4a60", command=self.clear_points).pack(side="left", padx=8)
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
        self.bt_rec = ctk.CTkButton(r, text="● เริ่มอัด (F4)", width=140, font=F, fg_color="#5a2a34", hover_color="#7a3a46",
                                    command=lambda: app.toggle_record())
        self.bt_rec.pack(side="left")
        self.bt_play = ctk.CTkButton(r, text="▶ เล่น (F5)", width=110, font=F, command=lambda: app.play_macro())
        self.bt_play.pack(side="left", padx=6)
        self.v_macro = ctk.StringVar(value="")
        self.opt_macro = ctk.CTkOptionMenu(r, values=["—"], variable=self.v_macro, font=F, width=170, command=lambda _: self.show_macro())
        self.opt_macro.pack(side="left", padx=6)
        ctk.CTkButton(r, text="ลบ", width=46, font=F, fg_color="#5a2a34", hover_color="#7a3a46",
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
        ctk.CTkButton(r, text="ลบ", width=50, font=F, fg_color="#5a2a34", hover_color="#7a3a46", command=self.del_profile).pack(side="left", padx=5)
        self.upd_cps()
        self.refresh_points()
        self.refresh_profiles()
        self.refresh_macros()

    # ---------- helper ----------
    def card(self, parent, title):
        ctk.CTkLabel(parent, text=title, font=FB, text_color="#c8c8dc").pack(anchor="w", padx=8, pady=(8, 2))
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
        self.l_cps.configure(text=f"ความเร็ว: {n} ครั้ง/วินาที{hint}", text_color=WARN if n > 14 else "#d0d0e0")

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
                               fg_color=BAD if app.mplay else ["#2FA572", "#2FA572"])
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
            v = ctk.CTkLabel(f, text="—", font=("Segoe UI", 26, "bold"))
            v.pack()
            sub = ctk.CTkLabel(f, text="", font=FS, text_color=DIM)
            sub.pack(pady=(0, 10))
            self.big[key] = (v, sub, unit)

        gf = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        gf.pack(fill="x", padx=20)
        ctk.CTkLabel(gf, text="20 นาทีล่าสุด   —   เขียว CPU · ฟ้า RAM · ส้ม GPU · แดง อุณหภูมิ GPU", font=FS, text_color=DIM).pack(anchor="w", padx=14, pady=(8, 0))
        self.canvas = ctk.CTkCanvas(gf, height=150, bg="#12121a", highlightthickness=0)
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
        self.l_top = ctk.CTkLabel(left, text="", font=("Consolas", 11), text_color="#d0d0e0", justify="left")
        self.l_top.pack(anchor="w", padx=14, pady=(0, 10))
        right = ctk.CTkFrame(bot, fg_color=CARD, corner_radius=12, width=330)
        right.pack(side="left", fill="y", padx=(10, 0))
        right.pack_propagate(False)
        ctk.CTkLabel(right, text="อื่นๆ", font=FB).pack(anchor="w", padx=14, pady=(10, 2))
        self.l_misc = ctk.CTkLabel(right, text="", font=F, text_color="#d0d0e0", justify="left")
        self.l_misc.pack(anchor="w", padx=14)
        self.v_game = ctk.BooleanVar(value=app.cfg["game_mode"])
        ctk.CTkSwitch(right, text="โหมดเล่นเกม: เปิด Roblox แล้วคายโมเดล AI คืน VRAM", variable=self.v_game,
                      font=FS, command=app.sync_cfg).pack(anchor="w", padx=14, pady=(8, 0))
        ctk.CTkButton(right, text="คายโมเดล AI ตอนนี้", width=170, font=FS, fg_color="#3a3a4e", hover_color="#4a4a60",
                      command=self.free_now).pack(anchor="w", padx=14, pady=(4, 2))
        self.v_alerts = ctk.BooleanVar(value=app.cfg["sys_alerts"])
        ctk.CTkSwitch(right, text="เตือนเมื่อร้อน/แรมตึง", variable=self.v_alerts, font=FS, command=app.sync_cfg).pack(anchor="w", padx=14, pady=(10, 4))
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
            cv.create_line(0, h * frac, w, h * frac, fill="#22222e")
        for key, col, mx in (("cpu", ACC, 100), ("ram", "#5aa9e6", 100), ("gpu", WARN, 100), ("gpu_temp", BAD, 100)):
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
        ctk.CTkButton(head, text="📤 แชร์การ์ด", width=110, font=F, fg_color="#3a3a4e", hover_color="#4a4a60",
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
                tips = analytics.insights(sess, app.hist.name, d)
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
            ctk.CTkLabel(r, text=txt, font=F, text_color="#d8d8e8", justify="left", anchor="w").pack(side="left", fill="x", expand=True)
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
        ctk.CTkButton(head, text="📤 แชร์การ์ดสัปดาห์", width=150, font=F, fg_color="#3a3a4e", hover_color="#4a4a60", command=self.share).pack(side="right", padx=6)
        self.seg = ctk.CTkSegmentedButton(head, values=["วันนี้", "7 วัน", "30 วัน", "ทั้งหมด"], command=lambda _: self.render(), font=F)
        self.seg.set("7 วัน")
        self.seg.pack(side="right", padx=10)
        self.l_sum = ctk.CTkLabel(self, text="กำลังอ่าน log ของ Roblox...", font=F, text_color=DIM)
        self.l_sum.pack(anchor="w", padx=20)
        self.canvas = ctk.CTkCanvas(self, height=120, bg="#12121a", highlightthickness=0)
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
                                  + ("  ·  " + time.strftime("%d/%m/%Y") if days == 1 else ""), text_color="#e8e8f0")
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
            c.create_rectangle(x0, h - 20 - bh, x0 + bw - 8, h - 20, fill=ACC if i == len(data) - 1 else "#2a7a5e", outline="")
            c.create_text(x0 + (bw - 8) / 2, h - 10, text=d.strftime("%d/%m"), fill=DIM, font=("Segoe UI", 8))
            if sec > 0:
                c.create_text(x0 + (bw - 8) / 2, h - 26 - bh, text=f"{sec / 3600:.1f}", fill="#e8e8f0", font=("Segoe UI", 8))
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
        ctk.CTkLabel(self, text="เหตุการณ์ล่าสุด (เน็ตหลุด / หลุดจากเกม)", font=FB).pack(anchor="w", padx=20, pady=(8, 2))
        self.events = ctk.CTkTextbox(self, font=("Consolas", 11), fg_color="#0c0c12", text_color=DIM)
        self.events.pack(fill="both", expand=True, padx=20, pady=(0, 12))

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
        if nm.server:
            reg = f"  ·  {nm.server_region}" if nm.server_region else ""
            self.l_server.configure(text=f"เซิร์ฟที่เล่นอยู่: {nm.server[0]}:{nm.server[1]}{reg}")
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
        ctk.CTkButton(row, text="สแกน Downloads", width=130, font=F, fg_color="#3a3a4e", hover_color="#4a4a60", command=self.scan_downloads).pack(side="left", padx=6)
        self.banner = ctk.CTkLabel(self, text="", font=FB, fg_color=CARD, corner_radius=10, height=44)
        self.banner.pack(fill="x", padx=20)
        self.out = ctk.CTkTextbox(self, font=("Consolas", 11), fg_color="#0c0c12", text_color="#d0d0e0")
        self.out.pack(fill="both", expand=True, padx=20, pady=10)
        b = ctk.CTkFrame(self, fg_color="transparent")
        b.pack(fill="x", padx=20, pady=(0, 12))
        self.bt_vt = ctk.CTkButton(b, text="เปิดใน VirusTotal", font=F, state="disabled", command=self.open_vt)
        self.bt_vt.pack(side="left")
        self.bt_copy = ctk.CTkButton(b, text="คัดลอก SHA-256", font=F, fg_color="#3a3a4e", hover_color="#4a4a60", state="disabled", command=self.copy_sha)
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
        img = ctk.CTkLabel(f, text="🎮", font=("Segoe UI", 28), width=72, height=72)
        img.grid(row=0, column=0, rowspan=2, padx=12, pady=10)
        name = ctk.CTkLabel(f, text=fav["name"], font=FB, anchor="w")
        name.grid(row=0, column=1, sticky="w", pady=(12, 0))
        meta = ctk.CTkLabel(f, text="กำลังโหลด...", font=FS, text_color=DIM, anchor="w")
        meta.grid(row=1, column=1, sticky="w", pady=(0, 12))
        btns = ctk.CTkFrame(f, fg_color="transparent")
        btns.grid(row=0, column=2, rowspan=2, padx=12)
        place = fav["place"]
        ctk.CTkButton(btns, text="▶ เข้าเกม", width=96, font=F, command=lambda: (launcher.launch(place), self.app.log(f"เปิดเกม {fav['name']}"))).pack(side="left", padx=3)
        ctk.CTkButton(btns, text="📶 ping ต่ำสุด", width=110, font=F, fg_color="#3a3a4e", hover_color="#4a4a60",
                      command=lambda: launcher.launch_best(place, self.app.log)).pack(side="left", padx=3)
        eng = self.app.eng
        if eng.last_place == place and eng.last_job:
            ctk.CTkButton(btns, text="↩ เซิร์ฟล่าสุด", width=110, font=F, fg_color="#3a3a4e", hover_color="#4a4a60",
                          command=lambda: (launcher.launch(place, eng.last_job), self.app.log("กลับเซิร์ฟล่าสุด"))).pack(side="left", padx=3)
        ctk.CTkButton(btns, text="✕", width=32, font=F, fg_color="transparent", hover_color="#4a2a34", text_color=DIM,
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
            ctk.CTkLabel(f, text=fmt_dur(sess["end"] - sess["start"]), font=FS, text_color="#e8e8f0", width=100, anchor="w").pack(side="left")
            r = sess["reason"]
            ctk.CTkLabel(f, text=fmt_reason(r), font=FS, text_color=BAD if r not in (None, 0, -1, 285) else DIM, anchor="w", width=160).pack(side="left")
            ctk.CTkButton(f, text="🖼", width=36, height=26, font=FS, fg_color="#2a2a3a", hover_color="#3a3a4e", command=lambda s_=sess: self.card(s_)).pack(side="right")

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
        ctk.CTkButton(b, text="ซ่อม Bloxstrap (handler + shortcut)", font=F, command=self.fix).pack(side="left")
        ctk.CTkButton(b, text="ล้าง log เก่ากว่า 7 วัน", font=F, fg_color="#3a3a4e", hover_color="#4a4a60", command=self.clean).pack(side="left", padx=6)
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
        ctk.CTkLabel(self, text="ตั้งค่า", font=FH, text_color=ACC).pack(anchor="w", padx=20, pady=(16, 8))
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        card.pack(fill="x", padx=20)
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
        info = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        info.pack(fill="x", padx=20, pady=12)
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
        ctk.CTkButton(io, text="⬆ ส่งออกค่าตั้งทั้งหมด", width=170, font=F, fg_color="#3a3a4e", hover_color="#4a4a60", command=self.export_cfg).pack(side="left")
        ctk.CTkButton(io, text="⬇ นำเข้าค่าตั้ง", width=140, font=F, fg_color="#3a3a4e", hover_color="#4a4a60", command=self.import_cfg).pack(side="left", padx=8)
        self.l_io = ctk.CTkLabel(io, text="", font=FS, text_color=DIM)
        self.l_io.pack(side="left", padx=6)

        rr = ctk.CTkFrame(info, fg_color="transparent")
        rr.pack(anchor="w", padx=14, pady=(0, 12))
        ctk.CTkButton(rr, text="เปิดโฟลเดอร์ข้อมูล", font=F, fg_color="#3a3a4e", hover_color="#4a4a60", command=lambda: os.startfile(config.DATA_DIR) if os.path.isdir(config.DATA_DIR) else None).pack(side="left")
        self.e_repo = ctk.CTkEntry(rr, font=F, width=220, placeholder_text="GitHub repo เช่น user/RobloxToolkit")
        self.e_repo.insert(0, c["update_repo"])
        self.e_repo.pack(side="left", padx=(12, 6))
        ctk.CTkButton(rr, text="เช็คอัปเดต", width=100, font=F, command=self.check_update).pack(side="left")
        self.l_upd = ctk.CTkLabel(self, text="", font=F, text_color=DIM)
        self.l_upd.pack(anchor="w", padx=20)

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

    def check_update(self):
        self.app.sync_cfg()
        repo = self.app.cfg["update_repo"].strip()
        if not repo:
            self.l_upd.configure(text="ยังไม่ได้ตั้ง repo — ถ้าปล่อยโปรแกรมบน GitHub แล้วค่อยใส่")
            return

        def work():
            try:
                import requests
                r = requests.get(f"https://api.github.com/repos/{repo}/releases/latest", timeout=8).json()
                tag = r.get("tag_name", "").lstrip("v")
                url = r.get("html_url", "")
                if tag and tag != config.VERSION:
                    self.app.ui(lambda: (self.l_upd.configure(text=f"มีเวอร์ชันใหม่ {tag} (ตอนนี้ {config.VERSION})", text_color=ACC), webbrowser.open(url)))
                else:
                    self.app.ui(lambda: self.l_upd.configure(text=f"เป็นเวอร์ชันล่าสุดแล้ว ({config.VERSION})"))
            except Exception as e:
                self.app.ui(lambda: self.l_upd.configure(text=f"เช็คไม่ได้: {e}"))

        threading.Thread(target=work, daemon=True).start()


# =====================================================================
class App(ctk.CTk):
    TIMER_ACTIONS = ("หยุด Anti-AFK", "ปิด Roblox", "ปิด Roblox + Sleep เครื่อง", "ปิดเครื่อง")
    NAV = [("afk", "🎮  Anti-AFK"), ("games", "🚀  เกมโปรด"), ("click", "🖱  ออโต้คลิก"), ("stats", "📊  สถิติ"), ("analytics", "📈  วิเคราะห์"), ("sys", "🖥  เครื่อง"), ("history", "🕘  ประวัติ"), ("net", "📶  เน็ต"),
           ("file", "🛡  ตรวจไฟล์"), ("health", "🩺  สุขภาพระบบ"), ("settings", "⚙  ตั้งค่า")]

    def __init__(self, args):
        super().__init__()
        self.title("Roblox Toolkit")
        self.geometry("940x640")
        self.minsize(900, 600)
        self.cfg = config.load()
        self.q = queue.Queue()
        self.log_lines = deque(maxlen=300)   # ให้ Discord bot ดึงไปดูได้ (/afk log)
        self.game_events = []
        self.hist = History()
        self.net = NetMonitor()
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
        self.ipc = ipc.CommandServer(self)
        self.ipc.start()
        config.dbg(f"app init ok v{config.VERSION}")

        self.side = ctk.CTkFrame(self, width=190, corner_radius=0, fg_color="#0e0e16")
        self.side.pack(side="left", fill="y")
        ctk.CTkLabel(self.side, text="ROBLOX\nTOOLKIT", font=("Segoe UI", 18, "bold"), text_color=ACC, justify="left").pack(anchor="w", padx=18, pady=(20, 14))
        self.navbtn = {}
        for key, text in self.NAV:
            b = ctk.CTkButton(self.side, text=text, anchor="w", font=F, height=40, fg_color="transparent",
                              hover_color="#1c1c28", text_color="#d0d0e0", command=lambda k=key: self.show(k))
            b.pack(fill="x", padx=10, pady=2)
            self.navbtn[key] = b
        self.l_mini = ctk.CTkLabel(self.side, text="", font=FS, text_color=DIM, justify="left")
        self.l_mini.pack(side="bottom", anchor="w", padx=18, pady=14)
        ctk.CTkButton(self.side, text="ซ่อนลง tray", font=FS, height=28, fg_color="#1c1c28", hover_color="#2a2a3a", command=self.to_tray).pack(side="bottom", fill="x", padx=10, pady=(0, 6))

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(side="left", fill="both", expand=True)
        self.pages = {"afk": AfkPage(self.container, self), "games": GamesPage(self.container, self), "stats": StatsPage(self.container, self),
                      "analytics": AnalyticsPage(self.container, self), "click": ClickPage(self.container, self),
                      "sys": SysPage(self.container, self),
                      "history": HistoryPage(self.container, self), "net": NetPage(self.container, self), "file": FilePage(self.container, self),
                      "health": HealthPage(self.container, self), "settings": SettingsPage(self.container, self)}
        self.current = None
        self.show("afk")

        if self.cfg.get("multi_instance"):
            fpscap.multi_instance(True)
        self.sched.start()
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
            self.navbtn[self.current].configure(fg_color="transparent", text_color="#d0d0e0")
        self.current = key
        self.pages[key].pack(fill="both", expand=True)
        self.navbtn[key].configure(fg_color="#1c1c28", text_color=ACC)
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
        c["game_mode"] = y.v_game.get()
        c["fps_cap_on"], c["fps_unlock_focus"], c["automute"] = y.v_fps.get(), y.v_unlock.get(), y.v_mute.get()
        try:
            c["fps_cap"] = int(y.v_fpsn.get())
        except ValueError:
            pass
        want_multi = s.v_multi.get()
        if want_multi != fpscap.multi_instance_on():
            ok = fpscap.multi_instance(want_multi)
            self.log("เปิดหลายหน้าต่างได้แล้ว — เปิดเกมตัวที่สองได้เลย" if ok and want_multi else
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
        elif kind == "server":
            self.net.set_server(d["ip"], d["port"], c["show_server_region"])
        elif kind == "disconnect":
            if d["reason"] != 285:
                self.sess.disconnects += 1
                self.game_events.insert(0, (time.time(), f"หลุดจากเกม: {d['text']} ({self.place_name(d['place'])})"))
            self.finish_session(d["text"])
            if d["reason"] != 285 and c["notify_disconnect"]:
                notify.toast("หลุดจากเกม", d["text"] + (" — กำลังต่อใหม่" if c["auto_rejoin"] else ""))
                notify.discord(c["webhook_url"], "⚠ หลุดจากเกม", f"{d['text']} (code {d['reason']})\nเกม: {self.place_name(d['place'])}\n{'กำลังต่อใหม่อัตโนมัติ...' if c['auto_rejoin'] else ''}", 0xFF5D7A)
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
            if self.current in ("afk", "net", "click", "sys"):
                self.pages[self.current].tick()
            e = self.eng
            cur = e.watcher.current
            st = self.net.stats("อินเทอร์เน็ต", 60) or {}
            self.l_mini.configure(text=("● Anti-AFK ทำงาน" if e.running else "○ Anti-AFK หยุด") + f"\nเน็ต {st.get('avg') and int(st['avg']) or '-'} ms · หาย {st.get('loss', 0):.0f}%")
            if st.get("avg") is not None:
                self.sess.sample_ping(st["avg"])
            if self.overlay.visible:
                nxt = max(0, int(e.next_at - time.time())) if e.running else 0
                l1 = (f"● AFK ทำงาน · ถัดไป {nxt // 60:02d}:{nxt % 60:02d}", ACC) if e.running else ("○ AFK หยุด (F8)", DIM)
                l2 = (f"📶 {int(st['avg'])} ms · หาย {st.get('loss', 0):.0f}%", ACC if st.get("loss", 0) < 5 else BAD) if st.get("avg") is not None else ("📶 กำลังวัด", DIM)
                l3 = (f"🎮 {self.place_name(cur.get('place'))[:28]} · {fmt_dur(time.time() - self.sess.start)}", "#e8e8f0") if cur.get("in_game") and self.sess.start else ("🎮 ไม่ได้อยู่ในเกม", DIM)
                sw = self.swatch
                l4 = ((f"👥 {sw.players}/{sw.maxp} คน" + (f" · เงียบสุด {sw.quiet}" if sw.quiet is not None else "") + f"  ·  {time.strftime('%H:%M')}",
                       BAD if sw.players >= (sw.maxp or 32) * 0.8 else (WARN if sw.players > self.cfg["hop_over"] else ACC))
                      if sw.players is not None else (time.strftime("%H:%M"), DIM))
                self.overlay.update([l1, l2, l3, l4], ACC if e.running else DIM)
            if int(time.time()) % 5 == 0:
                v, lvl = self.net.verdict()
                config.write_status({
                    "running": e.running, "next_poke": e.next_at, "poke_count": e.poke_count, "rejoining": e.rejoining,
                    "in_game": cur.get("in_game"), "place": cur.get("place") or self.eng.last_place, "job": cur.get("job") or self.eng.last_job, "place_name": self.place_name(cur.get("place") or self.eng.last_place),
                    "server": cur.get("server"), "region": self.net.server_region, "hidden": len(e.hidden),
                    "server_players": self.swatch.players, "server_max": self.swatch.maxp, "server_quiet": self.swatch.quiet,
                    "server_seen": self.swatch.seen, "server_sample": self.swatch.sample,
                    "clicking": self.click.running, "clicks": self.click.clicks,
                    "fps_cap": self.cfg["fps_cap"] if self.cfg["fps_cap_on"] else 0, "fps_capping": self.fps.capping,
                    "sys": {k: self.sys.cur.get(k) for k in ("cpu", "ram", "ram_used", "gpu", "gpu_temp", "vram", "gpu_power", "battery", "plugged", "disk_free")},
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
