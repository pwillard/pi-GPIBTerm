# SPDX-License-Identifier: GPL-3.0-only
"""HP 82990A "HP-IB Command Library for MS-DOS" work-alike on top of linux-gpib.

Implements the 26 library commands described in the HP-IB Command Library
Reference (82990-90001, June 1986), with the same names, parameter order,
addressing and error numbers:

    select code     7            -> the interface (linux-gpib board, default board 0)
    device address  723          -> select code 7, primary address 23
    extended        72315        -> select code 7, primary 23, secondary 15

Errors are raised as HpibError(code) with the library's numbers
(NOERR 0, EUNKNOWN 100001 ... EADDR 100008) and "HPIB: ..." messages.

The `gpib` argument is the linux-gpib Python module (or the hpib_sim simulator).
Strings are handled as latin-1 so every byte 0..255 maps to one character.
"""
import contextlib
import ctypes
import math
import os
import re
import sys

__version__ = "2.0.6"

@contextlib.contextmanager
def _quiet_stderr():
    """Hide what C code (libgpib) prints to stderr while the block runs."""
    try:
        sys.stderr.flush()
        saved = os.dup(2)
        null = os.open(os.devnull, os.O_WRONLY)
    except (OSError, AttributeError, ValueError):
        yield
        return
    try:
        os.dup2(null, 2)
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(null)


NOERR, EUNKNOWN, ESEL, ERANGE, ETIME, ECTRL, EPASS, ENUM, EADDR = (
    0, 100001, 100002, 100003, 100004, 100005, 100006, 100007, 100008)

ERRORS = {
    NOERR: ("NOERR", "No error"),
    EUNKNOWN: ("EUNKNOWN", "HPIB: unknown error"),
    ESEL: ("ESEL", "HPIB: invalid select code or device address"),
    ERANGE: ("ERANGE", "HPIB: value out of range"),
    ETIME: ("ETIME", "HPIB: timeout"),
    ECTRL: ("ECTRL", "HPIB: must be active/system controller"),
    EPASS: ("EPASS", "HPIB: pass control not permitted"),
    ENUM: ("ENUM", "HPIB: improperly formed number"),
    EADDR: ("EADDR", "HPIB: improper addressing"),
}

# IEEE-488 bus command bytes (sent with ATN)
GTL, SDC, PPC, GET, LLO, DCL, PPU, SPE, SPD = 0x01, 0x04, 0x05, 0x08, 0x11, 0x14, 0x15, 0x18, 0x19
UNL, UNT, PPD = 0x3F, 0x5F, 0x70

# linux-gpib constants (gpib_user.h); used numerically so older bindings work too
IbcPAD, IbcEOT, IbcEOSrd, IbcEOSchar, IbcEndBitIsNormal = 0x1, 0x4, 0xC, 0xF, 0x1A
IbaPAD = 0x1
STA_END, STA_TIMO, STA_ERR, STA_CIC, STA_TACS, STA_LACS = 0x2000, 0x4000, 0x8000, 0x20, 0x8, 0x4
BUS_NDAC, BUS_SRQ, VALID_NDAC, VALID_SRQ = 0x0200, 0x2000, 0x02, 0x20
TMO_TABLE = [(10e-6, 1), (30e-6, 2), (100e-6, 3), (300e-6, 4), (1e-3, 5), (3e-3, 6), (10e-3, 7),
             (30e-3, 8), (100e-3, 9), (300e-3, 10), (1, 11), (3, 12), (10, 13), (30, 14),
             (100, 15), (300, 16), (1000, 17)]

NUMBER_RE = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


class HpibError(Exception):
    """A library error. .code is the 82990A error number, .value an optional partial result."""

    def __init__(self, code, detail="", value=None):
        self.code = code
        self.mnemonic, self.message = ERRORS.get(code, ERRORS[EUNKNOWN])
        self.detail = detail
        self.value = value
        Exception.__init__(self, self.message + (" (%s)" % detail if detail else ""))


