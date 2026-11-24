# Introduction to the HP-IB Terminal

pi-GPIBTerm v2.0.6

This is a step-by-step introduction. You don't need to know BASIC or HP-IB to follow it: type the
examples and you'll see the same results. When you want the details, see
`HP-IB-Terminal-Guide.md` (the reference), or type `HELP` in the terminal.

---

## 1. What is it?

**HP-IB** is the instrument bus Hewlett-Packard designed in the 1960s and 70s. It's also called
**GPIB** or **IEEE-488**. Many bench instruments of that era have it: meters, power supplies,
signal generators, counters. With the bus, a computer can set an instrument up, trigger it and read
its results.

In 1985-86 HP sold the **HP-IB Command Library** (the HP 82990A) for PCs. It gave BASIC
programs a set of commands with names like `IOOUTPUTS` (send text to an instrument) and `IOENTER`
(read a number from one). Its manual, the *HP-IB Command Library Reference*, can be read or
downloaded at the Internet Archive: https://archive.org/details/hp-ib-command-library-reference

The **HP-IB Terminal** brings that back on a Raspberry Pi with a gpib4pi board:

- The same commands, used the same way as in the manual.
- A built-in BASIC, so you can type commands one at a time or write small programs, save them
  and run them again.
- Help for everything, typed right at the prompt.
- A practice mode that simulates an HP 3478A multimeter, so you can learn on the PC with no
  hardware at all.

## 2. What you need

| To practise (simulator) | To use your real meter |
|-------------------------|------------------------|
| The Pi with pi-GPIBTerm installed, or a PC with Python 3 | A Raspberry Pi with Lightside's gpib4pi board (lsi-gpib4pi-2.x) and pi-GPIBTerm installed (`README.md`, or section 0 of `pi-GPIBTerm-Setup-Guide.md`) |
| | The HP 3478A switched on, at its usual address 23 |

The terminal works with any GPIB instrument. This introduction uses an HP 3478A multimeter at
address 23 (device 723) as its example, because that is what the simulator has. With another
instrument, use its address and its own commands. Everything in this introduction works in the simulator. The simulated meter gives readings near
1.23456 volts, so your numbers will be slightly different each time, just like a real meter's.

## 3. Starting and stopping

On the Pi, type `hp3478a` for the menu and choose **1** (real meter) or **2** (simulator). Or
start it directly:

```bash
hpib            # use the real meter
hpib --sim      # practise with the simulated meter
```

With no Pi at all, you can practise on a PC with Python 3, from the project folder:
`python pi/hpibterm.py --sim`. On Windows, `.\pc\deploy.ps1 sim` does the same.

You'll see:

```
HP-IB Terminal 2.0.6 - HP 82990A HP-IB Command Library work-alike on linux-gpib
select code 7 = board 0   [SIMULATOR: HP 3478A at address 723]
Type HELP for help, HELP LIBRARY for the commands, BYE to leave.
HP-IB>
```

`HP-IB>` is the prompt: the terminal is waiting for you. Type something and press Enter.

To leave, type `BYE`. On the way out the meter is put back to front-panel control, so its
buttons work again.

## 4. Your first commands

Start with something that doesn't need an instrument at all:

```
HP-IB> PRINT 2 + 2
 4
```

