#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
# uninstall.sh - remove the pi-GPIBTerm programs and commands
# Part of pi-GPIBTerm v2.0.5
#
#   sudo bash uninstall.sh          remove /opt/pi-gpibterm and the commands (keeps the driver)
#   sudo bash uninstall.sh --driver also stop and remove gpib.service, the boot-time rebuild
#                                   check and the /dev/gpib0 access rule
# Never touches your folder ~/pi-gpibterm (programs, backups, logs) or the linux-gpib packages.
# To remove those packages too:  sudo apt-get remove 'libgpib*' python3-gpib gpib-modules-source

set -euo pipefail
PREFIX=/opt/pi-gpibterm
BINDIR=/usr/local/bin
DRIVER=no
while [ $# -gt 0 ]; do
  case "$1" in
    --driver) DRIVER=yes ;;
    --prefix) PREFIX="${2:-}"; shift ;;
    --bindir) BINDIR="${2:-}"; shift ;;
    -h|--help) sed -n '3,11p' "$0"; exit 0 ;;
    *) echo "unknown option: $1 (try --help)" >&2; exit 1 ;;
  esac
  shift
done
if [ "$DRIVER" = yes ] || [ "$PREFIX" = /opt/pi-gpibterm ]; then
  [ "$(id -u)" -eq 0 ] || { echo "run with sudo:  sudo bash uninstall.sh" >&2; exit 1; }
fi

# every command install.sh made says "(pi-GPIBTerm <version>)" in its second line
for c in "$BINDIR"/*; do
  if [ -f "$c" ] && head -2 "$c" | grep -q "(pi-GPIBTerm "; then rm -f "$c"; fi
done
if [ -f "$PREFIX/INSTALLED" ]; then rm -rf "$PREFIX"; fi
echo "Removed the programs ($PREFIX) and the commands."

if [ "$DRIVER" = yes ]; then
  for s in gpib.service pi-gpibterm-driver-rebuild.service; do
    systemctl disable --now "$s" 2>/dev/null || true
    rm -f "/etc/systemd/system/$s"
  done
  rm -f /etc/udev/rules.d/90-pi-gpibterm.rules /usr/local/sbin/pi-gpibterm-driver-rebuild
  systemctl daemon-reload
  udevadm control --reload 2>/dev/null || true
  echo "Removed gpib.service, the boot-time driver check and the /dev/gpib0 access rule."
fi
echo "Your folder ~/pi-gpibterm was not touched."
