# SPDX-License-Identifier: GPL-3.0-only
"""Simulated linux-gpib `gpib` module: an HP-IB bus with an HP 3478A at address 23.

Used by `hpibterm.py --sim` (practice on the PC without a Pi or meter) and by the
tests. It provides the functions of the linux-gpib Python binding that hpiblib uses,
plus parallel_poll(). Board 0 is the controller at bus address 0.

The simulated 3478A understands the codes the real one uses for normal work:
F1..F7, RA/R-2..R7, N3..N5, Z0/Z1, T1..T5, H0..H7, D1/D2text/D3text, K, M<oo>, S, B, E.
Readings are a slightly noisy value per function, e.g. +1.23456E+0 V DC.
Unknown codes set the syntax-error bit (status byte bit 2, RQS if enabled by M).
It also has the 256 x 4-bit calibration RAM, read with "W" + <address byte> (one reply
character, 64 + nibble), as the real meter does. The RAM holds made-up but valid entries.
Environment: HPIB_SIM_READING=+9.99999E+9 forces every reading (over-range tests);
HPIB_SIM_CALRAM=<file> loads the cal RAM from a dump (16x16 text or raw 256 bytes);
HPIB_SIM_CAL_GLITCH=n makes the n-th W read return a wrong value (bus error tests);
HPIB_SIM_EMPTY=1 takes the meter off the bus;
HPIB_SIM_STALE_READING=1 leaves a reading waiting after a device clear, ahead of any reply
(as a real 3478A did when a reading finished just before T4).
"""
import os
import random

__version__ = "2.0.5"

TNONE, T1s, T3s, T10s, T30s, T100s, T1000s = 0, 11, 12, 13, 14, 15, 17
END, TIMO, ERR, CIC, TACS, LACS = 0x2000, 0x4000, 0x8000, 0x20, 0x8, 0x4


SIMULATED = True   # not real hardware: hpiblib skips the /dev/gpibN driver check


class GpibError(Exception):
    pass


_MSG_TIMEOUT = ("A read or write of data bytes has been aborted, possibly due to a "
                "timeout or reception of a device clear command.")
_MSG_NOLISTEN = ("You have attempted to write data or command bytes, but there are no "
                 "listeners currently addressed.")
_MSG_ADDR = "The interface board has failed to address itself properly before starting an io operation."


def _make_calram():
    """Calibration RAM contents: from HPIB_SIM_CALRAM, or 19 made-up entries with valid checksums."""
    src = os.environ.get("HPIB_SIM_CALRAM")
    if src:
        raw = open(src, "rb").read()
        if not (len(raw) == 256 and all(b <= 0x0F for b in bytearray(raw))):
            raw = bytes(b for b in bytearray(raw) if b not in b"\r\n")
            raw = bytes(b - 0x40 for b in bytearray(raw))
        return bytearray(raw[:256])
    ram = bytearray(256)
    for e in range(19):
        if e in (5, 16, 18):
            nib = [0] * 11                              # unused entries
        else:
            off = (e * 37) % 200
            nib = [int(c) for c in "%06d" % off] + [0, 2, e % 8, 3, 1]
        total = sum(nib) & 0xFF
        nib += [(0xFF - total) >> 4, (0xFF - total) & 0x0F]
        ram[1 + e * 13:1 + (e + 1) * 13] = bytes(nib)
    return ram


