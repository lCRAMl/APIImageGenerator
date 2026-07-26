#AUTOBUILD.py

from ensurepip import version
import subprocess
from datetime import datetime
import os
import shutil
import time
from pathlib import Path

# =========================
# CONFIG
# =========================

APP_NAME = "API Image Generator"

ICON_PATH = "assets/gemini_icon.ico"

ASSET_PATHS = {
    "assets": "assets",
    "SplashScreenPython\\assets": "assets"
}

VERSION_FILE = "build_version.py"

OUTPUT_DIR = "output"
BUILD_DIR = "pyinstaller_build"

AUTO_PY_TO_EXE_LAUNCH = False


# =========================
# VERSION HELPERS
# =========================

def get_git_version():
    try:
        return subprocess.check_output(
            ["git", "describe", "--tags", "--long"]
        ).decode().strip()
    except Exception:
        return "0.0.0-0-unknown"

def get_git_commit():
    return subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"]
    ).decode().strip()

def get_git_commit_url():
    try:
        # short commit hash
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"]
        ).decode().strip()

        # remote URL (origin)
        remote = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"]
        ).decode().strip()

        # normalize SSH → HTTPS
        if remote.startswith("git@github.com:"):
            remote = remote.replace("git@github.com:", "https://github.com/")
            remote = remote.replace(".git", "")
        elif remote.startswith("https://") and remote.endswith(".git"):
            remote = remote[:-4]

        # build URL (GitHub-style)
        if "github.com" in remote:
            return f"{remote}/commit/{commit}"

        # fallback generic
        return f"{remote}/commit/{commit}"

    except Exception:
        return "unknown-commit-url"

def get_build_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =========================
# WRITE VERSION FILE
# =========================

def write_version_file(version, build_time, COMMIT, COMMIT_URL):
    content = f'''# AUTO GENERATED FILE
APP_NAME = "{APP_NAME}"
VERSION = "{version}"
BUILD_TIME = "{build_time}"
COMMIT = "{COMMIT}"
COMMIT_URL = "{COMMIT_URL}"
BUILD_INFO = "{APP_NAME} \\n{version} \\n{build_time}"
'''

    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ Version file written: {VERSION_FILE}")


# =========================
# CLEAN OUTPUT
# =========================

def clean():
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR, ignore_errors=True)

    # remove leftover spec files
    for file in os.listdir("."):
        if file.endswith(".spec"):
            os.remove(file)
            print(f"🧹 removed {file}")

def get_start_menu_programs_dir():
    """Liefert den "Start Menu\\Programs"-Ordner des aktuellen Benutzers
    (das ist der Ordner, aus dem Windows u.a. die An-die-Taskleiste-anheften-
    und Startmenü-Kacheln speist).

    Nutzt SHGetFolderPathW mit CSIDL_PROGRAMS - diese API wird von Windows
    seit Windows 2000 bis einschließlich Windows 11 aus Kompatibilitäts-
    gründen unterstützt und liefert den Pfad auch bei umgeleiteten Profilen
    (z.B. Firmen-Domänen) korrekt.
    """
    CSIDL_PROGRAMS = 0x0002
    SHGFP_TYPE_CURRENT = 0

    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        result = ctypes.windll.shell32.SHGetFolderPathW(
            0, CSIDL_PROGRAMS, 0, SHGFP_TYPE_CURRENT, buf
        )
        if result == 0 and buf.value:
            return buf.value
    except Exception:
        pass

    # Fallback: Pfad ueber die APPDATA-Umgebungsvariable dynamisch ermitteln
    appdata = os.environ.get("APPDATA") or os.path.join(
        "C:\\Users", os.environ.get("USERNAME", ""), "AppData", "Roaming"
    )
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs")


