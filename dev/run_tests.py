#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""PC-side tests for the Pi programs, using the fake gpib module (no Pi or meter needed).

    python dev/run_tests.py                 # current Python
    uv run --python 3.11 dev/run_tests.py   # Python of Raspberry Pi OS Bookworm
    uv run --python 3.9  dev/run_tests.py   # Python of Raspberry Pi OS Bullseye

Test vectors (sources and licenses: docs/THIRD-PARTY-NOTICES.md section 4):
  sample_calram.txt       example dump from github.com/PatrickBaus/pyAsyncHP3478A (GPL-3.0)
  tomverbeure_calram.txt  dump from github.com/tomverbeure/hp3478a_calibration README (BSD-2-Clause)
  vinayshanbhag_calram.bin  raw 256-byte '@'..'O' dump from github.com/vinayshanbhag/hp3478a (no license stated)
hpibterm.py is tested against pi/hpib_sim.py (simulated bus with an HP 3478A at 723).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PI = os.path.join(os.path.dirname(HERE), "pi")
MODULE = os.path.join(PI, "instruments", "hp3478a")          # the HP 3478A instrument module
CAL = os.path.join(MODULE, "hp3478a_cal.py")
LOG = os.path.join(MODULE, "hp3478a_log.py")
TERM = os.path.join(PI, "hpibterm.py")
EXAMPLES = os.path.join(PI, "examples")                       # core examples
MOD_EXAMPLES = os.path.join(MODULE, "examples")               # the module's examples


def all_examples():
    return [os.path.join(d, n) for d in (EXAMPLES, MOD_EXAMPLES) for n in sorted(os.listdir(d)) if n.endswith(".bas")]
SAMPLE = os.path.join(HERE, "sample_calram.txt")
TOM = os.path.join(HERE, "tomverbeure_calram.txt")
VINAY = os.path.join(HERE, "vinayshanbhag_calram.bin")
# (offset, gain) per entry as printed in vinayshanbhag/hp3478a README for that dump
VINAY_EXPECTED = [(175, 1.023421), (41, 1.0232), (3, 1.022818), (-3, 1.023378), (0, 1.022991),
                  (0, 1.0), (1008, 1.02092), (-102, 1.005329), (-11, 1.005097), (-2, 1.004728),
                  (-2, 1.005035), (-1, 1.004905), (-1, 1.004834), (-2, 1.005195), (4, 1.034679),
                  (1, 1.034265), (0, 1.0), (881, 1.032502), (0, 1.0)]
FAILS = []


def tom_checksums(nib):
    """Tom Verbeure's verify_checksum(), verbatim logic: True per entry if sum == 255."""
    res = []
    for entry in range(19):
        total = 0
        for idx in range(13):
            val = nib[entry * 13 + idx + 1]
            total += val * 16 if idx == 11 else val
        res.append(total == 255)
    return res


def nibbles(path):
    return [b - 64 for b in open(path, "rb").read() if b not in b"\r\n"]


