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
import sys

# Bundle the Microsoft Visual C++ runtime (redistributable DLLs). numpy and onnxruntime
# need msvcp140.dll / vcruntime140_1.dll, which PCs without the VC++ Redistributable lack,
# causing "ImportError: import numpy failed" at startup.
if sys.platform == "win32":
    sysdir = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
    for dll in ("msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "vcruntime140.dll",
                "vcruntime140_1.dll", "concrt140.dll", "vcomp140.dll"):
        path = os.path.join(sysdir, dll)
        if os.path.exists(path):
            binaries.append((path, "."))
            print(f"[spec] bundling {dll}")
        else:
            print(f"[spec] WARNING: {dll} not found")

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
