#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""HP-IB Terminal: an HP-IB programming environment for linux-gpib (e.g. the gpib4pi).

It works like the HP 82990A HP-IB Command Library with interpreted BASIC: type
library commands directly, or write line-numbered programs, LIST/RUN/SAVE them.

Installed (install.sh), it is the command  hpib  - also on the menu  pi-gpibterm :
    hpib                                  # interactive, select code 7 = board 0
    hpib --sim                            # practise: a simulated bus, an HP 3478A at 723
    hpib examples/bus_tour.bas --run      # run a program and exit
    hpib -c 'ASK 723, "H1"'               # one-off command
From the source folder: python3 hpibterm.py ... (with sudo if not in the 'gpib' group).

Inside: HELP, HELP LIBRARY, HELP IOENTERS, HELP EXAMPLES ...
"""
import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import hpibbasic  # noqa: E402
import hpibhelp  # noqa: E402
import hpiblib  # noqa: E402
from hpibbasic import BasicError  # noqa: E402

__version__ = "2.0.7"
PROMPT = "HP-IB> "
COMMANDS = {"RUN", "LIST", "NEW", "CONT", "EDIT", "DELETE", "RENUM", "AUTO", "LOAD", "SAVE",
            "MERGE", "FILES", "TRACE", "VARS", "CLEAR", "HELP", "BYE", "QUIT", "EXIT", "SYSTEM"}

try:
    import readline
except ImportError:          # Windows Python has no readline; history/completion just go away
    readline = None


def load_gpib(sim):
    if sim:
        import hpib_sim
        return hpib_sim
    try:
        import gpib
        return gpib
    except ImportError:
        sys.exit("The linux-gpib Python module 'gpib' is not installed.\n"
                 "On the Pi run setup_pi.sh first (it builds linux-gpib and python3-gpib),\n"
                 "or start with --sim to practise with a simulated HP 3478A.")


def example_dirs():
    """The example folders: the core's, then each instrument module's (instruments/*/examples)."""
    return [os.path.join(HERE, "examples")] + sorted(glob.glob(os.path.join(HERE, "instruments", "*", "examples")))


def program_path(name, must_exist=False):
    name = name.strip().strip('"').strip()
    if not name:
        raise BasicError(64, "Bad file name: give a file name in quotes")
    name = os.path.expanduser(name)
    if not os.path.splitext(name)[1]:
        name += ".bas"
    if must_exist and not os.path.exists(name):
        alt = os.path.join(HERE, name)
        if os.path.exists(alt):
            return alt
        rel = name.replace("\\", "/")
        if rel.lower().startswith("examples/"):
            # "examples/x" also finds the examples of the instrument modules
            for d in example_dirs():
                alt = os.path.join(d, rel[len("examples/"):])
                if os.path.exists(alt):
                    return alt
        raise BasicError(53, "File not found: %s" % name)
    return name


def renumber(program, start=10, step=10):
    """New line numbers plus fixed-up GOTO/GOSUB/THEN/ELSE/RESUME/RESTORE references."""
    old = sorted(program)
    mapping = {n: start + i * step for i, n in enumerate(old)}
    if old and mapping[old[-1]] > 65529:
        raise BasicError(5, "Illegal function call: line numbers would pass 65529")
    ref = re.compile(r"\b(GOTO|GOSUB|THEN|ELSE|RESUME|RESTORE)(\s*)(\d+(?:\s*,\s*\d+)*)", re.I)

    def fix_refs(m):
        nums = re.sub(r"\d+", lambda d: str(mapping.get(int(d.group(0)), int(d.group(0)))), m.group(3))
        return m.group(1) + m.group(2) + nums

    new = {}
    for n in old:
        parts = re.split(r'("[^"]*"?)', program[n])
        out = []
        for i, p in enumerate(parts):
            if i % 2 == 0:
                cut = re.search(r"'|\bREM\b", p, re.I)
                head, tail = (p[:cut.start()], p[cut.start():]) if cut else (p, "")
                out.append(ref.sub(fix_refs, head) + tail)
                if cut:
                    out.extend(parts[i + 1:])
                    break
            else:
                out.append(p)
        new[mapping[n]] = "".join(out)
    return new


class Terminal(object):
    def __init__(self, lib, interp, sim=False):
        self.lib = lib
        self.bi = interp
        self.sim = sim
        self.auto = None
        self.edit_text = None
        self.history = os.path.expanduser("~/.hpibterm_history")
        self.prompting = False      # VMS-style Topic? prompts: only when typing at the REPL

    def say(self, text):
        sys.stdout.write(text + "\n")
        sys.stdout.flush()

    def set_trace(self, on):
        self.lib.trace = (lambda t: self.say("    [bus] " + t)) if on else None

    # ------------------------------------------------ readline
    def setup_readline(self):
        if not readline:
            return
        try:
            readline.read_history_file(self.history)
        except (IOError, OSError):
            pass
        words = sorted(set(hpibbasic.KEYWORDS) | set(hpibbasic.LIBRARY) | set(hpibbasic.FUNCS)
                       | COMMANDS | set(hpibhelp.TOPICS) - {""} | {"LIBRARY"})

        def complete(text, state):
            up = text.upper()
            pool = words + sorted(self.bi.vars)
            hits = [w for w in pool if w.startswith(up)]
            return hits[state] if state < len(hits) else None

        readline.set_completer_delims(" \t:,;()=+-*/<>")
        readline.set_completer(complete)
        readline.parse_and_bind("tab: complete")

    def save_history(self):
        if readline:
            try:
                readline.set_history_length(1000)
                readline.write_history_file(self.history)
            except (IOError, OSError):
                pass

    def read_line(self):
        if self.edit_text is not None and readline:
            text = self.edit_text
            readline.set_startup_hook(lambda: readline.insert_text(text))
        try:
            prompt = PROMPT if self.auto is None else "%d " % self.auto[0]
            line = input(prompt)
        finally:
            if readline:
                readline.set_startup_hook()
            self.edit_text = None
        if self.auto is not None:
            if not line.strip():
                self.auto = None
                return ""
            line = "%d %s" % (self.auto[0], line)
            self.auto = (self.auto[0] + self.auto[1], self.auto[1])
        return line

    # ------------------------------------------------ main loop
    def banner(self):
        sc = sorted(self.lib.ifaces)
        where = ", ".join("select code %d = board %d" % (s, self.lib.ifaces[s].board) for s in sc)
        self.say("HP-IB Terminal %s - HP 82990A HP-IB Command Library work-alike on linux-gpib" % __version__)
        self.say(where + ("   [SIMULATOR: HP 3478A at address 723]" if self.sim else ""))
        self.say('Type HELP for help, HELP LIBRARY for the commands, BYE to leave.')
        problem = None if self.sim else self.lib.driver_problem()
        if problem:
            self.say("")
            self.say("WARNING: " + problem)
            self.say("Bus commands will fail until that is fixed. To try things without the Pi's")
            self.say("GPIB board, start the terminal with --sim (simulated HP 3478A at 723).")
            self.say("")

    def repl(self):
        self.setup_readline()
        self.prompting = sys.stdin.isatty()
        self.banner()
        while True:
            try:
                line = self.read_line()
            except EOFError:
                self.say("")
                break
            except KeyboardInterrupt:
                self.say("^C")
                self.auto = None
                continue
            try:
                if self.do_line(line) == "quit":
                    break
            except KeyboardInterrupt:
                self.say("Break")
        self.save_history()

    def do_line(self, line):
        """Process one line typed by the user (or given with -c). Returns 'quit' to leave."""
        text = line.strip()
        if not text:
            return None
        try:
            m = re.match(r"(\d+)\s?(.*)$", text)
            if m:
                try:
                    self.bi.store_line(int(m.group(1)), m.group(2))
                except BasicError as e:
                    if e.code == 8:
                        raise
                    self.say("%s (line %s kept - EDIT %s to fix)" % (e.msg, m.group(1), m.group(1)))
                return None
            word = re.match(r"[A-Za-z]+", text)
            word = word.group(0).upper() if word else ""
            if word in COMMANDS and not re.match(r"[A-Za-z]+\s*=", text):
                return self.command(word, text[len(word):].strip())
            self.bi.immediate(text)
        except BasicError as e:
            self.bi.failed = True
            self.say(e.msg)
        return None

    def _range(self, arg):
        arg = arg.strip()
        if not arg:
            return None, None
        m = re.match(r"^(\d*)\s*(-?)\s*(\d*)$", arg)
        if not m:
            raise BasicError(2)
        lo = int(m.group(1)) if m.group(1) else None
        hi = int(m.group(3)) if m.group(3) else (lo if not m.group(2) else None)
        return lo, hi

    def command(self, word, arg):
        bi = self.bi
        if word in ("BYE", "QUIT", "EXIT", "SYSTEM"):
            return "quit"
        if word == "HELP":
            noprompt = False
            m = re.match(r"(?i)^/NOPROMPT\b\s*", arg)
            if m:
                noprompt, arg = True, arg[m.end():]
            if self.prompting and not noprompt:
                hpibhelp.Session(input, self.say).run(arg.replace('"', " ").split())
            else:
                self.say(hpibhelp.help_text(arg))
        elif word == "RUN":
            if arg.startswith('"') or (arg and not arg[0].isdigit()):
                self.load(arg)
                arg = ""
            bi.run(int(arg) if arg else None)
        elif word == "CONT":
            bi.cont()
        elif word == "LIST":
            lo, hi = self._range(arg)
            for ln in bi.list_lines(lo, hi):
                self.say(ln)
        elif word == "NEW":
            bi.program = {}
            bi.clear()
            bi.cont_pc = None
        elif word == "CLEAR":
            bi.clear()
        elif word == "DELETE":
            lo, hi = self._range(arg)
            if lo is None and hi is None:
                raise BasicError(5, "Illegal function call: DELETE line or DELETE from-to")
            gone = [n for n in list(bi.program) if (lo is None or n >= lo) and (hi is None or n <= hi)]
            if not gone:
                raise BasicError(8)
            for n in gone:
                del bi.program[n]
            bi.cont_pc = None
        elif word == "EDIT":
            n = int(arg) if arg.isdigit() else None
            if n not in bi.program:
                raise BasicError(8)
            if readline:
                self.edit_text = "%d %s" % (n, bi.program[n])
            else:
                self.say("%d %s" % (n, bi.program[n]))
                self.say("(no line editor here - type the line again to replace it)")
        elif word == "RENUM":
            nums = [int(x) for x in re.findall(r"\d+", arg)] or [10]
            bi.program = renumber(bi.program, nums[0], nums[1] if len(nums) > 1 else 10)
            bi.cont_pc = None
        elif word == "AUTO":
            nums = [int(x) for x in re.findall(r"\d+", arg)]
            start = nums[0] if nums else ((max(bi.program) + 10) // 10 * 10 if bi.program else 10)
            self.auto = (start, nums[1] if len(nums) > 1 else 10)
            self.say("AUTO: press Enter on an empty line to stop")
        elif word in ("LOAD", "MERGE"):
            self.load(arg, merge=word == "MERGE")
        elif word == "SAVE":
            path = program_path(arg)
            with open(path, "w", encoding="latin-1", newline="\n") as f:
                f.write(bi.program_text())
            self.say("Saved %d line(s) to %s" % (len(bi.program), path))
        elif word == "FILES":
            pat = os.path.expanduser(arg.strip('"') or "*.bas")
            if os.path.isdir(pat):
                pat = os.path.join(pat, "*.bas")
            names = sorted(glob.glob(pat))
            rel = pat.replace("\\", "/")
            if rel.lower().startswith("examples"):
                # FILES examples: the installed examples, core and instrument modules
                tail = rel[len("examples"):].lstrip("/") or "*.bas"
                names = sorted(set("examples/" + os.path.basename(f) for d in example_dirs()
                                   for f in glob.glob(os.path.join(d, tail))) |
                               set(n.replace("\\", "/") for n in names))
            self.say("  ".join(names) if names else "No files match %s" % pat)
        elif word == "TRACE":
            on = arg.upper() != "OFF"
            self.set_trace(on)
            self.say("Bus trace %s" % ("ON" if on else "OFF"))
        elif word == "VARS":
            self.show_vars()
        return None

    def load(self, arg, merge=False):
        path = program_path(arg, must_exist=True)
        with open(path, encoding="latin-1") as f:
            bad = self.bi.load_text(f.read(), merge=merge)
        self.bi.clear()
        self.say("%s %s (%d lines)" % ("Merged" if merge else "Loaded", path, len(self.bi.program)))
        for n, msg in bad:
            self.say("  line %d: %s" % (n, msg))

    def show_vars(self):
        skip = set(m for m, _ in hpiblib.ERRORS.values()) | {"TRUE", "FALSE", "PCIB.BASERR"}
        for name in sorted(self.bi.vars):
            if name in skip:
                continue
            v = self.bi.vars[name]
            self.say("  %-16s %s" % (name, hpiblib.show(v) if isinstance(v, str) else hpibbasic.fmt_num(v).strip()))
        for name in sorted(self.bi.arrays):
            a = self.bi.arrays[name]
            self.say("  %-16s array (%s)" % (name + "()", ", ".join(str(d) for d in a["dims"])))

    def finish(self):
        """Leave every instrument in local (front panel) control."""
        for sc in self.lib.ifaces:
            try:
                self.lib.iolocal(sc)
            except Exception:
                pass
        self.bi.close_files()
        self.lib.close()


def parse_isc(values):
    out = {}
    for v in values or ["7=0"]:
        m = re.match(r"^(\d+)=(\d+)$", v)
        if not m or not 1 <= int(m.group(1)) <= 99:
            sys.exit("--isc must look like 7=0 (select code 1-99 = linux-gpib board index)")
        out[int(m.group(1))] = int(m.group(2))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(
        description="HP-IB Terminal v%s - HP-IB programming environment (HP 82990A command library "
                    "work-alike) for linux-gpib" % __version__)
    p.add_argument("program", nargs="?", help="BASIC program to load (.bas)")
    p.add_argument("--run", action="store_true", help="run the program, then exit")
    p.add_argument("-c", dest="commands", action="append", default=[],
                   help="run these statements/commands (repeatable), then exit")
    p.add_argument("-i", "--interactive", action="store_true",
                   help="stay in the terminal after --run / -c")
    p.add_argument("--sim", action="store_true", help="use the built-in simulator (HP 3478A at 723)")
    p.add_argument("--isc", action="append", metavar="SC=BOARD",
                   help="select code to board mapping (default 7=0); repeat for more boards")
    p.add_argument("--timeout", type=float, default=10.0,
                   help="start-up IOTIMEOUT in seconds (default 10; 0 = off as on the 82990A)")
    p.add_argument("--trace", action="store_true", help="start with TRACE ON (show bus activity)")
    p.add_argument("--version", action="version", version="hpibterm " + __version__)
    args = p.parse_args(argv)

    gpib = load_gpib(args.sim)
    lib = hpiblib.Library(gpib, parse_isc(args.isc), timeout=args.timeout)
    bi = hpibbasic.Interpreter(lib)
    bi.failed = False
    term = Terminal(lib, bi, sim=args.sim)
    term.set_trace(args.trace)
    batch = args.run or bool(args.commands)
    try:
        if args.program:
            try:
                term.load(args.program)
            except BasicError as e:
                term.say(e.msg)
                return 1
        if args.run:
            if not args.program:
                term.say("--run needs a program file")
                return 2
            try:
                bi.run()
            except BasicError as e:
                bi.failed = True
                term.say(e.msg)
        for c in args.commands:
            if term.do_line(c) == "quit":
                break
        if not batch or args.interactive:
            term.repl()
    except KeyboardInterrupt:
        term.say("Break")
    finally:
        term.finish()
    return 1 if (batch and not args.interactive and bi.failed) else 0


if __name__ == "__main__":
    sys.exit(main())
