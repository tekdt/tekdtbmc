import sys
import tempfile
from pathlib import Path

def resolve_base_dir():
    candidates = []
    try:
        p = Path(sys.argv[0]).resolve()
        candidates.append(p.parent)
    except Exception:
        pass
    try:
        candidates.append(Path(__file__).resolve().parent)
    except Exception:
        pass
    try:
        candidates.append(Path(sys.executable).resolve().parent)
    except Exception:
        pass
    candidates.append(Path.cwd())
    uniq = []
    seen = set()
    for c in candidates:
        if c not in seen:
            uniq.append(c)
            seen.add(c)
    important = ["Tools", "ISOs", "Drivers", "Themes"]
    for c in uniq:
        if all((c / d).exists() for d in important):
            return c
    for c in uniq:
        if any((c / d).exists() for d in important):
            return c
    if uniq:
        return uniq[0]
    return Path.cwd()

BASE_DIR = resolve_base_dir()
if not str(BASE_DIR).startswith(tempfile.gettempdir()):
    pass

# --- Cấu hình và Hằng số ---
APP_VERSION = "1.0.6"
CONFIG_FILE = BASE_DIR / "tekdt_bmc.json"
ICON_PATH = BASE_DIR / "logo.ico"

# Định nghĩa tất cả các đường dẫn dựa trên BASE_DIR
TOOLS_DIR = BASE_DIR / "Tools"
ISOS_DIR = BASE_DIR / "ISOs"
THEMES_DIR = BASE_DIR / "Themes"
DRIVERS_DIR = BASE_DIR / "Drivers"
SCRIPTS_DIR = BASE_DIR / "Scripts"
VENTOY_DIR = TOOLS_DIR / "Ventoy"
FIDO_DIR = TOOLS_DIR / "Fido"
ARIA2_DIR = TOOLS_DIR / "aria2"
SEVENZIP_DIR = TOOLS_DIR / "7z"
WINCDEMU_DIR = TOOLS_DIR / "WinCDEmu"
TEKDTAIS_DIR = TOOLS_DIR / "TekDT_AIS"
WIMLIB_DIR = TOOLS_DIR / "wimlib"
OSCDIMG_DIR = TOOLS_DIR / "oscdimg"

# Đường dẫn đến các file thực thi
ARIA2_EXE = ARIA2_DIR / "aria2c.exe"
SEVENZIP_EXE = SEVENZIP_DIR / "7z.exe"
WINCDEMU_EXE = WINCDEMU_DIR / "wcdemu.exe"
WIMLIB_EXE = WIMLIB_DIR / "wimlib-imagex.exe"
TEKDTAIS_EXE = TEKDTAIS_DIR / "tekdt_ais.exe"
FIDO_SCRIPT_PATH = FIDO_DIR / "Fido.ps1"
OSCDIMG_EXE = OSCDIMG_DIR / "oscdimg.exe"

# Các đường dẫn file cấu hình khác
ISO_ANALYSIS_CACHE = ISOS_DIR / "iso_cache.json"
SHUTDOWN_SIGNAL_TEKDTAIS = TEKDTAIS_DIR / "shutdown_signal.txt"

directories_to_create = [TOOLS_DIR, FIDO_DIR, ISOS_DIR, SCRIPTS_DIR, ARIA2_DIR, SEVENZIP_DIR, WINCDEMU_DIR, TEKDTAIS_DIR, WIMLIB_DIR, OSCDIMG_DIR]
for path in directories_to_create:
    path.mkdir(parents=True, exist_ok=True)
    
required_dirs = [DRIVERS_DIR, THEMES_DIR]
for dir_path in required_dirs:
    if not dir_path.exists():
        print(f"Cảnh báo: Thư mục {dir_path} không tồn tại. Vui lòng sao chép nó cạnh ứng dụng.")

# API and Download URLs
VENTOY_API_URL = "https://api.github.com/repos/ventoy/Ventoy/releases/latest"
ARIA2_API_URL = "https://api.github.com/repos/aria2/aria2/releases/latest"
SEVENZIP_API_URL = "https://api.github.com/repos/ip7z/7zip/releases/latest"
FIDO_PS1_URL = "https://github.com/pbatard/Fido/raw/refs/heads/master/Fido.ps1"
WIMLIB_URL = "https://wimlib.net/downloads/wimlib-1.14.4-windows-x86_64-bin.zip"
WINCDEMU_API_URL = "https://api.github.com/repos/sysprogs/WinCDEmu/releases/latest"
TEKDTAIS_API_URL = "https://api.github.com/repos/tekdt/tekdtais/releases/latest"
SELF_UPDATE_API_URL = "https://api.github.com/repos/tekdt/tekdtbmc/releases/latest"
OSCDIMG_EXE_URL = "https://msdl.microsoft.com/download/symbols/oscdimg.exe/3D44737265000/oscdimg.exe"

WINDOWS_SERVER_2016_URL = "https://go.microsoft.com/fwlink/p/?LinkID=2195174&clcid=0x409&culture=en-us&country=US"
WINDOWS_SERVER_2022_URL = "https://go.microsoft.com/fwlink/p/?LinkID=2195280&clcid=0x409&culture=en-us&country=US"
WINDOWS_SERVER_2025_URL = "https://go.microsoft.com/fwlink/?linkid=2293312&clcid=0x409&culture=en-us&country=us"