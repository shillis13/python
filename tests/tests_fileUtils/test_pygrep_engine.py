"""Engine tests for pygrep, derived solely from pygrep_spec.md (v5).

Target: the frozen API contract in Sec 9.1 --
    search(lines: Sequence[str], opts: Options) -> Result

Every test is a literal list of input lines, an Options object, and an
assertion about Result.  Nothing private is touched.  ASCII only.

Naming convention:
    test_s31_<row>      one row of the Sec 3.1 anchor-mode table
    test_s32_<row>      one row of the Sec 3.2 delimiter-mode table
    test_r<N>_<what>    ruling R<N> of Sec 4
"""

import pytest

from file_utils.lib_pygrep import search, Options, Occurrence, Candidate, Result


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def ranges_of(result):
    """The --emit ranges rendering: candidate spans, in source order."""
    return [(c.start, c.stop) for c in result.candidates]


def excluded_of(result):
    return [set(c.excluded) for c in result.candidates]


# ---------------------------------------------------------------------------
# Sec 9.1 -- the frozen dataclasses themselves
# ---------------------------------------------------------------------------

def test_frozen_api_occurrence_shape():
    o = Occurrence(lineno=3, start_col=4, end_col=7)
    assert (o.lineno, o.start_col, o.end_col) == (3, 4, 7)


def test_frozen_api_candidate_defaults():
    c = Candidate(start=2, stop=5)
    assert (c.start, c.stop) == (2, 5)
    assert c.anchor is None
    assert c.excluded == frozenset()
    assert c.terminated is True


def test_frozen_api_options_defaults():
    o = Options()
    assert o.pattern == ()
    assert o.after is None and o.before is None
    assert o.after_lines is None and o.before_lines is None
    assert o.max_distance is None
    assert o.pairing == "sed"
    assert o.unterminated == "truncate"
    assert o.exclude_after is False and o.exclude_before is False
    assert o.emit == "union"
    assert o.invert is False
    assert o.ignore_case is False and o.word is False and o.line_regexp is False
    assert o.max_count is None


def test_frozen_api_result_shape():
    r = search(["foo"], Options(pattern=("foo",)))
    assert isinstance(r, Result)
    assert isinstance(r.candidates, list)
    assert isinstance(r.selected, set)
    assert isinstance(r.groups, list)
    assert isinstance(r.count, int)


# ---------------------------------------------------------------------------
# Sec 3.1 -- anchor mode candidate construction, one test per table row
# ---------------------------------------------------------------------------

ANCHOR_LINES = [
    "head",          # 1
    "def alpha",     # 2
    "  x",           # 3
    "  TODO here",   # 4
    "  y",           # 5
    "",              # 6
    "tail",          # 7
]


def test_s31_row_p_only_match_line_only():
    """-P p  ->  the match line only."""
    r = search(ANCHOR_LINES, Options(pattern=("TODO",)))
    assert ranges_of(r) == [(4, 4)]
    assert sorted(r.selected) == [4]
    assert r.groups == [(4, 4)]
    assert r.count == 1


def test_s31_row_p_after_count():
    """-P p -A n  ->  match .. match+n."""
    r = search(ANCHOR_LINES, Options(pattern=("TODO",), after_lines=2))
    assert ranges_of(r) == [(4, 6)]
    assert sorted(r.selected) == [4, 5, 6]
    assert r.groups == [(4, 6)]


def test_s31_row_p_before_count():
    """-P p -B n  ->  match-n .. match."""
    r = search(ANCHOR_LINES, Options(pattern=("TODO",), before_lines=2))
    assert ranges_of(r) == [(2, 4)]
    assert sorted(r.selected) == [2, 3, 4]


def test_s31_row_p_context_count():
    """-P p -C n  ->  match-n .. match+n.  Sec 9.1: the caller expands -C
    into after_lines + before_lines with the same value."""
    r = search(ANCHOR_LINES,
               Options(pattern=("TODO",), before_lines=2, after_lines=2))
    assert ranges_of(r) == [(2, 6)]
    assert sorted(r.selected) == [2, 3, 4, 5, 6]


def test_s31_row_p_after_pattern():
    """-P p -A a  ->  match .. nearest following closer, inclusive."""
    r = search(ANCHOR_LINES, Options(pattern=("TODO",), after="^$"))
    assert ranges_of(r) == [(4, 6)]
    assert sorted(r.selected) == [4, 5, 6]


def test_s31_row_p_before_pattern():
    """-P p -B b  ->  nearest preceding opener .. match, inclusive."""
    r = search(ANCHOR_LINES, Options(pattern=("TODO",), before="^def "))
    assert ranges_of(r) == [(2, 4)]
    assert sorted(r.selected) == [2, 3, 4]


def test_s31_row_p_before_and_after_pattern():
    """-P p -B b -A a  ->  opener .. match .. closer."""
    r = search(ANCHOR_LINES,
               Options(pattern=("TODO",), before="^def ", after="^$"))
    assert ranges_of(r) == [(2, 6)]
    assert sorted(r.selected) == [2, 3, 4, 5, 6]
    assert r.count == 1


def test_s31_row_p_context_pattern():
    """-P p -C c  ==  -P p -B c -A c."""
    lines = ["---", "a", "TODO", "b", "---", "z"]
    r = search(lines, Options(pattern=("TODO",), before="^---$", after="^---$"))
    assert ranges_of(r) == [(1, 5)]
    assert sorted(r.selected) == [1, 2, 3, 4, 5]


def test_s31_mixed_count_and_pattern_is_legal():
    """Sec 3.1: '-P p -B 3 -A ^}' is three lines back, forward to the brace."""
    lines = ["a", "b", "c", "TODO", "d", "}", "e"]
    r = search(lines, Options(pattern=("TODO",), before_lines=3, after="^\\}"))
    assert ranges_of(r) == [(1, 6)]
    assert sorted(r.selected) == [1, 2, 3, 4, 5, 6]


