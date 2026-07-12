# `calc` — CLI Calculator: Design

**Status:** Design (approved via brainstorming dialogue 2026-07-10; user delegated spec review + implementation)
**Author:** Claude (session 20260703_230541_2897dc92_cla) with PianoMan
**Home:** `~/bin/python/src/calc/`
**Target:** Python 3.9+, cross-platform (macOS / Linux / Windows)

---

## Terms

- **Engine** — the dependency-free core that turns a string of source into a value: *tokenizer → parser → evaluator → formatter*. Knows nothing about how it was invoked.
- **Frontend** — a thin adapter that feeds source into the engine and prints results. Three of them: `oneshot`, `filter`, `repl`.
- **One-shot** — non-interactive evaluation of an expression passed as argv (`calc "2+2"`). The primary mode.
- **Filter** — non-interactive evaluation of expressions read from stdin, one result per input line (`echo "2+2" | calc`).
- **REPL** — Read-Eval-Print Loop; the optional interactive mode for building up formulas, with non-destructive help. Entered only at an interactive terminal with no expression to evaluate, or via `-i`.
- **Pratt parser** — a top-down operator-precedence parser; cleanly handles unary minus, right-associative power, and function calls.
- **AST** — Abstract Syntax Tree; the parsed structure the evaluator walks.
- **LET** — a local-binding construct for multi-step calculations (borrowed from Excel's `LET`). Bindings are scoped to a single expression.
- **LAMBDA** — an anonymous function value (borrowed from Excel's `LAMBDA`). A named user function is a lambda bound to a name.
- **`calcrc`** — the durable config/definitions file (`~/.config/calc/calcrc`), written in the same grammar the calculator evaluates, replayed at startup.
- **Reserved word** — a command verb or special identifier that cannot be used as a user definition name.
- **Ephemeral index** — a short numeric handle (`1`, `2`, …) printed by `calc list`, usable in the next command to reference a definition, invalidated by any change to the definitions.

---

## 1. Purpose & Priorities

A fast, intuitive, cross-platform command-line calculator. Priorities, in order (from the user):

1. **Intuitive** — type an expression, get an answer.
2. **Adaptive to sloppy input** — whitespace-agnostic, operator synonyms, case-insensitive functions, safe implicit multiplication.
3. **Correct precedence & parentheses** — a real parser; the engine never hands the string to Python's built-in expression evaluator.
4. **Responsive** — instant on the quick path; zero-dependency core.
5. **Input help** — mismatched-paren detection and mid-entry help (in the REPL), good error diagnostics everywhere.
6. **Legible output over precision** — clean human-readable results by default, full precision on demand.
7. **Bases** — decimal default; input and output bases independently selectable.
8. **Cross-platform** — pure-Python core, graceful frontend degradation.

Design stance settled during brainstorming: **go deep on the expression *language* (LET, LAMBDA, scopes — cheap, compounding), stay curated on the function *catalog* (a sensible math set, not a spreadsheet).**

---

## 2. Architecture

```
                         ┌─────────────────────────────────────────┐
   argv / stdin / TTY →  │            cli (dispatch)                │
                         │  command verb?  → command handler        │
                         │  else           → frontend → engine      │
                         └─────────────────────────────────────────┘
                                    │                     │
                     ┌──────────────┴────────┐            │
             frontends:                       │           │
             oneshot | filter | repl          │           │
                     └──────────────┬─────────┘           │
                                    ▼                      ▼
   ENGINE (zero-dependency):   tokenizer → parser → AST → evaluator → formatter
                                    ▲                          │
                                    └────── store (calcrc) ────┘
                                       durable defs + settings
```

**Data flow (one-shot):** argv → dispatch decides "expression, not a command" → `oneshot` frontend → engine tokenizes → parses to AST → evaluator (with defs/vars from `store`) produces a value → formatter renders per current settings → stdout. Errors → stderr, non-zero exit.

The engine is a pure library: `evaluate(source, env) -> Result`. Every frontend and the test suite call it the same way. Only the engine touches math; only frontends touch I/O; only `store` touches disk.

**Why a real parser, not the language's built-in expression evaluator:** beyond the obvious safety issue, the built-in brings Python's own semantics — `^` is bitwise-XOR not power, `/` is always float, integer division and precedence follow Python rules — which fight nearly every priority above. A purpose-built tokenizer/parser/evaluator gives full control over precedence, sloppy-input handling, bases, and legible output.

---

## 3. The Expression Language

### 3.1 Literals & bases
- Decimal: `42`, `3.14`, `6.02e23`, `.5`, `1_000` (underscores allowed as digit separators).
- Hex `0x1F`, binary `0b1010`, octal `0o17`. (Base prefixes are resolved by the tokenizer *before* implicit multiplication, so `0b10` is binary-2, never `0·b·10`.)

### 3.2 Operators & precedence (low → high)
| Level | Operators | Assoc | Notes |
|------|-----------|-------|-------|
| 1 | `+` `-` | left | binary add/subtract |
| 2 | `*` `/` `%` `//` | left | `%` = modulo, `//` = integer/floor division |
| 3 | unary `-` `+` | right | |
| 4 | `^` (`**`) | **right** | power; `2^3^2 = 512` |
| 5 | `!` (postfix) | — | factorial |
| 6 | function call, `( )` | — | |

**Operator synonyms (sloppy-input):** `x` / `X` / `·` / `×` → `*`; `÷` → `/`; unicode minus `−` → `-`; `**` → `^`; `mod` (word) → `%`. Case-insensitive function/constant names.

### 3.3 Implicit multiplication (safe subset only)
Inserted only where unambiguous: number-before-`(` (`2(3+4)` → `14`), number-before-constant/identifier (`2pi`, `3x`). **Not** applied where it would collide with function calls or base prefixes. When implicit multiplication is applied, the interpretation is echoed on stderr in the REPL / verbose mode (`2(3+4) → 2*(3+4)`), never a silent guess in ambiguous spots.

### 3.4 Functions & constants (curated catalog)
- Constants: `pi`, `e`, `tau`.
- Functions: `sqrt`, `cbrt`, `abs`, `sin cos tan asin acos atan`, `sinh cosh tanh`, `exp`, `ln`, `log(x[, base])` (natural by default, base optional), `log2`, `log10`, `floor`, `ceil`, `round(x[, n])`, `sign`, `min(...)`, `max(...)`, `gcd`, `lcm`, `factorial` (also postfix `!`), `hypot`.
- **Angle mode** (`deg` / `rad`) is a setting affecting trig; shown in the REPL prompt/toolbar and settable via `calc set angle deg`.

### 3.5 Bindings, LET, and LAMBDA (the unifying model)
All of "variables", "user functions", and "local steps" are one mechanism: **named bindings + lambda values + scopes.**

- **Variable / constant:** `x = 5`, `c = 299792458`.
- **User function (sugar):** `f(x) = x^2 + 1` desugars to `f = lambda(x, x^2 + 1)`. Multi-arg: `g(x, y) = x*y`.
- **LAMBDA (explicit):** `lambda(x, x^2 + 1)` is a first-class value.
- **LET / multi-step (inline):** semicolon-separated steps on one line, last is the result:
  ```
  r = 5; area = pi*r^2; area        → 78.53981633974483 → 78.54
  ```
  Bindings before the final expression are **local to that line** (LET semantics) unless the line is a bare top-level definition (see §6 lifetimes). Explicit form also accepted: `let r = 5, area = pi*r^2 : area`.
- **Multi-line stdin is LET spread across lines:** same model — intermediate named steps, last line is the answer.

**Scoping & safety:** function calls evaluate the lambda body in a child scope with parameters bound; user functions may call other user functions; a recursion-depth guard (default 200) raises a friendly error instead of a Python `RecursionError`.

---

## 4. Output Formatting (legible over precision)

Default rendering rules:
- **Exact when exact:** `10/2 → 5` (not `5.0`), `2+2 → 4`.
- **Float-noise cleanup:** round to ~12 significant figures then strip trailing zeros, so `0.1 + 0.2 → 0.3`, `1/3 → 0.333333333333`.
- **Scientific** only for very large / very small magnitudes (configurable thresholds).
- **Precision** is a setting (`calc set precision 10`); a per-call override shows full precision on demand.
- **Base output:** `calc -o hex "255+1" → 0x100`; also a per-line suffix `255+1 =hex`. Base output applies to **integer** results; on a non-integer with base output requested, **warn and fall back to decimal** (no ugly fractional-hex). Optional thousands separators for large integers (off by default — quarantined, see §11).

The engine keeps enough type information (int vs float vs known-exact) that "clean" never silently means "wrong."

---

## 5. Frontends

`calc` is **CLI-first**; the REPL is opt-in. Auto-detection rule:

> If an expression is given on argv **or** stdin is not a TTY (piped/redirected), it's non-interactive. The REPL is entered **only** at an interactive terminal with no expression, or via `-i`/`--repl`. A piped `calc` never surprise-blocks at a prompt.

### 5.1 `oneshot` (argv) — primary
```
calc "3 + 4*2"          → 11
calc -o hex "255+1"     → 0x100
calc --deg "sin(30)"    → 0.5
```

### 5.2 `filter` (stdin) — pipe-friendly
```
echo "3+4*2" | calc     → 11
calc < formulas.txt     → one result per line
echo "2+2" | calc "ans*10"   → 40      # ans = value arriving on stdin
```
Each input line is evaluated and printed one-for-one. Bindings/definitions on a line persist **down the stream**, and `ans`/`_` refers to the previous line's result — so a multi-line stream behaves like an inline LET.

### 5.3 `repl` (opt-in, `prompt_toolkit`) — formula building
The only place with the heavier dependency. Provides the **non-destructive help** that motivated it — your in-progress line stays on screen while help appears:
- **Completion menu with signatures** as you type a name (`lo` → `log(x)`, `log(x, base)`, `log2(x)`, `log10(x)` with hints) — discovery without knowing the exact name.
- **`?` / F1 help overlay** listing operators/functions by category, dismissing back to the intact line.
- **Bottom toolbar**: angle mode, output base, `Tab complete · ? help · ↑ history`, and a live result / parse-error preview as you type (live paren-balance feedback).

If `prompt_toolkit` is unavailable, the REPL degrades to a plain `input()` loop (history + tab-completion where `readline` exists). **The engine never imports `prompt_toolkit`**, so one-shot/filter stay instant and dependency-free.

---

## 6. Persistence — three lifetimes

| Lifetime | What | Mechanism |
|----------|------|-----------|
| **In-process** | `ans` / `_` (last result), LET-local bindings | held in the evaluator's scope; bound from stdin value or previous stream line; no disk, no cross-process state |
| **Per-shell-session** | `$ans` / `$_` as real shell variables across separate commands | optional sourced shell function `calc()` that captures output and `export`s it into the *current* shell (the same idiom as the user's `gdir` wrapper); per-terminal, no races, no state file |
| **Durable** | user-defined functions & named constants; default settings | `~/.config/calc/calcrc`, written in the calculator's own grammar, replayed at startup; the only thing that touches persistent disk state |

**Why not a global `ans` file:** a shared last-answer file is a mutable global across all processes → cross-terminal races and surprising side effects on quick calcs. Environment is per-shell-session, so the shell-wrapper approach delivers the `$ans` interface *without* the race. `ans` as a bare calc identifier covers the pipe/stream case with no shell magic at all.

Shipped shell wrapper (optional, sourced in `.bashrc`/`.zshrc`):
```bash
calc() { local out; out=$(command calc "$@") || return; export ans="$out" _="$out"; printf '%s\n' "$out"; }
```

### `calcrc` format (replayable grammar)
```
# ~/.config/calc/calcrc  — replayed at startup, hand-editable
f(x) = x^2 + 1
area(r) = pi*r^2
c = 299792458
angle = deg
base = dec
precision = 12
```

---

## 7. Management Commands (non-calculation surface)

Operate on stored definitions/settings. Curated verb set:
```
calc list              # numbered listing of functions, constants, settings
calc show f | show 2   # print one definition's body:  f(x) = x^2 + 1
calc del  f | del  2   # remove a definition (by name or ephemeral index)
calc clear             # remove all definitions (confirm)
calc edit              # open calcrc in $EDITOR
calc path              # print calcrc location
calc set <key> <val>   # persist a default setting (angle/base/precision/…)
calc help [topic]      # usage; `calc help sin` = operator/function help
```
Same verbs work inside the REPL without the `calc` prefix (`del f`), fully symmetric — no `:` prefix needed (reserved words guarantee no collision, §8).

### Ephemeral indexes
`calc list` prints a short numeric handle per item and writes an **index snapshot** (index→name + a hash/mtime of `calcrc` at listing time) to `~/.config/calc/`. `del 2` / `show 2` resolve through it. If `calcrc` changed since that listing (any add/remove/edit, from any terminal), the snapshot is **stale** and numeric refs hard-error: *"index stale — run `calc list` again."* Names always resolve regardless. Numbers can never collide with names (a definition can't be named `2`).

---

## 8. Dispatch & Reserved Words

**Dispatch rule:** the first argv/line token decides — `token ∈ command-verb-set` → command; otherwise → expression. Unambiguous because of reserved words.

**Reserved words cannot be used as definition names.** Attempting `list = 5` or `del(x) = …` is rejected: *"«list» is a reserved command name."* This kills the command-vs-expression ambiguity at the source (no escape hatch needed).

- **Hard-reserved** (never definable): the command verbs (`list show del clear edit path set help`) and the special identifiers `ans`, `_`.
- **Shadowable with warning:** built-in math names (`sin`, `pi`, `log`, …) — a power user may override (e.g. redefine `log`), but the tool warns. (Sub-decision, low-stakes; hard-forbid is the trivially-simpler fallback.)

---

## 9. Error Model

No Python tracebacks ever reach the user. Every error is a friendly one-liner, and where a position is known, a caret points at it:
```
calc "3 + log(8, )"
  3 + log(8, )
             ^  expected an expression after ','
```
- **Unbalanced parens:** report count and side (`2 unclosed «(»`).
- **Unknown name:** nearest-match suggestion (`unknown function «tna» — did you mean «tan»?`).
- **Domain/eval errors:** division by zero, `sqrt(-1)`, overflow → plain-language message.
- Exit codes: `0` success, non-zero on any parse/eval error (scriptable).

---

## 10. Cross-Platform & Dependencies

- **Engine + oneshot + filter + management + store:** standard library only. Runs anywhere Python 3.9+ runs.
- **REPL:** optional `prompt_toolkit` (pure-Python, cross-platform — also removes the Windows-`readline` wrinkle). Absent → plain `input()` fallback.
- Config path via `XDG_CONFIG_HOME`, defaulting to `~/.config/calc/` (works on macOS/Linux; Windows uses `%APPDATA%\calc\`).
- Packaged via the repo's `pyproject.toml` pattern: `[project.scripts] calc = "calc.cli:main"`, `requires-python = ">=3.9"`, `dependencies = []` with `prompt_toolkit` as an optional extra (`calc[repl]`).

---

## 11. Out of Scope / Quarantined (build-then-react)

Deliberately excluded from v1 until the tool is in-hand and the user can react:
- **Percent** (`50 + 10%`) — ambiguous semantics; revisit after real use.
- **Thousands separators** in output — trivial but as-often-annoying-as-helpful; a toggle, off by default, deferred.
- **Units / currency** — a whole subsystem; out.
- **Spreadsheet breadth** — arrays, ranges, tables, giant function catalog. The line is: language depth yes, catalog breadth no.

---

## 12. Module Layout

```
~/bin/python/src/calc/
  __init__.py
  cli.py           # entry point: argv/stdin/TTY dispatch → command or frontend
  engine/
    __init__.py    # evaluate(source, env) -> Result   (public engine API)
    tokenizer.py   # source → tokens (bases, synonyms, implicit-mult prep)
    parser.py      # Pratt parser → AST (operators, LET, LAMBDA, calls)
    ast_nodes.py   # AST node definitions
    evaluator.py   # AST walk; scopes, lambdas, recursion guard
    builtins.py    # curated functions & constants; angle mode
    formatter.py   # legible output, base rendering, precision
    errors.py      # typed errors carrying position for caret diagnostics
  frontends/
    oneshot.py     # argv evaluation
    filter.py      # stdin evaluation (one result/line, stream bindings)
    repl.py        # prompt_toolkit REPL (+ plain fallback)
  store.py         # calcrc load/save, settings, ephemeral index snapshot
  commands.py      # list/show/del/clear/edit/path/set/help handlers
  reserved.py      # reserved-word set + validation
  shell/calc.sh    # optional sourced $ans wrapper
  helptext.py      # help catalog (operators, functions, examples)
  test_*.py        # pytest suites (engine-first, TDD)
  docs/
    2026-07-10-calc-cli-design.md   # this document
```

---

## 13. Testing Strategy

Engine-first, test-driven. The engine's pure `evaluate(source, env)` API makes the bulk of behavior testable without any I/O:
- **Tokenizer:** bases, synonyms, digit separators, implicit-mult insertion points.
- **Parser:** precedence, associativity (esp. right-assoc `^`), unary, LET/LAMBDA, error positions.
- **Evaluator:** arithmetic correctness, scopes, user functions, recursion guard, angle mode.
- **Formatter:** exact-when-exact, float-noise cleanup, base rendering, non-integer-base fallback.
- **Frontends:** oneshot exit codes, filter one-result-per-line + stream bindings, TTY-detection (REPL not entered on pipe).
- **Store/commands:** calcrc round-trip (write → replay → identical), reserved-word rejection, ephemeral-index staleness detection.
- **Golden CLI tests:** representative expressions end-to-end.

---

## 14. Build Order

1. Engine core: tokenizer → parser → evaluator → formatter (with tests) — delivers `calc "expr"` correctness.
2. `cli.py` dispatch + `oneshot` + `filter` — the primary CLI, scriptable.
3. `store.py` + `calcrc` + bindings/user-functions/LET/LAMBDA persistence.
4. `commands.py` management surface + ephemeral indexes + `reserved.py`.
5. Bases in/out, angle mode, legible-output polish.
6. `repl.py` (prompt_toolkit) + non-destructive help + plain fallback.
7. Shell `$ans` wrapper, packaging entry point, docs/README.

---

## 15. Spec Review Resolutions (2026-07-10)

An automated spec review ran before implementation. Resolutions below **override**
anything above they touch.

**B1 — `x`/`X` dropped as a multiplication synonym.** It collided with `x` as the
canonical variable/parameter name. Multiplication synonyms are `*`, `×`, `·`, `∗`
only. `2x` means `2 * x` (implicit mult with variable `x`).

**B2/B3 — filter & stdin semantics.** A stdin stream is a sequence of statements
sharing one scope, evaluated top to bottom:
- An **expression** line prints exactly one result line.
- A **binding-only** line (`r = 5`, `f(x)=…`) prints **nothing** but its binding is
  visible to later lines; `ans`/`_` holds the previous *expression* result.
- **argv expression + piped stdin** (`echo "2+2" | calc "ans*10"`) is a distinct
  path: stdin is evaluated (each line, shared scope); the **last value** binds to
  `ans`/`_`; then the argv expression runs once and prints. Invalid stdin → error.
- Empty/whitespace/`#`-comment-only lines are skipped silently. `calc < /dev/null`
  exits 0 with no output.

**B4 — top-level definitions are ephemeral on the CLI.** `calc "c = 5"` or
`calc "f(x)=x^2"` defines within that process only; it **never** writes `calcrc`.
Durable definitions come only from: the new **`calc def "<definition>"`** command,
`calc set` (settings), `calc edit`, or the interactive REPL (which persists
deliberate definitions). This keeps the quick path free of disk side effects and
consistent with the anti-race stance in §6.

**B5 — numeric type model (int-preserving).** Integers are exact Python bigints.
`int (+ - * // % ^) int → int`; `!` on a non-negative integer → int. `/` returns an
int when it divides evenly, else a float. Any float operand, negative power, or a
transcendental function (`sin`, `ln`, `sqrt` of a non-perfect-square, …) yields a
float. This is what makes the formatter's "clean never means wrong" guarantee true:
exact values stay exact; only genuinely-float results get sig-fig cleanup. A size
guard caps runaway integer powers (see N8).

**S1 — `-2^2 = -4`.** Power binds tighter than unary minus (scientific/WolframAlpha
convention), so `-2^2 = -(2^2) = -4` and `2^-3 = 2^(-3)`. (This diverges from
Excel's `4`; a calculator follows math convention. LET/LAMBDA are borrowed from
Excel; operator precedence is not.)

**S2/S13 — base output via `as`, full precision via `--full`.** The `=hex` suffix is
dropped (it collided with `=` assignment). Output base is set by, in decreasing
precedence: a trailing `as <base>` in the expression (`255+1 as hex`), the `-o/--out`
flag, then `calc set base`. `as` is a reserved keyword. Full precision on one call:
the `--full` flag (oneshot) or `\full` before an expression in the REPL.

**S5 — reserved keywords.** Hard-reserved (case-insensitive, never definable):
command verbs `list show del clear edit path set help def shell-init`, grammar
keywords `let lambda mod as xor`, and special identifiers `ans _`. Lambda/function
parameters may not shadow these either.

**S6 — explicit lambda arity.** `lambda(p1, …, pn, body)`: the **last** item is the
body, all preceding items are parameters (each a bare name); minimum two items
(≥1 param + body). `lambda(x, y)` = one param `x`, body `y`.

**S7 — bitwise operators added (integer-only).** `&` (and), `|` (or), `xor` (word;
`^` is power), `~` (prefix not), `<<`, `>>`. C-like precedence, all below arithmetic:
tightest→loosest among them: `<< >>` (9) > `&` (8) > `xor` (7) > `|` (6); all bind
looser than `+`/`-` (10). Bitwise on a non-integer → error. *(Inferred from the
base-support priority; not explicitly requested — trivially removable.)*

**S8/N1 — arithmetic conventions.** `%` and `//` use Python floored semantics:
`-7 % 3 = 2`, `-7 // 2 = -4`. `round(x[,n])` rounds **half away from zero**
(`round(2.5)=3`, `round(-2.5)=-3`) — matching user expectation, not banker's rounding.
`factorial`/`!` requires a non-negative integer (no gamma in v1); else a friendly
error. Division, `%`, and `//` by zero all raise positioned errors.

**S9 — base output of integers only, signed magnitude.** `-5 as hex → -0x5`. No
fractional base output (`0x1.8` unsupported); a non-integer with base output requested
warns and falls back to decimal.

**S10 — argv joining & leading minus.** All non-flag argv tokens are joined with
spaces into one expression (`calc 2 + 2` → `"2 + 2"`). A leading-minus expression is
supported via `calc -- -5` or quoting; a bare `-<digit>…` with no known flag is also
treated as an expression.

**S11 — `e`: exponent vs constant.** `e`/`E` immediately after a digit mantissa and
followed by an optional sign then a digit is a scientific exponent (`2e3=2000`,
`1E3=1000`); otherwise `e` is the constant (`3e` → `3 * e`, `2 e` → `2 * e`).

**S12 — inverse trig honors angle mode.** In degrees mode `asin/acos/atan` return
degrees; in radians mode, radians.

**S3/S4 — shell wrapper.** The wrapper exports only `$ans` (bash clobbers `$_`).
`calc shell-init <bash|zsh|fish|powershell>` emits the correct wrapper per shell;
bash/zsh/fish shipped, PowerShell documented.

**N3/N6 — ephemeral index & calcrc writes.** `calc list` orders items by definition
order in `calcrc` (stable); the index snapshot stores a **content hash** of `calcrc`
(not mtime, so a no-op re-save doesn't falsely invalidate). `calcrc` writes are atomic
(temp + rename); concurrent `calc set`/`def` from two terminals is last-write-wins
(no locking) — acceptable and noted.

**N4 — comments.** `#` begins a comment to end-of-line in all input (oneshot, filter,
calcrc). `5 # 3` evaluates to `5`.

**N5 — adjacency rules.** `identifier(` is **always** a call, never implicit mult (a
non-callable target errors at eval: `r=5; r(3)` → "r is not a function"). `(2)(3) = 6`
(group-before-group is implicit mult). `pi e` and other name-name / number-number
adjacencies without an operator are errors.

**N8 — resource guard.** Integer power `a^b` whose result would exceed a large digit
bound (~100k digits) raises "result too large" instead of hanging, satisfying the
responsiveness priority for a single expression.
