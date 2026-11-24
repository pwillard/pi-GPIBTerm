5 REM SPDX-License-Identifier: GPL-3.0-only
10 REM Take 10 DC volt readings from an HP 3478A at address 23 (device address 723)
20 ISC = 7: DVM = 723
30 CALL IOTIMEOUT(ISC, 5)
35 CALL IOREMOTE(ISC)                ' REN on, so the meter obeys its commands
40 CALL IOCLEAR(DVM)
50 CALL IOOUTPUTS(DVM, "F1RAZ1N5T4")     ' DC volts, autorange, autozero, 5.5 digits, trigger hold
60 FOR I = 1 TO 10
70 CALL IOOUTPUTS(DVM, "T3")             ' one single trigger ...
80 CALL IOENTER(DVM, V)                  ' ... and read the result
90 IF ABS(V) >= 9E+09 THEN PRINT I, "OVERLOAD" ELSE PRINT I, V; "V"
100 NEXT I
110 CALL IOOUTPUTS(DVM, "T1")            ' back to free running
120 CALL IOLOCAL(DVM)                    ' and to front-panel control
130 END
