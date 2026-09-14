# Roblox Toolkit

โปรแกรมเดียวจบสำหรับคนเล่น Roblox บน Windows — เขียนเองทั้งหมด อ่านโค้ดได้ทุกบรรทัด ไม่ต่อเน็ตยกเว้นที่ระบุ

| หน้า | ทำอะไร |
|---|---|
| 🎮 Anti-AFK | กันโดนเตะ idle 20 นาที: เด้ง Roblox แบบล่องหน → กด Space/ซูมกล้อง → ย่อกลับ · โหมดซ่อน (ไม่กระพริบเลย) · ไม่กดตอนคุณกำลังพิมพ์ · **ต่อใหม่อัตโนมัติเมื่อหลุด** (อ่าน log ของ Roblox แล้วเปิดกลับเซิร์ฟเดิม) · **ตั้งเวลา** (อีก N นาที → หยุด / ปิด Roblox / Sleep / ปิดเครื่อง) · **พรีวิวหน้าจอเกม** (เห็นแม้ตอนซ่อนหน้าต่าง) · F8 เริ่ม/หยุด · tray · **🔁 ตารางเวลาทำซ้ำทุกวัน** (เช่น 23:00 เริ่ม Anti-AFK · 07:00 ปิด Roblox) |
| 🕘 ประวัติ | 50 เซสชันล่าสุด (เกม / เวลา / สาเหตุที่จบ) + การ์ดสรุปย้อนหลัง |
| 🖱 ออโต้คลิก | คลิกรัว/กดปุ่มรัว (SendInput) — สไลเดอร์ 1-100 ครั้ง/วิ **หรือระบุ ms เอง (1 ms ≈ 1000 ครั้ง/วิ)** · **โหมดกดค้าง**หรือกด F6 ติด-ดับ · คลิกเดี่ยว/ดับเบิล/ทริปเปิล · **ล็อกหลายจุดวนคลิก** (F7 เก็บตำแหน่ง) · สุ่มจังหวะกำหนดช่วงเอง · **รัวเป็นชุดแล้วพัก** · **โปรไฟล์ต่อเกม** · **คลิกเฉพาะตอนหน้าต่าง Roblox โฟกัส** · หยุดเองตามเวลา/จำนวนครั้ง — ⚠ เกมที่มีระบบจับออโต้คลิกอาจแบน ใช้โดยรับความเสี่ยงเอง 
| 🎬 อัดมาโคร | (อยู่ในหน้าออโต้คลิก) อัดการขยับเมาส์ + คลิก + กดปุ่ม พร้อมจังหวะเวลาจริง แล้วเล่นซ้ำ — **F4 อัด · F5 เล่น** · วนกี่รอบก็ได้ · ปรับความเร็ว 0.1-10x · เล่นเฉพาะตอนอยู่ในหน้าต่าง Roblox · เก็บได้หลายมาโคร |
| 🖥 เครื่อง | มอนิเตอร์สด: CPU / RAM / GPU / **อุณหภูมิ GPU** / VRAM / ไฟที่ GPU กิน / ดิสก์ / แบต · กราฟย้อนหลัง 20 นาที · โปรเซสที่กินแรมมากสุด · **เตือนอัตโนมัติ** เมื่อ GPU ร้อนค้างเกิน 2 นาที, แรมเกิน 92%, ดิสก์เหลือ <5 GB (toast + Discord) · **🐢 จำกัด FPS ตอนไม่ได้ดูจอ** (3-30 FPS · ปลดล็อกเองเมื่อกลับไปคลิกที่เกม) · **🔇 ปิดเสียง Roblox อัตโนมัติตอน AFK** · **🎮 โหมดเล่นเกม** คาย VRAM ให้เกม |
| 📈 วิเคราะห์ | **heatmap วัน×ชั่วโมง**, กราฟชั่วโมงที่เล่นบ่อย, เกมที่เล่นมากสุด, สาเหตุที่หลุด + **ข้อสังเกตเป็นภาษาคน** (วันไหนเล่นหนักสุด, หลุดบ่อยช่วงไหน, เล่นติดกันกี่วัน) · แชร์เป็นการ์ดเข้า Discord ได้ |
| 📊 สถิติ | อ่าน log ทั้งหมด → เวลาเล่นต่อวัน / ต่อเกม / ประวัติหลุดพร้อมสาเหตุ (ชื่อเกมดึงจาก Roblox API) |
| 📶 เน็ต | ping เร้าเตอร์ / อินเทอร์เน็ต / roblox.com ทุกวิ → บอกว่าหลุดเพราะ Wi-Fi, ISP หรือเซิร์ฟ + ที่ตั้งเซิร์ฟที่เล่นอยู่ |
| 🛡 ตรวจไฟล์ | เช็ค .exe ก่อนรัน: ลายเซ็น, แพ็คด้วยอะไร, string ของ stealer (webhook/cookie/ROBLOSECURITY), SHA-256 → VirusTotal · สแกนทั้ง Downloads |
| ⚡ FastFlag | ตั้งสวิตช์ภายในของ Roblox เอง (เขียน `ClientAppSettings.json` ตรงๆ **ไม่ต้องพึ่ง Bloxstrap**) — ทำตาม **allowlist ของ Roblox (29 ก.ย. 2025)** เท่านั้น: ระดับความแรง 5 ระดับ · ตัวเร่งกราฟิก DX11/Vulkan/OpenGL · สวิตช์เสริม · เตือนทันทีถ้าพิมพ์ flag ที่ Roblox ปิดไปแล้ว (ปลดล็อก FPS/ปิดเงา/telemetry ใช้ไม่ได้แล้ว) · ยก priority ให้ Roblox ได้ CPU ก่อน · ใส่ให้ใหม่เองเมื่อ Roblox อัปเดตเวอร์ชัน |
| 🩺 สุขภาพระบบ | เช็ค/ซ่อมตัวเปิดเกม (handler ที่ Roblox ชอบแย่งคืน, shortcut เสีย) · ล้าง log · เปิดพร้อม Windows · บอกว่า Roblox ที่รันอยู่เป็นตัวปกติ/Bloxstrap/Microsoft Store |
| 🚀 เกมโปรด | เกมที่เล่นบ่อย + เพิ่มเอง · คนเล่นสด · ปุ่ม เข้าเกม / เซิร์ฟ ping ต่ำสุด / กลับเซิร์ฟล่าสุด |
| ⚙ ตั้งค่า | แจ้งเตือน Discord webhook, **Session Recap** (การ์ดสรุปหลังเล่นจบ → toast + Discord), **Watchdog** (Roblox ค้าง >30 วิ → เปิดกลับเซิร์ฟเดิม · Roblox แครช/ปิดตัวเองระหว่าง Anti-AFK → เปิดกลับ · เก็บกวาด Roblox ที่ค้างเบื้องหลังไม่มีหน้าต่าง), **Adaptive delay** (โดนเตะ idle ทั้งที่ทำงานอยู่ → กดถี่ขึ้นเอง), **Overlay** มุมจอ (F9), เช็คอัปเดต , **เปิด Roblox หลายหน้าต่าง** (หลายบัญชี), **ส่งออก/นำเข้าค่าตั้ง** |

