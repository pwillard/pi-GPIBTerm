# pi-GPIBTerm Setup Guide: GPIB on a Raspberry Pi with the Lightside gpib4pi

pi-GPIBTerm v2.0.7

pi-GPIBTerm turns a Raspberry Pi with a Lightside Instruments gpib4pi board into an HP-IB (GPIB)
workstation for any GPIB instrument: the HP-IB Terminal (an HP 82990A HP-IB Command Library
work-alike with BASIC), a menu, and instrument modules for particular instruments (so far the
HP 3478A multimeter, see `HP3478A-Module-Guide.md`). This guide covers installing it and the hardware.

The Lightside board ("gpib4pi") doesn't come with its own software. It uses the standard
**linux-gpib** driver (`gpib_bitbang`), which drives the GPIB lines directly from the Pi's GPIO pins.

References:
- Product page (Lightside Instruments AS, Norway): https://lightside-instruments.com/product/gpib4pi/
- Quick start guide: https://www.hackster.io/lightside-instruments/the-gpib4pi-gpib-for-raspberry-pi-shield-4b3e9a
  (the same text is at https://github.com/lightside-instruments/docs/tree/gpib4pi-guide)
- Board design files (KiCad, schematic, BOM, CHANGELOG): https://github.com/lightside-instruments/gpib4pi
- Lightside's linux-gpib packages: https://github.com/lightside-instruments/gpib-debian
- linux-gpib docs: https://linux-gpib.sourceforge.io/doc_html/supported-hardware.html

---

## 0. Install and use

Everything installs and runs on the Pi itself. No PC is needed.

**Install** on a fresh Raspberry Pi OS Lite. The details are in the project's `README.md`.

```bash
sudo apt-get update && sudo apt-get -y install git
git clone https://github.com/<your-account>/pi-GPIBTerm.git
cd pi-GPIBTerm && sudo bash install.sh
```

You can also download a release package instead of using git:
`tar xzf pi-GPIBTerm-<version>.tar.gz`, then `cd pi-GPIBTerm-<version>` and
`sudo bash install.sh`. The first installation builds linux-gpib (sections 2 and 3, done for
you) and takes an hour or more on a Pi Zero 2 W. Most of that time goes on building linux-gpib's
documentation formats, so a long quiet spell is normal. Running it again later updates the programs in seconds.
Log out and back in once afterwards, so you can use the GPIB board without `sudo`.

**Use** it by typing `pi-gpibterm` to open the menu. It offers the HP-IB Terminal (with an
instrument or the simulator), the BASIC programs, a bus scan, an installation check, a driver
rebuild, the guides (item `D`: shown as text in the terminal, so they work over SSH), and a
section for each instrument module. The same tools are also commands:

```bash
pi-gpibterm                     # the menu (or ~/pi-gpibterm/menu)
hpib                            # HP-IB Terminal;  hpib --sim  = practise without an instrument
gpib-driver-rebuild             # rebuild the driver by hand (after a kernel update)
hp3478a-log, hp3478a-cal        # the HP 3478A module's tools (HP3478A-Module-Guide.md)
```

**Where things are on the Pi:**

```
/opt/pi-gpibterm/                the programs, examples/*.bas, docs/*.pdf (install.sh keeps it current)
  instruments/<name>/            the instrument modules (hp3478a: its tools and examples)
/usr/local/bin/                  the commands above
~/pi-gpibterm/                   YOUR folder - install.sh never overwrites anything in it
  menu                           starts the menu
  programs/                      your own BASIC programs: SAVE "programs/name"
  backups/, logs/                what the instrument modules save (e.g. HP 3478A calibration backups)
  pi-gpibterm.conf               settings made in the menu (e.g. HP3478A_ADDRESS)
```

**After a kernel update** (`apt upgrade`), the driver must be rebuilt for the new kernel. The
Pi does this by itself on the next boot (`pi-gpibterm-driver-rebuild.service`), so that boot takes a
few minutes longer on a Pi Zero.

**To remove it:** `sudo bash uninstall.sh` (add `--driver` to also remove the services). Your
`~/pi-gpibterm` folder is kept.

### Pi Zero 2 W notes (and the original Zero W)

- This project runs on a **Raspberry Pi Zero 2 W**: quad-core 64-bit ARM (Cortex-A53, 1 GHz),
  512 MB of RAM, 2.4 GHz Wi-Fi. It runs **Raspberry Pi OS Lite (32-bit)**. The 64-bit image also
  works on the Zero 2 W, but the 32-bit one leaves more of its 512 MB free.
- The original **Zero W is ARMv6, 32-bit only**. It needs the 32-bit image, because the 64-bit
  one won't boot on it. It works too, just more slowly.
- In Raspberry Pi Imager, set a username/password, Wi-Fi (2.4 GHz only), and enable SSH.
- Give the Pi a fixed address, such as a DHCP reservation in your router. Then
  `ssh <user>@<address>` always finds it (`<hostname>.local` usually works too).
- Both have only 512 MB of RAM, so the installer raises swap to 1 GB for the build. The build
  takes an hour or more, and longer on the single-core Zero W. Running the programs afterwards
  is light.
- Python on the Pi is 3.11 (Bookworm) or 3.13 (Trixie). The programs use only the standard library plus
  linux-gpib's `gpib` module. They're tested with Python 3.9, 3.11, 3.13 and 3.14.

### Developing on a Windows PC (optional)

This is how the project was developed: edit and test on the PC, then install on the Pi over SSH.

```
pi-GPIBTerm\
  install.sh, uninstall.sh         the installer, run on the Pi
  README.md                        the project page on GitHub
  *.pdf                            the guides, built from docs\
  pi\                              everything that runs on the Pi (the generic core)
    gpibterm_menu.py               the menu (command pi-gpibterm)
    hpibterm.py                    HP-IB Terminal (+ hpiblib, hpibbasic, hpibhelp, hpib_sim .py)
    setup_pi.sh                    linux-gpib build, gpib.conf, services (install.sh runs it)
    gpib_driver_rebuild.sh         driver rebuild for a new kernel
    run.sh                         starts a program (with sudo if you can't use /dev/gpib0 yet)
    examples\*.bas                 example programs for the terminal
    instruments\hp3478a\           the HP 3478A module: module.py (its menu section), COMMANDS,
                                   hp3478a_log.py, hp3478a_cal.py, examples\*.bas
  docs\                            guide sources (*.md), HTML copies, build_docs.ps1, doc-print.css
  pc\deploy.ps1                    from the PC: install on the Pi, run there, fetch backups
  pc\make_kit.ps1                  builds the release package dist\pi-GPIBTerm-<version>.tar.gz
  dev\                             tests (run_tests.py; test_install.sh and test_kit.sh on Linux)
  LICENSE, LICENSES\               GNU GPL version 3, and third-party license texts
  backups\                         calibration backups copied back from the Pi
  reference-local\                 your own copies of manuals; ignored by git, never published
```

Everyday commands, in PowerShell from the project folder:

```powershell
$env:PI_GPIBTERM_USER = 'someone'   # only if your Pi username isn't willard (the default); host defaults to 192.168.1.200
# other Pi: -PiHost x.x.x.x  or  $env:PI_GPIBTERM_HOST = 'x.x.x.x'

.\pc\deploy.ps1 setup                  # full installation on the Pi (runs install.sh there)
.\pc\deploy.ps1 push                   # install the latest programs (install.sh --no-driver)
.\pc\deploy.ps1 check                  # Pi model, OS, Python, driver service, /dev/gpib0
.\pc\deploy.ps1 menu                   # the menu on the Pi
.\pc\deploy.ps1 term                   # push, then the HP-IB Terminal on the Pi
.\pc\deploy.ps1 sim                    # HP-IB Terminal on this PC with a simulated meter
.\pc\deploy.ps1 test                   # push, then take 5 DC volt readings
.\pc\deploy.ps1 backup                 # calibration backup on the Pi, copied to .\backups
.\pc\deploy.ps1 verify  -File calram_YYYYMMDD_HHMMSS.txt
.\pc\deploy.ps1 restore -File calram_YYYYMMDD_HHMMSS.txt   # CAL ENABLE on; type YES
.\pc\deploy.ps1 pull                   # fetch all backups from the Pi
.\pc\deploy.ps1 shell                  # SSH into the Pi
.\pc\make_kit.ps1                      # build the release package for GitHub
.\docs\build_docs.ps1                  # rebuild the PDF + HTML guides after editing a .md
```

Add `-Address N` for the HP 3478A module's meter address, or `-DryRun` to only print the ssh/scp commands.
`deploy.ps1` installs the same release package that `make_kit.ps1` builds, with the same
`install.sh`, so what you test is exactly what other people get. Test on the PC first:

```powershell
python dev\run_tests.py
wsl bash dev/test_install.sh           # if you have WSL: installs into a scratch folder, drives the menu
```

---

## 1. Hardware

### The setup used for this project

| Part | What is used |
|------|--------------|
| GPIB adapter | **Lightside Instruments gpib4pi**, board **lsi-gpib4pi-2.x** (2.1 is the current revision), from https://lightside-instruments.com/product/gpib4pi/ (EUR 39; also on Amazon as B0BY32HH4G; EAN 7090060720065) |
| Computer | **Raspberry Pi Zero 2 W** (quad-core Cortex-A53, 512 MB RAM, 2.4 GHz Wi-Fi) |
| Operating system | **Raspberry Pi OS Lite, 32-bit** (Bookworm or Trixie), no desktop; kernel `rpi-v7` |
| Network | Wi-Fi, fixed address **192.168.1.200** (DHCP reservation), SSH enabled |
| GPIB software | **linux-gpib 4.3.6** in Lightside's packaging, branch `debian/4.3.6-lsi8` of `gpib-debian` (4.3.5-lsi4 on Bullseye or older) |
| Driver | `gpib_bitbang` kernel module, default pin map (`elektronomikon`), loaded at boot by `gpib.service` |
| Python | Raspberry Pi OS's `python3` (3.11 on Bookworm, 3.13 on Trixie), plus `python3-gpib` from the build |
| Instrument | **HP 3478A** multimeter at GPIB address **23**; the Pi is the controller at address 0 |

Lightside's guide was written on a Pi 5 with 64-bit Trixie, and they say other models should also
work. This project uses a Zero 2 W with the 32-bit image (an original Zero W also works, and
needs the 32-bit image). The record at the end of this
section is for the actual versions on your Pi.

### About the gpib4pi board

Photos of the board, on its own and fitted to an instrument, are on Lightside's product page:
https://lightside-instruments.com/product/gpib4pi/

- **What it is:** a GPIB (IEEE-488) interface for the Raspberry Pi's 40-pin header. It has no
  processor of its own: the Pi drives the GPIB lines through its GPIO pins, using linux-gpib's
  `gpib_bitbang` driver. It is open hardware (KiCad files published, OSHWA certified UID NO000003,
  TAPR Open Hardware License).
- **On the board:**
  - an **SN75160BN** (data lines) and an **SN75161BN** (control lines), standard GPIB bus
    transceivers;
  - bus termination resistors with the IEEE-488 values (3.3 k / 6.2 k);
  - a red power LED and a green activity LED (the driver uses GPIO4 as its activity-LED output);
  - a 24-pin **male** GPIB connector, so it plugs straight into the instrument's GPIB socket;
  - a 2 x 20 socket for the Pi's header.
- **Form factor:** the board has the outline of a Raspberry Pi main board, not of a HAT,
  because of where the GPIB connector has to go. It has mounting holes for a Pi Zero.
- **In the box (boards bought after 2024-07-01):** 2 M3.5 stainless thumb screws to fasten the
  board to the instrument's GPIB socket, and a stackable 2 x 20 connector that raises the board
  above a full-size Pi (a Zero doesn't need it). The Pi itself is not included.
- **Power:** it takes its power from the Pi's header. The meter doesn't power anything.

### What to expect from the gpib4pi

- **It is not a plug-and-play USB adapter.** It needs a kernel module (linux-gpib's `gpib_bitbang`)
  built for your kernel, a linux-gpib configuration, and the right GPIO pin map for your board
  revision. `install.sh` does all three, and the Pi rebuilds the module by itself after a kernel
  update. It is still useful to know they are there when something goes wrong.
- **It controls many legacy GPIB instruments** from Linux: through pi-GPIBTerm, or from your own
  programs in Python (`import gpib`) or C (`libgpib`).
- **The Pi must be the system controller.** The bitbang driver can only act as the GPIB system
  controller (`master = yes` in `gpib.conf`). It cannot be a plain device on a bus run by another
  controller, such as a PC with a GPIB card. pi-GPIBTerm always works as the controller, so this
  only matters if you want to share a bus with another controller: don't.
- **No parallel poll.** The driver doesn't support parallel poll. `IOPPOLL` gives an error on the
  gpib4pi, although it works in the simulator. `IOPPOLLC` and `IOPPOLLU` still send their bus
  commands. To find out which instrument wants attention, use service requests instead:
  `IOSTATUS 7, 1, S` to see SRQ, then `IOSPOLL` each instrument (`examples/3478a_srq.bas` shows how).
- **No adjustable T1 timing.** T1 is the settling delay between putting a byte on the data lines
  and signalling that it is valid. The driver uses its own fixed timing, which can't be changed.
  This is fine for most instruments, and the terminal has no command for it anyway.

### Board revisions

The revision is printed on the board. It decides one driver option:

| Revision | Change (from Lightside's CHANGELOG) | Driver option |
|----------|-------------------------------------|---------------|
| 1.0 | first version | do not use: EOI is not connected |
| 1.1 | EOI connected (SN75161 to GPIO9) | `pin_map=gpib4pi-1.1` (REN is on GPIO0) |
| 1.2 | moved to KiCad 6, no circuit change | `pin_map=gpib4pi-1.1` |
| 2.0 | REN moved to GPIO27 (pin 13), as on the elektronomikon board | none: the default pin map |
| **2.1** | logo and 3D model only, no circuit change | none: the default pin map |

So for the lsi-gpib4pi-2.x, nothing extra is needed. The installer uses the default unless you run
it as `sudo PIN_MAP=gpib4pi-1.1 bash install.sh` for a 1.x board.

### GPIO pin map (2.x board, from the `gpib_bitbang` driver source)

| GPIB signal | GPIB pin | Pi GPIO | Pi header pin |
|-------------|----------|---------|---------------|
| DIO1 | 1 | GPIO20 | 38 |
| DIO2 | 2 | GPIO26 | 37 |
| DIO3 | 3 | GPIO16 | 36 |
| DIO4 | 4 | GPIO19 | 35 |
| DIO5 | 13 | GPIO13 | 33 |
| DIO6 | 14 | GPIO12 | 32 |
| DIO7 | 15 | GPIO6 | 31 |
| DIO8 | 16 | GPIO5 | 29 |
| EOI | 5 | GPIO9 | 21 |
| DAV | 6 | GPIO10 | 19 |
| NRFD | 7 | GPIO24 | 18 |
| NDAC | 8 | GPIO23 | 16 |
| IFC | 9 | GPIO22 | 15 |
| SRQ | 10 | GPIO11 | 23 |
| ATN | 11 | GPIO25 | 22 |
| REN | 17 | GPIO27 (GPIO0 on 1.x boards) | 13 |
| Transceiver control: PE / DC / TE | - | GPIO7 / GPIO8 / GPIO18 | 26 / 24 / 12 |
| Activity LED | - | GPIO4 | 7 |
| Ground | 12, 18-24 | - | 14, 20, 25, 30, 34, 39 |

These pins belong to the driver while it is loaded. Don't use them for anything else (no SPI0,
since GPIO7-11 are SPI0's pins). The driver's numbers are GPIO numbers. Recent kernels number the
GPIO chip from an offset (512 on most Pis, 571 on a Pi 5), which is why the driver needs
`gpio_offset=` (section 3).

### Fitting it

- Plug the gpib4pi straight into the GPIB socket on the back of the meter and fasten it with the
  M3.5 thumbscrews. The Pi Zero sits on the board's 40-pin socket. No GPIB cable is needed.
- With a full-size Pi, use the stackable 2 x 20 connector from the package to raise the board.
- Power the Pi from its own USB supply.
- Find the meter's GPIB address: on the HP 3478A it is set with the **address DIP switches on the
  rear panel** (factory default **23**). Changes take effect at power-up.
- The Pi is the controller at address **0**. The meter must not use 0.
- The board's SN75160/SN75161 transceivers drive the bus the standard IEEE-488 way. (The
  driver's note about reduced fan-out, around 4 instruments, is for boards without these chips.)
  So more instruments can be daisy-chained with GPIB cables if needed. A bit-banged bus is
  slower than a commercial interface, which doesn't matter for a meter.

### Record of this installation

Fill this in once the Pi is set up. Menu item 9 (*Check the installation*) or
`.\pc\deploy.ps1 check` prints these items, so you can copy them from its output.

| Item | Value |
|------|-------|
| Pi model | |
| Raspberry Pi OS release | |
| Kernel (`uname -r`) | |
| Python version | |
| linux-gpib package version | |
| GPIO offset used | |
| gpib4pi board revision (silkscreen) | |
| Pi host name / IP address | 192.168.1.200 |
| Meter serial number / GPIB address | / 23 |

## 2. Software, on the Pi

**Easy way:** `sudo bash install.sh` (section 0). It does everything in sections 2 and 3:
- the build
- `/usr/etc/gpib.conf`
- GPIO offset detection
- a `gpib.service` that loads the driver at every boot
- a boot check that rebuilds the driver after a kernel update
- access to `/dev/gpib0` for the `gpib` group

It's safe to re-run. For the old v1.1 board, run `sudo PIN_MAP=gpib4pi-1.1 bash install.sh`.

**Manual way** (what the script does). Flash Raspberry Pi OS Lite (32-bit), enable Wi-Fi/SSH, then:

```bash
sudo apt-get update && sudo apt-get -y upgrade
sudo reboot

sudo apt-get -y install git rsync devscripts dh-python bison flex doxygen docbook-utils \
  docbook-to-man tcl8.6-dev python3-all-dev python3-setuptools debhelper autotools-dev \
  automake module-assistant

git clone -b debian/4.3.6-lsi8 https://github.com/lightside-instruments/gpib-debian.git gpib
rsync -rav gpib/ gpib_4.3.6
rm -rf gpib_4.3.6/.git gpib_4.3.6/debian
tar -czvf gpib_4.3.6.orig.tar.gz gpib_4.3.6
rm -rf gpib_4.3.6
cd gpib && debuild -us -uc && cd ..
sudo dpkg -i *.deb
sudo module-assistant auto-install gpib-modules-source
```

Notes:
- On a Pi Zero 2 W this build takes an hour or more, and longer on an original Zero W.
- If your OS is older than Bookworm, use branch `debian/4.3.5-lsi4` instead.

## 3. Configuration

Edit `/usr/etc/gpib.conf` and put in this interface block for the gpib4pi board. Instruments need
no `device` blocks: the programs address them by number (723 = select code 7, bus address 23).

```
interface {
    minor = 0
    board_type = "gpib_bitbang"
    name = "gpib0"
    pad = 0
    sad = 0
    timeout = T3s
    eos = 0x0a
    set-reos = yes
    set-bin = no
    set-xeos = no
    set-eot = yes
    base = 0
    irq = 0
    dma = 0
    master = yes
}
```

Next, find the GPIO offset:

```bash
sudo cat /sys/kernel/debug/gpio
```

Look at the line for GPIO0/ID_SDA. Its number is the offset. On newer kernels it is often 512
(571 on a Pi 5).

Load the driver and apply the config:

```bash
sudo modprobe gpib_bitbang gpio_offset=512
sudo gpib_config
```

- If you have the older 1.1 board (check the silkscreen), add `pin_map=gpib4pi-1.1` to the modprobe line.
- You'll need to run these two commands after every boot, unless you used `install.sh`, which installs `gpib.service` to do it.

## 4. Instruments

**Any GPIB instrument** can be used from the HP-IB Terminal (`hpib`, or menu item 1). `SCAN`, or
menu item 4, lists the bus addresses where an instrument answers. Address it as select code 7
followed by its two-digit bus address: an instrument at bus address 22 is device 722. Send it its
commands with `IOOUTPUTS 722, "..."`, and read its replies with `IOENTER`, `IOENTERS` or
`ASK 722, "..."`. The terminal guides explain the rest.

**Instrument modules** add ready-made tools for particular instruments. Each module has a section
in the menu, its own commands, and its own example programs:

| Module | Menu | Commands | Guide |
|--------|------|----------|-------|
| HP 3478A multimeter | `H` | `hp3478a-log`, `hp3478a-cal` | `HP3478A-Module-Guide.md` |

**Writing a module** for another instrument: make a folder `pi/instruments/<name>/` with
- `module.py`, which defines `TITLE`, `SUMMARY`, `KEY` (its menu letter) and `menu(ui)`. The menu
  passes `ui`, which has `ask`, `pause`, `run`, `choose_file`, `get_setting`/`set_setting`, `work`
  and `sim`. The HP 3478A module is the worked example.
- optionally `COMMANDS`, one line per command: `name  program.py  description`. `install.sh` turns
  each line into a command.
- optionally `examples/*.bas`. `LOAD "examples/<name>"` and menu item 3 find them.

`install.sh` installs every module folder. A module must not change the core.

## 5. If something doesn't work

- **The screen "staircases"** (each new line starts further to the right) during or after the
  installation: a build tool changed the terminal's settings. The installer puts them back
  after each step since version 2.0.7. To fix it by hand, type `stty sane` and press Enter; you
  may not see what you type. Or type `reset`. Nothing on the Pi is wrong; it is only the
  display.
- **Timeouts or no response:** the address is wrong. Check the instrument's address setting (on many
  older instruments, switches read at power-on, so power-cycle it after a change). Or the driver isn't
  loaded (see below).
- **`ssh: connect to host 192.168.1.200 ... timed out`:** the Pi is off, or not on Wi-Fi, or has a different IP.
  Check your router's client list, or `ping 192.168.1.200`.
- **modprobe fails:** the kernel module didn't build. Check that the kernel headers match the running
  kernel (`uname -r`), then re-run the module-assistant command.
- **`ibBoardOpen failed to open device file /dev/gpib0`**, or the HP-IB Terminal warning that
  `/dev/gpib0 does not exist`: the GPIB driver isn't loaded, so every bus command fails. On the Pi:
  1. `systemctl status gpib.service`: it should say `active (exited)`. If it says *could not be
     found*, setup was never finished: run `sudo bash install.sh` (section 0).
  2. If it failed, `sudo systemctl restart gpib.service`, then `journalctl -u gpib.service -b`
     shows why.
  3. `modprobe: FATAL: Module gpib_bitbang not found in directory /lib/modules/<version>` means
     there is no driver module for the running kernel. Usually `apt upgrade` installed a new
     kernel after linux-gpib was built. The Pi rebuilds the driver by itself at the next
     boot. To do it now, run `gpib-driver-rebuild` (or menu item R), then
     `sudo systemctl restart gpib.service`. If the rebuild fails, `journalctl -u
     pi-gpibterm-driver-rebuild -b` shows why. Usually the kernel headers are missing, and the Pi
     needs the network to fetch them. To stop kernel updates altogether:
     `sudo apt-mark hold linux-image-rpi-v6 linux-image-rpi-v7 linux-headers-rpi-v6 linux-headers-rpi-v7`
     (`apt-mark unhold ...` undoes it).
  4. `ls -l /dev/gpib0` should then show the device file, with group `gpib`.
- **An instrument answers but ignores what you send:** it is in local because the bus's REN
  line is off, and its REMOTE/RMT indicator is off. In local, instruments still answer reads but
  ignore their commands: an HP 3478A keeps sending readings after `T4`, for example. The terminal
  sets REN at start-up, but `IOLOCAL 7` clears it. Type `IOREMOTE 7` to set it again.
- **Nothing answers at all, not even `SCAN`:** check that the driver is loaded: `systemctl status gpib.service`.
  For a 1.x board, the driver needs `pin_map=gpib4pi-1.1` (section 1, Board revisions).
- **Other GPIO hardware on the same Pi:** the driver uses GPIO4-13, 16, 18-20 and 22-27 (section 1).
  Anything else on those pins, such as SPI0, an I2S sound card or a 1-wire sensor on GPIO4, conflicts.

- **Instrument-specific problems:** see the module's guide (e.g. `HP3478A-Module-Guide.md`).

## Credits

This project builds on the gpib4pi board and guide by Lightside Instruments, the linux-gpib
driver (including the `gpib_bitbang` driver by Thomas Klima and Marcello Carla'), HP's *HP-IB
Command Library* manual (1986), and, for the HP 3478A module, the calibration research of Tom Verbeure,
PyMeasure, Patrick Baus and Vinay Shanbhag. `THIRD-PARTY-NOTICES.md` says what came from each,
and the licenses.

pi-GPIBTerm itself is free software under the GNU General Public License version 3
(`GPL-3.0-only`); see `LICENSE`.
