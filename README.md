# MarkItDown GUI

A Windows desktop app (single `.exe`) wrapping Microsoft's
[MarkItDown](https://github.com/microsoft/markitdown) to convert documents to Markdown.

## Features
- **Batch convert** files: PDF, DOCX, PPTX, XLSX/XLS, Outlook MSG, HTML, CSV, JSON, XML, EPUB, IPYNB, ZIP, images (EXIF), audio (metadata)
- **Add a folder** (searched recursively) or **drag & drop** files/folders onto the list
- **URLs**: web pages, Wikipedia, YouTube (transcripts), RSS
- **Live Markdown preview** with Copy / Save As / Open output
- Save `.md` next to each source or into one output folder; optional overwrite (otherwise `name (1).md`)
- Options: keep embedded images as data URIs, enable MarkItDown plugins
- Runs conversions in a background thread with progress and Cancel
- Files passed on the command line (or dropped onto the `.exe` icon) are queued on launch

## Get the .exe

### Option A – GitHub Actions (no Windows machine needed)
Push this folder to a GitHub repo. The workflow in `.github/workflows/build-exe.yml`
builds on `windows-latest`, runs a self-test against the built exe, and uploads
`MarkItDownGUI.exe` as a build artifact (Actions → latest run → *Artifacts*).
To publish a release: **Actions → Build Windows EXE → Run workflow**, enter a tag such as
`v1.1.0`, and run it. The workflow builds and tests the exe, then creates that GitHub Release
with `MarkItDownGUI.exe` attached (notes come from `RELEASE_NOTES.md`).
Pushing a tag like `v1.1.0` from your own machine does the same.

### Option B – build locally on Windows
Requires Python 3.10+ (python.org installer, with "Add to PATH" and Tcl/Tk ticked).
```bat
build.bat
```
Output: `dist\MarkItDownGUI.exe` (~150–250 MB single file; first launch takes a few seconds while it unpacks).

### Run from source (any OS)
```bash
pip install -r requirements.txt
python markitdown_gui.py
```

### Verify a build
```bat
MarkItDownGUI.exe --selftest result.txt
```
Writes a PASS/FAIL report for HTML/CSV/XLSX/PPTX conversions; exit code 0 = OK.

## Files
| File | Purpose |
|---|---|
| `markitdown_gui.py` | Tkinter GUI (entry point) |
| `converter.py` | Thin, GUI-free wrapper around MarkItDown |
| `selftest.py` | Headless check used by `--selftest` |
| `MarkItDownGUI.spec` | PyInstaller build recipe (bundles MarkItDown's lazy imports and magika's model) |
| `build.bat` | One-click local Windows build |
| `requirements.txt` | Pinned dependencies |

## Notes
- Audio transcription and Azure Document Intelligence extras are left out to keep the exe smaller.
  To add them, change the extras in `requirements.txt` to `markitdown[all]` and rebuild.
- Windows SmartScreen may warn about an unsigned exe; click *More info → Run anyway*, or sign it with your certificate.
