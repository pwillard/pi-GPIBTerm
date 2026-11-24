# HP 3478A Module Guide

pi-GPIBTerm v2.0.7

The HP 3478A module is the part of pi-GPIBTerm made for the HP 3478A multimeter. The rest of
pi-GPIBTerm works with any GPIB instrument (`pi-GPIBTerm-Setup-Guide.md`). The module adds:

- section **H** in the menu (`pi-gpibterm`): readings, calibration RAM backup, verify, show and
  restore, and the meter's address
- the commands `hp3478a-log` (readings, CSV) and `hp3478a-cal` (calibration RAM)
- HP-IB Terminal programs: `3478a_read`, `3478a_log`, `3478a_srq` and `3478a_calsave`
  (`LOAD "examples/3478a_read"`, or menu item 3)

The meter's factory GPIB address is 23 (device address 723). If yours differs, set it in the
module's menu (`A`), or give `-a N` to the commands. It is stored in
`~/pi-gpibterm/pi-gpibterm.conf` as `HP3478A_ADDRESS`. The module's files are in
`pi/instruments/hp3478a/` (installed in `/opt/pi-gpibterm/instruments/hp3478a/`).

---

## 1. Talk to the HP 3478A

The 3478A is **pre-SCPI**: it does not understand `*IDN?`, `MEAS:...` or `READ?`.
It uses short codes, which can be chained in one string (e.g. `F1RAZ1N5T1`).

### Command summary

| Code | Meaning |
|------|---------|
| `F1`..`F7` | Function: F1 DC V, F2 AC V, F3 2-wire ohms, F4 4-wire ohms, F5 DC A, F6 AC A, F7 extended ohms |
| `RA` | Autorange |
| `R-2`..`R7` | Fixed range (see table below) |
| `N3` / `N4` / `N5` | 3.5 / 4.5 / 5.5 digits |
| `Z0` / `Z1` | Autozero off / on |
| `T1` | Internal trigger (free running) |
| `T2` | External trigger |
| `T3` | Single trigger (take one reading now) |
| `T4` | Trigger hold |
| `T5` | Fast trigger |
| `H0`..`H7` | Home/preset: H0 = DCV, autorange, 4.5 digits, autozero, hold. H1..H7 = preset + single reading of F1..F7 |
| `D1` | Normal display |
| `D2text` | Show text on the display |
| `D3text` | Show text and stop display updates |
| `S` | Returns 1 if FRONT input terminals selected, 0 if REAR |
| `B` | Returns 5 binary status bytes |
| `E` | Returns error register |
| `K` | Clear serial poll register |

Range codes (each range is 3 x 10^n):

| Code | DC V | AC V | Ohms | DC/AC A |
|------|------|------|------|---------|
| `R-2` | 30 mV | - | - | - |
| `R-1` | 300 mV | 300 mV | - | 300 mA |
| `R0` | 3 V | 3 V | - | 3 A |
| `R1` | 30 V | 30 V | 30 ohm | - |
| `R2` | 300 V | 300 V | 300 ohm | - |
| `R3`..`R7` | - | - | 3 k .. 30 M ohm | - |

Readings come back as text like `+1.23456E+0`. Over range is returned as `+9.99999E+9`.

**Check the FRONT/REAR switch** on the meter. The leads must be on the terminals it selects.

### Quick interactive test

```bash
sudo ibterm -d 23
```

Type `H1` and press Enter. The meter takes one DC volts reading and ibterm shows it.
(Typing `*IDN?` gives nothing or a syntax error. That is normal for this meter.)

### Minimal Python

```python
import gpib
dmm = gpib.dev(0, 23)                  # board 0, address 23
gpib.write(dmm, "F1RAZ1N5T3\r\n")      # DC volts, autorange, autozero, 5.5 digits, one reading
print(float(gpib.read(dmm, 64)))
gpib.write(dmm, "D2HELLO\r\n")         # text on the display
gpib.write(dmm, "D1\r\n")              # normal display
gpib.ibloc(dmm)                        # back to front-panel control
```

### Logger script: `hp3478a_log.py`

The command is `hp3478a-log` (the program is `pi/instruments/hp3478a/hp3478a_log.py`). Module menu item 1 asks the questions
for you and saves the readings in `~/pi-gpibterm/logs`.

