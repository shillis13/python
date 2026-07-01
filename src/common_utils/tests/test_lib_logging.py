#!/usr/bin/env python3
"""
Pytest suite for common_utils.lib_logging (the refactored logging module).

Focus of the refactor (asserted here):
  * NAMED loggers under the "ai" namespace; the root logger is never touched.
  * Color lives in the CONSOLE formatter only (tty-aware) and is NEVER baked
    into the text log_file or json_file output.
  * Idempotent configure_logging() unless force=True (no handler leaks).
  * JSONL output parses cleanly and carries exc info when exc_info=True.
  * Env-var precedence (env sets defaults, explicit kwargs override).
  * Back-compat helpers route through the "ai" logger, files stay ANSI-free.

Import path: the repo's pytest.ini sets ``pythonpath = src`` so
``common_utils`` imports directly. We also insert the src dir onto sys.path
defensively so the file can be run standalone.
"""
from __future__ import annotations

import io
import json
import logging
import os
import sys
from pathlib import Path

import pytest

# --- Import path ------------------------------------------------------------
# .../src/common_utils/tests/test_lib_logging.py  ->  .../src
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from common_utils import lib_logging as L  # noqa: E402

ANSI_INTRO = "\033["  # ESC[ — the start of every ANSI escape sequence


# =============================================================================
# Fixtures — isolate the process-global "ai" logger and env between tests
# =============================================================================

_ENV_KEYS = (
    "AI_LOG_LEVEL",
    "AI_LOG_FILE",
    "AI_LOG_JSON",
    "AI_LOG_CONSOLE",
    "AI_LOG_SESSION",
    "AI_SESSION_DIR",  # neutralize so the auto per-session log never fires
    "NO_COLOR",        # into the REAL session dir during unrelated tests
    "TERM",
)


def _reset_ai_logger():
    """Detach & close every handler on the "ai" logger and reset its state."""
    logger = logging.getLogger(L.ROOT_LOGGER_NAME)
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    # Reset the module-level idempotency guard.
    L._CONFIGURED = False


@pytest.fixture(autouse=True)
def clean_logging(monkeypatch):
    """Every test starts from a pristine "ai" logger with logging env cleared."""
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    _reset_ai_logger()
    yield
    _reset_ai_logger()


class TTYStringIO(io.StringIO):
    """StringIO that claims to be a TTY so color auto-detection turns on."""

    def isatty(self) -> bool:  # noqa: D401
        return True


def _read_bytes(path) -> str:
    return Path(path).read_text(encoding="utf-8")


# =============================================================================
# get_logger — namespacing contract
# =============================================================================

class TestGetLogger:
    def test_explicit_component(self):
        assert L.get_logger("send_prompt", component="prompting").name == "ai.prompting.send_prompt"

    def test_explicit_component_takes_leaf_of_dotted_name(self):
        assert L.get_logger("pkg.send_prompt", component="prompting").name == "ai.prompting.send_prompt"

    def test_dotted_name_preserved_as_component_path(self):
        # First segment is treated as the component; nothing is collapsed.
        assert L.get_logger("cli.claude").name == "ai.cli.claude"
        assert L.get_logger("a.b.mod").name == "ai.a.b.mod"

    def test_bare_name_auto_derives_component_from_caller_dir(self):
        # This test file lives in .../common_utils/tests/, so a bare name gets
        # the caller's directory ("tests") as its component.
        assert L.get_logger("somemod").name == "ai.tests.somemod"

    def test_already_namespaced_preserved(self):
        assert L.get_logger("ai.x").name == "ai.x"

    def test_deep_already_namespaced_preserved(self):
        assert L.get_logger("ai.pkg.sub").name == "ai.pkg.sub"

    def test_none_returns_root(self):
        assert L.get_logger(None).name == "ai"

    def test_empty_string_returns_root(self):
        assert L.get_logger("").name == "ai"

    def test_main_returns_root(self):
        assert L.get_logger("__main__").name == "ai"

    def test_bare_ai_returns_root(self):
        assert L.get_logger("ai").name == "ai"

    def test_returns_logger_instance(self):
        assert isinstance(L.get_logger("foo"), logging.Logger)


# =============================================================================
# coerce_level
# =============================================================================

