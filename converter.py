"""Conversion helpers for MarkItDown GUI (no GUI imports, so it is testable headless)."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from markitdown import MarkItDown

SUPPORTED_EXTS = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".msg",
    ".html", ".htm", ".csv", ".json", ".xml", ".txt", ".md", ".rss", ".atom",
    ".epub", ".ipynb", ".zip",
    ".jpg", ".jpeg", ".png",          # EXIF metadata only (no LLM configured)
    ".wav", ".mp3", ".m4a", ".mp4",   # metadata only unless transcription deps present
}


def is_url(source: str) -> bool:
    return urlparse(source).scheme in ("http", "https")


def make_converter(enable_plugins: bool = False) -> MarkItDown:
    return MarkItDown(enable_plugins=enable_plugins)


def convert_source(md: MarkItDown, source: str, keep_data_uris: bool = False) -> str:
    """Convert a local path or http(s) URL to Markdown text."""
    result = md.convert(source, keep_data_uris=keep_data_uris)
    return result.text_content or ""


def _safe_name(text: str) -> str:
    text = re.sub(r"[^\w\-. ]+", "_", text).strip(" ._")
    return text[:120] or "document"


def output_path_for(source: str, out_dir: str | None, overwrite: bool) -> Path:
    """Where to write the .md for a source. out_dir=None means 'next to the source file'."""
    if is_url(source):
        p = urlparse(source)
        base = _safe_name((p.netloc + p.path).replace("/", "_"))
        folder = Path(out_dir) if out_dir else Path.home() / "Documents"
    else:
        src = Path(source)
        base = src.stem
        folder = Path(out_dir) if out_dir else src.parent
    target = folder / f"{base}.md"
    if overwrite:
        return target
    n = 1
    while target.exists():
        target = folder / f"{base} ({n}).md"
        n += 1
    return target


def find_supported_files(folder: str, recursive: bool = True) -> list[str]:
    root = Path(folder)
    it = root.rglob("*") if recursive else root.glob("*")
    return sorted(str(p) for p in it if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS)
