# SPDX-License-Identifier: GPL-3.0-only
"""HELP text for hpibterm. Library entries follow the HP-IB Command Library
Reference (82990-90001), Chapter 2 "Interpreted BASIC Syntax Reference"."""

# name: (syntax, description, bus activity, possible errors, example)
LIB = {
    "IOABORT": ("IOABORT (select code)",
                "Aborts all activity on the interface. Devices in Local Lockout stay locked out.",
                "IFC pulsed (>100 us), REN set, ATN cleared.", "NOERR, ETIME, ESEL",
                "CALL IOABORT(7)"),
    "IOCLEAR": ("IOCLEAR (device address)\n  IOCLEAR (select code)",
                "Returns a device (SDC) or every device on the interface (DCL) to a known,\n"
                "  device-dependent state.",
                "Device: ATN UNL MTA LAD [OSA] SDC.   Select code: ATN DCL.", "NOERR, ETIME, ESEL",
                "CALL IOCLEAR(723)      ' clear the device at address 23"),
    "IOCONTROL": ("IOCONTROL (select code, condition, status)",
                  "Sets interface conditions directly. Use with caution.\n"
                  "  condition 5: address (status<>0) or unaddress the interface as talker\n"
                  "  condition 6: address or unaddress the interface as listener\n"
                  "  condition 7: set the interface's own bus address (status 0-30)",
                  "None (5/6 send MTA/UNT or MLA/UNL).", "NOERR, ESEL, ERANGE",
                  "CALL IOCONTROL(7, 5, 1)  ' interface becomes talker"),
    "IODMA": ("IODMA (select code, value, channel)",
              "Sets up DMA for long IOENTERS/IOOUTPUTS transfers (value = minimum length,\n"
              "  0 = off; channel 2 or 3). Accepted for compatibility - linux-gpib chooses\n"
              "  DMA by itself, so it has no effect here.",
              "None.", "NOERR, ESEL, ERANGE", "CALL IODMA(7, 1000, 3)"),
    "IOENTER": ("IOENTER (device address, data)\n  IOENTER (select code, data)",
                "Reads a single real number into the numeric variable data. Reading stops at\n"
                "  EOI or at a linefeed after the number started. No number -> ENUM, data = 0.\n"
                "  Here: leave out data to print the number.",
                "ATN UNL MLA TAD [OSA], ATN cleared, data entered.",
                "NOERR, ETIME, ESEL, EADDR, ENUM",
                "CALL IOENTER(723, READING)"),
    "IOENTERA": ("IOENTERA (device address, readings, max.elements, actual.elements)",
                 "Enters numbers into a numeric array, starting at the given element\n"
                 "  (e.g. READINGS(1)). Non-numeric characters separate values, so\n"
                 "  \"1,234,567\" is three numbers. Stops at EOI (if IOEOI is on) or when\n"
                 "  max.elements have been read. actual.elements gets the count.\n"
                 "  Here: max.elements defaults to the room left in the array; leave out\n"
                 "  the array to print the numbers.",
                 "ATN UNL MLA TAD [OSA], ATN cleared, data entered.",
                 "NOERR, ETIME, ESEL, EADDR, ENUM",
                 "DIM R(49): CALL IOENTERA(723, R(0), 50, N)"),
    "IOENTERS": ("IOENTERS (device address, data$, max.length, actual.length)",
                 "Enters a string. Stops at EOI (if enabled), at the IOMATCH character\n"
                 "  (linefeed by default; it is kept in the string) or after max.length\n"
                 "  characters. actual.length gets the length.\n"
                 "  Here: max.length defaults to 255; leave out data$ to print the reply\n"
                 "  with control characters shown as <CR><LF>.",
                 "ATN UNL MLA TAD [OSA], ATN cleared, data entered.",
                 "NOERR, ETIME, ESEL, EADDR",
                 "CALL IOENTERS(723, A$, 80, N): A$ = LEFT$(A$, N - 2)"),
    "IOEOI": ("IOEOI (select code, state)",
              "Enables (state<>0, default) or disables EOI. Writes set EOI on the last byte\n"
              "  of the EOL; reads stop when EOI is seen. With EOI off, IOENTERA/IOENTERS\n"
              "  keep reading past EOI (useful for instruments that send EOI per value).",
              "None.", "NOERR, ESEL", "CALL IOEOI(7, 0)   ' disable EOI"),
    "IOEOL": ("IOEOL (select code, endline$, length)",
              "Sets the End Of Line string (max 8 characters) sent after every IOOUTPUT,\n"
              "  IOOUTPUTA and IOOUTPUTS. Default CR/LF. length 0 = send nothing.",
              "None.", "NOERR, ESEL, ERANGE",
              "E$ = CHR$(10): CALL IOEOL(7, E$, 1)   ' LF only"),
    "IOGETTERM": ("IOGETTERM (select code, reason)",
                  "Why the last read stopped (sum): 0 other, 1 count reached,\n"
                  "  2 IOMATCH character, 4 EOI.",
                  "None.", "NOERR, ESEL",
                  "CALL IOGETTERM(7, R): IF (R AND 4) = 4 THEN PRINT \"EOI\""),
    "IOLLOCKOUT": ("IOLLOCKOUT (select code)",
                   "Sends Local Lockout (LLO): front panels are disabled (LOCAL key too).\n"
                   "  Only works while REN is set (IOREMOTE).",
                   "ATN LLO.", "NOERR, ETIME, ESEL", "CALL IOLLOCKOUT(7)"),
    "IOLOCAL": ("IOLOCAL (device address)\n  IOLOCAL (select code)",
                "Device: Go To Local (until it is addressed to listen again).\n"
                "  Select code: clears REN - every device to local, lockout cancelled.",
                "Device: ATN UNL MTA LAD [OSA] GTL.   Select code: REN and ATN cleared.",
                "NOERR, ETIME, ESEL", "CALL IOLOCAL(723)"),
    "IOMATCH": ("IOMATCH (select code, character$, flag)",
                "Sets the character that ends IOENTERS (default linefeed). flag 0 = no\n"
                "  matching, non-zero = enabled. Not used by IOENTER/IOENTERA.\n"
                "  Here: flag defaults to 1.",
                "None.", "NOERR, ESEL",
                "M$ = CHR$(13): CALL IOMATCH(7, M$, 1)   ' stop at CR"),
    "IOOUTPUT": ("IOOUTPUT (device address, data)\n  IOOUTPUT (select code, data)",
                 "Sends one real number, then the EOL (EOI on the last byte if enabled).\n"
                 "  7 significant digits; fixed point for 1E-5..1E+6 (no decimal point for\n"
                 "  whole numbers), else scientific; leading space if positive.",
                 "ATN UNL MTA LAD [OSA], ATN cleared, data and EOL sent.",
                 "NOERR, ETIME, ESEL, EADDR", "CALL IOOUTPUT(722, 12.3)   ' sends \" 12.3\"+CR/LF"),
    "IOOUTPUTA": ("IOOUTPUTA (device address, data, elements)",
                  "Sends 'elements' numbers from a numeric array (start element given,\n"
                  "  e.g. V(0)), separated by commas, then one EOL.",
                  "ATN UNL MTA LAD [OSA], ATN cleared, data and EOL sent.",
                  "NOERR, ETIME, ESEL, EADDR", "CALL IOOUTPUTA(722, V(0), 10)"),
    "IOOUTPUTS": ("IOOUTPUTS (device address, data$, length)",
                  "Sends 'length' characters of a string, then the EOL.\n"
                  "  Here: length defaults to LEN(data$). CHR$() puts any byte 0-255 in a\n"
                  "  string, e.g. \"W\" + CHR$(5) for binary commands (set IOEOL 7,\"\",0 first).",
                  "ATN UNL MTA LAD [OSA], ATN cleared, data and EOL sent.",
                  "NOERR, ETIME, ESEL, EADDR",
                  "C$ = \"F1RAN5T3\": CALL IOOUTPUTS(723, C$, LEN(C$))"),
    "IOPPOLL": ("IOPPOLL (select code, response)",
                "Parallel poll: response 0-255, bit n = data line DIO(n+1).\n"
                "  Not available on the gpib4pi board: linux-gpib's gpib_bitbang driver has no\n"
                "  parallel poll, so IOPPOLL gives an error there (it works in the simulator).\n"
                "  Use IOSTATUS (SRQ) and IOSPOLL instead.",
                "ATN and EOI asserted for 25 us, poll byte read, EOI cleared.",
                "NOERR, ESEL", "CALL IOPPOLL(7, R)"),
    "IOPPOLLC": ("IOPPOLLC (device address, configuration)\n  IOPPOLLC (select code, configuration)",
                 "Parallel Poll Configure. configuration 0-15: bits 0-2 = data line (0-7 =\n"
                 "  DIO1-8), bit 3 = sense of an affirmative response. 12 = '1' on DIO5.\n"
                 "  It only sends bus commands, so it works on any board; reading the poll\n"
                 "  (IOPPOLL) does not work on the gpib4pi.",
                 "Device: ATN UNL MTA LAD [OSA] PPC PPE.   Select code: PPC PPE.",
                 "NOERR, ETIME, ESEL, ERANGE", "CALL IOPPOLLC(723, 10)   ' '1' on line 2"),
    "IOPPOLLU": ("IOPPOLLU (device address)\n  IOPPOLLU (select code)",
                 "Parallel Poll Unconfigure: the device(s) stop responding to parallel polls.",
                 "Device: ATN UNL MTA LAD [OSA] PPC PPD.   Select code: ATN PPU.",
                 "NOERR, ETIME, ESEL", "CALL IOPPOLLU(723)"),
    "IOREMOTE": ("IOREMOTE (device address)\n  IOREMOTE (select code)",
                 "Puts a device in remote. With a select code only REN is set; devices go\n"
                 "  remote when they are next addressed to listen.",
                 "Device: REN set, ATN UNL MTA LAD [OSA].   Select code: REN set.",
                 "NOERR, ETIME, ESEL", "CALL IOREMOTE(723)"),
    "IORESET": ("IORESET (select code)",
                "Interface back to its start-up state: system and active controller, not\n"
                "  talking or listening; timeout 0 (OFF - reads can then wait forever),\n"
                "  EOI on, EOL CR/LF, IOMATCH linefeed. All devices go to local; REN is\n"
                "  then set again, so they go back to remote when next addressed to listen.",
                "IFC pulsed (>100 us), REN cleared (>10 us) then set again, ATN cleared.",
                "NOERR, ETIME, ESEL", "CALL IORESET(7): CALL IOTIMEOUT(7, 5)"),
    "IOSEND": ("IOSEND (select code, commands$, length)",
               "Sends bus command bytes with ATN set (no EOL, no EOI). Each character is\n"
               "  one command: '?' = UNL, '_' = UNT, CHR$(32+n) = listen n, CHR$(64+n) =\n"
               "  talk n, CHR$(8) = GET, CHR$(20) = DCL ... Then address the select code.",
               "ATN set, command bytes sent.", "NOERR, ETIME, ESEL, EPASS",
               "C$ = \"?)/4\": CALL IOSEND(7, C$, 4): CALL IOTRIGGER(7)   ' trigger 9, 15, 20"),
    "IOSPOLL": ("IOSPOLL (device address, response)",
                "Serial poll: the device's status byte (bit 6 = 64 = RQS, it asked for\n"
                "  service). Polling clears the device's SRQ.",
                "ATN UNL MLA TAD [OSA] SPE, ATN cleared, byte read, ATN SPD UNT.",
                "NOERR, ETIME, ESEL", "CALL IOSPOLL(723, S): IF S AND 64 THEN PRINT \"SRQ\""),
    "IOSTATUS": ("IOSTATUS (select code, condition, status)",
                 "Interface status (0 clear / 1 set): 0 remote (always 0), 1 SRQ line,\n"
                 "  2 NDAC line, 3 system controller (always 1), 4 active controller,\n"
                 "  5 addressed as talker, 6 addressed as listener, 7 = its bus address.",
                 "None.", "NOERR, ESEL, ERANGE",
                 "100 CALL IOSTATUS(7, 1, S): IF S = 0 THEN 100   ' wait for SRQ"),
    "IOTIMEOUT": ("IOTIMEOUT (select code, timeout)",
                  "Timeout in seconds for every transfer (0 = off, max 4096). On timeout\n"
                  "  PCIB.ERR = 100004 (ETIME), PCIB.ERR$ = \"HPIB: timeout\". linux-gpib rounds\n"
                  "  up to its steps (..1, 3, 10, 30, 100, 300, 1000 s). hpibterm starts at 10 s.",
                  "None.", "NOERR, ESEL, ERANGE", "CALL IOTIMEOUT(7, 2.5)"),
    "IOTRIGGER": ("IOTRIGGER (device address)\n  IOTRIGGER (select code)",
                  "Group Execute Trigger to one device, or to all devices addressed to listen\n"
                  "  (after IOSEND) when a select code is given.",
                  "Device: ATN UNL MTA LAD [OSA] GET.   Select code: ATN GET.",
                  "NOERR, ETIME, ESEL", "CALL IOTRIGGER(723)"),
}