class TestCoerceLevel:
    def test_upper_name(self):
        assert L.coerce_level("DEBUG") == logging.DEBUG

    def test_lower_name(self):
        assert L.coerce_level("debug") == logging.DEBUG

    def test_mixed_case_name(self):
        assert L.coerce_level("Warning") == logging.WARNING

    def test_int_passthrough(self):
        assert L.coerce_level(logging.ERROR) == logging.ERROR
        assert L.coerce_level(10) == 10

    def test_numeric_string(self):
        assert L.coerce_level("10") == 10

    def test_none_uses_default(self):
        assert L.coerce_level(None) == logging.INFO
        assert L.coerce_level(None, default=logging.WARNING) == logging.WARNING

    def test_unknown_name_falls_back_to_default(self):
        assert L.coerce_level("BOGUS", default=logging.CRITICAL) == logging.CRITICAL

    def test_whitespace_stripped(self):
        assert L.coerce_level("  INFO  ") == logging.INFO


# =============================================================================
# configure_logging — named-logger isolation & idempotency
# =============================================================================

class TestConfigureIsolation:
    def test_root_logger_not_touched(self):
        root_before = list(logging.getLogger().handlers)
        stream = io.StringIO()
        L.configure_logging(stream=stream, force=True)
        assert list(logging.getLogger().handlers) == root_before

    def test_ai_logger_does_not_propagate(self):
        L.configure_logging(stream=io.StringIO(), force=True)
        assert logging.getLogger("ai").propagate is False

    def test_is_configured_flag(self):
        assert L.is_configured() is False
        L.configure_logging(stream=io.StringIO(), force=True)
        assert L.is_configured() is True

    def test_returns_the_ai_logger(self):
        logger = L.configure_logging(stream=io.StringIO(), force=True)
        assert logger is logging.getLogger("ai")

    def test_level_applied(self):
        L.configure_logging(level="DEBUG", stream=io.StringIO(), force=True)
        assert logging.getLogger("ai").level == logging.DEBUG


class TestIdempotency:
    def test_second_call_without_force_keeps_handler_count(self):
        stream = io.StringIO()
        L.configure_logging(stream=stream, force=True)
        n = len(logging.getLogger("ai").handlers)
        # Repeated non-forced calls must not add handlers.
        for _ in range(3):
            L.configure_logging(stream=io.StringIO())
        assert len(logging.getLogger("ai").handlers) == n

    def test_non_forced_still_updates_level(self):
        L.configure_logging(level="INFO", stream=io.StringIO(), force=True)
        L.configure_logging(level="DEBUG", stream=io.StringIO())  # no force
        assert logging.getLogger("ai").level == logging.DEBUG

    def test_force_rebuilds_without_leaking(self, tmp_path):
        logf = tmp_path / "a.log"
        L.configure_logging(stream=io.StringIO(), log_file=logf, force=True)
        n1 = len(logging.getLogger("ai").handlers)
        for _ in range(5):
            L.configure_logging(stream=io.StringIO(), log_file=logf, force=True)
        n2 = len(logging.getLogger("ai").handlers)
        assert n1 == n2  # stable count -> no duplication/leak

    def test_console_can_be_disabled(self):
        logger = L.configure_logging(console=False, force=True)
        # No console handler; a NullHandler floor is acceptable.
        stream_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        assert stream_handlers == []


# =============================================================================
# CRITICAL PROPERTY 1 & 2 — color goes to console, never to files
# =============================================================================

