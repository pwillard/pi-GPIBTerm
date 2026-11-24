# SPDX-License-Identifier: GPL-3.0-only
"""pi-GPIBTerm instrument module: HP 3478A multimeter.

Adds a section to the pi-GPIBTerm menu (key H) with readings and the calibration RAM backup,
verify, show and restore. The programs it runs are in this folder:
    hp3478a_log.py   readings / CSV logging        (command: hp3478a-log)
    hp3478a_cal.py   calibration RAM tool          (command: hp3478a-cal)
    examples/*.bas   HP-IB Terminal programs for the 3478A (LOAD "examples/3478a_read" finds them)

A module is a folder in instruments/ with a module.py that defines TITLE, SUMMARY, KEY and
menu(ui); see pi/gpibterm_menu.py for what ui offers.
"""
import datetime
import os

__version__ = "2.0.6"
TITLE = "HP 3478A multimeter"
SUMMARY = "readings, calibration RAM backup/restore"
KEY = "H"

FUNCTIONS = [("dcv", "DC volts"), ("acv", "AC volts"), ("ohm2", "ohms, 2-wire"),
             ("ohm4", "ohms, 4-wire"), ("dca", "DC amps"), ("aca", "AC amps"),
             ("ohmx", "ohms, extended range")]
CAL = "instruments/hp3478a/hp3478a_cal.py"
LOG = "instruments/hp3478a/hp3478a_log.py"
BACKUP_PATTERNS = ["calram_*.txt", "calram_*.bin"]


def address(ui):
    a = ui.get_setting("HP3478A_ADDRESS", "23")
    return int(a) if a.isdigit() and 1 <= int(a) <= 30 else 23


def readings(ui, addr):
    print("\nTake readings and save them to logs/ as a CSV file (Ctrl+C stops).")
    for i, (code, name) in enumerate(FUNCTIONS, 1):
        print("  %d  %s" % (i, name))
    s = ui.ask("Function", "1")
    if not (s.isdigit() and 1 <= int(s) <= len(FUNCTIONS)):
        return
    func = FUNCTIONS[int(s) - 1][0]
    n = ui.ask("How many readings (0 = until Ctrl+C)", "10")
    every = ui.ask("Seconds between readings", "1")
    os.makedirs(os.path.join(ui.work, "logs"), exist_ok=True)
    csv = os.path.join("logs", "3478a_%s_%s.csv" % (func, datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    rc = ui.run(LOG, ["-a", str(addr), "-f", func, "-n", n, "-i", every, "--csv", csv])
    if rc == 0 and os.path.exists(os.path.join(ui.work, csv)):
        print("\nSaved: ~/pi-gpibterm/%s" % csv)
    ui.pause()


def backups(ui):
    return os.path.join(ui.work, "backups")


def cal_backup(ui, addr):
    print("\nBack up the meter's calibration RAM. This only READS the meter;")
    print("leave the front-panel CAL ENABLE switch OFF.")
    if ui.ask("Start the backup? (y/n)", "y").lower().startswith("y"):
        os.makedirs(backups(ui), exist_ok=True)
        ui.run(CAL, ["-a", str(addr), "backup"], cwd=backups(ui))
        print("\nCopy the new files in ~/pi-gpibterm/backups somewhere safe - not only on this Pi.")
    ui.pause()


def pick(ui):
    return ui.choose_file(backups(ui), BACKUP_PATTERNS, "backups", skip=(".info.txt",))


def cal_verify(ui, addr):
    f = pick(ui)
    if f:
        ui.run(CAL, ["-a", str(addr), "verify", f], cwd=backups(ui))
    ui.pause()


def cal_decode(ui):
    f = pick(ui)
    if f:
        ui.run(CAL, ["decode", f], board=False)
    ui.pause()


def cal_restore(ui, addr):
    print("""
RESTORE writes a backup into the meter's calibration RAM. Only do this after a battery
change has lost the calibration, or on advice. It needs the CAL ENABLE switch ON. The
meter's present contents are backed up first, and you must type YES before anything is
written.""")
    f = pick(ui)
    if f:
        ui.run(CAL, ["-a", str(addr), "restore", f], cwd=backups(ui))
    ui.pause()


def set_address(ui, addr):
    print("\nThe HP 3478A's GPIB address is set by the switches on its back (factory: 23).")
    s = ui.ask("Meter's GPIB address (1-30)", str(addr))
    if s.isdigit() and 1 <= int(s) <= 30:
        ui.set_setting("HP3478A_ADDRESS", s)
    else:
        print("Not changed.")


def menu(ui):
    while True:
        addr = address(ui)
        print("""
 HP 3478A multimeter              meter at address %d (device %d)
 ------------------------------------------------------------------------------
  1  Take readings                 (saved as CSV in logs/)
  2  Back up the calibration RAM   (read only - do this first!)
  3  Verify the meter against a backup
  4  Show what is in a backup      (no meter needed)
  5  Restore calibration RAM       (CAL ENABLE switch ON - careful)
  A  Change the meter's address
  B  Back to the main menu

  HP-IB Terminal programs for the 3478A: main menu 3 (3478a_read, 3478a_calsave ...)
""" % (addr, 700 + addr))
        c = ui.ask("Choose").upper()
        if c == "1":
            readings(ui, addr)
        elif c == "2":
            cal_backup(ui, addr)
        elif c == "3":
            cal_verify(ui, addr)
        elif c == "4":
            cal_decode(ui)
        elif c == "5":
            cal_restore(ui, addr)
        elif c == "A":
            set_address(ui, addr)
        elif c in ("B", "Q", "", "0"):
            return
