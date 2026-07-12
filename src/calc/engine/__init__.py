"""The calc engine: tokenizer -> parser -> evaluator -> formatter.

Zero third-party dependencies. The public surface is :func:`evaluate`; every
frontend and test calls it the same way.
"""

from calc.engine.errors import CalcError, LexError, ParseError, EvalError
from calc.engine.settings import Settings
from calc.engine.evaluator import Scope, NOTHING
from calc.engine.api import evaluate, Result

__all__ = [
    "evaluate", "Result", "Scope", "Settings", "NOTHING",
    "CalcError", "LexError", "ParseError", "EvalError",
]
