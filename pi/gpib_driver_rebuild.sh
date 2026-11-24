#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
# gpib_driver_rebuild.sh - rebuild the gpib4pi driver module (gpib_bitbang) for a kernel
# Part of pi-GPIBTerm v2.0.7
#
#   sudo gpib_driver_rebuild.sh            rebuild for the running kernel, if it is missing
#   sudo gpib_driver_rebuild.sh --force    rebuild even if it is there
#   sudo gpib_driver_rebuild.sh --boot     as run by pi-gpibterm-driver-rebuild.service at boot:
#                                          quiet when there is nothing to do
#
# Why: linux-gpib's driver is a kernel module, built for one kernel version. When 'apt upgrade'
# installs a new kernel, the module has to be built again or /dev/gpib0 never appears. At every
# boot pi-gpibterm-driver-rebuild.service runs this script before gpib.service; it only does work
# (a few minutes on a Pi Zero) on the first boot after a kernel update.

set -uo pipefail

KVER="$(uname -r)"
FORCE=no
BOOT=no
for a in "$@"; do
  case "$a" in
    --force) FORCE=yes ;;
    --boot) BOOT=yes ;;
    -h|--help) sed -n '3,14p' "$0"; exit 0 ;;
    *) echo "unknown option: $a (try --help)" >&2; exit 2 ;;
  esac
done

# Keep the terminal readable. Some build tools change the terminal's settings and don't put
# them back: the worst is turning off the carriage return that goes with each line feed, which
# makes the rest of the output "staircase" across the screen. So the settings are saved here
# and restored after each build step and at the end; the build tools get no keyboard input,
# and apt shows no dialog screens.
export DEBIAN_FRONTEND=noninteractive
TTY_SAVED="$( { stty -g </dev/tty; } 2>/dev/null || true)"
fix_tty() { if [ -n "$TTY_SAVED" ]; then { stty "$TTY_SAVED" </dev/tty; } 2>/dev/null || true; fi; }
trap fix_tty EXIT

say() { echo "pi-GPIBTerm: $*"; }
[ "$(id -u)" -eq 0 ] || { echo "run with sudo: sudo $0 $*" >&2; exit 1; }

if [ "$FORCE" = no ] && modinfo -k "$KVER" gpib_bitbang >/dev/null 2>&1; then
  [ "$BOOT" = yes ] || say "the driver is already built for kernel $KVER - nothing to do (use --force to rebuild)"
  exit 0
fi

if ! dpkg -s gpib-modules-source >/dev/null 2>&1; then
  say "linux-gpib is not installed (no gpib-modules-source package). Run install.sh first."
  exit 1
fi

say "building the GPIB driver for kernel $KVER - this takes a few minutes on a Pi Zero"
if [ ! -d "/lib/modules/$KVER/build" ]; then
  say "kernel headers for $KVER are missing - installing them"
  apt-get -y install "linux-headers-$KVER" </dev/null || apt-get -y install raspberrypi-kernel-headers </dev/null || {
    say "no kernel headers for $KVER. Connect the Pi to the network, then run: sudo $0"
    exit 1
  }
fi
if ! command -v module-assistant >/dev/null; then
  apt-get -y install module-assistant build-essential || { say "could not install module-assistant"; exit 1; }
fi

# -t text mode, -i non-interactive, -l the kernel to build for
if module-assistant -t -i -l "$KVER" auto-install gpib-modules-source </dev/null; then
  depmod -a "$KVER"
fi
fix_tty
if modinfo -k "$KVER" gpib_bitbang >/dev/null 2>&1; then
  say "driver built for kernel $KVER"
  exit 0
fi
say "the driver build FAILED for kernel $KVER - see the messages above (journalctl -u pi-gpibterm-driver-rebuild -b)"
exit 1
