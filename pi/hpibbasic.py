# SPDX-License-Identifier: GPL-3.0-only
"""A small GW-BASIC style interpreter with the HP-IB Command Library built in.

Programs are written the way the HP-IB Command Library Reference (82990A) shows
them for interpreted BASIC: line numbers, CALL IOxxx(...), PCIB.ERR error checks,
ON ERROR GOTO handlers. Differences from GW-BASIC are listed in HELP DIFFERENCES.
"""
import math
import os
import random
import re
import sys
import time

import hpiblib
from hpiblib import HpibError, show

__version__ = "2.0.5"


class BasicError(Exception):
    def __init__(self, code, msg=None):
        self.code = code
        self.msg = msg or MESSAGES.get(code, "Unprintable error")
        Exception.__init__(self, self.msg)


class StopProgram(Exception):
    def __init__(self, kind):
        self.kind = kind            # "END" or "STOP"
        Exception.__init__(self, kind)


MESSAGES = {
    1: "NEXT without FOR", 2: "Syntax error", 3: "RETURN without GOSUB", 4: "Out of DATA",
    5: "Illegal function call", 6: "Overflow", 8: "Undefined line number",
    9: "Subscript out of range", 10: "Duplicate Definition", 11: "Division by zero",
    13: "Type mismatch", 19: "No RESUME", 20: "RESUME without error", 26: "FOR without NEXT",
    29: "WHILE without WEND", 30: "WEND without WHILE", 52: "Bad file number",
    53: "File not found", 54: "Bad file mode", 55: "File already open", 62: "Input past end",
    64: "Bad file name", 75: "Path/File access error", 255: "HP-IB Command Library error",
}

KEYWORDS = set("""PRINT LET IF THEN ELSE GOTO GOSUB RETURN FOR TO STEP NEXT WHILE WEND END STOP
REM DIM INPUT LINE CALL ON ERROR RESUME OPTION BASE AND OR XOR NOT MOD SLEEP CLS DATA READ
RESTORE SWAP TRON TROFF OPEN CLOSE AS OUTPUT APPEND WRITE BEEP RANDOMIZE DEF BLOAD COMMON
CLEAR KEY WIDTH LOCATE COLOR SCREEN ERRORS CONTINUE ASK SCAN LINES SHOW MKDIR KILL""".split())
NOOPS = {"DEF", "BLOAD", "COMMON", "CLEAR", "KEY", "WIDTH", "LOCATE", "COLOR", "SCREEN", "RANDOMIZE"}

# Library command argument kinds: a=address/select code, sc=select code, n=number,
# s=string, on/os=numeric/string output variable, ai/ao=array in/out. "?" = optional here.
LIBRARY = {
    "IOABORT": "sc", "IOCLEAR": "a", "IOCONTROL": "sc n n", "IODMA": "sc n n",
    "IOENTER": "a on?", "IOENTERA": "a ao? n? on?", "IOENTERS": "a os? n? on?",
    "IOEOI": "sc n", "IOEOL": "sc s n?", "IOGETTERM": "sc on?", "IOLLOCKOUT": "sc",
    "IOLOCAL": "a", "IOMATCH": "sc s n?", "IOOUTPUT": "a n", "IOOUTPUTA": "a ai n?",
    "IOOUTPUTS": "a s n?", "IOPPOLL": "sc on?", "IOPPOLLC": "a n", "IOPPOLLU": "a",
    "IOREMOTE": "a", "IORESET": "sc", "IOSEND": "sc s n?", "IOSPOLL": "a on?",
    "IOSTATUS": "sc n on?", "IOTIMEOUT": "sc n", "IOTRIGGER": "a",
}
IGNORED_CALLS = {"DEFERR"}       # SETUP.BAS/QBSETUP.BAS housekeeping: nothing to do here

TOKEN_RE = re.compile(r"""\s*(?:
    (?P<num>&[Hh][0-9A-Fa-f]+|&[Oo]?[0-7]+|(?:\d+\.?\d*|\.\d+)(?:[EeDd][+-]?\d+)?[!#%]?)
   |(?P<str>"[^"]*"?)
   |(?P<id>[A-Za-z][A-Za-z0-9.]*[$%!#]?)
   |(?P<op><>|><|<=|=<|>=|=>|[-+*/^\\=<>(),;:#?'])
   )""", re.X)


def tokenize(text):
    toks = []
    pos = 0
    text = text.rstrip("\r\n")
    while pos < len(text):
        if text[pos:].strip() == "":
            break
        m = TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            raise BasicError(2, "Syntax error near '%s'" % text[pos:].strip()[:20])
        pos = m.end()
        if m.group("num") is not None:
            s = m.group("num").rstrip("!#%")
            if s[0] == "&":
                v = int(s[2:], 16) if s[1] in "Hh" else int(s.lstrip("&Oo"), 8)
            else:
                v = float(s.replace("D", "E").replace("d", "e"))
            toks.append(("num", v))
        elif m.group("str") is not None:
            toks.append(("str", m.group("str").strip('"')))
        elif m.group("id") is not None:
            name = m.group("id").upper()
            if name == "REM":
                toks.append(("kw", "REM"))
                break
            toks.append(("kw" if name in KEYWORDS else "id", name))
        else:
            op = m.group("op")
            if op == "'":
                break                       # comment to end of line (no ':' needed)
            if op == "?":
                toks.append(("kw", "PRINT"))
                continue
            toks.append(("op", {"><": "<>", "=<": "<=", "=>": ">="}.get(op, op)))
    toks.append(("eol", None))
    return toks


# ---------------------------------------------------------------- functions

def _num(v):
    if isinstance(v, str):
        raise BasicError(13)
    return v


def _str(v):
    if not isinstance(v, str):
        raise BasicError(13)
    return v


def _int(v):
    v = _num(v)
    if abs(v) > 2 ** 53:
        raise BasicError(6)
    return int(math.floor(v + 0.5)) if v != int(v) else int(v)


def fmt_num(x):
    if x == int(x) and abs(x) < 1e15:
        s = str(int(x))
    else:
        s = ("%.10g" % x).replace("e", "E")
    return s if s.startswith("-") else " " + s


def basic_val(s):
    s = s.strip()
    m = re.match(r"&H([0-9A-F]+)", s, re.I)
    if m:
        return float(int(m.group(1), 16))
    m = re.match(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[EeDd][+-]?\d+)?", s.replace(" ", ""))
    return float(m.group(0).replace("D", "E").replace("d", "e")) if m else 0.0


def _mid(s, start, n=None):
    start = _int(start)
    if start < 1:
        raise BasicError(5)
    return _str(s)[start - 1:] if n is None else _str(s)[start - 1:start - 1 + _int(n)]


def _instr(*a):
    if len(a) == 2:
        start, s, t = 1, a[0], a[1]
    else:
        start, s, t = _int(a[0]), a[1], a[2]
    return float(_str(s).find(_str(t), start - 1) + 1)


