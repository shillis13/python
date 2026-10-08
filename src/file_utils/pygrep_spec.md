# pygrep -- Specification (v5, IMPLEMENTATION SCOPE)

**Status:** v5. Design approved and trimmed to an implementation scope. No open items.
**Date:** 2026-09-23
**Author:** Inkwell (Claude Code)
**Reviewed by:** RuntimeGate (Codex), 2026-09-22 -- 4 defects accepted, 1 ruling rejected, 3 withdrawn by the reviewer
**Supersedes:** drafts v1, v2 and v3 (same path)
**Conventions:** ASCII only. Verbatim quoted material is the sole exception.

---

## Terms

Defined before use. Three are load-bearing and two are easy to confuse.

| Term | Meaning |
|---|---|
| **occurrence** | One regex match, located as `(lineno, start_col, end_col)`. Two occurrences of the same pattern can share a line. The unit the engine reasons about. |
| **match** | An occurrence of the primary pattern `-P`. |
| **opener** | An occurrence of `-B`. Starts a range. |
| **closer** | An occurrence of `-A`. Ends a range. |
| **boundary** | An opener or a closer, collectively. |
| **role** | What an occurrence is being used as within one candidate range: anchor, opener, or closer. |
| **candidate range** | One contiguous line span produced by step 2 of the algorithm, before union. |
| **range** | A contiguous span of lines that pygrep emits. `sed`'s word for `/a/,/b/`. |
| **context** | Lines inside an emitted range that are not themselves matches. grep's word. |
| **source** | One input stream: a file, or stdin, or the clipboard. Ranges never cross sources. |
| **anchor** | The line a candidate range grows outward from -- always a `-P` match. Modes without `-P` have no anchor. |
| **anchor mode** | `-P` is present. Candidate ranges grow outward from each match. |
| **delimiter mode** | No `-P`. Candidate ranges are built by pairing openers with closers. |
| **D** | The set of all lines in a source. |
| **S** | The set of lines selected for output, before `-v`. |

No new vocabulary is coined where `grep` and `sed` already name the distinction: *range* is sed's, *context* is grep's.

---

## 1. Scope, and what this replaces

**fsFind finds files. pygrep finds content.** That division is the spec's organizing constraint, and Sec 6 is written to make the seam between the two tools explicit:

```
fsFind ... | pygrep --files-from - -P 'TODO'
```

Everything about walking trees, filtering by name, honoring ignore files and detecting binaries belongs to the file finder. pygrep reads the sources it is handed and searches inside them.

The existing `pygrep.py` is a 51-line BRE-vs-ERE demo: one pattern, one file, no context, no stdin. It is not this tool and there is no sense in growing it into one.

- **`pygrep.py`** -- new tool, specified below.
- **`mingrep.py`** -- the existing file, moved verbatim. Its `bre_to_python()` is the only BRE translator in the tree and is useful in isolation.

### Migration checklist

Verified 2026-09-22. **`pygrep` resolves from three launchers on two different interpreters**, so regenerating `egg-info` proves nothing:

```
/Users/shawnhillis/myenv/bin/pygrep       -> #!/Users/shawnhillis/myenv/bin/python3.14
/Users/shawnhillis/bin/bin/pygrep         -> #!/Users/shawnhillis/myenv/bin/python3.14
/opt/homebrew/bin/pygrep                  -> #!/opt/homebrew/opt/python@3.14/bin/python3.14
mingrep                                    -> (does not exist)
```

| Step | Action |
|---|---|
| 1 | `pygrep.py` -> `mingrep.py`, verbatim, no edits |
| 2 | `setup.py`: keep `pygrep=file_utils.pygrep:main`; **add** `mingrep=file_utils.mingrep:main` |
| 3 | Reinstall the editable package so console scripts regenerate |
| 4 | **Verify all three launchers** resolve to the new code: `for p in $(which -a pygrep); do $p --version; done` |
| 5 | **Verify `mingrep`** appears on PATH and runs |
| 6 | `src/README.md:119` -- reword `pygrep`, add `mingrep` |
| 7 | `file_utils.egg-info/entry_points.txt` is generated; do not hand-edit |
| 8 | Shell aliases: none exist (checked `.bashrc`, `.bash_profile`, `.bash_functions`, `.bash_aliases`, `.zshrc`) |

Step 4 is not optional. Two launchers share one interpreter and one does not; a partial reinstall leaves a stale `pygrep` that still works, which is the worst failure mode.

---

## 2. The algorithm

One algorithm. Only **step 2** depends on which flags were given.

```
For each source independently:

  D = every line in the source

  1. Find all occurrences as (lineno, start_col, end_col): matches, openers, closers
  2. Construct candidate ranges per the active mode   <-- the ONLY mode-dependent step
  3. Reject any connection whose distance exceeds -d
  4. Apply the --unterminated policy to incomplete candidates
  5. Apply --exclude-A / --exclude-B to each candidate's contribution
  6. Emit:
       --emit union   (default)  S = union of all candidate lines
                                 output S, or (D minus S) with -v
       --emit ranges             output the candidate list in order, verbatim
  7. Group maximal contiguous emitted lines for formatting and separators
```

