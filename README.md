# pi-GPIBTerm

**pi-GPIBTerm** turns a **Raspberry Pi** with a **Lightside Instruments gpib4pi** board into an
HP-IB (GPIB / IEEE-488) workstation for your test equipment. Version 2.0.0.

- **HP-IB Terminal**, a programming environment that works like HP's 1986 **82990A HP-IB
  Command Library** with GW-BASIC.
  - Type library commands directly (`IOOUTPUTS 722, "..."`, `IOENTER 722`), or write, save and
    run line-numbered BASIC programs.
  - DEC VMS-style `HELP` covers every command.
  - A built-in simulated bus lets you practise with no hardware.
  - Programs written for the original library run with few or no changes.
- **Works with any GPIB instrument.** `SCAN` finds what is on the bus.
- **A menu** offers everything, so you don't need to remember commands.
- **Instrument modules** add ready-made tools for particular instruments. The first is for the
  **HP 3478A multimeter**: readings and CSV logging, and calibration RAM backup, verify and
  restore (do the backup before the meter's internal battery dies). Writing a module for
  another instrument is described in the setup guide.

Status: the HP-IB Terminal and the HP 3478A module run on real hardware. Readings and the
calibration backup are confirmed on a real meter. Service requests (SRQ) and verify/restore have
been tested only with the simulator so far.

**About the gpib4pi:** it is open hardware for the Pi's 40-pin header, driven by linux-gpib's
GPIO bit-banging driver. It is not a plug-and-play USB adapter: it needs a kernel module, a
linux-gpib configuration and the right GPIO pin map, and `install.sh` sets up all three. The Pi
must be the bus's **system controller**, and the driver has **no parallel poll** and no
adjustable T1 timing. The setup guide explains what that means in practice.

## What you need


| | |
|---|---|
| Raspberry Pi | **Pi Zero 2 W** (used here), or a Pi Zero W, 3, 4 or 5 |
| GPIB board | Lightside Instruments **gpib4pi** (lsi-gpib4pi-2.x): product page with photos https://lightside-instruments.com/product/gpib4pi/, board design files https://github.com/lightside-instruments/gpib4pi |
| Operating system | **Raspberry Pi OS Lite**, a fresh install. The **32-bit** image is used here, and it is required on an original Pi Zero W. |
| Instruments | Any HP-IB / GPIB instrument |
| Network | Internet access during installation (it downloads and builds linux-gpib) |

## Install on a fresh Raspberry Pi OS Lite

1. With **Raspberry Pi Imager**, write Raspberry Pi OS Lite to the SD card. In its settings, set
   a user name and password, your Wi-Fi, and **enable SSH**.
2. Fit the gpib4pi board, start the Pi, and log in (over SSH or with a keyboard).
3. Run:

   ```bash
   sudo apt-get update && sudo apt-get -y install git
   git clone https://github.com/<your-account>/pi-GPIBTerm.git
   cd pi-GPIBTerm
   sudo bash install.sh
   ```

   The first installation builds linux-gpib and the board's driver. That takes **an hour or
   more on a Pi Zero 2 W** and a few minutes on a Pi 4. For the old v1.1 board, use
   `sudo PIN_MAP=gpib4pi-1.1 bash install.sh`.
4. **Log out and back in** (this lets you use the GPIB board without `sudo`), then type:

   ```bash
   pi-gpibterm
   ```

```
 pi-GPIBTerm 2.0.0  -  HP-IB / GPIB on a Raspberry Pi
 ------------------------------------------------------------------------------
  1  HP-IB Terminal                (HP-IB programming environment, HELP inside)
  2  HP-IB Terminal - simulator    (practise without an instrument)
  3  Run a BASIC program           (your programs and the examples)
  4  Find instruments on the bus   (SCAN)

  Instrument modules:
  H  HP 3478A multimeter           (readings, calibration RAM backup/restore)

  9  Check the installation        (driver, /dev/gpib0, instruments on the bus)
  R  Rebuild the GPIB driver       (after a kernel update)
  D  Where are the guides (PDF)?
  Q  Quit
```

**Have an HP 3478A?** The first thing to do is choose `H` and then `2`, the calibration
backup. Then copy `~/pi-gpibterm/backups` to somewhere other than the Pi.

## What gets installed where

| Where | What |
|---|---|
| `/opt/pi-gpibterm` | The programs, the example BASIC programs, the instrument modules (`instruments/`) and the guides (`docs/*.pdf`) |
| `/usr/local/bin` | Commands: `pi-gpibterm` (menu), `hpib` (HP-IB Terminal), `gpib-driver-rebuild`, and the modules' commands (`hp3478a-log`, `hp3478a-cal`) |
| `~/pi-gpibterm` | **Your folder:** `menu`, `programs/` (your BASIC programs), `backups/` and `logs/` (what the modules save), `pi-gpibterm.conf` (settings) |
| system | linux-gpib, `/usr/etc/gpib.conf`, `gpib.service` (loads the driver at boot), `pi-gpibterm-driver-rebuild.service`, and access to `/dev/gpib0` for the `gpib` group |

**Updating:** run `cd pi-GPIBTerm && git pull && sudo bash install.sh`. This takes seconds
once linux-gpib is installed. It never overwrites anything in `~/pi-gpibterm`. An installation
of the earlier hp3478a-gpib (1.x) is replaced, and its `~/hp3478a` folder becomes
`~/pi-gpibterm`.

**Kernel updates:** the driver is built for one Linux kernel. After `apt upgrade` installs a
new kernel, the Pi rebuilds the driver by itself during the next boot, so that boot takes a
few minutes longer on a Pi Zero. To do it by hand, run `gpib-driver-rebuild`, or choose `R`
in the menu.

**Removing:** `sudo bash uninstall.sh` removes the programs and commands, and
`sudo bash uninstall.sh --driver` also removes the services. Your folder `~/pi-gpibterm` is
always kept.

## Guides

- [Introduction to the HP-IB Terminal](HP-IB-Terminal-Introduction.pdf), a first session step by step
- [HP-IB Terminal Guide](HP-IB-Terminal-Guide.pdf), the reference
- [pi-GPIBTerm Setup Guide](pi-GPIBTerm-Setup-Guide.pdf): installation, the gpib4pi board and
  its pin map, the driver, instrument modules, troubleshooting
- [HP 3478A Module Guide](HP3478A-Module-Guide.pdf): the meter's commands, readings,
  calibration backup and battery replacement
- [Third-party credits and notices](THIRD-PARTY-NOTICES.pdf)

The examples in the guides and in `HELP` use device 723, where the simulator has an HP 3478A.
Use your own instrument's address and commands instead.

HP's original manual, *HP-IB Command Library Reference* (82990-90001, 1986), is at the
Internet Archive: https://archive.org/details/hp-ib-command-library-reference

## For developers

| Folder | Contents |
|---|---|
| `pi/` | The generic core that runs on the Pi (Python 3, standard library only, plus linux-gpib's `gpib` module) |
| `pi/instruments/` | Instrument modules, one folder each (`hp3478a/`): `module.py` (the menu section), `COMMANDS`, tools, `examples/` |
| `docs/` | Guide sources (Markdown), and `build_docs.ps1`, which builds the PDFs |
| `dev/` | Tests: `python dev/run_tests.py` (any OS, uses simulators) and `bash dev/test_install.sh` (Linux: installs into a scratch folder and drives the menu) |
| `pc/` | Windows tools: `deploy.ps1` (install to the Pi over SSH) and `make_kit.ps1` (builds the release package) |

The HP-IB Terminal also runs on a PC without any hardware: `python pi/hpibterm.py --sim`.

## License

pi-GPIBTerm is free software under the **GNU General Public License version 3**
(`GPL-3.0-only`); see [LICENSE](LICENSE). It builds on the work of Lightside Instruments (the
[gpib4pi board](https://github.com/lightside-instruments/gpib4pi)) and linux-gpib, HP's Command Library, and (for the HP 3478A module) Tom Verbeure, PyMeasure,
Patrick Baus and Vinay Shanbhag; see [the credits and notices](docs/THIRD-PARTY-NOTICES.md).
`pi/examples/manual_example.bas` is HP's example program and is not covered by the GPL.

HP and HP-IB are trademarks of their owners. This project is not affiliated with HP, Keysight
or Lightside Instruments.
