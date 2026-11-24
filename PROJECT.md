# pi-GPIBTerm (v2.0.7) - formerly hp3478a-gpib

2.0.0: pi-GPIBTerm (renamed from hp3478a-gpib, generic): core in pi/, HP 3478A tools as instrument module pi/instruments/hp3478a (module.py adds menu section H; COMMANDS -> hp3478a-cal/hp3478a-log; examples found as examples/...). Paths /opt/pi-gpibterm, ~/pi-gpibterm, commands pi-gpibterm/hpib/gpib-driver-rebuild; gpib.conf has no device entry; install.sh migrates a 1.x install (~/hp3478a -> ~/pi-gpibterm, address -> HP3478A_ADDRESS).

1.6.0: standalone install for GitHub: install.sh/uninstall.sh (programs /opt/hp3478a, commands hp3478a/hpib/hp3478a-cal/hp3478a-log/hp3478a-driver-rebuild, user folder ~/hp3478a with menu/backups/logs/programs), menu pi/hp3478a_menu.py, boot-time driver rebuild service + headers metapackage, gpib group + udev rule, README.md, pc/make_kit.ps1 (dist/*.tar.gz), deploy.ps1 now installs the kit. Tests: dev/test_install.sh + test_menu_pty.py + test_kit.sh (Linux).

1.5.10: hardware results recorded - cal RAM backup of the real meter succeeded.

1.5.9: REN fix - set at start-up, IORESET pulses then sets it, examples call IOREMOTE, cal/log tools set it; sims ignore commands in local; tests reproduce the hardware failure.

1.5.8: deploy.ps1 default Pi user is now willard (was pi).

1.5.7: cal RAM read fix from the first hardware run: drain a waiting reading after T4 and on a bad W reply (retry 3x) in 3478a_calsave.bas and hp3478a_cal.py; sims model it (HPIB_SIM_STALE_READING, FAKE_STALE); libgpib END-on-EOI warning silenced.

1.5.6: first real-hardware confirmation recorded (IOOUTPUTS/IOENTER reading from the 3478A).

1.5.5: ASK without the comma (ASK 723 "H1") now says the comma is missing and shows ASK 723, "H1".

1.5.4: setup_pi.sh rebuilds only the kernel module (module-assistant gpib-modules-source) when linux-gpib is installed but gpib_bitbang is missing for uname -r (kernel updated). User's Pi hit this on 6.12.115+rpt-rpi-v7 (v7 kernel = Zero 2 W/Pi 2/3, not the original Zero W).

1.5.3: driver-not-loaded diagnosis: hpiblib.Library.driver_problem() (missing /dev/gpibN / no permission); banner warning; 'Bad file descriptor' -> ESEL with the fix. Setup guide troubleshooting entry (gpib.service, kernel updated after build).

1.5.2: documentation moved to docs\ (.md sources, .html copies, cover photo, build_docs.ps1, doc-print.css); the PDFs are still built into the project root. Test enforces the layout.

1.5.1: cover page on every PDF/HTML guide from "Compact Raspberry Pi GPIB Bench Stack.png" (build_docs.ps1 -Cover; @page :first full-bleed in doc-print.css).

1.5.0: project licensed GPL-3.0-only (LICENSE; SPDX header in every source file, test-enforced) to match the most restrictive source (pyAsyncHP3478A). HP manual linked to archive.org, local copy in ignored reference-local\. Vinay's dump treated as public domain (owner's decision). manual_example.bas marked as HP's.

1.4.3: THIRD-PARTY-NOTICES.md + LICENSES\ (Tom Verbeure BSD-2); Credits sections; HELP CREDITS.

1.4.2: PDF versions of the three guides; rebuild with pc\build_docs.ps1 (pandoc -> HTML + pc\doc-print.css -> Edge headless print-to-PDF; temp file then copy).

1.4.1: setup guide section 1 documents the hardware: lsi-gpib4pi-2.x board, revisions/pin_map, GPIO pin map, Pi/OS/linux-gpib versions, an installation record; deploy.ps1 check prints the record items.

1.4.0: examples/3478a_calsave.bas (cal RAM backup in BASIC, read only, hp3478a_cal.py file format); MKDIR/KILL statements; simulator has cal RAM + W command.

1.3.3: HELP prompts: TOP/^ jumps to the top level, names are found from any level, Ctrl+C leaves, hint shown.

1.3.2: added HP-IB-Terminal-Introduction.md (+ .html via pandoc), a tutorial first session.

1.3.1: HELP rebuilt as a DEC VMS style topic tree (hpibhelp.TREE / Session); every command,
statement, function and library call has an entry (tests enforce it).

**Next resume action:** test the standalone install on real hardware: (1) fresh SD card with
Raspberry Pi OS Lite 32-bit -> `git clone` / release tarball -> `sudo bash install.sh` -> log in again
-> `hp3478a` menu items 9, 1, 5; (2) a later `apt upgrade` with a new kernel -> reboot -> check
hp3478a-gpib-rebuild.service rebuilt the driver. Before publishing: keep the GitHub clone URL in README.md, install.sh and
 docs/pi-GPIBTerm-Setup-Guide.md pointed at the public repository (repo pi-GPIBTerm).

**Hardware status (Nov 2026): SUCCESS** - 3478a_calsave.bas backed up the real meter's cal RAM
(two matching reads, 16/16 checksums ok; backups/calram_20261123_153548.*) after IOREMOTE 723.
Earlier: confirmed on the real bus - IOOUTPUTS 723 "F1RAN5T4" / "T3" +
IOENTER 723 returned 3.01355 (DC V). User's Pi: user willard, host GPIB, files in ~/gpib, kernel
6.12.115+rpt-rpi-v7 (v7 => probably Zero 2 W; model not yet confirmed). Fixed on it: gpib_bitbang
module missing after a kernel update (rebuilt with module-assistant). ROOT CAUSE (1.5.9) of the calsave failures: REN was off. hpiblib never set REN at start-up, and
BYE (finish -> IOLOCAL 7) clears it, so after the first session (REN on from gpib_config at boot)
the meter stayed in local: it ignored T4/W but answered reads (trace: readings after T4, W ->
reading). Fixed: Library sets REN at start-up, IORESET pulses REN (manual: "REN is cleared
(>10 uS)") then sets it, examples call IOREMOTE(ISC), hp3478a_cal.py/log.py call remote_enable;
both sims ignore commands while in local. The 1.5.7 drain/retry was a wrong guess but is kept
(harmless, 0.5 s).
3478a_calsave.bas first run on HW: "Unexpected reply "-" at address 0" - a reading
waiting after IOCLEAR+T4 came out ahead of the W reply; 1.5.7 drains the output (read until a
0.5 s timeout) after T4 and on any bad reply, retrying 3x (hp3478a_cal.py too). Also libgpib
printed "no support for END on EOI only yet" for IbcEndBitIsNormal: now tried once, quietly.
Still only simulator-tested:
the other commands, SRQ, parallel poll, examples, 3478a_calsave.bas. deploy.ps1 default user is willard
(1.5.8); host 192.168.1.200 and folder ~/hp3478a still differ from this Pi (~/gpib).

## Parts
- `pi\hp3478a_log.py`, `pi\hp3478a_cal.py` - logger and cal-RAM tool (see docs\gpib4pi-HP-multimeter-setup.md)
- `pi\hpibterm.py` - HP-IB Terminal (guide: docs\HP-IB-Terminal-Guide.md). Modules: `hpiblib.py` (26 HP 82990A
  commands on linux-gpib), `hpibbasic.py` (interpreter), `hpibhelp.py`, `hpib_sim.py` (simulated 3478A at 723)
- `pc\deploy.ps1` - push/setup/test/log/term/sim/backup/verify/restore/pull/shell
- `dev\run_tests.py` - all tests (run under 3.9/3.11/3.13/3.14 with `uv run --no-project --python X`)

## Hardware-dependent things to check first on the real bus
- `IOPPOLL` uses ctypes `ibrpp` from libgpib.so.0 (the Python binding has no parallel poll).
- `IOSTATUS 7,1/2` uses `iblines`; gpib_bitbang may not report every line as valid.
- END-vs-EOS detection relies on `ibconfig(IbcEndBitIsNormal, 0)`.
- Board-level (select-code) reads/writes after `IOSEND` addressing.

## Conventions
- Bump every version (VERSION, every `__version__`, deploy.ps1 header, guides) on each change.
- LF line endings for everything that goes to the Pi (tests check this).