TOPICS = {
    "": """HP-IB Terminal - an HP-IB programming environment modelled on the
HP 82990A "HP-IB Command Library for MS-DOS" (BASIC version), running on linux-gpib.
It works with any GPIB instrument. The examples use device 723 (bus address 23), where
the simulator (--sim) has an HP 3478A multimeter.

Type statements directly, or give them line numbers to build a program:
    IOOUTPUTS 723, "F1RAN5T3"          send codes to the instrument at address 23
    IOENTERS 723                       read and show its reply
    ASK 723, "H1"                      send + read in one go
    10 CALL IOENTER(723, V): PRINT V   a program line;  RUN  LIST  SAVE "x"

Help works like DEC VMS HELP: HELP topic subtopic ...  Names may be shortened
(HELP COM SA = HELP COMMAND SAVE) and * or % wildcards used (HELP LIB IOENT*).
HELP SAVE finds COMMAND SAVE by itself. At a Topic? or Subtopic? prompt:
  a name   look it up (from where you are, or from the top if it isn't there)
  ?        show the text again         Enter   go up one level
  TOP      go to the top level         Ctrl+C  leave HELP (back to HP-IB>)""",

    "ADDRESS": """Addressing (manual 2-19). The first parameter of each command is either:
    select code     1-99      the interface itself - hpibterm: 7 = linux-gpib board 0
    device address  sc*100 + primary address            723   = sc 7, address 23
    extended        sc*10000 + primary*100 + secondary  72315 = sc 7, addr 23, sec 15
Primary addresses are 0-30, secondary 0-30. The interface's own address (pad in
gpib.conf, usually 0) cannot be used as a device. Some commands take only a select
code (IOABORT, IOEOI ...), IOSPOLL only a device address, most take either.
With a device address the library addresses the bus itself (UNL, MTA/MLA, LAD/TAD).
With a select code no addressing is done: use IOSEND or IOCONTROL first.
Other boards: start with  --isc 8=1  (select code 8 = board 1).""",

    "ERRORS": """Error handling (manual 2-14). After every library command:
    PCIB.ERR      0 = no error, else the error number below
    PCIB.ERR$     the message, e.g. "HPIB: timeout"
    PCIB.GLBERR   last error that occurred anywhere in the program
    PCIB.BASERR   255 - the BASIC error number used for library errors (ERR = 255)
  number  mnemonic  meaning
       0  NOERR     no error
  100001  EUNKNOWN  unknown error
  100002  ESEL      invalid select code or device address
  100003  ERANGE    parameter out of range
  100004  ETIME     timeout (IOTIMEOUT elapsed since the last byte)
  100005  ECTRL     interface must be active / system controller
  100006  EPASS     pass control not permitted
  100007  ENUM      no number / badly formed number (IOENTER, IOENTERA)
  100008  EADDR     improper addressing (select code used but not addressed)
The mnemonics are predefined variables:  IF PCIB.ERR <> NOERR THEN ERROR PCIB.BASERR
OPTION ERRORS STOP (default): a library error is BASIC error 255 at once - it goes
  to your ON ERROR GOTO handler (ERR = 255, ERL = line) or stops the program.
OPTION ERRORS CONTINUE: the program carries on; check PCIB.ERR yourself
  (exactly as on the original library).""",

    "BASIC": """Statements (GW-BASIC style; several per line with ':'):
  [LET] V = expr     A$ = "text"     DIM R(49), M(3,3)     OPTION BASE 0|1
  PRINT [#n,] a; b, c   (? = PRINT)   WRITE [#n,] a, b$   (CSV style)
  INPUT ["prompt";] A, B$     LINE INPUT ["prompt";] A$
  IF cond THEN statements|line [ELSE statements|line]     IF cond GOTO line
  GOTO n   GOSUB n / RETURN   ON x GOTO|GOSUB n1, n2 ...
  FOR I = a TO b [STEP s] ... NEXT [I]      WHILE cond ... WEND
  ON ERROR GOTO n   RESUME [NEXT|n]   ERROR n   ERR  ERL
  END  STOP (then CONT)   REM / '   DATA / READ / RESTORE   SWAP A, B
  SLEEP seconds   CLS   BEEP   TRON / TROFF (show line numbers)
  OPEN "file" FOR INPUT|OUTPUT|APPEND AS #n   CLOSE [#n]   EOF(n)
  CALL IOxxx(...)  or just  IOxxx ...   - see HELP LIBRARY
  OPTION ERRORS STOP|CONTINUE         - see HELP ERRORS
Extensions (not in the 82990A):
  ASK addr, cmd$ [, reply$]   IOOUTPUTS then IOENTERS (prints reply if no variable)
  SCAN [sc]    list the bus addresses that answer
  LINES [sc]   show the state of the bus lines (SRQ, REN, ATN, EOI ...)
  SHOW [sc]    show timeout, EOI, EOL, MATCH and the last error
Operators: + - * / ^ \\ (integer divide) MOD = <> < > <= >= AND OR XOR NOT
  (AND/OR work on bits: IF (S AND 64) THEN ...). True = -1, false = 0.
  Numbers: 1.5, 2E-3, &H41 (hex), &O17 (octal).  Strings hold any byte 0-255.""",

    "CREDITS": """Credits (details and licenses: THIRD-PARTY-NOTICES.pdf):
  Hardware   gpib4pi board and guide - Lightside Instruments AS (TAPR Open Hardware License),
             based on the elektronomikon board by Thomas Klima
             https://github.com/lightside-instruments/gpib4pi
  Driver     linux-gpib (GPL-2.0); gpib_bitbang driver by Thomas Klima (TU Vienna) and
             Marcello Carla' (University of Florence); Lightside's Debian packaging
  Library    the HP 82990A HP-IB Command Library and its 1986 reference manual,
             Hewlett-Packard Company - re-implemented here from the manual
  3478A cal  Tom Verbeure (BSD-2-Clause), PyMeasure (MIT), Patrick Baus's
             pyAsyncHP3478A (GPL-3.0) and Vinay Shanbhag's hp3478a: memory layout,
             commands, file formats and the test dumps in dev\\
  Styles     GW-BASIC (Microsoft) for the language, DEC VMS HELP for this help
This program's own code was written for this project; none of the above is copied
into it. pi-GPIBTerm is free software under the GNU General Public License
version 3 (GPL-3.0-only): see LICENSE.""",

    "KEYS": """Keys:
  Ctrl+C   stop a running program (CONT continues) or cancel the line being typed
  Up/Down  earlier lines (history is kept in ~/.hpibterm_history)
  Tab      complete command, statement, function and variable names
  Ctrl+D   leave (same as BYE)
In HELP:  Enter = up one level   TOP = top level   ? = repeat   Ctrl+C = leave HELP
Start-up options (hpibterm.py --help):
  hpibterm.py [program.bas] [--run] [-c "statements"] [-i] [--sim] [--trace]
              [--timeout SECONDS] [--isc SC=BOARD]
  program.bas  load it          --run  run it, then exit     -c  run statements, then exit
  -i  stay in the terminal after --run / -c     --sim  simulated HP 3478A at 723
  --trace  start with TRACE ON  --timeout  start-up IOTIMEOUT (default 10)
  --isc 8=1  select code 8 = linux-gpib board 1 (default 7=0)""",

    "INSTRUMENTS": """Notes on particular instruments. Any GPIB instrument works with the library
commands; these are the ones with an instrument module in pi-GPIBTerm (menu: pi-gpibterm).
The simulator (--sim) has an HP 3478A at 723, so the examples in HELP use that address.""",

    "3478A": """HP 3478A (factory address 23 -> device address 723). Pre-SCPI: no *IDN?.
  F1..F7  DCV ACV 2W-ohm 4W-ohm DCA ACA ext-ohm      RA / R-2..R7 range
  N3/N4/N5 digits   Z0/Z1 autozero   T1 internal T2 external T3 single T4 hold T5 fast
  H0..H7  home; H1..H7 = preset + one reading of F1..F7
  D1 normal display   D2text show text   D3text show text, freeze annunciators
  S  front(1)/rear(0) terminals   B  5 binary status bytes   E error register
  K  clear status   M<2 octal digits> SRQ mask (M01 = data ready, M04 = syntax error)
  Serial poll bits: 1 data ready, 4 syntax error, 8 hardware error, 64 RQS.
  Readings look like +1.23456E+0; +9.99999E+9 means OVERLOAD.
  Quick: ASK 723, "H1"     IOOUTPUTS 723, "F1RAN5T4": IOOUTPUTS 723, "T3": IOENTER 723""",

    "EXAMPLES": """Example programs (LOAD "examples/name", LIST, RUN). FILES examples lists them.
  bus_tour.bas       a tour of the library commands with TRACE ON (any instrument at 723)
  error_handler.bas  ON ERROR handler in the style of SETUP.BAS
  manual_example.bas the manual's 3325A/3456A example (needs those instruments)
From the HP 3478A instrument module (instruments/hp3478a/examples, found the same way):
  3478a_read.bas     take readings with single triggers, print them
  3478a_log.bas      log readings with time stamps to a CSV file
  3478a_srq.bas      wait for SRQ (IOSTATUS) and serial poll (IOSPOLL)
  3478a_calsave.bas  save the meter's calibration RAM (read only) - restore with hp3478a-cal""",


    "DIFFERENCES": """Differences from the original 82990A library and GW-BASIC:
  - Parameters may be literals or expressions: CALL IOCLEAR(723) is fine (the
    original needed variables). Output parameters must still be variables.
  - Optional trailing parameters: lengths default to LEN(), max.length to 255,
    IOMATCH flag to 1. Leave out an output variable to print the result.
  - Library errors stop the program (or go to ON ERROR) by default;
    OPTION ERRORS CONTINUE gives the original behaviour.
  - Timeout starts at 10 s (original: 0 = off). IORESET still sets it to 0.
  - REN is set when the terminal starts (the interface's start-up state), so instruments
    obey commands at once. IOLOCAL 7 clears it - instruments then ignore their commands
    but still answer reads - and IOREMOTE 7 sets it again. On BYE, REN is cleared and
    every instrument goes back to front-panel control.
  - IODMA is accepted but does nothing. IOEOI 7,0 cannot stop linux-gpib from
    ending a read at EOI; IOENTERA/IOENTERS then simply read again.
  - Keywords need spaces around them (FOR I = 1 TO 10, not FORI=1TO10).
  - Variable names are not truncated; no DEF FN, PRINT USING, graphics, sound.
  - SETUP.BAS housekeeping lines (DEF SEG, BLOAD, COMMON, CALL DEFERR,
    IOCLEAR = PCIB.BASE + ...) are accepted and ignored.""",
}