class TestColorPlacement:
    def test_console_gets_ansi_on_tty_with_use_color(self):
        stream = TTYStringIO()
        L.configure_logging(stream=stream, use_color=True, force=True)
        logging.getLogger("ai").warning("hello-console")
        out = stream.getvalue()
        assert "hello-console" in out
        assert ANSI_INTRO in out, "console with use_color=True should carry ANSI"

    def test_console_no_ansi_when_use_color_false(self):
        stream = TTYStringIO()
        L.configure_logging(stream=stream, use_color=False, force=True)
        logging.getLogger("ai").warning("plain-console")
        out = stream.getvalue()
        assert "plain-console" in out
        assert ANSI_INTRO not in out

    def test_console_no_ansi_on_non_tty_autodetect(self):
        stream = io.StringIO()  # isatty() -> False
        L.configure_logging(stream=stream, force=True)  # auto-detect
        logging.getLogger("ai").error("nontty")
        out = stream.getvalue()
        assert "nontty" in out
        assert ANSI_INTRO not in out

    def test_no_color_env_suppresses_console_color(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        stream = TTYStringIO()
        L.configure_logging(stream=stream, force=True)  # auto-detect
        logging.getLogger("ai").warning("nocolor-env")
        out = stream.getvalue()
        assert "nocolor-env" in out
        assert ANSI_INTRO not in out

    def test_term_dumb_suppresses_console_color(self, monkeypatch):
        monkeypatch.setenv("TERM", "dumb")
        stream = TTYStringIO()
        L.configure_logging(stream=stream, force=True)  # auto-detect
        logging.getLogger("ai").warning("dumb-term")
        out = stream.getvalue()
        assert "dumb-term" in out
        assert ANSI_INTRO not in out

    def test_no_ansi_in_text_file_even_when_console_color_forced(self, tmp_path):
        """CRITICAL: color forced ON for the tty console must NOT bleed into file."""
        logf = tmp_path / "app.log"
        stream = TTYStringIO()
        L.configure_logging(
            stream=stream, use_color=True, log_file=logf, force=True
        )
        logging.getLogger("ai").warning("file-clean %s", "arg")
        for h in logging.getLogger("ai").handlers:
            h.flush()
        console = stream.getvalue()
        text = _read_bytes(logf)
        # Console DID colorize.
        assert ANSI_INTRO in console
        # File is byte-clean.
        assert "file-clean arg" in text
        assert ANSI_INTRO not in text

    def test_no_ansi_in_json_file_even_when_console_color_forced(self, tmp_path):
        jsonf = tmp_path / "app.jsonl"
        stream = TTYStringIO()
        L.configure_logging(
            stream=stream, use_color=True, json_file=jsonf, force=True
        )
        logging.getLogger("ai").error("json-clean")
        for h in logging.getLogger("ai").handlers:
            h.flush()
        text = _read_bytes(jsonf)
        assert ANSI_INTRO not in text
        # And the level field is the plain level name, not a colorized one.
        rec = json.loads(text.strip().splitlines()[-1])
        assert rec["level"] == "ERROR"


# =============================================================================
# CRITICAL PROPERTY 5 — JSONL structure
# =============================================================================

class TestJsonFormatter:
    def _last_record(self, path):
        for h in logging.getLogger("ai").handlers:
            h.flush()
        lines = [ln for ln in _read_bytes(path).splitlines() if ln.strip()]
        return json.loads(lines[-1])

    def test_each_line_is_valid_json(self, tmp_path):
        jsonf = tmp_path / "j.jsonl"
        L.configure_logging(console=False, json_file=jsonf, force=True)
        log = logging.getLogger("ai")
        log.warning("one")
        log.error("two")
        for h in log.handlers:
            h.flush()
        lines = [ln for ln in _read_bytes(jsonf).splitlines() if ln.strip()]
        assert len(lines) == 2
        for ln in lines:
            json.loads(ln)  # must not raise

    def test_required_keys_and_values(self, tmp_path):
        jsonf = tmp_path / "j.jsonl"
        L.configure_logging(console=False, json_file=jsonf, force=True)
        logging.getLogger("ai").warning("structured msg")
        rec = self._last_record(jsonf)
        for key in ("ts", "level", "logger", "func", "line", "message"):
            assert key in rec, f"missing key {key}"
        assert rec["level"] == "WARNING"
        assert rec["message"] == "structured msg"
        assert rec["logger"] == "ai"
        assert isinstance(rec["line"], int)

    def test_message_arg_interpolation(self, tmp_path):
        jsonf = tmp_path / "j.jsonl"
        L.configure_logging(console=False, json_file=jsonf, force=True)
        logging.getLogger("ai").info("value is %d", 42)
        rec = self._last_record(jsonf)
        assert rec["message"] == "value is 42"

    def test_exc_included_when_exc_info(self, tmp_path):
        jsonf = tmp_path / "j.jsonl"
        L.configure_logging(console=False, json_file=jsonf, force=True)
        try:
            raise ValueError("boom-json")
        except ValueError:
            logging.getLogger("ai").error("caught", exc_info=True)
        rec = self._last_record(jsonf)
        assert "exc" in rec
        assert "ValueError" in rec["exc"]
        assert "boom-json" in rec["exc"]

    def test_exc_absent_without_exc_info(self, tmp_path):
        jsonf = tmp_path / "j.jsonl"
        L.configure_logging(console=False, json_file=jsonf, force=True)
        logging.getLogger("ai").info("no exc here")
        rec = self._last_record(jsonf)
        assert "exc" not in rec


# =============================================================================
# CRITICAL PROPERTY 6 — env-var precedence
# =============================================================================

class TestEnvPrecedence:
    def test_env_sets_default_level(self, monkeypatch):
        monkeypatch.setenv("AI_LOG_LEVEL", "DEBUG")
        L.configure_logging(stream=io.StringIO(), force=True)
        assert logging.getLogger("ai").level == logging.DEBUG

    def test_kwarg_overrides_env_level(self, monkeypatch):
        monkeypatch.setenv("AI_LOG_LEVEL", "DEBUG")
        L.configure_logging(level="ERROR", stream=io.StringIO(), force=True)
        assert logging.getLogger("ai").level == logging.ERROR

    def test_default_level_is_info(self):
        L.configure_logging(stream=io.StringIO(), force=True)
        assert logging.getLogger("ai").level == logging.INFO

    def test_env_console_off_disables_console(self, monkeypatch):
        monkeypatch.setenv("AI_LOG_CONSOLE", "0")
        logger = L.configure_logging(force=True)
        stream_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        assert stream_handlers == []

    def test_kwarg_console_overrides_env(self, monkeypatch):
        monkeypatch.setenv("AI_LOG_CONSOLE", "0")
        stream = io.StringIO()
        logger = L.configure_logging(console=True, stream=stream, force=True)
        stream_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_handlers) == 1

    def test_env_log_file_used(self, monkeypatch, tmp_path):
        logf = tmp_path / "env.log"
        monkeypatch.setenv("AI_LOG_FILE", str(logf))
        L.configure_logging(console=False, force=True)
        logging.getLogger("ai").warning("via-env-file")
        for h in logging.getLogger("ai").handlers:
            h.flush()
        assert logf.exists()
        assert "via-env-file" in _read_bytes(logf)

    def test_env_json_file_used(self, monkeypatch, tmp_path):
        jsonf = tmp_path / "env.jsonl"
        monkeypatch.setenv("AI_LOG_JSON", str(jsonf))
        L.configure_logging(console=False, force=True)
        logging.getLogger("ai").warning("via-env-json")
        for h in logging.getLogger("ai").handlers:
            h.flush()
        assert jsonf.exists()
        rec = json.loads(_read_bytes(jsonf).strip().splitlines()[-1])
        assert rec["message"] == "via-env-json"