def test_s31_count_boundaries_clamp_at_source_edges():
    lines = ["a", "foo", "b"]
    r = search(lines, Options(pattern=("foo",), before_lines=5, after_lines=5))
    assert ranges_of(r) == [(1, 3)]
    assert sorted(r.selected) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Sec 3.2 -- delimiter mode candidate construction, one test per table row
# ---------------------------------------------------------------------------

def test_s32_row_before_and_after_pairs_per_pairing():
    """-B b -A a  ->  pair openers with closers per --pairing."""
    lines = ["x", "BEGIN", "body", "END", "y"]
    r = search(lines, Options(before="^BEGIN", after="^END"))
    assert ranges_of(r) == [(2, 4)]
    assert sorted(r.selected) == [2, 3, 4]
    assert r.groups == [(2, 4)]
    assert r.count == 1          # R10: completed candidate ranges


def test_s32_row_context_pattern_self_paired():
    """-C c  ==  -B c -A c, self-paired.  R6: pairs occurrences 1-2, 3-4."""
    lines = ["x", "M", "a", "M", "b", "M", "c", "M"]
    r = search(lines, Options(before="^M$", after="^M$"))
    assert ranges_of(r) == [(2, 4), (6, 8)]
    assert sorted(r.selected) == [2, 3, 4, 6, 7, 8]
    assert r.groups == [(2, 4), (6, 8)]
    assert r.count == 2


def test_s32_row_after_alone_segments_ranges():
    """-A a alone  ->  [BOF..a1] [a1..a2] ... [a_n-1..a_n]."""
    lines = ["a", "b", "STOP", "c", "STOP", "d"]
    r = search(lines, Options(after="^STOP$", emit="ranges"))
    assert ranges_of(r) == [(1, 3), (3, 5)]
    assert r.count == 2


def test_s32_row_after_alone_union_is_bof_to_last_closer():
    """Sec 3.2 union table: -A a collapses to BOF..a_n."""
    lines = ["a", "b", "STOP", "c", "STOP", "d"]
    r = search(lines, Options(after="^STOP$"))
    assert sorted(r.selected) == [1, 2, 3, 4, 5]
    assert r.groups == [(1, 5)]


def test_s32_row_before_alone_segments_ranges():
    """-B b alone  ->  [b1..b2] [b2..b3] ... [b_n..EOF]."""
    lines = ["a", "GO", "b", "GO", "c"]
    r = search(lines, Options(before="^GO$", emit="ranges"))
    assert ranges_of(r) == [(2, 4), (4, 5)]
    assert r.count == 2


def test_s32_row_before_alone_union_is_first_opener_to_eof():
    """Sec 3.2 union table: -B b collapses to b1..EOF."""
    lines = ["a", "GO", "b", "GO", "c"]
    r = search(lines, Options(before="^GO$"))
    assert sorted(r.selected) == [2, 3, 4, 5]
    assert r.groups == [(2, 5)]


def test_s32_seam_lines_are_shared_between_adjacent_segments():
    """Sec 3.2: in [BOF..a1] [a1..a2] the line a1 belongs to both.
    Observable only under --emit ranges; irrelevant under union."""
    lines = ["a", "S", "b", "S", "c"]
    r = search(lines, Options(after="^S$", emit="ranges"))
    assert ranges_of(r) == [(1, 2), (2, 4)]
    shared = [span for span in ranges_of(r) if span[0] <= 2 <= span[1]]
    assert len(shared) == 2


# ---------------------------------------------------------------------------
# Sec 3.3 / R6 -- pairing
# ---------------------------------------------------------------------------

PAIR_LINES = ["B1", "B2", "A1", "A2"]
MALFORMED_LINES = ["B1", "B2", "B3", "A1", "A2"]
FIFO_LINES = ["login alice", "login bob", "logout alice", "logout bob"]
LIFO_LINES = ["login alice", "login bob", "logout bob", "logout alice"]


def test_pairing_sed_is_the_default():
    assert Options().pairing == "sed"


def test_pairing_sed_on_b1_b2_a1_a2():
    """Sec 3.3: sed  ->  B1->A1; B2 interior; A2 exterior.  Union B1..A1."""
    r = search(PAIR_LINES, Options(before="^B", after="^A", pairing="sed"))
    assert ranges_of(r) == [(1, 3)]
    assert sorted(r.selected) == [1, 2, 3]
    assert r.count == 1


def test_pairing_occurrence_on_b1_b2_a1_a2():
    """Sec 3.3: occurrence  ->  B1->A1, B2->A2.  Union B1..A2."""
    r = search(PAIR_LINES,
               Options(before="^B", after="^A", pairing="occurrence"))
    assert ranges_of(r) == [(1, 3), (2, 4)]
    assert sorted(r.selected) == [1, 2, 3, 4]
    assert r.groups == [(1, 4)]
    assert r.count == 2


def test_pairing_sed_resynchronizes_on_malformed_input():
    """Sec 3.3: given B1 B2 B3 A1 A2, sed emits B1..A1, treats B2/B3 as
    interior, and opens the next candidate at the first opener after A1 --
    there is none, so A2 is exterior."""
    r = search(MALFORMED_LINES, Options(before="^B", after="^A", pairing="sed"))
    assert ranges_of(r) == [(1, 4)]
    assert sorted(r.selected) == [1, 2, 3, 4]
    assert r.count == 1


