"""วาดข้อความด้วย Windows GDI (จัดสระ/วรรณยุกต์ไทยถูกต้อง ต่างจาก Pillow ที่ไม่มี raqm)
ใช้: mask = text_mask("ยิ่งห้ามยิ่งยุ", 40, bold=True, max_w=500)  → PIL 'L' image (ขาว = ตัวอักษร)"""
import ctypes
from ctypes import wintypes

from PIL import Image

gdi32, user32 = ctypes.windll.gdi32, ctypes.windll.user32
DT_SINGLELINE, DT_NOPREFIX, DT_CALCRECT, DT_END_ELLIPSIS, DT_NOCLIP = 0x20, 0x800, 0x400, 0x8000, 0x100
ANTIALIASED_QUALITY, TRANSPARENT = 4, 1
FONT_NAME = "Leelawadee UI"


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


gdi32.CreateFontW.restype = ctypes.c_void_p
gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
gdi32.SelectObject.restype = ctypes.c_void_p
gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
gdi32.SetBkMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdi32.SetTextColor.argtypes = [ctypes.c_void_p, wintypes.DWORD]
gdi32.CreateDIBSection.restype = ctypes.c_void_p
gdi32.CreateDIBSection.argtypes = [ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, wintypes.DWORD]
user32.DrawTextW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.RECT), wintypes.UINT]


def _font(size, bold, name):
    return gdi32.CreateFontW(-int(size), 0, 0, 0, 700 if bold else 400, 0, 0, 0, 0, 0, 0, ANTIALIASED_QUALITY, 0, name)


def text_mask(text, size, bold=False, max_w=None, name=FONT_NAME):
    """คืน PIL 'L' mask ของข้อความ (ตัดด้วย … อัตโนมัติถ้าเกิน max_w)"""
    text = text or " "
    hdc = gdi32.CreateCompatibleDC(None)
    hfont = _font(size, bold, name)
    old_font = gdi32.SelectObject(hdc, hfont)
    flags = DT_SINGLELINE | DT_NOPREFIX | (DT_END_ELLIPSIS if max_w else 0)
    rect = wintypes.RECT(0, 0, int(max_w) if max_w else 6000, 0)
    user32.DrawTextW(hdc, text, -1, ctypes.byref(rect), flags | DT_CALCRECT)
    w = max(1, min(rect.right, int(max_w) if max_w else rect.right) + 4)
    h = max(1, rect.bottom + 2)
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth, bmi.bmiHeader.biHeight = w, -h
    bmi.bmiHeader.biPlanes, bmi.bmiHeader.biBitCount = 1, 32
    bits = ctypes.c_void_p()
    hbm = gdi32.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    old_bm = gdi32.SelectObject(hdc, hbm)
    gdi32.SetBkMode(hdc, TRANSPARENT)
    gdi32.SetTextColor(hdc, 0x00FFFFFF)
    draw_rect = wintypes.RECT(0, 0, w, h)
    user32.DrawTextW(hdc, text, -1, ctypes.byref(draw_rect), flags)
    buf = ctypes.string_at(bits, w * h * 4)
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("L")
    gdi32.SelectObject(hdc, old_bm)
    gdi32.SelectObject(hdc, old_font)
    gdi32.DeleteObject(hbm)
    gdi32.DeleteObject(hfont)
    gdi32.DeleteDC(hdc)
    return img


def draw_text(canvas, xy, text, size, color, bold=False, max_w=None, anchor="left", name=FONT_NAME):
    """วาดข้อความลง canvas (RGBA) คืนความกว้างที่ใช้"""
    mask = text_mask(text, size, bold, max_w, name)
    x, y = xy
    if anchor == "right":
        x -= mask.size[0]
    elif anchor == "center":
        x -= mask.size[0] // 2
    fill = Image.new("RGBA", mask.size, tuple(color[:3]) + (255,))
    canvas.paste(fill, (int(x), int(y)), mask)
    return mask.size[0]


def text_width(text, size, bold=False, name=FONT_NAME):
    return text_mask(text, size, bold, None, name).size[0]
