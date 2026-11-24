#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""HP 3478A calibration RAM backup / verify / restore tool (linux-gpib, e.g. Lightside gpib4pi).

The 3478A keeps its calibration constants in battery-backed RAM. If the battery
dies or is removed with the meter off, the calibration is lost. This tool lets you
save the RAM to a file and write it back later.

Usage (run on the Pi, as root):
Part of pi-GPIBTerm's HP 3478A instrument module; installed as the command hp3478a-cal
(also in the menu: pi-gpibterm, then H):
    hp3478a-cal backup                    # save calram_<date>.txt/.bin/.info.txt
    hp3478a-cal verify  calram_XXXX.txt   # compare meter RAM with a backup
    hp3478a-cal restore calram_XXXX.txt   # write a backup back (CAL switch ENABLE)
    hp3478a-cal decode  calram_XXXX.txt   # show what is in a file (no meter needed)

Options: -a/--addr GPIB address (default 23), -b/--board board index (default 0).

How it works (undocumented 3478A commands; cross-checked against Tom Verbeure's
hp3478a_calibration scripts, pymeasure's HP3478A driver, pyAsyncHP3478A and
vinayshanbhag/hp3478a):
  The cal memory is a 256 x 4-bit SRAM (U512), battery BT701.
  "W" + <raw address byte>              -> meter returns 1 character, 64 + nibble ('@'..'O')
  "X" + <raw address byte> + <nibble>   -> writes the low 4 bits (only with CAL ENABLE switch on;
                                           the switch hard-wires the SRAM to read-only otherwise)
  "B"                                   -> 5 status bytes; byte 2 bit 5 = CAL RAM write enabled
Address 0 is a read/write check nibble the meter uses to test write protection (not cal data).
Addresses 1..247 hold 19 entries of 13 nibbles: 6 offset + 5 gain + 2 checksum, where
sum(11 data nibbles) + (16*hi + lo) must equal 255. Entries 5, 16, 18 are unused.
Addresses 248..255 are don't-care.