def test_pairing_occurrence_shifts_on_malformed_input():
    """Sec 3.3: occurrence pairs B1->A1 and B2->A2 -- the second candidate
    spans a record boundary.  B3 never pairs; --unterminated=drop discards it
    so the shift is visible without depending on the truncate clamp point."""
    r = search(MALFORMED_LINES,
               Options(before="^B", after="^A", pairing="occurrence",
                       unterminated="drop"))
    assert ranges_of(r) == [(1, 4), (2, 5)]
    assert sorted(r.selected) == [1, 2, 3, 4, 5]
    assert r.count == 2


def test_pairing_occurrence_fifo_login_logout_is_right():
    """Sec 3.3 FIFO example: B1->A1 = alice->alice, B2->A2 = bob->bob."""
    r = search(FIFO_LINES,
               Options(before="^login ", after="^logout ",
                       pairing="occurrence", emit="ranges"))
    assert ranges_of(r) == [(1, 3), (2, 4)]
    first, second = r.candidates[0], r.candidates[1]
    assert FIFO_LINES[first.start - 1] == "login alice"
    assert FIFO_LINES[first.stop - 1] == "logout alice"
    assert FIFO_LINES[second.start - 1] == "login bob"
    assert FIFO_LINES[second.stop - 1] == "logout bob"


def test_pairing_occurrence_lifo_gives_the_documented_wrong_answer():
    """Sec 3.3 LIFO example, pinned as a known limitation: occurrence pairing
    connects 'login alice' to 'logout bob' and 'login bob' to 'logout alice'.
    No v1 mode is right here; the line spans are asserted so the limitation is
    pinned rather than discovered later."""
    r = search(LIFO_LINES,
               Options(before="^login ", after="^logout ",
                       pairing="occurrence", emit="ranges"))
    assert ranges_of(r) == [(1, 3), (2, 4)]
    first, second = r.candidates[0], r.candidates[1]
    assert LIFO_LINES[first.start - 1] == "login alice"
    assert LIFO_LINES[first.stop - 1] == "logout bob"        # WRONG, on purpose
    assert LIFO_LINES[second.start - 1] == "login bob"
    assert LIFO_LINES[second.stop - 1] == "logout alice"     # WRONG, on purpose


def test_pairing_sed_on_fifo_login_logout_is_wrong():
    """Sec 3.3: 'a real use case that sed handles wrong' -- sed emits only the
    first record and treats the second login as interior."""
    r = search(FIFO_LINES,
               Options(before="^login ", after="^logout ", pairing="sed"))
    assert ranges_of(r) == [(1, 3)]
    assert sorted(r.selected) == [1, 2, 3]
    assert r.count == 1


# ---------------------------------------------------------------------------
# Sec 4 -- rulings
# ---------------------------------------------------------------------------

def test_r1_b_is_leading_edge_a_is_trailing_edge():
    """R1: -B b -A a emits b through a, in both modes."""
    lines = ["a", "OPEN", "b", "CLOSE", "c"]
    delim = search(lines, Options(before="^OPEN$", after="^CLOSE$"))
    assert ranges_of(delim) == [(2, 4)]

    anchor_lines = ["OPEN", "foo", "CLOSE"]
    anchor = search(anchor_lines,
                    Options(pattern=("foo",), before="^OPEN$", after="^CLOSE$"))
    assert ranges_of(anchor) == [(1, 3)]
    assert anchor.candidates[0].anchor == 2


# R2 -- polymorphic -A/-B/-C argument parsing ("^\d+$" is a count, anything
# else is a pattern; --after-lines vs --after-pattern).  NOT TESTABLE at the
# engine layer: Sec 9.1 gives the engine two separate, already-disambiguated
# fields (`after` vs `after_lines`), so the polymorphism has been resolved by
# the CLI before search() is ever called.  Covered by the CLI suite.


def test_r3_nearest_boundary_wins_in_anchor_mode():
    """R3: -A takes the first matching line going forward, -B the first going
    backward -- not the outermost."""
    lines = ["MARK", "MARK", "foo", "MARK", "MARK"]
    r = search(lines,
               Options(pattern=("foo",), before="^MARK$", after="^MARK$"))
    assert ranges_of(r) == [(2, 4)]
    assert sorted(r.selected) == [2, 3, 4]


def test_r4_anchor_does_not_close_itself():
    """R4, first table row: with '-P foo -A foo' and a line holding exactly one
    'foo', the occurrence is the anchor and cannot also close; search continues
    to the next line.  '-P foo -A foo' still means 'foo to the next foo'."""
    lines = ["foo", "bar", "foo"]
    r = search(lines, Options(pattern=("foo",), after="foo"))
    spans = ranges_of(r)
    assert (1, 1) not in spans          # the anchor did NOT close itself
    assert (1, 3) in spans              # it closed on the next foo
    assert sorted(r.selected) == [1, 2, 3]
    assert r.count == 2                 # R10: two accepted -P match lines


def test_r4_second_occurrence_on_the_same_line_may_close():
    """R4, second table row: 'foo bar foo' has two occurrences; foo#1 anchors
    and foo#2 closes -- a one-line range at distance 0.  This is the case the
    line-based v1-v3 rule silently hid."""
    lines = ["foo bar foo"]
    r = search(lines, Options(pattern=("foo",), after="foo"))
    assert (1, 1) in ranges_of(r)
    assert any(c.terminated and (c.start, c.stop) == (1, 1)
               for c in r.candidates)
    assert sorted(r.selected) == [1]
    assert r.count == 1                 # R10 counts match LINES, not occurrences


def test_r4_one_line_two_occurrences_differs_from_one_line_one_occurrence():
    """The distinction R4 exists to make: a line with one match behaves
    differently from a line with two, under the identical Options."""
    o = Options(pattern=("foo",), after="foo")
    one = search(["foo", "zzz"], o)
    two = search(["foo bar foo", "zzz"], o)
    assert not any(c.terminated and (c.start, c.stop) == (1, 1)
                   for c in one.candidates)
    assert any(c.terminated and (c.start, c.stop) == (1, 1)
               for c in two.candidates)


