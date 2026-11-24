#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""HP 3478A reader/logger for the Lightside gpib4pi (linux-gpib) on a Raspberry Pi.

Part of pi-GPIBTerm's HP 3478A instrument module; installed as the command hp3478a-log
(also in the menu: pi-gpibterm, then H). Examples:
    hp3478a-log                      # 10 DC volt readings, address 23
    hp3478a-log -f ohm2 -n 0 -i 1    # 2-wire ohms, every 1 s, until Ctrl+C
    hp3478a-log -f dcv -r 1 --csv log.csv -n 100

The 3478A is pre-SCPI: it does NOT understand *IDN? or MEAS:... commands.
It uses short codes (F=function, R=range, N=digits, Z=autozero, T=trigger, D=display).
"""
import argparse
import csv
import datetime
import sys
import time

import gpib

# Function codes (F1..F7)
FUNCS = {
    "dcv": ("F1", "V DC"),
    "acv": ("F2", "V AC"),
    "ohm2": ("F3", "Ohm 2-wire"),
    "ohm4": ("F4", "Ohm 4-wire"),
    "dca": ("F5", "A DC"),
    "aca": ("F6", "A AC"),
    "ohmx": ("F7", "Ohm extended"),
}

__version__ = "2.0.7"
OVERLOAD = 9.0e9  # 3478A sends +9.99999E+9 when over range


def send(dev, cmd):
    gpib.write(dev, cmd + "\r\n")


def read_value(dev):
    raw = gpib.read(dev, 64).decode("ascii", "replace").strip()
    return raw, float(raw)


def main():
    p = argparse.ArgumentParser(description="HP 3478A reader/logger (linux-gpib) v%s" % __version__)
    p.add_argument("-a", "--addr", type=int, default=23, help="GPIB address (default 23)")
    p.add_argument("-b", "--board", type=int, default=0, help="linux-gpib board index (default 0)")
    p.add_argument("-f", "--func", choices=FUNCS, default="dcv", help="measurement function")
    p.add_argument("-r", "--range", default="A",
                   help="range code: A=auto, or -2..7 (e.g. DCV: -2=30mV, -1=300mV, 0=3V, 1=30V, 2=300V)")
    p.add_argument("-d", "--digits", type=int, choices=(3, 4, 5), default=5,
                   help="3, 4 or 5 = 3.5/4.5/5.5 digits (default 5)")
    p.add_argument("-n", "--count", type=int, default=10, help="number of readings, 0 = until Ctrl+C")
    p.add_argument("-i", "--interval", type=float, default=0.5, help="seconds between readings")
    p.add_argument("--csv", help="also append readings to this CSV file")
    args = p.parse_args()

    fcode, unit = FUNCS[args.func]
    rcode = "RA" if str(args.range).upper() == "A" else "R%d" % int(args.range)

    try:
        dev = gpib.dev(args.board, args.addr)
        gpib.remote_enable(args.board, 1)   # REN on: in local the meter ignores every command
        gpib.timeout(dev, gpib.T10s)    # 5.5 digit readings can take ~0.5 s each
        gpib.clear(dev)                 # selected device clear
    except gpib.GpibError as e:
        sys.exit("Could not open GPIB device %d on board %d: %s" % (args.addr, args.board, e))

    try:
        # Which input terminals are active? 'S' returns 1 = front, 0 = rear.
        send(dev, "S")
        side = "front" if gpib.read(dev, 8).decode().strip() == "1" else "rear"
        print("HP 3478A at address %d, %s terminals selected" % (args.addr, side))

        send(dev, "D2PI GPIB")          # show a message on the meter's display
        time.sleep(1)
        send(dev, "D1")                 # back to normal display
        # function, range, autozero on, digits, trigger hold (we trigger each reading)
        send(dev, "%s%sZ1N%dT4" % (fcode, rcode, args.digits))
    except gpib.GpibError as e:
        sys.exit("Meter did not respond (check address, cable, power): %s" % e)

    writer = None
    fh = None
    if args.csv:
        fh = open(args.csv, "a", newline="")
        writer = csv.writer(fh)
        if fh.tell() == 0:
            writer.writerow(["timestamp", "function", "value", "raw"])

    n = 0
    try:
        while args.count == 0 or n < args.count:
            send(dev, "T3")             # single trigger, then read the result
            raw, val = read_value(dev)
            ts = datetime.datetime.now().isoformat(timespec="milliseconds")
            shown = "OVERLOAD" if abs(val) >= OVERLOAD else "%.6g %s" % (val, unit)
            print("%s  %s" % (ts, shown))
            if writer:
                writer.writerow([ts, args.func, "" if abs(val) >= OVERLOAD else val, raw])
                fh.flush()
            n += 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    except gpib.GpibError as e:
        print("GPIB error: %s" % e, file=sys.stderr)
    finally:
        try:
            send(dev, "T1")             # leave meter free-running
            gpib.ibloc(dev)             # return to front-panel (LOCAL) control
        except Exception:
            pass
        if fh:
            fh.close()
    print("%d reading(s) taken" % n)


if __name__ == "__main__":
    main()
