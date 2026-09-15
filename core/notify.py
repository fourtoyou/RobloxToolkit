"""แจ้งเตือนเข้า Discord ผ่าน webhook (ผู้ใช้ใส่ URL เองในหน้าตั้งค่า) + Windows toast"""
import threading
import time


def discord(url, title, desc, color=0x2EE6A8):
    if not url or "discord" not in url:
        return

    def _send():
        try:
            import requests
            requests.post(url, json={"embeds": [{"title": title, "description": desc, "color": color,
                                                 "footer": {"text": "Roblox Toolkit"},
                                                 "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())}]},
                          timeout=8)
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()


def discord_file(url, title, desc, path, color=0x2EE6A8):
    """webhook พร้อมรูปแนบ (multipart) — ใช้ตอนเฝ้าจอเจอของ จะได้เห็นภาพบนมือถือเลย"""
    if not url or "discord" not in url:
        return

    def _send():
        try:
            import json
            import requests
            payload = {"embeds": [{"title": title, "description": desc, "color": color, "image": {"url": "attachment://hit.png"},
                                   "footer": {"text": "Roblox Toolkit"}, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())}]}
            with open(path, "rb") as f:
                requests.post(url, data={"payload_json": json.dumps(payload)}, files={"files[0]": ("hit.png", f, "image/png")}, timeout=15)
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()


def toast(title, msg):
    """แจ้งเตือนมุมจอด้วย PowerShell (ไม่ต้องลงอะไรเพิ่ม)"""
    def _t():
        try:
            import subprocess
            t = title.replace("'", "''")
            m = msg.replace("'", "''")
            ps = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;"
                  "$x=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
                  f"$t=$x.GetElementsByTagName('text'); $t[0].AppendChild($x.CreateTextNode('{t}'))|Out-Null; $t[1].AppendChild($x.CreateTextNode('{m}'))|Out-Null;"
                  "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Roblox Toolkit').Show([Windows.UI.Notifications.ToastNotification]::new($x))")
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=15,
                           creationflags=0x08000000)
        except Exception:
            pass

    threading.Thread(target=_t, daemon=True).start()