# name: (syntax, description, example)
COMMAND = {
    "RUN": ('RUN  |  RUN line  |  RUN "file"',
            "Runs the program from the start (or from a line). Clears all variables first.\n"
            "With a file name: LOAD it, then run it. Ctrl+C stops it; CONT carries on.",
            'RUN        RUN 100        RUN "examples/3478a_read"'),
    "LIST": ("LIST  |  LIST line  |  LIST from-to  |  LIST from-  |  LIST -to",
             "Shows the program, or part of it.", "LIST 100-200"),
    "NEW": ("NEW", "Deletes the program in memory and clears all variables. Save first!", "NEW"),
    "CONT": ("CONT", "Continues a program after STOP or Ctrl+C, at the statement where it stopped.\n"
             "Not possible after the program was changed.", "CONT"),
    "EDIT": ("EDIT line",
             "Puts the line on the input line so you can change it with the arrow keys,\n"
             "then press Enter. (Without readline it is shown so you can retype it.)", "EDIT 40"),
    "DELETE": ("DELETE line  |  DELETE from-to  |  DELETE from-  |  DELETE -to",
               "Deletes program lines. Typing only a line number deletes that one line.",
               "DELETE 100-150"),
    "RENUM": ("RENUM [start[, step]]",
              "Renumbers the program (default 10, 20, 30 ...) and fixes the line numbers\n"
              "after GOTO, GOSUB, THEN, ELSE, RESUME and RESTORE.", "RENUM 1000, 10"),
    "AUTO": ("AUTO [start[, step]]",
             "Numbers new lines for you as you type them. Press Enter on an empty line\n"
             "to stop. Default: after the last line, step 10.", "AUTO 1000"),
    "LOAD": ('LOAD "file"',
             "Loads a program (plain text with line numbers) and replaces the one in\n"
             "memory. .bas is added if the name has no extension. Lines with syntax\n"
             "errors are loaded anyway and listed, so you can fix them.",
             'LOAD "examples/3478a_read"'),
    "SAVE": ('SAVE "file"',
             "Saves the program as a plain text file (one numbered line per line, LF line\n"
             "endings). .bas is added if the name has no extension. An existing file with\n"
             "the same name is replaced.", 'SAVE "mytest"        (writes mytest.bas)'),
    "MERGE": ('MERGE "file"',
              "Adds the lines of a file to the program in memory. Lines with the same\n"
              "number are replaced by the file's lines.", 'MERGE "subroutines"'),
    "FILES": ('FILES [folder | "pattern"]', "Lists program files (*.bas by default).",
              'FILES        FILES examples        FILES "*.txt"'),
    "TRACE": ("TRACE ON  |  TRACE OFF",
              "Shows the bus activity of every library command as it happens, in the words\n"
              "of the manual's 'Bus Activity' sections, plus the data sent and received.",
              "TRACE ON: IOCLEAR 723     shows  [bus] ATN UNL MTA LAD 23 SDC"),
    "VARS": ("VARS", "Lists all variables with their values, and the arrays with their sizes.", "VARS"),
    "CLEAR": ("CLEAR", "Forgets all variables and arrays and closes open files; the program stays.\n"
              "(In a program line, CLEAR is ignored, as in SETUP.BAS.)", "CLEAR"),
    "HELP": ("HELP [topic [subtopic ...]]     HELP/NOPROMPT topic ...",
             "Help in the style of DEC VMS HELP. Topics form a tree: LIBRARY, COMMAND,\n"
             "STATEMENT, FUNCTION, ERRORS ... and their entries. Names can be shortened\n"
             "(HELP COM SA) and use * or % wildcards (HELP LIB IOENT*); HELP SAVE finds\n"
             "COMMAND SAVE by itself. Afterwards it asks Topic? or Subtopic?: type a name,\n"
             "? to see the text again, Enter to go up one level, TOP for the top level,\n"
             "Ctrl+C to leave HELP.\n"
             "/NOPROMPT shows the text without asking.",
             "HELP COMMAND SAVE      HELP LIBRARY IOENTERS BUS_ACTIVITY      HELP ERRORS ETIME"),
    "BYE": ("BYE  (or QUIT, EXIT, SYSTEM, Ctrl+D)",
            "Leaves the terminal. Every instrument is put back to local (front panel)\n"
            "control and open files are closed.", "BYE"),
}
COMMAND_ALIASES = {"QUIT": "BYE", "EXIT": "BYE", "SYSTEM": "BYE"}

