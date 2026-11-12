"""MarkItDown GUI - a desktop front-end for Microsoft MarkItDown.

Convert PDF, Word, PowerPoint, Excel, HTML, CSV, EPUB, Outlook .msg and more
into Markdown. Batch conversion, URL support, live preview, drag & drop.
"""
from __future__ import annotations

import os
import sys

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--selftest":
    import selftest  # headless check used by CI; runs before tkinter is imported
    sys.exit(selftest.run(sys.argv[2] if len(sys.argv) > 2 else "selftest.txt"))

import queue
import threading
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import converter

try:  # optional drag & drop support
    from tkinterdnd2 import DND_FILES, TkinterDnD
    BaseTk = TkinterDnD.Tk
    HAS_DND = True
except Exception:  # pragma: no cover
    BaseTk = tk.Tk
    HAS_DND = False

APP_NAME = "MarkItDown GUI"
try:
    from importlib.metadata import version as _v
    MD_VERSION = _v("markitdown")
except Exception:
    MD_VERSION = "?"

STATUS_PENDING, STATUS_WORKING, STATUS_DONE, STATUS_FAILED = "Pending", "Converting…", "Done", "Failed"


def resource_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


class App(BaseTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME}  (markitdown {MD_VERSION})")
        self.geometry("1100x700")
        self.minsize(820, 520)
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass

        self.items: dict[str, dict] = {}   # tree iid -> {"source", "output", "markdown", "error"}
        self.msgs: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.cancel_flag = threading.Event()

        self.out_mode = tk.StringVar(value="beside")      # "beside" | "folder"
        self.out_dir = tk.StringVar(value="")
        self.overwrite = tk.BooleanVar(value=False)
        self.keep_data_uris = tk.BooleanVar(value=False)
        self.enable_plugins = tk.BooleanVar(value=False)
        self.save_files = tk.BooleanVar(value=True)
        self.url_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Add files, a folder, or a URL to get started.")

        self._build_ui()
        self.after(100, self._poll_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        # toolbar
        bar = ttk.Frame(root)
        bar.pack(fill="x")
        ttk.Button(bar, text="Add Files…", command=self.add_files).pack(side="left")
        ttk.Button(bar, text="Add Folder…", command=self.add_folder).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Remove", command=self.remove_selected).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Clear", command=self.clear_all).pack(side="left", padx=(6, 0))
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Label(bar, text="URL:").pack(side="left")
        url_entry = ttk.Entry(bar, textvariable=self.url_var, width=40)
        url_entry.pack(side="left", padx=(4, 4), fill="x", expand=True)
        url_entry.bind("<Return>", lambda e: self.add_url())
        ttk.Button(bar, text="Add URL", command=self.add_url).pack(side="left")

        panes = ttk.PanedWindow(root, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(10, 0))

        # left: file list + options
        left = ttk.Frame(panes)
        panes.add(left, weight=1)

        list_frame = ttk.LabelFrame(left, text="Inputs" + ("  (drag & drop files here)" if HAS_DND else ""))
        list_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(list_frame, columns=("name", "status"), show="headings", selectmode="extended")
        self.tree.heading("name", text="File / URL")
        self.tree.heading("status", text="Status")
        self.tree.column("name", width=300, anchor="w")
        self.tree.column("status", width=90, anchor="center", stretch=False)
        ysb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        ysb.pack(side="right", fill="y", pady=4)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Delete>", lambda e: self.remove_selected())
        self.tree.bind("<Double-1>", lambda e: self.open_output())
        self.tree.tag_configure("failed", foreground="#b00020")
        self.tree.tag_configure("done", foreground="#1b7f3a")
        if HAS_DND:
            for w in (self.tree, list_frame):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._on_drop)

        opts = ttk.LabelFrame(left, text="Options")
        opts.pack(fill="x", pady=(8, 0))
        ttk.Checkbutton(opts, text="Save .md files", variable=self.save_files).grid(row=0, column=0, sticky="w", padx=6, pady=2)
        ttk.Radiobutton(opts, text="Next to each source file", value="beside", variable=self.out_mode).grid(row=1, column=0, sticky="w", padx=20)
        rb = ttk.Frame(opts)
        rb.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20)
        ttk.Radiobutton(rb, text="In folder:", value="folder", variable=self.out_mode).pack(side="left")
        ttk.Entry(rb, textvariable=self.out_dir).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(rb, text="Browse…", command=self.choose_out_dir).pack(side="left")
        ttk.Checkbutton(opts, text="Overwrite existing .md files", variable=self.overwrite).grid(row=3, column=0, sticky="w", padx=20, pady=2)
        ttk.Checkbutton(opts, text="Keep embedded images as data URIs", variable=self.keep_data_uris).grid(row=4, column=0, sticky="w", padx=6, pady=2)
        ttk.Checkbutton(opts, text="Enable MarkItDown plugins", variable=self.enable_plugins).grid(row=5, column=0, sticky="w", padx=6, pady=(2, 6))
        opts.columnconfigure(0, weight=1)

        run = ttk.Frame(left)
        run.pack(fill="x", pady=(8, 0))
        self.convert_btn = ttk.Button(run, text="Convert", style="Accent.TButton", command=self.start_conversion)
        self.convert_btn.pack(side="left", fill="x", expand=True, ipady=4)
        self.cancel_btn = ttk.Button(run, text="Cancel", command=self.cancel_flag.set, state="disabled")
        self.cancel_btn.pack(side="left", padx=(6, 0), ipady=4)
        self.progress = ttk.Progressbar(left, mode="determinate")
        self.progress.pack(fill="x", pady=(8, 0))

        # right: preview
        right = ttk.LabelFrame(panes, text="Markdown preview")
        panes.add(right, weight=2)
        pbar = ttk.Frame(right)
        pbar.pack(fill="x", padx=4, pady=4)
        ttk.Button(pbar, text="Copy", command=self.copy_preview).pack(side="left")
        ttk.Button(pbar, text="Save As…", command=self.save_preview_as).pack(side="left", padx=(6, 0))
        ttk.Button(pbar, text="Open Output", command=self.open_output).pack(side="left", padx=(6, 0))
        ttk.Button(pbar, text="Open Folder", command=self.open_output_folder).pack(side="left", padx=(6, 0))
        self.wrap = tk.BooleanVar(value=True)
        ttk.Checkbutton(pbar, text="Wrap", variable=self.wrap,
                        command=lambda: self.preview.configure(wrap="word" if self.wrap.get() else "none")).pack(side="right")
        txt_frame = ttk.Frame(right)
        txt_frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.preview = tk.Text(txt_frame, wrap="word", font=("Consolas", 10), undo=False, relief="flat",
                               borderwidth=1, highlightthickness=1, highlightbackground="#c8c8c8")
        pys = ttk.Scrollbar(txt_frame, orient="vertical", command=self.preview.yview)
        pxs = ttk.Scrollbar(txt_frame, orient="horizontal", command=self.preview.xview)
        self.preview.configure(yscrollcommand=pys.set, xscrollcommand=pxs.set)
        pys.pack(side="right", fill="y")
        pxs.pack(side="bottom", fill="x")
        self.preview.pack(side="left", fill="both", expand=True)

        ttk.Label(root, textvariable=self.status_var, anchor="w").pack(fill="x", pady=(8, 0))

    # ------------------------------------------------------------- inputs
    def _add_source(self, source: str) -> None:
        if any(d["source"] == source for d in self.items.values()):
            return
        display = source if converter.is_url(source) else os.path.basename(source)
        iid = self.tree.insert("", "end", values=(display, STATUS_PENDING))
        self.items[iid] = {"source": source, "output": None, "markdown": None, "error": None}
        self._set_status(f"{len(self.items)} item(s) queued.")

    def add_files(self) -> None:
        exts = " ".join(f"*{e}" for e in sorted(converter.SUPPORTED_EXTS))
        paths = filedialog.askopenfilenames(title="Select files to convert",
                                            filetypes=[("Supported files", exts), ("All files", "*.*")])
        for p in paths:
            self._add_source(os.path.normpath(p))

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select a folder (searched recursively)")
        if not folder:
            return
        files = converter.find_supported_files(folder)
        if not files:
            messagebox.showinfo(APP_NAME, "No supported files found in that folder.")
        for p in files:
            self._add_source(os.path.normpath(p))

    def add_url(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            return
        if not converter.is_url(url):
            messagebox.showwarning(APP_NAME, "Please enter a full http:// or https:// URL.")
            return
        self._add_source(url)
        self.url_var.set("")

    def _on_drop(self, event) -> None:
        for p in self.tk.splitlist(event.data):
            if os.path.isdir(p):
                for f in converter.find_supported_files(p):
                    self._add_source(os.path.normpath(f))
            elif os.path.isfile(p):
                self._add_source(os.path.normpath(p))

    def remove_selected(self) -> None:
        if self._busy():
            return
        for iid in self.tree.selection():
            self.tree.delete(iid)
            self.items.pop(iid, None)
        self._set_status(f"{len(self.items)} item(s) queued.")

    def clear_all(self) -> None:
        if self._busy():
            return
        self.tree.delete(*self.tree.get_children())
        self.items.clear()
        self._show_text("")
        self._set_status("Cleared.")

    def choose_out_dir(self) -> None:
        d = filedialog.askdirectory(title="Choose output folder")
        if d:
            self.out_dir.set(os.path.normpath(d))
            self.out_mode.set("folder")

    # --------------------------------------------------------- conversion
    def _busy(self) -> bool:
        return self.worker is not None and self.worker.is_alive()

    def start_conversion(self) -> None:
        if self._busy():
            return
        todo = [iid for iid in self.tree.get_children() if self.items[iid]["markdown"] is None]
        if not todo:
            todo = list(self.tree.get_children())   # re-run everything
        if not todo:
            messagebox.showinfo(APP_NAME, "Add some files or URLs first.")
            return
        out_dir = None
        if self.save_files.get() and self.out_mode.get() == "folder":
            out_dir = self.out_dir.get().strip()
            if not out_dir:
                messagebox.showwarning(APP_NAME, "Choose an output folder, or select 'Next to each source file'.")
                return
            os.makedirs(out_dir, exist_ok=True)

        jobs = [(iid, self.items[iid]["source"]) for iid in todo]
        for iid, _ in jobs:
            self.tree.set(iid, "status", STATUS_PENDING)
            self.tree.item(iid, tags=())
        opts = dict(out_dir=out_dir, save=self.save_files.get(), overwrite=self.overwrite.get(),
                    keep_data_uris=self.keep_data_uris.get(), plugins=self.enable_plugins.get())
        self.cancel_flag.clear()
        self.progress.configure(maximum=len(jobs), value=0)
        self.convert_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self._set_status("Loading MarkItDown…")
        self.worker = threading.Thread(target=self._run_jobs, args=(jobs, opts), daemon=True)
        self.worker.start()

    def _run_jobs(self, jobs, opts) -> None:
        ok = failed = 0
        try:
            md = converter.make_converter(enable_plugins=opts["plugins"])
        except Exception as e:
            self.msgs.put(("fatal", f"Could not initialise MarkItDown:\n{e}"))
            return
        for i, (iid, source) in enumerate(jobs, 1):
            if self.cancel_flag.is_set():
                break
            self.msgs.put(("status", iid, STATUS_WORKING, f"[{i}/{len(jobs)}] Converting {source}"))
            try:
                text = converter.convert_source(md, source, keep_data_uris=opts["keep_data_uris"])
                out = None
                if opts["save"]:
                    out = converter.output_path_for(source, opts["out_dir"], opts["overwrite"])
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(text, encoding="utf-8")
                self.msgs.put(("done", iid, text, str(out) if out else None))
                ok += 1
            except Exception as e:
                detail = f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"
                self.msgs.put(("failed", iid, detail))
                failed += 1
            self.msgs.put(("progress", i))
        self.msgs.put(("finished", ok, failed, self.cancel_flag.is_set()))

    def _poll_queue(self) -> None:
        try:
            while True:
                msg = self.msgs.get_nowait()
                kind = msg[0]
                if kind == "status":
                    _, iid, st, text = msg
                    self.tree.set(iid, "status", st)
                    self._set_status(text)
                elif kind == "done":
                    _, iid, text, out = msg
                    self.items[iid].update(markdown=text, output=out, error=None)
                    self.tree.set(iid, "status", STATUS_DONE)
                    self.tree.item(iid, tags=("done",))
                    if not self.tree.selection() or self.tree.selection() == (iid,):
                        self.tree.selection_set(iid)
                        self.tree.see(iid)
                        self._show_text(text)
                elif kind == "failed":
                    _, iid, detail = msg
                    self.items[iid].update(markdown=None, error=detail)
                    self.tree.set(iid, "status", STATUS_FAILED)
                    self.tree.item(iid, tags=("failed",))
                elif kind == "progress":
                    self.progress.configure(value=msg[1])
                elif kind == "finished":
                    _, ok, failed, cancelled = msg
                    self._finish(f"{'Cancelled. ' if cancelled else ''}Converted {ok}, failed {failed}."
                                 + ("  Select a failed item to see the error." if failed else ""))
                elif kind == "fatal":
                    self._finish("Error.")
                    messagebox.showerror(APP_NAME, msg[1])
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _finish(self, text: str) -> None:
        self.convert_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self._set_status(text)

    # ------------------------------------------------------------ preview
    def _selected(self) -> dict | None:
        sel = self.tree.selection()
        return self.items.get(sel[0]) if sel else None

    def _on_select(self, _event=None) -> None:
        item = self._selected()
        if not item:
            return
        if item["markdown"] is not None:
            self._show_text(item["markdown"])
            self._set_status(f"Saved to: {item['output']}" if item["output"] else "Converted (not saved to disk).")
        elif item["error"]:
            self._show_text("Conversion failed:\n\n" + item["error"])
        else:
            self._show_text("")

    def _show_text(self, text: str) -> None:
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)

    def copy_preview(self) -> None:
        text = self.preview.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status(f"Copied {len(text):,} characters to clipboard.")

    def save_preview_as(self) -> None:
        text = self.preview.get("1.0", "end-1c")
        if not text:
            return
        item = self._selected()
        initial = Path(item["output"]).name if item and item["output"] else "document.md"
        path = filedialog.asksaveasfilename(defaultextension=".md", initialfile=initial,
                                            filetypes=[("Markdown", "*.md"), ("Text", "*.txt"), ("All files", "*.*")])
        if path:
            Path(path).write_text(text, encoding="utf-8")
            self._set_status(f"Saved {path}")

    def open_output(self) -> None:
        item = self._selected()
        if item and item["output"] and os.path.exists(item["output"]):
            _open_path(item["output"])

    def open_output_folder(self) -> None:
        item = self._selected()
        if item and item["output"]:
            _open_path(os.path.dirname(item["output"]))
        elif self.out_mode.get() == "folder" and os.path.isdir(self.out_dir.get()):
            _open_path(self.out_dir.get())

    # -------------------------------------------------------------- misc
    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _on_close(self) -> None:
        if self._busy() and not messagebox.askyesno(APP_NAME, "A conversion is running. Quit anyway?"):
            return
        self.cancel_flag.set()
        self.destroy()


def _open_path(path: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        os.system(f'open "{path}"')
    else:
        os.system(f'xdg-open "{path}"')


def main() -> None:
    if sys.platform.startswith("win"):
        try:  # crisp text on high-DPI screens
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = App()
    for arg in sys.argv[1:]:   # supports "Open with…" / dragging files onto the .exe
        if os.path.isdir(arg):
            for f in converter.find_supported_files(arg):
                app._add_source(os.path.normpath(f))
        elif os.path.isfile(arg) or converter.is_url(arg):
            app._add_source(arg if converter.is_url(arg) else os.path.normpath(arg))
    app.mainloop()


if __name__ == "__main__":
    main()