class HP3478A(object):
    FUNCS = {1: 1.23456, 2: 0.70711, 3: 1000.12, 4: 999.87, 5: 0.0123456, 6: 0.0070711, 7: 1.0e8}

    def __init__(self):
        self.calram = _make_calram()
        self.w_reads = 0
        self.reset()
        self.remote = False
        self.ppconf = None
        self.display = ""

    def reset(self):
        self.func, self.rng, self.digits, self.trig = 1, "A", 5, 1
        self.out = b""
        self.status = 0
        self.mask = 0
        self.error = 0

    def _reading(self):
        forced = os.environ.get("HPIB_SIM_READING")
        if forced:
            return forced
        v = self.FUNCS[self.func] * (1 + random.uniform(-2e-5, 2e-5))
        mant, exp = ("%+.5E" % v).split("E")
        return "%sE%+d" % (mant, int(exp))           # 3478A style: +1.23456E+0

    def take_reading(self):
        self.out = (self._reading() + "\r\n").encode()
        self.status |= 0x01
        self._srq()

    def _srq(self):
        if self.status & self.mask & 0x3F:
            self.status |= 0x40

    def device_clear(self):
        self.out = b""
        if os.environ.get("HPIB_SIM_STALE_READING"):
            self.out = b"-0.00012E-3\r\n"          # a reading that finished before T4

    def trigger(self):
        self.take_reading()

    def write(self, data):
        if not self.remote:
            # In local (REN off) a real 3478A ignores its commands but still answers reads
            return
        s = data.decode("latin-1")
        i = 0
        while i < len(s):
            c = s[i].upper()
            i += 1
            if c in " \r\n,":
                continue
            if c == "W" and i < len(s):              # W + raw address byte: one cal RAM nibble
                addr = ord(s[i]) & 0xFF
                i += 1
                self.w_reads += 1
                nib = self.calram[addr] & 0x0F
                if str(self.w_reads) == os.environ.get("HPIB_SIM_CAL_GLITCH"):
                    nib ^= 0x01
                if os.environ.get("HPIB_SIM_STALE_READING") and self.out:
                    self.out += bytes([0x40 | nib])   # queued behind what is still waiting
                else:
                    self.out = bytes([0x40 | nib])
                continue
            if c == "D":
                mode = s[i:i + 1]
                i += 1
                if mode in ("2", "3"):
                    end = len(s)
                    for t in ("\r", "\n"):
                        if t in s[i:]:
                            end = min(end, s.index(t, i))
                    self.display = s[i:end][:12]
                    i = end
                else:
                    self.display = ""
                continue
            num = ""
            while i < len(s) and (s[i].isdigit() or (s[i] == "-" and not num)):
                num += s[i]
                i += 1
            if c == "F" and num and 1 <= int(num) <= 7:
                self.func = int(num)
            elif c == "R" and (num or s[i:i + 1].upper() == "A"):
                if not num:
                    i += 1
                self.rng = num or "A"
            elif c == "N" and num in ("3", "4", "5"):
                self.digits = int(num)
            elif c == "Z" and num in ("0", "1"):
                pass
            elif c == "T" and num and 1 <= int(num) <= 5:
                self.trig = int(num)
                if self.trig in (3, 5):
                    self.take_reading()
            elif c == "H" and num and 0 <= int(num) <= 7:
                self.reset()
                if int(num):
                    self.func = int(num)
                    self.take_reading()
                    self.trig = 4
            elif c == "K" and not num:
                self.status = 0
                self.error = 0
            elif c == "M" and len(num) == 2 and "8" not in num and "9" not in num:
                self.mask = int(num, 8)          # SRQ mask, two octal digits
            elif c == "S" and not num:
                self.out = b"1\r\n"
            elif c == "B" and not num:
                rng = {"A": 0}.get(self.rng, 1)
                self.out = bytes(bytearray([(self.func << 5) | (rng << 2) | (self.digits - 2),
                                            0x15, self.status & 0x3F, self.error, 0x20]))
            elif c == "E" and not num:
                self.out = ("%03o\r\n" % self.error).encode()
            else:
                self._syntax()

    def _syntax(self):
        self.status |= 0x04
        self.error |= 0x01
        self._srq()

    def read(self, n):
        if not self.out and self.trig == 1:
            self.take_reading()
        r, self.out = self.out[:n], self.out[n:]
        if not self.out:
            self.status &= ~0x01
        return r, not self.out          # (data, EOI on last byte)

    def spoll(self):
        st = self.status
        self.status &= ~0x40
        return st


class Bus(object):
    def __init__(self):
        self.me = 0
        self.devices = {} if os.environ.get("HPIB_SIM_EMPTY") else {23: HP3478A()}
        self.listeners = set()
        self.talker = None
        self.ren = False
        self.llo = False
        self.sta = 0
        self.handles = {}          # ud -> dict(pad, sad, eot, eosrd, eoschar, tmo, endbit)
        self.next_ud = 16
        self.board_cfg = {"eosrd": 0, "eoschar": 10, "eot": 1, "endbit": 1, "tmo": T10s}

    def command(self, data):
        for c in bytearray(data):
            if c == 0x3F:
                self.listeners.clear()
            elif c == 0x5F:
                self.talker = None
            elif 0x20 <= c < 0x3F:
                self.listeners.add(c - 0x20)
            elif 0x40 <= c < 0x5F:
                self.talker = c - 0x40
            elif c == 0x14:
                for d in self.devices.values():
                    d.device_clear()
            elif c == 0x04:
                for p in self._listening_devices():
                    self.devices[p].device_clear()
            elif c == 0x08:
                for p in self._listening_devices():
                    self.devices[p].trigger()
            elif c == 0x01:
                for p in self._listening_devices():
                    self.devices[p].remote = False
            elif c == 0x11:
                self.llo = True
            elif c == 0x15:
                for d in self.devices.values():
                    d.ppconf = None
            elif 0x60 <= c < 0x80:
                for p in self._listening_devices():
                    self.devices[p].ppconf = None if c >= 0x70 else c & 0x0F
        for p in self._listening_devices():
            if self.ren:
                self.devices[p].remote = True

    def _listening_devices(self):
        return [p for p in self.listeners if p in self.devices]


BUS = Bus()


def _h(ud):
    if ud in BUS.handles:
        return BUS.handles[ud]
    if ud == 0:
        return None
    raise GpibError("%s() failed: One or more arguments to the function call were invalid." % "call")


def _err(func, msg, timo=False):
    BUS.sta = ERR | (TIMO if timo else 0)
    raise GpibError("%s() failed: %s" % (func, msg))


