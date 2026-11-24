5 REM SPDX-License-Identifier: GPL-3.0-only
10 REM A tour of the HP-IB Command Library. Type TRACE ON before RUN to see the bus.
20 ISC = 7: DVM = 723
30 PRINT "IORESET - interface to its start-up state": CALL IORESET(ISC)
40 PRINT "IOTIMEOUT - 5 s": CALL IOTIMEOUT(ISC, 5)
50 PRINT "IOREMOTE - meter to remote": CALL IOREMOTE(DVM)
60 PRINT "IOCLEAR - selected device clear": CALL IOCLEAR(DVM)
70 PRINT "IOOUTPUTS - send codes": CALL IOOUTPUTS(DVM, "F1RAN5T4")
80 PRINT "IOTRIGGER - group execute trigger": CALL IOTRIGGER(DVM)
90 CALL IOENTER(DVM, V): PRINT "IOENTER -"; V
100 CALL IOGETTERM(ISC, R): PRINT "IOGETTERM -"; R; "(4 = ended by EOI)"
110 CALL IOSPOLL(DVM, S): PRINT "IOSPOLL - status byte"; S
120 CALL IOSTATUS(ISC, 7, A): PRINT "IOSTATUS 7 - our own bus address"; A
130 PRINT "IOSEND - UNL + listen 23 by hand, then IOTRIGGER on the select code"
140 C$ = "?" + CHR$(32 + 23): CALL IOSEND(ISC, C$, LEN(C$)): CALL IOTRIGGER(ISC)
150 CALL IOENTER(DVM, V): PRINT "  reading after the group trigger:"; V
160 PRINT "IOOUTPUTS D2 - text on the meter display": CALL IOOUTPUTS(DVM, "D2HP-IB TERM")
170 SLEEP 2: CALL IOOUTPUTS(DVM, "D1")
180 PRINT "IOLLOCKOUT - front panel LOCAL key disabled": CALL IOLLOCKOUT(ISC)
190 PRINT "IOLOCAL - every device back to local": CALL IOLOCAL(ISC)
200 END
