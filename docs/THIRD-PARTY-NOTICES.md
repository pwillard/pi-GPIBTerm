# Third-party credits and notices

pi-GPIBTerm v2.0.5

This project builds on other people's hardware, software, documentation and research. This file
says what was used, where it came from, how it was used, and under which license. The license
details were checked against each project's published license file (November 2026).

## This project's license

pi-GPIBTerm is free software, released under the **GNU General Public License version 3 only**
(SPDX `GPL-3.0-only`). The full text is in `LICENSE` in the project's root folder.

That license was chosen to match the most restrictive license among the sources the project is
based on:

| Source | License | Fits under GPL-3.0-only |
|--------|---------|-------------------------|
| pyAsyncHP3478A (copied test data) | GPL-3.0-only (its `pyproject.toml`) | yes: the same license, and the most restrictive |
| linux-gpib (the `gpib` module the programs import) | GPL-2.0-or-later (its source headers) | yes: "or later" allows version 3 |
| Tom Verbeure's hp3478a_calibration | BSD-2-Clause | yes, with its notice kept (`LICENSES/`) |
| PyMeasure | MIT | yes (nothing copied) |
| Vinay Shanbhag's hp3478a | treated as public domain (see section 4) | yes |
| gpib4pi board | TAPR Open Hardware License | not involved: that license covers the board design, which nothing here is derived from |

Two exceptions keep their own terms: Tom Verbeure's material keeps its BSD notice, and
`pi/examples/manual_example.bas` is Hewlett-Packard's program (section 3).

---

## 1. Hardware

### gpib4pi GPIB board (lsi-gpib4pi-2.x)

- **By:** Lightside Instruments AS, Norway (Vladimir Vassilev). Copyright 2019 Lightside Instruments AS.
- **Where:** https://lightside-instruments.com/product/gpib4pi/ and
  https://github.com/lightside-instruments/gpib4pi