STATEMENT = {
    "LET": ("[LET] variable = expression",
            "Assigns a value. LET may be left out. Names ending in $ hold strings.",
            'DVM = 723: CODE$ = "F1RAN5"'),
    "PRINT": ("PRINT [#n,] items      (? is short for PRINT)",
              "Prints numbers and strings. ';' joins items, ',' moves to the next 14-column\n"
              "zone, a ';' or ',' at the end keeps the cursor on the line. Positive numbers\n"
              "get a leading space. #n prints to an open file.",
              'PRINT "V ="; V, "OK"        ? I; V'),
    "WRITE": ("WRITE [#n,] items",
              "Like PRINT but CSV style: items separated by commas, strings in quotes.",
              'WRITE #1, TIME$, V'),
    "INPUT": ('INPUT ["prompt";] var [, var ...]     INPUT #n, var [, var ...]',
              "Asks for values (comma separated). A bad number gives ?Redo from start.\n"
              "Use ',' instead of ';' after the prompt to leave out the '?'.",
              'INPUT "How many readings"; N'),
    "LINE INPUT": ('LINE INPUT ["prompt";] var$     LINE INPUT #n, var$',
                   "Reads a whole line, commas included, into a string variable.",
                   'LINE INPUT "File name: "; F$'),
    "IF": ("IF condition THEN statements|line [ELSE statements|line]\n  IF condition GOTO line",
           "Runs the THEN part if the condition is not 0, otherwise the ELSE part (or the\n"
           "next line). Everything after THEN to the end of the line belongs to it.",
           'IF ABS(V) >= 9E+09 THEN PRINT "OVERLOAD" ELSE PRINT V'),
    "GOTO": ("GOTO line", "Continues at the given line.", "GOTO 100"),
    "GOSUB": ("GOSUB line ... RETURN", "Calls a subroutine; RETURN comes back after the GOSUB.",
              "GOSUB 1000"),
    "RETURN": ("RETURN", "Ends a subroutine started with GOSUB.", "1090 RETURN"),
    "ON GOTO": ("ON x GOTO line1, line2 ...     ON x GOSUB line1, line2 ...",
                "Jumps to the x-th line in the list (x = 1, 2 ...); if x is 0 or past the end of\n"
                "the list, carries on with the next statement.", "ON F GOSUB 100, 200, 300"),
    "ON ERROR": ("ON ERROR GOTO line     ON ERROR GOTO 0",
                 "From now on, any error jumps to the line (ERR = number, ERL = line). HP-IB\n"
                 "library errors have ERR = 255 (PCIB.BASERR). GOTO 0 switches it off; inside\n"
                 "the handler it reports the error and stops. See HELP ERRORS.",
                 "ON ERROR GOTO 400"),
    "RESUME": ("RESUME  |  RESUME NEXT  |  RESUME line",
               "Ends an ON ERROR handler: retry the statement that failed, go on with the\n"
               "one after it, or continue at a line.", "RESUME NEXT"),
    "ERROR": ("ERROR n",
              "Raises error n as if it had happened. ERROR PCIB.BASERR (255) reports the\n"
              "last HP-IB library error - the manual's check after each CALL:\n"
              "  IF PCIB.ERR <> NOERR THEN ERROR PCIB.BASERR      (see HELP ERRORS)",
              "IF PCIB.ERR <> NOERR THEN ERROR PCIB.BASERR"),
    "FOR": ("FOR var = start TO end [STEP step] ... NEXT [var]",
            "Repeats the lines up to NEXT, counting var from start to end. Works on one\n"
            "typed line too.", "FOR I = 1 TO 10: IOENTER 723, V: PRINT I, V: NEXT I"),
    "NEXT": ("NEXT [var [, var ...]]", "End of a FOR loop.", "NEXT I"),
    "WHILE": ("WHILE condition ... WEND", "Repeats the lines up to WEND as long as the condition is not 0.",
              "WHILE S = 0: IOSTATUS 7, 1, S: WEND"),
    "WEND": ("WEND", "End of a WHILE loop.", "WEND"),
    "END": ("END", "Ends the program and closes open files.", "END"),
    "STOP": ("STOP", "Stops the program with 'Break in line'. CONT continues; variables can\n"
             "be looked at in between.", "STOP"),
    "REM": ("REM text     ' text", "A comment. ' can also follow a statement on the same line.",
            "IOCLEAR 723   ' reset the meter"),
    "DIM": ("DIM name(size [, size ...]) [, ...]",
            "Creates an array. Elements go from 0 (or 1 with OPTION BASE 1) to size.\n"
            "Arrays used without DIM get size 10.", "DIM READINGS(49), M$(3)"),
    "OPTION BASE": ("OPTION BASE 0|1", "Whether array elements start at 0 or 1. Use before DIM.",
                    "OPTION BASE 1"),
    "OPTION ERRORS": ("OPTION ERRORS STOP|CONTINUE",
                      "STOP (default): an HP-IB library error is BASIC error 255 at once (goes\n"
                      "to ON ERROR or stops). CONTINUE: as the original library - the program\n"
                      "carries on and you check PCIB.ERR yourself.", "OPTION ERRORS CONTINUE"),
    "SLEEP": ("SLEEP seconds", "Waits; fractions are allowed.", "SLEEP 0.5"),
    "CLS": ("CLS", "Clears the screen.", "CLS"),
    "BEEP": ("BEEP", "Sounds the terminal bell.", "BEEP"),
    "TRON": ("TRON  |  TROFF", "Shows [line number] for every program line run (TROFF stops it).",
             "TRON: RUN"),
    "DATA": ("DATA value, value ...", "Values for READ, stored in the program.", 'DATA 1, 2, "THREE"'),
    "READ": ("READ var [, var ...]", "Takes the next values from the DATA lines.", "READ F, R$"),
    "RESTORE": ("RESTORE [line]", "READ starts again from the first DATA (or the DATA at line).",
                "RESTORE 500"),
    "SWAP": ("SWAP var1, var2", "Exchanges two variables of the same type.", "SWAP A, B"),
    "OPEN": ('OPEN "file" FOR INPUT|OUTPUT|APPEND AS #n',
             "Opens a file as number n (1-15). OUTPUT replaces the file, APPEND adds to it.\n"
             "Use PRINT #n, WRITE #n, INPUT #n, LINE INPUT #n, EOF(n), CLOSE #n.",
             'OPEN "log.csv" FOR APPEND AS #1'),
    "MKDIR": ('MKDIR "folder"',
              "Creates a folder. If it already exists you get error 75 (Path/File access\n"
              "error) - catch it with ON ERROR if that is fine.", 'MKDIR "backups"'),
    "KILL": ('KILL "file"', "Deletes a file (error 53 if it isn't there). There is no undo.",
             'KILL "old.csv"'),
    "CLOSE": ("CLOSE [#n [, #n ...]]", "Closes files (all of them if no number is given).", "CLOSE #1"),
    "CALL": ("CALL IOxxx(parameters)     or just     IOxxx parameters",
             "Runs an HP-IB library command. HELP LIBRARY lists them; HELP LIBRARY IOxxx\n"
             "gives the details.", "CALL IOOUTPUTS(723, \"T3\")     IOOUTPUTS 723, \"T3\""),
    "ASK": ("ASK address, command$ [, reply$]",
            "Extension: IOOUTPUTS the command, then IOENTERS the reply into reply$ (or\n"
            "prints it, with control characters shown as <CR><LF>).", 'ASK 723, "H1", R$'),
    "SCAN": ("SCAN [select code]", "Extension: lists the bus addresses where an instrument answers.",
             "SCAN"),
    "LINES": ("LINES [select code]",
              "Extension: shows the bus lines DAV NDAC NRFD IFC REN SRQ ATN EOI (1 = asserted,\n"
              "? = the interface cannot tell).", "LINES"),
    "SHOW": ("SHOW [select code]",
             "Extension: shows the interface settings (board, bus address, IOTIMEOUT, IOEOI,\n"
             "IOEOL, IOMATCH, last IOGETTERM) and the last library error.", "SHOW"),
}
STATEMENT_ALIASES = {"TROFF": "TRON", "?": "PRINT", "'": "REM", "ON": "ON GOTO", "ON GOSUB": "ON GOTO",
                     "LINE": "LINE INPUT", "OPTION": None}

