"""pygrep search engine.

Runs the seven-step pygrep algorithm over one source held in memory as a
Sequence[str]. The module is pure: it imports only ``re``, ``dataclasses`` and
``typing``, performs no I/O, reads no arguments and prints nothing.

The public surface is the frozen engine contract -- ``Occurrence``,
``Candidate``, ``Options``, ``Result`` and ``search`` -- plus the pipeline
helpers named by the module structure section (``find_occurrences``,
``to_union``, ``group_contiguous``) and the error types the CLI catches.
Everything else is an implementation detail.

Two distinctions drive the whole design:

* An *occurrence* is ``(lineno, start_col, end_col)``. Direction on the
  anchor's own line is decided by column, so two occurrences can share a line
  and still stand in a forward/backward relationship to one another.
* ``candidates`` is the pre-union record list; ``selected`` is the union (or
  its complement under invert). They are different answers, not two renderings
  of one answer, so both are always produced.
"""

import re
from dataclasses import dataclass
from typing import Optional, Sequence

__all__ = [
    "Occurrence",
    "Candidate",
    "Options",
    "Result",
    "PygrepError",
    "PatternError",
    "OptionError",
    "find_occurrences",
    "to_union",
    "group_contiguous",
    "search",
]


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class PygrepError(ValueError):
    """Base class for every engine-level failure.

    Subclasses ValueError so a caller that only guards against bad input still
    catches it, while a caller that wants engine-specific handling can name
    PygrepError directly. No re.error ever escapes this module.
    """


class PatternError(PygrepError):
    """A supplied pattern is not a valid Python regular expression."""


class OptionError(PygrepError):
    """An Options combination the engine has no defined behavior for."""


# --------------------------------------------------------------------------
# Frozen contract types
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Occurrence:
    """One regex match, located within a source."""

    lineno: int        # 1-based
    start_col: int     # 0-based, inclusive
    end_col: int       # 0-based, exclusive


@dataclass(frozen=True)
class Candidate:
    """One contiguous line span produced by step 2, after steps 3 through 5."""

    start: int                          # 1-based lineno, inclusive
    stop: int                           # 1-based lineno, inclusive
    anchor: Optional[int] = None        # lineno of the -P match, None in delimiter mode
    excluded: frozenset = frozenset()   # linenos this candidate does NOT contribute
    terminated: bool = True             # False if a boundary was missing or beyond -d


@dataclass
class Options:
    """The resolved flag set the engine acts on.

    -C and --exclude-bounds are expanded by the caller, so the engine only ever
    sees after/before and the two exclude flags.
    """

    pattern: tuple = ()                   # -P, OR'd. empty => delimiter mode
    after: Optional[str] = None           # -A as a pattern
    before: Optional[str] = None          # -B as a pattern
    after_lines: Optional[int] = None
    before_lines: Optional[int] = None
    max_distance: Optional[int] = None    # -d
    pairing: str = "sed"                  # "sed" | "occurrence"
    unterminated: str = "truncate"        # "truncate" | "drop"
    exclude_after: bool = False           # --exclude-A
    exclude_before: bool = False          # --exclude-B
    emit: str = "union"                   # "union" | "ranges"
    invert: bool = False                  # -v
    ignore_case: bool = False             # -i
    word: bool = False                    # -w
    line_regexp: bool = False             # -x
    max_count: Optional[int] = None       # -m


@dataclass
class Result:
    """Everything one source yields. The CLI decides which parts to render."""

    candidates: list    # list[Candidate], source order, pre-union
    selected: set       # set[int] of 1-based linenos: S, or D-S under invert
    groups: list        # list[tuple[int, int]] maximal contiguous runs of selected
    count: int          # selected match lines, or completed candidates


# --------------------------------------------------------------------------
# Internal working types
# --------------------------------------------------------------------------