- **License:** TAPR Open Hardware License v1.0. OSHWA certified open hardware, UID NO000003.
- **Used for:** the GPIB interface this project runs on. The board facts in
  `pi-GPIBTerm-Setup-Guide.md` (parts, revisions, pin use) come from its bill of materials,
  CHANGELOG and schematic, and from Lightside's quick start guide
  (https://www.hackster.io/lightside-instruments/the-gpib4pi-gpib-for-raspberry-pi-shield-4b3e9a).
  No design files are included here.

### elektronomikon GPIB board

- **By:** Thomas Klima (http://elektronomikon.org).
- **Used for:** the gpib4pi is based on its pinout and schematic, which the `gpib_bitbang` driver
  was written for. It is credited here because the pin map in the setup guide is that design's.

## 2. Software this project uses (not included)

These are installed on the Pi by `install.sh` (through `pi/setup_pi.sh`). Nothing from them is
copied into this project.

### linux-gpib

- **What:** the Linux GPIB driver and library: the `gpib_bitbang` kernel module, `gpib_config`,
  `ibterm` and the `gpib` Python module that every program here talks to.
- **Where:** https://linux-gpib.sourceforge.io/, built from Lightside Instruments' Debian
  packaging, https://github.com/lightside-instruments/gpib-debian (branch `debian/4.3.6-lsi8`).
- **License:** GNU General Public License version 2 (the COPYING files in that repository).
- **gpib_bitbang driver:** copyright 2016 Thomas Klima, developed at the Institute of Sensor and
  Actuator Systems, Technical University of Vienna. It was extended by Marcello Carla',
  Department of Physics, University of Florence. The GPIO pin map table in the setup guide is
  taken from its source.
- **Python binding:** the list of functions `hpiblib.py` relies on was checked against the
  binding's source (`linux-gpib-user/language/python/gpibinter.c`).

### Raspberry Pi OS and Python

The programs run on Raspberry Pi OS (Raspberry Pi Ltd) and its Python 3 (Python Software
Foundation License). They use only Python's standard library plus linux-gpib's `gpib` module.

## 3. Documentation

### HP-IB Command Library Reference

- **What:** *HP-IB Command Library for MS-DOS* reference manual, Hewlett-Packard part
  82990-90001, Edition 2, June 1986. Copyright 1986 Hewlett-Packard Company, Corvallis
  Workstation Operation. All rights reserved by Hewlett-Packard.
- **Where:** a scanned copy is at the Internet Archive,
  https://archive.org/details/hp-ib-command-library-reference (uploaded by nmretrolab.org). The
  Archive lists no license for it, so this project only links to it and includes no copy.
- **Used for:**
  - The HP-IB Terminal re-implements the library's command set from this manual: command names,
    parameter order, select-code/device addressing and error numbers.
  - The `HELP LIBRARY` texts summarise its chapter 2 syntax reference, in new wording.
  - `pi/examples/manual_example.bas` is a transcription of the example program on its pages 2-6
    to 2-12. It remains Hewlett-Packard's work and is not covered by this project's GPL. It is
    included so the manual's example can be run as printed, and it says so in its first line.

### HP 3478A

The HP 3478A multimeter, its command codes and its manuals are Hewlett-Packard's. The meter's
codes are used here as HP published them.

## 4. HP 3478A calibration memory research and test data

How the 3478A stores its calibration was not published by HP. The calibration tools here
(the HP 3478A module's `pi/instruments/hp3478a/hp3478a_cal.py` and `examples/3478a_calsave.bas`) were written for this project, following
and cross-checking the work below. No code was copied from it. Three files in `dev/` are copies
of other people's calibration dumps, used as test data.

### Tom Verbeure: hp3478a_calibration

- **Where:** https://github.com/tomverbeure/hp3478a_calibration, and Tom's blog posts on the 3478A.
- **License:** BSD 2-Clause, copyright 2022 Tom Verbeure. Full text: `LICENSES/BSD-2-Clause-tomverbeure.txt`.
- **Used for:**
  - The memory layout, the `W` (read) and `X` (write) commands, the checksum rule and the raw
    `.bin` file format.
  - The battery-replacement advice in the setup guide.
- **Copied:**
  - `dev/tomverbeure_calram.txt` is the calibration dump printed in the project's README.
  - `tom_checksums()` in `dev/run_tests.py` reproduces the logic of his `verify_checksum()`.

### PyMeasure: HP 3478A instrument driver

- **Where:** https://github.com/pymeasure/pymeasure
- **License:** MIT, copyright 2013-2026 PyMeasure Developers.
- **Used for:** cross-checking the calibration commands and the CAL ENABLE status bit. Nothing
  copied.

### Patrick Baus: pyAsyncHP3478A

- **Where:** https://github.com/PatrickBaus/pyAsyncHP3478A
- **License:** GNU General Public License version 3 only (`GPL-3.0-only` in its `pyproject.toml`;
  its source files say "version 3 or later"). Copyright 2021 Patrick Baus. Full text: `LICENSE`.
- **Used for:** cross-checking, and the 16 x 16 text dump format that the `.txt` backups use.
- **Copied:** `dev/sample_calram.txt` is that project's `examples/calram_example.bin`, under its
  GPL-3.0-only license, which this project shares. Nothing else was copied.

### Vinay Shanbhag: hp3478a

- **Where:** https://github.com/vinayshanbhag/hp3478a
- **License:** the repository has no license file. Its material is treated as **public domain**
  by this project's owner. That is an assumption made for this project, not a statement by the
  author.
- **Used for:** a third decoding check: his README lists the decoded offset and gain of every
  entry in his dump.
- **Copied:**
  - `dev/vinayshanbhag_calram.bin` is his `hp3478a_2619A46970_cal_data_dump.bin`.
  - `VINAY_EXPECTED` in `dev/run_tests.py` holds the values from his README.

## 5. Ideas and styles borrowed (no code)

- **GW-BASIC** (Microsoft): the HP-IB Terminal's BASIC follows its statements, functions and
  editing commands. Its interpreter was written from scratch for this project.
- **DEC VMS HELP** (Digital Equipment Corporation, OpenVMS): the HP-IB Terminal's `HELP` follows
  its topic tree, abbreviations and `Topic?` / `Subtopic?` prompts.

## 6. Tools used to build and test (not included)

- **pandoc** (John MacFarlane and contributors, GPL-2.0-or-later) and **Microsoft Edge** make the
  PDF and HTML guides (`docs/build_docs.ps1`).
- **uv** (Astral, MIT/Apache-2.0) runs the tests under several Python versions.
- **ShellCheck** (Vidar Holen and contributors, GPL-3.0) checks the shell scripts (`install.sh`, `pi/*.sh`).
- **OpenSSH** (the Windows client) copies files to the Pi in `pc/deploy.ps1`; Windows' `tar`
  builds the release package in `pc/make_kit.ps1`.

## 7. Images

The project contains no photographs or other third-party images. The guides' covers are plain
text. Photos of the gpib4pi board are on Lightside Instruments' product page,
https://lightside-instruments.com/product/gpib4pi/, which the README and the Setup Guide link to.

## 8. Trademarks

HP, Hewlett-Packard and HP-IB are trademarks of their owners. Raspberry Pi is a trademark of
Raspberry Pi Ltd. GW-BASIC and Microsoft Edge are trademarks of Microsoft Corporation.
VMS and OpenVMS are trademarks of their owners. They are used here only to name the products.
This project is not affiliated with or endorsed by any of these companies, or by the people
and projects credited above.