FUNCTION = {
    "ABS": ("ABS(x)", "Absolute value.", "ABS(-2.5) = 2.5"),
    "ATN": ("ATN(x)", "Arc tangent, in radians.", "ATN(1) * 4 = 3.14159..."),
    "COS": ("COS(x)", "Cosine (x in radians).", "COS(0) = 1"),
    "SIN": ("SIN(x)", "Sine (x in radians).", "SIN(PI / 2) = 1"),
    "TAN": ("TAN(x)", "Tangent (x in radians).", "TAN(0) = 0"),
    "EXP": ("EXP(x)", "e to the power x.", "EXP(1) = 2.71828..."),
    "LOG": ("LOG(x)", "Natural logarithm (x > 0). LOG(x) / LOG(10) gives log base 10.", "LOG(10) / LOG(10) = 1"),
    "SQR": ("SQR(x)", "Square root (x >= 0).", "SQR(16) = 4"),
    "INT": ("INT(x)", "Largest whole number <= x.", "INT(-2.5) = -3"),
    "FIX": ("FIX(x)", "x without its fraction (towards 0).", "FIX(-2.5) = -2"),
    "SGN": ("SGN(x)", "-1, 0 or 1 for negative, zero, positive.", "SGN(-7) = -1"),
    "RND": ("RND  |  RND(x)", "Random number from 0 to just below 1.", "INT(RND * 6) + 1"),
    "LEN": ("LEN(s$)", "Number of characters.", 'LEN("F1RA") = 4'),
    "ASC": ("ASC(s$)", "Code (0-255) of the first character.", 'ASC("A") = 65'),
    "VAL": ("VAL(s$)", "The number at the start of a string (0 if none); &H.. is hex.",
            'VAL("+1.23456E+0") = 1.23456'),
    "CHR$": ("CHR$(n)", "The character with code n (0-255); builds binary commands.",
             'CHR$(13) + CHR$(10) = CR LF'),
    "STR$": ("STR$(x)", "A number as text, with a leading space if positive.", 'STR$(5) = " 5"'),
    "HEX$": ("HEX$(x)", "Whole number as hexadecimal text.", 'HEX$(255) = "FF"'),
    "OCT$": ("OCT$(x)", "Whole number as octal text.", 'OCT$(8) = "10"'),
    "BIN$": ("BIN$(x [, width])", "Whole number as binary text, width digits (default 8).",
             'BIN$(65) = "01000001"'),
    "LEFT$": ("LEFT$(s$, n)", "The first n characters.", 'LEFT$(A$, N - 2)  (drop CR LF)'),
    "RIGHT$": ("RIGHT$(s$, n)", "The last n characters.", 'RIGHT$("ABCDE", 2) = "DE"'),
    "MID$": ("MID$(s$, start [, n])", "n characters (or the rest) from position start (1 = first).",
             'MID$("HELLO", 2, 3) = "ELL"'),
    "INSTR": ("INSTR([start,] s$, find$)", "Position of find$ in s$ (0 if not found).",
              'INSTR("F1RA", "R") = 3'),
    "SPACE$": ("SPACE$(n)", "n spaces (the manual uses it before IOENTERS).", "A$ = SPACE$(80)"),
    "STRING$": ("STRING$(n, c)", "n copies of a character (code c or first character of c$).",
                'STRING$(3, "*") = "***"'),
    "UCASE$": ("UCASE$(s$)", "Upper case.", 'UCASE$("f1") = "F1"'),
    "LCASE$": ("LCASE$(s$)", "Lower case.", 'LCASE$("F1") = "f1"'),
    "LTRIM$": ("LTRIM$(s$)", "Without leading spaces.", 'LTRIM$("  5") = "5"'),
    "RTRIM$": ("RTRIM$(s$)", "Without trailing spaces.", 'RTRIM$("5  ") = "5"'),
    "SHOW$": ("SHOW$(s$)", "s$ in quotes with control characters made visible.",
              'PRINT SHOW$(A$)   prints  "+1.5E+0<CR><LF>"'),
    "BIT": ("BIT(x, n)", "-1 if bit n (0 = lowest) of x is set, else 0.",
            'IF BIT(S, 6) THEN PRINT "RQS"'),
    "TAB": ("TAB(n)", "In PRINT: move to column n.", 'PRINT "V"; TAB(10); V'),
    "SPC": ("SPC(n)", "In PRINT: n spaces.", 'PRINT "A"; SPC(5); "B"'),
    "EOF": ("EOF(n)", "-1 when file #n (opened FOR INPUT) has no more lines.",
            "WHILE NOT EOF(1): LINE INPUT #1, L$: PRINT L$: WEND"),
    "TIMER": ("TIMER", "Seconds since midnight, with fractions - for timing and timeouts.",
              "T0 = TIMER: ... : PRINT TIMER - T0; \"s\""),
    "DATE$": ("DATE$", 'Today as "mm-dd-yyyy".', "PRINT DATE$"),
    "TIME$": ("TIME$", 'The time as "hh:mm:ss".', "PRINT TIME$"),
    "PI": ("PI", "3.14159265...", "PRINT 2 * PI"),
    "ERR": ("ERR", "Number of the last error (in an ON ERROR handler); 255 = HP-IB library error.",
            "IF ERR = PCIB.BASERR THEN PRINT PCIB.ERR$"),
    "ERL": ("ERL", "Line where the last error happened.", 'PRINT "error in line"; ERL'),
}
FUNCTION["TRIM$"] = ("TRIM$(s$)", "Without spaces at either end (CR/LF stay - use LEFT$ to drop them).",
                     'TRIM$(" 5 ") = "5"')