## อัปเดตอัตโนมัติ
- Release ล่าสุด: https://github.com/fourtoyou/RobloxToolkit/releases/latest (ไฟล์ `RobloxToolkit.exe` + SHA256 ในโน้ต) · โปรแกรมตั้ง repo `fourtoyou/RobloxToolkit` ไว้ให้แล้ว
- หน้าตั้งค่า → ใส่ repo (`ชื่อGitHub/RobloxToolkit`) → **เช็คอัปเดต** → ถ้ามีใหม่กด **⬇ ติดตั้งเวอร์ชันใหม่** โปรแกรมโหลด ตรวจขนาด + SHA256 แล้วเปิดตัวเองใหม่
- ปล่อยเวอร์ชัน: แก้ `VERSION` ใน `core/config.py` → commit → `git tag v2.9.0 && git push --tags` → GitHub Actions build .exe และสร้าง Release พร้อม SHA256 ให้เอง (`.github/workflows/release.yml`)

## ใช้งาน
- ดับเบิลคลิก `dist\RobloxToolkit.exe` (หรือ `run.bat` ถ้ามี Python)
- `RobloxToolkit.exe --afk` = เปิดแล้วเริ่ม Anti-AFK ทันที · `--tray` = เริ่มแบบซ่อน
- ปุ่มลัด: **F8** เริ่ม/หยุด Anti-AFK · **F9** เปิด/ปิด overlay มุมจอ · **F6** เริ่ม/หยุดออโต้คลิก · **F7** เก็บตำแหน่งเมาส์เป็นจุดคลิก · **F4** อัดมาโคร · **F5** เล่นมาโคร
- หน้าสถิติ: ปุ่ม "แชร์การ์ดสัปดาห์" วาดการ์ดสถิติ 7 วันเป็นรูป + ส่งเข้า Discord ถ้าตั้ง webhook ไว้
- **คลังประวัติถาวร** `sessions.json` — Roblox ลบ log ตัวเองทิ้งเรื่อยๆ (เคยมี 436 ไฟล์ เหลือ 21 ในวันเดียว) โปรแกรมจึงเก็บเซสชันที่อ่านได้ไว้เองตลอด เก็บ 2 ปี
- ข้อมูล/ตั้งค่าอยู่ที่ `%USERPROFILE%\.robloxtoolkit\` (`status.json` ให้ Discord bot อ่าน · `cmd/` `res/` รับคำสั่งจากบอท) — ไม่ใช้ AppData เพราะ Python จาก Microsoft Store จำลองโฟลเดอร์นั้น
- รองรับ Roblox ทั้งตัวปกติ/Bloxstrap (`%LOCALAPPDATA%\Roblox\logs`) และตัว **Microsoft Store / Xbox app** (`%LOCALAPPDATA%\RobloxPCGDK\logs`) — หน้าสุขภาพระบบจะบอกว่าที่เปิดอยู่เป็นตัวไหน (Bloxstrap ไม่มีผลกับตัว Store)

## สั่งจาก Discord (ผ่าน bot.หมา)
บอทเขียนไฟล์คำสั่งลง `cmd/` → Toolkit ทำแล้วตอบใน `res/` (ไม่เปิดพอร์ต ไม่ต้องตั้งค่าอะไร)

| คำสั่งในดิส | Toolkit ทำอะไร |
|---|---|
| `/screen` (`live:True`) | ถ่ายหน้าต่าง Roblox ด้วย PrintWindow (ถ่ายได้แม้โดนบัง/ซ่อนอยู่) · live = อัปเดตทุก 10 วิ 2 นาที |
| `/afk start` `stop` `hide` `unhide` `status` | ควบคุม Anti-AFK / โหมดซ่อน |
| `/afk timer <นาที> <ทำอะไร>` | ตั้งเวลาเหมือนในหน้า Anti-AFK (0 = ยกเลิก) |
| `/afk log` | log ล่าสุดของ Toolkit |
| `/launch <ลิงก์>` `/rejoin` | เปิดเกม / กลับเซิร์ฟล่าสุด |
| `/power` | ปิด Roblox / Sleep / ปิดเครื่อง / ยกเลิก (มีปุ่มยืนยันในดิส) |
| `/quiet` | ย้ายไปเซิร์ฟที่คนน้อยสุด |
| `/analytics [days]` | สร้างการ์ดวิเคราะห์การเล่นส่งเข้าดิส |
| `/pc` | ดึงค่าเฉลี่ย CPU/RAM/GPU/อุณหภูมิ + โปรเซสกินแรม จาก Toolkit |


## build เอง
```
build.bat
```
(ต้องมี Python 3.10+ — สคริปต์จะลง customtkinter, pystray, pillow, requests, pyinstaller ให้)

## โครงสร้าง
```
app.py              UI ทั้งหมด (customtkinter)
core/win.py         Win32: หาหน้าต่าง, focus, คีย์, ICMP ping, hotkey
core/antiafk.py     engine + LogWatcher (ตาม log Roblox) + auto-rejoin
core/history.py     parse log → เซสชัน/สถิติ, ชื่อเกม
core/netmon.py      วัดเน็ต 3 จุด + verdict
core/filecheck.py   วิเคราะห์ไฟล์
core/health.py      Bloxstrap/registry/shortcut/autostart
core/notify.py      Discord webhook + Windows toast
core/session.py     Session recap + การ์ดรูป (recap/weekly) + webhook รูป
core/watchdog.py    ตรวจ Roblox ค้าง / แครช / โปรเซสค้างเบื้องหลัง
core/launcher.py    เกมโปรด, เซิร์ฟ ping ต่ำสุด, deep link เข้าเกม
core/overlay.py     หน้าต่างลอยมุมจอ (คลิกทะลุ)
core/gditext.py     วาดฟอนต์ไทยด้วย Windows GDI
core/analytics.py   วิเคราะห์: ชั่วโมง/วัน/heatmap/สาเหตุหลุด/ข้อสังเกต
core/charts.py      วาดกราฟด้วย PIL (ไม่ใช้ matplotlib)
core/clicker.py     ออโต้คลิก/กดปุ่มรัว (SendInput) + เบรกความปลอดภัย
core/sysmon.py      เฝ้า CPU/RAM/GPU/อุณหภูมิ + เตือนเมื่อร้อน/แรมตึง
core/macro.py       อัด/เล่นมาโคร (low-level hook + SendInput)
core/schedule.py    ตารางเวลาทำซ้ำทุกวัน
core/fpscap.py      จำกัด FPS (หยุด-ปลุกเธรด) + ปิดเสียงเกม + เปิดหลายหน้าต่าง
core/fastflag.py    เขียน FastFlag ให้ Roblox (ClientAppSettings.json)
core/servers.py     หาเซิร์ฟคนน้อยสุด + เฝ้าจำนวนคน + ย้ายเซิร์ฟ
core/config.py      ค่าตั้ง, path, status.json
core/ipc.py         รับคำสั่งจาก Discord bot ผ่านไฟล์ + จับภาพหน้าต่าง (PrintWindow)
```

## สิ่งที่ส่งออกนอกเครื่อง (ทั้งหมดปิดได้)
- ชื่อเกม: `apis.roblox.com`, `games.roblox.com` (ส่งแค่ placeId)
- ที่ตั้งเซิร์ฟ: `ipinfo.io` (ส่งแค่ IP ของเซิร์ฟเกม ไม่ใช่ของคุณ) — ปิดได้ในตั้งค่า
- Discord webhook ที่คุณตั้งเอง

## หมายเหตุสำหรับคนแก้โค้ด
- ถ้ารันจาก **Python ของ Microsoft Store** registry ที่อ่าน/เขียนจะเป็นตัวจำลอง (MSIX virtualization) — หน้าสุขภาพระบบจะโชว์ค่าผิด และปุ่มซ่อมจะไม่มีผลจริง ใช้ .exe ที่ build แล้ว หรือ Python จาก python.org
- เทคนิค Anti-AFK อ้างอิง JunkBeat/AntiAFK-Roblox · การอ่าน log อ้างอิง Bloxstrap ActivityWatcher