Three consequences, all load-bearing:

- **Exclusion is a contribution-level operation, not a veto.** A line excluded by one candidate but included by another is emitted. Why a line was included is not relevant to membership.
- **S and (D minus S) are disjoint, and together they are D.** Inversion is a single set complement at step 6, not a second selection pass. This is why there is one algorithm and not two.
- **`--emit ranges` is not a formatting option.** Union collapses overlap and emits each line at most once; ranges preserves each candidate as a record and may repeat lines. These are different answers, not different renderings of one answer.

---

## 3. Step 2 -- candidate range construction

`p` is the `-P` pattern; `a`/`b`/`c` are boundary patterns; `n` is an integer.

### 3.1 Anchor mode (`-P` present)

Each match seeds one candidate. Nearest boundary wins in each direction (R3), measured in **occurrence order**: forward means a later column on the anchor's own line, then subsequent lines; backward means an earlier column, then prior lines (R4).

| Invocation | Candidate range |
|---|---|
| `-P p` | the match line only |
| `-P p -A n` | match .. match+n |
| `-P p -B n` | match-n .. match |
| `-P p -C n` | match-n .. match+n |
| `-P p -A a` | match .. **nearest following** closer, inclusive |
| `-P p -B b` | **nearest preceding** opener .. match, inclusive |
| `-P p -B b -A a` | nearest preceding opener .. match .. nearest following closer |
| `-P p -C c` | same as `-P p -B c -A c` |

Mixed count/pattern is legal: `-P p -B 3 -A '^}'` is three lines back, forward to the next closing brace.

### 3.2 Delimiter mode (no `-P`)

**A is always the closer. B is always the opener.** A missing side defaults to the edge of the source:

```
-A a    ==    -B <BOF> -A a
-B b    ==    -B b -A <EOF>
```

| Invocation | Candidate ranges |
|---|---|
| `-B b -A a` | pair openers with closers per `--pairing` (Sec 3.3) |
| `-C c` | same as `-B c -A c`, self-paired |
| `-A a` alone | `[BOF..a1] [a1..a2] ... [a_n-1..a_n]` |
| `-B b` alone | `[b1..b2] [b2..b3] ... [b_n..EOF]` |

The single-sided forms **segment** the source at each boundary. The asymmetry is correct and not a special case: `-A a` stops at `a_n` because no closer follows it, and `-B b` starts at `b1` because no opener precedes it.

The defaulted edge is a **found** boundary, so every segment is `terminated=True` and `--unterminated=drop` discards none of them. See R5.

**Seam lines are shared** (decided). In `[BOF..a1] [a1..a2]`, line `a1` belongs to both, because "start to A1, A1 to A2" says so literally and because ranges mode already permits duplication. Observable only under `--emit ranges`; irrelevant under union.

This is the one place the seam meets R4's one-occurrence-one-role rule, and the two are reconciled by scope: R4 binds **within** a candidate range, so `a1` may close the first segment and open the second. See R4.

Under union the single-sided forms collapse to their useful degenerate answer, which resolves "first or last?" without a separate rule:

| | `--emit ranges` | `--emit union` |
|---|---|---|
| `-A a` | the segment list above | `BOF..a_n` -- up to the **last** closer |
| `-B b` | the segment list above | `b1..EOF` -- from the **first** opener |

### 3.3 Pairing (`--pairing`, delimiter mode only)

Five readings exist; **two are implemented.** For input `B1 B2 A1 A2`:

| Mode | Candidates | Union result | In v1 |
|---|---|---|---|
| `sed` **(default)** | `B1->A1`; `B2` interior; `A2` exterior | `B1..A1` | yes |
| `occurrence` | `B1->A1`, `B2->A2` | `B1..A2` | yes |
| `nested` | `B2->A1`, `B1->A2` (stack/LIFO) | `B1..A2` | no |
| `innermost` | `B2->A1`; `B1`, `A2` exterior | `B2..A1` | no |
| *(unnamed)* | `B1->A1` and `B2->A1` | `B1..A1` | no |

`sed` and `occurrence` cover both stated use cases: record extraction and FIFO entry/exit tracking. The other three are deferred. `innermost` and the unnamed reading are indistinguishable from modes already present under union, and `nested` is better served by `--pair-by GROUP` (below) than by a positional stack.

**Why `sed` is the default:** failure behavior, not precedent. Given a malformed `B1 B2 B3 A1 A2`:

- **`occurrence`** pairs `B1->A1` and `B2->A2` -- the second candidate spans a record boundary, and every pairing after the stray opener stays shifted. One anomaly silently corrupts the rest of the source.
- **`sed`** emits `B1..A1`, treats `B2`/`B3` as interior, and opens the next candidate at the first opener after `A1`. It resynchronizes at every closer.