def test_r4_different_patterns_on_one_line_give_a_one_line_range():
    """R4, third table row: 'foo bar' with '-P foo -A bar' -- different
    patterns, different occurrences: one-line range."""
    r = search(["foo bar"], Options(pattern=("foo",), after="bar"))
    assert ranges_of(r) == [(1, 1)]
    assert sorted(r.selected) == [1]


def test_r4_backward_search_uses_an_earlier_column_on_the_anchor_line():
    """R4: backward means an earlier column on the anchor's own line, then
    prior lines."""
    r = search(["bar foo"], Options(pattern=("foo",), before="bar"))
    assert ranges_of(r) == [(1, 1)]
    assert sorted(r.selected) == [1]


def test_r4_earlier_column_does_not_satisfy_a_forward_search():
    """R4: a boundary occurrence at an earlier column than the anchor must not
    satisfy a forward search.  'bar' on line 1 sits left of 'foo', so the
    closer is the 'bar' on line 3."""
    lines = ["bar foo", "x", "bar"]
    r = search(lines, Options(pattern=("foo",), after="bar"))
    assert ranges_of(r) == [(1, 3)]
    assert sorted(r.selected) == [1, 2, 3]


def test_r4_later_column_does_not_satisfy_a_backward_search():
    """R4, mirror image: 'bar' at a later column than the anchor cannot open."""
    lines = ["bar", "x", "foo bar"]
    r = search(lines, Options(pattern=("foo",), before="bar"))
    assert ranges_of(r) == [(1, 3)]
    assert sorted(r.selected) == [1, 2, 3]


def test_r4_scope_is_one_candidate_so_a_seam_occurrence_fills_two_roles():
    """R4 binds WITHIN a candidate range.  Across candidates an occurrence may
    close one and open the next -- the Sec 3.2 seam.  Not a violation."""
    lines = ["a", "S", "b", "S", "c"]
    r = search(lines, Options(after="^S$", emit="ranges"))
    assert ranges_of(r) == [(1, 2), (2, 4)]
    assert r.candidates[0].stop == r.candidates[1].start == 2


def test_r5_unterminated_truncate_clamps_at_end_of_source():
    """R5: truncate clamps at start/end of source."""
    lines = ["a", "foo", "b", "c"]
    r = search(lines, Options(pattern=("foo",), after="^NOPE$",
                              unterminated="truncate"))
    assert ranges_of(r) == [(2, 4)]
    assert r.candidates[0].terminated is False
    assert sorted(r.selected) == [2, 3, 4]


def test_r5_unterminated_truncate_clamps_at_start_of_source():
    lines = ["a", "b", "foo", "c"]
    r = search(lines, Options(pattern=("foo",), before="^NOPE$",
                              unterminated="truncate"))
    assert ranges_of(r) == [(1, 3)]
    assert r.candidates[0].terminated is False


def test_r5_unterminated_drop_discards_the_candidate():
    """R5: drop discards the candidate entirely."""
    lines = ["a", "foo", "b", "c"]
    r = search(lines, Options(pattern=("foo",), after="^NOPE$",
                              unterminated="drop"))
    assert ranges_of(r) == []
    assert r.selected == set()
    assert r.groups == []


def test_r5_exceeding_max_distance_is_treated_as_boundary_not_found():
    """R5: 'Exceeding -d is treated identically to boundary not found, so one
    policy covers both.'  Asserted with drop, where the two readings of the
    truncate clamp point cannot differ."""
    lines = ["foo", "a", "b", "c", "MARK"]
    kept = search(lines, Options(pattern=("foo",), after="^MARK$",
                                 max_distance=4, unterminated="drop"))
    assert ranges_of(kept) == [(1, 5)]

    dropped = search(lines, Options(pattern=("foo",), after="^MARK$",
                                    max_distance=3, unterminated="drop"))
    assert ranges_of(dropped) == []
    assert dropped.selected == set()


def test_r5_unterminated_default_is_truncate():
    assert Options().unterminated == "truncate"


def test_r6_pairing_default_is_sed_and_c_alone_pairs_1_2_then_3_4():
    """R6: default sed; '-C c alone therefore pairs occurrences 1-2, 3-4'."""
    assert Options().pairing == "sed"
    lines = ["M", "a", "M", "b", "M", "c", "M"]
    r = search(lines, Options(before="^M$", after="^M$"))
    assert ranges_of(r) == [(1, 3), (5, 7)]
    assert sorted(r.selected) == [1, 2, 3, 5, 6, 7]
    assert r.groups == [(1, 3), (5, 7)]
    assert r.count == 2


def test_r7_unterminated_range_clamps_at_the_end_of_this_source():
    """R7: candidate ranges never cross sources; an unterminated range at EOF
    does not continue into the next file.  search() is per-source (Sec 9.1),
    so the engine-observable half of R7 is that truncate stops at len(lines).
    The cross-file half is CLI-level."""
    lines = ["BEGIN", "a"]
    r = search(lines, Options(before="^BEGIN$", after="^END$"))
    assert ranges_of(r) == [(1, 2)]
    assert r.candidates[0].terminated is False
    assert max(r.selected) == len(lines)


def test_r8_exclusion_removes_a_contribution_not_a_line():
    """R8: --exclude-B drops the opener from THAT candidate's contribution.
    With occurrence pairing over B1 B2 A1 A2 the candidates overlap, so line 2
    is excluded by its own candidate and included by the other -- and is
    therefore emitted."""
    r = search(PAIR_LINES,
               Options(before="^B", after="^A", pairing="occurrence",
                       exclude_before=True))
    assert ranges_of(r) == [(1, 3), (2, 4)]
    assert excluded_of(r) == [{1}, {2}]
    assert sorted(r.selected) == [2, 3, 4]
    assert r.groups == [(2, 4)]


