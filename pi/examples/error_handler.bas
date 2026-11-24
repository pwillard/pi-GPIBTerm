5 REM SPDX-License-Identifier: GPL-3.0-only
10 REM Error handling the way SETUP.BAS does it (manual pages 2-14 and 2-15)
20 ON ERROR GOTO 400
30 OPTION ERRORS CONTINUE         ' original behaviour: test PCIB.ERR after each CALL
40 ISC = 7: DEV = 715             ' nothing at address 15, so this will time out
50 CALL IOTIMEOUT(ISC, 1)
60 CALL IOENTERS(DEV, A$, 80, N)
70 IF PCIB.ERR <> NOERR THEN ERROR PCIB.BASERR
80 PRINT "Got: "; A$
90 END
400 REM Error handling routine
410 IF ERR = PCIB.BASERR THEN GOTO 425
420 PRINT "BASIC error #"; ERR; " occurred in line "; ERL: STOP
425 TMPERR = PCIB.ERR
430 IF TMPERR = 0 THEN TMPERR = PCIB.GLBERR
435 PRINT "PC Instrument error #"; TMPERR; " detected at line "; ERL
440 PRINT "Error: "; PCIB.ERR$
445 END
