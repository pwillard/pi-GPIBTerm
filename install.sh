#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
# install.sh - install pi-GPIBTerm on a Raspberry Pi with a Lightside gpib4pi board
# Part of pi-GPIBTerm v2.0.6
#
# On a fresh Raspberry Pi OS Lite:
#     sudo apt-get update && sudo apt-get -y install git
#     git clone https://github.com/<your-account>/pi-GPIBTerm.git
#     cd pi-GPIBTerm && sudo bash install.sh
# Then log out and back in, and type:  pi-gpibterm      (the menu)
#
# Options:
#   --no-driver    only install/update the programs; skip linux-gpib and the driver
#   --user NAME    whose home folder gets ~/pi-gpibterm (default: the user who ran sudo)
#   --prefix DIR   where the programs go (default /opt/pi-gpibterm)
#   --bindir DIR   where the commands go (default /usr/local/bin)
#   --home DIR     the home folder to use (default: NAME's home)
#   --address N    the HP 3478A module's meter address (default 23; also set in the menu)
#
# What it does:
#   1. builds and installs linux-gpib and the gpib4pi driver (pi/setup_pi.sh): kernel headers,
#      /usr/etc/gpib.conf, gpib.service (loads the driver at boot), a boot check that rebuilds
#      the driver after a kernel update, and access to /dev/gpib0 for the 'gpib' group.
#      This part takes 1-2 hours on a Pi Zero, the first time only.
#   2. copies the programs and instrument modules to /opt/pi-gpibterm and adds the commands
#      pi-gpibterm (menu), hpib (HP-IB Terminal), gpib-driver-rebuild, and one per
#      instrument-module tool (hp3478a-cal, hp3478a-log)
#   3. makes ~/pi-gpibterm with the menu, programs/, backups/ and logs/ (never overwrites files)
# Safe to run again: that is also how to update. An earlier hp3478a-gpib installation is
# replaced, and its ~/hp3478a folder becomes ~/pi-gpibterm.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(tr -d ' \r\n' < "$SRC/VERSION")"
ADDR=""
DRIVER=yes
TARGET_USER="${SUDO_USER:-}"
PREFIX=/opt/pi-gpibterm
BINDIR=/usr/local/bin
HOME_DIR=""

die() { echo "ERROR: $*" >&2; exit 1; }
say() { echo; echo "=== $*"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --address) ADDR="${2:-}"; shift ;;
    --no-driver) DRIVER=no ;;
    --user) TARGET_USER="${2:-}"; shift ;;
    --prefix) PREFIX="${2:-}"; shift ;;
    --bindir) BINDIR="${2:-}"; shift ;;
    --home) HOME_DIR="${2:-}"; shift ;;
    -h|--help) sed -n '3,30p' "$0"; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

if [ -n "$ADDR" ]; then
  [[ "$ADDR" =~ ^[0-9]+$ ]] && [ "$ADDR" -ge 1 ] && [ "$ADDR" -le 30 ] || die "--address must be 1..30"
fi
[ -n "$TARGET_USER" ] || TARGET_USER="$(id -un)"
if [ -z "$HOME_DIR" ]; then
  HOME_DIR="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
  [ -n "$HOME_DIR" ] || die "user $TARGET_USER not found (use --user NAME)"
fi
if [ "$DRIVER" = yes ] || [ "$PREFIX" = /opt/pi-gpibterm ] || [ "$BINDIR" = /usr/local/bin ]; then
  [ "$(id -u)" -eq 0 ] || die "run with sudo:  sudo bash install.sh"
fi
[ -f "$SRC/pi/hpibterm.py" ] || die "pi/hpibterm.py not found next to install.sh - run it from the pi-GPIBTerm folder"
command -v python3 >/dev/null || die "python3 is missing (it is part of Raspberry Pi OS)"

echo "pi-GPIBTerm $VERSION installer"
echo "programs: $PREFIX   commands: $BINDIR   your folder: $HOME_DIR/pi-gpibterm (user $TARGET_USER)"