import fnmatch  # noqa: E402
import re  # noqa: E402

ERROR_CODES = [
    ("NOERR", 0, "No error occurred."),
    ("EUNKNOWN", 100001, "An unknown error. Check the equipment, the hardware configuration and the\n"
                         "program lines."),
    ("ESEL", 100002, "Invalid select code or device address: a select code where a device address\n"
                     "was needed (or the other way round), an address outside 0-30, or the\n"
                     "interface's own address used as a device."),
    ("ERANGE", 100003, "A parameter is out of range (IOSTATUS 0-7, IOCONTROL 5-7, IOTIMEOUT >= 0,\n"
                       "IOPPOLLC 0-15, IOEOL length 0-8)."),
    ("ETIME", 100004, "Timeout: the IOTIMEOUT time passed with no byte transferred. Usually the\n"
                      "instrument is off, at another address, or has nothing to send."),
    ("ECTRL", 100005, "The interface must be the active and/or system controller."),
    ("EPASS", 100006, "Pass control is not permitted."),
    ("ENUM", 100007, "No digits or a badly formed number in an IOENTER / IOENTERA read. The\n"
                     "value read is set to 0."),
    ("EADDR", 100008, "Improper addressing: a read or write with a select code while the interface\n"
                      "was not addressed to listen or talk (use IOSEND or IOCONTROL first)."),
]