```bash
hp3478a-log                              # 10 DC volt readings, address 23
hp3478a-log -f ohm2 -n 0 -i 1            # 2-wire ohms every 1 s until Ctrl+C
hp3478a-log -f dcv -r 1 -n 100 --csv log.csv   # 30 V range, 100 readings to CSV
```

Options:

| Option | Meaning | Default |
|--------|---------|---------|
| `-a` | GPIB address | 23 |
| `-f` | `dcv`, `acv`, `ohm2`, `ohm4`, `dca`, `aca`, `ohmx` | dcv |
| `-r` | Range: `A` = auto, or a code -2..7 | A |
| `-d` | Digits: 3, 4 or 5 | 5 |
| `-n` | Number of readings, 0 = until Ctrl+C | 10 |
| `-i` | Seconds between readings | 0.5 |
| `--csv` | Append readings to a CSV file | off |

When it finishes, the script puts the meter back into free-running mode and front-panel control.
Over-range readings are shown as OVERLOAD and left blank in the CSV.

### HP-IB Terminal: `hpib`

An interactive HP-IB programming environment. It has the commands of the HP 82990A HP-IB
Command Library (`IOOUTPUTS`, `IOENTER`, `IOSPOLL` ...) and a BASIC with line numbers, so you can
type commands one at a time or write, save and run programs. Start with
`HP-IB-Terminal-Introduction.md`; the reference is `HP-IB-Terminal-Guide.md`.

```bash
hpib                                   # or menu item 1
HP-IB> ASK 723, "H1"                  # one DC volts reading
HP-IB> HELP
```

## 2. Back up and restore the calibration RAM (battery replacement)

The 3478A stores its calibration constants in a 256 x 4-bit SRAM (U512). An internal 3 V lithium
battery (BT701) keeps it powered when the meter is unplugged. If the battery dies or is removed
with no other power, **the calibration is lost**. The display then shows `CAL` on the affected ranges,
and the readings are wrong.

This was cross-checked against Tom Verbeure's scripts and write-up:
- https://github.com/tomverbeure/hp3478a_calibration
- https://tomverbeure.github.io/2022/12/02/HP3478A-Multimeter-Calibration-Data-Backup-and-Battery-Replacement.html

It was also checked against the pymeasure HP3478A driver, pyAsyncHP3478A, and
https://github.com/vinayshanbhag/hp3478a. This tool decodes Vinay's sample dump to the same
offset/gain values his README lists.

| Command | Action |
|---------|--------|
| `W` + raw address byte | Meter returns 1 character: 64 + the stored nibble (`@`..`O`) |
| `X` + raw address byte + nibble | Stores the low 4 bits. Works **only** with the front-panel CAL ENABLE switch on |
| `B` | 5 status bytes. Byte 2, bit 5 = CAL RAM write enabled. This is how the script checks the switch |

Memory layout:
- **Address 0:** a read/write check nibble the meter uses to test write protection. It isn't calibration data, and restore doesn't write it.
  The sources disagree on what its value means for the CAL switch, so the script reads the switch from the `B` status byte instead.
- **Addresses 1-247:** 19 entries of 13 nibbles each: a 6-nibble offset, a 5-nibble gain, and a 2-nibble checksum.
  For each entry, the sum of the 11 data nibbles plus the 8-bit checksum must equal 255. Entries 5, 16 and 18 are unused.
- **Addresses 248-255:** not used.

With CAL ENABLE off, the switch hard-wires the SRAM to read-only. That means backup and verify **can't** change
the calibration.

### Files written by `backup`