# Side kinds, recorded per candidate side so later steps know how the side was
# produced without re-deriving it from the options:
#   "none"    no boundary requested; the side sits on the anchor line
#   "count"   resolved by arithmetic from a line count; never distance-limited
#             and never unterminated, because there is no boundary to find
#   "pattern" resolved by searching for a boundary occurrence; distance-limited
#             and unterminated when the search fails
#   "seed"    the occurrence the candidate itself grew from in delimiter mode
#   "edge"    deliberately the start or end of the source, which is what a
#             single-sided delimiter invocation substitutes for the missing side
_KIND_NONE = "none"
_KIND_COUNT = "count"
_KIND_PATTERN = "pattern"
_KIND_SEED = "seed"
_KIND_EDGE = "edge"


@dataclass
class _Draft:
    """A candidate under construction, carrying the provenance of each side."""

    anchor: Optional[int] = None
    start: Optional[int] = None        # None while the leading side is unresolved
    stop: Optional[int] = None         # None while the trailing side is unresolved
    open_line: Optional[int] = None    # lineno of the occurrence in the opener role
    close_line: Optional[int] = None   # lineno of the occurrence in the closer role
    lead_kind: str = _KIND_NONE
    trail_kind: str = _KIND_NONE
    lead_origin: int = 1               # lineno the leading side is measured from
    trail_origin: int = 1              # lineno the trailing side is measured from
    terminated: bool = True


@dataclass
class _Event:
    """One boundary occurrence together with the roles it is eligible to fill.

    Openers and closers are merged into a single ordered event stream for sed
    pairing. An occurrence matched by both boundary patterns is one event, not
    two, because a single occurrence fills exactly one role in a range.
    """

    occ: Occurrence
    is_open: bool
    is_close: bool


# --------------------------------------------------------------------------
# Ordering helpers
# --------------------------------------------------------------------------


def _direction_key(occ: Occurrence) -> tuple:
    """Key deciding forward/backward: line first, then column.

    end_col is deliberately absent. Forward means a strictly later column on
    the anchor's own line, so an occurrence starting at the anchor's own column
    is neither ahead of it nor behind it and cannot serve as either boundary.
    """

    key = (occ.lineno, occ.start_col)
    return key


def _sort_key(occ: Occurrence) -> tuple:
    """Total order over occurrences, used for merging and de-duplication."""

    key = (occ.lineno, occ.start_col, occ.end_col)
    return key


def _nearest_before(occurrences: list, key: tuple) -> Optional[Occurrence]:
    """Last occurrence strictly before key, or None.

    The list is ascending, so the scan can stop at the first occurrence that is
    not strictly earlier.
    """

    best = None
    for occ in occurrences:
        probe = _direction_key(occ)
        if probe < key:
            best = occ
        else:
            break
    return best


def _nearest_after(occurrences: list, key: tuple) -> Optional[Occurrence]:
    """First occurrence strictly after key, or None."""

    best = None
    for occ in occurrences:
        probe = _direction_key(occ)
        if probe > key:
            best = occ
            break
    return best


# --------------------------------------------------------------------------
# Step 1 -- occurrences
# --------------------------------------------------------------------------


def _pattern_texts(opts: Options) -> tuple:
    """Normalize opts.pattern to a tuple of pattern strings.

    A bare string is accepted as a single pattern rather than iterated one
    character at a time, which would otherwise be a silent misreading.
    """

    raw = opts.pattern
    if raw is None:
        texts = ()
    elif isinstance(raw, str):
        texts = (raw,)
    else:
        texts = tuple(raw)
    return texts


def _wrap(body: str, opts: Options) -> str:
    """Apply -x or -w to one pattern body.

    -x wins over -w: a whole-line match is already the stronger constraint, so
    adding word boundaries on top of it can only reject lines -x accepted.
    """

    wrapped = body
    if opts.line_regexp:
        wrapped = "\\A(?:" + body + ")\\Z"
    elif opts.word:
        wrapped = "\\b(?:" + body + ")\\b"
    return wrapped


