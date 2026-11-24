5 REM SPDX-License-Identifier: GPL-3.0-only
10 REM Save the HP 3478A calibration RAM to files. READ ONLY: it never writes to the meter.
20 REM It writes the same files as "hp3478a_cal.py backup", so hp3478a_cal.py can verify
30 REM and restore from them:
40 REM   calram_<date>_<time>.txt       16 lines of 16 characters '@'..'O' (64 + nibble)
50 REM   calram_<date>_<time>.bin       256 raw values 0-15 (Tom Verbeure's format)
60 REM   calram_<date>_<time>.info.txt  the decoded table, for people to read
70 REM The RAM is read twice; the files are only written if both reads are the same.
80 REM Files go into the folder in DIR$ (created if needed). Copy them off the Pi!
90 DVM = 723: ISC = 7: DIR$ = "backups"
100 OPTION BASE 0
110 DIM A(255), B(255), N(255), NAME$(18), LN$(18)
120 FOR E = 0 TO 18: READ NAME$(E): NEXT E
130 DATA "30 mV DC", "300 mV DC", "3 V DC", "30 V DC", "300 V DC", "(unused)", "V AC"
140 DATA "30 ohm", "300 ohm", "3 kohm", "30 kohm", "300 kohm", "3 Mohm", "30 Mohm"
150 DATA "300 mA DC", "3 A DC", "(unused)", "300 mA/3 A AC", "(unused)"
160 REM ---------------------------------------------------------- read the RAM twice
170 ON ERROR GOTO 1500
180 CALL IOTIMEOUT(ISC, 3)
185 CALL IOREMOTE(ISC)                      ' REN on: in local the meter ignores every command
190 CALL IOCLEAR(DVM)
200 CALL IOOUTPUTS(DVM, "T4")               ' trigger hold: no readings get in the way
205 GOSUB 1400                              ' throw away a reading finished before T4
210 CALL IOEOL(ISC, "", 0)                  ' W is a binary command: send it exactly, no CR/LF
220 PRINT "Reading calibration RAM (pass 1)..."
230 FOR I = 0 TO 255
240 GOSUB 1000: A(I) = C
250 IF I MOD 64 = 63 THEN PRINT "  read"; I + 1; "of 256"
260 NEXT I
270 PRINT "Reading calibration RAM (pass 2, check)..."
280 FOR I = 0 TO 255: GOSUB 1000: B(I) = C: NEXT I
290 GOSUB 1100                              ' meter back to normal
300 ON ERROR GOTO 0
310 D = 0
320 FOR I = 0 TO 255
330 IF A(I) <> B(I) THEN D = D + 1
340 NEXT I
350 IF D = 0 THEN GOTO 380
360 PRINT "The two reads differ in"; D; "place(s). Check the cable and try again."
370 PRINT "Nothing was saved.": END
380 REM ---------------------------------------------------------- decode the 19 entries
390 FOR I = 0 TO 255: N(I) = A(I) - 64: NEXT I
400 BAD = 0
410 H$ = "#   range              offset        gain  checksum"
420 PRINT: PRINT "Address 0 (r/w check nibble):"; N(0)
430 PRINT H$
440 FOR E = 0 TO 18
450 GOSUB 1200
460 PRINT LN$(E)
470 NEXT E
480 IF BAD = 0 THEN R$ = "all used entries valid" ELSE R$ = "INVALID checksum in" + STR$(BAD) + " used entry(s)"
490 PRINT "Result: "; R$
500 REM ---------------------------------------------------------- pick a file name not in use
510 D$ = DATE$: T$ = TIME$
520 STEM$ = "calram_" + MID$(D$, 7, 4) + LEFT$(D$, 2) + MID$(D$, 4, 2)
530 STEM$ = STEM$ + "_" + LEFT$(T$, 2) + MID$(T$, 4, 2) + RIGHT$(T$, 2)
540 IF DIR$ = "" THEN GOTO 580
550 ON ERROR GOTO 1600
560 MKDIR DIR$                              ' error 75 = it is already there, which is fine
570 ON ERROR GOTO 0: STEM$ = DIR$ + "/" + STEM$
580 F$ = STEM$: K = 1
590 ON ERROR GOTO 1700
600 OPEN F$ + ".txt" FOR INPUT AS #1        ' opens only if the file exists ...
610 CLOSE #1
620 K = K + 1: F$ = STEM$ + "_" + MID$(STR$(K), 2): GOTO 600
630 ON ERROR GOTO 0                         ' ... so we come here when the name is free
640 REM ---------------------------------------------------------- write the three files
650 OPEN F$ + ".txt" FOR OUTPUT AS #1
660 FOR R = 0 TO 15: L$ = ""
670 FOR K = 0 TO 15: L$ = L$ + CHR$(A(R * 16 + K)): NEXT K
680 PRINT #1, L$: NEXT R
690 CLOSE #1
700 OPEN F$ + ".bin" FOR OUTPUT AS #2
710 FOR I = 0 TO 255: PRINT #2, CHR$(N(I));: NEXT I
720 CLOSE #2
730 OPEN F$ + ".info.txt" FOR OUTPUT AS #3
740 PRINT #3, "HP 3478A calibration RAM backup"
750 PRINT #3, "Saved: "; DATE$; " "; TIME$; "  device address:"; DVM; " tool: hpibterm 3478a_calsave.bas"
760 PRINT #3, ""
770 PRINT #3, "Address 0 (r/w check nibble):"; N(0)
780 PRINT #3, H$
790 FOR E = 0 TO 18: PRINT #3, LN$(E): NEXT E
800 PRINT #3, "Result: "; R$
810 CLOSE #3
820 REM ---------------------------------------------------------- read the .txt back to be sure
830 OK = -1
840 OPEN F$ + ".txt" FOR INPUT AS #1
850 FOR R = 0 TO 15: LINE INPUT #1, L$
860 IF LEN(L$) <> 16 THEN OK = 0: GOTO 890
870 FOR K = 0 TO 15: IF ASC(MID$(L$, K + 1, 1)) <> A(R * 16 + K) THEN OK = 0
880 NEXT K
890 NEXT R
900 CLOSE #1
910 IF NOT OK THEN PRINT "The saved file does not read back correctly - do not rely on it!": END
920 PRINT
930 PRINT "Saved and checked: "; F$; ".txt"
940 PRINT "                   "; F$; ".bin"
950 PRINT "                   "; F$; ".info.txt"
960 IF BAD THEN PRINT "WARNING: the meter's RAM already has invalid entries (the battery may be weak or flat)."
970 PRINT "Copy these files somewhere safe (PC, USB stick) - not only on the Pi."
980 PRINT "To check the meter later:  sudo python3 hp3478a_cal.py verify "; F$; ".txt"
990 END
1000 REM ---------------------------------------------------------- read address I into C
1005 RT = 0                                  ' tries so far
1010 CALL IOOUTPUTS(DVM, "W" + CHR$(I))      ' W + the address as one raw byte
1020 CALL IOENTERS(DVM, R$, 1, L)            ' the reply is one character: 64 + the nibble
1030 C = -1: IF L = 1 THEN C = ASC(R$)
1040 IF C >= 64 AND C <= 79 THEN RETURN
1042 RT = RT + 1: IF RT >= 3 THEN GOTO 1050  ' something else came back, e.g. a reading:
1044 GOSUB 1400: GOTO 1010                   ' throw it away and ask again
1050 PRINT "Unexpected reply "; SHOW$(R$); " at address"; I; "- nothing was saved."
1060 GOSUB 1100: END
1100 REM ---------------------------------------------------------- meter back to normal
1110 CALL IOEOL(ISC, CHR$(13) + CHR$(10), 2)  ' CR/LF line ends again
1120 CALL IOOUTPUTS(DVM, "T1")               ' free-running readings
1130 CALL IOLOCAL(DVM)                       ' front panel works again
1140 RETURN
1200 REM ---------------------------------------------------------- decode entry E into LN$(E)
1210 REM Each entry is 13 nibbles: 6 offset digits, 5 gain digits, 2 checksum nibbles.
1220 P = 1 + E * 13: S = 0: OFF = 0: G = 0
1230 FOR K = 0 TO 10: S = S + N(P + K): NEXT K
1240 FOR K = 0 TO 5: OFF = OFF * 10 + N(P + K): NEXT K
1250 IF OFF >= 900000 THEN OFF = OFF - 1000000     ' 9xxxxx means a negative offset
1260 FOR K = 6 TO 10
1270 X = N(P + K): IF X >= 8 THEN X = X - 16       ' gain digits are signed (-8..7)
1280 G = G * 10 + X
1290 NEXT K
1300 CK = 16 * N(P + 11) + N(P + 12)
1310 IF 255 - (S AND 255) = CK THEN ST$ = "ok" ELSE ST$ = "BAD"
1320 IF ST$ = "BAD" AND NAME$(E) = "(unused)" THEN ST$ = "(unused, ignored)"
1330 IF ST$ = "BAD" THEN BAD = BAD + 1
1340 W$ = MID$(STR$(1000000 + G), 2)              ' gain = 1 + G / 1000000, 6 decimals
1350 IF LEN(W$) = 6 THEN W$ = "0" + W$
1360 GA$ = LEFT$(W$, 1) + "." + RIGHT$(W$, 6)
1370 LN$(E) = LEFT$(MID$(STR$(E), 2) + "    ", 4) + LEFT$(NAME$(E) + SPACE$(16), 16)
1380 LN$(E) = LN$(E) + RIGHT$(SPACE$(9) + STR$(OFF), 9) + RIGHT$(SPACE$(12) + GA$, 12) + "  " + ST$
1390 RETURN
1400 REM ---------------------------------------------------------- empty the meter's output
1405 REM Reads (and throws away) whatever the meter still has to send, until it has nothing
1410 REM left: then the read times out after 0.5 s, which is what we wait for.
1415 ON ERROR GOTO 1460: CALL IOTIMEOUT(ISC, .5): DN = 0
1420 CALL IOENTERS(DVM, J$, 80, L): DN = DN + 1
1430 IF DN < 10 THEN GOTO 1420
1440 CALL IOTIMEOUT(ISC, 3): ON ERROR GOTO 1500: RETURN
1460 RESUME 1440
1500 REM ---------------------------------------------------------- error while reading
1510 IF ERR = PCIB.BASERR THEN PRINT "HP-IB error"; PCIB.ERR; "- "; PCIB.ERR$; " (line"; ERL; ")"
1520 IF ERR <> PCIB.BASERR THEN PRINT "Error"; ERR; "in line"; ERL
1530 PRINT "Is the meter switched on, at address 23 and connected? Nothing was saved."
1540 RESUME 1550
1550 ON ERROR GOTO 0: GOSUB 1100: END
1600 REM ---------------------------------------------------------- MKDIR failed
1610 IF ERR = 75 THEN RESUME NEXT                   ' the folder already exists: fine
1620 PRINT "Cannot create folder "; DIR$; " (error"; ERR; ")": END
1700 REM ---------------------------------------------------------- OPEN FOR INPUT failed
1710 IF ERR = 53 THEN RESUME 630                    ' no such file: the name is free
1720 PRINT "Cannot check file "; F$; ".txt (error"; ERR; ")": END