| File | Format |
|------|--------|
| `calram_<date>.txt` | 16 lines of 16 characters `@`..`O` (same as pyAsyncHP3478A) |
| `calram_<date>.bin` | 256 raw nibble values 0-15 (same as Tom's `hp3478a_cal_data.bin`) |
| `calram_<date>.info.txt` | Human-readable decode: offset, gain and checksum for each range |

`verify`, `restore` and `decode` accept any of these formats:
- the `.txt` or `.bin` written by this tool
- a `.bin` made by Tom's script (raw values 0-15)
- a dump made by Vinay's `hp3478a_cal_ram_util.py` (256 raw `@`..`O` bytes)

### Commands (module menu items 2-5, or on the Pi in `~/pi-gpibterm/backups`)

```bash
cd ~/pi-gpibterm/backups
hp3478a-cal backup                 # .txt + .bin + .info.txt
hp3478a-cal verify  calram_X.txt   # does the meter still match the backup?
hp3478a-cal restore calram_X.txt   # write it back (CAL ENABLE on)
hp3478a-cal decode  calram_X.bin   # show a file's contents, no meter needed
```

Add `-a <address>` if the meter isn't at 23.

Safety features (beyond Tom's scripts, which write without checking):
- **backup** reads the RAM twice and only saves if both reads match. It never overwrites a file and
  checks every entry's checksum.
- **restore** refuses a file with bad checksums and checks the CAL ENABLE status bit. After you type `YES`,
  it saves the meter's current RAM to `calram_before_restore_<date>.txt`. It then writes each nibble,
  reads it back (retrying up to 3 times), and verifies the whole RAM at the end.

### Saving from the HP-IB Terminal

The HP-IB Terminal has a BASIC program that does the same backup: `examples/3478a_calsave.bas`.
It reads twice, checks the checksums, and writes the same `.txt`, `.bin` and `.info.txt` files into
`~/pi-gpibterm/backups`, so `verify`, `restore` and `deploy.ps1 pull` work with them. It only reads, so
restoring is still done with `hp3478a-cal restore`.

```bash
pi-gpibterm                    # menu item 3, then 3478a_calsave
hpib examples/3478a_calsave.bas --run     # the same, from ~/pi-gpibterm
```

### Battery replacement procedure

The replacement is a 3 V lithium cell with solder pins, e.g. Panasonic **BR-2/3AE5SPN** (Digikey).
It's soldered onto the PCB, not in a socket.

1. **Before touching anything:** let the meter warm up, then run module menu item 2 (backup) and item 3
   (verify). From the PC, use `.\pc\deploy.ps1 backup` and `.\pc\deploy.ps1 verify -File calram_....txt`.
   Check the `.info.txt` says "all used entries valid".
2. Copy the backup files from `~/pi-gpibterm/backups` to the PC (`.\pc\deploy.ps1 pull` does it), and keep a
   second copy somewhere else, e.g. a USB stick.
3. **Unplug the meter's power cable**, then desolder the old battery and solder in the new one.
   Tom found the calibration survived the swap without a restore. A capacitor (C510) seems to hold the
   SRAM long enough, but don't count on it.
   - Don't swap the battery with the meter powered. That means working near live mains, and an earthed
     soldering iron can short things. Tom's advice is "just don't do it".
   - Another option is a temporary 3 V supply (2 x AA) with its own diode, soldered across during the swap.
     That's mainly for people without GPIB. You have GPIB, so backup and restore is simpler.
   - While it's open: Tom also recommends replacing the **RIFA mains-filter capacitors**. They're a known
     fire risk even with the meter switched off but plugged in.
4. Plug in, power up, and run `verify` against your backup.
   - **MATCH:** done.
   - **DIFFERENT**, or `CAL` showing on the display: continue to step 5.
5. Set the front-panel **CAL ENABLE** switch on, then run module menu item 5 (restore), or
   `.\pc\deploy.ps1 restore -File calram_....txt` from the PC.
6. Set CAL ENABLE back off (slot horizontal), power-cycle the meter, and run `verify` again.
   Then check readings against a known voltage and resistance.

Make a fresh `backup` from time to time, and always before opening the meter.

## 3. If something doesn't work

- **Timeouts:** check the rear-panel address switches (the meter reads them at power-on), and the
  address in the module's menu.
- **SRQ / ERR annunciator on the meter:** usually a syntax error, e.g. a SCPI command like `*IDN?`
  was sent. Send `K` to clear it, or press LOCAL.
- **Readings near zero / wrong:** check the FRONT/REAR terminal switch.
- **The meter keeps sending readings after `T4`, or the calibration backup says
  `Unexpected reply "+"` (or `"-"`):** the meter is in local (RMT annunciator off), because the bus's
  REN line is off. Type `IOREMOTE 7` in the HP-IB Terminal. The module's tools and examples set it
  themselves.
- Bus and driver problems: section 5 of `pi-GPIBTerm-Setup-Guide.md`.

## Credits

The calibration tools follow and cross-check the HP 3478A calibration research of Tom Verbeure,
PyMeasure, Patrick Baus and Vinay Shanbhag. `THIRD-PARTY-NOTICES.md` (section 4) says what came
from each, and the licenses. The module is part of pi-GPIBTerm, free software under the GNU
General Public License version 3 (`GPL-3.0-only`); see `LICENSE`.