def _compile_pattern(body: str, opts: Options, label: str):
    """Compile one pattern, translating re.error into PatternError."""

    if not isinstance(body, str):
        message = label + " pattern must be a string, got " + type(body).__name__
        raise PatternError(message)
    flags = 0
    if opts.ignore_case:
        flags = re.IGNORECASE
    source = _wrap(body, opts)
    try:
        compiled = re.compile(source, flags)
    except re.error as exc:
        detail = str(exc)
        shown = repr(body)
        message = "invalid " + label + " pattern " + shown + ": " + detail
        raise PatternError(message) from exc
    return compiled


def _compile_primary(opts: Options):
    """Compile the -P alternatives into one regex, or None in delimiter mode.

    Each alternative is compiled on its own first so a syntax error names the
    offending pattern rather than the joined blob the engine actually uses.
    """

    texts = _pattern_texts(opts)
    if not texts:
        compiled = None
    else:
        parts = []
        for body in texts:
            _compile_pattern(body, opts, "-P")
            parts.append("(?:" + body + ")")
        joined = "|".join(parts)
        compiled = _compile_pattern(joined, opts, "-P")
    return compiled


def find_occurrences(lines: Sequence[str], regex) -> list:
    """Locate every match of regex as an Occurrence, in source order.

    regex may be None, meaning the pattern was not supplied; the result is then
    empty. finditer yields non-overlapping matches left to right, so the list
    is already ascending in (lineno, start_col, end_col).
    """

    found = []
    if regex is not None:
        for lineno, text in enumerate(lines, 1):
            for match in regex.finditer(text):
                start = match.start()
                end = match.end()
                occ = Occurrence(lineno=lineno, start_col=start, end_col=end)
                found.append(occ)
    return found


# --------------------------------------------------------------------------
# Step 2 -- candidate construction, anchor mode
# --------------------------------------------------------------------------


def _build_anchor_drafts(matches: list,
                         openers: Optional[list],
                         closers: Optional[list],
                         opts: Options,
                         total: int) -> list:
    """Grow one draft outward from each match.

    Nearest boundary wins in each direction, measured in occurrence order, so
    the search begins at the next occurrence rather than the next line. That is
    what lets a second occurrence on the anchor's own line close the range, and
    what stops the anchor occurrence from closing its own range.

    A line count is resolved here and clamped to the source, because a count
    cannot fail to be found and so never reaches the unterminated policy.
    """

    drafts = []
    for match in matches:
        key = _direction_key(match)
        draft = _Draft(anchor=match.lineno,
                       start=match.lineno,
                       stop=match.lineno,
                       lead_origin=match.lineno,
                       trail_origin=match.lineno)
        if opts.before_lines is not None:
            draft.lead_kind = _KIND_COUNT
            reach = match.lineno - opts.before_lines
            if reach < 1:
                reach = 1
            draft.start = reach
        elif openers is not None:
            draft.lead_kind = _KIND_PATTERN
            opener = _nearest_before(openers, key)
            if opener is None:
                draft.start = None
            else:
                draft.start = opener.lineno
                draft.open_line = opener.lineno
        if opts.after_lines is not None:
            draft.trail_kind = _KIND_COUNT
            reach = match.lineno + opts.after_lines
            if reach > total:
                reach = total
            draft.stop = reach
        elif closers is not None:
            draft.trail_kind = _KIND_PATTERN
            closer = _nearest_after(closers, key)
            if closer is None:
                draft.stop = None
            else:
                draft.stop = closer.lineno
                draft.close_line = closer.lineno
        drafts.append(draft)
    return drafts


# --------------------------------------------------------------------------
# Step 2 -- candidate construction, delimiter mode
# --------------------------------------------------------------------------


