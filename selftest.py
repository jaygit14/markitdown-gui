"""Headless self-test: `MarkItDownGUI.exe --selftest result.txt` converts sample files
with the bundled MarkItDown and writes a report. Exit code 0 = all passed."""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path


def _make_samples(d: Path) -> dict[str, str]:
    samples = {}
    (d / "s.html").write_text("<html><body><h1>Hello HTML</h1><p>para</p></body></html>", encoding="utf-8")
    samples["s.html"] = "# Hello HTML"
    (d / "s.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    samples["s.csv"] = "| a | b |"
    import openpyxl
    wb = openpyxl.Workbook(); wb.active.append(["col1", "col2"]); wb.active.append(["x", "y"])
    wb.save(d / "s.xlsx"); samples["s.xlsx"] = "col1"
    from pptx import Presentation
    p = Presentation(); s = p.slides.add_slide(p.slide_layouts[1]); s.shapes.title.text = "Hello PPTX"
    p.save(d / "s.pptx"); samples["s.pptx"] = "Hello PPTX"
    return samples


def run(report_path: str) -> int:
    lines, ok = [], True
    try:
        import converter
        md = converter.make_converter()
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for name, expect in _make_samples(d).items():
                try:
                    text = converter.convert_source(md, str(d / name))
                    passed = expect in text
                except Exception as e:
                    text, passed = f"{type(e).__name__}: {e}", False
                ok &= passed
                lines.append(f"{'PASS' if passed else 'FAIL'} {name}: {text[:80]!r}")
            # extension-less file exercises magika content sniffing (bundled ONNX model)
            (d / "noext").write_text("<html><body><h2>Sniffed</h2></body></html>", encoding="utf-8")
            text = converter.convert_source(md, str(d / "noext"))
            lines.append(f"INFO noext (magika): {text[:80]!r}")
    except Exception:
        ok = False
        lines.append("FATAL\n" + traceback.format_exc())
    lines.append("RESULT: " + ("OK" if ok else "FAILED"))
    Path(report_path).write_text("\n".join(lines), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else "selftest.txt"))
