#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""pi-gpibterm - the pi-GPIBTerm menu: pick what to run, including the HP-IB Terminal.

Start it with the command  pi-gpibterm  (or ~/pi-gpibterm/menu). Everything it saves goes into
your folder ~/pi-gpibterm: programs/ (your BASIC), backups/ and logs/ (instrument modules).

Instrument modules live in instruments/<name>/module.py next to this file. Each one adds a
section to the menu (the HP 3478A module: readings and calibration RAM backup/restore).

Environment (for testing): PI_GPIBTERM_HOME = the folder to use instead of ~/pi-gpibterm;
PI_GPIBTERM_SIM=1 runs programs and module tools on the simulator.
"""
import datetime
import glob
import importlib.util
import os
import shutil
import subprocess
import sys

__version__ = "2.0.5"
NAME = "pi-GPIBTerm"

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.environ.get("PI_GPIBTERM_HOME") or os.path.expanduser("~/pi-gpibterm")
CONF = os.path.join(WORK, "pi-gpibterm.conf")
DEV = "/dev/gpib0"
SIM = bool(os.environ.get("PI_GPIBTERM_SIM"))


# ------------------------------------------------------------------ helpers (also used by modules)
def ask(prompt, default=""):
    try:
        s = input(prompt + (" [%s]" % default if default else "") + ": ").strip()
    except EOFError:
        raise SystemExit(0)
    return s or default


def pause():
    try:
        input("\nPress Enter to return to the menu ")
    except EOFError:
        raise SystemExit(0)


def get_setting(key, default=""):
    try:
        for line in open(CONF, encoding="utf-8"):
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip()
    except OSError:
        pass
    return default


def set_setting(key, value):
    try:
        lines = open(CONF, encoding="utf-8").read().splitlines()
    except OSError:
        lines = ["# pi-GPIBTerm settings (the menu reads and writes this)"]
    found = False
    for i, line in enumerate(lines):
        if line.partition("=")[0].strip() == key:
            lines[i], found = "%s=%s" % (key, value), True
    if not found:
        lines.append("%s=%s" % (key, value))
    os.makedirs(WORK, exist_ok=True)
    with open(CONF, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def is_root():
    return hasattr(os, "geteuid") and os.geteuid() == 0


def needs_sudo():
    """True when the GPIB board exists but this user may not use it (not in the gpib group
    yet, or not logged in again since being added)."""
    return os.name == "posix" and not is_root() and os.path.exists(DEV) and not os.access(DEV, os.W_OK)


def run(prog, args, cwd=None, board=True, env=None):
    """Run a program from the installation (path relative to this file); returns its exit code."""
    cmd = [sys.executable, os.path.join(HERE, prog)] + list(args)
    if board and needs_sudo() and shutil.which("sudo"):
        cmd = ["sudo"] + cmd
    print()
    try:
        return subprocess.call(cmd, cwd=cwd or WORK, env=env)
    except KeyboardInterrupt:
        return 130


def choose_file(folder, patterns, what, skip=()):
    files = []
    for p in patterns:
        files += glob.glob(os.path.join(folder, p))
    files = sorted((f for f in set(files) if not f.endswith(tuple(skip))), key=os.path.getmtime, reverse=True)
    if not files:
        print("\nNo %s found in %s" % (what, folder))
        return None
    print()
    for i, f in enumerate(files[:20], 1):
        stamp = datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
        print("  %2d  %-44s %s" % (i, os.path.relpath(f, WORK), stamp))
    s = ask("Number (Enter = cancel)")
    if s.isdigit() and 1 <= int(s) <= min(20, len(files)):
        return files[int(s) - 1]
    return None


def sh(cmd):
    """Output of a shell command for the status screen ('' if it fails)."""
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


class UI(object):
    """What an instrument module may use from the menu."""
    ask = staticmethod(ask)
    pause = staticmethod(pause)
    run = staticmethod(run)
    choose_file = staticmethod(choose_file)
    get_setting = staticmethod(get_setting)
    set_setting = staticmethod(set_setting)
    work = WORK
    here = HERE
    sim = SIM


def load_modules():
    """Instrument modules: instruments/<name>/module.py with TITLE, SUMMARY, KEY and menu(ui)."""
    mods = []
    for path in sorted(glob.glob(os.path.join(HERE, "instruments", "*", "module.py"))):
        name = os.path.basename(os.path.dirname(path))
        try:
            spec = importlib.util.spec_from_file_location("pi_gpibterm_module_" + name, path)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            m.FOLDER = os.path.dirname(path)
            m.KEY = str(getattr(m, "KEY", name[:1])).upper()
            mods.append(m)
        except Exception as e:                       # a broken module must not stop the menu
            print("note: instrument module %s could not be loaded: %s" % (name, e))
    return mods


# ------------------------------------------------------------------ menu actions
def terminal(sim=False):
    print("HP-IB Terminal: type HELP for help, BYE to come back to this menu.")
    print("Device addresses are select code 7 + the bus address: 723 = address 23. SCAN finds them.")
    print('Your programs: SAVE "programs/name"   LOAD "programs/name"')
    run("hpibterm.py", ["--sim"] if sim else [], board=not sim)


def program_list():
    mine = sorted(glob.glob(os.path.join(WORK, "programs", "*.bas")))
    dirs = [os.path.join(HERE, "examples")] + sorted(glob.glob(os.path.join(HERE, "instruments", "*", "examples")))
    examples = [f for d in dirs for f in sorted(glob.glob(os.path.join(d, "*.bas")))]
    return mine, examples


def program(sim=False):
    mine, examples = program_list()
    progs = mine + examples
    if not progs:
        print("\nNo programs found.")
        pause()
        return
    print()
    for i, p in enumerate(progs, 1):
        if p in mine:
            where = "programs"
        else:
            parts = os.path.relpath(p, HERE).replace("\\", "/").split("/")
            where = parts[1] if parts[0] == "instruments" else "examples"
        first = ""
        try:
            for line in open(p, encoding="utf-8", errors="replace"):
                if "REM" in line and "SPDX" not in line and "not covered" not in line:
                    first = line.split("REM", 1)[1].strip()
                    break
        except OSError:
            pass
        print("  %2d  %-9s %-20s %s" % (i, where, os.path.basename(p)[:-4], first[:44]))
    s = ask("Number (Enter = cancel)")
    if s.isdigit() and 1 <= int(s) <= len(progs):
        run("hpibterm.py", [progs[int(s) - 1], "--run"] + (["--sim"] if sim else []), board=not sim)
        pause()


def scan(sim=False):
    print("\nLooking for instruments on the bus (select code 7)...")
    run("hpibterm.py", ["-c", "SCAN"] + (["--sim"] if sim else []), board=not sim)
    pause()


def status():
    print("\n%s %s" % (NAME, __version__))
    inst = os.path.join(HERE, "INSTALLED")
    if os.path.exists(inst):
        print("Installed:     " + open(inst, encoding="utf-8").read().strip())
    print("Pi:            " + (sh("tr -d '\\0' < /proc/device-tree/model") or "?"))
    print("System:        %s, kernel %s" % (sh(". /etc/os-release && echo $PRETTY_NAME") or "?", sh("uname -r") or "?"))
    print("Driver built:  " + ("yes" if sh("modinfo gpib_bitbang >/dev/null 2>&1 && echo y") else
                               "NO - choose 'Rebuild the GPIB driver'"))
    print("gpib.service:  " + (sh("systemctl is-active gpib.service") or "?"))
    if os.path.exists(DEV):
        print("%s:   present, %s" % (DEV, "you can use it" if os.access(DEV, os.W_OK) or is_root()
                                     else "needs sudo (log out and in again after installing)"))
    else:
        print("%s:   MISSING - the driver is not loaded" % DEV)
    mods = load_modules()
    print("Modules:       " + (", ".join(m.TITLE for m in mods) or "none"))
    print("Your folder:   " + WORK)
    if os.path.exists(DEV):
        print("\nLooking for instruments on the bus...")
        run("hpibterm.py", ["-c", "SCAN"])
    pause()


def rebuild():
    print("\nRebuild the GPIB driver for the running kernel (needed after a kernel update;")
    print("the Pi also does this by itself at the next boot). Takes a few minutes on a Pi Zero.")
    if ask("Rebuild now? (y/n)", "n").lower().startswith("y"):
        tool = os.path.join(HERE, "gpib_driver_rebuild.sh")
        cmd = ["bash", tool] if is_root() else ["sudo", "bash", tool]
        if subprocess.call(cmd + ["--force"]) == 0:
            subprocess.call(["sudo", "systemctl", "restart", "gpib.service"])
    pause()


def docs():
    d = os.path.join(HERE, "docs")
    print("\nThe guides are PDF files in %s:" % d)
    for f in sorted(glob.glob(os.path.join(d, "*.pdf"))):
        print("  " + os.path.basename(f))
    print("""