# ---------------------------------------------------------------- 1. linux-gpib + driver
if [ "$DRIVER" = yes ]; then
  say "Step 1 of 3: linux-gpib and the gpib4pi driver"
  INSTALL_USER="$TARGET_USER" bash "$SRC/pi/setup_pi.sh"
else
  say "Step 1 of 3: skipped (--no-driver)"
fi

# ---------------------------------------------------------------- 2. programs
say "Step 2 of 3: programs into $PREFIX"
# an earlier installation under the old name (hp3478a-gpib, before 2.0.0) is removed
OLD_PREFIX="$(dirname "$PREFIX")/hp3478a"
if [ -f "$OLD_PREFIX/INSTALLED" ]; then
  rm -rf "$OLD_PREFIX"
  echo "removed the earlier hp3478a-gpib programs in $OLD_PREFIX"
fi
for c in hp3478a hp3478a-driver-rebuild; do
  if [ -f "$BINDIR/$c" ] && grep -q "hp3478a-gpib" "$BINDIR/$c"; then rm -f "$BINDIR/$c"; fi
done

rm -rf "$PREFIX/instruments" "$PREFIX/examples"      # so removed files don't linger
mkdir -p "$PREFIX/examples" "$PREFIX/docs" "$PREFIX/instruments" "$BINDIR"
for f in "$SRC"/pi/*.py; do install -m 0644 "$f" "$PREFIX/"; done
for f in "$SRC"/pi/*.sh; do install -m 0755 "$f" "$PREFIX/"; done
chmod 0755 "$PREFIX"/hpibterm.py "$PREFIX"/gpibterm_menu.py
for f in "$SRC"/pi/examples/*.bas; do install -m 0644 "$f" "$PREFIX/examples/"; done
cp -R "$SRC/pi/instruments/." "$PREFIX/instruments/"
find "$PREFIX/instruments" -name __pycache__ -prune -exec rm -rf {} +
find "$PREFIX/instruments" -type d -exec chmod 0755 {} +
find "$PREFIX/instruments" -type f -exec chmod 0644 {} +
for f in "$SRC"/*.pdf "$SRC"/LICENSE "$SRC"/VERSION "$SRC"/README.md; do
  if [ -f "$f" ]; then install -m 0644 "$f" "$PREFIX/docs/"; fi
done
if [ -d "$SRC/LICENSES" ]; then
  mkdir -p "$PREFIX/docs/LICENSES"
  install -m 0644 "$SRC"/LICENSES/* "$PREFIX/docs/LICENSES/"
fi
# the guides' sources too: plain text, for reading on the Pi itself (menu item D)
for f in "$SRC"/docs/*.md; do
  if [ -f "$f" ]; then install -m 0644 "$f" "$PREFIX/docs/"; fi
done
# no line-ending surprises: everything that runs must be LF
find "$PREFIX" \( -name '*.py' -o -name '*.sh' -o -name '*.bas' \) -exec sed -i 's/\r$//' {} +
echo "$VERSION installed $(date '+%Y-%m-%d %H:%M') from $SRC" > "$PREFIX/INSTALLED"

# the commands: small wrappers that run the programs from $PREFIX
wrapper() {   # name, program (relative to $PREFIX), description
  cat > "$BINDIR/$1" <<EOF
#!/bin/sh
# $1 - $3 (pi-GPIBTerm $VERSION)
exec "$PREFIX/run.sh" $2 "\$@"
EOF
  chmod 0755 "$BINDIR/$1"
}
wrapper pi-gpibterm gpibterm_menu.py "menu"
wrapper hpib hpibterm.py "HP-IB Terminal"
cat > "$BINDIR/gpib-driver-rebuild" <<EOF
#!/bin/sh
# gpib-driver-rebuild - rebuild the GPIB driver for the running kernel (pi-GPIBTerm $VERSION)
exec sudo "$PREFIX/gpib_driver_rebuild.sh" "\$@"
EOF
chmod 0755 "$BINDIR/gpib-driver-rebuild"
CMDS="pi-gpibterm  hpib  gpib-driver-rebuild"
# instrument modules: each COMMANDS line "name program description" becomes a command
for list in "$PREFIX"/instruments/*/COMMANDS; do
  [ -f "$list" ] || continue
  mod="$(basename "$(dirname "$list")")"
  while read -r name prog desc; do
    case "$name" in ''|'#'*) continue ;; esac
    wrapper "$name" "instruments/$mod/$prog" "$desc"
    CMDS="$CMDS  $name"
  done < "$list"
