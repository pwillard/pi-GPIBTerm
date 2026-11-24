#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
# setup_pi.sh - linux-gpib and the gpib4pi driver on a Raspberry Pi (install.sh runs this)
# Part of pi-GPIBTerm v2.0.6
#
# Run ON THE PI:   sudo bash setup_pi.sh        (install.sh runs it for you)
#
# What it does:
#   1. installs build tools and kernel headers
#   2. builds + installs Lightside's linux-gpib packages (skipped if already installed).
#      If only the kernel module is missing - the usual result of an 'apt upgrade' that
#      installed a new kernel - it rebuilds just the module for the running kernel.
#   3. writes /usr/etc/gpib.conf for the gpib4pi board (system controller, address 0)
#   4. detects the GPIO offset and installs a systemd service that loads the driver
#      and runs gpib_config at every boot
#   5. installs a boot check (pi-gpibterm-driver-rebuild.service) that rebuilds the driver on the
#      first boot after a kernel update, and the kernel headers package that follows updates
#   6. lets the 'gpib' group use /dev/gpib0 (udev rule) and adds the user to that group
# Safe to re-run. The build takes an hour or more on a Pi Zero 2 W (longer on a Zero W).

set -euo pipefail

BRANCH="debian/4.3.6-lsi8"     # Bookworm/Trixie. Use debian/4.3.5-lsi4 on Bullseye or older.
VER="4.3.6"
BUILD_DIR="/usr/local/src/linux-gpib-lsi"
CONF="/usr/etc/gpib.conf"
PIN_MAP="${PIN_MAP:-}"          # set PIN_MAP=gpib4pi-1.1 for the old v1.1 board

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REBUILD=/usr/local/sbin/pi-gpibterm-driver-rebuild
GPIB_USER="${INSTALL_USER:-${SUDO_USER:-}}"

say() { echo; echo "=== $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run with sudo:  sudo bash setup_pi.sh"

ARCH="$(uname -m)"
say "Pi: $(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo unknown), arch $ARCH, kernel $(uname -r)"
case "$ARCH" in
  armv6l|armv7l) ;;
  aarch64) echo "Note: 64-bit OS. Works on Zero 2 W / Pi 3+; the original Zero W needs 32-bit Raspberry Pi OS." ;;
  *) die "unexpected architecture $ARCH" ;;
esac

if [ -f /etc/os-release ]; then . /etc/os-release; echo "OS: $PRETTY_NAME"; fi
if [ "${VERSION_CODENAME:-}" = "bullseye" ] || [ "${VERSION_CODENAME:-}" = "buster" ]; then
  BRANCH="debian/4.3.5-lsi4"; VER="4.3.5"
fi

# ---------------------------------------------------------------- swap (Pi Zero / Zero 2 W have 512 MB RAM)
MEM_MB=$(( $(awk '/MemTotal/ {print $2}' /proc/meminfo) / 1024 ))
SWAP_MB=$(( $(awk '/SwapTotal/ {print $2}' /proc/meminfo) / 1024 ))
echo "RAM ${MEM_MB} MB, swap ${SWAP_MB} MB"
if [ "$SWAP_MB" -lt 900 ] && [ -f /etc/dphys-swapfile ] && command -v dphys-swapfile >/dev/null; then
  say "Increasing swap to 1024 MB for the build (dphys-swapfile)"
  sed -i 's/^#\?CONF_SWAPSIZE=.*/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile
  dphys-swapfile setup && dphys-swapfile swapon || echo "warning: could not enlarge swap, continuing"
elif [ "$SWAP_MB" -lt 900 ]; then
  echo "warning: less than 900 MB swap; the build may run out of memory on a Pi Zero"
fi

install_headers() {
  say "Installing kernel headers for $(uname -r)"
  apt-get -y install "linux-headers-$(uname -r)" \
    || apt-get -y install raspberrypi-kernel-headers \
    || die "no kernel headers for $(uname -r). Run 'sudo apt-get -y full-upgrade', reboot, and re-run."
}

# ---------------------------------------------------------------- build + install linux-gpib
USERSPACE_OK=no
if command -v gpib_config >/dev/null && python3 -c "import gpib" 2>/dev/null; then
  USERSPACE_OK=yes
fi
if [ "$USERSPACE_OK" = yes ] && modinfo gpib_bitbang >/dev/null 2>&1; then
  say "linux-gpib already installed - skipping build"
elif [ "$USERSPACE_OK" = yes ] && dpkg -s gpib-modules-source >/dev/null 2>&1; then
  say "linux-gpib is installed, but its kernel module is missing for kernel $(uname -r)"
  echo "Built for:  $(find /lib/modules -name 'gpib_bitbang.ko*' -printf '%h\n' 2>/dev/null \
                       | sed 's|^/lib/modules/||; s|/.*||' | sort -u | tr '\n' ' ')"
  echo "This usually means 'apt upgrade' installed a new kernel. Rebuilding only the module."
  apt-get update
  install_headers
  bash "$HERE/gpib_driver_rebuild.sh" || die "the driver rebuild failed"