Stray openers are routine in real logs: a retried `BEGIN` with no `END`. Self-healing beats correct-only-on-clean-input.

**Why `occurrence` exists:** tracking recurrent entries and exits -- logins, network calls, request/response pairs -- is a real use case that `sed` handles wrong. It is also a case where ordering decides which mode is correct, and the v1 answer is honest rather than complete:

```
login alice      B1     FIFO -- occurrence pairing is right
login bob        B2       B1->A1 = alice->alice
logout alice     A1       B2->A2 = bob->bob
logout bob       A2

login alice      B1     LIFO -- occurrence pairing is wrong
login bob        B2       B1->A1 = alice->BOB
logout bob       A1       B2->A2 = bob->ALICE
logout alice     A2     no v1 mode is right here -- see below
```

**Stated plainly, because it will bite someone:** all five modes pair by *position*. For correlated events, position is a heuristic and interleaving breaks every one of them -- LIFO above is only the simplest counterexample. The robust answer is pairing on a **captured key**: match `user=(\w+)` in both boundaries and connect occurrences with equal capture values. That is `--pair-by GROUP`, deferred to v2, and it is the only construction that actually solves the login/network-call case. Adding `nested` would buy one more interleaving shape while leaving the general problem unsolved, which is why it is deferred rather than implemented. Use `occurrence` knowing it is a positional approximation valid for FIFO.

**`innermost` is already the rule in anchor mode.** That is R3, which is why it is not also needed as a `--pairing` value. The two modes differ legitimately: with `-P` there is a seed to grow outward from, so *nearest* is meaningful; without one there is only a forward scan, so *first-open-wins* is.

### 3.4 Worked examples

```bash
# the whole enclosing function around every TODO
pygrep -P 'TODO' -B '^def ' -A '^$' src/*.py

# each PEM block, boundaries included
pygrep -B '-----BEGIN' -A '-----END' bundle.pem

# each PEM block as a separate record, boundaries stripped
pygrep -B '-----BEGIN' -A '-----END' --exclude-bounds --emit ranges bundle.pem

# split a file into stanzas at blank lines, one record each
pygrep -A '^$' --emit ranges config.ini

# everything up to the last checkpoint marker
pygrep -A '^CHECKPOINT' app.log

# everything from the first error onward
pygrep -B '^ERROR' app.log

# stack trace: ERROR line to the next blank line, stopping 40 lines in if none
pygrep -P 'ERROR' -A '^$' -d 40 app.log

# same, but emit nothing at all when no blank line is within 40 lines
pygrep -P 'ERROR' -A '^$' -d 40 --unterminated drop app.log

# each login/logout pair as its own record
pygrep -B 'login' -A 'logout' --pairing occurrence --emit ranges auth.log

# piped, the primary use case
journalctl -u nginx | pygrep -P 'upstream timed out' -B 2 -A '^\s*$'

# the fsFind seam: fsFind selects files, pygrep searches inside them
fsFind ... | pygrep --files-from - -P 'TODO'
```

---

## 4. Rulings

Numbered for redlining. Changes from v2 are marked.

**R1 -- A means After/closer, B means Before/opener.** Grep-compatible in anchor mode, and the same rule extends to delimiter mode: `-A` is always the trailing edge, `-B` always the leading edge. `-B b -A a` emits `b` through `a`.

**R2 -- `-A` / `-B` / `-C` are polymorphic.** *(Simplified in v3: `-F` dropped, so the dialect paragraph is gone.)* An argument matching `^\d+$` is a line count; anything else is a pattern. To match a digits-only pattern, use `--after-pattern 3` or `-A '[3]'`. Unambiguous long forms exist for both readings and should be preferred in scripts:

- `--after-lines N` / `--before-lines N` / `--context-lines N`
- `--after-pattern P` / `--before-pattern P` / `--context-pattern P`

*Reviewer note: an earlier review proposed removing polymorphism because `-F` broke the `[3]` spelling. `-F` was added by this spec, not requested; letting it veto the primary requested feature was backwards. The reviewer withdrew the point, and `-F` is now gone entirely.*

**R3 -- Nearest boundary wins, in anchor mode.** `-A` takes the first matching line going forward; `-B` the first going backward. See Sec 3.3 for why delimiter mode differs.

**R4 -- Within one candidate range, a single occurrence fills exactly one role.** *(Changed in v4: the rule was line-based in v1-v3 and is now occurrence-based. This is the correction that deletes the v3 flag.)*

Boundary search starts at the **next occurrence**, not the next line:

- forward: a later column on the anchor's own line, then subsequent lines
- backward: an earlier column on the anchor's own line, then prior lines

Consequences, all of which fall out with no flag and no user decision:

| Input, with `-P foo -A foo` | Result |
|---|---|
| `foo` (one occurrence on the line) | the occurrence is the anchor and cannot also close; search continues to the next line. `-P foo -A foo` still means "foo to the next foo" |
| `foo bar foo` (two occurrences) | `foo#1` anchors, `foo#2` closes: a one-line range at distance 0 |
| `foo bar`, with `-P foo -A bar` | different patterns, different occurrences: one-line range |