def test_r8_exclusion_still_requires_the_boundary_to_be_found():
    """R8: 'The boundary must still be found, or --unterminated applies.'"""
    lines = ["a", "foo", "b"]
    r = search(lines, Options(pattern=("foo",), after="^NOPE$",
                              exclude_after=True, unterminated="drop"))
    assert ranges_of(r) == []
    assert r.selected == set()


def test_r8_exclude_both_bounds_strips_only_the_boundary_lines():
    """--exclude-bounds is expanded by the caller into both flags (Sec 9.1)."""
    lines = ["x", "BEGIN", "body", "END", "y"]
    r = search(lines, Options(before="^BEGIN", after="^END",
                              exclude_before=True, exclude_after=True))
    assert ranges_of(r) == [(2, 4)]
    assert excluded_of(r) == [{2, 4}]
    assert sorted(r.selected) == [3]
    assert r.groups == [(3, 3)]


def test_r8_anchor_mode_exclusion_then_union_across_candidates():
    """Exclusion followed by union in anchor mode: line 2 is candidate 1's
    closer (excluded there) and plain context for candidate 2 (included)."""
    lines = ["foo", "end", "foo"]
    r = search(lines, Options(pattern=("foo",), after="^end$", before_lines=1,
                              exclude_after=True))
    assert excluded_of(r)[0] == {2}
    assert sorted(r.selected) == [1, 2, 3]
    assert r.groups == [(1, 3)]


def test_r9_invert_is_a_set_complement():
    """R9: compute S exactly as without -v, then emit D minus S."""
    lines = ["a", "foo", "c", "d", "e"]
    plain = search(lines, Options(pattern=("foo",)))
    assert sorted(plain.selected) == [2]

    inverted = search(lines, Options(pattern=("foo",), invert=True))
    assert sorted(inverted.selected) == [1, 3, 4, 5]
    assert inverted.groups == [(1, 1), (3, 5)]
    assert plain.selected.isdisjoint(inverted.selected)
    assert plain.selected | inverted.selected == set(range(1, len(lines) + 1))


def test_r9_line_dropped_by_exclusion_reappears_under_invert():
    """R9, the surprising consequence: a line dropped by --exclude-B is not in
    S, so the complement puts it back."""
    lines = ["B1", "x", "A1"]
    plain = search(lines, Options(before="^B", after="^A", exclude_before=True))
    assert sorted(plain.selected) == [2, 3]

    inverted = search(lines, Options(before="^B", after="^A",
                                     exclude_before=True, invert=True))
    assert sorted(inverted.selected) == [1]
    assert inverted.groups == [(1, 1)]


def test_r9_excluded_line_does_not_reappear_when_another_candidate_includes_it():
    """R9: '...unless another candidate includes it.'"""
    inverted = search(PAIR_LINES,
                      Options(before="^B", after="^A", pairing="occurrence",
                              exclude_before=True, invert=True))
    assert sorted(inverted.selected) == [1]      # line 2 stayed in S


def test_r9_invert_over_delimiter_mode_complements_the_whole_source():
    lines = ["a", "GO", "b", "GO", "c"]
    r = search(lines, Options(before="^GO$", invert=True))
    assert sorted(r.selected) == [1]
    assert r.groups == [(1, 1)]


# R9, second consequence -- '-v requires --emit union; -v --emit ranges exits
# 2'.  NOT TESTABLE at the engine layer: Sec 8 defines exit codes and Sec 9.1
# gives search() no way to report one.  Flag-combination rejection is listed in
# Sec 9 as pygrep.py's responsibility.  Covered by the CLI suite.


def test_r10_count_in_anchor_mode_is_accepted_match_lines():
    """R10: in anchor mode -c counts accepted -P match lines; context is never
    counted."""
    lines = ["foo", "a", "b", "foo", "c"]
    r = search(lines, Options(pattern=("foo",), after_lines=1))
    assert sorted(r.selected) == [1, 2, 4, 5]
    assert r.count == 2


def test_r10_count_in_anchor_mode_excludes_dropped_candidates():
    """'accepted' -P match lines: a candidate discarded by --unterminated=drop
    contributes nothing, so its match line is not counted."""
    lines = ["foo", "a", "MARK", "b", "foo", "c"]
    r = search(lines, Options(pattern=("foo",), after="^MARK$",
                              unterminated="drop"))
    assert ranges_of(r) == [(1, 3)]
    assert r.count == 1


def test_r10_count_in_delimiter_mode_is_completed_candidate_ranges():
    """R10: in delimiter mode -c counts completed candidate ranges."""
    lines = ["BEGIN", "a", "END", "b", "BEGIN", "c", "END"]
    r = search(lines, Options(before="^BEGIN$", after="^END$"))
    assert ranges_of(r) == [(1, 3), (5, 7)]
    assert r.count == 2


def test_r10_count_in_delimiter_mode_ignores_incomplete_candidates():
    lines = ["BEGIN", "a", "END", "b", "BEGIN", "c"]
    r = search(lines, Options(before="^BEGIN$", after="^END$"))
    assert r.candidates[0].terminated is True
    assert r.candidates[1].terminated is False
    assert r.count == 1


# R11 -- '-o is incompatible with any boundary flag, exit 2'.  NOT TESTABLE at
# the engine layer: Options (Sec 9.1) has no only_matching field at all, and
# exit codes belong to pygrep.py.  Covered by the CLI suite.

# R12 -- '-C is incompatible with -A or -B, exit 2'.  NOT TESTABLE at the
# engine layer: Sec 9.1 states plainly that '-C is expanded by the caller into
# after + before' and 'the engine never sees -C'.  Covered by the CLI suite.