def format_real(x):
    """Number text as the library sends it (IOOUTPUT/IOOUTPUTA): 7 significant digits,
    fixed point for 1E-5 <= |x| < 1E+6 (no decimal point for integers), otherwise
    scientific; a leading space for positive numbers, '-' for negative."""
    x = float(x)
    if x == 0:
        s = "0"
    elif 1e-5 <= abs(x) < 1e6:
        places = max(0, 6 - int(math.floor(math.log10(abs(x)))))
        s = "%.*f" % (places, x)
        if "." in s:
            s = s.rstrip("0").rstrip(".")
    else:
        s = "%.6E" % x
    if not s.startswith("-"):
        s = " " + s
    return s


def parse_numbers(text):
    return [float(m.group(0)) for m in NUMBER_RE.finditer(text)]


def to_bytes(s):
    if isinstance(s, bytes):
        return s
    try:
        return s.encode("latin-1")
    except UnicodeEncodeError:
        raise HpibError(ERANGE, "string contains a character above CHR$(255)")


class _Iface(object):
    """Per-select-code settings that the library keeps (IOEOI, IOEOL, IOMATCH, ...)."""

    def __init__(self, board, timeout):
        self.board = board
        self.reset_settings(timeout)

    def reset_settings(self, timeout):
        self.eoi = True
        self.eol = b"\r\n"
        self.match = b"\n"
        self.match_on = True
        self.timeout = timeout
        self.term = 0
        self.dma = (0, 3)