def create_shortcut(app_name, target_exe, working_dir):
    try:
        import pythoncom
        from win32com.shell import shell

        pythoncom.CoInitialize()  # 🔥 CRITICAL FIX

        target_exe = os.path.realpath(os.path.abspath(target_exe))

        if not os.path.exists(target_exe):
            raise FileNotFoundError(target_exe)

        shortcut_dir = get_start_menu_programs_dir()
        os.makedirs(shortcut_dir, exist_ok=True)
        shortcut_path = os.path.realpath(os.path.join(shortcut_dir, f"{app_name}.lnk"))

        shell_link = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink,
            None,
            pythoncom.CLSCTX_INPROC_SERVER,
            shell.IID_IShellLinkW
        )

        for _ in range(50):
            if os.path.exists(target_exe) and os.path.getsize(target_exe) > 0:
                break
            time.sleep(0.1)
        else:
            raise FileNotFoundError("EXE not ready yet: " + target_exe)

        shell_link.SetPath(target_exe)
        shell_link.SetWorkingDirectory(os.path.abspath(working_dir))
        shell_link.SetDescription(app_name)

        persist_file = shell_link.QueryInterface(pythoncom.IID_IPersistFile)
        persist_file.Save(shortcut_path, 0)

        print(f"🔗 Windows Taskbar Shortcut created: {shortcut_path}")

    except Exception as e:
        print(f"⚠ Shortcut creation failed: {e}")


# =========================
# PYINSTALLER BUILD
# =========================

def get_c2pa_dll_path():
    """Findet die c2pa_c.dll im installierten c2pa-Package.

    Das c2pa-Package laedt diese DLL zur Laufzeit dynamisch per ctypes,
    weshalb PyInstaller sie bei der statischen Analyse nicht automatisch
    erkennt und mitbuendelt.
    """
    try:
        import c2pa
    except ImportError:
        return None

    dll_path = Path(c2pa.__file__).parent / "libs" / "c2pa_c.dll"
    return dll_path if dll_path.exists() else None


def build_pyinstaller(exe_name):

    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",

        # output control
        f"--name={exe_name}",
        f"--distpath={OUTPUT_DIR}",
        f"--workpath={BUILD_DIR}",

        "--clean",
        "--noconfirm",

        f"--icon={ICON_PATH}",
    ]

    # =========================
    # ADD DATA FIXED MAPPING
    # =========================
    for source, target in ASSET_PATHS.items():
        if os.path.exists(source):
            cmd.append(f"--add-data={source}{os.pathsep}{target}")

    # =========================
    # ADD C2PA DLL (dynamisch per ctypes geladen, von PyInstaller nicht
    # automatisch erkannt)
    # =========================
    c2pa_dll = get_c2pa_dll_path()
    if c2pa_dll:
        cmd.append(f"--add-binary={c2pa_dll}{os.pathsep}c2pa/libs")
    else:
        print("⚠ c2pa_c.dll nicht gefunden - Build wird ohne C2PA-Unterstuetzung erstellt")

    cmd.append("APIImageGenerator.py")

    print("\n🚀 Running build:\n")
    print(" ".join(cmd))
    print("\n")

    subprocess.run(cmd, check=True)


# =========================
# MAIN
# =========================

def main():
    print("🔧 Build started...")

    version = get_git_version()
    build_time = get_build_time()
    COMMIT = get_git_commit()
    COMMIT_URL = get_git_commit_url()

    print(f"📦 Git Version: {version}")
    print(f"⏱ Build Time: {build_time}")
    print(f"🔗 Commit: {COMMIT}")
    print(f"🌐 Commit URL: {COMMIT_URL}")

    write_version_file(version, build_time, COMMIT, COMMIT_URL)

    safe_app = APP_NAME.replace(" ", "")
    safe_version = version.replace("+", "_").replace(" ", "_")
    exe_name = f"{safe_app}_{safe_version}"

    build_pyinstaller(exe_name)
    
    exe_file = f"{exe_name}.exe"
    exe_path = os.path.abspath(os.path.join(OUTPUT_DIR, exe_file))

    create_shortcut(safe_app, exe_path, OUTPUT_DIR)
    clean()

    print("\n✅ DONE")


if __name__ == "__main__":
    main()