def test_r13_multiple_primary_patterns_are_ord():
    """R13, the one engine-visible half: '-P is repeatable and multiple values
    are OR'd'.  The rest of R13 -- patterns are never positional, a positional
    '-' means stdin -- is argument parsing and is CLI-level."""
    lines = ["alpha", "beta", "gamma"]
    r = search(lines, Options(pattern=("alpha", "gamma")))
    assert sorted(r.selected) == [1, 3]
    assert r.groups == [(1, 1), (3, 3)]
    assert r.count == 2


def test_r13_ord_patterns_both_matching_one_line_count_that_line_once():
    lines = ["alpha gamma", "beta"]
    r = search(lines, Options(pattern=("alpha", "gamma")))
    assert sorted(r.selected) == [1]
    assert r.count == 1


def test_r14_engine_accepts_any_sequence_of_str():
    """R14: 'The engine takes a Sequence[str], so there is no streaming.'  The
    memory characteristic itself is not assertable; the accepted input type is.
    A tuple is a Sequence and must work exactly as a list does."""
    as_list = search(["a", "foo", "b"], Options(pattern=("foo",)))
    as_tuple = search(("a", "foo", "b"), Options(pattern=("foo",)))
    assert as_tuple.selected == as_list.selected
    assert ranges_of(as_tuple) == ranges_of(as_list)


def test_r15_distance_is_line_number_difference_adjacent_is_one():
    """R15: distance is later_line - earlier_line; adjacent lines are 1."""
    lines = ["foo", "bar"]
    ok = search(lines, Options(pattern=("foo",), after="bar", max_distance=1,
                               unterminated="drop"))
    assert ranges_of(ok) == [(1, 2)]

    too_far = search(lines, Options(pattern=("foo",), after="bar",
                                    max_distance=0, unterminated="drop"))
    assert ranges_of(too_far) == []


def test_r15_two_occurrences_on_one_line_are_distance_zero():
    """R15: two occurrences on the same line are distance 0."""
    r = search(["foo bar foo"],
               Options(pattern=("foo",), after="foo", max_distance=0,
                       unterminated="drop"))
    assert (1, 1) in ranges_of(r)


def test_r15_max_distance_has_no_effect_on_count_boundaries():
    """R15: '-d constrains pattern boundaries only and has no effect on count
    boundaries, where the count already is the limit.'"""
    lines = ["foo", "a", "b", "c"]
    r = search(lines, Options(pattern=("foo",), after_lines=3, max_distance=1))
    assert ranges_of(r) == [(1, 4)]
    assert sorted(r.selected) == [1, 2, 3, 4]


def test_r15_max_distance_constrains_only_the_pattern_side_of_a_mixed_range():
    lines = ["a", "b", "foo", "c", "d", "MARK"]
    r = search(lines, Options(pattern=("foo",), before_lines=2, after="^MARK$",
                              max_distance=1, unterminated="drop"))
    assert ranges_of(r) == []           # the -A side failed, so nothing remains


def test_r16_max_distance_zero_is_legal_and_means_same_line_only():
    """R16: '-d 0 is legal and means same line only.'  No special case."""
    same_line = search(["foo bar foo"],
                       Options(pattern=("foo",), after="foo", max_distance=0,
                               unterminated="drop"))
    assert (1, 1) in ranges_of(same_line)

    next_line = search(["foo", "foo"],
                       Options(pattern=("foo",), after="foo", max_distance=0,
                               unterminated="drop"))
    assert ranges_of(next_line) == []
    assert next_line.selected == set()


def test_r16_max_distance_zero_in_delimiter_mode():
    lines = ["BEGIN x END", "y", "BEGIN", "z", "END"]
    r = search(lines, Options(before="BEGIN", after="END", max_distance=0,
                              unterminated="drop"))
    assert ranges_of(r) == [(1, 1)]
    assert sorted(r.selected) == [1]


def test_r17_regex_dialect_is_python_re():
    """R17: 'The regex dialect is Python re, always.'  Constructs POSIX ERE has
    no equivalent for -- non-capturing groups, named groups, lookaround -- must
    compile and behave as Python does."""
    lines = ["foobar", "foobaz", "quux"]
    lookahead = search(lines, Options(pattern=("foo(?=bar)",)))
    assert sorted(lookahead.selected) == [1]

    named = search(lines, Options(pattern=("(?P<head>foo)ba(?:z)",)))
    assert sorted(named.selected) == [2]


def test_r17_alternation_is_leftmost_first_not_leftmost_longest():
    """R17: 'POSIX ERE is leftmost-longest; Python is leftmost-first with
    ordered alternation.'  Observable through R4: the shorter alternative wins,
    so the anchor occurrence ends earlier and a later-column closer exists."""
    r = search(["foofoobar"], Options(pattern=("foo|foofoo",), after="bar"))
    assert ranges_of(r)[0] == (1, 1)


def test_r18_empty_boundary_pattern_is_valid_and_governed_by_r4():
    """R18: '-B "" is a valid regex; under Python re it yields a zero-width
    occurrence at every column, so R4 governs which of them can serve as the
    boundary.'  The anchor here starts at column 2, so an earlier column on its
    own line exists and the nearest one wins (R3)."""
    r = search(["x beta"], Options(pattern=("beta",), before=""))
    assert ranges_of(r) == [(1, 1)]
    assert sorted(r.selected) == [1]


def test_r18_empty_primary_pattern_matches_every_line():
    """R18: an empty pattern is a valid regex, not a missing one.  Zero-width
    occurrences exist on every line, including an empty one."""
    lines = ["a", "", "b"]
    r = search(lines, Options(pattern=("",)))
    assert sorted(r.selected) == [1, 2, 3]
    assert r.groups == [(1, 3)]
    assert r.count == 3


def test_r18_empty_closer_pattern_closes_on_the_anchor_line_if_room_exists():
    lines = ["zz foo zz", "tail"]
    r = search(lines, Options(pattern=("foo",), after=""))
    assert ranges_of(r) == [(1, 1)]