done
echo "commands: $CMDS"

# ---------------------------------------------------------------- 3. your folder
WORK="$HOME_DIR/pi-gpibterm"
say "Step 3 of 3: your folder $WORK"
if [ ! -e "$WORK" ] && [ -f "$HOME_DIR/hp3478a/menu" ]; then
  mv "$HOME_DIR/hp3478a" "$WORK"
  echo "your earlier folder ~/hp3478a is now ~/pi-gpibterm (backups, logs and programs kept)"
  if [ -f "$WORK/hp3478a.conf" ] && [ ! -f "$WORK/pi-gpibterm.conf" ]; then
    OLDADDR="$(sed -n 's/^ADDRESS=//p' "$WORK/hp3478a.conf" | head -1)"
    [ -z "$ADDR" ] && ADDR="$OLDADDR"
    rm -f "$WORK/hp3478a.conf"
  fi
fi
mkdir -p "$WORK/programs" "$WORK/backups" "$WORK/logs"
# An older copy of the programs in the folder (from deploy.ps1 push) is moved aside, so the
# old versions can't be run by mistake. Backups and anything else are left where they are.
OLD=""
for f in hpibterm.py hpiblib.py hpibbasic.py hpibhelp.py hpib_sim.py hp3478a_cal.py hp3478a_log.py setup_pi.sh; do
  if [ -f "$WORK/$f" ]; then
    [ -n "$OLD" ] || { OLD="$WORK/old-programs-$(date +%Y%m%d_%H%M%S)"; mkdir -p "$OLD"; }
    mv "$WORK/$f" "$OLD/"
  fi
done
if [ -d "$WORK/examples" ] && [ -n "$OLD" ]; then mv "$WORK/examples" "$OLD/"; fi
if [ -n "$OLD" ]; then echo "an older copy of the programs was moved to $OLD"; fi
cat > "$WORK/menu" <<EOF
#!/bin/sh
# menu - start the pi-GPIBTerm menu (same as typing: pi-gpibterm)
exec "$BINDIR/pi-gpibterm" "\$@"
EOF
chmod 0755 "$WORK/menu"
CONF="$WORK/pi-gpibterm.conf"
[ -f "$CONF" ] || printf '# pi-GPIBTerm settings (the menu reads and writes this)\n' > "$CONF"
if [ -n "$ADDR" ]; then
  if grep -q '^HP3478A_ADDRESS=' "$CONF"; then
    sed -i "s/^HP3478A_ADDRESS=.*/HP3478A_ADDRESS=$ADDR/" "$CONF"
  else
    echo "HP3478A_ADDRESS=$ADDR" >> "$CONF"
  fi
fi
if [ ! -f "$WORK/programs/README.txt" ]; then
  cat > "$WORK/programs/README.txt" <<EOF
Your own HP-IB Terminal programs go here, for example:
    HP-IB> SAVE "programs/myprog"
    HP-IB> LOAD "programs/myprog"
The example programs are in $PREFIX/examples and in each instrument module
($PREFIX/instruments/*/examples). LOAD "examples/bus_tour" finds them from anywhere.
EOF
fi
if [ "$(id -u)" -eq 0 ]; then
  chown -R "$TARGET_USER": "$WORK"
fi

say "Done - pi-GPIBTerm $VERSION"
cat <<EOF
Start the menu:   pi-gpibterm    (or ~/pi-gpibterm/menu)
HP-IB Terminal:   hpib           (practise without an instrument: hpib --sim)
Guides:           menu item D reads them here; PDFs for a PC in $PREFIX/docs
Your files:       $WORK  (programs/, backups/, logs/)
EOF
if [ "$DRIVER" = yes ] && ! id -nG "$TARGET_USER" 2>/dev/null | grep -qw gpib; then
  echo "Log out and back in once, so that $TARGET_USER can use the GPIB board without sudo."
fi
