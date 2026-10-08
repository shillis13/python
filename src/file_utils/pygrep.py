#!/usr/bin/env python3
"""
pygrep.py: Content search whose context boundaries can be patterns.

Where egrep takes -A/-B/-C as line counts, pygrep also takes them as patterns:
grow each match outward until a line matches the boundary. With no -P at all,
-B opens a range and -A closes it, which extracts records rather than matches.

fsFind finds files; pygrep searches inside them. Pipe the two together:

    fsFind ... | pygrep --files-from - -P 'TODO'

Usage:
    pygrep -P 'ERROR' -A '^$' app.log
    pygrep -B '-----BEGIN' -A '-----END' --exclude-bounds bundle.pem
    pygrep -A '^$' --emit ranges config.ini
    journalctl -u nginx | pygrep -P 'timed out' -B 2 -A '^\\s*$'

Exit codes: 0 selected something, 1 selected nothing, 2 error.
"""
import argparse
import re
import sys
from pathlib import Path

from file_utils.lib_pygrep import Options, PygrepError, search
from file_utils import lib_fileInput

EXIT_SELECTED = 0
EXIT_NOTHING = 1
EXIT_ERROR = 2

_COUNT_RE = re.compile(r"^\d+$")

_COLOR_MATCH = "\033[1;31m"
_COLOR_BOUND = "\033[1;36m"
_COLOR_OFF = "\033[0m"


class Source:
    """One input stream: a label for output plus its lines."""

    def __init__(self, label, lines):
        self.label = label
        self.lines = lines


# --------------------------------------------------------------------------
# Argument parsing
# --------------------------------------------------------------------------


def build_parser():
    """Construct the argument parser.

    Input arguments are declared here rather than through
    lib_fileInput.add_text_input_arguments so that -v keeps grep's
    invert-match meaning and -f stays an input file.
    """

    parser = argparse.ArgumentParser(
        prog="pygrep",
        description="Content search with pattern boundaries.",
        epilog="Patterns are always flags; positional arguments are always sources.",
    )

    patterns = parser.add_argument_group("patterns")
    patterns.add_argument("-P", "--pattern", action="append", default=[],
                          metavar="PAT",
                          help="primary pattern; repeatable, alternatives OR'd")
    patterns.add_argument("-A", "--after", metavar="PAT|N",
                          help="closing boundary: a pattern, or bare digits for a line count")
    patterns.add_argument("-B", "--before", metavar="PAT|N",
                          help="opening boundary: a pattern, or bare digits for a line count")
    patterns.add_argument("-C", "--context", metavar="PAT|N",
                          help="both boundaries; not combinable with -A or -B")
    patterns.add_argument("--after-pattern", metavar="PAT",
                          help="closing boundary, always a pattern")
    patterns.add_argument("--before-pattern", metavar="PAT",
                          help="opening boundary, always a pattern")
    patterns.add_argument("--context-pattern", metavar="PAT",
                          help="both boundaries, always patterns")
    patterns.add_argument("--after-lines", type=int, metavar="N",
                          help="lines after the match")
    patterns.add_argument("--before-lines", type=int, metavar="N",
                          help="lines before the match")
    patterns.add_argument("--context-lines", type=int, metavar="N",
                          help="lines on both sides of the match")
    patterns.add_argument("--pattern-file", metavar="FILE",
                          help="further -P alternatives, one per line; # comments skipped")

    ranges = parser.add_argument_group("range construction")
    ranges.add_argument("-d", "--max-distance", type=int, metavar="N",
                        help="reject a boundary this many lines or more away")
    ranges.add_argument("--pairing", choices=("sed", "occurrence"), default="sed",
                        help="how openers pair with closers (default: sed)")
    ranges.add_argument("--unterminated", choices=("truncate", "drop"),
                        default="truncate",
                        help="when a boundary is not found (default: truncate)")
    ranges.add_argument("--exclude-A", dest="exclude_after", action="store_true",
                        help="omit the closing boundary line")
    ranges.add_argument("--exclude-B", dest="exclude_before", action="store_true",
                        help="omit the opening boundary line")
    ranges.add_argument("--exclude-bounds", action="store_true",
                        help="omit both boundary lines")

    shape = parser.add_argument_group("output shape")
    shape.add_argument("--emit", choices=("union", "ranges"), default="union",
                       help="one merged set of lines, or one record per range")

    matching = parser.add_argument_group("matching")
    matching.add_argument("-i", "--ignore-case", action="store_true")
    matching.add_argument("-w", "--word-regexp", action="store_true")
    matching.add_argument("-x", "--line-regexp", action="store_true")
    matching.add_argument("-v", "--invert-match", action="store_true",
                          help="emit every line NOT selected; requires --emit union")
    matching.add_argument("-m", "--max-count", type=int, metavar="N",
                          help="stop after N selected lines per source")
    matching.add_argument("-E", "--extended-regexp", action="store_true",
                          help=argparse.SUPPRESS)
    matching.add_argument("-F", "--fixed-strings", action="store_true",
                          help=argparse.SUPPRESS)

    output = parser.add_argument_group("output")
    output.add_argument("-n", "--line-number", action="store_true")
    output.add_argument("-c", "--count", action="store_true")
    output.add_argument("-l", "--files-with-matches", action="store_true")
    output.add_argument("-o", "--only-matching", action="store_true",
                        help="print only the matched text; not combinable with boundaries")
    output.add_argument("-q", "--quiet", action="store_true")
    output.add_argument("-s", "--no-messages", action="store_true",
                        help="suppress unreadable-source diagnostics; exit status unchanged")
    output.add_argument("--color", choices=("auto", "always", "never"), default="auto")

    source = parser.add_argument_group("input")
    source.add_argument("paths", nargs="*", metavar="PATH",
                        help="files to search; '-' means stdin as text")
    source.add_argument("-f", "--file", dest="input_file", metavar="FILE",
                        help="read text from this file")
    source.add_argument("--files-from", metavar="FILE",
                        help="read a LIST OF PATHS from FILE; '-' means from stdin")
    source.add_argument("-p", "--paste", action="store_true",
                        help="read text from the clipboard")

    return parser


