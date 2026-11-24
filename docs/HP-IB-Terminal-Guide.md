# HP-IB Terminal (`hpib`)

pi-GPIBTerm v2.0.5

The HP-IB Terminal is an HP-IB programming environment for the Raspberry Pi with Lightside
Instruments' gpib4pi board (lsi-gpib4pi-2.x). Installation and hardware: `pi-GPIBTerm-Setup-Guide.md`.
It works like the **HP 82990A HP-IB Command Library for MS-DOS** used with interpreted BASIC. Its
manual, *HP-IB Command Library Reference* (part 82990-90001, June 1986), is online at the Internet
Archive: https://archive.org/details/hp-ib-command-library-reference. The terminal has:

- the same 26 commands (`IOOUTPUTS`, `IOENTER`, `IOSPOLL`, `IOTRIGGER` ...), with the same
  parameters, addressing (`7`, `723`, `72315`) and error numbers (`PCIB.ERR`, `ETIME` ...);
- a GW-BASIC style language with line numbers, `LIST`, `RUN`, `SAVE`, `LOAD`, so the programs in the
  manual can be typed in almost unchanged;
- extras for bench work: `ASK` (send and read in one go), `SCAN` (find instruments), `LINES` (bus
  line states), `TRACE ON` (show the bus activity of every command), and `HELP` for every command.

New to it? Start with `HP-IB-Terminal-Introduction.md`, a step-by-step first session.
This guide is the reference.

You can also run it **on the PC without any hardware**. It then talks to a simulated HP 3478A at
address 23, which is handy for learning and for trying programs out.

---

## 1. Start it

On the Pi, after `install.sh` (see `README.md`):

```bash
hp3478a                          # the menu: 1 = HP-IB Terminal, 2 = with the simulator
hpib                             # or directly: real bus, select code 7 = /dev/gpib0
hpib --sim                       # simulator, no meter needed
```

Started from the menu, or from `~/pi-gpibterm`, its files go into your folder: `SAVE "programs/name"`,
and backups written by `examples/3478a_calsave` go to `backups/`. `LOAD "examples/..."` finds the
installed examples from any folder.

Without a Pi, from the project folder on a PC with Python 3: `python pi/hpibterm.py --sim`
(on Windows: `.\pc\deploy.ps1 sim`). From a Windows PC with the Pi on the network,
`.\pc\deploy.ps1 term` installs the latest version on the Pi and opens the terminal there.

You see:

```
HP-IB Terminal 2.0.5 - HP 82990A HP-IB Command Library work-alike on linux-gpib
select code 7 = board 0
Type HELP for help, HELP LIBRARY for the commands, BYE to leave.
HP-IB>
```

Type `BYE` (or press Ctrl+D) to leave. The instruments are put back to front-panel (local) control.

## 2. First steps with the HP 3478A

The meter's address is 23, so its **device address is 723** (select code 7, address 23).

```
HP-IB> ASK 723, "H1"
"+1.23456E+0<CR><LF>"
```

`H1` tells the 3478A to take one DC volts reading. `ASK` sends the text and shows the reply.
Control characters are shown in angle brackets, so you can see exactly what came back.

The same thing with the library commands:

```
HP-IB> IOOUTPUTS 723, "F1RAN5T4"       ' DC volts, autorange, 5.5 digits, trigger hold
HP-IB> IOOUTPUTS 723, "T3"             ' take one reading
HP-IB> IOENTER 723                     ' read it as a number
1.23456
HP-IB> IOSPOLL 723                     ' serial poll: the status byte
0  (&H00, bits 7..0 = 00000000)
```

Text after `'` is a comment. Several statements can go on one line with `:`, and loops work
straight away:

```
HP-IB> FOR I = 1 TO 5: IOOUTPUTS 723, "T3": IOENTER 723, V: PRINT I, V: NEXT I
```

Other useful commands:

| Type this | What it does |
|-----------|--------------|
| `SCAN` | lists the addresses where an instrument answers |
| `TRACE ON` | shows the bus activity of each command (`ATN UNL MTA LAD 23 ...`); `TRACE OFF` stops it |
| `SHOW` | shows timeout, EOI, EOL and match settings, and the last error |
| `LINES` | shows the state of the bus lines (SRQ, REN, ATN, EOI ...) |
| `HELP IOENTERS` | the manual's description of a command (see section 3) |
| `HELP 3478A` | the meter's codes |

## 3. Getting help

HELP works like DEC VMS HELP. The topics form a tree:

```
HELP                                   the overview and the list of topics
HELP COMMAND                           all terminal commands, one line each
HELP COMMAND SAVE                      just SAVE
HELP LIBRARY IOENTERS                  one HP-IB library command
HELP LIBRARY IOENTERS BUS_ACTIVITY     a subtopic of it (also: ERRORS)
HELP STATEMENT FOR       HELP FUNCTION MID$       HELP ERRORS ETIME
```

