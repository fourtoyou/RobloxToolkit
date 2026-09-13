"""Overlay ลอยมุมจอ (คลิกทะลุได้, อยู่บนสุด, โปร่งใส) โชว์ ping / เวลาเล่น / สถานะ Anti-AFK — F9 เปิด/ปิด
ทำงานกับ Roblox โหมด borderless/windowed (โหมด exclusive fullscreen จะบังทุก overlay เป็นปกติ)"""
import ctypes
import tkinter as tk

u = ctypes.windll.user32
GWL_EXSTYLE = -20
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80000, 0x20, 0x80, 0x08000000
TRANS = "#010101"  # สีที่ทำให้โปร่งใส


class Overlay:
    def __init__(self, master, corner="top-right"):
        self.master = master
        self.corner = corner
        self.win = None
        self.visible = False
        self.labels = []

    def _build(self):
        w = tk.Toplevel(self.master)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.attributes("-transparentcolor", TRANS)
        w.configure(bg=TRANS)
        self.frame = tk.Frame(w, bg="#101018", padx=12, pady=8, highlightthickness=1, highlightbackground="#2ee6a8")
        self.frame.pack()
        self.labels = []
        for i in range(4):
            lb = tk.Label(self.frame, text="", bg="#101018", fg="#e8e8f0", font=("Segoe UI", 11, "bold" if i == 0 else "normal"), anchor="w", justify="left")
            lb.pack(anchor="w")
            self.labels.append(lb)
        w.update_idletasks()
        self.win = w
        self._click_through()
        self.place()

    def _click_through(self):
        hwnd = self.win.winfo_id()
        for h in (hwnd, u.GetParent(hwnd)):
            if not h:
                continue
            st = u.GetWindowLongW(h, GWL_EXSTYLE)
            u.SetWindowLongW(h, GWL_EXSTYLE, st | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)

    def place(self):
        if not self.win:
            return
        self.win.update_idletasks()
        w, h = self.win.winfo_width(), self.win.winfo_height()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        m = 16
        x = sw - w - m if "right" in self.corner else m
        y = sh - h - m - 40 if "bottom" in self.corner else m
        self.win.geometry(f"+{x}+{y}")

    def show(self):
        if not self.win:
            self._build()
        self.win.deiconify()
        self.visible = True

    def hide(self):
        if self.win:
            self.win.withdraw()
        self.visible = False

    def toggle(self):
        (self.hide if self.visible else self.show)()
        return self.visible

    def update(self, lines, accent="#2ee6a8"):
        """lines: list ของ (ข้อความ, สี) สูงสุด 4 บรรทัด"""
        if not self.win or not self.visible:
            return
        for lb, item in zip(self.labels, lines + [("", "#fff")] * 4):
            text, color = item
            lb.configure(text=text, fg=color)
            lb.pack_forget() if not text else lb.pack(anchor="w")
        self.frame.configure(highlightbackground=accent)
        self.win.attributes("-topmost", True)
        self.place()
