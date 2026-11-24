5 REM SPDX-License-Identifier: GPL-3.0-only
10 REM Log HP 3478A readings with time stamps to a CSV file
20 ISC = 7: DVM = 723
30 INPUT "Function (1=DCV 2=ACV 3=2W ohm 4=4W ohm 5=DCA 6=ACA)"; F
40 IF F < 1 OR F > 6 THEN PRINT "Please type 1 to 6": GOTO 30
50 INPUT "Number of readings (0 = until Ctrl+C)"; N
60 INPUT "Seconds between readings"; T
70 LINE INPUT "CSV file name (Enter = readings.csv): "; FILE$
80 IF FILE$ = "" THEN FILE$ = "readings.csv"
90 CALL IOTIMEOUT(ISC, 5)
95 CALL IOREMOTE(ISC)                ' REN on, so the meter obeys its commands
100 CALL IOCLEAR(DVM)
110 CALL IOOUTPUTS(DVM, "F" + MID$(STR$(F), 2) + "RAZ1N5T4")
120 OPEN FILE$ FOR APPEND AS #1
130 K = 0
140 WHILE N = 0 OR K < N
150 CALL IOOUTPUTS(DVM, "T3")
160 CALL IOENTER(DVM, V)
170 K = K + 1
180 IF ABS(V) >= 9E+09 THEN R$ = "OVERLOAD" ELSE R$ = MID$(STR$(V), 2)
190 PRINT DATE$; " "; TIME$, R$
200 PRINT #1, DATE$; " "; TIME$; ","; R$
210 IF T > 0 THEN SLEEP T
220 WEND
230 CLOSE #1
240 CALL IOOUTPUTS(DVM, "T1"): CALL IOLOCAL(DVM)
250 PRINT K; "reading(s) added to "; FILE$
260 END