Files written by backup:
  calram_<date>.txt       16 lines x 16 chars '@'..'O' (same as pyAsyncHP3478A)
  calram_<date>.bin       256 raw nibbles 0..15 (same as Tom Verbeure's hp3478a_cal_data.bin)
  calram_<date>.info.txt  human-readable decode
verify/restore/decode accept .txt, a raw-nibble .bin (Tom), or a raw 256-byte '@'..'O' dump
(vinayshanbhag/hp3478a's hp3478a_cal_ram_util.py output).
"""
import argparse
import datetime
import os
import sys
import time

RAM_SIZE = 256
BLOCK = 13
N_ENTRIES = 19
UNUSED = {5, 16, 18}  # entries the meter ignores; their checksums do not matter
ENTRY_NAMES = [
    "30 mV DC", "300 mV DC", "3 V DC", "30 V DC", "300 V DC", "(unused)",
    "V AC", "30 ohm", "300 ohm", "3 kohm", "30 kohm", "300 kohm", "3 Mohm",
    "30 Mohm", "300 mA DC", "3 A DC", "(unused)", "300 mA/3 A AC", "(unused)",
]
__version__ = "2.0.7"


# ---------------------------------------------------------------- data format

def bcd(nibbles):
    v = 0
    for n in nibbles:
        v = v * 10 + n
    return v


def decode(data):
    """Return [(name, offset, gain, checksum_ok), ...] for 256 bytes in 0x40..0x4F form."""
    if len(data) != RAM_SIZE:
        raise ValueError("calibration data must be %d bytes, got %d" % (RAM_SIZE, len(data)))
    bad = [i for i, b in enumerate(data) if not 0x40 <= b <= 0x4F]
    if bad:
        raise ValueError("invalid byte(s) at address %s (must be '@'..'O')" % bad[:8])
    nib = [b - 0x40 for b in data]
    entries = []
    for e in range(N_ENTRIES):
        blk = nib[1 + e * BLOCK: 1 + (e + 1) * BLOCK]
        offset = bcd(blk[:6])
        if offset >= 900000:
            offset -= 1000000
        gain_digits = [n - 16 if n & 0x8 else n for n in blk[6:11]]
        gain = 1.0 + bcd(gain_digits) / 1e6
        checksum = (blk[11] << 4) + blk[12]
        ok = (0xFF - (sum(blk[:11]) & 0xFF)) == checksum
        entries.append((ENTRY_NAMES[e], offset, gain, ok))
    return entries


def bad_entries(entries):
    return [i for i, (_, _, _, ok) in enumerate(entries) if not ok and i not in UNUSED]


def report(data):
    entries = decode(data)
    lines = ["Address 0 (r/w check nibble): %d" % (data[0] - 0x40),
             "%-3s %-14s %9s %12s  %s" % ("#", "range", "offset", "gain", "checksum")]
    for i, (name, off, gain, ok) in enumerate(entries):
        state = "ok" if ok else ("(unused, ignored)" if i in UNUSED else "BAD")
        lines.append("%-3d %-14s %9d %12.6f  %s" % (i, name, off, gain, state))
    bad = bad_entries(entries)
    lines.append("Result: %s" % ("all used entries valid" if not bad
                                  else "INVALID checksum in entries %s" % bad))
    return "\n".join(lines)


def to_text(data):
    s = bytes(data).decode("ascii")
    return "\n".join(s[i:i + 16] for i in range(0, RAM_SIZE, 16)) + "\n"


def to_bin(data):
    """Tom Verbeure / pymeasure format: 256 raw nibble values 0..15."""
    return bytes(b - 0x40 for b in data)


def load_file(path):
    """Load a .txt ('@'..'O' text) or .bin (256 raw nibbles) backup; returns 256 bytes 0x40..0x4F."""
    with open(path, "rb") as f:
        content = f.read()
    if len(content) == RAM_SIZE and all(b <= 0x0F for b in content):
        raw = bytes(b + 0x40 for b in content)          # raw-nibble .bin file
    else:
        raw = bytes(b for b in content if b not in b"\r\n \t")
    decode(raw)  # validates length and characters
    return raw


# ---------------------------------------------------------------- meter I/O

class Meter:
    def __init__(self, board, addr):
        try:
            import gpib  # only needed when talking to the meter
        except ImportError:
            raise IOError("Python 'gpib' module not found - install linux-gpib (python3-gpib) on the Pi")
        self.gpib = gpib
        self.dev = gpib.dev(board, addr)
        gpib.remote_enable(board, 1)   # REN on: in local the meter ignores every command
        gpib.timeout(self.dev, gpib.T3s)
        gpib.clear(self.dev)
        self.write(b"T4")  # trigger hold so no readings get in the way
        self.drain()       # ... and throw away a reading that finished before T4

    def write(self, data):
        # must be bytes: str would be UTF-8 encoded and corrupt address bytes >= 0x80
        self.gpib.write(self.dev, bytes(data))

    def drain(self):
        """Read and throw away whatever the meter still has to send, until a short read
        times out. A real 3478A can have a reading waiting (finished just before T4); it
        comes out ahead of the W reply and would be taken for cal data."""
        g = self.gpib
        g.timeout(self.dev, getattr(g, "T300ms", g.T1s))
        try:
            for _ in range(10):
                try:
                    if not g.read(self.dev, 256):
                        break
                except g.GpibError:
                    break
        finally:
            g.timeout(self.dev, g.T3s)

    def read_byte(self, addr):
        r = b""
        for _ in range(3):
            self.write(bytes([ord("W"), addr]))
            r = self.gpib.read(self.dev, 1)
            if len(r) == 1 and 0x40 <= r[0] <= 0x4F:
                return r[0]
            self.drain()   # something else came back (e.g. a reading): empty and ask again
        raise IOError("unexpected reply %r reading cal RAM address %d (3 tries)" % (r, addr))

    def read_ram(self, progress=True):
        out = bytearray()
        for a in range(RAM_SIZE):
            out.append(self.read_byte(a))
            if progress and a % 32 == 31:
                print("  read %3d/%d" % (a + 1, RAM_SIZE), flush=True)
        return bytes(out)

    def write_byte(self, addr, value):
        """value is the stored form 0x40..0x4F; the meter is sent the raw nibble 0..15,
        as Tom Verbeure's script and pymeasure do (only the low 4 bits are stored)."""
        self.write(bytes([ord("X"), addr, value & 0x0F]))

    def cal_enabled(self):
        """Front-panel CAL ENABLE switch, from status byte 2 bit 5 (as pymeasure does)."""
        self.write(b"B")
        st = self.gpib.read(self.dev, 5)
        if len(st) != 5:
            raise IOError("no/short reply to status command B")
        return bool(st[1] & 0x20)

    def done(self):
        try:
            self.write(b"T1")
            self.gpib.ibloc(self.dev)
        except Exception:
            pass


def read_twice(m):
    """Read the RAM twice and require identical results (guards against bus errors)."""
    print("Reading calibration RAM (pass 1)...")
    a = m.read_ram()
    print("Reading calibration RAM (pass 2, check)...")
    b = m.read_ram(progress=False)
    if a != b:
        diff = [i for i in range(RAM_SIZE) if a[i] != b[i]]
        raise IOError("two reads differ at addresses %s - check cable/bus and retry" % diff[:16])
    return a


def unique_name(stem):
    """stem.txt, or stem_2.txt, stem_3.txt ... if it already exists."""
    path, n = stem + ".txt", 1
    while os.path.exists(path):
        n += 1
        path = "%s_%d.txt" % (stem, n)
    return path


def save(data, path, addr):
    stem = os.path.splitext(path)[0]
    binpath, info = stem + ".bin", stem + ".info.txt"
    for p in (path, binpath):
        if os.path.exists(p):
            raise IOError("%s already exists - choose another name" % p)
    with open(path, "x", newline="\n") as f:  # never overwrite an existing backup
        f.write(to_text(data))
    with open(binpath, "xb") as f:
        f.write(to_bin(data))
    with open(info, "w", newline="\n") as f:
        f.write("HP 3478A calibration RAM backup\n")
        f.write("Saved: %s  GPIB address: %d  tool: hp3478a_cal.py %s\n\n"
                % (datetime.datetime.now().isoformat(timespec="seconds"), addr, __version__))
        f.write(report(data) + "\n")
    return binpath, info


# ---------------------------------------------------------------- commands

def cmd_backup(args):
    path = args.file or "calram_%s.txt" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if os.path.exists(path):
        sys.exit("%s already exists - choose another name" % path)
    m = Meter(args.board, args.addr)
    try:
        data = read_twice(m)
    finally:
        m.done()
    print(report(data))
    binpath, info = save(data, path, args.addr)
    print("\nSaved: %s\n       %s\n       %s"
          % (os.path.abspath(path), os.path.abspath(binpath), os.path.abspath(info)))
    if bad_entries(decode(data)):
        print("WARNING: the meter's RAM already has invalid entries (battery may already be weak/lost).")
    print("Copy these files somewhere safe (PC, USB stick, cloud) - not only on the Pi.")


def cmd_verify(args):
    ref = load_file(args.file)
    m = Meter(args.board, args.addr)
    try:
        data = read_twice(m)
    finally:
        m.done()
    diff = [i for i in range(1, RAM_SIZE) if data[i] != ref[i]]
    if diff:
        print("DIFFERENT: %d byte(s) differ, e.g. addresses %s" % (len(diff), diff[:16]))
        sys.exit(1)
    print("MATCH: meter calibration RAM is identical to %s" % args.file)


def cmd_restore(args):
    ref = load_file(args.file)
    bad = bad_entries(decode(ref))
    if bad and not args.force:
        sys.exit("Backup file has invalid checksums in entries %s - refusing (use --force to override)" % bad)
    print("Backup file contents:\n" + report(ref) + "\n")

    m = Meter(args.board, args.addr)
    try:
        if not m.cal_enabled():
            sys.exit("The front-panel CAL switch is not in ENABLE. Set it to ENABLE and run again.")
        current = read_twice(m)
        if all(current[i] == ref[i] for i in range(1, RAM_SIZE)):
            print("Meter already matches the backup - nothing to write.")
            return
        if not args.yes:
            ans = input("Write %s to the meter? Type YES to continue: " % args.file)
            if ans.strip() != "YES":
                sys.exit("Cancelled - nothing written.")

        pre = unique_name("calram_before_restore_%s" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        save(current, pre, args.addr)
        print("Current meter RAM saved first as %s" % pre)

        print("Writing...")
        for a in range(1, RAM_SIZE):        # address 0 is the meter's own r/w check nibble
            for attempt in range(3):
                m.write_byte(a, ref[a])
                if m.read_byte(a) == ref[a]:
                    break
            else:
                sys.exit("Write failed at address %d. Meter RAM is now partly written - "
                         "run restore again. Backup of previous contents: %s" % (a, pre))
            if a % 32 == 31:
                print("  wrote %3d/%d" % (a + 1, RAM_SIZE), flush=True)

        final = read_twice(m)
    finally:
        m.done()
    diff = [i for i in range(1, RAM_SIZE) if final[i] != ref[i]]
    if diff:
        sys.exit("VERIFY FAILED at addresses %s" % diff[:16])
    print("Restore complete and verified.")
    print("Now set the CAL switch back to its normal (disabled) position.")
    print("Then power-cycle the meter and check it against a known voltage/resistance.")


def cmd_decode(args):
    print(report(load_file(args.file)))


def main():
    p = argparse.ArgumentParser(description="HP 3478A calibration RAM backup/restore (v%s)" % __version__)
    p.add_argument("-a", "--addr", type=int, default=23, help="GPIB address (default 23)")
    p.add_argument("-b", "--board", type=int, default=0, help="linux-gpib board index (default 0)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("backup", help="read cal RAM and save to a file")
    s.add_argument("file", nargs="?", help="output file (default calram_<date>.txt)")
    s.set_defaults(fn=cmd_backup)
    s = sub.add_parser("verify", help="compare meter cal RAM with a backup file")
    s.add_argument("file")
    s.set_defaults(fn=cmd_verify)
    s = sub.add_parser("restore", help="write a backup file to the meter (CAL switch ENABLE)")
    s.add_argument("file")
    s.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation")
    s.add_argument("--force", action="store_true", help="allow a backup with bad checksums")
    s.set_defaults(fn=cmd_restore)
    s = sub.add_parser("decode", help="show the contents of a backup file (no meter needed)")
    s.add_argument("file")
    s.set_defaults(fn=cmd_decode)
    args = p.parse_args()
    try:
        args.fn(args)
    except (IOError, ValueError) as e:
        sys.exit("Error: %s" % e)
    except Exception as e:
        if type(e).__name__ == "GpibError":
            sys.exit("GPIB error: %s (check address, cable, and that gpib_config was run)" % e)
        raise


if __name__ == "__main__":
    main()