class Library(object):
    """The HP-IB Command Library. Method names are the command names in lower case."""

    def __init__(self, gpib, select_codes=None, timeout=10.0, trace=None):
        self.gpib = gpib
        self.ifaces = {}
        for sc, board in (select_codes or {7: 0}).items():
            self.ifaces[int(sc)] = _Iface(int(board), float(timeout))
        self.trace = trace            # callable(str) or None: prints bus activity
        self._devs = {}               # (sc, pad, sad) -> linux-gpib handle
        self._endbit_ok = {}          # handle -> True if END now means EOI only
        # Start-up configuration, as on the 82990A: REN set, so an instrument obeys commands
        # as soon as it is addressed to listen. (A device ignores its commands while REN is
        # off - it stays in local - but still answers reads.) IOLOCAL <select code> clears
        # REN, IOREMOTE sets it again.
        for iface in self.ifaces.values():
            try:
                self.gpib.remote_enable(iface.board, 1)
            except Exception:
                pass                  # e.g. the driver isn't loaded: driver_problem() says so

    # ------------------------------------------------------------ helpers
    def _t(self, text):
        if self.trace:
            self.trace(text)

    def _iface(self, sc):
        if sc not in self.ifaces:
            raise HpibError(ESEL, "no interface at select code %d (known: %s)"
                            % (sc, ", ".join(str(k) for k in sorted(self.ifaces))))
        return self.ifaces[sc]

    def address(self, value, allow_sc=True, allow_dev=True):
        """Split a library address into (select code, pad or None, sad or None)."""
        try:
            f = float(value)
        except (TypeError, ValueError):
            raise HpibError(ESEL, "address must be a number")
        a = int(f)
        if a != f or a < 0:
            raise HpibError(ESEL, "%r is not a select code or device address" % value)
        if a <= 99:
            if not allow_sc:
                raise HpibError(ESEL, "this command needs a device address such as 723, not a select code")
            self._iface(a)
            return a, None, None
        if not allow_dev:
            raise HpibError(ESEL, "this command needs a select code such as 7, not a device address")
        if a <= 9999:
            sc, pad = divmod(a, 100)
            sad = None
        else:
            sc, rest = divmod(a, 10000)
            pad, sad = divmod(rest, 100)
            if sad > 30:
                raise HpibError(ESEL, "secondary address %d out of range 0-30" % sad)
        self._iface(sc)
        if pad > 30:
            raise HpibError(ESEL, "primary address %d out of range 0-30" % pad)
        if pad == self._my_pad(sc):
            raise HpibError(ESEL, "address %d is the interface itself" % pad)
        return sc, pad, sad

    _endbit_supported = None     # IbcEndBitIsNormal: None = not tried yet

    def driver_problem(self, sc=None, dev_dir="/dev"):
        """Explain why the linux-gpib board for select code sc (default: all) can't be used,
        or return None. The board's device file (/dev/gpib0 for board 0) only exists while the
        gpib4pi driver (gpib_bitbang) is loaded and gpib_config has run."""
        if getattr(self.gpib, "SIMULATED", False) is True or not os.path.isdir(dev_dir):
            return None
        for s in ([sc] if sc is not None else sorted(self.ifaces)):
            board = self.ifaces[s].board
            path = "%s/gpib%d" % (dev_dir, board)
            if not os.path.exists(path):
                return ("%s does not exist, so the GPIB driver is not loaded (select code %d = board %d). "
                        "Check it with: systemctl status gpib.service   Start it with: "
                        "sudo systemctl restart gpib.service   (if gpib.service is missing, run "
                        "setup_pi.sh first)" % (path, s, board))
            if not os.access(path, os.R_OK | os.W_OK):
                return ("no permission to use %s - log out and in again after installing "
                        "(you are added to the 'gpib' group), or run the terminal with sudo" % path)
        return None

    def _call(self, fn, *args):
        try:
            return fn(*args)
        except self.gpib.GpibError as e:
            raise self._map_error(e)

    def _map_error(self, e):
        msg = str(e)
        low = msg.lower()
        sta = 0
        try:
            sta = self.gpib.ibsta()
        except Exception:
            pass
        if (sta & STA_TIMO) or "timeout" in low or "aborted" in low or "timed out" in low:
            return HpibError(ETIME, msg)
        if "no listeners" in low:
            return HpibError(ETIME, "no device is listening at that address - check power, cable and address")
        if "controller-in-charge" in low or "system controller" in low:
            return HpibError(ECTRL, msg)
        if "address itself" in low:
            return HpibError(EADDR, msg)
        if "does not exist" in low or "driver is not loaded" in low or "no such" in low:
            return HpibError(ESEL, msg)
        if "bad file descriptor" in low or "errno: 9" in low or "ibboardopen" in low:
            # linux-gpib could not open the board's device file: the driver isn't loaded
            return HpibError(ESEL, self.driver_problem() or msg)
        if "permission denied" in low or "errno: 13" in low:
            return HpibError(ESEL, self.driver_problem() or (msg + " - run the terminal with sudo"))
        if "arguments" in low and "invalid" in low:
            return HpibError(ERANGE, msg)
        return HpibError(EUNKNOWN, msg)

    def _tmo_code(self, seconds):
        if seconds <= 0:
            return 0                          # TNONE: disabled
        for limit, code in TMO_TABLE:
            if seconds <= limit * 1.0000001:
                return code
        return 17

    def _my_pad(self, sc):
        iface = self.ifaces[sc]
        if not hasattr(iface, "pad"):
            try:
                iface.pad = int(self.gpib.ask(iface.board, IbaPAD))
            except Exception:
                iface.pad = 0
        return iface.pad

    def _dev(self, sc, pad, sad):
        key = (sc, pad, sad)
        if key not in self._devs:
            iface = self.ifaces[sc]
            ud = self._call(self.gpib.dev, iface.board, pad, 0 if sad is None else 0x60 + sad,
                            self._tmo_code(iface.timeout), 1, 0)
            # END bit = EOI only, so IOGETTERM can tell EOI from the match character. Some
            # linux-gpib versions don't support it and print "libgpib: no support for END on
            # EOI only yet" to stderr: try once, quietly, and remember the answer.
            if Library._endbit_supported is not False:
                try:
                    with _quiet_stderr():
                        self.gpib.config(ud, IbcEndBitIsNormal, 0)
                    Library._endbit_supported = True
                except Exception:
                    Library._endbit_supported = False
            self._endbit_ok[ud] = bool(Library._endbit_supported)
            self._devs[key] = ud
        return self._devs[key]

    def _target(self, sc, pad, sad):
        """linux-gpib handle for a device address, or the board for a select code."""
        if pad is None:
            return self.ifaces[sc].board
        return self._dev(sc, pad, sad)

    def _cmd(self, sc, data):
        self._call(self.gpib.command, self.ifaces[sc].board, bytes(bytearray(data)))

    def _addr_bytes(self, sc, pad, sad, listen=True):
        """UNL, MTA, LAD[, SAD] (or UNL, MLA, TAD[, SAD] when the device is to talk)."""
        me = self._my_pad(sc)
        if listen:
            seq = [UNL, 0x40 + me, 0x20 + pad]
        else:
            seq = [UNL, 0x20 + me, 0x40 + pad]
        if sad is not None:
            seq.append(0x60 + sad)
        return seq

    def _who(self, pad, sad):
        return "%d" % pad + ("" if sad is None else ",SA%d" % sad)

    def _read(self, sc, ud, maxlen, use_match):
        """One linux-gpib read. Returns (data, reason) with reason as IOGETTERM sums it."""
        iface = self.ifaces[sc]
        m = iface.match if (use_match and iface.match_on) else None
        try:
            if m:
                self.gpib.config(ud, IbcEOSchar, m[0])
            self.gpib.config(ud, IbcEOSrd, 1 if m else 0)
        except Exception:
            pass
        data = self._call(self.gpib.read, ud, int(maxlen))
        try:
            sta = self.gpib.ibsta()
        except Exception:
            sta = 0
        reason = 0
        if len(data) >= maxlen:
            reason |= 1
        matched = bool(m) and data.endswith(m)
        if matched:
            reason |= 2
        if sta & STA_END and (self._endbit_ok.get(ud) or not matched):
            reason |= 4
        return data, reason

    def _write(self, sc, pad, sad, payload):
        iface = self.ifaces[sc]
        ud = self._target(sc, pad, sad)
        try:
            self.gpib.config(ud, IbcEOT, 1 if iface.eoi else 0)
        except Exception:
            pass
        if pad is not None:
            self._t("ATN UNL MTA LAD %s, ATN off" % self._who(pad, sad))
        self._t("data %s%s" % (show(payload), " +EOI" if iface.eoi and payload else ""))
        self._call(self.gpib.write, ud, payload)

    # ------------------------------------------------------------ the 26 commands
    def ioabort(self, sc):
        sc = self.address(sc, allow_dev=False)[0]
        b = self.ifaces[sc].board
        self._t("IFC pulsed, REN set, ATN cleared")
        self._call(self.gpib.interface_clear, b)
        self._call(self.gpib.remote_enable, b, 1)

    def ioclear(self, addr):
        sc, pad, sad = self.address(addr)
        if pad is None:
            self._t("ATN DCL")
            self._cmd(sc, [DCL])
        else:
            self._t("ATN UNL MTA LAD %s SDC" % self._who(pad, sad))
            self._call(self.gpib.clear, self._dev(sc, pad, sad))

    def iocontrol(self, sc, condition, status):
        sc = self.address(sc, allow_dev=False)[0]
        condition, status = int(condition), int(status)
        me = self._my_pad(sc)
        if condition == 5:
            self._t("ATN %s" % ("MTA" if status else "UNT"))
            self._cmd(sc, [0x40 + me] if status else [UNT])
        elif condition == 6:
            self._t("ATN %s" % ("MLA" if status else "UNL"))
            self._cmd(sc, [0x20 + me] if status else [UNL])
        elif condition == 7:
            if not 0 <= status <= 30:
                raise HpibError(ERANGE, "bus address must be 0-30")
            self._call(self.gpib.config, self.ifaces[sc].board, IbcPAD, status)
            self.ifaces[sc].pad = status
        else:
            raise HpibError(ERANGE, "condition must be 5, 6 or 7")

    def iodma(self, sc, value, channel):
        sc = self.address(sc, allow_dev=False)[0]
        if value < 0 or int(channel) not in (2, 3):
            raise HpibError(ERANGE, "value must be >= 0 and channel 2 or 3")
        self.ifaces[sc].dma = (int(value), int(channel))   # linux-gpib decides DMA itself

    def ioenter(self, addr):
        sc, pad, sad = self.address(addr)
        ud = self._target(sc, pad, sad)
        if pad is not None:
            self._t("ATN UNL MLA TAD %s, ATN off, enter number" % self._who(pad, sad))
        data, reason = self._read(sc, ud, 256, False)
        text = data.decode("latin-1")
        # stop at the first linefeed after the number started (as the 82990A does)
        nums = parse_numbers(text)
        self.ifaces[sc].term = reason
        self._t("received %s" % show(data))
        if not nums:
            raise HpibError(ENUM, "received %s" % show(data), value=0.0)
        return nums[0]

    def ioentera(self, addr, max_elements):
        sc, pad, sad = self.address(addr)
        max_elements = int(max_elements)
        if max_elements < 0:
            raise HpibError(ERANGE, "max.elements must be >= 0")
        iface = self.ifaces[sc]
        ud = self._target(sc, pad, sad)
        if pad is not None:
            self._t("ATN UNL MLA TAD %s, ATN off, enter numbers" % self._who(pad, sad))
        text, nums, reason = "", [], 0
        while len(nums) < max_elements:
            try:
                data, reason = self._read(sc, ud, 4096, False)
            except HpibError as e:
                e.value = nums[:max_elements]
                raise
            text += data.decode("latin-1")
            nums = parse_numbers(text)
            if iface.eoi and reason & 4:
                break
            if not data:
                break
        iface.term = (reason & 4) | (1 if len(nums) >= max_elements else 0)
        self._t("received %d number(s)" % min(len(nums), max_elements))
        if not nums and max_elements:
            raise HpibError(ENUM, "no number in %s" % show(to_bytes(text[:60])), value=[])
        return nums[:max_elements]

    def ioenters(self, addr, max_length):
        sc, pad, sad = self.address(addr)
        max_length = int(max_length)
        if max_length < 0:
            raise HpibError(ERANGE, "max.length must be >= 0")
        iface = self.ifaces[sc]
        ud = self._target(sc, pad, sad)
        if pad is not None:
            self._t("ATN UNL MLA TAD %s, ATN off, enter string" % self._who(pad, sad))
        out, reason = b"", 0
        while len(out) < max_length:
            try:
                data, reason = self._read(sc, ud, max_length - len(out), True)
            except HpibError as e:
                e.value = out.decode("latin-1")
                raise
            out += data
            if reason & 2 or (reason & 4 and iface.eoi) or not data:
                break
            # EOI disabled: linux-gpib still stops on EOI, so keep reading (82990A behaviour)
        if len(out) >= max_length:
            reason |= 1
        iface.term = reason
        self._t("received %s" % show(out))
        return out.decode("latin-1")

    def ioeoi(self, sc, state):
        sc = self.address(sc, allow_dev=False)[0]
        self.ifaces[sc].eoi = bool(state)

    def ioeol(self, sc, endline, length=None):
        sc = self.address(sc, allow_dev=False)[0]
        b = to_bytes(endline)
        length = len(b) if length is None else int(length)
        if not 0 <= length <= 8:
            raise HpibError(ERANGE, "EOL length must be 0-8")
        self.ifaces[sc].eol = b[:length]

    def iogetterm(self, sc):
        sc = self.address(sc, allow_dev=False)[0]
        return self.ifaces[sc].term

    def iollockout(self, sc):
        sc = self.address(sc, allow_dev=False)[0]
        self._t("ATN LLO")
        self._cmd(sc, [LLO])

    def iolocal(self, addr):
        sc, pad, sad = self.address(addr)
        if pad is None:
            self._t("REN cleared, ATN cleared")
            self._call(self.gpib.remote_enable, self.ifaces[sc].board, 0)
        else:
            self._t("ATN UNL MTA LAD %s GTL" % self._who(pad, sad))
            self._call(self.gpib.ibloc, self._dev(sc, pad, sad))

    def iomatch(self, sc, character, flag=1):
        sc = self.address(sc, allow_dev=False)[0]
        b = to_bytes(character)
        if flag and len(b) < 1:
            raise HpibError(ERANGE, "give one match character")
        if b:
            self.ifaces[sc].match = b[:1]
        self.ifaces[sc].match_on = bool(flag)

    def iooutput(self, addr, data):
        sc, pad, sad = self.address(addr)
        self._write(sc, pad, sad, to_bytes(format_real(data)) + self.ifaces[sc].eol)

    def iooutputa(self, addr, values):
        sc, pad, sad = self.address(addr)
        text = ",".join(format_real(v) for v in values)
        self._write(sc, pad, sad, to_bytes(text) + self.ifaces[sc].eol)

    def iooutputs(self, addr, data, length=None):
        sc, pad, sad = self.address(addr)
        b = to_bytes(data)
        if length is not None:
            if int(length) < 0:
                raise HpibError(ERANGE, "length must be >= 0")
            b = b[:int(length)]
        self._write(sc, pad, sad, b + self.ifaces[sc].eol)

    def ioppoll(self, sc):
        sc = self.address(sc, allow_dev=False)[0]
        b = self.ifaces[sc].board
        self._t("ATN+EOI asserted, poll byte read")
        if hasattr(self.gpib, "parallel_poll"):          # simulator / future bindings
            return self._call(self.gpib.parallel_poll, b)
        try:
            lib = ctypes.CDLL("libgpib.so.0")
        except OSError:
            raise HpibError(EUNKNOWN, "parallel poll needs libgpib.so.0 (linux-gpib)")
        ppr = ctypes.c_char()
        sta = lib.ibrpp(b, ctypes.byref(ppr))
        if sta & STA_ERR:
            if sta & STA_TIMO:
                raise HpibError(ETIME, "ibrpp timed out (ibsta 0x%04X)" % sta)
            # linux-gpib's gpib_bitbang driver (the gpib4pi board) has no parallel poll at all
            raise HpibError(EUNKNOWN, "parallel poll failed (ibsta 0x%04X): this GPIB driver may not "
                                      "support it - the gpib4pi's gpib_bitbang driver has none. "
                                      "Use IOSTATUS (SRQ) and IOSPOLL instead." % sta)
        return ord(ppr.value)

    def ioppollc(self, addr, configuration):
        sc, pad, sad = self.address(addr)
        configuration = int(configuration)
        if not 0 <= configuration <= 15:
            raise HpibError(ERANGE, "configuration must be 0-15")
        seq = [] if pad is None else self._addr_bytes(sc, pad, sad)
        self._t("ATN %sPPC PPE(%d)" % ("" if pad is None else "UNL MTA LAD %s " % self._who(pad, sad),
                                        configuration))
        self._cmd(sc, seq + [PPC, 0x60 | configuration])

    def ioppollu(self, addr):
        sc, pad, sad = self.address(addr)
        if pad is None:
            self._t("ATN PPU")
            self._cmd(sc, [PPU])
        else:
            self._t("ATN UNL MTA LAD %s PPC PPD" % self._who(pad, sad))
            self._cmd(sc, self._addr_bytes(sc, pad, sad) + [PPC, PPD])

    def ioremote(self, addr):
        sc, pad, sad = self.address(addr)
        b = self.ifaces[sc].board
        self._call(self.gpib.remote_enable, b, 1)
        if pad is None:
            self._t("REN set")
        else:
            self._t("REN set, ATN UNL MTA LAD %s" % self._who(pad, sad))
            self._cmd(sc, self._addr_bytes(sc, pad, sad))

    def ioreset(self, sc):
        sc = self.address(sc, allow_dev=False)[0]
        iface = self.ifaces[sc]
        # The manual: "IFC is pulsed (>100 uS). REN is cleared (>10 uS)." REN is pulsed
        # off - every device goes to local - and set again, the start-up configuration.
        self._t("IFC pulsed, REN pulsed off (devices to local) then set, ATN cleared; "
                "timeout 0 (off), EOI on, EOL CR/LF, MATCH LF")
        self._call(self.gpib.interface_clear, iface.board)
        self._call(self.gpib.remote_enable, iface.board, 0)
        self._call(self.gpib.remote_enable, iface.board, 1)
        iface.reset_settings(0.0)
        self._apply_timeout(sc)

    def iosend(self, sc, commands, length=None):
        sc = self.address(sc, allow_dev=False)[0]
        b = to_bytes(commands)
        if length is not None:
            if int(length) < 0:
                raise HpibError(ERANGE, "length must be >= 0")
            b = b[:int(length)]
        self._t("ATN %s" % " ".join(bus_name(c, self._my_pad(sc)) for c in bytearray(b)))
        self._cmd(sc, bytearray(b))

    def iospoll(self, addr):
        sc, pad, sad = self.address(addr, allow_sc=False)
        self._t("ATN UNL MLA TAD %s SPE, ATN off, read byte, ATN SPD UNT" % self._who(pad, sad))
        return int(self._call(self.gpib.serial_poll, self._dev(sc, pad, sad)))

    def iostatus(self, sc, condition):
        sc = self.address(sc, allow_dev=False)[0]
        condition = int(condition)
        b = self.ifaces[sc].board
        if not 0 <= condition <= 7:
            raise HpibError(ERANGE, "condition must be 0-7")
        if condition == 0:
            return 0
        if condition in (3,):
            return 1
        if condition in (1, 2):
            lines = int(self._call(self.gpib.lines, b))
            valid, bit = (VALID_SRQ, BUS_SRQ) if condition == 1 else (VALID_NDAC, BUS_NDAC)
            if not lines & valid:
                raise HpibError(EUNKNOWN, "this interface cannot report that bus line")
            return 1 if lines & bit else 0
        if condition == 7:
            return self._my_pad(sc)
        sta = int(self._call(self.gpib.wait, b, 0))
        return 1 if sta & {4: STA_CIC, 5: STA_TACS, 6: STA_LACS}[condition] else 0

    def iotimeout(self, sc, timeout):
        sc = self.address(sc, allow_dev=False)[0]
        timeout = float(timeout)
        if not 0 <= timeout <= 4096:
            raise HpibError(ERANGE, "timeout must be 0 (off) to 4096 seconds")
        self.ifaces[sc].timeout = timeout
        self._apply_timeout(sc)

    def _apply_timeout(self, sc):
        iface = self.ifaces[sc]
        code = self._tmo_code(iface.timeout)
        for (s, _p, _s), ud in self._devs.items():
            if s == sc:
                self._call(self.gpib.timeout, ud, code)
        self._call(self.gpib.timeout, iface.board, code)

    def iotrigger(self, addr):
        sc, pad, sad = self.address(addr)
        if pad is None:
            self._t("ATN GET")
            self._cmd(sc, [GET])
        else:
            self._t("ATN UNL MTA LAD %s GET" % self._who(pad, sad))
            self._call(self.gpib.trigger, self._dev(sc, pad, sad))

    # ------------------------------------------------------------ extras (not in the 82990A)
    def scan(self, sc):
        """Primary addresses 0-30 where a listener answers (linux-gpib ibln)."""
        sc = self.address(sc, allow_dev=False)[0]
        b, me = self.ifaces[sc].board, self._my_pad(sc)
        found = []
        for pad in range(31):
            if pad != me and self._call(self.gpib.listener, b, pad):
                found.append(pad)
        return found

    def lines(self, sc):
        sc = self.address(sc, allow_dev=False)[0]
        v = int(self._call(self.gpib.lines, self.ifaces[sc].board))
        names = ["DAV", "NDAC", "NRFD", "IFC", "REN", "SRQ", "ATN", "EOI"]
        return [(n, None if not v & (1 << i) else bool(v & (0x100 << i))) for i, n in enumerate(names)]

    def settings(self, sc):
        sc = self.address(sc, allow_dev=False)[0]
        i = self.ifaces[sc]
        return {"board": i.board, "bus address": self._my_pad(sc), "timeout": i.timeout,
                "EOI": i.eoi, "EOL": i.eol, "MATCH": i.match if i.match_on else None,
                "last termination": i.term}

    def close(self):
        for ud in self._devs.values():
            try:
                self.gpib.close(ud)
            except Exception:
                pass
        self._devs.clear()