def _merge_events(openers: list, closers: list) -> list:
    """Fold openers and closers into one ordered stream of role-tagged events.

    Identical spans collapse to a single event that is eligible for both roles,
    because one occurrence is one occurrence no matter how many patterns found
    it.
    """

    table = {}
    for occ in openers:
        key = _sort_key(occ)
        event = table.get(key)
        if event is None:
            event = _Event(occ=occ, is_open=True, is_close=False)
            table[key] = event
        else:
            event.is_open = True
    for occ in closers:
        key = _sort_key(occ)
        event = table.get(key)
        if event is None:
            event = _Event(occ=occ, is_open=False, is_close=True)
            table[key] = event
        else:
            event.is_close = True
    ordered = sorted(table)
    events = []
    for key in ordered:
        event = table[key]
        events.append(event)
    return events


def _pair_sed(events: list) -> list:
    """Pair openers with closers the way sed reads /a/,/b/.

    A range never reopens while one is open, so openers seen inside an open
    range are interior and closers seen outside one are exterior. The closer
    search always begins at the event after the opener, so a single occurrence
    cannot both open and close the same range; it resynchronizes at every
    closer, which is why a stray opener corrupts one range instead of all of
    them.
    """

    drafts = []
    open_event = None
    for event in events:
        if open_event is None:
            if event.is_open:
                open_event = event
        elif event.is_close:
            opener = open_event.occ
            closer = event.occ
            draft = _Draft(start=opener.lineno,
                           stop=closer.lineno,
                           open_line=opener.lineno,
                           close_line=closer.lineno,
                           lead_kind=_KIND_SEED,
                           trail_kind=_KIND_PATTERN,
                           lead_origin=opener.lineno,
                           trail_origin=opener.lineno)
            drafts.append(draft)
            open_event = None
    if open_event is not None:
        opener = open_event.occ
        draft = _Draft(start=opener.lineno,
                       stop=None,
                       open_line=opener.lineno,
                       lead_kind=_KIND_SEED,
                       trail_kind=_KIND_PATTERN,
                       lead_origin=opener.lineno,
                       trail_origin=opener.lineno)
        drafts.append(draft)
    return drafts


def _pair_occurrence(openers: list, closers: list) -> list:
    """Pair the n-th opener with the n-th closer, positionally.

    The pairing is FIFO and purely positional. A closer is only accepted when
    it follows its opener in occurrence order, which keeps one occurrence from
    filling both ends of a range and keeps a range from running backwards;
    an opener whose positional partner fails that test is left unterminated.
    Surplus closers have no opener to belong to and produce no candidate.
    """

    drafts = []
    available = len(closers)
    for index, opener in enumerate(openers):
        closer = None
        if index < available:
            partner = closers[index]
            opener_key = _direction_key(opener)
            partner_key = _direction_key(partner)
            if partner_key > opener_key:
                closer = partner
        draft = _Draft(start=opener.lineno,
                       open_line=opener.lineno,
                       lead_kind=_KIND_SEED,
                       trail_kind=_KIND_PATTERN,
                       lead_origin=opener.lineno,
                       trail_origin=opener.lineno)
        if closer is not None:
            draft.stop = closer.lineno
            draft.close_line = closer.lineno
        drafts.append(draft)
    return drafts


def _segment_by_closers(closers: list) -> list:
    """Segment the source at each closer: [BOF..a1] [a1..a2] ... [a(n-1)..an].

    The seam line is shared by the two segments it separates, so a1 closes the
    first and opens the second. That is legal because the one-occurrence-one-
    role rule binds within a single range, not across ranges. The list stops at
    the last closer because no closer follows it.
    """

    drafts = []
    previous = None
    for occ in closers:
        if previous is None:
            draft = _Draft(start=1,
                           stop=occ.lineno,
                           close_line=occ.lineno,
                           lead_kind=_KIND_EDGE,
                           trail_kind=_KIND_SEED,
                           lead_origin=1,
                           trail_origin=1)
        else:
            draft = _Draft(start=previous.lineno,
                           stop=occ.lineno,
                           open_line=previous.lineno,
                           close_line=occ.lineno,
                           lead_kind=_KIND_SEED,
                           trail_kind=_KIND_PATTERN,
                           lead_origin=previous.lineno,
                           trail_origin=previous.lineno)
        drafts.append(draft)
        previous = occ
    return drafts