To read them on your PC, copy them over, e.g. in PowerShell on the PC:
    scp "%s@<this Pi>:%s/*.pdf" .
Inside the HP-IB Terminal, HELP explains every command (HELP LIBRARY, HELP BASIC ...).""" % (
        os.environ.get("USER", "you"), d))
    pause()


def show_menu(mods):
    print("""
 %s %s  -  HP-IB / GPIB on a Raspberry Pi
 ------------------------------------------------------------------------------
  1  HP-IB Terminal                (HP-IB programming environment, HELP inside)
  2  HP-IB Terminal - simulator    (practise without an instrument)
  3  Run a BASIC program           (your programs and the examples)
  4  Find instruments on the bus   (SCAN)
""" % (NAME, __version__))
    if mods:
        print("  Instrument modules:")
        for m in mods:
            print("  %s  %-29s (%s)" % (m.KEY, m.TITLE, m.SUMMARY))
        print()
    print("""  9  Check the installation        (driver, /dev/gpib0, instruments on the bus)
  R  Rebuild the GPIB driver       (after a kernel update)
  D  Where are the guides (PDF)?
  Q  Quit
""")


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "--version":
        print("pi-gpibterm menu " + __version__)
        return 0
    for sub in ("programs", "backups", "logs"):
        os.makedirs(os.path.join(WORK, sub), exist_ok=True)
    mods = load_modules()
    by_key = {m.KEY: m for m in mods}
    while True:
        show_menu(mods)
        c = ask("Choose").upper()
        try:
            if c == "1":
                terminal()
            elif c == "2":
                terminal(sim=True)
            elif c == "3":
                program(sim=SIM)
            elif c == "4":
                scan(sim=SIM)
            elif c in by_key:
                by_key[c].menu(UI)
            elif c == "9":
                status()
            elif c == "R":
                rebuild()
            elif c == "D":
                docs()
            elif c in ("Q", "0", "X", "EXIT", "BYE"):
                return 0
        except KeyboardInterrupt:
            print("\n(stopped)")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(0)