- Names can be shortened as long as they're clear: `HELP COM SA` is `HELP COMMAND SAVE`.
- You can leave out the group: `HELP SAVE`, `HELP IOSPOLL`, `HELP MID$` find the entry by themselves.
- Wildcards: `HELP LIB IOENT*` shows IOENTER, IOENTERA and IOENTERS. `%` stands for one character.
- After the text, HELP asks `Topic?` or, deeper down, something like `LIBRARY IOSPOLL Subtopic?`.
  The prompt always shows where you are. At the prompt:

  | Type | What happens |
  |------|--------------|
  | a name | looks it up, from where you are; if it isn't there, from the top (so `SAVE` works anywhere) |
  | `?` | shows the current text again |
  | Enter | goes up one level; Enter at `Topic?` leaves HELP |
  | `TOP` (or `^`) | jumps straight back to the top level and lists the main topics |
  | Ctrl+C | leaves HELP at once, back to `HP-IB>` |
- `HELP/NOPROMPT SAVE` shows the text without asking.

The groups are LIBRARY (the 26 HP-IB commands), COMMAND (terminal commands), STATEMENT (BASIC
statements), FUNCTION, ERRORS (each error code), and the topics ADDRESS, BASIC, 3478A, EXAMPLES,
KEYS and DIFFERENCES.

## 4. Writing programs

Type a line with a number in front and it is stored instead of run:

```
HP-IB> 10 DVM = 723
HP-IB> 20 CALL IOOUTPUTS(DVM, "F1RAN5T4")
HP-IB> 30 FOR I = 1 TO 10
HP-IB> 40 CALL IOOUTPUTS(DVM, "T3")
HP-IB> 50 CALL IOENTER(DVM, V)
HP-IB> 60 PRINT I, V
HP-IB> 70 NEXT I
HP-IB> 80 CALL IOLOCAL(DVM)
HP-IB> RUN
```

| Command | What it does |
|---------|--------------|
| `LIST` / `LIST 20-50` | show the program |
| `RUN` | run it; **Ctrl+C** stops it, `CONT` carries on |
| `EDIT 40` | puts line 40 on the input line so you can change it with the arrow keys |
| `40` | (just the number) deletes line 40 |
| `DELETE 20-50` | deletes a range of lines |
| `AUTO` | numbers new lines for you; an empty line stops it |
| `RENUM` | renumbers 10, 20, 30 ... and fixes the `GOTO`/`GOSUB` targets |
| `SAVE "myprog"` / `LOAD "myprog"` | save/load `myprog.bas` (a plain text file) |
| `FILES` | lists the `.bas` files |
| `NEW` | clears the program |

Up/Down arrows recall earlier lines and Tab completes command names (on the Pi).

Run a program without the prompt, for example from cron:

```bash
hpib examples/bus_tour.bas --run
hpib -c 'ASK 723, "H1"'
```

The exit code is 1 if the program stopped with an error.

## 5. Example programs

`LOAD "examples/name"`, then `LIST` and `RUN`. `FILES examples` lists them all, and menu item 3
runs them. The general examples are in `examples/`:

| File | What it shows |
|------|---------------|
| `bus_tour.bas` | a tour of the library commands; type `TRACE ON` first |
| `error_handler.bas` | error handling exactly as in the manual's SETUP.BAS |
| `manual_example.bas` | the manual's example (HP 3325A + HP 3456A). It needs those instruments |

The HP 3478A module adds these (`instruments/hp3478a/examples/`, found the same way):

| File | What it shows |
|------|---------------|
| `3478a_read.bas` | 10 readings with single triggers; over-range is shown as OVERLOAD |
| `3478a_log.bas` | asks for function, count and interval, and logs readings to a CSV file |
| `3478a_srq.bas` | the meter asks for service when a reading is ready: `IOSTATUS` + `IOSPOLL` |
| `3478a_calsave.bas` | saves the calibration RAM (read only), in the same files as `hp3478a-cal backup` |

## 6. Addresses

| You write | Means |
|-----------|-------|
| `7` | the interface itself (select code 7 = the gpib4pi, linux-gpib board 0) |
| `723` | select code 7, instrument address 23 |
| `72315` | select code 7, address 23, secondary address 15 |

Some commands take only the select code (`IOTIMEOUT 7, 5`, `IOEOI 7, 0`, `IOABORT 7`),
`IOSPOLL` needs a device address, and most take either. For example, `IOCLEAR 723` clears one
instrument, `IOCLEAR 7` clears all of them.

## 7. Errors

A library error stops the program with a message such as:

