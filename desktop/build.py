"""Builds TrackDog for this system (run it on Linux for Linux, on Windows for Windows).

    python build.py            # dist/TrackDog/ (PyInstaller), on Windows also the installer (Inno Setup 6)

Needs the .venv with requirements.txt and requirements-dev.txt. The texts and the mark come from the
Android app (app/src/main/res, design/logo.svg): they are copied into tdd/res, so both versions ship the same.
"""
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
RES = HERE / "tdd" / "res"
sys.path.insert(0, str(HERE))
from tdd import VERSION  # noqa: E402


def copy_res():
    shutil.rmtree(RES, ignore_errors=True)
    for d in ("values", "values-pl"):
        (RES / d).mkdir(parents=True)
        shutil.copy(REPO / "app" / "src" / "main" / "res" / d / "strings.xml", RES / d / "strings.xml")
    shutil.copy(REPO / "design" / "logo.svg", RES / "logo.svg")


def make_icons():
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtCore import Qt
    app = QGuiApplication.instance() or QGuiApplication(["build"])  # noqa: F841
    r = QSvgRenderer(str(RES / "logo.svg"))
    img = QImage(256, 256, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    r.render(p)
    p.end()
    img.save(str(RES / "app.png"))
    img.save(str(RES / "app.ico"))


def main():
    copy_res()
    make_icons()
    sep = ";" if sys.platform == "win32" else ":"
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "TrackDog",
            "--icon", str(RES / ("app.ico" if sys.platform == "win32" else "app.png")),
            "--add-data", f"{RES}{sep}tdd/res",
            "--collect-submodules", "bleak", "--collect-submodules", "meshcore",
            "--distpath", str(HERE / "dist"), "--workpath", str(HERE / "build"), "--specpath", str(HERE / "build")]
    if sys.platform == "win32":
        args += ["--collect-all", "winrt"]
    subprocess.run(args + [str(HERE / "trackdog_desktop.py")], check=True)
    if sys.platform == "win32":
        iscc = [Path(p) for p in (Path.home() / "AppData/Local/Programs/Inno Setup 6/ISCC.exe",
                                  Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe")) if Path(p).exists()]
        if not iscc:
            sys.exit("Inno Setup 6 not found (winget install JRSoftware.InnoSetup)")
        subprocess.run([str(iscc[0]), f"/DAppVersion={VERSION}", str(HERE / "installer" / "setup.iss")], check=True)
        print(f"dist/TrackDog-Setup-{VERSION}.exe")
    else:
        out = HERE / "dist" / f"TrackDog-{VERSION}-linux-x86_64.tar.gz"
        with tarfile.open(out, "w:gz") as tar:
            tar.add(HERE / "dist" / "TrackDog", arcname="TrackDog")
            tar.add(HERE / "install-linux.sh", arcname="TrackDog/install-linux.sh")
        print(out)


if __name__ == "__main__":
    main()