else
  say "Installing build dependencies"
  apt-get update
  apt-get -y install git rsync devscripts dh-python bison flex doxygen docbook-utils \
      docbook-to-man tcl8.6-dev python3-all-dev python3-setuptools debhelper \
      autotools-dev automake module-assistant
  install_headers

  say "Building Lightside linux-gpib ($BRANCH) in $BUILD_DIR - this is slow on a Pi Zero"
  rm -rf "$BUILD_DIR"; mkdir -p "$BUILD_DIR"; cd "$BUILD_DIR"
  git clone --depth 1 -b "$BRANCH" https://github.com/lightside-instruments/gpib-debian.git gpib
  rsync -a gpib/ "gpib_$VER"
  rm -rf "gpib_$VER/.git" "gpib_$VER/debian"
  tar -czf "gpib_$VER.orig.tar.gz" "gpib_$VER"
  rm -rf "gpib_$VER"
  (cd gpib && debuild -us -uc)
  dpkg -i ./*.deb
  module-assistant -t -i auto-install gpib-modules-source
  depmod -a
fi

# The headers metapackage for this kernel flavour (e.g. linux-headers-rpi-v6), so that every
# kernel update also brings the headers the boot check needs to rebuild the driver.
FLAVOUR="$(uname -r | sed -n 's/.*+rpt-//p')"
if [ -n "$FLAVOUR" ]; then
  apt-get -y install "linux-headers-$FLAVOUR" >/dev/null 2>&1 \
    && echo "kernel headers will follow kernel updates (linux-headers-$FLAVOUR)" \
    || echo "note: linux-headers-$FLAVOUR not available; after a kernel update run gpib-driver-rebuild"
fi

GPIB_CONFIG="$(command -v gpib_config || true)"
[ -n "$GPIB_CONFIG" ] || die "gpib_config not found after install"
modinfo gpib_bitbang >/dev/null 2>&1 || die "gpib_bitbang kernel module not built for $(uname -r)"

# ---------------------------------------------------------------- gpib.conf
say "Writing $CONF (the gpib4pi board: system controller at address 0)"
mkdir -p "$(dirname "$CONF")"
[ -f "$CONF" ] && cp "$CONF" "$CONF.bak.$(date +%Y%m%d_%H%M%S)"
cat > "$CONF" <<EOF
/* written by pi-GPIBTerm setup_pi.sh. Instruments need no entries here: the programs
   address them by number (723 = select code 7, bus address 23). */
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

EOF

# ---------------------------------------------------------------- GPIO offset
OFFSET=""
for c in /sys/class/gpio/gpiochip*; do
  [ -f "$c/label" ] || continue
  case "$(cat "$c/label")" in
    pinctrl-bcm2835|pinctrl-bcm2711|pinctrl-rp1) OFFSET="$(cat "$c/base")"; break ;;
  esac
done
if [ -z "$OFFSET" ] && [ -r /sys/kernel/debug/gpio ]; then
  OFFSET="$(sed -n 's/^gpiochip0: GPIOs \([0-9]*\)-.*/\1/p' /sys/kernel/debug/gpio | head -1)"
fi
[ -n "$OFFSET" ] || die "could not detect the GPIO offset; check: sudo cat /sys/kernel/debug/gpio"
echo "GPIO offset: $OFFSET"

OPTS="gpio_offset=$OFFSET"
[ -n "$PIN_MAP" ] && OPTS="$OPTS pin_map=$PIN_MAP"

# ---------------------------------------------------------------- boot service
say "Installing gpib.service (loads driver + gpib_config at boot)"
cat > /etc/systemd/system/gpib.service <<EOF
[Unit]
Description=linux-gpib: gpib4pi bitbang driver + gpib_config
After=local-fs.target pi-gpibterm-driver-rebuild.service
Wants=pi-gpibterm-driver-rebuild.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStartPre=/sbin/modprobe gpib_bitbang $OPTS
ExecStart=$GPIB_CONFIG
ExecStop=/sbin/modprobe -r gpib_bitbang

[Install]
WantedBy=multi-user.target
EOF

# ---------------------------------------------------------------- boot check after kernel updates
# an earlier installation under the old name (hp3478a-gpib, before 2.0.0)
if [ -f /etc/systemd/system/hp3478a-gpib-rebuild.service ]; then
  systemctl disable hp3478a-gpib-rebuild.service 2>/dev/null || true
  rm -f /etc/systemd/system/hp3478a-gpib-rebuild.service /usr/local/sbin/hp3478a-gpib-rebuild
fi
rm -f /etc/udev/rules.d/90-hp3478a-gpib.rules
say "Installing pi-gpibterm-driver-rebuild.service (rebuilds the driver after a kernel update)"
install -m 0755 "$HERE/gpib_driver_rebuild.sh" "$REBUILD"
cat > /etc/systemd/system/pi-gpibterm-driver-rebuild.service <<EOF
[Unit]
Description=pi-GPIBTerm: rebuild the GPIB driver if the kernel was updated
Before=gpib.service

[Service]
Type=oneshot
ExecStart=$REBUILD --boot
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

# ---------------------------------------------------------------- /dev/gpib0 without sudo
say "Letting the 'gpib' group use /dev/gpib0"
getent group gpib >/dev/null || groupadd --system gpib
cat > /etc/udev/rules.d/90-pi-gpibterm.rules <<'EOF'
# pi-GPIBTerm: members of the gpib group may use the GPIB boards
KERNEL=="gpib[0-9]*", GROUP="gpib", MODE="0660"
EOF
udevadm control --reload 2>/dev/null || true
if [ -n "$GPIB_USER" ] && [ "$GPIB_USER" != root ]; then
  usermod -aG gpib "$GPIB_USER" && echo "added $GPIB_USER to the gpib group (log in again to use it)"
fi

systemctl daemon-reload
systemctl enable pi-gpibterm-driver-rebuild.service
systemctl enable gpib.service
systemctl restart gpib.service
systemctl --no-pager status gpib.service | head -5 || true
[ -e /dev/gpib0 ] && chgrp gpib /dev/gpib0* 2>/dev/null && chmod 0660 /dev/gpib0* 2>/dev/null || true

say "Done"
cat <<EOF
Driver loaded (options: $OPTS). It will load automatically at every boot.
Quick test with an instrument connected and switched on: sudo ibterm -d <its bus address>
After install.sh has finished: the menu is  pi-gpibterm , the HP-IB Terminal is  hpib .
EOF
