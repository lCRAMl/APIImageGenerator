import subprocess
from datetime import datetime
import os
import shutil

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


# =========================
# PYINSTALLER BUILD
# =========================

def build_pyinstaller(version):
    safe_app = APP_NAME.replace(" ", "")
    safe_version = version.replace("v", "").replace("+", "_").replace(" ", "_")
    exe_name = f"{safe_app}_v{safe_version}"

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

    build_pyinstaller(version)
    
    clean()

    print("\n✅ DONE")


if __name__ == "__main__":
    main()