def _split_boundary(raw):
    """Classify a -A/-B/-C argument as a line count or a pattern (R2).

    Bare digits are a count. To match digits as a pattern, use the explicit
    --after-pattern form, or spell it so it is not bare digits: '[3]'.
    """

    if raw is None:
        pair = (None, None)
    elif _COUNT_RE.match(raw):
        pair = (None, int(raw))
    else:
        pair = (raw, None)
    return pair


def _resolve_side(polymorphic, explicit_pattern, explicit_count, ctx_pattern,
                  ctx_count, label):
    """Pick one side's pattern and count from the flags that can set it."""

    pattern, count = _split_boundary(polymorphic)
    if explicit_pattern is not None:
        pattern = explicit_pattern
    if explicit_count is not None:
        count = explicit_count
    if ctx_pattern is not None:
        pattern = ctx_pattern
    if ctx_count is not None:
        count = ctx_count
    if pattern is not None and count is not None:
        raise PygrepError(label + " was given both a pattern and a line count")
    return (pattern, count)


def _load_pattern_file(path):
    """Read extra -P alternatives, skipping blanks and # comments."""

    alternatives = []
    try:
        text = Path(path).expanduser().read_text(encoding="utf-8")
    except OSError as err:
        raise PygrepError("cannot read pattern file " + str(path) + ": " + str(err))
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            alternatives.append(stripped)
    return alternatives


def _reject_unsupported(args):
    """Refuse flags accepted only so the error can name them (R17, Sec 5.6)."""

    problem = None
    if args.extended_regexp:
        problem = ("-E is not supported: the dialect is always Python re, which "
                   "is not a POSIX ERE superset, so accepting -E would promise "
                   "a compatibility the engine cannot keep")
    elif args.fixed_strings:
        problem = ("-F is not supported: every pattern is a Python regular "
                   "expression. Escape literals with re.escape semantics instead")
    if problem is not None:
        raise PygrepError(problem)
    return None


