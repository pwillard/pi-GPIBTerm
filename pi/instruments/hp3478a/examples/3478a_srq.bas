5 REM SPDX-License-Identifier: GPL-3.0-only
10 REM Let the HP 3478A request service (SRQ) when a reading is ready
20 ISC = 7: DVM = 723
30 CALL IOTIMEOUT(ISC, 5)
35 CALL IOREMOTE(ISC)                ' REN on, so the meter obeys its commands
40 CALL IOCLEAR(DVM)
50 CALL IOOUTPUTS(DVM, "KM01F1RAN5T4")   ' clear status, SRQ on data ready, DC volts, hold
60 CALL IOOUTPUTS(DVM, "T3")             ' trigger one reading
70 T0 = TIMER
80 CALL IOSTATUS(ISC, 1, S)              ' condition 1 = state of the SRQ line
90 IF S = 0 AND TIMER - T0 < 5 THEN GOTO 80
100 IF S = 0 THEN PRINT "No SRQ within 5 seconds": GOTO 160
110 CALL IOSPOLL(DVM, R)                 ' serial poll: why did it ask? (also clears SRQ)
120 PRINT "Status byte"; R; "= "; BIN$(R)
130 IF (R AND 65) = 65 THEN PRINT "RQS (64) + data ready (1)"
140 CALL IOENTER(DVM, V)
150 PRINT "Reading:"; V
160 CALL IOOUTPUTS(DVM, "KM00T1"): CALL IOLOCAL(DVM)
170 END
