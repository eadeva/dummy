import inspect
import json as json_module
import logging
import os
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import colorlog


# print(f"RBLogger loaded as: {__name__}, id={id(sys.modules[__name__])}")
class OriginalCallerFilter(logging.Filter):
    def filter(self, record):
        frame = inspect.currentframe()
        while frame:
            if (
                frame.f_globals['__name__'] != __name__
                and frame.f_globals['__name__'] != 'logging'
            ):
                record.module = frame.f_globals['__name__']
                record.funcName = frame.f_code.co_name
                break
            frame = frame.f_back
        return True


class VariantAliasFilter(logging.Filter):
    """Add XC_CE_UTILS_VARIANT_ALIAS to log records with proper formatting."""

    def filter(self, record):
        # Read environment variable each time to catch updates
        variant_alias = os.environ.get('XC_CE_UTILS_VARIANT_ALIAS', '')
        # Format with dashes if variant is set, otherwise empty string
        if variant_alias:
            record.variant_alias = f' - {variant_alias} - '
        else:
            record.variant_alias = ' - '
        return True


class TraceIdFilter(logging.Filter):
    """Inject a correlation "trace ID" into each log record.

    A trace ID is a short string identifying one logical execution slice
    (typically one action + variant pair) so log lines from parallel or
    nested executions can be correlated.

    Resolution order (first non-empty wins):
      1. Thread-local value set via ``RBLogger.set_trace_id`` or
         ``RBLogger.trace_context``.
      2. ``XC_CE_UTILS_TRACE_ID`` environment variable. The env var is the
         transport across subprocess boundaries (e.g. the variant pool spawns
         one subprocess per variant).

    When no trace ID is active the ``trace_id_prefix`` record attribute is
    an empty string, keeping the log format byte-identical to the legacy
    output.
    """

    def __init__(self):
        super().__init__()
        self._local = threading.local()

    # --- thread-local storage --------------------------------------------------
    def set(self, trace_id):
        self._local.trace_id = trace_id or None

    def clear(self):
        if hasattr(self._local, 'trace_id'):
            self._local.trace_id = None

    def get(self):
        tid = getattr(self._local, 'trace_id', None)
        if tid:
            return tid
        env_tid = os.environ.get('XC_CE_UTILS_TRACE_ID', '').strip()
        return env_tid or None

    # --- logging.Filter contract -----------------------------------------------
    def filter(self, record):
        tid = self.get()
        record.trace_id = tid or ''
        record.trace_id_prefix = f'[{tid}] ' if tid else ''
        return True


class ThreadAffinityFilter(logging.Filter):
    """Only allow log records emitted from the thread that created the filter."""

    def __init__(self):
        super().__init__()
        self._owner_thread = threading.get_ident()

    def filter(self, record):
        return record.thread == self._owner_thread


class ContextFilter(logging.Filter):
    """Add context stack prefixes (e.g., [SET:flash][STEP:t32_connect]) to log records."""

    def __init__(self):
        super().__init__()
        self._context_stack = threading.local()

    def filter(self, record):
        stack = getattr(self._context_stack, 'stack', [])
        if stack:
            prefix = ''.join(f'[{label}:{name}]' for label, name in stack)
            record.context_prefix = f'{prefix} '
        else:
            record.context_prefix = ''
        return True

    def push(self, label, name):
        if not hasattr(self._context_stack, 'stack'):
            self._context_stack.stack = []
        self._context_stack.stack.append((label, name))

    def pop(self):
        stack = getattr(self._context_stack, 'stack', [])
        if stack:
            stack.pop()


class StepFilter(logging.Filter):
    """Attach the current step name (thread-local stack) to log records.

    Used by ``JsonFormatter`` to emit a ``step`` field so log entries can
    be correlated to the producing pipeline step without parsing message
    text. The stack is managed via :meth:`RBLogger.step_scope`.
    """

    def __init__(self):
        super().__init__()
        self._stack = threading.local()

    def filter(self, record):
        stack = getattr(self._stack, 'stack', [])
        record.step = stack[-1] if stack else ''
        return True

    def push(self, name):
        if not hasattr(self._stack, 'stack'):
            self._stack.stack = []
        self._stack.stack.append(name)

    def pop(self):
        stack = getattr(self._stack, 'stack', [])
        if stack:
            stack.pop()