def to_options(args):
    """Translate parsed arguments into the engine's Options (Sec 9.1).

    -C and --exclude-bounds are expanded here; the engine never sees them.
    """

    _reject_unsupported(args)
    if args.context is not None or args.context_pattern is not None \
            or args.context_lines is not None:
        conflicting = (args.after is not None or args.before is not None
                       or args.after_pattern is not None
                       or args.before_pattern is not None
                       or args.after_lines is not None
                       or args.before_lines is not None)
        if conflicting:
            raise PygrepError("-C cannot be combined with -A or -B")
    ctx_pattern, ctx_count = _split_boundary(args.context)
    if args.context_pattern is not None:
        ctx_pattern = args.context_pattern
    if args.context_lines is not None:
        ctx_count = args.context_lines

    after, after_lines = _resolve_side(args.after, args.after_pattern,
                                       args.after_lines, ctx_pattern, ctx_count,
                                       "-A")
    before, before_lines = _resolve_side(args.before, args.before_pattern,
                                         args.before_lines, ctx_pattern,
                                         ctx_count, "-B")

    alternatives = list(args.pattern)
    if args.pattern_file is not None:
        alternatives.extend(_load_pattern_file(args.pattern_file))

    has_boundary = (after is not None or before is not None
                    or after_lines is not None or before_lines is not None)
    if args.only_matching and has_boundary:
        raise PygrepError("-o cannot be combined with a boundary flag")

    exclude_after = args.exclude_after or args.exclude_bounds
    exclude_before = args.exclude_before or args.exclude_bounds

    opts = Options(pattern=tuple(alternatives),
                   after=after,
                   before=before,
                   after_lines=after_lines,
                   before_lines=before_lines,
                   max_distance=args.max_distance,
                   pairing=args.pairing,
                   unterminated=args.unterminated,
                   exclude_after=exclude_after,
                   exclude_before=exclude_before,
                   emit=args.emit,
                   invert=args.invert_match,
                   ignore_case=args.ignore_case,
                   word=args.word_regexp,
                   line_regexp=args.line_regexp,
                   max_count=args.max_count)
    return opts


# --------------------------------------------------------------------------
# Input resolution (Sec 6)
# --------------------------------------------------------------------------


def _read_path(path, quiet):
    """Read one file into lines, or None if it cannot be read."""

    source = None
    try:
        text = Path(path).expanduser().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        if not quiet:
            sys.stderr.write("pygrep: " + str(path) + ": " + str(err) + "\n")
    else:
        source = Source(str(path), text.splitlines())
    return source


def resolve_sources(args):
    """Determine the sources, with the type of each stated explicitly.

    Only one consumer of stdin may be active: a bare '-' means stdin is text,
    while --files-from - means stdin is a list of paths.
    """

    wants_stdin_text = "-" in args.paths
    wants_stdin_list = args.files_from == "-"
    if wants_stdin_text and wants_stdin_list:
        raise PygrepError("'-' and --files-from - both consume stdin")

    sources = []
    failures = 0

    if args.paste:
        text = lib_fileInput.read_clipboard_text()
        sources.append(Source("(clipboard)", text.splitlines()))
    elif args.input_file is not None:
        one = _read_path(args.input_file, args.no_messages)
        if one is None:
            failures += 1
        else:
            sources.append(one)
    elif args.files_from is not None:
        if wants_stdin_list:
            listing = sys.stdin.read()
        else:
            listing = Path(args.files_from).expanduser().read_text(encoding="utf-8")
        for line in listing.splitlines():
            candidate = line.strip()
            if not candidate or candidate.startswith("#"):
                continue
            for expanded in lib_fileInput.expand_path(candidate):
                one = _read_path(expanded, args.no_messages)
                if one is None:
                    failures += 1
                else:
                    sources.append(one)
    elif args.paths:
        for raw in args.paths:
            if raw == "-":
                sources.append(Source("(standard input)", sys.stdin.read().splitlines()))
                continue
            target = Path(raw).expanduser()
            if target.is_dir():
                raise PygrepError(
                    str(raw) + " is a directory: pygrep searches content, not trees. "
                    "Use fsFind with --files-from, or a shell glob")
            one = _read_path(raw, args.no_messages)
            if one is None:
                failures += 1
            else:
                sources.append(one)
    elif not sys.stdin.isatty():
        sources.append(Source("(standard input)", sys.stdin.read().splitlines()))
    else:
        raise PygrepError("no input: give a PATH, pipe to stdin, or use -p")

    return (sources, failures)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def _use_color(choice):
    """Decide whether to emit escape sequences."""

    if choice == "always":
        enabled = True
    elif choice == "never":
        enabled = False
    else:
        enabled = sys.stdout.isatty()
    return enabled