class Node(object):
    def __init__(self, name, text="", children=None):
        self.name = name
        self.text = text
        self.children = children or []      # list of Node, in display order

    def child_names(self):
        return [c.name for c in self.children]


def _entry_node(name, entry, library=False):
    if library:
        syn, desc, bus, errs, ex = entry
        text = "  %s\n\n  %s\n\n  Example: %s" % (syn, desc, ex)
        kids = [Node("Bus_activity", "  " + bus),
                Node("Errors", "  Possible errors: %s\n\n  HELP ERRORS <name> explains each one." % errs)]
        return Node(name, text, kids)
    syn, desc, ex = entry
    return Node(name, "  %s\n\n  %s\n\n  Example: %s" % (syn, "\n  ".join(desc.split("\n")), ex))


def summary(desc, width=60):
    """First sentence of a description, cut at a word boundary."""
    text = " ".join(desc.split())
    m = re.search(r"\. |\.$|: ", text)
    if m and m.start() > 10:
        text = text[:m.start()]
    if len(text) > width:
        text = text[:width - 3].rsplit(" ", 1)[0].rstrip(",;(") + "..."
    return text


def _category(name, title, entries, library=False, tail=""):
    kids = [_entry_node(n, entries[n], library) for n in sorted(entries)]
    lines = ["  " + title, ""]
    for n in sorted(entries):
        lines.append("  %-14s %s" % (n, summary(entries[n][1])))
    if tail:
        lines += ["", "  " + tail]
    return Node(name, "\n".join(lines), kids)


def build_tree():
    errs = Node("ERRORS", TOPICS["ERRORS"],
                [Node(m, "  %d  %s" % (n, "\n  ".join(d.split("\n")))) for m, n, d in ERROR_CODES])
    kids = [
        _category("LIBRARY", "The HP-IB Command Library commands (address = 7 or 723, see ADDRESS):",
                  LIB, library=True),
        _category("COMMAND", "Terminal commands - type them without a line number:", COMMAND,
                  tail="QUIT, EXIT and SYSTEM are the same as BYE. Keys and start-up options: HELP KEYS."),
        _category("STATEMENT", "BASIC statements - direct, or in numbered program lines:", STATEMENT,
                  tail="Operators and an overview of the language: HELP BASIC."),
        _category("FUNCTION", "Functions - use them in expressions:", FUNCTION),
        Node("ADDRESS", TOPICS["ADDRESS"]), Node("BASIC", TOPICS["BASIC"]), errs,
        Node("INSTRUMENTS", TOPICS["INSTRUMENTS"], [Node("3478A", TOPICS["3478A"])]),
        Node("EXAMPLES", TOPICS["EXAMPLES"]),
        Node("KEYS", TOPICS["KEYS"]), Node("DIFFERENCES", TOPICS["DIFFERENCES"]),
        Node("CREDITS", TOPICS["CREDITS"]),
    ]
    return Node("", TOPICS[""], kids)


