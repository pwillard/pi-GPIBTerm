# SPDX-License-Identifier: GPL-3.0-only
"""dev/test_tty_restore.py - check that install.sh's terminal guard puts the terminal back after a
build tool breaks it (stty -onlcr = the "staircase" screen). Linux/WSL, in a real pseudo-terminal:
    python3 dev/test_tty_restore.py
"""
import os
import pty
import re
import sys

here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "..", "install.sh"), encoding="utf-8").read()
guard = re.search(r"^TTY_SAVED=.*?^trap fix_tty EXIT$", src, re.S | re.M).group(0)
script = guard + "\nstty -onlcr -echo   # what a misbehaving build tool might do\nexit 0\n"
ok = True
pid, fd = pty.fork()
if pid == 0:
    os.execvp("bash", ["bash", "-c", script + "\n"])
os.waitpid(pid, 0)
# the pty's settings after the script ended (the guard ran at exit)
import termios
attrs = termios.tcgetattr(fd)
onlcr = bool(attrs[1] & termios.ONLCR)
echo = bool(attrs[3] & termios.ECHO)
print(("PASS  " if onlcr and echo else "FAIL  ") + "install.sh restores the terminal (CR with LF, echo) after a build tool turns them off")
sys.exit(0 if onlcr and echo else 1)
