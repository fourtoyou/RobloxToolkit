"""ธีม + ชิ้นส่วน UI ที่ใช้ซ้ำทั้งโปรแกรม

แก้สี/ฟอนต์ที่ไฟล์นี้ที่เดียว เปลี่ยนทั้ง 13 หน้าเลย
install() ต้องเรียกก่อนสร้างหน้าต่าง — มันเซ็ตค่าเริ่มต้นของ customtkinter
ให้ปุ่ม/การ์ด/สวิตช์ทุกตัวหน้าตาตรงกันโดยไม่ต้องไปแก้ทีละจุด
"""
import tkinter as tk

import customtkinter as ctk

# ---------- สี ----------
INK = "#07080e"        # ลึกสุด — ช่อง log
BG = "#0d0f17"         # พื้นหลังหน้า
SIDE = "#090b12"       # เมนูซ้าย
CARD = "#161a26"       # การ์ด
CARD2 = "#1e2331"      # การ์ดซ้อน / ช่องกรอก
BTN = "#252b3b"        # ปุ่มรอง
BTNH = "#323a52"       # ปุ่มรองตอนชี้
LINE = "#252b3c"       # เส้นขอบ
ACC = "#2ee6a8"        # สีหลัก (มิ้นต์)
ACC2 = "#1aa87b"       # ปุ่มหลัก
ACC3 = "#23c993"       # ปุ่มหลักตอนชี้
OKBG = "#13291f"       # พื้นเขียวจาง
WARN = "#ffc857"
YEL = "#d6d65a"
BAD = "#ff5d7a"
BADT = "#ffb3c0"
BADBG = "#2a1620"
DANGER = "#4b2130"     # ปุ่มลบ/อันตราย
DANGERH = "#6a2f42"
INFO = "#5aa9e6"
TXT = "#e9ebf5"
TXT2 = "#c2c6d8"
DIM = "#7e849c"

# ---------- ฟอนต์ ----------
FAM = "Segoe UI"
FTINY = (FAM, 9)
FS = (FAM, 11)
FSB = (FAM, 11, "bold")
F = (FAM, 13)
FB = (FAM, 13, "bold")
FMB = (FAM, 15, "bold")
FH3 = (FAM, 16, "bold")
FH2 = (FAM, 18, "bold")
FH = (FAM, 20, "bold")
FTITLE = (FAM, 24, "bold")
FBIG = (FAM, 26, "bold")
FHUGE = (FAM, 28)
MONO = ("Consolas", 11)


def _d(c):
    """ctk ต้องการ [สีโหมดสว่าง, สีโหมดมืด]"""
    return [c, c]


def install():
    """เซ็ตค่าเริ่มต้นของ customtkinter ให้เป็นธีมของเรา"""
    ctk.set_appearance_mode("dark")
    t = ctk.ThemeManager.theme
    d = _d
    t["CTk"]["fg_color"] = d(BG)
    t["CTkToplevel"]["fg_color"] = d(BG)
    t["CTkFrame"].update({"corner_radius": 14, "border_width": 0, "fg_color": d(CARD),
                          "top_fg_color": d(CARD2), "border_color": d(LINE)})
    t["CTkButton"].update({"corner_radius": 10, "border_width": 0, "fg_color": d(ACC2), "hover_color": d(ACC3),
                           "text_color": d("#f2fffa"), "border_color": d(LINE), "text_color_disabled": d(DIM)})
    t["CTkLabel"].update({"corner_radius": 0, "fg_color": "transparent", "text_color": d(TXT)})
    t["CTkEntry"].update({"corner_radius": 9, "border_width": 1, "fg_color": d(CARD2), "border_color": d(LINE),
                          "text_color": d(TXT), "placeholder_text_color": d(DIM)})
    t["CTkSwitch"].update({"fg_color": d(BTN), "progress_color": d(ACC), "button_color": d("#e2e5f0"),
                           "button_hover_color": d("#ffffff"), "text_color": d(TXT2), "text_color_disabled": d(DIM)})
    t["CTkCheckBox"].update({"corner_radius": 5, "fg_color": d(ACC2), "border_color": d(BTN), "hover_color": d(ACC3),
                             "checkmark_color": d("#f2fffa"), "text_color": d(TXT2)})
    t["CTkRadioButton"].update({"fg_color": d(ACC), "border_color": d(BTN), "hover_color": d(ACC3), "text_color": d(TXT2)})
    t["CTkOptionMenu"].update({"corner_radius": 9, "fg_color": d(CARD2), "button_color": d(BTN),
                               "button_hover_color": d(BTNH), "text_color": d(TXT)})
    t["CTkComboBox"].update({"corner_radius": 9, "border_width": 1, "fg_color": d(CARD2), "border_color": d(LINE),
                             "button_color": d(BTN), "button_hover_color": d(BTNH), "text_color": d(TXT)})
    t["CTkSlider"].update({"fg_color": d(BTN), "progress_color": d(ACC), "button_color": d(ACC),
                           "button_hover_color": d("#8bf5d2")})
    t["CTkProgressBar"].update({"corner_radius": 1000, "fg_color": d(BTN), "progress_color": d(ACC)})
    t["CTkSegmentedButton"].update({"corner_radius": 10, "border_width": 3, "fg_color": d(CARD2),
                                    "selected_color": d(ACC2), "selected_hover_color": d(ACC3),
                                    "unselected_color": d(CARD2), "unselected_hover_color": d(BTN),
                                    "text_color": d(TXT), "text_color_disabled": d(DIM)})
    t["CTkTextbox"].update({"corner_radius": 10, "border_width": 0, "fg_color": d(INK), "text_color": d(TXT2),
                            "scrollbar_button_color": d(BTN), "scrollbar_button_hover_color": d(BTNH)})
    t["CTkScrollbar"].update({"corner_radius": 1000, "fg_color": "transparent", "button_color": d(BTN),
                              "button_hover_color": d(BTNH)})
    t["CTkScrollableFrame"]["label_fg_color"] = d(CARD)
    t["DropdownMenu"].update({"fg_color": d(CARD2), "hover_color": d(BTN), "text_color": d(TXT)})