TREE = build_tree()
# words that should find a topic under another name
SYNONYMS = {"QUIT": "BYE", "EXIT": "BYE", "SYSTEM": "BYE", "TROFF": "TRON", "?": "PRINT",
            "COMMANDS": "COMMAND", "STATEMENTS": "STATEMENT", "FUNCTIONS": "FUNCTION",
            "LIB": "LIBRARY", "ERROR_CODES": "ERRORS", "ADDRESSING": "ADDRESS", "HP3478A": "3478A"}


def _norm(word):
    return word.upper().replace(" ", "_")


def match(node, word):
    """Children of node matching word: exact name, unique-or-not prefix, or * / % wildcard."""
    w = SYNONYMS.get(_norm(word), _norm(word))
    names = [(_norm(c.name), c) for c in node.children]
    if "*" in w or "%" in w:
        pat = w.replace("%", "?")
        return [c for n, c in names if fnmatch.fnmatchcase(n, pat)]
    exact = [c for n, c in names if n == w]
    if exact:
        return exact
    if node.children and any(n.endswith("$") for n, _ in names):
        exact = [c for n, c in names if n == w + "$"]
        if exact:
            return exact
    return [c for n, c in names if n.startswith(w)]


def _split(words):
    """Join multi-word entry names typed with spaces (ON ERROR, LINE INPUT, OPTION BASE)."""
    return [w for w in words if w]


def lookup(words, node=None, path=None):
    """All (path, node) pairs reached by following words down the tree from node."""
    node = node or TREE
    path = path or []
    if not words:
        return [(path, node)]
    results = []
    hits = match(node, words[0])
    # multi-word names: "ON ERROR" typed as two words
    if len(words) > 1:
        joined = match(node, words[0] + "_" + words[1])
        if joined and all(_norm(c.name) == _norm(words[0] + "_" + words[1]) for c in joined):
            for c in joined:
                results += lookup(words[2:], c, path + [c.name])
            return results
    for c in hits:
        results += lookup(words[1:], c, path + [c.name])
    return results


def find(words):
    """VMS-style lookup from the root; if the first word is not a root topic, look one
    level down too (HELP SAVE -> COMMAND SAVE, HELP IOENTERS -> LIBRARY IOENTERS)."""
    words = _split(words)
    found = lookup(words)
    if found or not words:
        return found
    for cat in TREE.children:
        found += lookup(words, cat, [cat.name])
    return found


def columns(names, width=78):
    if not names:
        return ""
    w = max(len(n) for n in names) + 2
    per = max(1, (width - 2) // w)
    rows = []
    for i in range(0, len(names), per):
        rows.append("  " + "".join(n.ljust(w) for n in names[i:i + per]).rstrip())
    return "\n".join(rows)


def render(path, node):
    head = " ".join(p.replace("_", " ") if " " in p else p for p in path)
    out = []
    if head:
        out.append(head)
        out.append("")
    if node.text:
        out.append(node.text)
    if node.children:
        out.append("")
        out.append("  Additional information available:")
        out.append("")
        out.append(columns(node.child_names()))
    return "\n".join(out)


def help_text(topic=""):
    """Help for HELP <topic subtopic ...> without prompting (VMS HELP/NOPROMPT)."""
    words = topic.replace('"', " ").split()
    found = find(words)
    if not found:
        return no_doc(*deepest(words))
    return "\n\n".join(render(p, n) for p, n in found)


def deepest(words, node=None, path=None):
    """Follow words while they match exactly one topic; returns (rest, node, path)."""
    node, path = node or TREE, list(path or [])
    words = list(words)
    while words:
        hits = match(node, words[0])
        if len(hits) != 1:
            break
        node = hits[0]
        path.append(node.name)
        words.pop(0)
    return words, node, path


def no_doc(words, node, path=None):
    where = " ".join(path or [])
    text = "Sorry, no documentation on %s" % " ".join(([where] if where else []) + [w.upper() for w in words])
    if node.children:
        text += "\n\n  Additional information available:\n\n" + columns(node.child_names())
    return text


TOP_WORDS = ("TOP", "^", "/TOP")
HINT = ("  [At the prompt: a name looks it up, ? repeats the text, Enter goes up one level,\n"
        "   TOP goes to the top level, Ctrl+C leaves HELP.]")


class Session(object):
    """Interactive VMS-style HELP: Topic? / Subtopic? prompts. Enter goes up one level,
    TOP (or ^) jumps to the top level, ? shows the current text again, Ctrl+C or EOF
    (Ctrl+D, Ctrl+Z on Windows) leaves HELP. A name that is not under the current level is
    looked up from the top, so you can jump straight to any topic."""

    def __init__(self, ask, say):
        self.ask = ask          # ask(prompt) -> str, raises EOFError
        self.say = say

    def run(self, words):
        path, node = [], TREE
        if words:
            found = find(words)
            if not found:
                rest, node, path = deepest(words)
                self.say(no_doc(rest, node, path) + "\n")
                if not node.children:
                    path, node = path[:-1], self._node(path[:-1])
            else:
                for p, n in found:
                    self.say(render(p, n) + "\n")
                if len(found) == 1:
                    path, node = found[0]
                    if not node.children:           # leaf: prompt at its parent's level
                        path = path[:-1]
                        node = self._node(path)
        else:
            self.say(render([], TREE) + "\n")
        self.say(HINT + "\n")
        while True:
            prompt = "Topic? " if not path else "%s Subtopic? " % " ".join(path)
            try:
                line = self.ask(prompt)
            except (EOFError, KeyboardInterrupt):
                self.say("")
                return
            line = line.strip()
            if not line:
                if not path:
                    return
                path = path[:-1]
                node = self._node(path)
                continue
            if line == "?":
                self.say(render(path, node) + "\n")
                continue
            if line.upper() in TOP_WORDS:
                path, node = [], TREE
                self.say("  Additional information available:\n\n" + columns(TREE.child_names()) + "\n")
                continue
            words = line.replace('"', " ").split()
            found = lookup(words, node, list(path))
            if not found and path:                  # not under this level: look from the top
                found = find(words)
            elif not found:
                found = find(words)
            if not found:
                rest, where, wpath = deepest(words, node, path)
                self.say(no_doc(rest, where, wpath) + "\n")
                continue
            for p, n in found:
                self.say(render(p, n) + "\n")
            if len(found) == 1:
                fpath, fnode = found[0]
                if fnode.children:
                    path, node = fpath, fnode
                elif fpath[:-1] != path:            # jumped elsewhere: prompt at that level
                    path = fpath[:-1]
                    node = self._node(path)

    def _node(self, path):
        node = TREE
        for name in path:
            node = [c for c in node.children if c.name == name][0]
        return node
