# PyInstaller recipe for the desktop build. From the backend folder, after `npm run build`
# in frontend:
#   pyinstaller --noconfirm desktop/knifeforge.spec
# Output: dist/KnifeForge Pro/ (the program and its files). Windows: packed by
# installer/knifeforge.iss; Linux: packed as an AppImage by installer/linux/build-appimage.sh;
# macOS: dist/KnifeForge Pro.app, packed as a disk image by the CI.
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

backend = Path(SPECPATH).parent
frontend_dist = backend.parent / "frontend" / "dist"
if not (frontend_dist / "index.html").exists():
    raise SystemExit("Build the interface first: cd frontend && npm run build")

datas = [
    (str(frontend_dist), "frontend_dist"),
    (str(backend / "alembic"), "alembic"),  # migration scripts are loaded at run time
    (str(backend / "desktop" / "icon.ico"), "desktop"),
]
datas += collect_data_files("facturx")  # XSD schemas and XMP template of Factur-X
datas += collect_data_files("reportlab")  # embedded fonts of the invoice PDF
datas += collect_data_files("ezdxf")

# numpy (under shapely) loads parts of numpy._core dynamically: the stock hook misses some
hiddenimports = collect_submodules("app") + collect_submodules("uvicorn") + collect_submodules("numpy._core")
hiddenimports += ["alembic.runtime.migration"]

a = Analysis(
    [str(backend / "desktop" / "launcher.py")],
    pathex=[str(backend)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["psycopg2", "pytest", "IPython", "matplotlib"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KnifeForge Pro",
    icon=str(backend / "desktop" / "icon.ico"),
    # the control window is the interface; logs go to the data folder.
    # KF_CONSOLE=1 builds a diagnostic variant that also prints to a console.
    console=os.environ.get("KF_CONSOLE") == "1",
)
coll = COLLECT(exe, a.binaries, a.datas, name="KnifeForge Pro")
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="KnifeForge Pro.app",
        icon=str(backend / "desktop" / "icon.ico"),  # converted to .icns by PyInstaller (Pillow)
        bundle_identifier="fr.knifeforge.pro",
        info_plist={"CFBundleShortVersionString": os.environ.get("KF_VERSION", "0.0.0"), "NSHighResolutionCapable": True},
    )