# ---------- ชิ้นส่วน ----------
def card(parent, **kw):
    kw.setdefault("fg_color", CARD)
    kw.setdefault("corner_radius", 14)
    return ctk.CTkFrame(parent, **kw)


def row(parent, **kw):
    kw.setdefault("fg_color", "transparent")
    return ctk.CTkFrame(parent, **kw)


def head(parent, title_text, sub="", icon=""):
    """หัวหน้าเพจแบบเดียวกันทุกหน้า — คืน frame ฝั่งขวาไว้ใส่ปุ่ม"""
    wrap = ctk.CTkFrame(parent, fg_color="transparent")
    wrap.pack(fill="x", padx=22, pady=(18, 6))
    left = ctk.CTkFrame(wrap, fg_color="transparent")
    left.pack(side="left", anchor="w")
    ctk.CTkLabel(left, text=(icon + "  " + title_text) if icon else title_text, font=FH, text_color=TXT).pack(anchor="w")
    if sub:
        ctk.CTkLabel(left, text=sub, font=FS, text_color=DIM, justify="left").pack(anchor="w", pady=(1, 0))
    right = ctk.CTkFrame(wrap, fg_color="transparent")
    right.pack(side="right", anchor="e")
    return right


def title(parent, text, padx=14):
    """หัวข้อในการ์ด"""
    lb = ctk.CTkLabel(parent, text=text, font=FB, text_color=TXT)
    lb.pack(anchor="w", padx=padx, pady=(12, 2))
    return lb


def note(parent, text, **kw):
    kw.setdefault("wraplength", 720)
    return ctk.CTkLabel(parent, text=text, font=FS, text_color=DIM, justify="left", **kw)


def ghost(parent, text, cmd=None, **kw):
    """ปุ่มรอง — สีเทา ไม่แย่งสายตาปุ่มหลัก"""
    kw.setdefault("height", 34)
    kw.setdefault("font", F)
    return ctk.CTkButton(parent, text=text, command=cmd, fg_color=BTN, hover_color=BTNH, **kw)


def danger_btn(parent, text, cmd=None, **kw):
    kw.setdefault("height", 34)
    kw.setdefault("font", F)
    return ctk.CTkButton(parent, text=text, command=cmd, fg_color=DANGER, hover_color=DANGERH, **kw)


def big(parent, text, cmd=None, **kw):
    """ปุ่มหลักของหน้า"""
    kw.setdefault("height", 42)
    kw.setdefault("font", FB)
    return ctk.CTkButton(parent, text=text, command=cmd, **kw)


def chip(parent, text, color=DIM, **kw):
    """ป้ายสถานะกลมๆ"""
    return ctk.CTkLabel(parent, text="  " + text + "  ", font=FSB, text_color=color,
                        fg_color=CARD2, corner_radius=999, height=24, **kw)


def hr(parent, pad=10):
    f = ctk.CTkFrame(parent, height=1, fg_color=LINE)
    f.pack(fill="x", padx=14, pady=pad)
    return f


def switch_row(parent, text, var, hint="", cmd=None, padx=16, pady=4):
    """สวิตช์ + คำอธิบายเล็กใต้ชื่อ — อ่านง่ายกว่าสวิตช์เปล่าๆ"""
    w = ctk.CTkFrame(parent, fg_color="transparent")
    w.pack(fill="x", padx=padx, pady=pady)
    sw = ctk.CTkSwitch(w, text=text, variable=var, command=cmd, font=F)
    sw.pack(anchor="w")
    if hint:
        ctk.CTkLabel(w, text=hint, font=FS, text_color=DIM, justify="left", wraplength=640).pack(anchor="w", padx=(52, 0))
    return sw


def tip(widget, text, delay=420):
    """ชี้แล้วมีคำอธิบายเด้ง — ใช้กับปุ่ม/สวิตช์ที่ชื่อสั้นจนไม่เข้าใจ"""
    st = {"id": None, "win": None}

    def hide(_=None):
        if st["id"]:
            try:
                widget.after_cancel(st["id"])
            except Exception:
                pass
            st["id"] = None
        if st["win"] is not None:
            try:
                st["win"].destroy()
            except Exception:
                pass
            st["win"] = None

    def show():
        st["id"] = None
        if st["win"] is not None or not widget.winfo_exists():
            return
        try:
            t = tk.Toplevel(widget)
            t.wm_overrideredirect(True)
            t.configure(bg=LINE)
            tk.Label(t, text=text, font=FS, fg=TXT2, bg=CARD2, justify="left",
                     wraplength=340, padx=10, pady=7, bd=0).pack(padx=1, pady=1)
            t.wm_geometry("+%d+%d" % (widget.winfo_rootx() + 14, widget.winfo_rooty() + widget.winfo_height() + 6))
            t.attributes("-topmost", True)
            st["win"] = t
        except Exception:
            st["win"] = None

    def enter(_=None):
        st["id"] = widget.after(delay, show)

    widget.bind("<Enter>", enter, add="+")
    widget.bind("<Leave>", hide, add="+")
    widget.bind("<Button-1>", hide, add="+")
    widget.bind("<Destroy>", hide, add="+")
    return widget