# R18, remaining halves -- 'in pygrep -A -B "", -A consumes no argument because
# -B begins the next option: a command-line error', and 'an empty
# --pattern-file contributes zero alternatives, which yields no matches and
# exit 1 -- not a parse error'.  NOT TESTABLE at the engine layer: both are
# argparse behavior plus an exit code.  The engine consequence of the empty
# pattern file -- an empty `pattern` tuple -- is not distinguishable from
# delimiter mode at this layer by design.  Covered by the CLI suite.


# ---------------------------------------------------------------------------
# Sec 2 -- emit union vs emit ranges over one overlapping input
# ---------------------------------------------------------------------------

OVERLAP_LINES = ["foo", "foo", "x"]
OVERLAP_OPTS = dict(pattern=("foo",), after_lines=1)


def test_emit_union_collapses_overlap():
    """Sec 2: 'Union collapses overlap and emits each line at most once.'"""
    r = search(OVERLAP_LINES, Options(emit="union", **OVERLAP_OPTS))
    assert sorted(r.selected) == [1, 2, 3]
    assert r.groups == [(1, 3)]


def test_emit_ranges_preserves_each_candidate_as_a_record():
    """Sec 2: 'ranges preserves each candidate as a record and may repeat
    lines.'"""
    r = search(OVERLAP_LINES, Options(emit="ranges", **OVERLAP_OPTS))
    assert ranges_of(r) == [(1, 2), (2, 3)]


def test_emit_union_and_ranges_are_different_answers():
    """Sec 2: 'These are different answers, not different renderings of one
    answer.'  Line 2 is emitted once under union and twice under ranges."""
    union = search(OVERLAP_LINES, Options(emit="union", **OVERLAP_OPTS))
    ranges = search(OVERLAP_LINES, Options(emit="ranges", **OVERLAP_OPTS))

    union_view = sorted(union.selected)
    ranges_view = [n
                   for (start, stop) in ranges_of(ranges)
                   for n in range(start, stop + 1)]
    assert union_view == [1, 2, 3]
    assert ranges_view == [1, 2, 2, 3]
    assert ranges_view != union_view
    assert ranges_view.count(2) == 2


def test_emit_ranges_still_populates_selected_and_groups():
    """Sec 9.1: 'Under emit="ranges", selected and groups are still populated;
    the CLI chooses which to render.'"""
    r = search(OVERLAP_LINES, Options(emit="ranges", **OVERLAP_OPTS))
    assert sorted(r.selected) == [1, 2, 3]
    assert r.groups == [(1, 3)]


# ---------------------------------------------------------------------------
# Boundary present / absent / exactly -d / -d + 1
# ---------------------------------------------------------------------------

DIST_LINES = ["foo", "a", "b", "c", "MARK", "d"]


def test_boundary_present_is_found():
    r = search(DIST_LINES, Options(pattern=("foo",), after="^MARK$"))
    assert ranges_of(r) == [(1, 5)]
    assert r.candidates[0].terminated is True
    assert sorted(r.selected) == [1, 2, 3, 4, 5]


def test_boundary_absent_is_unterminated():
    lines = ["foo", "a", "b"]
    r = search(lines, Options(pattern=("foo",), after="^MARK$"))
    assert r.candidates[0].terminated is False


def test_boundary_at_exactly_max_distance_is_accepted():
    """R15: distance from line 1 to line 5 is 4."""
    r = search(DIST_LINES, Options(pattern=("foo",), after="^MARK$",
                                   max_distance=4))
    assert ranges_of(r) == [(1, 5)]
    assert r.candidates[0].terminated is True
    assert sorted(r.selected) == [1, 2, 3, 4, 5]


def test_boundary_at_max_distance_plus_one_is_rejected():
    """One under the required distance: the connection is rejected at step 3.
    Asserted with --unterminated=drop so the result does not depend on where
    truncate clamps (see the truncate-clamp test below)."""
    r = search(DIST_LINES, Options(pattern=("foo",), after="^MARK$",
                                   max_distance=3, unterminated="drop"))
    assert ranges_of(r) == []
    assert r.selected == set()
    assert r.groups == []
    assert r.count == 0


def test_truncate_after_distance_rejection_clamps_at_the_max_distance_limit():
    """R5: 'truncate -- clamp at start/end of source, OR AT THE -d LIMIT.'

    AMBIGUITY (R5): the sentence also says exceeding -d is 'treated identically
    to boundary not found', which read alone would clamp at the end of source.
    The two readings differ here: -d 3 from line 1 gives (1, 4) under the
    -d-limit reading and (1, 6) under the source-edge reading.  This test takes
    the -d-limit reading, because it is the only reading under which the phrase
    'or at the -d limit' has any effect, and because clamping to EOF would make
    -d useless for its own worked example (Sec 3.4, the -d 40 stack trace)."""
    r = search(DIST_LINES, Options(pattern=("foo",), after="^MARK$",
                                   max_distance=3, unterminated="truncate"))
    assert ranges_of(r) == [(1, 4)]
    assert r.candidates[0].terminated is False
    assert sorted(r.selected) == [1, 2, 3, 4]


def test_truncate_backward_after_distance_rejection():
    """Mirror image of the above, on the -B side."""
    lines = ["MARK", "a", "b", "c", "foo"]
    r = search(lines, Options(pattern=("foo",), before="^MARK$",
                              max_distance=2, unterminated="truncate"))
    assert ranges_of(r) == [(3, 5)]
    assert r.candidates[0].terminated is False


# ---------------------------------------------------------------------------
# Degenerate inputs
# ---------------------------------------------------------------------------