def run(script, args, ram=None, cal="1", stdin=None, fake=True, xlog=None):
    env = dict(os.environ)
    env.pop("FAKE_XLOG", None)
    if xlog:
        env["FAKE_XLOG"] = xlog
    env["PYTHONPATH"] = os.path.join(HERE, "fake_gpib") if fake else ""
    env["CAL"] = cal
    env.pop("FAKE_RAM", None)
    if ram:
        env["FAKE_RAM"] = ram
    p = subprocess.run([sys.executable, script] + args, env=env, input=stdin,
                       capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout + p.stderr


def check(name, cond, out=""):
    print("%-48s %s" % (name, "PASS" if cond else "FAIL"))
    if not cond:
        FAILS.append(name)
        print("    " + out.strip().replace("\n", "\n    ")[-800:])


def term(args, stdin=None, env_extra=None):
    """Run hpibterm.py (normally with --sim) and return (exit code, output)."""
    env = dict(os.environ)
    env["PYTHONPATH"] = ""
    env.pop("HPIB_SIM_READING", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, TERM] + args, env=env, input=stdin,
                       capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout + p.stderr


def sim(*commands, **kw):
    args = ["--sim"]
    for c in commands:
        args += ["-c", c]
    return term(args, **kw)


class Recorder(object):
    """Wraps hpib_sim and records what the library asks linux-gpib to do."""

    def __init__(self):
        sys.path.insert(0, PI)
        import importlib
        import hpib_sim
        self.g = importlib.reload(hpib_sim)
        self.log = []

    def __getattr__(self, name):
        f = getattr(self.g, name)
        if not callable(f) or name in ("GpibError",):
            return f

        def wrapped(*a):
            self.log.append((name,) + a)
            return f(*a)
        return wrapped


def test_library():
    sys.path.insert(0, PI)
    import hpiblib
    from hpiblib import HpibError, format_real
    cases = {12.3: " 12.3", 5.0: " 5", -0.5: "-0.5", 0.0: " 0", 1e7: " 1.000000E+07",
             1e-6: " 1.000000E-06", 123456.7: " 123456.7", -2.5e-5: "-0.000025",
             1.0 / 3: " 0.3333333", 1234567.0: " 1.234567E+06"}
    got = {k: format_real(k) for k in cases}
    check("IOOUTPUT number format (manual 2-44)", all(got[k] == v for k, v in cases.items()), str(got))
    r = Recorder()
    lib = hpiblib.Library(r, {7: 0})
    ok = lib.address(7) == (7, None, None) and lib.address(723) == (7, 23, None) \
        and lib.address(72315) == (7, 23, 15)
    check("addressing: 7 / 723 / 72315", ok)
    codes = []
    for bad in (3, 731, 700, 7.5, 72331):
        try:
            lib.address(bad)
        except HpibError as e:
            codes.append(e.code)
    check("addressing: bad values -> ESEL 100002", codes == [100002] * 5, str(codes))

    def err_of(fn, *a):
        try:
            fn(*a)
        except HpibError as e:
            return e.code
        return 0
    check("ERANGE: IOTIMEOUT -1, IOEOL len 9, IOCONTROL 4, IOSTATUS 8, IOPPOLLC 16",
          [err_of(lib.iotimeout, 7, -1), err_of(lib.ioeol, 7, "x" * 9, 9), err_of(lib.iocontrol, 7, 4, 1),
           err_of(lib.iostatus, 7, 8), err_of(lib.ioppollc, 723, 16)] == [100003] * 5)
    check("ESEL: IOSPOLL needs a device, IOABORT a select code",
          err_of(lib.iospoll, 7) == 100002 and err_of(lib.ioabort, 723) == 100002)

    r.log[:] = []
    lib.iooutputs(723, "F1" + chr(200), None)
    writes = [e for e in r.log if e[0] == "write"]
    check("IOOUTPUTS sends bytes + CR/LF, CHR$(200) stays one byte",
          writes and writes[-1][2] == b"F1\xc8\r\n", repr(writes))
    lib.ioeol(7, "", 0)
    r.log[:] = []
    lib.iooutputs(723, "X" + chr(5) + chr(0x0F))
    check("IOEOL 0 length: binary command sent exactly", [e[2] for e in r.log if e[0] == "write"] == [b"X\x05\x0f"])
    lib.ioeol(7, "\r\n", 2)
    r.log[:] = []
    lib.ioppollc(723, 10)
    cmds = [e[2] for e in r.log if e[0] == "command"]
    check("IOPPOLLC bus bytes: UNL MTA LAD23 PPC PPE", cmds == [bytes([0x3F, 0x40, 0x37, 0x05, 0x6A])], repr(cmds))
    r.log[:] = []
    lib.ioclear(7)
    lib.iollockout(7)
    lib.ioppollu(7)
    lib.iosend(7, "?" + chr(32 + 9) + chr(32 + 15), None)
    lib.iotrigger(7)
    cmds = [e[2] for e in r.log if e[0] == "command"]
    check("DCL / LLO / PPU / IOSEND bytes / GET", cmds == [b"\x14", b"\x11", b"\x15", b"?)/", b"\x08"], repr(cmds))
    r.log[:] = []
    lib.iotimeout(7, 2.5)
    lib.iospoll(723)
    tm = [e for e in r.log if e[0] == "timeout"]
    check("IOTIMEOUT 2.5 s -> linux-gpib T3s on board and devices", tm and all(e[2] == 12 for e in tm), repr(tm))
    v = lib.ioenter(723)
    check("IOENTER reads a 3478A reading; IOGETTERM = 4 (EOI)",
          abs(v - 1.23456) < 1e-3 and lib.iogetterm(7) == 4, "%r %r" % (v, lib.iogetterm(7)))
    s5 = lib.ioenters(723, 5)
    check("IOENTERS max.length 5 -> 5 chars, IOGETTERM bit 1", len(s5) == 5 and lib.iogetterm(7) & 1, repr(s5))
    lib.ioclear(723)
    lib.iomatch(7, "E", 1)
    s6 = lib.ioenters(723, 80)
    check("IOMATCH 'E': IOENTERS stops after the match character (kept)",
          s6.endswith("E") and lib.iogetterm(7) & 2, repr(s6))
    lib.iomatch(7, "\n", 1)
    lib.ioclear(723)
    check("IOENTERA with EOI on: stops at first EOI", len(lib.ioentera(723, 3)) == 1)
    lib.ioeoi(7, 0)
    check("IOENTERA with IOEOI 7,0: keeps reading to max.elements", len(lib.ioentera(723, 3)) == 3)
    lib.ioeoi(7, 1)
    check("IOENTER on empty address -> ETIME", err_of(lib.ioenter, 705) == 100004)
    check("IOOUTPUTS to empty address -> ETIME", err_of(lib.iooutputs, 705, "x", None) == 100004)
    check("SCAN finds the meter at 23", lib.scan(7) == [23])

    class NoPpollLib:                      # libgpib with a driver that has no parallel poll
        def ibrpp(self, board, ppr):
            return 0x8000                  # ERR
    real_cdll, real_gpib = hpiblib.ctypes.CDLL, lib.gpib
    hpiblib.ctypes.CDLL = lambda name: NoPpollLib()
    lib.gpib = object()                    # real linux-gpib bindings: no parallel_poll()
    try:
        msg = ""
        try:
            lib.ioppoll(7)
        except HpibError as e:
            msg = str(e)
    finally:
        hpiblib.ctypes.CDLL, lib.gpib = real_cdll, real_gpib
    check("IOPPOLL on a driver without parallel poll explains it (gpib_bitbang)",
          "gpib_bitbang" in msg and "IOSPOLL" in msg, msg)


def test_terminal(tmp):
    import hpibhelp
    import hpibbasic
    for f in ["hpiblib.py", "hpibbasic.py", "hpibterm.py", "hpibhelp.py", "hpib_sim.py"] + \
            [os.path.relpath(p, PI) for p in all_examples()]:
        check("LF line endings: " + f.replace(os.sep, "/"), b"\r\n" not in open(os.path.join(PI, f), "rb").read())
    check("HELP covers all 26 library commands", sorted(hpibhelp.LIB) == sorted(hpibbasic.LIBRARY)
          and len(hpibbasic.LIBRARY) == 26)
    missing = [n for n in hpibbasic.LIBRARY if not hasattr(__import__("hpiblib").Library, n.lower())]
    check("every library command is implemented", not missing, str(missing))

    rc, out = sim('ASK 723, "H1"')
    check("ASK 723 H1 -> 3478A reading", rc == 0 and re.search(r'"\+1\.23\d+E\+0<CR><LF>"', out), out)
    rc, out = sim('IOOUTPUTS 723, "F1RAN5T4"', 'IOOUTPUTS 723, "T3": IOENTER 723, V: PRINT "V="; V')
    check("IOOUTPUTS/IOENTER into a variable", rc == 0 and re.search(r"V= 1\.23", out), out)
    rc, out = sim('CALL IOOUTPUTS(723, "KM01T4"): CALL IOOUTPUTS(723, "T3"): CALL IOSPOLL(723, S): PRINT S')
    check("IOSPOLL after SRQ on data ready = 65", rc == 0 and out.strip().endswith("65"), out)
    rc, out = sim('IOSPOLL 723')
    check("IOSPOLL without variable prints the bits", "bits 7..0" in out, out)
    rc, out = sim('IOENTERS 705')
    check("batch: HP-IB error -> message + exit code 1", rc == 1 and "100004 (ETIME)" in out, out)
    rc, out = sim('OPTION ERRORS CONTINUE: IOENTERS 705: PRINT "ERR="; PCIB.ERR; PCIB.ERR$; PCIB.GLBERR')
    check("OPTION ERRORS CONTINUE sets PCIB.ERR / PCIB.ERR$ / GLBERR",
          "ERR= 100004 HPIB: timeout 100004" in out, out)
    rc, out = sim('IOEOI 7, 0: DIM R(9): IOENTERA 723, R(1), 4, N: PRINT N; R(1); R(4); R(5)')
    check("IOENTERA into array from element 1", re.search(r" 4  1\.23\d+  1\.23\d+  0 ", out), out)
    rc, out = sim('FOR I = 1 TO 3: PRINT I;: NEXT I: PRINT', 'I = 0: WHILE I < 3: I = I + 1: WEND: PRINT "W"; I')
    check("direct mode FOR/NEXT and WHILE/WEND", " 1  2  3" in out and "W 3" in out, out)
    rc, out = sim('PRINT LEN("ABC"); MID$("HELLO", 2, 3); CHR$(65); HEX$(255); BIN$(5, 4); 7 \\ 2; 7 MOD 3')
    check("functions and operators", "3 ELL" in out and "AFF0101 3  1" in out, out)
    rc, out = sim('PRINT (65 AND 64) = 64; NOT 0; BIT(65, 6); 2 ^ 10; &H41')
    check("logic: bit tests, NOT, ^, hex", "-1 -1 -1  1024  65" in out, out)

    prog = os.path.join(tmp, "p.bas")
    with open(prog, "w", newline="\n") as f:
        f.write('5 DATA 3, "X"\n10 READ N, A$: GOSUB 100\n20 ON N GOTO 30, 30, 40\n30 PRINT "BAD": END\n'
                '40 PRINT "OK"; N; A$\n50 IF N = 3 THEN PRINT "THEN" ELSE PRINT "ELSE"\n60 END\n'
                '100 PRINT "SUB": RETURN\n')
    rc, out = term(["--sim", prog, "--run"])
    check("program: DATA/READ, GOSUB, ON GOTO, IF/ELSE", rc == 0 and "SUB\n" in out.replace("\r", "")
          and "OK 3 X" in out and "THEN" in out and "BAD" not in out, out)
    rc, out = term(["--sim", prog, "-c", "RENUM 100, 5", "-c", "LIST"])
    check("RENUM renumbers and fixes GOSUB/ON GOTO targets",
          "105 READ N, A$: GOSUB 135" in out and "110 ON N GOTO 115, 115, 120" in out, out)
    saved = os.path.join(tmp, "copy")
    rc, out = term(["--sim", prog, "-c", 'SAVE "%s"' % saved.replace("\\", "/"), "-c", "NEW",
                    "-c", 'LOAD "%s"' % saved.replace("\\", "/"), "-c", "RUN"])
    check("SAVE / NEW / LOAD / RUN round trip (.bas added)", os.path.exists(saved + ".bas")
          and "OK 3 X" in out and b"\r\n" not in open(saved + ".bas", "rb").read(), out)
    rc, out = term(["--sim"], stdin="AUTO\nPRINT 1\nPRINT 2\nPRINT 3\n\nDELETE 20\n30\nLIST\n"
                                     "FILES examples\nRUN\nBYE\n")
    lst = out.replace("\r", "")
    check("REPL: AUTO, DELETE, delete by number, LIST, FILES", "10 PRINT 1\n" in lst and "20 PRINT" not in lst
          and "30 PRINT" not in lst and "3478a_read.bas" in lst and "HP-IB>  1 \n" in lst, out)
    rc, out = sim("10 PRINT 1: STOP", "20 PRINT 2", "RUN", "CONT")
    check("STOP / CONT", "Break in 10" in out and " 2" in out, out)
    rc, out = sim("10 X = 1 / 0", "RUN")
    check("BASIC error reported with line number", "Division by zero in 10" in out, out)
    rc, out = sim("10 PRINT (1", "LIST")
    check("syntax error reported when the line is typed (line kept)", "Syntax error" in out and "10 PRINT (1" in out, out)
    rc, out = sim("10 INPUT \"N\"; N: PRINT N * 2", "RUN", stdin="abc\n21\n")
    check("INPUT: redo on bad number", "?Redo from start" in out and " 42" in out, out)
    rc, out = sim("HELP IOENTERS", "HELP LIBRARY", "HELP NOSUCH")
    check("HELP topics", "max.length" in out and "IOTRIGGER" in out and "Sorry, no documentation on NOSUCH" in out, out)
    rc, out = sim("HELP COMMAND SAVE")
    check("HELP COMMAND SAVE shows only SAVE", out.startswith("COMMAND SAVE") and 'SAVE "file"' in out
          and "LOAD" not in out and "MERGE" not in out, out)
    rc, a1 = sim("HELP COM SA")
    rc, a2 = sim("help save")
    check("VMS-style abbreviations and HELP <name> without the category", a1 == out and a2 == out, a1 + a2)
    rc, out = sim("HELP LIBRARY IOENTERS BUS")
    check("third level: HELP LIBRARY IOENTERS BUS_ACTIVITY", out.startswith("LIBRARY IOENTERS Bus_activity")
          and "ATN UNL MLA TAD" in out, out)
    rc, out = sim("HELP LIB IOENT*")
    check("wildcards: HELP LIB IOENT* -> IOENTER, IOENTERA, IOENTERS",
          all("LIBRARY %s\n" % n in out.replace("\r", "") for n in ("IOENTER", "IOENTERA", "IOENTERS")), out)
    rc, out = sim("HELP ON ERROR", "HELP FUNCTION MID", "HELP ERRORS ETIME", "HELP/NOPROMPT QUIT")
    check("multi-word names, $ optional, error codes, synonyms", "STATEMENT ON ERROR" in out
          and "FUNCTION MID$" in out and "100004" in out and "COMMAND BYE" in out, out)
    rc, out = sim("HELP COMMAND XYZ")
    check("unknown subtopic -> Sorry + what is available", "Sorry, no documentation on COMMAND XYZ" in out
          and "Additional information available" in out and "SAVE" in out, out)
    import hpibhelp
    import hpibterm
    missing = [w for w in sorted(hpibterm.COMMANDS) if not hpibhelp.find([w])]
    stmts = ["LET", "PRINT", "WRITE", "INPUT", "LINE INPUT", "IF", "GOTO", "GOSUB", "RETURN", "ON", "ON ERROR",
             "RESUME", "ERROR", "FOR", "NEXT", "WHILE", "WEND", "END", "STOP", "REM", "DIM", "OPTION BASE",
             "OPTION ERRORS", "SLEEP", "CLS", "BEEP", "TRON", "TROFF", "DATA", "READ", "RESTORE", "SWAP",
             "OPEN", "CLOSE", "CALL", "ASK", "SCAN", "LINES", "SHOW", "MKDIR", "KILL"]
    missing += [w for w in stmts if not hpibhelp.find(["STATEMENT"] + w.split())]
    missing += [f for f in sorted(hpibbasic.FUNCS) + ["TAB", "SPC", "EOF", "TIMER", "DATE$", "TIME$", "PI",
                                                       "ERR", "ERL"] if not hpibhelp.find(["FUNCTION", f])]
    missing += [n for n in hpibbasic.LIBRARY if not hpibhelp.find(["LIBRARY", n])]
    check("every command, statement, function and library call has a help entry", not missing, str(missing))
    said = []
    answers = iter(["SAVE", "?", "", "STATEMENT", "FOR", "", "", ""])
    hpibhelp.Session(lambda prompt: (said.append("<" + prompt + ">"), next(answers))[1], said.append).run(["COMMAND"])
    text = "\n".join(said)
    check("interactive Topic?/Subtopic? prompts, ? redisplays, Enter goes up",
          "<COMMAND Subtopic? >" in text and "COMMAND SAVE\n" in text and text.count("Terminal commands - type") == 2 and "<Topic? >" in text
          and "<STATEMENT Subtopic? >" in text and "STATEMENT FOR" in text and said[-1] == "<Topic? >", text)
    said = []
    answers = iter(["IOENTERS", "TOP", "LIBRARY", "IOSPOLL", "SAVE", "ERRORS", "ETIME", "^"])

    def ask(prompt):
        said.append("<" + prompt + ">")
        nxt = next(answers, None)
        if nxt is None:
            raise EOFError
        return nxt
    hpibhelp.Session(ask, said.append).run([])
    text = "\n".join(said)
    prompts = [x for x in said if x.startswith("<")]
    check("HELP: TOP / ^ jump to the top level; names from anywhere; hint shown",
          "TOP goes to the top level" in text and prompts == [
              "<Topic? >", "<LIBRARY IOENTERS Subtopic? >", "<Topic? >", "<LIBRARY Subtopic? >",
              "<LIBRARY IOSPOLL Subtopic? >", "<COMMAND Subtopic? >", "<ERRORS Subtopic? >",
              "<ERRORS Subtopic? >", "<Topic? >"] and "COMMAND SAVE" in text, str(prompts))
    rc, out = sim("TRACE ON", "IOCLEAR 723")
    check("TRACE shows bus activity", "[bus] ATN UNL MTA LAD 23 SDC" in out, out)
    rc, out = sim("SCAN", "LINES", "SHOW")
    check("SCAN / LINES / SHOW", "23 (address 723)" in out and "SRQ=0" in out and "IOTIMEOUT 10 s" in out, out)
    rc, out = sim('IOCLEAR 3')
    check("unknown select code -> ESEL", "100002 (ESEL)" in out, out)
    rc, out = term(["-c", "IOCLEAR 723"])
    check("no gpib module -> friendly message", rc != 0 and "--sim" in out, out)

    csv = os.path.join(tmp, "term_log.csv")
    for path in all_examples():
        name = os.path.basename(path)
        rc, out = term(["--sim", path, "-c", "QUIT"])
        check("example loads without syntax errors: " + name, rc == 0 and "line " not in out, out)
        if name == "manual_example.bas":
            continue                        # needs an HP 3325A and HP 3456A
        stdin = "1\n3\n0\n%s\n" % csv if name == "3478a_log.bas" else None
        rc, out = term(["--sim", path, "--run"], stdin=stdin)
        check("example runs on the simulator: " + name, rc == 0 and " in " not in out.split("lines)")[-1], out)
    rows = open(csv).read().splitlines() if os.path.exists(csv) else []
    check("3478a_log.bas wrote 3 CSV rows", len(rows) == 3 and all(r.count(",") == 1 for r in rows), str(rows))
    rc, out = term(["--sim", os.path.join(MOD_EXAMPLES, "3478a_read.bas"), "--run"],
                   env_extra={"HPIB_SIM_READING": "+9.99999E+9"})
    check("3478a_read.bas shows OVERLOAD", "OVERLOAD" in out, out)
    test_calsave(tmp)


def test_calsave(tmp):
    """examples/3478a_calsave.bas against the simulated meter's calibration RAM."""
    prog = os.path.join(MOD_EXAMPLES, "3478a_calsave.bas")
    entry = re.compile(r"^(\d+)\s+.+?\s(-?\d+)\s+(\d\.\d{6})\s+(\S+)", re.M)

    def run_in(name, ram=None, extra=None):
        d = os.path.join(tmp, name)
        os.makedirs(d, exist_ok=True)
        env = dict(extra or {})
        if ram:
            env["HPIB_SIM_CALRAM"] = ram
        old = os.getcwd()
        os.chdir(d)
        try:
            rc, out = term(["--sim", prog, "--run"], env_extra=env)
        finally:
            os.chdir(old)
        bdir = os.path.join(d, "backups")
        files = sorted(os.listdir(bdir)) if os.path.isdir(bdir) else []
        return rc, out, bdir, files

    for vec in (SAMPLE, TOM, VINAY):
        tag = os.path.basename(vec)
        rc, out, bdir, files = run_in("cs_" + tag, vec)
        txt = [f for f in files if f.endswith(".txt") and not f.endswith(".info.txt")]
        ok = rc == 0 and len(txt) == 1 and "Saved and checked" in out
        check("calsave.bas: saves .txt/.bin/.info.txt (%s)" % tag, ok and len(files) == 3, out)
        if not ok:
            continue
        base = os.path.join(bdir, txt[0][:-4])
        want = nibbles(vec) if not vec.endswith(".bin") else [b - 64 for b in open(vec, "rb").read()]
        got_txt = nibbles(base + ".txt")
        check("calsave.bas: .txt is the meter RAM byte for byte (%s)" % tag, got_txt == want)
        check("calsave.bas: .bin = 256 raw nibbles (%s)" % tag, list(open(base + ".bin", "rb").read()) == want)
        for ext in (".txt", ".bin"):
            rc2, out2 = run(CAL, ["decode", base + ext], fake=False)
            check("hp3478a_cal.py accepts the calsave %s (%s)" % (ext, tag),
                  rc2 == 0 and "all used entries valid" in out2, out2)
        rc2, out2 = run(CAL, ["decode", vec], fake=False)
        py = [m.groups() for m in entry.finditer(out2)]
        bas = [m.groups() for m in entry.finditer(open(base + ".info.txt").read())]
        check("calsave.bas decode = hp3478a_cal.py decode, all 19 entries (%s)" % tag,
              len(bas) == 19 and bas == py, "%s\n%s" % (bas[:3], py[:3]))
    got = [(int(m.group(2)), float(m.group(3))) for m in entry.finditer(open(base + ".info.txt").read())]
    check("calsave.bas: Vinay's dump decodes to his published offsets/gains", got == VINAY_EXPECTED, str(got))

    rc, out, bdir, files = run_in("cs_twice", SAMPLE)
    rc, out, bdir, files = run_in("cs_twice", SAMPLE)
    txt = [f for f in files if f.endswith(".txt") and not f.endswith(".info.txt")]
    check("calsave.bas: a second run never overwrites the first", len(txt) == 2 and len(files) == 6, str(files))
    rc, out, bdir, files = run_in("cs_glitch", SAMPLE, {"HPIB_SIM_CAL_GLITCH": "300"})
    check("calsave.bas: reads differ -> nothing saved", "differ in 1 place" in out and not files, out)
    rc, out, bdir, files = run_in("cs_stale", SAMPLE, {"HPIB_SIM_STALE_READING": "1"})
    txt = [f for f in files if f.endswith(".txt") and not f.endswith(".info.txt")]
    same = len(txt) == 1 and open(os.path.join(bdir, txt[0]), "rb").read().replace(b"\n", b"") == \
        open(SAMPLE, "rb").read().replace(b"\n", b"")
    check("calsave.bas: reading left waiting -> thrown away, RAM saved", rc == 0 and same, out)
    rc, out, bdir, files = run_in("cs_empty", None, {"HPIB_SIM_EMPTY": "1"})
    check("calsave.bas: no meter -> HP-IB error message, nothing saved",
          "HP-IB error 100004" in out and "Nothing was saved" in out and not files, out)
    blank = os.path.join(tmp, "blank_ram.txt")
    with open(blank, "w", newline="\n") as f:
        f.write(("@" * 16 + "\n") * 16)
    rc, out, bdir, files = run_in("cs_blank", blank)
    check("calsave.bas: lost calibration -> saved, with BAD entries and a warning",
          len(files) == 3 and "INVALID checksum in 16 used entry(s)" in out and "WARNING" in out, out)
    rc, out = sim('MKDIR "%s"' % os.path.join(tmp, "mk").replace("\\", "/"),
                  'MKDIR "%s"' % os.path.join(tmp, "mk").replace("\\", "/"),
                  'OPEN "%s/x.txt" FOR OUTPUT AS #1: CLOSE #1' % os.path.join(tmp, "mk").replace("\\", "/"),
                  'KILL "%s/x.txt"' % os.path.join(tmp, "mk").replace("\\", "/"),
                  'KILL "%s/x.txt"' % os.path.join(tmp, "mk").replace("\\", "/"))
    check("MKDIR / KILL (and their errors 75 / 53)", os.path.isdir(os.path.join(tmp, "mk"))
          and "Path/File access error" in out and "File not found" in out
          and not os.path.exists(os.path.join(tmp, "mk", "x.txt")), out)


def test_license_headers():
    root = os.path.dirname(HERE)
    files = [os.path.join(PI, f) for f in os.listdir(PI) if f.endswith((".py", ".sh"))]
    files += all_examples()
    files += [os.path.join(MODULE, f) for f in os.listdir(MODULE) if f.endswith(".py")]
    for sub in ("pc", "docs"):
        files += [os.path.join(root, sub, f) for f in os.listdir(os.path.join(root, sub))
                  if f.endswith((".ps1", ".css"))]
    files += [os.path.join(HERE, "run_tests.py"), os.path.join(HERE, "fake_gpib", "gpib.py"),
              os.path.join(HERE, "test_menu_pty.py"), os.path.join(HERE, "test_install.sh"),
              os.path.join(HERE, "test_kit.sh"), os.path.join(root, "install.sh"),
              os.path.join(root, "uninstall.sh")]
    bad = []
    for f in files:
        # .ps1: inside the comment-based help (.NOTES), because a line above it hides the help
        head = "".join(open(f, encoding="utf-8", errors="replace").readlines()[:60 if f.endswith(".ps1") else 3])
        if f.endswith("manual_example.bas"):
            ok = "Hewlett-Packard's example" in head and "not covered" in head
        else:
            ok = "SPDX-License-Identifier: GPL-3.0-only" in head
        if not ok:
            bad.append(os.path.relpath(f, root))
    check("license header in every source file (%d files)" % len(files), not bad, str(bad))
    lic = open(os.path.join(root, "LICENSE"), encoding="utf-8").read()
    docs = os.path.join(root, "docs")
    guides = ("HP-IB-Terminal-Introduction", "HP-IB-Terminal-Guide",
              "pi-GPIBTerm-Setup-Guide", "HP3478A-Module-Guide", "THIRD-PARTY-NOTICES")
    check("documentation sources are in docs\\, not the root",
          all(os.path.isfile(os.path.join(docs, g + ".md")) for g in guides)
          and not [f for f in os.listdir(root) if f.lower().endswith((".md", ".html", ".png"))
                   and f not in ("PROJECT.md", "README.md")])
    check("LICENSE is the GNU GPL version 3", lic.lstrip().startswith("GNU GENERAL PUBLIC LICENSE")
          and "Version 3, 29 June 2007" in lic)
    check("no HP manual PDF inside the project (linked instead)",
          not [f for f in os.listdir(root) + os.listdir(PI) if f.lower().endswith(".pdf")
               and "command_library" in f.lower()])


def test_driver_not_loaded():
    """/dev/gpib0 missing (driver not loaded) gives a clear message, not EUNKNOWN."""
    import tempfile
    sys.path.insert(0, PI)
    import hpiblib

    class FakeErr(Exception):
        pass

    class RealishGpib(object):          # looks like linux-gpib: no SIMULATED flag
        GpibError = FakeErr

        def ibsta(self):
            return 0

    lib = hpiblib.Library(RealishGpib(), {7: 0})
    empty = tempfile.mkdtemp()
    msg = lib.driver_problem(dev_dir=empty) or ""
    check("driver check: missing /dev/gpib0 explained",
          "gpib0 does not exist" in msg and "gpib.service" in msg, msg)
    open(os.path.join(empty, "gpib0"), "w").close()
    check("driver check: present /dev/gpib0 is fine",
          lib.driver_problem(dev_dir=empty) in (None,) or "permission" in lib.driver_problem(dev_dir=empty))
    e = lib._map_error(FakeErr("listener() error: Bad file descriptor (errno: 9)"))
    check("Bad file descriptor maps to ESEL, not EUNKNOWN", e.code == hpiblib.ESEL, "%s %s" % (e.code, e))
    import hpib_sim
    check("simulator is exempt from the driver check", hpiblib.Library(hpib_sim, {7: 0}).driver_problem() is None)


def test_ask_missing_comma():
    rc, out = term(["--sim", "-c", 'ASK 723 "H1"', "-c", 'ASK 723', "-c", 'ASK 723, "H1"'])
    check("ASK without comma names the missing comma", "a comma is missing" in out, out)
    check("ASK with only an address shows an example", 'e.g. ASK 723, "H1"' in out, out)
    check("ASK with the comma still works", "+1.2345" in out, out)


def test_ren():
    """REN: a meter in local ignores its commands (seen on the real 3478A)."""
    w1 = 'ASK 723, "W" + CHR$(1)'
    rc, out = term(["--sim", "-c", w1])
    check("REN: set at start-up, W gets a cal nibble", re.search(r'^"[@-O]"', out, re.M), out)
    rc, out = term(["--sim", "-c", "IOLOCAL 7", "-c", w1])
    check("REN: IOLOCAL 7 -> meter ignores W, answers with a reading", '"+1.2345' in out, out)
    rc, out = term(["--sim", "-c", "IOLOCAL 7", "-c", "IOREMOTE 7", "-c", w1])
    check("REN: IOREMOTE 7 -> commands obeyed again", re.search(r'^"[@-O]"', out, re.M), out)
    rc, out = term(["--sim", "-c", "IOLOCAL 7", "-c", "IORESET 7", "-c", w1])
    check("REN: IORESET pulses REN and sets it again", re.search(r'^"[@-O]"', out, re.M), out)
    prog = os.path.join(MOD_EXAMPLES, "3478a_calsave.bas")
    d = tempfile.mkdtemp()
    old = os.getcwd()
    os.chdir(d)
    try:
        rc, out = term(["--sim", "-c", "IOLOCAL 7", "-c", 'RUN "%s"' % prog.replace("\\", "/")])
    finally:
        os.chdir(old)
    check("REN: calsave.bas sets REN itself (works after IOLOCAL 7)",
          "Saved and checked" in out and "Unexpected reply" not in out, out)


def test_installer():
    """install.sh / uninstall.sh / the menu: static checks everywhere, the real install test on Linux."""
    root = os.path.dirname(HERE)
    ver = open(os.path.join(root, "VERSION")).read().strip()
    for f in ("install.sh", "uninstall.sh"):
        data = open(os.path.join(root, f), "rb").read()
        check("%s: LF line endings" % f, b"\r" not in data)
    for d in (PI, MODULE):
        for f in os.listdir(d):
            if f.endswith((".sh", ".py")) or f == "COMMANDS":
                rel = os.path.relpath(os.path.join(d, f), os.path.dirname(PI)).replace(os.sep, "/")
                check("%s: LF line endings" % rel, b"\r" not in open(os.path.join(d, f), "rb").read())
    mod = open(os.path.join(MODULE, "module.py"), encoding="utf-8").read()
    check("HP 3478A module: TITLE, KEY, menu() and version", "TITLE =" in mod and "KEY =" in mod
          and "def menu(ui)" in mod and '__version__ = "%s"' % ver in mod)
    core = [f for f in os.listdir(PI) if f.endswith(".py")]
    check("the core has no instrument-specific programs", not [f for f in core if "3478" in f], str(core))
    menu = open(os.path.join(PI, "gpibterm_menu.py"), encoding="utf-8").read()
    ver = open(os.path.join(root, "VERSION")).read().strip()
    check("menu version = VERSION", '__version__ = "%s"' % ver in menu)
    for f in ("install.sh", "uninstall.sh", "pi/setup_pi.sh", "pi/gpib_driver_rebuild.sh", "pi/run.sh"):
        check("%s names version %s" % (f, ver), ("v" + ver) in open(os.path.join(root, f), encoding="utf-8").read())
    readme = open(os.path.join(root, "README.md"), encoding="utf-8").read()
    check("README: install command and menu", "sudo bash install.sh" in readme and "pi-gpibterm" in readme)
    if sys.platform.startswith("linux") and shutil.which("bash"):
        p = subprocess.run(["bash", os.path.join(HERE, "test_install.sh")], capture_output=True, text=True, timeout=600)
        check("install.sh into a scratch area + menu via a pty (test_install.sh)", p.returncode == 0,
              p.stdout[-3000:] + p.stderr[-2000:])
    else:
        print("%-48s %s" % ("install.sh test (Linux only)", "skipped"))


def main():
    print("Python %s" % sys.version.split()[0])
    test_installer()
    test_ren()
    test_ask_missing_comma()
    test_driver_not_loaded()
    test_license_headers()
    for f in (CAL, LOG, os.path.join(PI, "setup_pi.sh")):
        check("LF line endings: " + os.path.basename(f), b"\r\n" not in open(f, "rb").read())

    tmp = tempfile.mkdtemp(prefix="pi-gpibterm-test-")
    old = os.getcwd()
    os.chdir(tmp)
    try:
        blank = os.path.join(tmp, "blank.txt")
        with open(blank, "w", newline="\n") as f:
            f.write(("@" * 16 + "\n") * 16)

        rc, out = run(CAL, ["decode", SAMPLE], fake=False)
        check("decode sample (no gpib module needed)", rc == 0 and "all used entries valid" in out, out)
        rc, out = run(CAL, ["decode", TOM], fake=False)
        check("decode Tom Verbeure's dump: all valid", rc == 0 and "all used entries valid" in out, out)
        rc, out = run(CAL, ["decode", VINAY], fake=False)
        got = [(int(m.group(1)), float(m.group(2)))
               for m in re.finditer(r"^\d+\s+.+?\s(-?\d+)\s+(\d\.\d{6})\s", out, re.M)]
        check("decode Vinay's raw .bin: offsets/gains match his README", got == VINAY_EXPECTED, out)
        for vec in (SAMPLE, TOM):
            n = nibbles(vec)
            ok_tom = tom_checksums(n)
            check("Tom's checksum algorithm agrees: " + os.path.basename(vec), all(ok_tom), str(ok_tom))
        rc, out = run(CAL, ["decode", blank], fake=False)
        check("decode blank RAM reports bad checksums", "INVALID checksum" in out, out)
        rc, out = run(CAL, ["verify", SAMPLE], fake=False)
        check("missing gpib module -> friendly error", rc != 0 and "python3-gpib" in out, out)

        rc, out = run(CAL, ["backup", "b1.txt"], ram=SAMPLE)
        same = rc == 0 and open("b1.txt", "rb").read().replace(b"\n", b"") == \
            open(SAMPLE, "rb").read().replace(b"\n", b"")
        check("backup is byte-identical to meter RAM", same, out)
        check("backup writes .info.txt", os.path.exists("b1.info.txt"), out)
        binok = os.path.exists("b1.bin") and list(open("b1.bin", "rb").read()) == nibbles(SAMPLE)
        check("backup .bin = Tom's format (256 nibbles 0..15)", binok, out)
        rc, out = run(CAL, ["decode", "b1.bin"], fake=False)
        check("decode accepts .bin", rc == 0 and "all used entries valid" in out, out)
        with open("tom.bin", "wb") as f:                 # file as Tom's read script writes it
            f.write(bytes(nibbles(TOM)))
        os.environ["FAKE_STALE"] = "1"
        try:
            rc, out = run(CAL, ["backup", "b_stale.txt"], ram=SAMPLE)
        finally:
            del os.environ["FAKE_STALE"]
        same = rc == 0 and open("b_stale.txt", "rb").read().replace(b"\n", b"") == \
            open(SAMPLE, "rb").read().replace(b"\n", b"")
        check("backup: reading left waiting -> thrown away, RAM saved", same, out)
        rc, out = run(CAL, ["backup", "b1.txt"], ram=SAMPLE)
        check("backup refuses to overwrite", rc != 0 and "already exists" in out, out)

        rc, out = run(CAL, ["verify", "b1.txt"], ram=SAMPLE)
        check("verify: match", rc == 0 and "MATCH" in out, out)
        rc, out = run(CAL, ["verify", "b1.txt"], ram=blank)
        check("verify: difference detected", rc != 0 and "DIFFERENT" in out, out)

        rc, out = run(CAL, ["restore", "-y", "b1.txt"], ram=blank, cal="0")
        check("restore refused with CAL switch disabled", rc != 0 and "ENABLE" in out, out)
        rc, out = run(CAL, ["restore", "-y", blank], ram=SAMPLE)
        check("restore refuses file with bad checksums", rc != 0 and "refusing" in out, out)
        rc, out = run(CAL, ["restore", "b1.txt"], ram=blank, stdin="no\n")
        check("restore cancelled unless YES typed", rc != 0 and "Cancelled" in out, out)
        rc, out = run(CAL, ["restore", "b1.txt"], ram=blank, stdin="YES\n", xlog="x.log")
        check("restore writes and verifies", rc == 0 and "Restore complete and verified" in out, out)
        sent = open("x.log", "rb").read() if os.path.exists("x.log") else b""
        check("X command sends raw nibbles 0..15 (as Tom)", sent and max(sent) <= 0x0F, repr(sent[:20]))
        rc, out = run(CAL, ["restore", "-y", "tom.bin"], ram=blank)
        check("restore from Tom-format .bin", rc == 0 and "verified" in out, out)
        rc, out = run(CAL, ["restore", "-y", VINAY], ram=blank)
        check("restore from Vinay-format raw dump", rc == 0 and "verified" in out, out)
        check("restore saved previous RAM first",
              any(n.startswith("calram_before_restore_") for n in os.listdir(tmp)), out)

        rc, out = run(LOG, ["-n", "3", "-i", "0", "--csv", "log.csv"])
        rows = open("log.csv").read().splitlines() if os.path.exists("log.csv") else []
        check("logger: 3 readings + CSV", rc == 0 and len(rows) == 4 and "1.23456" in out, out)
        env_over = dict(os.environ, FAKE_READING="+9.99999E+9")
        os.environ.update(env_over)
        rc, out = run(LOG, ["-n", "1", "-i", "0"])
        os.environ.pop("FAKE_READING")
        check("logger: over-range shown as OVERLOAD", rc == 0 and "OVERLOAD" in out, out)

        test_library()
        test_terminal(tmp)
    finally:
        os.chdir(old)
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%s" % ("ALL TESTS PASSED" if not FAILS else "%d FAILED: %s" % (len(FAILS), FAILS)))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