```
HP-IB error 100004 (ETIME): HPIB: timeout - no device is listening at that address - check power, cable and address in 50
```

If the program has `ON ERROR GOTO`, it goes there instead (`ERR` = 255, `ERL` = the line).
To get the original library's behaviour, put `OPTION ERRORS CONTINUE` in the program. It then
carries on and you check `PCIB.ERR` yourself, as the manual does:

```
110 CALL IOCLEAR(DVM)
120 IF PCIB.ERR <> NOERR THEN ERROR PCIB.BASERR
```

| Number | Name | Meaning |
|--------|------|---------|
| 100001 | EUNKNOWN | unknown error |
| 100002 | ESEL | wrong select code or device address |
| 100003 | ERANGE | a value is out of range |
| 100004 | ETIME | timeout: the instrument did not answer (off, wrong address, or nothing to send) |
| 100005 | ECTRL | the interface is not the controller |
| 100006 | EPASS | pass control not allowed |
| 100007 | ENUM | no number in the reply (`IOENTER`) |
| 100008 | EADDR | select code used but the bus was not addressed (`IOSEND` first) |

The timeout starts at 10 seconds. Change it with `IOTIMEOUT 7, 2` (seconds).
`IORESET` sets it to 0, as the original did. 0 means "wait forever", so set it again afterwards.

## 8. Differences from the original

- Values can be written directly: `CALL IOCLEAR(723)`. The original needed variables.
- Trailing length parameters can be left out (`IOOUTPUTS 723, "F1"`). Leave out the result
  variable of `IOENTER`, `IOENTERS`, `IOSPOLL`, `IOSTATUS` ... and the result is printed.
- `IODMA` is accepted but does nothing (linux-gpib decides about DMA itself).
- REN (Remote Enable) is set when the terminal starts, so instruments obey commands at once.
  `IOLOCAL 7` clears it: instruments then **ignore their commands but still answer reads**,
  so you get readings back whatever you send. `IOREMOTE 7` sets it again. `BYE` clears it,
  which returns every instrument to front-panel control.
- Keywords need spaces around them: `FOR I = 1 TO 10`, not `FORI=1TO10`.
- No `DEF FN`, `PRINT USING`, graphics or sound. SETUP.BAS lines (`DEF SEG`, `BLOAD`, `COMMON`,
  `CALL DEFERR`, `IOCLEAR = PCIB.BASE + ...`) are accepted and ignored, so old programs load.

`HELP DIFFERENCES` in the terminal has the full list.

## 9. Files

In the project (installed on the Pi in `/opt/pi-gpibterm`):

```
pi/hpibterm.py     the terminal (the command hpib)
pi/hpiblib.py      the 26 library commands on top of linux-gpib
pi/hpibbasic.py    the BASIC interpreter
pi/hpibhelp.py     HELP texts
pi/hpib_sim.py     simulated bus with an HP 3478A (--sim)
pi/gpibterm_menu.py the menu (the command pi-gpibterm)
pi/instruments/    instrument modules (hp3478a: tools and examples for the HP 3478A)
pi/examples/       example programs
```

Tests (PC, no hardware): `python dev\run_tests.py`. The terminal is tested against the
simulator, plus a readline test on Debian (Python 3.11).

On the real hardware (gpib4pi on the Pi, HP 3478A at 723), this has been confirmed
(November 2026):
- `IOOUTPUTS 723, "F1RAN5T4"`, `IOOUTPUTS 723, "T3"` and `IOENTER 723`, which returned a DC
  volts reading.
- `IOREMOTE`, `IOCLEAR`, `IOTIMEOUT`, `IOEOL`, `IOENTERS`, `ASK`, `TRACE ON` and `LOAD`/`RUN`.
- `examples/3478a_calsave.bas`: all 256 calibration nibbles read twice and matched, all 16
  used entries had valid checksums, and the three backup files were saved.

SRQ, the other examples and `hp3478a-cal` (verify, restore) have so far been tried only on the
simulator. Parallel poll (`IOPPOLL`) works only in the simulator: the gpib4pi's `gpib_bitbang`
driver doesn't support it (Setup Guide, "What to expect from the gpib4pi").

## Credits

This project builds on the gpib4pi board and guide by Lightside Instruments, the linux-gpib
driver (including the `gpib_bitbang` driver by Thomas Klima and Marcello Carla'), HP's *HP-IB
Command Library* manual (1986), and the HP 3478A calibration research of Tom Verbeure,
PyMeasure, Patrick Baus and Vinay Shanbhag. `THIRD-PARTY-NOTICES.md` says what came from each,
and the licenses.

pi-GPIBTerm itself is free software under the GNU General Public License version 3
(`GPL-3.0-only`); see `LICENSE`.
