# PyInstaller spec for MarkItDown GUI  ->  dist/MarkItDownGUI.exe (single file, no console)
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = [], [], []

# MarkItDown loads its converters/optional deps lazily, and magika ships an ONNX model,
# so pull these packages in whole.
for pkg in ("markitdown", "magika", "tkinterdnd2", "pdfminer", "mammoth", "pptx",
            "openpyxl", "xlrd", "olefile", "youtube_transcript_api"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception as e:
        print(f"[spec] skipping {pkg}: {e}")

hiddenimports += collect_submodules("markitdown.converters") + ["selftest", "converter"]
import os
ICON = "icon.ico" if os.path.exists("icon.ico") else None
if ICON:
    datas += [(ICON, ".")]

a = Analysis(
    ["markitdown_gui.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["matplotlib", "IPython", "pytest", "notebook", "scipy"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="MarkItDownGUI",
    console=False,
    icon=ICON,
    upx=False,
)
