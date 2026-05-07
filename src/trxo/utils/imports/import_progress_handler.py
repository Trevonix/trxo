"""
Import Progress Handler.

A custom Python logging.Handler that intercepts trxo_lib log records
during CLI import operations and renders them to the console in real-time
using Rich — providing users with step-by-step import status without any
changes to the library layer.
"""

import logging
import re
from typing import List, Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text

# ── Pattern matching ──────────────────────────────────────────────────────────

# Individual item success — catches "✔ ...", "Successfully imported X", etc.
_ITEM_SUCCESS_RE = re.compile(
    r"^(?:✔\s*|Successfully\s+(?:imported|processed|updated|created|deleted|upserted|PUT)\s+|"
    r"(?:Created|Updated|Upserted|Deleted|Processed)\s+)"
    r"(?P<item>.+)",
    re.IGNORECASE,
)

# Individual item failure
_ITEM_FAILURE_RE = re.compile(
    r"(?:Failed\s+to\s+(?:import|process|update|create|delete|upsert)\s+|✖\s*)"
    r"(?P<item>.+)",
    re.IGNORECASE,
)

# Soft warnings / skips about a specific item
_ITEM_WARNING_RE = re.compile(
    r"(?:no changes needed for|skipping|missing (?:_id|name|valueBase64))\s+"
    r"(?P<item>.+)",
    re.IGNORECASE,
)

# Generic errors that accompany item failures (should not count as separate items)
_GENERIC_ERROR_RE = re.compile(
    r"^(?:✖\s*)(?:HTTP error|Request error|SSL error|Connect error|Request timeout)",
    re.IGNORECASE,
)

# Very internal / noisy messages the user doesn't need to see
_SUPPRESS_RE = re.compile(
    r"(^Starting import operation"
    r"|Authentication initialized"
    r"|setting up git|Cloning repository|Fetching branch"
    r"|Import operation complete"
    r"|trxo CLI"
    r"|Logging initialized"
    r"|API call"
    r"|Data integrity verified"  # hash check — not useful noise
    r"|\[DEBUG\]"
    r"|Processing \d+ "
    r"|Successfully processed \d+ "
    r"|Failed to process \d+ "
    r"|✔ \d+ "
    r"|No \w+ were processed"
    r"|✔ \S+ imported successfully"
    r"|✖ Failed to import \S+)",
    re.IGNORECASE,
)


class ImportProgressHandler(logging.Handler):
    """
    Scoped Rich logging handler for CLI import operations.

    Lifecycle::

        handler = ImportProgressHandler("scripts", console)
        handler.attach()
        try:
            sdk_call()
        finally:
            handler.detach()
            handler.print_summary()
    """

    _ROOT_LOGGER = "trxo_lib"

    def __init__(self, command_name: str, console: Optional[Console] = None):
        super().__init__(level=logging.INFO)
        self.command_name = command_name
        self.console = console or Console()

        # We'll temporarily silence pre-existing StreamHandlers on trxo_lib
        # while we own the output, to avoid double-printing at WARNING level.
        self._silenced_handlers: List[logging.Handler] = []

        # Rich live display
        self._progress = self._make_progress()
        self._task_id = self._progress.add_task(
            f"[bold cyan]Importing {command_name}[/bold cyan]",
            total=None,  # indeterminate spinner
        )
        self._live = Live(
            self._progress,
            console=self.console,
            refresh_per_second=12,
            transient=False,
        )
        self._live_started = False

    # ── Rich helpers ──────────────────────────────────────────────────────────

    def _make_progress(self) -> Progress:
        return Progress(
            SpinnerColumn(spinner_name="dots2", style="bold cyan"),
            TextColumn("[bold blue]{task.description}"),
            TimeElapsedColumn(),
            console=self.console,
            transient=False,
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def attach(self) -> None:
        """
        Install this handler on the trxo_lib root logger.
        Temporarily silences any StreamHandlers that are already attached
        (the default WARNING-level console handler added by setup_logging).
        """
        lib_logger = logging.getLogger(self._ROOT_LOGGER)

        # Silence StreamHandlers so we own the console exclusively
        for h in list(lib_logger.handlers):
            if isinstance(h, logging.StreamHandler) and not isinstance(
                h, ImportProgressHandler
            ):
                self._silenced_handlers.append(h)
                lib_logger.removeHandler(h)

        lib_logger.addHandler(self)

        # Ensure the logger level lets INFO through
        if lib_logger.level == logging.NOTSET or lib_logger.level > logging.INFO:
            lib_logger.setLevel(logging.INFO)

        self._live.start()
        self._live_started = True

    def detach(self) -> None:
        """
        Remove this handler and restore any previously silenced handlers.
        """
        lib_logger = logging.getLogger(self._ROOT_LOGGER)

        if self in lib_logger.handlers:
            lib_logger.removeHandler(self)

        # Restore the original handlers
        for h in self._silenced_handlers:
            lib_logger.addHandler(h)
        self._silenced_handlers.clear()

        if self._live_started:
            self._live.stop()
            self._live_started = False

    # ── logging.Handler interface ─────────────────────────────────────────────

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._process_record(record.levelno, msg)
        except Exception:
            self.handleError(record)

    # ── Core record classification ────────────────────────────────────────────

    def _process_record(self, level: int, msg: str) -> None:
        """Route a log record to the appropriate Rich renderer."""
        msg = msg.strip()
        if not msg:
            return

        # ── Suppress internal noise ───────────────────────────────────────────
        if _SUPPRESS_RE.search(msg):
            return

        # ── Classify and render ───────────────────────────────────────────────
        if _GENERIC_ERROR_RE.search(msg):
            # Contextual error lines (e.g. HTTP status) that accompany a failure line.
            self._print_stage(msg)

        elif _ITEM_FAILURE_RE.search(msg):
            self._print_item(msg, "error")

        elif level == logging.WARNING or _ITEM_WARNING_RE.search(msg):
            self._print_item(msg, "warning")

        elif _ITEM_SUCCESS_RE.search(msg):
            self._print_item(msg, "success")

        elif level >= logging.ERROR:
            # Errors like transport/API status can accompany a per-item failure line.
            self._print_stage(msg)

        else:
            # Stage message (loading, auth, git, cherry-pick, etc.)
            self._print_stage(msg)

    # ── Rich renderers ────────────────────────────────────────────────────────

    def _print_item(self, msg: str, kind: str) -> None:
        """Permanently print a per-item status line above the live progress bar."""
        ICONS = {
            "success": ("✔", "bold green"),
            "error": ("✖", "bold red"),
            "warning": ("⚠", "bold yellow"),
        }
        icon, style = ICONS[kind]

        # Strip common boilerplate prefixes so lines are concise
        clean = re.sub(
            r"^(?:Successfully\s+(?:imported|processed|updated|created|deleted)\s+"
            r"|Failed\s+to\s+(?:import|process|update|create|delete)\s+"
            r"|✔\s*|✖\s*)",
            "",
            msg,
            flags=re.IGNORECASE,
        ).strip()
        clean = clean[:1].upper() + clean[1:] if clean else msg

        self.console.print(Text(f"  {icon} {clean}", style=style))

    def _print_stage(self, msg: str) -> None:
        """Print a dim stage-level message (file loading, auth, git, etc.)."""
        clean = msg.strip()
        if not clean:
            return
        self.console.print(Text(f"  · {clean}", style="dim"))

