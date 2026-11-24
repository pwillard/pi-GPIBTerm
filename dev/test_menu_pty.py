# SPDX-License-Identifier: GPL-3.0-only
"""dev/test_menu_pty.py - drive the installed pi-GPIBTerm menu through a real pseudo-terminal,
as a person at the keyboard would (Linux/WSL only).

    python3 dev/test_menu_pty.py <menu command> <work folder>
"""
import os
import pty
import select
import sys
import time

menu, work = sys.argv[1], sys.argv[2]
env = dict(os.environ, PI_GPIBTERM_HOME=work, PI_GPIBTERM_SIM="1", TERM="dumb")
pid, fd = pty.fork()
if pid == 0:
    os.execvpe(menu, [menu], env)

buf = b""


def expect(text, timeout=20):
    global buf
    end = time.time() + timeout
    while text.encode() not in buf:
        r, _, _ = select.select([fd], [], [], max(0, end - time.time()))
        if not r:
            raise SystemExit("TIMEOUT waiting for %r; got:\n%s" % (text, buf.decode(errors="replace")[-1500:]))
        try:
            buf += os.read(fd, 4096)
        except OSError:
            break
    i = buf.index(text.encode()) + len(text)
    seen, buf = buf[:i], buf[i:]
    return seen.decode(errors="replace")


def send(line):
    os.write(fd, line.encode() + b"\r")


results = []


def check(name, cond):
    results.append(cond)
    print(("PASS  " if cond else "FAIL  ") + name)


out = expect("Choose")
check("menu: generic core items", "1  HP-IB Terminal" in out and "4  Find instruments on the bus" in out)
check("menu: the HP 3478A module is listed under Instrument modules",
      "Instrument modules:" in out and "H  HP 3478A multimeter" in out)
check("menu: no 3478A items in the core", "calibration RAM" not in out.split("Instrument modules:")[0])
send("2")                                   # terminal on the simulator
check("2 starts the HP-IB Terminal on the simulator", "SIMULATOR" in expect("HP-IB>"))
send("SCAN")
check("the terminal answers inside the menu", "Listeners found: 23" in expect("HP-IB>"))
send("BYE")
expect("Choose")
send("4")
check("4 scans the bus", "Listeners found: 23" in expect("Press Enter"))
send("")
expect("Choose")
send("3")                                   # run a BASIC program
out = expect("Number")
check("3 lists core and module examples", "bus_tour" in out and "hp3478a   3478a_read" in out)
line = [l for l in out.splitlines() if "3478a_read" in l][0]
send(line.split()[0])
out = expect("Press Enter")
check("3 runs the chosen program (simulator)", " V" in out and "Loaded" in out)
send("")
expect("Choose")
send("H")                                   # the HP 3478A module
out = expect("Choose")
check("H opens the HP 3478A module", "meter at address 22 (device 722)" in out and "2  Back up the calibration RAM" in out)
send("A")
expect("1-30)")
send("21")
check("module A changes the meter address", "meter at address 21 (device 721)" in expect("Choose"))
send("4")                                   # show a backup (no meter needed)
check("module 4 lists the backups", "calram_test.txt" in expect("Number"))
send("1")
check("module 4 decodes the chosen backup", "all used entries valid" in expect("Press Enter"))
send("")
expect("Choose")
send("B")
check("B returns to the main menu", "Instrument modules:" in expect("Choose"))
send("Q")
time.sleep(0.5)
_, status = os.waitpid(pid, 0)
check("Q leaves the menu", os.WEXITSTATUS(status) == 0)
with open(os.path.join(work, "pi-gpibterm.conf")) as f:
    check("the module's address is saved", "HP3478A_ADDRESS=21" in f.read())
sys.exit(0 if all(results) else 1)