def _segment_by_openers(openers: list, total: int) -> list:
    """Segment the source at each opener: [b1..b2] ... [bn..EOF].

    The mirror of closer segmentation. The list starts at the first opener
    because no opener precedes it, and the final segment runs to the end of the
    source.
    """

    drafts = []
    available = len(openers)
    for index, occ in enumerate(openers):
        following = index + 1
        if following < available:
            partner = openers[following]
            draft = _Draft(start=occ.lineno,
                           stop=partner.lineno,
                           open_line=occ.lineno,
                           close_line=partner.lineno,
                           lead_kind=_KIND_SEED,
                           trail_kind=_KIND_PATTERN,
                           lead_origin=occ.lineno,
                           trail_origin=occ.lineno)
        else:
            draft = _Draft(start=occ.lineno,
                           stop=total,
                           open_line=occ.lineno,
                           lead_kind=_KIND_SEED,
                           trail_kind=_KIND_EDGE,
                           lead_origin=occ.lineno,
                           trail_origin=occ.lineno)
        drafts.append(draft)
    return drafts


def _build_delimiter_drafts(openers: Optional[list],
                            closers: Optional[list],
                            opts: Options,
                            total: int) -> list:
    """Dispatch to the delimiter-mode construction the flag set selects."""

    if openers is not None and closers is not None:
        if opts.pairing == "occurrence":
            drafts = _pair_occurrence(openers, closers)
        else:
            events = _merge_events(openers, closers)
            drafts = _pair_sed(events)
    elif closers is not None:
        drafts = _segment_by_closers(closers)
    else:
        drafts = _segment_by_openers(openers, total)
    return drafts


# --------------------------------------------------------------------------
# Steps 3 to 5
# --------------------------------------------------------------------------


def _apply_distance(drafts: list, opts: Options) -> list:
    """Step 3: reject any pattern-to-pattern connection longer than -d.

    Distance is later_lineno - earlier_lineno, so two occurrences on one line
    are distance 0 and -d 0 means same line only. Count boundaries are exempt
    because the count already is the limit, and a side that falls back to the
    edge of the source is not a connection between two found occurrences.
    A rejected connection is unresolved, which hands it to the unterminated
    policy exactly as a boundary that was never found.
    """

    limit = opts.max_distance
    if limit is not None:
        for draft in drafts:
            if draft.lead_kind == _KIND_PATTERN and draft.start is not None:
                gap = draft.lead_origin - draft.start
                if gap > limit:
                    draft.start = None
                    draft.open_line = None
            if draft.trail_kind == _KIND_PATTERN and draft.stop is not None:
                gap = draft.stop - draft.trail_origin
                if gap > limit:
                    draft.stop = None
                    draft.close_line = None
    return drafts


def _side_is_terminated(kind: str, resolved: Optional[int]) -> bool:
    """Report whether one side of a draft found the boundary it wanted.

    Only a pattern side can fail, and only by not matching or by matching
    beyond -d. A side defaulted to the edge of the source is a found boundary,
    because a single-sided invocation asks for that edge; a count side is
    always found, because the count defines it.
    """

    if kind == _KIND_PATTERN:
        settled = resolved is not None
    else:
        settled = True
    return settled


def _apply_unterminated(drafts: list, opts: Options, total: int) -> list:
    """Step 4: truncate or drop drafts whose boundary was not found.

    Truncation clamps at the edge of the source, and additionally at the -d
    limit when one is set: a connection refused for being too far away must not
    then emit lines beyond that same distance.
    """

    kept = []
    limit = opts.max_distance
    for draft in drafts:
        lead_ok = _side_is_terminated(draft.lead_kind, draft.start)
        trail_ok = _side_is_terminated(draft.trail_kind, draft.stop)
        draft.terminated = lead_ok and trail_ok
        if draft.terminated:
            kept.append(draft)
        elif opts.unterminated == "drop":
            continue
        else:
            if draft.start is None:
                floor = 1
                if limit is not None:
                    reach = draft.lead_origin - limit
                    if reach > floor:
                        floor = reach
                draft.start = floor
            if draft.stop is None:
                ceiling = total
                if limit is not None:
                    reach = draft.trail_origin + limit
                    if reach < ceiling:
                        ceiling = reach
                draft.stop = ceiling
            kept.append(draft)
    return kept