def _chr(n):
    n = _int(n)
    if not 0 <= n <= 255:
        raise BasicError(5)
    return chr(n)


def _asc(s):
    if not _str(s):
        raise BasicError(5)
    return float(ord(s[0]))


def _string(n, c):
    return (_chr(c) if not isinstance(c, str) else c[:1]) * _int(n)


def _log(x):
    if _num(x) <= 0:
        raise BasicError(5)
    return math.log(x)


def _sqr(x):
    if _num(x) < 0:
        raise BasicError(5)
    return math.sqrt(x)


FUNCS = {
    "ABS": (1, 1, lambda x: abs(_num(x))), "ATN": (1, 1, lambda x: math.atan(_num(x))),
    "COS": (1, 1, lambda x: math.cos(_num(x))), "SIN": (1, 1, lambda x: math.sin(_num(x))),
    "TAN": (1, 1, lambda x: math.tan(_num(x))), "EXP": (1, 1, lambda x: math.exp(_num(x))),
    "LOG": (1, 1, _log), "SQR": (1, 1, _sqr),
    "INT": (1, 1, lambda x: float(math.floor(_num(x)))), "FIX": (1, 1, lambda x: float(int(_num(x)))),
    "SGN": (1, 1, lambda x: float((_num(x) > 0) - (x < 0))),
    "RND": (0, 1, lambda *x: random.random()),
    "LEN": (1, 1, lambda s: float(len(_str(s)))), "ASC": (1, 1, _asc),
    "VAL": (1, 1, lambda s: basic_val(_str(s))), "CHR$": (1, 1, _chr),
    "STR$": (1, 1, lambda x: fmt_num(_num(x))), "HEX$": (1, 1, lambda x: "%X" % _int(x)),
    "OCT$": (1, 1, lambda x: "%o" % _int(x)),
    "BIN$": (1, 2, lambda x, w=8: format(_int(x), "0%db" % _int(w))),
    "LEFT$": (2, 2, lambda s, n: _str(s)[:max(0, _int(n))]),
    "RIGHT$": (2, 2, lambda s, n: _str(s)[len(_str(s)) - _int(n):] if _int(n) > 0 else ""),
    "MID$": (2, 3, _mid), "INSTR": (2, 3, _instr), "SPACE$": (1, 1, lambda n: " " * _int(n)),
    "STRING$": (2, 2, _string), "UCASE$": (1, 1, lambda s: _str(s).upper()),
    "LCASE$": (1, 1, lambda s: _str(s).lower()), "LTRIM$": (1, 1, lambda s: _str(s).lstrip()),
    "RTRIM$": (1, 1, lambda s: _str(s).rstrip()), "TRIM$": (1, 1, lambda s: _str(s).strip()),
    "SHOW$": (1, 1, lambda s: show(_str(s))),
    "BIT": (2, 2, lambda x, b: -1.0 if (_int(x) >> _int(b)) & 1 else 0.0),
}
ZERO_ARG = {"TIMER", "DATE$", "TIME$", "ERR", "ERL", "RND", "PI"}


# ---------------------------------------------------------------- parser

