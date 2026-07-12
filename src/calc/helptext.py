"""Help content for `calc help [topic]` and the REPL `?` overlay."""

from __future__ import annotations

from typing import Optional

from calc.engine.builtins import BUILTINS, CONSTANTS

USAGE = """\
calc — a command-line calculator

USAGE
  calc "EXPR"              evaluate an expression        calc "3 + 4*2"  -> 11
  calc EXPR...             bare args are joined          calc 3 + 4 \\* 2
  echo EXPR | calc         read from stdin (filter)      echo 2^10 | calc
  EXPR | calc "ans*10"     stdin value bound to ans/_
  calc                     interactive REPL (at a tty)

OPTIONS
  -o, --out BASE           output base: dec|hex|bin|oct  calc -o hex 255+1
  --deg | --rad            angle mode for this call
  --precision N            significant figures (float display)
  --full                   show full float precision
  -i, --repl               force the interactive REPL
  --version                print version

EXPRESSIONS
  + - * / // %  ^(power)  !(factorial)      2^10, 5!, 7 % 3, 7 // 2
  bitwise: & | ~ << >>  and the word 'xor'  0xF0 | 0x0F, 1 << 8
  bases in: 0x1F 0b1010 0o17   out: 255 as hex
  implicit mult: 2pi, 2(3+4)   comment: 5 # note
  multi-step: r=5; area=pi*r^2; area
  functions:  f(x) = x^2 + 1   then   f(5)
  lambda/let: (lambda(x, x*x))(4)   let a=2, b=3 : a*b

MANAGE DEFINITIONS (persist to calcrc)
  calc def "f(x)=x^2+1"    save a function/constant
  calc list                list saved definitions (numbers them)
  calc show f | show 2     show one (by name or list-number)
  calc del  f | del  2     remove one
  calc clear               remove all (use --yes to skip confirm)
  calc set angle deg       persist a default (angle/base/precision/full)
  calc edit | calc path    open / locate calcrc
  calc help [topic]        this help, or help on a function

Type  calc help functions  for the full function list."""


def _functions_list() -> str:
    lines = ["FUNCTIONS"]
    for name in sorted(BUILTINS):
        lo, hi, _ = BUILTINS[name]
        if hi is None:
            sig = "{}(…)".format(name)
        elif lo == hi == 1:
            sig = "{}(x)".format(name)
        elif name == "log":
            sig = "log(x[, base])"
        elif name == "round":
            sig = "round(x[, n])"
        else:
            sig = "{}({})".format(name, ", ".join(["a"] * lo) + (", …" if hi != lo else ""))
        lines.append("  {:<16} {}".format(sig, _FN_DESC.get(name, "")))
    lines.append("")
    lines.append("CONSTANTS")
    lines.append("  " + ", ".join(sorted(CONSTANTS)))
    return "\n".join(lines)


_FN_DESC = {
    "sqrt": "square root", "cbrt": "cube root", "abs": "absolute value",
    "sin": "sine", "cos": "cosine", "tan": "tangent",
    "asin": "inverse sine", "acos": "inverse cosine", "atan": "inverse tangent",
    "ln": "natural log", "log": "log (natural, or given base)",
    "log2": "base-2 log", "log10": "base-10 log", "exp": "e to the x",
    "floor": "round down", "ceil": "round up",
    "round": "round half away from zero", "sign": "-1, 0, or 1",
    "min": "smallest", "max": "largest", "gcd": "greatest common divisor",
    "lcm": "least common multiple", "factorial": "n! (also postfix !)",
    "hypot": "sqrt(x^2 + y^2)",
}


def help_text(topic: Optional[str] = None) -> str:
    if not topic:
        return USAGE
    t = topic.lower()
    if t in ("functions", "funcs", "fn"):
        return _functions_list()
    if t in BUILTINS:
        lo, hi, _ = BUILTINS[t]
        arity = "1" if lo == hi else ("{}+".format(lo) if hi is None else "{}-{}".format(lo, hi))
        return "{} — {}  (arguments: {})".format(t, _FN_DESC.get(t, ""), arity)
    if t in CONSTANTS:
        return "{} = {}".format(t, CONSTANTS[t])
    return "no help topic '{}'. Try: calc help functions".format(topic)