def _apply_max_count(drafts: list, opts: Options, anchor_mode: bool) -> list:
    """Cap how much of the source is selected, then stop.

    The budget is spent on the same thing -c reports: distinct match lines in
    anchor mode, so two matches on one line cost one unit and context is never
    charged; candidate ranges in delimiter mode.
    """

    limit = opts.max_count
    if limit is None:
        kept = drafts
    else:
        kept = []
        spent = 0
        seen = set()
        for draft in drafts:
            if anchor_mode:
                fresh = draft.anchor not in seen
                if fresh and spent >= limit:
                    break
                if fresh:
                    seen.add(draft.anchor)
                    spent += 1
                kept.append(draft)
            else:
                if spent >= limit:
                    break
                spent += 1
                kept.append(draft)
    return kept


def _apply_exclusions(drafts: list, opts: Options) -> list:
    """Step 5: turn drafts into Candidates, recording withheld boundary lines.

    Exclusion removes a line from one candidate's contribution; it is not a
    veto, so the same line contributed by another candidate is still emitted.
    A side with no boundary occurrence -- a count, an edge, or a truncated
    search -- has no line to withhold.
    """

    candidates = []
    for draft in drafts:
        withheld = set()
        if opts.exclude_before and draft.open_line is not None:
            withheld.add(draft.open_line)
        if opts.exclude_after and draft.close_line is not None:
            withheld.add(draft.close_line)
        frozen = frozenset(withheld)
        candidate = Candidate(start=draft.start,
                              stop=draft.stop,
                              anchor=draft.anchor,
                              excluded=frozen,
                              terminated=draft.terminated)
        candidates.append(candidate)
    return candidates


# --------------------------------------------------------------------------
# Steps 6 and 7
# --------------------------------------------------------------------------


def to_union(candidates: list, total: int, invert: bool = False) -> set:
    """Step 6: collapse the candidate list into the selected line set.

    Under invert the answer is the complement over the whole source. That is a
    single set operation on the finished set, not a second selection pass,
    which is why a line withheld by --exclude-A reappears under -v unless some
    other candidate contributed it.
    """

    chosen = set()
    for candidate in candidates:
        lowest = candidate.start
        if lowest < 1:
            lowest = 1
        highest = candidate.stop
        if highest > total:
            highest = total
        upper = highest + 1
        for lineno in range(lowest, upper):
            if lineno not in candidate.excluded:
                chosen.add(lineno)
    if invert:
        span = total + 1
        every = set(range(1, span))
        chosen = every - chosen
    return chosen


def group_contiguous(linenos) -> list:
    """Step 7: maximal ascending runs of consecutive linenos as (start, stop)."""

    ordered = sorted(linenos)
    groups = []
    first = None
    last = None
    for lineno in ordered:
        if first is None:
            first = lineno
            last = lineno
        elif lineno == last + 1:
            last = lineno
        else:
            span = (first, last)
            groups.append(span)
            first = lineno
            last = lineno
    if first is not None:
        span = (first, last)
        groups.append(span)
    return groups


def _tally(candidates: list, selected: set, anchor_mode: bool, opts: Options) -> int:
    """Count what -c reports: match lines, or completed ranges.

    Context is never counted. Under invert the reported figure is the size of
    the emitted set, because that is the only thing left to count once the
    answer is the complement.
    """

    if opts.invert:
        total = len(selected)
    elif anchor_mode:
        seen = set()
        for candidate in candidates:
            if candidate.anchor is not None:
                seen.add(candidate.anchor)
        total = len(seen)
    else:
        total = 0
        for candidate in candidates:
            if candidate.terminated:
                total += 1
    return total


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def _check_nonnegative(value, label: str) -> None:
    """Reject a negative line count, distance or cap."""

    if value is not None:
        if not isinstance(value, int) or isinstance(value, bool):
            message = label + " must be an integer, got " + type(value).__name__
            raise OptionError(message)
        if value < 0:
            shown = str(value)
            message = label + " must not be negative, got " + shown
            raise OptionError(message)


