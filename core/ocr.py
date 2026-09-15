"""OCR ด้วยเอนจินของ Windows (Windows.Media.Ocr) ผ่าน PowerShell ที่เปิดค้างไว้ — ไม่ต้องลงอะไรเพิ่ม
เปิด PowerShell ใหม่ทุกครั้งเสีย ~1 วิ (โหลด WinRT) → เปิดทีเดียวแล้วส่งชื่อไฟล์ทาง stdin รับบรรทัดกลับทาง stdout
บังคับ en-US: ถ้าให้เลือกตามภาษาเครื่อง (ไทย) จะอ่านอังกฤษในเกมแทบไม่ได้"""
import os
import subprocess
import threading

from . import config

NO_WINDOW = 0x08000000
SCRIPT = r"""
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $t) { $asTask.MakeGenericMethod($t).Invoke($null, @($op)).GetAwaiter().GetResult() }
[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('en-US'))
if (-not $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if (-not $engine) { Write-Output "<<NOENGINE>>"; exit 1 }
Write-Output ("<<READY " + $engine.RecognizerLanguage.LanguageTag + ">>")
while ($true) {
  $p = [Console]::In.ReadLine()
  if ($null -eq $p) { break }
  try {
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($p)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $result.Lines | ForEach-Object { Write-Output $_.Text }
    $stream.Dispose(); $bitmap.Dispose(); $decoder = $null; $file = $null; $result = $null
  } catch { Write-Output ("<<ERR " + $_.Exception.Message + ">>") }
  [GC]::Collect(); [GC]::WaitForPendingFinalizers()
  Write-Output "<<END>>"
}
"""


class OCR:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.lang = None
        self.script = os.path.join(config.DATA_DIR, "ocr_server.ps1")

    def _start(self):
        os.makedirs(config.DATA_DIR, exist_ok=True)
        with open(self.script, "w", encoding="utf-8-sig") as f:
            f.write(SCRIPT)
        self.proc = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", self.script],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=NO_WINDOW)
        line = self.proc.stdout.readline().strip()
        if not line.startswith("<<READY"):
            raise RuntimeError("OCR ของ Windows ใช้ไม่ได้ (" + line + ") — ต้องมีภาษา English ติดตั้งใน Windows")
        self.lang = line[8:-2]

    def recognize(self, path):
        """คืน list บรรทัดข้อความในรูป — ยกเว้น RuntimeError ถ้าเอนจินใช้ไม่ได้"""
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                self._start()
            try:
                self.proc.stdin.write(path + "\n")
                self.proc.stdin.flush()
            except OSError:
                self.proc = None
                self._start()
                self.proc.stdin.write(path + "\n")
                self.proc.stdin.flush()
            out = []
            while True:
                line = self.proc.stdout.readline()
                if not line:
                    self.proc = None
                    raise RuntimeError("OCR หยุดทำงานกลางคัน")
                line = line.rstrip("\r\n")
                if line == "<<END>>":
                    break
                if line.startswith("<<ERR"):
                    raise RuntimeError(line[6:-2])
                if line.strip():
                    out.append(line)
            return out

    def stop(self):
        with self.lock:
            if self.proc:
                try:
                    self.proc.stdin.close()
                    self.proc.kill()
                except Exception:
                    pass
                self.proc = None


_ocr = None


def get():
    global _ocr
    if _ocr is None:
        _ocr = OCR()
    return _ocr