# =============================================================================
# Per-session log ($AI_SESSION_DIR/logs/session.log)
# =============================================================================

class TestSessionFile:
    def test_auto_session_log_when_session_dir_set(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AI_SESSION_DIR", str(tmp_path))
        L.configure_logging(console=False, force=True)
        L.get_logger("send_prompt", component="prompting").info("session line")
        for h in logging.getLogger("ai").handlers:
            h.flush()
        sess = tmp_path / "logs" / "session.log"
        assert sess.exists()
        text = _read_bytes(sess)
        # Filterable by component AND module in the single session log.
        assert "ai.prompting.send_prompt" in text
        assert "session line" in text
        assert "\033[" not in text  # never any ANSI in the file

    def test_session_log_handler_is_non_rotating(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AI_SESSION_DIR", str(tmp_path))
        L.configure_logging(console=False, force=True)
        file_handlers = [h for h in logging.getLogger("ai").handlers
                         if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 1
        # Plain FileHandler, NOT a RotatingFileHandler (multiprocess-append-safe).
        assert not isinstance(file_handlers[0], logging.handlers.RotatingFileHandler)

    def test_no_session_log_when_session_dir_unset(self, tmp_path):
        # Fixture already clears AI_SESSION_DIR.
        L.configure_logging(console=False, force=True)
        assert L.default_session_log_path() is None
        file_handlers = [h for h in logging.getLogger("ai").handlers
                         if isinstance(h, logging.FileHandler)]
        assert file_handlers == []

    def test_session_file_disabled_via_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AI_SESSION_DIR", str(tmp_path))
        monkeypatch.setenv("AI_LOG_SESSION", "0")
        L.configure_logging(console=False, force=True)
        assert not (tmp_path / "logs" / "session.log").exists()
        file_handlers = [h for h in logging.getLogger("ai").handlers
                         if isinstance(h, logging.FileHandler)]
        assert file_handlers == []

    def test_session_file_disabled_via_kwarg(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AI_SESSION_DIR", str(tmp_path))
        L.configure_logging(console=False, session_file=False, force=True)
        file_handlers = [h for h in logging.getLogger("ai").handlers
                         if isinstance(h, logging.FileHandler)]
        assert file_handlers == []

    def test_explicit_log_file_supersedes_session_default(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AI_SESSION_DIR", str(tmp_path))
        explicit = tmp_path / "explicit.log"
        L.configure_logging(console=False, log_file=explicit, force=True)
        L.get_logger("m", component="c").info("hi")
        for h in logging.getLogger("ai").handlers:
            h.flush()
        assert explicit.exists()
        # The session default must NOT also be attached when an explicit file wins.
        assert not (tmp_path / "logs" / "session.log").exists()


# =============================================================================
# add_file_handler / remove_handler
# =============================================================================

class TestAddRemoveHandler:
    def test_add_text_handler_writes_clean(self, tmp_path):
        L.configure_logging(console=False, force=True)
        logf = tmp_path / "extra.log"
        h = L.add_file_handler(logf, level="DEBUG")
        try:
            logging.getLogger("ai").setLevel(logging.DEBUG)
            logging.getLogger("ai").debug("extra-line")
            h.flush()
            text = _read_bytes(logf)
            assert "extra-line" in text
            assert ANSI_INTRO not in text
        finally:
            L.remove_handler(h)
        assert h not in logging.getLogger("ai").handlers

    def test_add_json_handler(self, tmp_path):
        L.configure_logging(console=False, force=True)
        jsonf = tmp_path / "extra.jsonl"
        h = L.add_file_handler(jsonf, json=True)
        try:
            logging.getLogger("ai").warning("json-extra")
            h.flush()
            rec = json.loads(_read_bytes(jsonf).strip().splitlines()[-1])
            assert rec["message"] == "json-extra"
        finally:
            L.remove_handler(h)

    def test_add_returns_handler_and_attaches(self, tmp_path):
        L.configure_logging(console=False, force=True)
        h = L.add_file_handler(tmp_path / "x.log")
        assert isinstance(h, logging.Handler)
        assert h in logging.getLogger("ai").handlers
        L.remove_handler(h)

    def test_remove_handler_is_safe_to_double_call(self, tmp_path):
        L.configure_logging(console=False, force=True)
        h = L.add_file_handler(tmp_path / "x.log")
        L.remove_handler(h)
        # Second removal must not raise.
        L.remove_handler(h)


# =============================================================================
# Formatter units
# =============================================================================

class TestFormatters:
    def _record(self, level=logging.INFO, msg="m", args=None):
        return logging.LogRecord(
            name="ai.test", level=level, pathname=__file__, lineno=10,
            msg=msg, args=args or (), exc_info=None, func="fn",
        )

    def test_color_formatter_no_color_is_plain(self):
        fmt = L.ColorFormatter(use_color=False)
        out = fmt.format(self._record(level=logging.ERROR))
        assert ANSI_INTRO not in out
        assert "ERROR" in out

    def test_color_formatter_with_color_colorizes_levelname(self):
        if L.Colors is None:
            pytest.skip("Colors module unavailable")
        fmt = L.ColorFormatter(use_color=True)
        rec = self._record(level=logging.ERROR)
        out = fmt.format(rec)
        assert ANSI_INTRO in out
        # The record's levelname must be restored (not left mutated).
        assert rec.levelname == "ERROR"

    def test_json_formatter_produces_object(self):
        fmt = L.JsonFormatter()
        out = fmt.format(self._record(msg="hi %s", args=("there",)))
        rec = json.loads(out)
        assert rec["message"] == "hi there"
        assert rec["logger"] == "ai.test"
        assert rec["level"] == "INFO"


# =============================================================================
# CRITICAL PROPERTY 7 — back-compat helpers
# =============================================================================

class TestBackCompat:
    def test_setup_logging_returns_ai_logger(self):
        logger = L.setup_logging(level=logging.DEBUG)
        assert logger is logging.getLogger("ai")
        assert logger.level == logging.DEBUG
        assert L.is_configured() is True

    def test_log_helpers_route_to_ai_logger(self, tmp_path):
        logf = tmp_path / "bc.log"
        L.configure_logging(
            level="DEBUG", console=False, log_file=logf, force=True
        )
        L.log_info("bc-info")
        L.log_error("bc-error")
        L.log_debug("bc-debug")
        for h in logging.getLogger("ai").handlers:
            h.flush()
        text = _read_bytes(logf)
        assert "bc-info" in text
        assert "bc-error" in text
        assert "bc-debug" in text
        # Levels routed correctly.
        assert "INFO" in text and "ERROR" in text and "DEBUG" in text

    def test_back_compat_files_have_no_ansi(self, tmp_path):
        """Back-compat helpers must not bake ANSI into files (console color on)."""
        logf = tmp_path / "bc.log"
        stream = TTYStringIO()
        L.configure_logging(
            stream=stream, use_color=True, log_file=logf, force=True
        )
        L.log_info("bc-clean")
        for h in logging.getLogger("ai").handlers:
            h.flush()
        assert ANSI_INTRO not in _read_bytes(logf)

    def test_log_info_stacklevel_attribution(self, tmp_path):
        """Attribution of the back-compat log_info() record.

        The call chain has TWO wrapper frames -- log_info() -> _emit() ->
        logger.log() -- so _emit passes ``stacklevel + 1`` (default 3) to skip
        both and attribute the record to the USER'S call site. Here that call
        site is this test method, so funcName must be this method's name, NOT
        the "log_info"/"_emit" wrappers.
        """
        jsonf = tmp_path / "attr.jsonl"
        L.configure_logging(console=False, json_file=jsonf, force=True)
        L.log_info("attributed")
        for h in logging.getLogger("ai").handlers:
            h.flush()
        rec = json.loads(_read_bytes(jsonf).strip().splitlines()[-1])
        assert rec["func"] == "test_log_info_stacklevel_attribution"

    def test_log_out_prints_to_stdout(self, capsys):
        L.log_out("plain output line")
        captured = capsys.readouterr()
        assert "plain output line" in captured.out

    def test_log_block_logs_entry_exit(self, tmp_path):
        logf = tmp_path / "block.log"
        L.configure_logging(console=False, log_file=logf, force=True)
        with L.log_block("myblock"):
            pass
        for h in logging.getLogger("ai").handlers:
            h.flush()
        text = _read_bytes(logf)
        assert "Entering block: myblock" in text
        assert "Exiting block: myblock" in text

    def test_log_block_logs_exit_on_exception(self, tmp_path):
        logf = tmp_path / "block.log"
        L.configure_logging(console=False, log_file=logf, force=True)
        with pytest.raises(RuntimeError):
            with L.log_block("errblock"):
                raise RuntimeError("x")
        for h in logging.getLogger("ai").handlers:
            h.flush()
        text = _read_bytes(logf)
        assert "Entering block: errblock" in text
        assert "Exiting block: errblock" in text

    def test_log_function_decorator(self, tmp_path):
        jsonf = tmp_path / "deco.jsonl"
        L.configure_logging(
            level="DEBUG", console=False, json_file=jsonf, force=True
        )

        @L.log_function
        def add(a, b):
            return a + b

        assert add(2, 3) == 5
        for h in logging.getLogger("ai").handlers:
            h.flush()
        msgs = [
            json.loads(ln)["message"]
            for ln in _read_bytes(jsonf).splitlines() if ln.strip()
        ]
        assert any("add called" in m for m in msgs)
        assert any("add returned 5" in m for m in msgs)

    def test_parse_args_default_level(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog"])
        level = L.parse_args()
        assert level == logging.INFO
        assert logging.getLogger("ai").level == logging.INFO

    def test_parse_args_explicit_level(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog", "--log-level", "ERROR"])
        level = L.parse_args()
        assert level == logging.ERROR
        assert logging.getLogger("ai").level == logging.ERROR

    def test_parse_args_ignores_unknown(self, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["prog", "--other", "val", "--log-level", "DEBUG"]
        )
        level = L.parse_args()
        assert level == logging.DEBUG


# =============================================================================
# End-to-end sanity — plain text file content
# =============================================================================

class TestTextFileOutput:
    def test_text_file_contains_formatted_record(self, tmp_path):
        logf = tmp_path / "e2e.log"
        L.configure_logging(console=False, log_file=logf, force=True)
        logging.getLogger("ai").warning("e2e-message")
        for h in logging.getLogger("ai").handlers:
            h.flush()
        text = _read_bytes(logf)
        assert "WARNING" in text
        assert "e2e-message" in text
        assert "ai" in text  # logger name present

    def test_level_filtering(self, tmp_path):
        logf = tmp_path / "filter.log"
        L.configure_logging(level="WARNING", console=False, log_file=logf, force=True)
        log = logging.getLogger("ai")
        log.info("should-not-appear")
        log.warning("should-appear")
        for h in log.handlers:
            h.flush()
        text = _read_bytes(logf)
        assert "should-appear" in text
        assert "should-not-appear" not in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