def test_degenerate_empty_lines_anchor_mode():
    r = search([], Options(pattern=("foo",)))
    assert r.candidates == []
    assert r.selected == set()
    assert r.groups == []
    assert r.count == 0


def test_degenerate_empty_lines_delimiter_mode():
    r = search([], Options(before="^B", after="^A"))
    assert r.candidates == []
    assert r.selected == set()
    assert r.groups == []
    assert r.count == 0


def test_degenerate_empty_lines_under_invert():
    """D is empty, so D minus S is empty too."""
    r = search([], Options(pattern=("foo",), invert=True))
    assert r.selected == set()
    assert r.groups == []


def test_degenerate_no_match_at_all():
    lines = ["alpha", "beta", "gamma"]
    r = search(lines, Options(pattern=("zzz",)))
    assert r.candidates == []
    assert r.selected == set()
    assert r.groups == []
    assert r.count == 0


def test_degenerate_no_match_under_invert_selects_everything():
    """R9: S is empty, so D minus S is D."""
    lines = ["alpha", "beta", "gamma"]
    r = search(lines, Options(pattern=("zzz",), invert=True))
    assert sorted(r.selected) == [1, 2, 3]
    assert r.groups == [(1, 3)]


def test_degenerate_single_line_that_matches():
    r = search(["foo"], Options(pattern=("foo",)))
    assert ranges_of(r) == [(1, 1)]
    assert sorted(r.selected) == [1]
    assert r.groups == [(1, 1)]
    assert r.count == 1


def test_degenerate_single_line_with_boundaries_on_itself():
    """Everything on one line: R4 keeps the three roles distinct."""
    r = search(["B foo A"], Options(pattern=("foo",), before="B", after="A"))
    assert ranges_of(r) == [(1, 1)]
    assert sorted(r.selected) == [1]


def test_degenerate_boundary_on_the_first_line_anchor_mode():
    lines = ["MARK", "foo", "x"]
    r = search(lines, Options(pattern=("foo",), before="^MARK$"))
    assert ranges_of(r) == [(1, 2)]
    assert sorted(r.selected) == [1, 2]


def test_degenerate_boundary_on_the_last_line_anchor_mode():
    lines = ["x", "foo", "MARK"]
    r = search(lines, Options(pattern=("foo",), after="^MARK$"))
    assert ranges_of(r) == [(2, 3)]
    assert sorted(r.selected) == [2, 3]


def test_degenerate_boundary_on_the_first_line_delimiter_mode():
    """-A a alone with a single closer on line 1: [BOF..a1] is (1, 1)."""
    lines = ["STOP", "a", "b"]
    r = search(lines, Options(after="^STOP$"))
    assert ranges_of(r) == [(1, 1)]
    assert sorted(r.selected) == [1]
    assert r.groups == [(1, 1)]


def test_degenerate_boundary_on_the_last_line_delimiter_mode():
    """-B b alone with a single opener on the last line: [b1..EOF] is (3, 3)."""
    lines = ["a", "b", "GO"]
    r = search(lines, Options(before="^GO$"))
    assert ranges_of(r) == [(3, 3)]
    assert sorted(r.selected) == [3]


def test_degenerate_empty_string_lines_are_real_lines():
    """Sec 9.1: 'lines excludes line terminators.'  An empty string is a line."""
    lines = ["a", "", "b"]
    r = search(lines, Options(pattern=("^$",)))
    assert sorted(r.selected) == [2]
    assert r.count == 1


def test_degenerate_delimiter_mode_with_no_boundary_occurrences():
    lines = ["a", "b", "c"]
    r = search(lines, Options(before="^NOPE$", after="^ALSO_NOPE$"))
    assert r.candidates == []
    assert r.selected == set()
    assert r.count == 0


# ---------------------------------------------------------------------------
# groups: maximal contiguous runs, ascending (Sec 9.1, step 7)
# ---------------------------------------------------------------------------

def test_groups_are_maximal_contiguous_runs_ascending():
    lines = ["foo", "foo", "x", "foo", "x", "foo"]
    r = search(lines, Options(pattern=("foo",)))
    assert sorted(r.selected) == [1, 2, 4, 6]
    assert r.groups == [(1, 2), (4, 4), (6, 6)]


def test_groups_of_an_empty_selection_is_empty():
    r = search(["a", "b"], Options(pattern=("zzz",)))
    assert r.groups == []


# ---------------------------------------------------------------------------
# Sec 5.4 matching flags that the engine owns
# ---------------------------------------------------------------------------

def test_ignore_case():
    lines = ["FOO", "bar"]
    assert search(lines, Options(pattern=("foo",))).selected == set()
    assert sorted(search(lines,
                         Options(pattern=("foo",),
                                 ignore_case=True)).selected) == [1]


def test_word_regexp():
    lines = ["foobar", "foo bar"]
    r = search(lines, Options(pattern=("foo",), word=True))
    assert sorted(r.selected) == [2]


def test_line_regexp():
    lines = ["foo", "foo bar"]
    r = search(lines, Options(pattern=("foo",), line_regexp=True))
    assert sorted(r.selected) == [1]


def test_max_count_stops_after_n_selected_lines():
    """Sec 5.4: '-m stops after N selected lines per source.'  Asserted without
    any boundary flag so 'selected line' and 'match line' coincide."""
    lines = ["foo", "foo", "foo", "foo", "foo"]
    r = search(lines, Options(pattern=("foo",), max_count=2))
    assert sorted(r.selected) == [1, 2]
    assert r.groups == [(1, 2)]


def test_max_count_above_the_available_matches_is_a_no_op():
    lines = ["foo", "x", "foo"]
    capped = search(lines, Options(pattern=("foo",), max_count=10))
    uncapped = search(lines, Options(pattern=("foo",)))
    assert capped.selected == uncapped.selected
    assert ranges_of(capped) == ranges_of(uncapped)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