def show(data):
    """Printable form of bytes/str: control characters as <CR>, <LF>, <1B>..."""
    if isinstance(data, str):
        data = data.encode("latin-1", "replace")
    names = {13: "<CR>", 10: "<LF>", 9: "<TAB>", 0: "<NUL>"}
    out = []
    for c in bytearray(data):
        if 32 <= c < 127:
            out.append(chr(c))
        else:
            out.append(names.get(c, "<%02X>" % c))
    return '"' + "".join(out) + '"'


def bus_name(c, me=0):
    """Mnemonic for one bus command byte (as listed in Table 2-1)."""
    fixed = {GTL: "GTL", SDC: "SDC", PPC: "PPC", GET: "GET", 0x09: "TCT", LLO: "LLO",
             DCL: "DCL", PPU: "PPU", SPE: "SPE", SPD: "SPD", UNL: "UNL", UNT: "UNT", PPD: "PPD"}
    if c in fixed:
        return fixed[c]
    if 0x20 <= c < 0x3F:
        return "MLA" if c - 0x20 == me else "LAD%d" % (c - 0x20)
    if 0x40 <= c < 0x5F:
        return "MTA" if c - 0x40 == me else "TAD%d" % (c - 0x40)
    if 0x60 <= c < 0x80:
        return "SA%d/PPE" % (c - 0x60)
    return "%02X" % c