def _validate_options(opts: Options) -> None:
    """Reject option sets the engine has no defined behavior for."""

    if opts.pairing not in ("sed", "occurrence"):
        message = "pairing must be 'sed' or 'occurrence', got " + repr(opts.pairing)
        raise OptionError(message)
    if opts.unterminated not in ("truncate", "drop"):
        message = ("unterminated must be 'truncate' or 'drop', got "
                   + repr(opts.unterminated))
        raise OptionError(message)
    if opts.emit not in ("union", "ranges"):
        message = "emit must be 'union' or 'ranges', got " + repr(opts.emit)
        raise OptionError(message)
    if opts.invert and opts.emit == "ranges":
        raise OptionError(
            "invert needs emit='union': the complement of an ordered list of "
            "overlapping ranges is not defined")
    _check_nonnegative(opts.max_distance, "max_distance")
    _check_nonnegative(opts.after_lines, "after_lines")
    _check_nonnegative(opts.before_lines, "before_lines")
    _check_nonnegative(opts.max_count, "max_count")
    if opts.after is not None and opts.after_lines is not None:
        raise OptionError("after and after_lines are mutually exclusive")
    if opts.before is not None and opts.before_lines is not None:
        raise OptionError("before and before_lines are mutually exclusive")
    texts = _pattern_texts(opts)
    if not texts:
        if opts.after_lines is not None or opts.before_lines is not None:
            raise OptionError(
                "a line count needs a -P pattern to count from; delimiter mode "
                "builds ranges from boundary patterns only")
        if opts.after is None and opts.before is None:
            raise OptionError(
                "nothing to search for: supply a -P pattern, or a -A or -B "
                "boundary pattern")


def _dedupe_candidates(candidates: list) -> list:
    """Drop candidates identical to one already kept, preserving order.

    Two occurrences on one line resolve to the same boundary and so produce the
    same span twice, which is noise once the list is rendered as records. A
    differing anchor makes two candidates distinct even at the same span.
    """

    seen = set()
    unique = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def search(lines: Sequence[str], opts: Options) -> Result:
    """Run the algorithm over one source. Pure; no I/O.

    lines excludes line terminators and lineno is index + 1. Ranges never cross
    sources because one call sees exactly one source.
    """

    _validate_options(opts)
    total = len(lines)
    primary = _compile_primary(opts)
    opener_regex = None
    if opts.before is not None:
        opener_regex = _compile_pattern(opts.before, opts, "-B")
    closer_regex = None
    if opts.after is not None:
        closer_regex = _compile_pattern(opts.after, opts, "-A")
    matches = find_occurrences(lines, primary)
    openers = None
    if opener_regex is not None:
        openers = find_occurrences(lines, opener_regex)
    closers = None
    if closer_regex is not None:
        closers = find_occurrences(lines, closer_regex)
    anchor_mode = primary is not None
    if anchor_mode:
        drafts = _build_anchor_drafts(matches, openers, closers, opts, total)
    else:
        drafts = _build_delimiter_drafts(openers, closers, opts, total)
    measured = _apply_distance(drafts, opts)
    settled = _apply_unterminated(measured, opts, total)
    capped = _apply_max_count(settled, opts, anchor_mode)
    resolved = _apply_exclusions(capped, opts)
    candidates = _dedupe_candidates(resolved)
    selected = to_union(candidates, total, opts.invert)
    groups = group_contiguous(selected)
    tally = _tally(candidates, selected, anchor_mode, opts)
    result = Result(candidates=candidates,
                    selected=selected,
                    groups=groups,
                    count=tally)
    return result