def find(name):
    return 0


def dev(board, pad, sad=0, tmo=T10s, eot=1, eos=0):
    if board != 0:
        _err("dev", "The GPIB interface board does not exist, its driver is not loaded, or it is in use by another process.")
    ud = BUS.next_ud
    BUS.next_ud += 1
    BUS.handles[ud] = {"pad": pad, "sad": sad, "eot": eot, "eosrd": 0, "eoschar": 10,
                       "tmo": tmo, "endbit": 1}
    return ud


def ask(ud, option):
    if option == 0x1:
        return BUS.me if ud == 0 else _h(ud)["pad"]
    return 0


def config(ud, option, value):
    cfg = BUS.board_cfg if ud == 0 else _h(ud)
    key = {0x1: "pad", 0x4: "eot", 0xC: "eosrd", 0xF: "eoschar", 0x1A: "endbit", 0x3: "tmo"}.get(option)
    if key is None:
        _err("config", "One or more arguments to the function call were invalid.")
    if ud == 0 and key == "pad":
        BUS.me = value
    cfg[key] = value


def timeout(ud, value):
    (BUS.board_cfg if ud == 0 else _h(ud))["tmo"] = value


def _device(ud, func):
    h = _h(ud)
    d = BUS.devices.get(h["pad"])
    if d is None:
        _err(func, _MSG_NOLISTEN if func in ("write", "clear", "trigger", "ibloc") else _MSG_TIMEOUT,
             timo=func not in ("write", "clear", "trigger", "ibloc"))
    return h, d


def write(ud, data):
    if isinstance(data, str):
        data = data.encode("utf-8")          # what the real binding's s# does with str
    if ud == 0:
        if BUS.talker != BUS.me:
            _err("write", _MSG_ADDR)
        targets = BUS._listening_devices()
        if not targets:
            _err("write", _MSG_NOLISTEN)
        for p in targets:
            BUS.devices[p].write(bytes(data))
    else:
        _h_, d = _device(ud, "write")
        if BUS.ren:
            d.remote = True
        d.write(bytes(data))
    BUS.sta = 0x100


def _read_from(d, cfg, n):
    out = b""
    eoi = False
    while len(out) < n:
        chunk, last = d.read(1)
        if not chunk:
            break
        out += chunk
        if last:
            eoi = True
            break
        if cfg["eosrd"] and chunk[0] == cfg["eoschar"]:
            break
    if not out:
        _err("read", _MSG_TIMEOUT, timo=True)
    end = eoi or (cfg["endbit"] and cfg["eosrd"] and out[-1] == cfg["eoschar"])
    BUS.sta = 0x100 | (END if end else 0)
    return out


def read(ud, n):
    if ud == 0:
        if BUS.me not in BUS.listeners or BUS.talker not in BUS.devices:
            _err("read", _MSG_ADDR)
        return _read_from(BUS.devices[BUS.talker], BUS.board_cfg, n)
    h, d = _device(ud, "read")
    return _read_from(d, h, n)


def command(ud, data):
    BUS.command(bytes(data))
    BUS.sta = 0x100


def remote_enable(ud, val):
    BUS.ren = bool(val)
    if not val:
        BUS.llo = False
        for d in BUS.devices.values():
            d.remote = False


def clear(ud):
    _h_, d = _device(ud, "clear")
    d.device_clear()


def interface_clear(ud):
    BUS.listeners.clear()
    BUS.talker = None


def close(ud):
    BUS.handles.pop(ud, None)


def wait(ud, mask):
    sta = CIC
    if BUS.talker == BUS.me:
        sta |= TACS
    if BUS.me in BUS.listeners:
        sta |= LACS
    if any(d.status & 0x40 for d in BUS.devices.values()):
        sta |= 0x1000
    return sta


def lines(ud):
    srq = any(d.status & 0x40 for d in BUS.devices.values())
    v = 0xFF                                   # all lines valid
    if srq:
        v |= 0x2000
    if BUS.ren:
        v |= 0x1000
    if BUS.devices:
        v |= 0x0200                             # NDAC held by an idle device
    return v


def serial_poll(ud):
    _h_, d = _device(ud, "serial_poll")
    return d.spoll()


def trigger(ud):
    _h_, d = _device(ud, "trigger")
    d.trigger()


def ibloc(ud):
    if ud == 0:
        remote_enable(0, 0)
        return
    _h_, d = _device(ud, "ibloc")
    d.remote = False


def listener(ud, pad, sad=0):
    return pad in BUS.devices


def parallel_poll(ud):
    v = 0
    for d in BUS.devices.values():
        if d.ppconf is not None:
            sense, line = (d.ppconf >> 3) & 1, d.ppconf & 7
            ist = 1 if d.status & 0x40 else 0
            if ist == sense:
                v |= 1 << line
    return v


def ibsta():
    return BUS.sta


def ibcnt():
    return 0


def version():
    return "hpib_sim " + __version__