**Scope of the rule is one candidate range.** Across candidates an occurrence may close one and open the next -- that is the seam in Sec 3.2, and it is not a violation. What is forbidden is one occurrence being both ends of the *same* range, or being both the anchor and a boundary of its own range.

*v1-v3 stated this line-based ("search starts at anchor+-1"), which silently hid every second occurrence on the anchor's line: given `foo bar foo`, the closer search skipped the whole line and `foo#2` was invisible with no way to reveal it. v3 papered over this with an `--allow-self-boundary` flag whose default was the live question. At occurrence granularity the flag is unnecessary -- both readings are correct simultaneously -- so it is deleted. Credit: PianoMan, who supplied the rule as "one 'foo' shouldn't match more than one A, B, or P" and the argument that hiding the second occurrence denies the user the choice.*

**R5 -- `--unterminated=truncate|drop`, default `truncate`.** *(Trimmed in v5: `anchor` dropped.)*
- `truncate` -- clamp at start/end of source, or at the `-d` limit.
- `drop` -- discard the candidate entirely.

Exceeding `-d` is treated identically to "boundary not found", so one policy covers both. A third mode emitting only the anchor line was specified and cut: it is reachable by rerunning without the boundary flag, so it earned a mode nobody would reach for.

**A range that abuts the source edge is not unterminated.** `--unterminated` applies only when a boundary the user *asked for* was not found, or was found beyond `-d`. An edge that arrives by default under Sec 3.2 -- the implicit BOF for `-A a` alone, the implicit EOF for `-B b` alone -- is a **found** boundary: `terminated=True`, and `--unterminated=drop` does not discard it. Likewise a count boundary clamped at the source edge is terminated, because a count boundary is always found; clamping is arithmetic, not failure.

*Wording defect corrected in v6. This paragraph previously read "an unterminated range is normal and intended -- `-B b` alone deliberately runs to EOF", using "unterminated" loosely to mean "runs to the edge". Two agents deriving independently from the spec split on exactly that word: the test suite read Sec 3.2 and expected `terminated=True`, the implementation read this paragraph and produced `terminated=False`, and the candidate spans agreed in every other respect. Sec 3.2's equivalence is the authority.*

*The reviewer recommended adding `error` and making it the default. Rejected: an edge-abutting range is the designed behavior of the single-sided forms, so erroring on it is backwards. `drop` covers the strict use case.*

**R6 -- Pairing is `--pairing`, default `sed`, two modes in v1.** *(Trimmed in v5 from four.)* See Sec 3.3. `-C c` alone therefore pairs occurrences 1-2, 3-4 under the default.

**R7 -- Candidate ranges never cross sources.** An unterminated range at EOF does not continue into the next file.

**R8 -- Exclusion removes a contribution, not a line.** `--exclude-A` / `--exclude-B` / `--exclude-bounds` drop the boundary line from *that candidate's* contribution. The boundary must still be found, or `--unterminated` applies. If another candidate independently includes the same line, it is emitted.

**R9 -- `-v` is a set complement at step 6.** Compute `S` exactly as without `-v`, then emit `D minus S`. This holds identically in both modes and preserves the single algorithm.

Two consequences that will surprise people and are therefore tested:
- **A line dropped by `--exclude-A` reappears under `-v`**, because it is not in `S` -- unless another candidate includes it.
- **`-v` requires `--emit union`.** The complement of an ordered list of overlapping ranges is not defined. `-v --emit ranges` exits 2. **The engine enforces this, not just the CLI** -- `search()` raises on the combination, so a direct caller cannot bypass it.

**R10 -- `-c` counts selected lines.** In anchor mode, accepted `-P` match lines; in delimiter mode, completed candidate ranges. Context is never counted.

**R11 -- `-o` is incompatible with any boundary flag**, exit 2. GNU grep ignores context with `-o` and warns; rejecting is a deliberate divergence, recorded in Sec 5.6.

**R12 -- `-C` is incompatible with `-A` or `-B`**, exit 2.

**R13 -- Patterns are always flags; positionals are always sources.** `pygrep foo file.txt` does *not* treat `foo` as a pattern -- with four pattern slots a positional pattern silently mis-parses. `-P` is repeatable and multiple values are OR'd. A positional `-` means stdin-as-text.

**R14 -- v1 buffers one source at a time: O(largest source).** The engine takes a `Sequence[str]`, so there is no streaming and no constant-memory guarantee. `-d` bounds *matching*, not memory.

*An earlier draft claimed constant memory with `-d` while specifying a `list[str]` engine. The two are incompatible and the claim is withdrawn rather than softened. A streaming engine over `Iterable[str]` with bounded deques is a separate change.*

**R15 -- Distance is `later_line_number - earlier_line_number`.** Adjacent lines are distance 1; two occurrences on the same line are distance 0. `-d` constrains **pattern boundaries only** and has no effect on count boundaries, where the count already is the limit.

