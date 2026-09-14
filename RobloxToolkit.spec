# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['pystray._win32', 'pycaw']
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('comtypes')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# ห้ามแพ็ค UCRT/api-ms-win-* ของเครื่องที่ build ไปด้วย — เครื่อง GitHub Actions มีไฟล์พวกนี้ในโฟลเดอร์ Python
# PyInstaller เลยหยิบใส่ แล้ว python312.dll โหลดไม่ขึ้นบนเครื่องผู้ใช้ ("Failed to load Python DLL")
# Windows 10/11 มี UCRT ของระบบอยู่แล้ว ใช้ของระบบดีกว่า (เจอจริงตอนทดสอบอัปเดต 2.9.5→2.9.6)
a.binaries = [b for b in a.binaries if not b[0].lower().startswith(("api-ms-win-", "ucrtbase"))]
# numpy ไม่ได้ใช้ แต่ hook ของ PIL ลากมาถ้าเครื่องที่ build มีติดตั้ง — ตัดออก (เล็กลง ~10 MB)
a.binaries = [b for b in a.binaries if not b[0].lower().startswith("numpy")]
a.datas = [d for d in a.datas if not d[0].lower().startswith("numpy")]
a.pure = [m for m in a.pure if not m[0].startswith("numpy")]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RobloxToolkit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