def _prefix(label, lineno, args, show_label, is_selected):
    """Build grep's location prefix: ':' for selected, '-' for context."""

    parts = []
    if show_label:
        parts.append(label)
    if args.line_number:
        parts.append(str(lineno))
    if not parts:
        rendered = ""
    else:
        separator = ":" if is_selected else "-"
        rendered = separator.join(parts) + separator
    return rendered


def _roles(candidates):
    """Collect which linenos are anchors and which are boundaries.

    Boundaries are highlighted in their own colour so it is visible why a range
    stopped where it did, which is the whole point of a pattern boundary.
    """

    anchors = set()
    bounds = set()
    for candidate in candidates:
        if candidate.anchor is None:
            bounds.add(candidate.start)
            bounds.add(candidate.stop)
        else:
            anchors.add(candidate.anchor)
            if candidate.start != candidate.anchor:
                bounds.add(candidate.start)
            if candidate.stop != candidate.anchor:
                bounds.add(candidate.stop)
    return (anchors, bounds)


def _paint(body, lineno, anchors, bounds, colored):
    """Apply the match or boundary colour to one line's text."""

    painted = body
    if colored:
        if lineno in anchors:
            painted = _COLOR_MATCH + body + _COLOR_OFF
        elif lineno in bounds:
            painted = _COLOR_BOUND + body + _COLOR_OFF
    return painted


def _render_union(result, source, args, show_label, out, colored):
    """Print the selected set, with '--' between non-contiguous groups."""

    anchors, bounds = _roles(result.candidates)
    if args.invert_match:
        # Under -v every emitted line is a selected line by definition: the
        # candidates describe what was withheld, not what is being printed.
        anchors = set()
        bounds = set()
    first = True
    for start, stop in result.groups:
        if not first:
            out.write("--\n")
        first = False
        for lineno in range(start, stop + 1):
            body = source.lines[lineno - 1]
            selected = lineno in anchors or not anchors
            painted = _paint(body, lineno, anchors, bounds, colored)
            out.write(_prefix(source.label, lineno, args, show_label, selected)
                      + painted + "\n")
    return None


def _render_ranges(result, source, args, show_label, out, colored):
    """Print one record per candidate, separated by '--'."""

    anchors, bounds = _roles(result.candidates)
    first = True
    for candidate in result.candidates:
        if not first:
            out.write("--\n")
        first = False
        for lineno in range(candidate.start, candidate.stop + 1):
            if lineno in candidate.excluded:
                continue
            body = source.lines[lineno - 1]
            selected = lineno == candidate.anchor or candidate.anchor is None
            painted = _paint(body, lineno, anchors, bounds, colored)
            out.write(_prefix(source.label, lineno, args, show_label, selected)
                      + painted + "\n")
    return None


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def run(argv, out=None):
    """Parse, search every source, render, and return an exit code."""

    stream = out if out is not None else sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    status = EXIT_NOTHING

    try:
        opts = to_options(args)
        sources, failures = resolve_sources(args)
    except PygrepError as exc:
        sys.stderr.write("pygrep: " + str(exc) + "\n")
        return EXIT_ERROR

    show_label = len(sources) > 1
    colored = _use_color(args.color)
    any_selected = False

    for source in sources:
        try:
            result = search(source.lines, opts)
        except PygrepError as exc:
            sys.stderr.write("pygrep: " + str(exc) + "\n")
            return EXIT_ERROR
        if args.count:
            # grep -c reports every source, including the ones with no matches.
            if show_label:
                stream.write(source.label + ":" + str(result.count) + "\n")
            else:
                stream.write(str(result.count) + "\n")
            if result.selected:
                any_selected = True
            continue
        if not result.selected:
            continue
        any_selected = True
        if args.quiet:
            break
        if args.files_with_matches:
            stream.write(source.label + "\n")
        elif args.emit == "ranges":
            _render_ranges(result, source, args, show_label, stream, colored)
        else:
            _render_union(result, source, args, show_label, stream, colored)

    if failures:
        status = EXIT_ERROR
    elif any_selected:
        status = EXIT_SELECTED
    return status


def main():
    """Console-script entry point."""

    code = run(sys.argv[1:])
    sys.exit(code)


if __name__ == "__main__":
    main()