**R16 -- `-d 0` is legal and means "same line only".** *(Simplified in v4; there is no flag.)* It is reachable whenever two distinct occurrences share a line, which R4 permits. No special case is needed.

*v2 rejected `-d 0` outright and v3 gated it behind `--allow-self-boundary`. Both were artifacts of R4 being line-based. Once R4 is occurrence-based, `-d 0` is just a distance limit like any other.*

**R17 -- The regex dialect is Python `re`, always, and `-E` is rejected.** Python `re` is **not** a POSIX ERE superset:
- POSIX ERE is leftmost-longest; Python is leftmost-first with ordered alternation.
- Python lacks POSIX bracket expressions such as `[[:alpha:]]`.
- Python adds constructs POSIX has no equivalent for: `(?:...)`, `(?P<name>...)`, lookaround.

Accepting `-E` as a no-op would advertise a compatibility guarantee the engine cannot keep.

**R18 -- Empty and missing patterns are different.** In `pygrep -A -B ""`, `-A` consumes no argument because `-B` begins the next option -- a command-line error. `-B ""` is a valid regex; under Python `re` it yields a zero-width occurrence at every column, so R4 governs which of them can serve as the boundary. An empty `--pattern-file` contributes zero alternatives, which yields no matches and exit 1 -- not a parse error.

---

### 4.1 Refinements settled by the two-derivation pass

Every row below was **undefined or ambiguous in v5** and was surfaced by writing the test
suite and the engine independently from the same text. Recorded here rather than scattered,
so the provenance stays visible.

| # | Question | Ruling |
|---|---|---|
| 1 | Does each `-P` *occurrence* seed a candidate, or each match *line*? | **Per occurrence.** Necessary for R4's table: given `-P foo -A foo` on `foo bar foo`, occurrence 1 closes on occurrence 2 giving a one-line range, while occurrence 2 must search onward. Line-seeding cannot express that. **But identical candidates are then deduped** (same start, stop, excluded, terminated), because two occurrences on one line with the same boundary produce the same range twice, which is noise under `--emit ranges`. |
| 2 | Is "earlier/later column" strict or inclusive? | **Strict.** Forward needs `start_col >` the anchor's; backward `start_col <`. An occurrence at exactly the anchor's column is neither, so it cannot serve -- the natural extension of R4 to zero-width and equal-start patterns. `end_col` plays no part in direction. |
| 3 | Do `--exclude-A`/`-B` apply when the boundary is a count, or a defaulted edge? | **No, and for one reason: exclusion is role-based, not flag-based.** `--exclude-B` withholds whatever occurrence fills the *opener* role. A count boundary and a defaulted edge have no occurrence, so nothing is withheld -- a silent no-op, not an error, because `-B 2 -A '^$' --exclude-bounds` is a legitimate command. Consequence worth knowing: in `-A a` alone the seam line fills the opener role, so `--exclude-B` strips the leading boundary from each segment even though `-B` was never passed. |
| 4 | `--exclude-A` when the closer sits on the anchor's own line | Taken literally: that line enters `excluded` and the candidate contributes nothing. R8 is stated at line granularity over a candidate's contribution. |
| 5 | Does `-d` constrain edge-defaulted connections? | **No.** R15 says pattern boundaries only. `BOF..a1` and `b_n..EOF` are never distance-rejected. The constrained connection is anchor-to-boundary in anchor mode, opener-to-closer in delimiter mode, and `a_i` to `a_i+1` in segmentation. |
| 6 | What does `-m` cap when context is active? | **The same thing `-c` counts** (R10): distinct match lines in anchor mode, candidate ranges in delimiter mode. Never output lines -- capping `|S|` would truncate context, and `grep -m 1 -A 3` prints four lines. |
| 7 | Does `-v` change `count`? | **Yes: `count == len(selected)` under invert.** grep-faithful -- `grep -vc` counts the lines it would print. |
| 8 | Do `-i` / `-w` / `-x` apply to boundary patterns as well as `-P`? | **Yes, uniformly to every pattern.** Matches grep, where `-i` is global. `-x` beats `-w` if both are given. |
| 9 | Numeric `-A`/`-B` with no `-P` | **Error.** There is no anchor to count from and Sec 3.2 defines no meaning. Exit 2 rather than an invented construction. |
| 10 | Both a count and a pattern on the same side | **Error.** `-A 3 --after-pattern x` is a contradiction, not a precedence question. |
| 11 | `groups` endpoint convention | Inclusive `(start, stop)`, ascending, matching `Candidate.start`/`stop`. |
| 12 | Surplus boundaries under `--pairing occurrence` | A closer with no opener produces no candidate. A surplus opener produces an unterminated candidate, mirroring sed's dangling open. |

**Where the two derivations agreed without being told to**, the spec is positively confirmed
unambiguous rather than merely unchallenged: rows 6, 7 and 8 above, plus R5's `-d` clamp
point and R10's line-granularity. That agreement is the signal a single implementer cannot
produce.

