"""TrackDog for Linux and Windows.

    python trackdog_desktop.py [--demo] [--lang pl|en]
"""
import logging
import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from tdd import i18n


def main():
    QCoreApplication.setApplicationName("TrackDog")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # the window may hide in the tray and keep listening
    from tdd.ui import Config, MainWindow, data_dir
    logging.basicConfig(filename=str(data_dir() / "trackdog.log"), level=logging.INFO,
                        format="%(asctime)s %(name)s %(message)s")
    cfg = Config(data_dir() / "config.json")
    if "--lang" in sys.argv[:-1]:   # the installer passes the language chosen on its first page
        cfg["lang"] = sys.argv[sys.argv.index("--lang") + 1]
    if cfg["lang"]:
        i18n.set_lang(cfg["lang"])
    if "--demo" in sys.argv:
        cfg["demo"] = True
    w = MainWindow(cfg)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
