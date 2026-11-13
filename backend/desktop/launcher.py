"""KnifeForge Pro, desktop build: the program behind the desktop icon.

1. Find the data folder (Windows: %LOCALAPPDATA%\\KnifeForge Pro, macOS: ~/Library/Application
   Support/KnifeForge Pro, Linux: ~/.local/share/knifeforge-pro) and prepare its config.
2. If KnifeForge is already running, open it in the browser and stop there.
3. Copy the database aside when an update brings new migrations, then apply them.
4. Serve the interface and the API on 127.0.0.1 only, and open the browser.
5. Show a small window: open, data folder, quit. Closing it stops KnifeForge.

Nothing is sent anywhere: the server listens on this computer only.

    python desktop/launcher.py [--data-dir DIR] [--no-browser] [--no-window]
"""

import argparse
import faulthandler
import json
import logging
import logging.handlers
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
FROZEN = getattr(sys, "frozen", False)
# PyInstaller unpacks next to the executable; from source, the backend folder is HERE's parent
BUNDLE = Path(getattr(sys, "_MEIPASS", HERE.parent))
if not FROZEN:
    sys.path.insert(0, str(BUNDLE))

from app.core import desktop  # noqa: E402 - needs the path above, and must not import app.config

APP_TITLE = "KnifeForge Pro"
logger = logging.getLogger("knifeforge")


def frontend_dist() -> Path | None:
    candidate = BUNDLE / "frontend_dist" if FROZEN else BUNDLE.parent / "frontend" / "dist"
    return candidate if (candidate / "index.html").exists() else None


def setup_logging(data_dir: Path) -> None:
    logs = data_dir / "Journaux"
    logs.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(logs / "knifeforge.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    if sys.stderr is not None:  # a windowed executable has no console
        root.addHandler(logging.StreamHandler())


def running_instance(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
            return json.load(response).get("app") == "knifeforge-pro"
    except Exception:  # noqa: BLE001 - nothing there, or something that is not KnifeForge
        return False


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def migrate(data_dir: Path) -> None:
    """Bring the database to the version of this program. Before an update changes it, the
    file is copied aside: an update can always be undone by putting that copy back."""
    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine

    cfg = Config()
    cfg.set_main_option("script_location", str(BUNDLE / "alembic"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    db_file = data_dir / desktop.DB_NAME
    if db_file.exists():
        engine = create_engine(f"sqlite:///{db_file.as_posix()}")
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
        engine.dispose()
        if current != head:
            folder = data_dir / "Sauvegardes avant mise à jour"
            folder.mkdir(parents=True, exist_ok=True)
            copy = folder / f"knifeforge-v{current or 'vide'}-{datetime.now():%Y-%m-%d_%H%M}.db"
            shutil.copy2(db_file, copy)
            logger.info("Database %s -> %s, copy kept in %s", current, head, copy)
    command.upgrade(cfg, "head")


def open_folder(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - the user's own data folder
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    try:
        subprocess.Popen([opener, str(path)])  # noqa: S603 - fixed program, the user's own data folder
    except OSError:
        webbrowser.open(path.as_uri())


def control_window(url: str, data_dir: Path, stop) -> None:
    """The small window that says KnifeForge is running and lets the user stop it."""
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title(APP_TITLE)
    root.resizable(False, False)
    icon = BUNDLE / "desktop" / "icon.ico"
    if icon.exists():
        try:
            root.iconbitmap(str(icon))
        except tk.TclError:
            pass
    frame = ttk.Frame(root, padding=18)
    frame.grid()
    ttk.Label(frame, text="KnifeForge Pro est lancé.", font=("Segoe UI", 12, "bold")).grid(columnspan=3, sticky="w")
    ttk.Label(frame, text=f"Il s'ouvre dans votre navigateur à l'adresse {url}").grid(columnspan=3, sticky="w", pady=(4, 0))
    ttk.Label(frame, text="Fermer cette fenêtre arrête KnifeForge.", foreground="#6f6a60").grid(columnspan=3, sticky="w", pady=(2, 12))

    def quit_app() -> None:
        stop()
        root.destroy()

    ttk.Button(frame, text="Ouvrir KnifeForge", command=lambda: webbrowser.open(url)).grid(row=3, column=0, padx=(0, 8))
    ttk.Button(frame, text="Dossier des données", command=lambda: open_folder(data_dir)).grid(row=3, column=1, padx=(0, 8))
    ttk.Button(frame, text="Quitter", command=quit_app).grid(row=3, column=2)
    root.protocol("WM_DELETE_WINDOW", quit_app)
    root.mainloop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("KNIFEFORGE_DATA_DIR") or desktop.default_data_dir()))
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument("--no-window", action="store_true", help="no control window: run until interrupted")
    args = parser.parse_args(argv)

    data_dir: Path = args.data_dir
    config = desktop.prepare_environment(data_dir, frontend_dist())
    setup_logging(data_dir)
    # a start that hangs leaves no trace in a windowed program: after 90 s, write where it is
    stack_file = open(data_dir / "Journaux" / "demarrage-lent.txt", "w", encoding="utf-8")  # noqa: SIM115
    faulthandler.dump_traceback_later(90, repeat=False, file=stack_file)

    preferred = int(config.get("port", desktop.DEFAULT_PORT))
    if running_instance(preferred):
        logger.info("Already running on port %s: opening it", preferred)
        if not args.no_browser:
            webbrowser.open(f"http://127.0.0.1:{preferred}/")
        return 0
    port = preferred if port_free(preferred) else free_port()
    if port != preferred:
        logger.info("Port %s is taken by another program, using %s", preferred, port)
    desktop.update_config(data_dir, port=port)

    try:
        migrate(data_dir)
    except Exception:
        logger.exception("Database update failed")
        raise

    logger.info("Loading the application")
    import uvicorn

    from app.main import app

    logger.info("Starting the server on port %s", port)

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None, access_log=False))
    thread = threading.Thread(target=server.run, name="server", daemon=True)
    thread.start()
    for _ in range(300):  # up to 30 s on a slow first start
        if server.started or not thread.is_alive():
            break
        time.sleep(0.1)
    if not server.started:
        logger.error("The server did not start")
        return 1

    faulthandler.cancel_dump_traceback_later()
    url = f"http://127.0.0.1:{port}/"
    logger.info("KnifeForge Pro ready at %s (data: %s)", url, data_dir)
    if not args.no_browser:
        webbrowser.open(url)

    def stop() -> None:
        server.should_exit = True

    if args.no_window:
        try:
            while thread.is_alive():
                thread.join(0.5)
        except KeyboardInterrupt:
            stop()
    else:
        control_window(url, data_dir, stop)
    thread.join(10)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("KnifeForge Pro stopped on an error")
        raise