## 5. Flag reference

Named **grep-derived**, not grep-compatible. Divergences are listed in Sec 5.6. There is no single grep to be compatible with: this machine's `/usr/bin/grep` is BSD and has no `--group-separator`, GNU grep is the naming reference, and the `grep` inside CLI sessions is a bundled `ugrep`.

### 5.1 Patterns

| Flag | Meaning |
|---|---|
| `-P, --pattern PAT` | primary pattern; repeatable, OR'd |
| `-A, --after PAT\|N` | closer, or a forward line count (R2) |
| `-B, --before PAT\|N` | opener, or a backward line count |
| `-C, --context PAT\|N` | both; incompatible with `-A`/`-B` (R12) |
| `--after-lines N`, `--before-lines N`, `--context-lines N` | unambiguous count forms |
| `--after-pattern P`, `--before-pattern P`, `--context-pattern P` | unambiguous pattern forms |
| `--pattern-file FILE` | additional `-P` alternatives, one per line; `#` comments skipped; unioned with explicit `-P` |

### 5.2 Range construction

| Flag | Meaning |
|---|---|
| `-d, --max-distance N` | max distance between connected lines (R15, R16) |
| `--pairing MODE` | `sed` (default) \| `occurrence` (Sec 3.3) |
| `--unterminated MODE` | `truncate` (default) \| `drop` (R5) |
| `--exclude-A` / `--exclude-B` / `--exclude-bounds` | drop boundary lines from contributions (R8) |

### 5.3 Output shape

| Flag | Meaning |
|---|---|
| `--emit MODE` | `union` (default) \| `ranges` (Sec 2) |

### 5.4 Matching

| Flag | Meaning |
|---|---|
| `-i, --ignore-case` | |
| `-w, --word-regexp` | |
| `-x, --line-regexp` | |
| `-v, --invert-match` | R9; requires `--emit union` |
| `-m, --max-count N` | stop after N **selected lines** per source (grep-faithful) |

### 5.5 Output

| Flag | Meaning |
|---|---|
| `-n, --line-number` | |
| `-c, --count` | R10 |
| `-l, --files-with-matches` | |
| `-o, --only-matching` | R11 |
| `-q, --quiet` | no output; exit status only; exits early on first selected line |
| `-s, --no-messages` | suppress unreadable-source diagnostics; **does not change exit status** |
| `--color WHEN` | `auto` (default) \| `always` \| `never` |

Filename prefixing is automatic: on iff more than one source. There is no manual override in v1.

### 5.6 Deliberate divergences from GNU grep

1. `-P` is the primary pattern, **not** `--perl-regexp`. No loss: Python `re` is the only dialect (R17), so a dialect flag would be meaningless.
2. `-E` is **rejected**, not accepted-and-ignored (R17).
3. `-f` is an input file, **not** patterns-from-file; grep's meaning moves to `--pattern-file`.
4. `-d` is `--max-distance`, **not** `--directories=ACTION`.
5. `-o` with a boundary flag is an **error**; grep ignores context and warns (R11).
6. Patterns are never positional (R13).
7. `-p` is `--paste`; ripgrep uses it for `--pretty`.
8. `-F, --fixed-strings` is **not supported**. It was never requested and its only effect on this design was to complicate R2.

### 5.7 Short flag budget

Taken: `A a B b C c d i l m n o P p q s v w x`
Rejected-with-a-message (not reusable): `E`, `F`
Free: `G H h I j J k K L M N O r R S T u U W X y Y Z`

`-H`/`-h`/`-L`/`-Z` are free because v1 cut them, not because they are unwanted; they are the first things to add back if the automatic filename rule proves insufficient.

`-r`/`-R` are deliberately left free: recursion belongs to fsFind (Sec 1, Sec 6).

---

## 6. Input model

Source types are always explicit. An earlier draft said to call both `get_text_from_input()` and `get_file_paths_from_input()`; the first reads non-TTY stdin as *content* (`lib_fileInput.py:121-154`), the second reads the same stdin as a *list of paths* (`lib_fileInput.py:157-223`). No reliable heuristic distinguishes them, so the caller must say which it means.

