from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path
from tkinter import StringVar, Text, Tk, filedialog, messagebox
from tkinter import ttk
from typing import Any, Callable

from . import __version__
from .desktop_core import DesktopCommandResult, capture_repository, load_dashboard, run_safe_demo


BACKGROUND = "#111418"
SURFACE = "#181d22"
SURFACE_ALT = "#20262d"
BORDER = "#343c45"
TEXT = "#eef2f5"
MUTED = "#9ba7b3"
ACCENT = "#46b981"
WARNING = "#e4b44c"
BLOCK = "#e26767"


class AgentLedgerDesktop:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title(f"AgentLedger {__version__}")
        self.root.geometry("1120x760")
        self.root.minsize(900, 620)
        self.root.configure(background=BACKGROUND)
        self.busy = False
        self.latest_paths: dict[str, str | None] = {}
        self.history_paths: dict[str, str] = {}

        self.repo_var = StringVar(value=str(Path.cwd()))
        self.out_var = StringVar(value="")
        self.status_var = StringVar(value="UNKNOWN")
        self.summary_var = StringVar(value="No AgentLedger run loaded")
        self.chain_var = StringVar(value="unavailable")
        self.latest_var = StringVar(value="No run")
        self.feedback_var = StringVar(value="0 notes")
        self.command_var = StringVar(value="git status --short")
        self.privacy_var = StringVar(value="summary")
        self.zip_var = StringVar(value="1")
        self.repomori_var = StringVar(value="0")
        self.jester_var = StringVar(value="0")
        self.tokometer_var = StringVar(value="0")
        self.footer_var = StringVar(value="Ready")

        self._configure_style()
        self._build_ui()
        self.root.after(150, self.refresh)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=BACKGROUND, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=BACKGROUND)
        style.configure("Surface.TFrame", background=SURFACE)
        style.configure("Header.TFrame", background=SURFACE_ALT)
        style.configure("TLabel", background=BACKGROUND, foreground=TEXT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Header.TLabel", background=SURFACE_ALT, foreground=TEXT)
        style.configure("Title.TLabel", background=SURFACE_ALT, foreground=TEXT, font=("Segoe UI Semibold", 18))
        style.configure("Metric.TLabel", background=SURFACE, foreground=TEXT, font=("Segoe UI Semibold", 12))
        style.configure("MetricName.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("TButton", background=SURFACE_ALT, foreground=TEXT, bordercolor=BORDER, padding=(12, 7))
        style.map("TButton", background=[("active", BORDER), ("disabled", SURFACE)])
        style.configure("Accent.TButton", background=ACCENT, foreground="#07130e", bordercolor=ACCENT)
        style.map("Accent.TButton", background=[("active", "#5bc991"), ("disabled", BORDER)])
        style.configure("TEntry", fieldbackground=SURFACE_ALT, foreground=TEXT, insertcolor=TEXT, bordercolor=BORDER)
        style.configure("TCombobox", fieldbackground=SURFACE_ALT, foreground=TEXT, arrowcolor=TEXT)
        style.map("TCombobox", fieldbackground=[("readonly", SURFACE_ALT)], foreground=[("readonly", TEXT)])
        style.configure("TCheckbutton", background=BACKGROUND, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", BACKGROUND)])
        style.configure("TNotebook", background=BACKGROUND, borderwidth=0)
        style.configure("TNotebook.Tab", background=SURFACE_ALT, foreground=MUTED, padding=(16, 8))
        style.map("TNotebook.Tab", background=[("selected", SURFACE)], foreground=[("selected", TEXT)])
        style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT, rowheight=28, borderwidth=0)
        style.configure("Treeview.Heading", background=SURFACE_ALT, foreground=TEXT, relief="flat")
        style.map("Treeview", background=[("selected", "#245b48")])
        style.configure("TSeparator", background=BORDER)

    def _build_ui(self) -> None:
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(22, 14))
        header.pack(fill="x")
        ttk.Label(header, text="AgentLedger", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text=f"Desktop alpha  |  {__version__}", style="Header.TLabel").pack(side="left", padx=(14, 0))
        self.demo_button = ttk.Button(header, text="Safe demo", command=self.run_demo)
        self.demo_button.pack(side="right")
        self.refresh_button = ttk.Button(header, text="Refresh", style="Accent.TButton", command=self.refresh)
        self.refresh_button.pack(side="right", padx=(0, 8))

        repo_bar = ttk.Frame(self.root, padding=(22, 14))
        repo_bar.pack(fill="x")
        ttk.Label(repo_bar, text="Repository", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(repo_bar, textvariable=self.repo_var).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(repo_bar, text="Browse", command=self.browse_repo).grid(row=1, column=1, padx=(8, 0), pady=(4, 0))
        ttk.Label(repo_bar, text="Evidence output (optional)", style="Muted.TLabel").grid(row=0, column=2, sticky="w", padx=(18, 0))
        ttk.Entry(repo_bar, textvariable=self.out_var, width=34).grid(row=1, column=2, sticky="ew", padx=(18, 0), pady=(4, 0))
        ttk.Button(repo_bar, text="Browse", command=self.browse_out).grid(row=1, column=3, padx=(8, 0), pady=(4, 0))
        repo_bar.columnconfigure(0, weight=3)
        repo_bar.columnconfigure(2, weight=2)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=22, pady=(0, 14))
        self.overview_tab = ttk.Frame(self.notebook, style="Surface.TFrame", padding=18)
        self.capture_tab = ttk.Frame(self.notebook, style="Surface.TFrame", padding=18)
        self.history_tab = ttk.Frame(self.notebook, style="Surface.TFrame", padding=0)
        self.activity_tab = ttk.Frame(self.notebook, style="Surface.TFrame", padding=0)
        self.notebook.add(self.overview_tab, text="Overview")
        self.notebook.add(self.capture_tab, text="Capture")
        self.notebook.add(self.history_tab, text="History")
        self.notebook.add(self.activity_tab, text="Activity")

        self._build_overview()
        self._build_capture()
        self._build_history()
        self._build_activity()

        footer = ttk.Frame(self.root, style="Header.TFrame", padding=(22, 7))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.footer_var, style="Header.TLabel").pack(side="left")
        ttk.Label(footer, text="Evidence stays local by default", style="Header.TLabel").pack(side="right")

    def _build_overview(self) -> None:
        metrics = ttk.Frame(self.overview_tab, style="Surface.TFrame")
        metrics.pack(fill="x")
        for index, (name, variable) in enumerate(
            (
                ("POLICY STATUS", self.status_var),
                ("HISTORY INTEGRITY", self.chain_var),
                ("LATEST RUN", self.latest_var),
                ("LOCAL FEEDBACK", self.feedback_var),
            )
        ):
            group = ttk.Frame(metrics, style="Surface.TFrame", padding=(0, 4, 20, 14))
            group.grid(row=0, column=index, sticky="nsew")
            ttk.Label(group, text=name, style="MetricName.TLabel").pack(anchor="w")
            ttk.Label(group, textvariable=variable, style="Metric.TLabel", wraplength=230).pack(anchor="w", pady=(5, 0))
            metrics.columnconfigure(index, weight=1)

        ttk.Separator(self.overview_tab).pack(fill="x", pady=(4, 16))
        ttk.Label(self.overview_tab, text="Latest verdict", style="MetricName.TLabel").pack(anchor="w")
        ttk.Label(self.overview_tab, textvariable=self.summary_var, style="Metric.TLabel", wraplength=900).pack(anchor="w", pady=(6, 18))

        actions = ttk.Frame(self.overview_tab, style="Surface.TFrame")
        actions.pack(fill="x", pady=(0, 18))
        self.open_report_button = ttk.Button(actions, text="Open Markdown report", command=self.open_latest_report)
        self.open_report_button.pack(side="left")
        self.open_folder_button = ttk.Button(actions, text="Open evidence folder", command=self.open_evidence_folder)
        self.open_folder_button.pack(side="left", padx=(8, 0))
        self.verify_button = ttk.Button(actions, text="Verify chain", command=self.verify_chain)
        self.verify_button.pack(side="left", padx=(8, 0))

        ttk.Label(self.overview_tab, text="Next actions", style="MetricName.TLabel").pack(anchor="w")
        self.actions_text = Text(
            self.overview_tab,
            height=10,
            background=SURFACE,
            foreground=TEXT,
            insertbackground=TEXT,
            selectbackground="#245b48",
            relief="flat",
            wrap="word",
            font=("Segoe UI", 10),
            padx=0,
            pady=8,
        )
        self.actions_text.pack(fill="both", expand=True)
        self.actions_text.configure(state="disabled")

    def _build_capture(self) -> None:
        ttk.Label(self.capture_tab, text="Command", style="MetricName.TLabel").grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Entry(self.capture_tab, textvariable=self.command_var).grid(row=1, column=0, columnspan=4, sticky="ew", pady=(5, 18))
        ttk.Label(self.capture_tab, text="Privacy", style="MetricName.TLabel").grid(row=2, column=0, sticky="w")
        privacy = ttk.Combobox(self.capture_tab, textvariable=self.privacy_var, values=("summary", "standard"), state="readonly", width=16)
        privacy.grid(row=3, column=0, sticky="w", pady=(5, 18))

        ttk.Checkbutton(self.capture_tab, text="Zip bundle", variable=self.zip_var, onvalue="1", offvalue="0").grid(row=3, column=1, sticky="w")
        ttk.Checkbutton(self.capture_tab, text="RepoMori", variable=self.repomori_var, onvalue="1", offvalue="0").grid(row=3, column=2, sticky="w")
        ttk.Checkbutton(self.capture_tab, text="Jester", variable=self.jester_var, onvalue="1", offvalue="0").grid(row=4, column=1, sticky="w")
        ttk.Checkbutton(self.capture_tab, text="Tokometer", variable=self.tokometer_var, onvalue="1", offvalue="0").grid(row=4, column=2, sticky="w")

        self.capture_button = ttk.Button(self.capture_tab, text="Run and capture", style="Accent.TButton", command=self.capture)
        self.capture_button.grid(row=5, column=0, sticky="w", pady=(26, 0))
        ttk.Button(self.capture_tab, text="Open latest after capture", command=self.open_latest_report).grid(row=5, column=1, sticky="w", pady=(26, 0), padx=(8, 0))
        self.capture_tab.columnconfigure(0, weight=1)
        self.capture_tab.columnconfigure(1, weight=1)
        self.capture_tab.columnconfigure(2, weight=1)
        self.capture_tab.columnconfigure(3, weight=1)

    def _build_history(self) -> None:
        columns = ("started", "integrity", "exit", "changed", "test", "command")
        self.history_tree = ttk.Treeview(self.history_tab, columns=columns, show="headings", selectmode="browse")
        headings = {
            "started": "Started",
            "integrity": "Integrity",
            "exit": "Exit",
            "changed": "Changed",
            "test": "Test",
            "command": "Command",
        }
        widths = {"started": 170, "integrity": 90, "exit": 55, "changed": 75, "test": 110, "command": 480}
        for column in columns:
            self.history_tree.heading(column, text=headings[column])
            self.history_tree.column(column, width=widths[column], minwidth=50, stretch=column == "command")
        scrollbar = ttk.Scrollbar(self.history_tab, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        self.history_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.history_tree.bind("<Double-1>", lambda _event: self.open_selected_history())

    def _build_activity(self) -> None:
        self.activity_text = Text(
            self.activity_tab,
            background="#0d1013",
            foreground="#d9e1e7",
            insertbackground=TEXT,
            selectbackground="#245b48",
            relief="flat",
            wrap="word",
            font=("Cascadia Mono", 9),
            padx=14,
            pady=12,
        )
        self.activity_text.pack(fill="both", expand=True)
        self.activity_text.configure(state="disabled")

    def _repo(self) -> Path:
        return Path(self.repo_var.get()).expanduser().resolve()

    def _out(self) -> Path | None:
        value = self.out_var.get().strip()
        return Path(value).expanduser().resolve() if value else None

    def browse_repo(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.repo_var.get(), title="Select Git repository")
        if selected:
            self.repo_var.set(selected)
            self.refresh()

    def browse_out(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.repo_var.get(), title="Select evidence output")
        if selected:
            self.out_var.set(selected)
            self.refresh()

    def refresh(self) -> None:
        repo = self._repo()
        out = self._out()
        self._start_task("Refreshing dashboard", lambda: load_dashboard(repo, out=out), self._apply_dashboard)

    def capture(self) -> None:
        repo = self._repo()
        if not repo.is_dir():
            messagebox.showerror("AgentLedger", f"Repository directory not found:\n{repo}")
            return
        command = self.command_var.get()
        self._start_task(
            "Capturing repository command",
            lambda: capture_repository(
                repo,
                command,
                out=self._out(),
                privacy_mode=self.privacy_var.get(),
                zip_bundle=self.zip_var.get() == "1",
                repomori=self.repomori_var.get() == "1",
                jester=self.jester_var.get() == "1",
                tokometer=self.tokometer_var.get() == "1",
            ),
            self._capture_complete,
        )

    def run_demo(self) -> None:
        self._start_task("Running safe demo", run_safe_demo, self._demo_complete)

    def verify_chain(self) -> None:
        repo = self._repo()
        out = self._out()

        def command() -> DesktopCommandResult:
            from .desktop_core import invoke_cli

            arguments = ["verify-chain", "--repo", str(repo)]
            if out is not None:
                arguments.extend(["--out", str(out)])
            return invoke_cli(arguments)

        self._start_task("Verifying report chain", command, self._command_complete)

    def _start_task(self, label: str, operation: Callable[[], Any], callback: Callable[[Any], None]) -> None:
        if self.busy:
            return
        self.busy = True
        self.footer_var.set(label + "...")
        self._set_buttons_enabled(False)

        def worker() -> None:
            try:
                result = operation()
            except Exception as exc:  # pragma: no cover - GUI boundary
                self.root.after(0, lambda: self._task_failed(exc))
                return
            self.root.after(0, lambda: self._task_finished(result, callback))

        threading.Thread(target=worker, daemon=True).start()

    def _task_finished(self, result: Any, callback: Callable[[Any], None]) -> None:
        self.busy = False
        self._set_buttons_enabled(True)
        callback(result)

    def _task_failed(self, exc: Exception) -> None:
        self.busy = False
        self._set_buttons_enabled(True)
        self.footer_var.set("Operation failed")
        self._append_activity(f"ERROR\n{exc}\n")
        messagebox.showerror("AgentLedger", str(exc))

    def _set_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in (self.refresh_button, self.demo_button, self.capture_button):
            button.configure(state=state)

    def _apply_dashboard(self, dashboard: dict[str, Any]) -> None:
        payload = dashboard["status"]
        status = str(payload.get("status") or "unknown")
        check = payload.get("check") or {}
        chain = payload.get("history_integrity") or {}
        feedback = payload.get("feedback") or {}
        self.status_var.set(status.upper())
        self.summary_var.set(str(check.get("summary") or "; ".join(payload.get("errors") or []) or "No run available"))
        self.chain_var.set(str(chain.get("status") or "unavailable"))
        latest = payload.get("latest_run")
        self.latest_var.set(Path(str(latest)).name if latest else "No run")
        self.feedback_var.set(f"{feedback.get('total_entries', 0)} notes")
        self.latest_paths = dict(payload.get("paths") or {})
        self._replace_actions(payload.get("next_actions") or payload.get("errors") or ["Run and capture a command."])
        self._replace_history(dashboard.get("history") or [])
        self.footer_var.set(f"{status.upper()}  |  {payload.get('out') or self._out() or self._repo() / '.agentledger'}")
        self._append_result("STATUS", dashboard["status_result"])

    def _replace_actions(self, actions: list[str]) -> None:
        self.actions_text.configure(state="normal")
        self.actions_text.delete("1.0", "end")
        self.actions_text.insert("1.0", "\n".join(f"{index}. {action}" for index, action in enumerate(actions, start=1)))
        self.actions_text.configure(state="disabled")

    def _replace_history(self, runs: list[dict[str, Any]]) -> None:
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        self.history_paths.clear()
        for run in runs:
            run_id = str(run.get("run_id") or "")
            integrity = run.get("integrity") or {}
            self.history_tree.insert(
                "",
                "end",
                iid=run_id,
                values=(
                    run.get("started_at") or "",
                    integrity.get("status") or "legacy",
                    run.get("exit_code") if run.get("exit_code") is not None else "n/a",
                    run.get("changed_files", 0),
                    run.get("test_framework") or "n/a",
                    run.get("command") or "snapshot",
                ),
            )
            markdown = run.get("markdown")
            if markdown:
                self.history_paths[run_id] = str(markdown)

    def _capture_complete(self, result: DesktopCommandResult) -> None:
        self._append_result("CAPTURE", result)
        self.footer_var.set(f"Capture finished with exit code {result.exit_code}")
        self.notebook.select(self.overview_tab)
        self.refresh()

    def _demo_complete(self, result: DesktopCommandResult) -> None:
        self._append_result("SAFE DEMO", result)
        self.footer_var.set(f"Safe demo finished with exit code {result.exit_code}")
        payload = result.payload or {}
        paths = payload.get("paths") or {}
        markdown = paths.get("markdown")
        if result.exit_code == 0 and markdown and messagebox.askyesno("AgentLedger", "Safe demo complete. Open the Markdown report?"):
            self._open_path(str(markdown))

    def _command_complete(self, result: DesktopCommandResult) -> None:
        self._append_result("VERIFY CHAIN", result)
        self.footer_var.set(f"Verification finished with exit code {result.exit_code}")
        self.notebook.select(self.activity_tab)
        self.refresh()

    def _append_result(self, title: str, result: DesktopCommandResult) -> None:
        body = result.output or f"Exit code: {result.exit_code}"
        self._append_activity(f"{title} (exit {result.exit_code})\n{body}\n")

    def _append_activity(self, text: str) -> None:
        self.activity_text.configure(state="normal")
        if self.activity_text.index("end-1c") != "1.0":
            self.activity_text.insert("end", "\n")
        self.activity_text.insert("end", text.rstrip() + "\n")
        self.activity_text.see("end")
        self.activity_text.configure(state="disabled")

    def open_latest_report(self) -> None:
        path = self.latest_paths.get("markdown")
        if path:
            self._open_path(path)
        else:
            messagebox.showinfo("AgentLedger", "No Markdown report is available yet.")

    def open_evidence_folder(self) -> None:
        latest = self.latest_var.get()
        path = self.latest_paths.get("json")
        if path:
            self._open_path(str(Path(path).parent))
        elif latest != "No run":
            self._open_path(str(self._out() or self._repo() / ".agentledger"))
        else:
            messagebox.showinfo("AgentLedger", "No evidence folder is available yet.")

    def open_selected_history(self) -> None:
        selection = self.history_tree.selection()
        if not selection:
            return
        path = self.history_paths.get(selection[0])
        if path:
            self._open_path(path)

    def _open_path(self, value: str) -> None:
        path = Path(value)
        if not path.exists():
            messagebox.showerror("AgentLedger", f"Path not found:\n{path}")
            return
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            webbrowser.open(path.resolve().as_uri())


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--version"]:
        print(f"AgentLedger Desktop {__version__}")
        return 0

    smoke_test = args == ["--smoke-test"]
    if args and not smoke_test:
        print("usage: agentledger-desktop [--version | --smoke-test]", file=sys.stderr)
        return 2

    root = Tk()
    AgentLedgerDesktop(root)
    if smoke_test:
        root.withdraw()
        root.update_idletasks()
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
