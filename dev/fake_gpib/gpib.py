# SPDX-License-Identifier: GPL-3.0-only
"""Minimal stand-in for the linux-gpib `gpib` Python module, for off-hardware tests.

Usage: PYTHONPATH=<this dir>, then run the script under test.
Simulates an HP 3478A: 256 x 4-bit cal SRAM (W/X), status bytes (B), S, readings.
Env: FAKE_RAM=<dump file, 16x16 chars>  CAL=1|0 (front-panel CAL switch)
     FAKE_READING=+1.23456E+0   FAKE_XLOG=<file> (records every X data byte sent)
     FAKE_STALE=1 (a reading is left waiting after clear(), ahead of any reply)
Like a real meter, it ignores every command until remote_enable(board, 1) has set REN.
"""
import os

T300ms, T1s, T3s, T10s, T30s = 10, 11, 12, 13, 14


SIMULATED = True   # not real hardware: hpiblib skips the /dev/gpibN driver check


class GpibError(Exception):
    pass


_src = os.environ.get("FAKE_RAM")
RAM = bytearray(b for b in open(_src, "rb").read() if b not in b"\r\n") if _src else bytearray(b"@" * 256)
CAL = os.environ.get("CAL", "1") == "1"
_out = b""


def dev(board, pad, *a): return 1
def timeout(d, t): pass
def clear(d):
    global _out
    _out = b"-0.00012E-3\r\n" if os.environ.get("FAKE_STALE") else b""
_ren = False


def remote_enable(d, val):
    global _ren
    _ren = bool(val)


def ibloc(d): pass


def write(d, data):
    global _out
    if isinstance(data, str):
        data = data.encode("utf-8")  # mimic the binding's s# behaviour
    if not _ren:
        return                       # REN off: the meter is in local and ignores commands
    if data[:1] == b"W":
        if os.environ.get("FAKE_STALE") and _out:
            _out += bytes([RAM[data[1]]])
        else:
            _out = bytes([RAM[data[1]]])
    elif data[:1] == b"X":
        log = os.environ.get("FAKE_XLOG")
        if log:
            with open(log, "ab") as f:
                f.write(bytes([data[2]]))
        if CAL:                      # SRAM stores only the low 4 bits; W adds 64
            RAM[data[1]] = 0x40 | (data[2] & 0x0F)
    elif data[:1] == b"B":
        _out = bytes([0x21, 0x15 | (0x20 if CAL else 0), 0x00, 0x00, 0x20])
    elif data[:1] == b"S":
        _out = b"1\r\n"
    elif b"T3" in data or data[:1] == b"H":
        _out = os.environ.get("FAKE_READING", "+1.23456E+0").encode() + b"\r\n"


def read(d, n):
    global _out
    if not _out:
        raise GpibError("read() error: A timeout occurred. (errno: 0)")   # as linux-gpib does
    r, _out = _out[:n], _out[n:]
    return r