`PRINT` shows the result of whatever you give it. (BASIC prints a space in front of positive
numbers; that's normal.)

Now find out what's on the bus:

```
HP-IB> SCAN
Listeners found: 23 (address 723)
```

There's one instrument, at bus address 23. You'll talk to it as **723**. That's because the
commands from the manual put the interface number in front of the instrument address: the gpib4pi
is interface **7**, so the instrument at address 23 is **7**23. You'll use 723 everywhere from now on.

Ask the meter for a reading:

```
HP-IB> ASK 723, "H1"
"+1.23457E+0<CR><LF>"
```

`ASK` sends some text to the instrument, then shows what it sends back. `H1` is the 3478A's code
for "take one DC volts reading". The answer `+1.23457E+0` means 1.23457 x 10^0, which is
1.23457 volts. `<CR><LF>` are the two invisible end-of-line characters the meter sends after every
reading. The terminal shows them so you can see exactly what arrived.

## 5. Talking to the meter with the library commands

`ASK` is a handy shortcut. The real work is done with the library commands, and they're worth
getting to know, because every program uses them. The two you'll use most:

| Command | What it does |
|---------|--------------|
| `IOOUTPUTS 723, "text"` | send text (instrument codes) to the instrument |
| `IOENTER 723` | read one number back from it |

Set the meter up, trigger one reading, and read it:

```
HP-IB> IOOUTPUTS 723, "F1RAN5T4"
HP-IB> IOOUTPUTS 723, "T3"
HP-IB> IOENTER 723
1.23457
```

The first line is a string of 3478A codes, one after the other:

| Code | Meaning |
|------|---------|
| `F1` | function 1 = DC volts |
| `RA` | range: automatic |
| `N5` | 5.5 digits |
| `T4` | trigger hold: wait until told to measure |

`T3` then says "measure once, now", and `IOENTER` reads the result as a number. Commands that
only send something print nothing when they work. (`HELP 3478A` lists all the meter's codes.)

Instead of printing the reading, you can keep it in a **variable**, and use it:

```
HP-IB> IOOUTPUTS 723, "T3": IOENTER 723, V: PRINT "The meter reads"; V; "volts"
The meter reads 1.23457 volts
```

Two new things here:

- `IOENTER 723, V` puts the reading into a variable called `V` instead of printing it.
- The `:` lets you put several commands on one line. They run left to right.

You can even repeat something on one line:

```
HP-IB> FOR I = 1 TO 3: IOOUTPUTS 723, "T3": IOENTER 723, V: PRINT I, V: NEXT I
 1             1.23457
 2             1.23456
 3             1.23457
```

`FOR I = 1 TO 3 ... NEXT I` runs the commands in between three times, with `I` counting 1, 2, 3.

Try a fun one on the real meter. It shows text on the meter's display (up to 12 characters),
and `D1` puts the normal display back:

```
HP-IB> IOOUTPUTS 723, "D2HELLO"
HP-IB> IOOUTPUTS 723, "D1"
```

## 6. Your first program

Typing the same line again and again gets old. A **program** is a list of lines that the terminal
remembers and runs whenever you ask. You make one by putting a **line number** in front of each
line. A numbered line is stored, not run:

```
HP-IB> 10 REM My first program
HP-IB> 20 DVM = 723
HP-IB> 30 IOOUTPUTS DVM, "F1RAN5T4"
HP-IB> 40 FOR I = 1 TO 5
HP-IB> 50 IOOUTPUTS DVM, "T3"
HP-IB> 60 IOENTER DVM, V
HP-IB> 70 PRINT "Reading"; I; "="; V
HP-IB> 80 NEXT I
HP-IB> 90 IOLOCAL DVM
```

- `REM` is a remark: a note for people, ignored by the computer.
- `DVM = 723` keeps the meter's address in a variable called `DVM` (digital voltmeter). If the
  meter ever moves to another address, you change one line.
- `IOLOCAL` puts the meter back to front-panel control at the end.

`LIST` shows the program and `RUN` runs it:

```
HP-IB> RUN
Reading 1 = 1.23457
Reading 2 = 1.23456
Reading 3 = 1.23457
Reading 4 = 1.23456
Reading 5 = 1.23455
```

### Changing a program

- **Replace a line:** type it again with the same number. To add "V" after each reading:

  ```
  HP-IB> 70 PRINT "Reading"; I; "="; V; "V"
  ```

- **Insert a line:** use a number in between. That's why lines are numbered in tens:

  ```
  HP-IB> 35 PRINT "Taking 5 readings..."
  ```

- **Delete a line:** type just its number, e.g. `35`.
- **Edit a line in place:** `EDIT 70` puts line 70 on the input line. Move with the arrow keys,
  change it, press Enter.
- **Tidy the numbers:** `RENUM` renumbers everything 10, 20, 30 ... and fixes any `GOTO`s.

`LIST` and `RUN` again:

```
HP-IB> RUN
Taking 5 readings...
Reading 1 = 1.23457 V
Reading 2 = 1.23457 V
...
```

### Saving and loading

```
HP-IB> SAVE "first"
Saved 10 line(s) to first.bas
HP-IB> NEW
HP-IB> LOAD "first"
Loaded first.bas (10 lines)
```

`SAVE` writes the program to `first.bas`, a plain text file you can also open in Notepad.
`NEW` clears the program from memory (save first!). `LOAD` brings it back. `FILES` lists your
saved programs. Started from the menu (or from `~/pi-gpibterm`), `SAVE "programs/name"` keeps them in
`~/pi-gpibterm/programs`, and menu item 3 lists them.

To **stop** a program that is running, press **Ctrl+C**. `CONT` carries on from where it stopped.

## 7. Something useful: logging readings to a file

The folder `examples` has ready-made programs. Load the logger and look at it:

```
HP-IB> LOAD "examples/3478a_log"
HP-IB> LIST
```

It asks a few questions, then takes readings and adds each one, with the date and time, to a CSV
file that Excel can open:

```
HP-IB> RUN
Function (1=DCV 2=ACV 3=2W ohm 4=4W ohm 5=DCA 6=ACA)? 1
Number of readings (0 = until Ctrl+C)? 3
Seconds between readings? 1
CSV file name (Enter = readings.csv): bench.csv
11-23-2026 09:23:11         1.23457
11-23-2026 09:23:12         1.23458
11-23-2026 09:23:13         1.23454
 3 reading(s) added to bench.csv
```

Reading the listing is a good way to learn: the program uses `INPUT` to ask questions,
`OPEN ... FOR APPEND` and `PRINT #1` to write the file, and `WHILE ... WEND` to repeat. Each of
these has its own help entry, e.g. `HELP OPEN`.

The other examples:

| Program | What it shows |
|---------|---------------|
| `3478a_read` | readings with single triggers; over-range shown as OVERLOAD |
| `3478a_srq` | the meter signals "reading ready" by itself (service request, serial poll) |
| `3478a_calsave` | saves the meter's calibration memory to files (see below) |
| `error_handler` | catching errors the way the 1986 manual does |
| `bus_tour` | one of each library command. Type `TRACE ON` first to watch the bus |
| `manual_example` | the example program from the manual (needs an HP 3325A and HP 3456A) |

### Saving the meter's calibration

The 3478A keeps its calibration in a small memory that a battery keeps alive. If the battery
goes flat, the calibration is lost. `3478a_calsave` reads that memory and saves it to files, so it
can be put back later:

```
HP-IB> RUN "examples/3478a_calsave"
Reading calibration RAM (pass 1)...
  read 64 of 256
  ...
Reading calibration RAM (pass 2, check)...

Address 0 (r/w check nibble): 0
#   range              offset        gain  checksum
0   30 mV DC              116    1.000983  ok
1   300 mV DC               5    1.000694  ok
...
18  (unused)                0    1.000000  ok
Result: all used entries valid

Saved and checked: backups/calram_20261123_103426.txt
                   backups/calram_20261123_103426.bin
                   backups/calram_20261123_103426.info.txt
```

It only **reads** the meter and never changes it. The memory is read twice, and the files are only
written if both reads are the same. The files are the same as those of `hp3478a-cal backup`
(menu item 5), so that tool can `verify` the meter against them, or `restore` them after a
battery change (see section 2 of `HP3478A-Module-Guide.md`). Copy them off the Pi.
From a Windows PC with this project, `.\pc\deploy.ps1 pull` does it. The program is also a good example of a longer BASIC program,
with subroutines, error handling and files. `LIST` it and read it.

## 8. When something goes wrong

### Error messages

If an instrument doesn't answer, you get an HP-IB error:

```
HP-IB> IOENTER 705
HP-IB error 100004 (ETIME): HPIB: timeout - ...
```

There's nothing at address 5, so the terminal waited, gave up, and said so. The number and the
name (`ETIME`) come from the original manual, so you can look them up there or with
`HELP ERRORS ETIME`. In a program, the message also tells you the line number.

Mistakes in BASIC give BASIC errors, also with the line number:

```
HP-IB> RUN
NEXT without FOR in 40
```

Here line 40 said `NEXT J`, but the loop was `FOR I`. Use `EDIT 40` to fix it.

### Checklist when an instrument won't answer

1. Is it switched on? Is the cable (or the gpib4pi) firmly in?
2. `SCAN`: does its address show up? If it shows a different address, use that one.
3. The 3478A, like many HP instruments of its age, reads its address switches only when it is
   switched on. After changing the switches, turn it off and on again.
4. Some instruments only answer after you've asked them something. Send a code first, then read.
5. `IOCLEAR 723` resets the instrument's bus interface, which clears a confused state.

### Seeing what happens on the bus

`TRACE ON` makes every command show what it does on the bus, in the words of the manual:

```
HP-IB> TRACE ON
HP-IB> IOCLEAR 723
    [bus] ATN UNL MTA LAD 23 SDC
HP-IB> TRACE OFF
```

That line reads: attention, unlisten everyone, the Pi is the talker, instrument 23 listen,
"selected device clear". You don't need to understand it to use the terminal, but it's a great way
to learn how HP-IB works. Try it with `bus_tour`.

## 9. Getting help

Help is built in and works like the old DEC VMS HELP:

```
HP-IB> HELP                         the overview
HP-IB> HELP COMMAND                 all the terminal commands (RUN, LIST, SAVE ...)
HP-IB> HELP COMMAND SAVE            just SAVE
HP-IB> HELP SAVE                    the same: HELP finds it by itself
HP-IB> HELP LIBRARY                 all 26 HP-IB library commands
HP-IB> HELP IOENTER                 one of them
```

You can shorten names (`HELP COM SA`). After the text, help keeps asking for more, and the
prompt shows where you are, for example `LIBRARY IOSPOLL Subtopic?`. From there:

- type another name to look it up (any name works, wherever you are);
- press **Enter** to go up one level;
- type **TOP** to jump straight back to the top level;
- press **Ctrl+C** to leave help and get back to `HP-IB>`.

There are four groups: **LIBRARY** (talking to instruments), **COMMAND** (working with
programs), **STATEMENT** (BASIC: PRINT, FOR, IF ...) and **FUNCTION** (LEN, MID$, TIMER ...).
`HELP 3478A` lists the meter's codes.

## 10. Where to go next

- Load each example, `LIST` it, `RUN` it, change it, and run it again.
- `HELP LIBRARY` and try the commands one at a time with `TRACE ON`.
- `HP-IB-Terminal-Guide.md` is the full reference: addressing, error handling, running programs
  without the prompt (for example on a timer), and the differences from the original.
- Chapter 2 of HP's *HP-IB Command Library Reference* (https://archive.org/details/hp-ib-command-library-reference) is HP's own
  description of every command. Programs written for it run here with few or no changes.

## 11. Credits

This project builds on the gpib4pi board and guide by Lightside Instruments, the linux-gpib
driver (including the `gpib_bitbang` driver by Thomas Klima and Marcello Carla'), HP's *HP-IB
Command Library* manual (1986), and the HP 3478A calibration research of Tom Verbeure,
PyMeasure, Patrick Baus and Vinay Shanbhag. `THIRD-PARTY-NOTICES.md` says what came from each,
and the licenses.

pi-GPIBTerm itself is free software under the GNU General Public License version 3
(`GPL-3.0-only`); see `LICENSE`.

---

## Quick reference card

```
Start / stop      hp3478a (menu)   hpib   hpib --sim   BYE
The meter         address 723      ASK 723, "H1"      SCAN
Send / read       IOOUTPUTS 723, "codes"       IOENTER 723, V       IOENTERS 723, A$
Reset / local     IOCLEAR 723                  IOLOCAL 723
3478A codes       F1 DCV  F2 ACV  F3 ohm  F5 DCA   RA autorange   N5 5.5 digits
                  T3 one reading   T4 hold   T1 free run   D2text display   D1 normal
Programs          10 PRINT "HI"   LIST   RUN   EDIT 10   10 (delete)   RENUM   NEW
Files             SAVE "name"   LOAD "name"   FILES   LOAD "examples/3478a_read"
BASIC             V = 5   A$ = "TEXT"   PRINT V; A$   INPUT "Value"; V
                  FOR I = 1 TO 10 ... NEXT I   IF V > 2 THEN PRINT "HIGH"   GOTO 100
Stop a program    Ctrl+C   (CONT to carry on)
Trouble           SCAN   TRACE ON   IOCLEAR 723   HELP ERRORS
Help              HELP   HELP COMMAND SAVE   HELP IOENTER   HELP 3478A
In HELP           Enter = up one level   TOP = top level   ? = repeat   Ctrl+C = leave
```
