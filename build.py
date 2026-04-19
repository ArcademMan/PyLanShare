"""Build script for PyLanShare: Nuitka compilation + Inno Setup installer."""

import subprocess
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DIST = ROOT / "dist"
APP_NAME = "PyLanShare"
ENTRY = ROOT / "run.py"
ICON = ROOT / "assets" / "icon.ico"
ISS = ROOT / "installer.iss"


def find_inno_setup() -> Path | None:
    """Locate the Inno Setup compiler (ISCC.exe)."""
    candidates = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"),
    ]
    for p in candidates:
        if p.exists():
            return p
    # Try PATH
    iscc = shutil.which("ISCC")
    return Path(iscc) if iscc else None


def build_nuitka():
    """Compile the project with Nuitka."""
    print(f"\n{'='*60}")
    print(f"  Nuitka build — {APP_NAME}")
    print(f"{'='*60}\n")

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        f"--output-dir={DIST}",
        f"--output-filename={APP_NAME}.exe",
        "--enable-plugin=pyside6",
        "--windows-console-mode=disable",
        f"--windows-icon-from-ico={ICON}",
        # Include data dirs
        f"--include-data-dir={ROOT / 'shared' / 'locale'}=shared/locale",
        f"--include-data-dir={ROOT / 'pylanshare' / 'assets'}=pylanshare/assets",
        # Product info
        f"--product-name={APP_NAME}",
        "--product-version=1.0.1",
        f"--company-name=AmMstools",
        f"--file-description={APP_NAME} — LAN File Sync",
        "--copyright=MIT License",
        # Cleanup
        "--remove-output",
        str(ENTRY),
    ]

    print("Running:", " ".join(cmd), "\n")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("\nERROR: Nuitka build failed.")
        sys.exit(1)

    print(f"\nNuitka build complete. Output: {DIST / 'run.dist'}")


def build_installer():
    """Package the compiled output with Inno Setup."""
    print(f"\n{'='*60}")
    print(f"  Inno Setup — {APP_NAME}")
    print(f"{'='*60}\n")

    iscc = find_inno_setup()
    if iscc is None:
        print("WARNING: Inno Setup (ISCC.exe) not found. Skipping installer.")
        print("Install it from https://jrsoftware.org/isdl.php")
        return

    result = subprocess.run([str(iscc), str(ISS)])
    if result.returncode != 0:
        print("\nERROR: Inno Setup build failed.")
        sys.exit(1)

    print(f"\nInstaller created in: {ROOT / 'installer_output'}")


if __name__ == "__main__":
    build_nuitka()
    build_installer()
    print(f"\n{'='*60}")
    print("  All done!")
    print(f"{'='*60}")