class Parser(object):
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self, k=0):
        return self.t[min(self.i + k, len(self.t) - 1)]

    def next(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def at(self, kind, val=None):
        tok = self.peek()
        return tok[0] == kind and (val is None or tok[1] == val)

    def accept(self, kind, val=None):
        if self.at(kind, val):
            return self.next()
        return None

    def expect(self, kind, val=None):
        tok = self.accept(kind, val)
        if tok is None:
            want = val if val is not None else kind
            got = self.peek()[1]
            raise BasicError(2, "Syntax error: expected %s%s" % (
                want, "" if got is None else " before '%s'" % got))
        return tok

    def end_of_stmt(self):
        return self.at("eol") or self.at("op", ":") or self.at("kw", "ELSE")

    # expressions, lowest to highest precedence
    def expr(self):
        return self._binary(["XOR"], self._or)

    def _or(self):
        return self._binary(["OR"], self._and)

    def _and(self):
        return self._binary(["AND"], self._not)

    def _not(self):
        if self.accept("kw", "NOT"):
            return ("not", self._not())
        return self._rel()

    def _rel(self):
        left = self._add()
        while self.peek()[0] == "op" and self.peek()[1] in ("=", "<>", "<", ">", "<=", ">="):
            op = self.next()[1]
            left = ("bin", op, left, self._add())
        return left

    def _add(self):
        left = self._mod()
        while self.peek()[0] == "op" and self.peek()[1] in "+-":
            op = self.next()[1]
            left = ("bin", op, left, self._mod())
        return left

    def _mod(self):
        left = self._idiv()
        while self.accept("kw", "MOD"):
            left = ("bin", "MOD", left, self._idiv())
        return left

    def _idiv(self):
        left = self._mul()
        while self.accept("op", "\\"):
            left = ("bin", "\\", left, self._mul())
        return left

    def _mul(self):
        left = self._unary()
        while self.peek()[0] == "op" and self.peek()[1] in "*/":
            op = self.next()[1]
            left = ("bin", op, left, self._unary())
        return left

    def _unary(self):
        if self.accept("op", "-"):
            return ("neg", self._unary())
        if self.accept("op", "+"):
            return self._unary()
        return self._pow()

    def _pow(self):
        left = self._atom()
        while self.accept("op", "^"):
            right = self._unary() if self.at("op", "-") else self._atom()
            left = ("bin", "^", left, right)
        return left

    def _binary(self, ops, sub):
        left = sub()
        while self.peek()[0] == "kw" and self.peek()[1] in ops:
            op = self.next()[1]
            left = ("bin", op, left, sub())
        return left

    def _atom(self):
        tok = self.next()
        if tok[0] == "num":
            return ("num", float(tok[1]))
        if tok[0] == "str":
            return ("str", tok[1])
        if tok[0] == "op" and tok[1] == "(":
            e = self.expr()
            self.expect("op", ")")
            return e
        if tok[0] == "id":
            name = tok[1]
            if self.accept("op", "("):
                args = []
                if not self.at("op", ")"):
                    args.append(self.expr())
                    while self.accept("op", ","):
                        args.append(self.expr())
                self.expect("op", ")")
                if name in FUNCS or name in ("TAB", "SPC", "EOF", "RND"):
                    return ("fn", name, args)
                return ("idx", name, args)
            if name in ZERO_ARG:
                return ("fn", name, [])
            return ("var", name)
        raise BasicError(2, "Syntax error at '%s'" % (tok[1] if tok[1] is not None else "end of line"))

    def lvalue(self):
        tok = self.expect("id")
        name = tok[1]
        if self.accept("op", "("):
            args = [self.expr()]
            while self.accept("op", ","):
                args.append(self.expr())
            self.expect("op", ")")
            return ("idx", name, args)
        return ("var", name)

    def lineno(self):
        tok = self.expect("num")
        return int(tok[1])

    def filenum(self):
        self.accept("op", "#")
        return self.expr()

    # statements
    def statements(self):
        """Statements up to end of line (or ELSE). IF nodes nest their branches."""
        out = []
        while True:
            while self.accept("op", ":"):
                pass
            if self.at("eol") or self.at("kw", "ELSE"):
                return out
            out.append(self.statement())
            if self.at("kw", "ELSE") or self.at("eol"):
                return out
            if not self.accept("op", ":"):
                raise BasicError(2, "Syntax error: unexpected '%s'" % self.peek()[1])

    def branch(self):
        if self.at("num"):
            n = self.lineno()
            return [("GOTO", n)]
        return self.statements()

    def statement(self):
        tok = self.peek()
        if tok[0] == "kw":
            kw = tok[1]
            self.next()
            meth = getattr(self, "st_" + kw, None)
            if meth is None:
                if kw in NOOPS:
                    while not self.end_of_stmt():
                        self.next()
                    return ("NOP",)
                raise BasicError(2, "Syntax error: %s cannot start a statement" % kw)
            return meth()
        if tok[0] == "id":
            name = tok[1]
            if name in LIBRARY or name in IGNORED_CALLS:
                self.next()
                return self.lib_call(name)
            target = self.lvalue()
            self.expect("op", "=")
            return ("LET", target, self.expr())
        raise BasicError(2)

    def lib_call(self, name):
        args = []
        if self.at("op", "="):                # SETUP.BAS entry-point line, e.g. IOCLEAR = PCIB.BASE+3
            while not self.end_of_stmt():
                self.next()
            return ("NOP",)
        save = self.i
        if self.accept("op", "("):
            try:
                args = self._arglist(")")
                self.expect("op", ")")
                if not self.end_of_stmt():
                    raise BasicError(2)
                return ("CALL", name, args)
            except BasicError:
                self.i = save
        if not self.end_of_stmt():
            args = self._arglist(None)
        return ("CALL", name, args)

    def _arglist(self, close):
        args = []
        if close and self.at("op", close):
            return args
        while True:
            args.append(self.expr())
            if not self.accept("op", ","):
                return args

    def st_CALL(self):
        name = self.expect("id")[1]
        return self.lib_call(name)

    def st_REM(self):
        return ("NOP",)

    def st_LET(self):
        target = self.lvalue()
        self.expect("op", "=")
        return ("LET", target, self.expr())

    def st_PRINT(self):
        fn = None
        if self.accept("op", "#"):
            fn = self.expr()
            self.expect("op", ",")
        items = []
        while not self.end_of_stmt():
            if self.accept("op", ";"):
                items.append(";")
            elif self.accept("op", ","):
                items.append(",")
            else:
                items.append(self.expr())
        return ("PRINT", fn, items)

    def st_WRITE(self):
        fn = None
        if self.accept("op", "#"):
            fn = self.expr()
            self.expect("op", ",")
        items = [] if self.end_of_stmt() else self._arglist(None)
        return ("WRITE", fn, items)

    def st_INPUT(self):
        fn, prompt, qmark = None, None, True
        if self.accept("op", "#"):
            fn = self.expr()
            self.expect("op", ",")
        elif self.at("str"):
            prompt = self.next()[1]
            if self.accept("op", ","):
                qmark = False
            else:
                self.expect("op", ";")
        targets = [self.lvalue()]
        while self.accept("op", ","):
            targets.append(self.lvalue())
        return ("INPUT", fn, prompt, qmark, targets)

    def st_LINE(self):
        self.expect("kw", "INPUT")
        fn, prompt = None, None
        if self.accept("op", "#"):
            fn = self.expr()
            self.expect("op", ",")
        elif self.at("str"):
            prompt = self.next()[1]
            if not self.accept("op", ";"):
                self.expect("op", ",")
        return ("LINEINPUT", fn, prompt, self.lvalue())

    def st_IF(self):
        cond = self.expr()
        if self.accept("kw", "GOTO"):
            then = [("GOTO", self.lineno())]
            if not self.end_of_stmt():
                raise BasicError(2)
        else:
            self.expect("kw", "THEN")
            then = self.branch()
        other = []
        if self.accept("kw", "ELSE"):
            other = self.branch()
        return ("IF", cond, then, other)

    def st_GOTO(self):
        return ("GOTO", self.lineno())

    def st_GOSUB(self):
        return ("GOSUB", self.lineno())

    def st_RETURN(self):
        return ("RETURN",)

    def st_ON(self):
        if self.accept("kw", "ERROR"):
            self.expect("kw", "GOTO")
            return ("ONERROR", self.lineno())
        e = self.expr()
        kind = "GOSUB" if self.accept("kw", "GOSUB") else None
        if kind is None:
            self.expect("kw", "GOTO")
            kind = "GOTO"
        lines = [self.lineno()]
        while self.accept("op", ","):
            lines.append(self.lineno())
        return ("ON", e, kind, lines)

    def st_ERROR(self):
        return ("ERROR", self.expr())

    def st_RESUME(self):
        if self.accept("kw", "NEXT"):
            return ("RESUME", "NEXT")
        if self.at("num"):
            n = self.lineno()
            return ("RESUME", n if n else None)
        return ("RESUME", None)

    def st_FOR(self):
        var = self.expect("id")[1]
        self.expect("op", "=")
        start = self.expr()
        self.expect("kw", "TO")
        stop = self.expr()
        step = self.expr() if self.accept("kw", "STEP") else ("num", 1.0)
        return ("FOR", var, start, stop, step)

    def st_NEXT(self):
        names = []
        if self.at("id"):
            names.append(self.next()[1])
            while self.accept("op", ","):
                names.append(self.expect("id")[1])
        return ("NEXT", names)

    def st_WHILE(self):
        return ("WHILE", self.expr())

    def st_WEND(self):
        return ("WEND",)

    def st_END(self):
        return ("END",)

    def st_STOP(self):
        return ("STOP",)

    def st_DIM(self):
        decls = []
        while True:
            name = self.expect("id")[1]
            self.expect("op", "(")
            dims = [self.expr()]
            while self.accept("op", ","):
                dims.append(self.expr())
            self.expect("op", ")")
            decls.append((name, dims))
            if not self.accept("op", ","):
                return ("DIM", decls)

    def st_OPTION(self):
        if self.accept("kw", "BASE"):
            return ("OPTIONBASE", int(self.expect("num")[1]))
        self.expect("kw", "ERRORS")
        if self.accept("kw", "STOP"):
            return ("OPTIONERRORS", True)
        self.expect("kw", "CONTINUE")
        return ("OPTIONERRORS", False)

    def st_SLEEP(self):
        return ("SLEEP", self.expr() if not self.end_of_stmt() else ("num", 1.0))

    def st_CLS(self):
        return ("CLS",)

    def st_BEEP(self):
        return ("BEEP",)

    def st_TRON(self):
        return ("TRON", True)

    def st_TROFF(self):
        return ("TRON", False)

    def st_DATA(self):
        items = []
        while not self.at("eol") and not self.at("op", ":"):
            tok = self.next()
            if tok[0] == "op" and tok[1] == ",":
                continue
            if tok[0] == "op" and tok[1] == "-" and self.at("num"):
                items.append(-self.next()[1])
            else:
                items.append(tok[1])
        return ("DATA", items)

    def st_READ(self):
        targets = [self.lvalue()]
        while self.accept("op", ","):
            targets.append(self.lvalue())
        return ("READ", targets)

    def st_RESTORE(self):
        return ("RESTORE", self.lineno() if self.at("num") else None)

    def st_SWAP(self):
        a = self.lvalue()
        self.expect("op", ",")
        return ("SWAP", a, self.lvalue())

    def st_OPEN(self):
        name = self.expr()
        self.expect("kw", "FOR")
        mode = self.next()
        if mode[1] not in ("INPUT", "OUTPUT", "APPEND"):
            raise BasicError(2, "Syntax error: OPEN ... FOR INPUT, OUTPUT or APPEND")
        self.expect("kw", "AS")
        return ("OPEN", name, mode[1], self.filenum())

    def st_CLOSE(self):
        nums = []
        while not self.end_of_stmt():
            nums.append(self.filenum())
            self.accept("op", ",")
        return ("CLOSE", nums)

    def st_MKDIR(self):
        return ("MKDIR", self.expr())

    def st_KILL(self):
        return ("KILL", self.expr())

    def st_ASK(self):
        args = self._arglist(None)
        if len(args) < 3 and not self.end_of_stmt():
            # e.g. ASK 723 "H1": something follows the address with no comma in between
            raise BasicError(2, 'Syntax error: a comma is missing. Separate the parts with commas: '
                                'ASK 723, "H1"   or   ASK 723, "H1", R$')
        if not 2 <= len(args) <= 3:
            raise BasicError(2, 'Syntax error: ASK address, command$ [, reply$]   e.g. ASK 723, "H1"')
        return ("ASK", args)

    def st_SCAN(self):
        return ("SCAN", None if self.end_of_stmt() else self.expr())

    def st_LINES(self):
        return ("LINES", None if self.end_of_stmt() else self.expr())

    def st_SHOW(self):
        return ("SHOW", None if self.end_of_stmt() else self.expr())


def flatten(stmts, out):
    """Turn nested IF nodes into conditional jumps inside one flat statement list."""
    for s in stmts:
        if s[0] == "IF":
            at = len(out)
            out.append(None)
            flatten(s[2], out)
            if s[3]:
                jmp = len(out)
                out.append(None)
                else_at = len(out)
                flatten(s[3], out)
                out[jmp] = ("JMP", len(out))
                out[at] = ("IFJ", s[1], else_at)
            else:
                out[at] = ("IFJ", s[1], len(out))
        else:
            out.append(s)
    return out


def compile_line(text):
    p = Parser(tokenize(text))
    stmts = p.statements()
    if not p.at("eol"):
        raise BasicError(2, "Syntax error: unexpected '%s'" % p.peek()[1])
    return flatten(stmts, [])


# ---------------------------------------------------------------- interpreter

class Interpreter(object):
    def __init__(self, lib, out=None, inp=None):
        self.lib = lib
        self.write = out or (lambda s: (sys.stdout.write(s), sys.stdout.flush()))
        self.input = inp or input
        self.program = {}          # line number -> source text
        self.stop_on_hpib_error = True
        self.tron = False
        self.cont_pc = None
        self.files = {}
        self.col = 0
        self.failed = False
        self.clear()

    # ------------------------------------------------ state
    def clear(self):
        self.vars = {}
        self.arrays = {}
        self.base = 0
        self.for_stack = []
        self.gosub_stack = []
        self.while_stack = []
        self.on_error = None
        self.in_handler = False
        self.err = 0
        self.erl = 0
        self.err_pc = None
        self.err_msg = ""
        self.data = []
        self.data_ptr = 0
        self.close_files()
        for code, (mnem, _msg) in hpiblib.ERRORS.items():
            self.vars[mnem] = float(code)
        self.vars.update({"PCIB.ERR": 0.0, "PCIB.ERR$": "", "PCIB.GLBERR": 0.0,
                          "PCIB.BASERR": 255.0, "TRUE": -1.0, "FALSE": 0.0})

    def flush_files(self):
        for f in self.files.values():
            try:
                f["fh"].flush()
            except Exception:
                pass

    def close_files(self):
        for f in getattr(self, "files", {}).values():
            try:
                f["fh"].close()
            except Exception:
                pass
        self.files = {}

    # ------------------------------------------------ program editing
    def store_line(self, number, text):
        if not 0 <= number <= 65529:
            raise BasicError(5, "Line numbers must be 0-65529")
        if text.strip():
            self.program[number] = text.strip()
            self.cont_pc = None
            compile_line(text)                    # report syntax errors now (line is kept)
        elif number in self.program:
            del self.program[number]
            self.cont_pc = None
        else:
            raise BasicError(8)

    def list_lines(self, lo=None, hi=None):
        out = []
        for n in sorted(self.program):
            if (lo is None or n >= lo) and (hi is None or n <= hi):
                out.append("%d %s" % (n, self.program[n]))
        return out

    def load_text(self, text, merge=False):
        if not merge:
            self.program = {}
        bad = []
        for raw in text.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            m = re.match(r"(\d+)\s?(.*)$", raw)
            if not m:
                raise BasicError(2, "Syntax error: program line without a line number: %s" % raw[:40])
            n = int(m.group(1))
            self.program[n] = m.group(2).strip()
            try:
                compile_line(m.group(2))
            except BasicError as e:
                bad.append((n, e.msg))
        self.cont_pc = None
        return bad

    def program_text(self):
        return "".join("%d %s\n" % (n, self.program[n]) for n in sorted(self.program))

    # ------------------------------------------------ running
    def _compile_all(self, keep_data=False):
        self.lines = sorted(self.program)
        self.index = {n: i for i, n in enumerate(self.lines)}
        self.code = []
        ptr = self.data_ptr
        self.data = []
        self.data_lines = {}
        for n in self.lines:
            try:
                stmts = compile_line(self.program[n])
            except BasicError as e:
                raise BasicError(e.code, "%s in %d" % (e.msg, n))
            self.code.append(stmts)
            for s in stmts:
                if s[0] == "DATA":
                    self.data_lines.setdefault(n, len(self.data))
                    self.data.extend(s[1])
        self.data_ptr = ptr if keep_data else 0

    def run(self, start=None, keep_vars=False):
        if not keep_vars:
            self.clear()
        self._compile_all()
        if not self.lines:
            return
        if start is None:
            li = 0
        elif start in self.index:
            li = self.index[start]
        else:
            raise BasicError(8)
        self._execute((li, 0))

    def cont(self):
        if self.cont_pc is None:
            raise BasicError(17, "Can't continue")
        pc, self.cont_pc = self.cont_pc, None
        self._compile_all(keep_data=True)
        self._execute(pc)

    def _jump_line(self, n):
        if n not in self.index:
            raise BasicError(8, "Undefined line number %d" % n)
        return (self.index[n], 0)

    def _execute(self, pc):
        self.pc = pc
        last_line = None
        while True:
            li, si = self.pc
            if li >= len(self.code):
                break
            stmts = self.code[li]
            if si >= len(stmts):
                if self.lines[li] is not None and li + 1 < len(self.lines) and self.lines[li + 1] is None:
                    break                     # program ran off its end: don't re-run the direct line
                self.pc = (li + 1, 0)
                continue
            line = self.lines[li]
            if self.tron and line != last_line and line is not None:
                self.write("[%d]" % line)
            last_line = line
            self.cur = (li, si)
            self.pc = (li, si + 1)
            try:
                self.exec_stmt(stmts[si])
            except StopProgram as sp:
                self.flush_files()
                if sp.kind == "STOP":
                    self.cont_pc = self.pc
                    self._newline()
                    self.write(_where("Break", line) + "\n")
                if sp.kind == "END":
                    self.close_files()
                return
            except KeyboardInterrupt:
                self.flush_files()
                self.cont_pc = self.cur if line is not None else None
                self._newline()
                self.write(_where("Break", line) + "\n")
                return
            except BasicError as e:
                if self.on_error is not None and not self.in_handler:
                    self.err, self.erl, self.err_msg = e.code, line or 0, e.msg
                    self.err_pc = self.cur
                    self.in_handler = True
                    self.pc = self._jump_line(self.on_error)
                    continue
                self.flush_files()
                self._newline()
                self.failed = True
                self.write(_where(e.msg, line) + "\n")
                self.cont_pc = None
                return
        self._newline()

    def _newline(self):
        if self.col:
            self.write("\n")
            self.col = 0

    def immediate(self, text):
        """Run one direct-mode line (no line number). It runs as a temporary last
        program line, so FOR/NEXT, WHILE/WEND and GOTO into the program all work."""
        stmts = compile_line(text)
        try:
            self._compile_all(keep_data=True)
        except BasicError:
            self.lines, self.index, self.code = [], {}, []
        self.lines.append(None)
        self.code.append(stmts)
        self._execute((len(self.code) - 1, 0))

    # ------------------------------------------------ expressions
    def _truth(self, v):
        return _num(v) != 0

    def eval(self, e):
        k = e[0]
        if k == "num" or k == "str":
            return e[1]
        if k == "var":
            name = e[1]
            if name in self.vars:
                return self.vars[name]
            return "" if name.endswith("$") else 0.0
        if k == "idx":
            arr, pos = self._element(e[1], e[2])
            return arr["data"][pos]
        if k == "neg":
            return -_num(self.eval(e[1]))
        if k == "not":
            return float(~_int(self.eval(e[1])))
        if k == "fn":
            return self._call_fn(e[1], e[2])
        if k == "bin":
            return self._binop(e[1], self.eval(e[2]), self.eval(e[3]))
        raise BasicError(2)

    def _binop(self, op, a, b):
        if op == "+":
            if isinstance(a, str) and isinstance(b, str):
                return a + b
            return _num(a) + _num(b)
        if op in ("=", "<>", "<", ">", "<=", ">="):
            if isinstance(a, str) != isinstance(b, str):
                raise BasicError(13)
            r = {"=": a == b, "<>": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]
            return -1.0 if r else 0.0
        a, b = _num(a), _num(b)
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                raise BasicError(11)
            return a / b
        if op == "^":
            try:
                return float(a ** b)
            except (OverflowError, ZeroDivisionError):
                raise BasicError(6)
        if op in ("\\", "MOD"):
            ia, ib = _int(a), _int(b)
            if ib == 0:
                raise BasicError(11)
            q = abs(ia) // abs(ib) * (1 if (ia >= 0) == (ib >= 0) else -1)
            return float(q) if op == "\\" else float(ia - q * ib)
        ia, ib = _int(a), _int(b)
        return float({"AND": ia & ib, "OR": ia | ib, "XOR": ia ^ ib}[op])

    def _call_fn(self, name, args):
        if name == "TIMER":
            t = time.localtime()
            return float(t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec) + time.time() % 1
        if name == "DATE$":
            return time.strftime("%m-%d-%Y")
        if name == "TIME$":
            return time.strftime("%H:%M:%S")
        if name == "ERR":
            return float(self.err)
        if name == "ERL":
            return float(self.erl)
        if name == "PI":
            return math.pi
        vals = [self.eval(a) for a in args]
        if name == "TAB":
            n = max(1, _int(vals[0]))
            return " " * max(0, n - 1 - self.col)
        if name == "SPC":
            return " " * max(0, _int(vals[0]))
        if name == "EOF":
            f = self._file(vals[0], "INPUT")
            pos = f["fh"].tell()
            at_end = f["fh"].readline() == ""
            f["fh"].seek(pos)
            return -1.0 if at_end else 0.0
        lo, hi, fn = FUNCS[name]
        if not lo <= len(vals) <= hi:
            raise BasicError(5, "Illegal function call: %s takes %s argument(s)" % (
                name, lo if lo == hi else "%d-%d" % (lo, hi)))
        try:
            return fn(*vals)
        except (ValueError, OverflowError):
            raise BasicError(5)

    # ------------------------------------------------ variables / arrays
    def _dim(self, name, bounds):
        if name in self.arrays:
            raise BasicError(10)
        size = 1
        for b in bounds:
            if b < self.base:
                raise BasicError(9)
            size *= b - self.base + 1
        self.arrays[name] = {"dims": bounds, "data": ["" if name.endswith("$") else 0.0] * size}

    def _element(self, name, idx_exprs, create=True):
        idx = [_int(self.eval(x)) for x in idx_exprs]
        if name not in self.arrays:
            if not create:
                raise BasicError(9)
            self._dim(name, [10] * len(idx))
        arr = self.arrays[name]
        if len(idx) != len(arr["dims"]):
            raise BasicError(9)
        pos = 0
        for i, b in zip(idx, arr["dims"]):
            if not self.base <= i <= b:
                raise BasicError(9)
            pos = pos * (b - self.base + 1) + (i - self.base)
        return arr, pos

    def assign(self, target, value):
        name = target[1]
        if name.endswith("$"):
            value = _str(value)
        else:
            value = float(_num(value))
        if target[0] == "var":
            if name in ("ERR", "ERL"):
                raise BasicError(2)
            self.vars[name] = value
        else:
            arr, pos = self._element(name, target[2])
            arr["data"][pos] = value

    def _array_ref(self, e):
        """(array, start position) for an array argument: NAME(i) start element or bare NAME."""
        if e[0] == "idx":
            return self._element(e[1], e[2])
        if e[0] == "var":
            if e[1] not in self.arrays:
                self._dim(e[1], [10])
            return self.arrays[e[1]], 0
        raise BasicError(13, "Type mismatch: an array element such as READINGS(1) is needed here")

    # ------------------------------------------------ output
    def emit(self, text, fnum=None):
        if fnum is not None:
            f = self._file(fnum, "OUTPUT")
            f["fh"].write(text)
            f["col"] = len(text) - text.rfind("\n") - 1 if "\n" in text else f["col"] + len(text)
            return
        self.write(text)
        if "\n" in text:
            self.col = len(text) - text.rfind("\n") - 1
        else:
            self.col += len(text)

    def _col(self, fnum):
        return self.col if fnum is None else self._file(fnum, "OUTPUT")["col"]

    def _file(self, fnum, mode):
        n = _int(fnum if not isinstance(fnum, tuple) else self.eval(fnum))
        if n not in self.files:
            raise BasicError(52)
        f = self.files[n]
        if (mode == "INPUT") != (f["mode"] == "INPUT"):
            raise BasicError(54)
        return f

    # ------------------------------------------------ statements
    def exec_stmt(self, s):
        k = s[0]
        if k == "NOP" or k == "DATA":
            return
        getattr(self, "x_" + k)(s)

    def x_LET(self, s):
        self.assign(s[1], self.eval(s[2]))

    def x_PRINT(self, s):
        fnum = None if s[1] is None else self.eval(s[1])
        items = s[2]
        for it in items:
            if it == ";":
                continue
            if it == ",":
                col = self._col(fnum)
                self.emit(" " * (14 - col % 14), fnum)
                continue
            v = self.eval(it)
            self.emit(v if isinstance(v, str) else fmt_num(v) + " ", fnum)
        if not items or items[-1] not in (";", ","):
            self.emit("\n", fnum)

    def x_WRITE(self, s):
        fnum = None if s[1] is None else self.eval(s[1])
        parts = []
        for it in s[2]:
            v = self.eval(it)
            parts.append('"%s"' % v if isinstance(v, str) else fmt_num(v).strip())
        self.emit(",".join(parts) + "\n", fnum)

    def _read_input_line(self, prompt):
        self._newline()
        try:
            return self.input(prompt)
        except EOFError:
            raise BasicError(62)

    def x_INPUT(self, s):
        _k, fnum, prompt, qmark, targets = s
        if fnum is not None:
            f = self._file(self.eval(fnum), "INPUT")
            fields = []
            while len(fields) < len(targets):
                line = f["fh"].readline()
                if not line:
                    raise BasicError(62)
                fields.extend(_split_fields(line.rstrip("\r\n")))
            for t, v in zip(targets, fields):
                self.assign(t, v if t[1].endswith("$") else basic_val(v))
            return
        while True:
            text = self._read_input_line((prompt or "") + ("? " if qmark else ""))
            fields = _split_fields(text)
            if len(fields) != len(targets) or any(
                    not t[1].endswith("$") and not re.match(r"^\s*[-+]?(\d|\.\d|&H)", v or "0", re.I)
                    for t, v in zip(targets, fields)):
                self.write("?Redo from start\n")
                continue
            for t, v in zip(targets, fields):
                self.assign(t, v if t[1].endswith("$") else basic_val(v))
            return

    def x_LINEINPUT(self, s):
        _k, fnum, prompt, target = s
        if fnum is not None:
            line = self._file(self.eval(fnum), "INPUT")["fh"].readline()
            if not line:
                raise BasicError(62)
            self.assign(target, line.rstrip("\r\n"))
        else:
            self.assign(target, self._read_input_line(prompt or ""))

    def x_IFJ(self, s):
        if not self._truth(self.eval(s[1])):
            self.pc = (self.cur[0], s[2])

    def x_JMP(self, s):
        self.pc = (self.cur[0], s[1])

    def x_GOTO(self, s):
        self.pc = self._jump_line(s[1])

    def x_GOSUB(self, s):
        self.gosub_stack.append(self.pc)
        self.pc = self._jump_line(s[1])

    def x_RETURN(self, s):
        if not self.gosub_stack:
            raise BasicError(3)
        self.pc = self.gosub_stack.pop()

    def x_ON(self, s):
        n = _int(self.eval(s[1]))
        if n < 0 or n > 255:
            raise BasicError(5)
        if 1 <= n <= len(s[3]):
            if s[2] == "GOSUB":
                self.gosub_stack.append(self.pc)
            self.pc = self._jump_line(s[3][n - 1])

    def x_ONERROR(self, s):
        self.on_error = s[1] or None
        if s[1] == 0 and self.in_handler:
            self.in_handler = False
            raise BasicError(self.err, self.err_msg)

    def x_ERROR(self, s):
        code = _int(self.eval(s[1]))
        if code == 255:
            msg = "HP-IB error %d (%s): %s" % (self.vars.get("PCIB.ERR", 0), _mnemonic(self.vars.get("PCIB.ERR", 0)),
                                               self.vars.get("PCIB.ERR$", ""))
            raise BasicError(255, msg)
        raise BasicError(code)

    def x_RESUME(self, s):
        if not self.in_handler:
            raise BasicError(20)
        self.in_handler = False
        if s[1] is None:
            self.pc = self.err_pc
        elif s[1] == "NEXT":
            self.pc = (self.err_pc[0], self.err_pc[1] + 1)
        else:
            self.pc = self._jump_line(s[1])

    def x_FOR(self, s):
        _k, var, start, stop, step = s
        self.assign(("var", var), self.eval(start))
        limit, inc = _num(self.eval(stop)), _num(self.eval(step))
        self.for_stack = [f for f in self.for_stack if f[0] != var]
        v = self.vars[var]
        if (inc >= 0 and v > limit) or (inc < 0 and v < limit):
            self.pc = self._skip_to_next(var)
            return
        self.for_stack.append((var, limit, inc, self.pc))

    def _scan(self, pc, opener, closer):
        """Position after the closer (NEXT/WEND) that matches, searching from pc."""
        depth = 0
        li, si = pc
        while li < len(self.code):
            stmts = self.code[li]
            while si < len(stmts):
                k = stmts[si][0]
                if k == opener:
                    depth += 1
                elif k == closer:
                    count = max(1, len(stmts[si][1])) if closer == "NEXT" else 1
                    for _ in range(count):
                        if depth == 0:
                            return (li, si + 1)
                        depth -= 1
                si += 1
            li, si = li + 1, 0
        return None

    def _skip_to_next(self, var):
        pc = self._scan(self.pc, "FOR", "NEXT")
        if pc is None:
            raise BasicError(26)
        return pc

    def x_NEXT(self, s):
        names = s[1] or [None]
        for name in names:
            while self.for_stack and name and self.for_stack[-1][0] != name:
                self.for_stack.pop()
            if not self.for_stack:
                raise BasicError(1)
            var, limit, inc, body = self.for_stack[-1]
            v = self.vars.get(var, 0.0) + inc
            self.vars[var] = v
            if (inc >= 0 and v <= limit) or (inc < 0 and v >= limit):
                self.pc = body
                return
            self.for_stack.pop()

    def x_WHILE(self, s):
        if self._truth(self.eval(s[1])):
            if not self.while_stack or self.while_stack[-1] != self.cur:
                self.while_stack.append(self.cur)
        else:
            if self.while_stack and self.while_stack[-1] == self.cur:
                self.while_stack.pop()
            pc = self._scan(self.pc, "WHILE", "WEND")
            if pc is None:
                raise BasicError(29)
            self.pc = pc

    def x_WEND(self, s):
        if not self.while_stack:
            raise BasicError(30)
        self.pc = self.while_stack[-1]

    def x_END(self, s):
        raise StopProgram("END")

    def x_STOP(self, s):
        raise StopProgram("STOP")

    def x_DIM(self, s):
        for name, dims in s[1]:
            self._dim(name, [_int(self.eval(d)) for d in dims])

    def x_OPTIONBASE(self, s):
        if s[1] not in (0, 1):
            raise BasicError(5)
        if self.arrays:
            raise BasicError(10)
        self.base = s[1]

    def x_OPTIONERRORS(self, s):
        self.stop_on_hpib_error = s[1]

    def x_SLEEP(self, s):
        t = _num(self.eval(s[1]))
        if t > 0:
            time.sleep(t)

    def x_CLS(self, s):
        self.write("\x1b[2J\x1b[H")
        self.col = 0

    def x_BEEP(self, s):
        self.write("\a")

    def x_TRON(self, s):
        self.tron = s[1]

    def x_READ(self, s):
        for t in s[1]:
            if self.data_ptr >= len(self.data):
                raise BasicError(4)
            v = self.data[self.data_ptr]
            self.data_ptr += 1
            if t[1].endswith("$"):
                v = v if isinstance(v, str) else fmt_num(v).strip()
            elif isinstance(v, str):
                raise BasicError(13, "Syntax error in DATA (number expected)")
            self.assign(t, v)

    def x_RESTORE(self, s):
        if s[1] is None:
            self.data_ptr = 0
        elif s[1] in self.data_lines:
            self.data_ptr = self.data_lines[s[1]]
        else:
            later = [n for n in self.data_lines if n >= s[1]]
            self.data_ptr = self.data_lines[min(later)] if later else len(self.data)

    def x_SWAP(self, s):
        a, b = self.eval(s[1]), self.eval(s[2])
        if isinstance(a, str) != isinstance(b, str):
            raise BasicError(13)
        self.assign(s[1], b)
        self.assign(s[2], a)

    def x_OPEN(self, s):
        name = _str(self.eval(s[1]))
        n = _int(self.eval(s[3]))
        if not 1 <= n <= 15:
            raise BasicError(52)
        if n in self.files:
            raise BasicError(55)
        mode = s[2]
        try:
            fh = open(os.path.expanduser(name), {"INPUT": "r", "OUTPUT": "w", "APPEND": "a"}[mode],
                      encoding="latin-1", newline="")
        except FileNotFoundError:
            raise BasicError(53)
        except OSError as e:
            raise BasicError(64, "Bad file name: %s" % e)
        self.files[n] = {"fh": fh, "mode": mode, "col": 0}

    def x_CLOSE(self, s):
        nums = [_int(self.eval(x)) for x in s[1]] or list(self.files)
        for n in nums:
            f = self.files.pop(n, None)
            if f:
                f["fh"].close()

    def x_MKDIR(self, s):
        name = os.path.expanduser(_str(self.eval(s[1])))
        try:
            os.mkdir(name)
        except FileExistsError:
            raise BasicError(75, "Path/File access error: %s already exists" % name)
        except OSError as e:
            raise BasicError(75, "Path/File access error: %s" % e)

    def x_KILL(self, s):
        name = os.path.expanduser(_str(self.eval(s[1])))
        if any(f["fh"].name == name for f in self.files.values()):
            raise BasicError(55, "File already open: %s" % name)
        try:
            os.remove(name)
        except FileNotFoundError:
            raise BasicError(53, "File not found: %s" % name)
        except OSError as e:
            raise BasicError(75, "Path/File access error: %s" % e)

    # ------------------------------------------------ HP-IB
    def _lib_error(self, e):
        self.vars["PCIB.ERR"] = float(e.code)
        self.vars["PCIB.ERR$"] = e.message
        self.vars["PCIB.GLBERR"] = float(e.code)
        if self.stop_on_hpib_error:
            raise BasicError(255, "HP-IB error %d (%s): %s%s" % (
                e.code, e.mnemonic, e.message, " - " + e.detail if e.detail else ""))

    def x_CALL(self, s):
        name, args = s[1], s[2]
        if name in IGNORED_CALLS:
            return
        if name not in LIBRARY:
            raise BasicError(5, "Illegal function call: %s is not an HP-IB Library command (HELP LIBRARY)" % name)
        spec = LIBRARY[name].split()
        need = len([k for k in spec if not k.endswith("?")])
        if not need <= len(args) <= len(spec):
            raise BasicError(5, "Illegal function call: %s needs %s parameter(s) - HELP %s" % (
                name, need if need == len(spec) else "%d to %d" % (need, len(spec)), name))
        vals = []
        for kind, a in zip(spec, args):
            kind = kind.rstrip("?")
            if kind in ("a", "sc", "n"):
                vals.append(_num(self.eval(a)))
            elif kind == "s":
                vals.append(_str(self.eval(a)))
            elif kind in ("on", "os"):
                if a[0] not in ("var", "idx"):
                    raise BasicError(13, "Type mismatch: parameter %d of %s must be a variable" % (
                        args.index(a) + 1, name))
                if a[1].endswith("$") != (kind == "os"):
                    raise BasicError(13, "Type mismatch: parameter %d of %s must be a %s variable" % (
                        args.index(a) + 1, name, "string" if kind == "os" else "numeric"))
                vals.append(a)
            else:
                vals.append(self._array_ref(a))
        vals += [None] * (len(spec) - len(vals))
        try:
            self._do_call(name, vals)
        except HpibError as e:
            self._lib_error(e)
            return
        self.vars["PCIB.ERR"] = 0.0
        self.vars["PCIB.ERR$"] = ""

    def _result(self, target, value, label=None):
        if target is not None:
            self.assign(target, value)
        else:
            self._newline()
            if label:
                self.write(label(value) + "\n")
            elif isinstance(value, str):
                self.write(show(value) + "\n")
            else:
                self.write(fmt_num(value).strip() + "\n")

    def _do_call(self, name, v):
        lib = self.lib
        m = name.lower()
        if name == "IOENTER":
            try:
                r = lib.ioenter(v[0])
            except HpibError as e:
                if e.value is not None:
                    self._result(v[1], e.value) if v[1] is not None else None
                raise
            self._result(v[1], r)
        elif name == "IOENTERS":
            max_len = 255 if v[2] is None else _int(v[2])
            try:
                r = lib.ioenters(v[0], max_len)
            except HpibError as e:
                if v[1] is not None and e.value is not None:
                    self.assign(v[1], e.value)
                if v[3] is not None:
                    self.assign(v[3], float(len(e.value or "")))
                raise
            self._result(v[1], r)
            if v[3] is not None:
                self.assign(v[3], float(len(r)))
        elif name == "IOENTERA":
            arr, pos = v[1] if v[1] is not None else (None, 0)
            room = len(arr["data"]) - pos if arr else 1000
            max_el = room if v[2] is None else _int(v[2])
            if arr and max_el > room:
                raise BasicError(9, "Subscript out of range: array has room for %d element(s)" % room)
            try:
                nums = lib.ioentera(v[0], max_el)
            except HpibError as e:
                nums = e.value or []
                self._store_array(arr, pos, nums, v[3])
                raise
            self._store_array(arr, pos, nums, v[3])
            if arr is None:
                self._newline()
                self.write(" ".join(fmt_num(x).strip() for x in nums) + "\n")
        elif name == "IOOUTPUTA":
            arr, pos = v[1]
            n = len(arr["data"]) - pos if v[2] is None else _int(v[2])
            if n < 0 or pos + n > len(arr["data"]):
                raise BasicError(9, "Subscript out of range: only %d element(s) after the start element"
                                 % (len(arr["data"]) - pos))
            data = arr["data"][pos:pos + n]
            if any(isinstance(x, str) for x in data):
                raise BasicError(13)
            lib.iooutputa(v[0], data)
        elif name in ("IOOUTPUTS", "IOSEND", "IOEOL"):
            getattr(lib, m)(v[0], v[1], None if v[2] is None else _int(v[2]))
        elif name == "IOMATCH":
            lib.iomatch(v[0], v[1], 1 if v[2] is None else v[2])
        elif name == "IOSPOLL":
            self._result(v[1], float(lib.iospoll(v[0])), _spoll_label)
        elif name == "IOPPOLL":
            self._result(v[1], float(lib.ioppoll(v[0])), _spoll_label)
        elif name == "IOGETTERM":
            self._result(v[1], float(lib.iogetterm(v[0])), _term_label)
        elif name == "IOSTATUS":
            self._result(v[2], float(lib.iostatus(v[0], v[1])))
        else:
            getattr(lib, m)(*[x for x in v if x is not None])

    def _store_array(self, arr, pos, nums, actual):
        if arr is not None:
            for i, x in enumerate(nums):
                arr["data"][pos + i] = float(x)
        if actual is not None:
            self.assign(actual, float(len(nums)))

    # extensions
    def x_ASK(self, s):
        vals = [self.eval(a) for a in s[1][:2]]
        target = s[1][2] if len(s[1]) == 3 else None
        if target is not None and (target[0] not in ("var", "idx") or not target[1].endswith("$")):
            raise BasicError(13, "Type mismatch: ASK reply must go into a string variable")
        try:
            self.lib.iooutputs(_num(vals[0]), _str(vals[1]))
            r = self.lib.ioenters(_num(vals[0]), 255)
        except HpibError as e:
            self._lib_error(e)
            return
        self.vars["PCIB.ERR"] = 0.0
        self.vars["PCIB.ERR$"] = ""
        self._result(target, r)

    def _sc(self, e):
        return 7 if e is None else _num(self.eval(e))

    def x_SCAN(self, s):
        try:
            found = self.lib.scan(self._sc(s[1]))
        except HpibError as e:
            self._lib_error(e)
            return
        sc = int(self._sc(s[1]))
        self._newline()
        if found:
            self.write("Listeners found: %s\n" % ", ".join("%d (address %d)" % (p, sc * 100 + p) for p in found))
        else:
            self.write("No listeners found on select code %d\n" % sc)

    def x_LINES(self, s):
        try:
            states = self.lib.lines(self._sc(s[1]))
        except HpibError as e:
            self._lib_error(e)
            return
        self._newline()
        self.write("  ".join("%s=%s" % (n, "?" if v is None else ("1" if v else "0")) for n, v in states)
                   + "   (1 = asserted)\n")

    def x_SHOW(self, s):
        try:
            st = self.lib.settings(self._sc(s[1]))
        except HpibError as e:
            self._lib_error(e)
            return
        self._newline()
        tmo = st["timeout"]
        self.write("Select code %d = linux-gpib board %d, interface bus address %d\n" % (
            int(self._sc(s[1])), st["board"], st["bus address"]))
        self.write("IOTIMEOUT %s   IOEOI %s   IOEOL %s   IOMATCH %s   last IOGETTERM %d\n" % (
            ("%g s" % tmo) if tmo else "0 (off)", "on" if st["EOI"] else "off", show(st["EOL"]),
            show(st["MATCH"]) if st["MATCH"] is not None else "off", st["last termination"]))
        self.write("OPTION ERRORS %s   PCIB.ERR %d %s\n" % (
            "STOP" if self.stop_on_hpib_error else "CONTINUE", self.vars["PCIB.ERR"],
            self.vars["PCIB.ERR$"]))


def _where(msg, line):
    return msg if line is None else "%s in %d" % (msg, line)


def _mnemonic(code):
    return hpiblib.ERRORS.get(int(code), ("?", ""))[0]


def _spoll_label(v):
    v = int(v)
    return "%d  (&H%02X, bits 7..0 = %s%s)" % (v, v, format(v, "08b"), ", RQS" if v & 64 else "")


def _term_label(v):
    v = int(v)
    why = [t for bit, t in ((1, "count reached"), (2, "match character"), (4, "EOI")) if v & bit]
    return "%d  (%s)" % (v, ", ".join(why) if why else "other")


def _split_fields(text):
    fields, cur, inq = [], "", False
    for c in text:
        if c == '"':
            inq = not inq
        elif c == "," and not inq:
            fields.append(cur.strip())
            cur = ""
        else:
            cur += c
    fields.append(cur.strip() if not inq else cur)
    return fields