class JsonFormatter(logging.Formatter):
    """JSON-line formatter for CI/machine-parseable log output."""

    def format(self, record):
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'module': record.module,
            'function': record.funcName,
            'message': record.getMessage(),
        }
        variant = getattr(record, 'variant_alias', '').strip(' -')
        if variant:
            log_entry['variant'] = variant
        action = getattr(record, 'trace_id', '')
        if action:
            log_entry['action'] = action
        step = getattr(record, 'step', '')
        if step:
            log_entry['step'] = step
        context = getattr(record, 'context_prefix', '').strip()
        if context:
            log_entry['context'] = context
        return json_module.dumps(log_entry, ensure_ascii=False)


class RBLogger:
    TRACE_LEVEL_NUM = 5
    NOTE_LEVEL_NUM = 22
    PROGRESS_LEVEL_NUM = 25
    SUCCESS_LEVEL_NUM = 28
    PHASE_LEVEL_NUM = 29

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(RBLogger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self, name='rb_logger', logging_level_console=None, log_legend=False
    ):
        """
        Initialize the RBLogger with the given name and level.

        Args:
            name (str): The name of the logger.
            logging_level_console (int): The logging level for the console.
            log_legend (bool): Whether to print logger info on initialization.
        """
        # Skip initialization if already done
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._initialized = True

        # Always use the same logger name to prevent multiple logger instances
        # This ensures only one logger with one set of handlers is created
        self.logger = colorlog.getLogger('rb_logger')

        # Prevent propagation to root logger to avoid duplicate messages
        self.logger.propagate = False

        # Set base logger level to DEBUG to allow all messages to handlers
        self.logger.setLevel(logging.DEBUG)

        # Allow override via environment variable
        if logging_level_console is None:
            level_name = os.environ.get('LOG_LEVEL', 'INFO')
            logging_level_console = getattr(logging, level_name, logging.INFO)

        self.line_length = int(os.environ.get('LOG_LINE_LENGTH', '100'))

        # Debug: Print logger information
        # print(f"DEBUG: RBLogger init - Logger name: {self.logger.name}, Handlers: {len(self.logger.handlers)}")
        # print(f"DEBUG: Root logger handlers: {len(logging.getLogger().handlers)}")

        # Check for existing handlers to prevent duplication
        if not self.logger.handlers:
            # Console handler
            self.console_handler = colorlog.StreamHandler()
            self.console_handler.setLevel(logging_level_console)
            # Use dynamic variant_alias placeholder that will be filled by VariantAliasFilter
            # The filter adds the variant_alias attribute to each log record
            # trace_id is intentionally not rendered on the console: it
            # already encodes the action+variant pair which would duplicate
            # the variant alias shown by VariantAliasFilter. The trace_id
            # is still emitted to the JSON file log by JsonFormatter for
            # cross-process correlation.
            console_formatter = colorlog.ColoredFormatter(
                '%(log_color)s%(levelname)-8s%(variant_alias)s%(context_prefix)s%(message)s%(reset)s',
                datefmt=None,
                reset=True,
                log_colors={
                    'TRACE': 'purple',
                    'DEBUG': 'bold_purple',
                    'INFO': 'white',
                    'NOTE': 'cyan',
                    'PROGRESS': 'bold_cyan',
                    'SUCCESS': 'bold_green',
                    'WARNING': 'bold_yellow',
                    'ERROR': 'bold_red',
                    'CRITICAL': 'bg_red,bold_white',
                    'PHASE': 'bold_blue',
                },
            )
            self.console_handler.setFormatter(console_formatter)
            self.logger.addHandler(self.console_handler)

            # Add custom filters
            self.logger.addFilter(OriginalCallerFilter())
            self.logger.addFilter(VariantAliasFilter())
            self._trace_id_filter = TraceIdFilter()
            self.logger.addFilter(self._trace_id_filter)
            self._context_filter = ContextFilter()
            self.logger.addFilter(self._context_filter)
            self._step_filter = StepFilter()
            self.logger.addFilter(self._step_filter)

            # Define custom log levels (only need to do this once)
            logging.addLevelName(self.TRACE_LEVEL_NUM, 'TRACE')
            logging.addLevelName(self.NOTE_LEVEL_NUM, 'NOTE')
            logging.addLevelName(self.PROGRESS_LEVEL_NUM, 'PROGRESS')
            logging.addLevelName(self.SUCCESS_LEVEL_NUM, 'SUCCESS')
            logging.addLevelName(self.PHASE_LEVEL_NUM, 'PHASE')

            # Add custom log level methods to the logger
            logging.Logger.trace = self.trace
            logging.Logger.note = self.note
            logging.Logger.progress = self.progress
            logging.Logger.success = self.success
            logging.Logger.phase = self.phase
        else:
            # If handlers exist, just store a reference to the first handler as console_handler
            for handler in self.logger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    self.console_handler = handler
                    break
            else:
                # If no StreamHandler found, create one
                self.console_handler = colorlog.StreamHandler()
                self.console_handler.setLevel(logging_level_console)
                self.logger.addHandler(self.console_handler)

        # Initialize file_handlers dictionary (guarded by _file_lock for thread safety)
        self.file_handlers = {}
        self._file_lock = threading.Lock()

        # Initialize context filter (for nested set/step prefixes)
        self._context_filter = None
        for f in self.logger.filters:
            if isinstance(f, ContextFilter):
                self._context_filter = f
                break

        # Cache reference to trace-ID filter (added during first init).
        # When the logger is re-instantiated the filter already exists on
        # the underlying ``colorlog`` logger — just pick it up.
        self._trace_id_filter = None
        for f in self.logger.filters:
            if isinstance(f, TraceIdFilter):
                self._trace_id_filter = f
                break
        if self._trace_id_filter is None:
            self._trace_id_filter = TraceIdFilter()
            self.logger.addFilter(self._trace_id_filter)

        # Pick up (or create) the step filter for ``step_scope``.
        self._step_filter = None
        for f in self.logger.filters:
            if isinstance(f, StepFilter):
                self._step_filter = f
                break
        if self._step_filter is None:
            self._step_filter = StepFilter()
            self.logger.addFilter(self._step_filter)

        # Check if we should skip phase headers (for PowerShell integration)
        self.skip_phase_headers = (
            os.environ.get('POWERSHELL_LOGGING_ACTIVE', 'false').lower()
            == 'true'
        )

        # Default JSON log file (always on unless explicitly disabled). Each
        # run overwrites the file so a developer always sees the most recent
        # invocation alone — no historical mixing. Disable with
        # ``XC_CE_UTILS_JSON_LOG=0`` if a tool wants to manage its own JSON
        # destination via ``add_json_file_logger``.
        #
        # Subprocesses spawned by the build (e.g. PyInstaller analysis runs
        # that re-import xc_ce_utils) inherit ``XC_CE_UTILS_JSON_LOG_INSTALLED``
        # from the parent and MUST NOT re-open the same file — on Windows the
        # parent already holds it open and the unlink/open in the child would
        # raise WinError 32 (sharing violation), spamming stderr.
        json_enabled = os.environ.get(
            'XC_CE_UTILS_JSON_LOG', '1'
        ).strip().lower() not in (
            '0',
            'false',
            'no',
            'off',
        )
        json_already_installed = (
            os.environ.get('XC_CE_UTILS_JSON_LOG_INSTALLED', '0') == '1'
        )
        self._default_json_handler = None
        if json_enabled and not json_already_installed:
            try:
                repo_root = Path(os.environ.get('REPO_PATH') or Path.cwd())
                logs_root = Path(
                    os.environ.get('XC_CE_UTILS_LOGS_DIR')
                    or (repo_root / '_logs')
                )
                default_json_path = Path(
                    os.environ.get('XC_CE_UTILS_JSON_LOG_PATH')
                    or (logs_root / 'xc-ce-utils.jsonl')
                )
                self._install_default_json_handler(default_json_path)
                # Signal child processes to skip re-installing the same handler.
                os.environ['XC_CE_UTILS_JSON_LOG_INSTALLED'] = '1'
            except Exception as exc:  # pragma: no cover - best effort
                # Never let a logging-setup failure crash the application.
                sys.stderr.write(
                    f'[rb_logger] failed to install default JSON log handler: {exc}\n'
                )

        if log_legend and not self.skip_phase_headers:
            self.print_logger_info()

    def _install_default_json_handler(self, log_file: Path) -> None:
        """Attach a JSON-line file handler used for the whole process lifetime.

        Truncates ``log_file`` so each invocation starts fresh \u2014 no append.
        The handler captures all log levels (DEBUG and above) regardless of
        console verbosity so post-mortem inspection always has full detail.
        """
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        if log_file.exists():
            log_file.unlink()
        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(JsonFormatter())
        # NOTE: no ThreadAffinityFilter \u2014 we want every thread / variant in
        # one JSON file so they can be correlated through the trace_id field.
        self.logger.addHandler(handler)
        self._default_json_handler = handler

    def relocate_default_json_log(self, new_path: Path) -> None:
        """Move the default JSON log to *new_path*, preserving all lines written so far.

        Called by the action runner once variant/action are known so the file
        lands in ``_log/<variant>/<action>/xc-ce-utils_full_log.jsonl`` instead
        of the temporary ``_log/xc-ce-utils.jsonl`` created at import time.

        Safe to call repeatedly; subsequent calls with the same path are no-ops.
        """
        if self._default_json_handler is None:
            return  # JSON logging disabled or not installed; nothing to do

        old_path = Path(self._default_json_handler.baseFilename)
        new_path = Path(new_path)
        if old_path == new_path:
            return  # already in the right place

        # Flush and close so Windows releases the file lock before the rename.
        self._default_json_handler.flush()
        self._default_json_handler.close()
        self.logger.removeHandler(self._default_json_handler)
        self._default_json_handler = None

        new_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # atomic rename; overwrites target if it already exists
            old_path.replace(new_path)
        except OSError:
            pass  # best-effort — only pre-action init lines would be lost

        # Re-open in append mode so the relocated lines are preserved.
        handler = logging.FileHandler(new_path, mode='a', encoding='utf-8')
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(JsonFormatter())
        self.logger.addHandler(handler)
        self._default_json_handler = handler
        os.environ['XC_CE_UTILS_JSON_LOG_PATH'] = str(new_path)

    def add_file_logger(
        self,
        logger_name,
        log_file,
        logging_level_file=logging.INFO,
        only_level=False,
    ):
        new_log_file = Path(log_file)

        if new_log_file.exists():
            new_log_file.unlink()

        new_file_handler = logging.FileHandler(new_log_file, encoding='utf-8')
        new_file_handler.setLevel(logging_level_file)
        if only_level:
            new_file_handler.addFilter(
                lambda record: record.levelno == logging_level_file
            )

        # Attach thread-affinity filter so this handler only captures
        # log records from the thread that created it.  This prevents
        # cross-contamination when multiple steps log in parallel.
        new_file_handler.addFilter(ThreadAffinityFilter())

        file_formatter = logging.Formatter(
            '%(asctime)s - %(module)s - %(funcName)s - %(levelname)s - %(trace_id_prefix)s%(message)s'
        )
        new_file_handler.setFormatter(file_formatter)

        # Use a composite key (logger_name + thread id) so that parallel
        # threads can each have their own file handler without collisions.
        key = (logger_name, threading.get_ident())
        with self._file_lock:
            self.logger.addHandler(new_file_handler)
            self.file_handlers[key] = new_file_handler

    def set_logging_level_console(self, level):
        self.console_handler.setLevel(level)

    def set_level(self, level):
        """
        Set the logging level for the console handler.

        Args:
            level: Logging level (can be string like 'DEBUG', 'INFO', 'TRACE' or integer constant)
        """
        if isinstance(level, str):
            # Try standard logging levels first, then fall back to
            # custom levels registered via logging.addLevelName().
            numeric = getattr(logging, level.upper(), None)
            if numeric is None:
                numeric = logging.getLevelName(level.upper())
            if not isinstance(numeric, int):
                numeric = logging.INFO
            level = numeric
        self.console_handler.setLevel(level)
        # Ensure the base logger allows messages at this level to pass through
        if level < self.logger.level:
            self.logger.setLevel(level)

    def set_logging_level_file(self, logger_name, level):
        key = (logger_name, threading.get_ident())
        with self._file_lock:
            if key in self.file_handlers:
                self.file_handlers[key].setLevel(level)

    def stop_file_logging(self, logger_name):
        key = (logger_name, threading.get_ident())
        with self._file_lock:
            handler = self.file_handlers.pop(key, None)
            if handler is not None:
                self.logger.removeHandler(handler)
                handler.close()

    def trace(self, message, *args, **kwargs):
        if self.logger.isEnabledFor(self.TRACE_LEVEL_NUM):
            self.logger._log(self.TRACE_LEVEL_NUM, message, args, **kwargs)

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def note(self, message, *args, **kwargs):
        if self.logger.isEnabledFor(self.NOTE_LEVEL_NUM):
            self.logger._log(self.NOTE_LEVEL_NUM, message, args, **kwargs)

    def progress(self, message, *args, **kwargs):
        if self.logger.isEnabledFor(self.PROGRESS_LEVEL_NUM):
            self.logger._log(self.PROGRESS_LEVEL_NUM, message, args, **kwargs)

    def success(self, message, *args, **kwargs):
        if self.logger.isEnabledFor(self.SUCCESS_LEVEL_NUM):
            self.logger._log(self.SUCCESS_LEVEL_NUM, message, args, **kwargs)

    def phase(self, message, *args, **kwargs):
        if self.logger.isEnabledFor(self.PHASE_LEVEL_NUM):
            self.logger._log(self.PHASE_LEVEL_NUM, message, args, **kwargs)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def critical(self, message):
        self.logger.critical(message)

    def fill_line_with_character(self, character, line_length=100):
        self.phase(character * line_length)

    def log_phase_header(self, phase_title):
        """
        Log a message with balanced '#' characters before and after the text.

        Args:
            phase_title (str): The message to log.
            total_length (int): The total length of the log line, including the message and '#' characters.
        """
        message_length = len(phase_title)
        if message_length >= self.line_length:
            self.phase(phase_title)
            return

        padding_length = (self.line_length - message_length) // 2
        padding = '#' * padding_length
        balanced_message = f'{padding} {phase_title} {padding}'

        # If the total length is odd, add one more '#' at the end
        if len(balanced_message) < self.line_length:
            balanced_message += '#'

        self.phase('##')
        self.phase(balanced_message)
        self.phase('##')

    def clear_console(self):
        """Clear the console using ANSI escape sequences (cross-platform)."""
        sys.stdout.write('\033[2J\033[H')
        sys.stdout.flush()

    @contextmanager
    def context(self, label, name):
        """Context manager that adds a prefix to all log messages within the block.

        Usage:
            with logger.context("SET", "flash-verification"):
                with logger.context("STEP", "t32_connect"):
                    logger.info("Connecting...")
                    # → INFO - [SET:flash-verification][STEP:t32_connect] Connecting...
        """
        if self._context_filter is not None:
            self._context_filter.push(label, name)
        try:
            yield
        finally:
            if self._context_filter is not None:
                self._context_filter.pop()

    # ------------------------------------------------------------------
    # Trace-ID helpers
    # ------------------------------------------------------------------
    def set_trace_id(self, trace_id):
        """Set the current thread's trace ID.

        Every subsequent log record emitted from this thread (and any of its
        nested ``logger.context`` blocks) is prefixed with ``[<trace_id>]``.
        Pass ``None`` or an empty string to clear.

        The value is also published to ``XC_CE_UTILS_TRACE_ID`` so that any
        ``subprocess`` / ``multiprocessing`` child started afterwards inherits
        the same ID through the environment.
        """
        if self._trace_id_filter is None:
            return
        if trace_id:
            self._trace_id_filter.set(str(trace_id))
            os.environ['XC_CE_UTILS_TRACE_ID'] = str(trace_id)
        else:
            self._trace_id_filter.clear()
            os.environ.pop('XC_CE_UTILS_TRACE_ID', None)

    def clear_trace_id(self):
        """Clear the current thread's trace ID and the env variable."""
        self.set_trace_id(None)

    def get_trace_id(self):
        """Return the active trace ID (thread-local or env), or ``None``."""
        if self._trace_id_filter is None:
            return None
        return self._trace_id_filter.get()

    @contextmanager
    def trace_context(self, trace_id):
        """Context manager that scopes a trace ID to a block.

        The previous trace ID (and env var) is restored on exit, so nested
        scopes work correctly. Use this around every logical execution
        slice that you want to be able to correlate later.

        Usage:
            with logger.trace_context(f"{action}-{variant_alias}"):
                run_build(...)   # all logs are prefixed with [build-pl9]
        """
        previous = self.get_trace_id()
        self.set_trace_id(trace_id)
        try:
            yield trace_id
        finally:
            self.set_trace_id(previous)

    @contextmanager
    def step_scope(self, step_name):
        """Tag every log record emitted in this block with ``step_name``.

        Pushes ``step_name`` onto a thread-local stack so the JSON file
        formatter can emit a ``step`` field on each record. Nested scopes
        are supported; the outer step is restored on exit.

        Usage:
            with logger.step_scope("pytest-unit"):
                logger.info("running tests")   # JSON: {"step": "pytest-unit", ...}
        """
        if self._step_filter is None:
            yield
            return
        self._step_filter.push(step_name)
        try:
            yield
        finally:
            self._step_filter.pop()

    @contextmanager
    def file_scope(
        self,
        logger_name,
        log_file,
        logging_level_file=logging.INFO,
        only_level=False,
    ):
        """Context manager for scoped file logging.

        Adds a file logger on entry and removes it on exit, ensuring cleanup.

        Usage:
            with logger.file_scope("step_cmake", "logs/cmake.log"):
                logger.info("Building...")  # goes to both console and file
        """
        log_path = Path(log_file)
        json_logger_name = f'{logger_name}__json'
        json_log_file = log_path.with_suffix('.jsonl')

        self.add_file_logger(
            logger_name, log_path, logging_level_file, only_level
        )
        self.add_json_file_logger(
            json_logger_name, json_log_file, logging_level_file=logging.DEBUG
        )
        try:
            yield
        finally:
            self.stop_file_logging(logger_name)
            self.stop_file_logging(json_logger_name)

    def add_json_file_logger(
        self, logger_name, log_file, logging_level_file=logging.INFO
    ):
        """Add a JSON-line file logger for CI/machine-parseable log output.

        Each log entry is a single JSON line with timestamp, level, module,
        function, message, variant, and context fields.
        """
        new_log_file = Path(log_file)
        new_log_file.parent.mkdir(parents=True, exist_ok=True)

        if new_log_file.exists():
            new_log_file.unlink()

        new_file_handler = logging.FileHandler(new_log_file, encoding='utf-8')
        new_file_handler.setLevel(logging_level_file)
        new_file_handler.setFormatter(JsonFormatter())
        new_file_handler.addFilter(ThreadAffinityFilter())

        key = (logger_name, threading.get_ident())
        with self._file_lock:
            self.logger.addHandler(new_file_handler)
            self.file_handlers[key] = new_file_handler

    def print_logger_info(self):
        # self.clear_console()
        self.log_phase_header('LOGGER CONFIGURATION')
        self.trace('This is a trace message')
        self.debug('This is a debug message')
        self.info('This is an info message')
        self.note('This is a note message')
        self.progress('This is a progress message')
        self.success('This is a success message')
        self.phase('This is a script phase message')
        self.warning('This is a warning message')
        self.error('This is an error message')
        self.critical('This is a critical message')
        self.log_phase_header('LOGGER CONFIGURATION - FINISHED')


logger = RBLogger()


def get_logger():
    return logger