| Form | Source type |
|---|---|
| positional `PATH...` | files |
| positional `-` | stdin, as **text** |
| bare pipe, no positional | stdin, as **text** |
| `-f, --file FILE` | one file, as text (lib_fileInput meaning, not grep's) |
| `--files-from FILE` | a **list of paths** to search |
| `--files-from -` | the path list comes from stdin |
| `-p, --paste` | clipboard |

Encoding is `utf-8`, not configurable in v1.

Only one stdin consumer may be active: `-` together with `--files-from -` exits 2.

`lib_fileInput` is still used for the *reading* -- `read_clipboard_text()`, and `expand_path()` under `--files-from` -- but **never for argument declaration**, so `-v` and `-f` keep their pygrep meanings.

### Not pygrep's job: directory recursion and binary handling

`-r`/`-R`, `--include`/`--exclude`, `--binary-files` and ignore-file behavior are **out of scope**, per Sec 1. fsFind is the file finder; `--files-from -` is the seam.

This is a scope boundary, not a deferral. It also removes symlink policy, hidden-file policy, ignore-file semantics and NUL-based binary detection from this tool entirely. `expand_path()` (`lib_fileInput.py:237-278`) walks directories unconditionally, so an `-r` switch here would gate nothing anyway.

A directory passed positionally exits 2 with `use fsFind and --files-from, or a shell glob`.

*Recorded because it is a live defect elsewhere: ignore-file semantics diverging silently between tools is exactly what makes `ai_general/data/` invisible to the session `grep`. Whatever owns recursion must not repeat it.*

---

## 7. Output format

grep's format, because downstream tools already parse it.

```
file:lineno:text      selected line       (: separator)
file:lineno-text      context line        (- separator)
--                    between non-contiguous groups
```

`lineno` appears only with `-n`; `file:` per `-H`/`-h`. Under `--color`, the `-P` match substring is highlighted in one color and boundary lines in a second, so it is visible *why* a range stopped where it did.

Under `--emit ranges`, each candidate is a record separated by `--`, and identical lines may appear in more than one record. A JSON output mode was specified and cut from v1; it is the right answer for machine consumption of overlapping records, and the `-n` line numbers are the workaround until it exists.

## 8. Exit codes

| Code | Meaning |
|---|---|
| 0 | at least one line selected |
| 1 | nothing selected |
| 2 | error: bad regex, invalid flag combination, unreadable source |

`-s` suppresses the *message* for an unreadable source; the exit status is still 2. `-q` exits 0 as soon as the first line is selected.

---

## 9. Module structure

The step-2 rules are where all the subtlety lives, so they are separated from argparse and from I/O and testable against literal lists of strings.

| File | Responsibility | Depends on |
|---|---|---|
| `lib_pygrep.py` | the engine: `find_occurrences` (via `re.finditer`, returning `(lineno, start_col, end_col)`), `build_candidates` (one function per Sec 3 mode), `apply_distance`, `apply_unterminated`, `apply_exclusions`, `to_union`, `group_contiguous`. Pure functions over `Sequence[str]`. No argparse, no file I/O, no printing. | `re` |
| `pygrep.py` | CLI: argparse, flag validation (R11/R12/R13/R18, Sec 6 stdin conflict), source resolution, formatting, exit codes | `lib_pygrep`, `lib_fileInput` |
| `mingrep.py` | the old tool, moved verbatim | `re`, `argparse` |

`lib_pygrep.py` having zero I/O dependencies is the point: every ruling in Sec 4 is a short test against a literal list.

### 9.1 Engine API contract (frozen)

This is the surface the tests target and the implementation provides. It is fixed so that a test suite and an implementation written independently meet. **Everything below is binding; everything not mentioned is the implementer's choice.**

```python
from dataclasses import dataclass, field
from typing import Optional, Sequence

@dataclass(frozen=True)
class Occurrence:
    lineno: int        # 1-based
    start_col: int     # 0-based, inclusive
    end_col: int       # 0-based, exclusive

@dataclass(frozen=True)
class Candidate:
    start: int                     # 1-based lineno, inclusive
    stop: int                      # 1-based lineno, inclusive
    anchor: Optional[int] = None   # lineno of the -P match, None in delimiter mode
    excluded: frozenset = frozenset()   # linenos this candidate does NOT contribute (R8)
    terminated: bool = True        # False if a boundary was missing or beyond -d (R5)

@dataclass
class Options:
    pattern: tuple = ()            # -P, OR'd. empty => delimiter mode
    after: Optional[str] = None    # -A as a pattern
    before: Optional[str] = None   # -B as a pattern
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
    candidates: list        # list[Candidate], in source order, post-distance,
                            # post-unterminated, pre-union. This is what
                            # --emit ranges renders.
    selected: set           # set[int] of 1-based linenos. The set S, or D-S
                            # under invert. This is what --emit union renders.
    groups: list            # list[tuple[int,int]] maximal contiguous runs of
                            # `selected`, ascending. Drives the `--` separator.
    count: int              # R10: selected lines in anchor mode, completed
                            # candidates in delimiter mode.

def search(lines: Sequence[str], opts: Options) -> Result:
    """Run the Sec 2 algorithm over one source. Pure; no I/O."""
```

Notes that are part of the contract:

- `-C` is expanded by the caller into `after` + `before` with the same value. The engine never sees `-C`.
- `--exclude-bounds` is expanded by the caller into both exclude flags.
- `lines` excludes line terminators. `lineno` is `index + 1`.
- Under `emit="ranges"`, `selected` and `groups` are still populated; the CLI chooses which to render.
- `Options` may gain fields; existing field names and meanings are frozen.

## 10. Test plan

Location: `/Users/shawnhillis/bin/all_languages/python/tests/tests_fileUtils/test_pygrep.py` -- the existing convention is a sibling `tests/` tree, not `tests/` under `src/`.

**Engine** -- one test per ruling in Sec 4 and per row of Sec 3.1/3.2. Each is a list of input lines, a flag set, and an expected list of emitted line numbers.

Matrices:
- every valid and invalid mode combination, including `-A` alone, `-B` alone, numeric `-A`/`-B` without `-P`, `--pattern-file` without `-P`
- boundary found / missing / exactly `N` / `N+1` away
- both `--pairing` modes against `B1 B2 A1 A2`, malformed `B1 B2 B3 A1 A2`, and the FIFO login pairs from Sec 3.3; plus a LIFO case asserting the documented-wrong result, so the limitation is pinned rather than discovered later
- **R4 at occurrence granularity**, which is the most regression-prone rule in the spec: `foo` alone on a line vs `foo bar foo`; `-P foo -A bar` with both on one line; a boundary occurrence at an *earlier* column than the anchor (must not satisfy a forward search); `-d 0` and `-d 1` against same-line and adjacent-line pairs; and the seam case proving one occurrence may close one segment and open the next
- `--emit union` vs `--emit ranges` on the same overlapping input
- exclusion followed by union, including the same line excluded by one candidate and included by another
- `-v` complement, including the excluded-line-reappears case (R9)
- empty input, empty regex, empty pattern file, no trailing newline, multiple sources

**CLI** -- via `subprocess`:
- each Sec 6 input form, and the `-` plus `--files-from -` conflict
- exit codes 0 / 1 / 2; `-s` keeps exit 2; `-q` early exit
- `-c` counts selected lines in anchor mode and completed ranges in delimiter mode (R10); `-m` caps selected lines
- rejected combinations: `-C`+`-A` (R12), `-o`+`-A` (R11), `-v`+`--emit ranges` (R9), `-E` (R17), `-F` (Sec 5.6)
- `-A 3` vs `--after-pattern 3` (R2)
- filename prefixing auto-on at 2 sources
- a positional directory exits 2 (Sec 6)

**Migration** -- all three launchers resolve to the new code; `mingrep` exists on PATH and runs.

---

## 11. Decision log

### Settled

| Item | Resolution | Settled in |
|---|---|---|
| Same-line anchor and boundary | R4 restated at **occurrence** granularity. Both readings become correct at once, so no flag is needed | v4 |
| `--allow-self-boundary` | **Deleted.** It only existed to paper over line-based R4 | v4 |
| `-d 0` | Legal, means "same line only". No special case (R16) | v4 |
| Seam lines | Shared, and reconciled with R4 by scope: R4 binds within one candidate range (Sec 3.2, R4) | v3, refined v4 |
| Does `--pairing` exist | Yes -- recurrent entry/exit tracking requires `occurrence` | v3 |
| Flag count | **Trimmed 38 options to 27** (counted, not estimated; 11 removed, listed below). With the 6 long-form `-A`/`-B`/`-C` aliases counted as separate spellings, 33 accepted spellings total | v5 |
| `-F` | **Dropped.** Never requested; its only effect was complicating R2 | v3 |
| `-r` / binary handling | Out of scope, not deferred. fsFind finds files; pygrep finds content (Sec 1) | v3 |
| Unterminated default | `truncate`, against the reviewer's recommendation of `error` (R5) | v2 |
| Output shape | `--emit union\|ranges`; `--merge/--no-merge` deleted, union is the behavior | v2 |
| Input source typing | Always explicit; `--files-from -` for path lists (Sec 6) | v2 |

### Cut from v1 (the trim)

Everything here was specified, agreed to be fat, and removed. Recorded so nobody re-derives it as a gap:

| Cut | Why |
|---|---|
| `--pairing nested`, `innermost` | `innermost` duplicates R3; `nested` solves one interleaving shape while `--pair-by` solves the class |
| `--unterminated anchor` | reachable by rerunning without the boundary flag |
| `--json` | right answer for machine-reading overlapping records, wrong size for v1 |
| `--max-ranges`, `--count-ranges` | `-m` and `-c` cover the real cases |
| `--group-separator`, `--no-group-separator` | `--` is fixed |
| `-L`, `-Z`, `-H`, `-h` | filename prefixing is automatic; the rest are unused shapes |
| `--encoding`, `--clipboard` | utf-8 fixed; `-p/--paste` is the one spelling |
| `-F, --fixed-strings` | never requested, and its only effect was complicating R2 |

**The honest accounting:** three of these exist because a reviewer asked "what about X" and the answer was a flag rather than "out of scope." A reviewer raising a case is not a requirement to handle it.

### Deferred to v2 of the tool

- `--pair-by GROUP` -- pair boundaries by captured key rather than position (Sec 3.3). The only construction that correctly handles interleaved correlated events; every positional mode is an approximation.
- A streaming engine over `Iterable[str]` with bounded deques (R14).
- JSON output for `--emit ranges`.

### Open

None.
