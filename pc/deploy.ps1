<#
.SYNOPSIS
  pi-GPIBTerm v2.0.7 - develop on the PC, install and run on the Raspberry Pi (optional).

.DESCRIPTION
  A helper for working on this project from a Windows PC. It isn't needed to use the
  project: on the Pi, install.sh does the whole installation by itself (see README.md).

  It builds the install package (pc\make_kit.ps1), copies it to the Pi over SSH, runs
  install.sh there, starts programs on the Pi, and brings calibration backups back to this
  PC. Uses the OpenSSH client built into Windows. On the Pi everything lands where
  install.sh puts it: programs in /opt/pi-gpibterm, your files in ~/pi-gpibterm.

  Actions:
    push    install the latest programs on the Pi (install.sh --no-driver: seconds)
    setup   full installation on the Pi, including linux-gpib and the driver
    check   show Pi model/OS/Python, driver service state and /dev/gpib0
    menu    open the pi-gpibterm menu on the Pi
    term    push, then open the HP-IB Terminal (hpib) on the Pi (extra arguments via -TermArgs)
    test    push, then take 5 DC volt readings
    log     push, then take readings (hp3478a-log; extra arguments via -LogArgs)
    sim     run the HP-IB Terminal here on the PC with the built-in simulator (needs Python)
    backup  back up the 3478A calibration RAM on the Pi, then pull it to .\backups
    verify  compare the meter with a backup file (-File name in .\backups)
    restore write a backup back to the meter (-File; CAL switch at ENABLE; asks you to type YES)
    pull    copy all backups from the Pi to .\backups
    shell   open an SSH session on the Pi

.EXAMPLE
  .\pc\deploy.ps1 setup                         # user willard, Pi at 192.168.1.200 by default
  .\pc\deploy.ps1 push -PiHost GPIB.local
  .\pc\deploy.ps1 menu
  .\pc\deploy.ps1 term   -TermArgs 'examples/3478a_read.bas --run'
  .\pc\deploy.ps1 log    -LogArgs '-f ohm2 -n 20 -i 1'
  .\pc\deploy.ps1 sim
  .\pc\deploy.ps1 backup
  .\pc\deploy.ps1 verify -File calram_20261122_200000.txt
  .\pc\deploy.ps1 push   -DryRun

.NOTES
  SPDX-License-Identifier: GPL-3.0-only (see LICENSE)
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory, Position = 0)]
    [ValidateSet('push', 'setup', 'check', 'menu', 'test', 'log', 'term', 'sim', 'backup', 'verify', 'restore', 'pull', 'shell')]
    [string]$Action,
    [string]$PiHost = $(if ($env:PI_GPIBTERM_HOST) { $env:PI_GPIBTERM_HOST } else { '192.168.1.200' }),
    [string]$User = $(if ($env:PI_GPIBTERM_USER) { $env:PI_GPIBTERM_USER } else { 'willard' }),
    [ValidateRange(0, 30)][int]$Address = 0,   # HP 3478A module address; 0 = keep the Pi's setting (23)
    [string]$LogArgs = '',
    [string]$TermArgs = '',
    [string]$File = '',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$PiDir = Join-Path $Root 'pi'
$BackupDir = Join-Path $Root 'backups'
$Target = "$User@$PiHost"
$Remote = 'pi-gpibterm'             # your folder ~/pi-gpibterm on the Pi (made by install.sh)

function Invoke-Tool([string]$Exe, [string[]]$ArgList) {
    Write-Host "> $Exe $($ArgList -join ' ')" -ForegroundColor DarkGray
    if ($DryRun) { return }
    & $Exe @ArgList
    if ($LASTEXITCODE -ne 0) { throw "$Exe failed (exit $LASTEXITCODE)" }
}

function Invoke-Remote([string]$Command, [switch]$Tty) {
    $a = @()
    if ($Tty) { $a += '-t' }
    Invoke-Tool 'ssh' ($a + @($Target, $Command))
}

function Install-Kit([switch]$WithDriver) {
    # the same package a GitHub release offers, installed with the same install.sh
    $kitDir = Join-Path ([IO.Path]::GetTempPath()) "pi-gpibterm-deploy-$PID"
    $kit = & (Join-Path $PSScriptRoot 'make_kit.ps1') -OutDir $kitDir | Select-Object -Last 1
    try {
        $opts = $(if ($Address) { "--address $Address" } else { '' }) + $(if ($WithDriver) { '' } else { ' --no-driver' })
        Invoke-Tool 'scp' @($kit, "${Target}:pi-gpibterm-kit.tar.gz")
        Invoke-Remote ("rm -rf ~/pi-gpibterm-kit && mkdir ~/pi-gpibterm-kit && " +
            "tar xzf ~/pi-gpibterm-kit.tar.gz -C ~/pi-gpibterm-kit --strip-components=1 && " +
            "sudo bash ~/pi-gpibterm-kit/install.sh $opts && rm -rf ~/pi-gpibterm-kit ~/pi-gpibterm-kit.tar.gz") -Tty
    }
    finally { Remove-Item -Recurse -Force $kitDir -ErrorAction SilentlyContinue }
}

function Pull-Backups {
    New-Item -ItemType Directory -Force $BackupDir | Out-Null
    Invoke-Tool 'scp' @("${Target}:$Remote/backups/calram_*", $BackupDir)
    Write-Host "Backups are in $BackupDir" -ForegroundColor Green
}

if ($Action -eq 'sim') {
    $py = Get-Command python, python3, py -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $py) { throw 'Python not found. Install Python 3 from python.org to use the simulator on the PC.' }
    $simArgs = @((Join-Path $PiDir 'hpibterm.py'), '--sim') + @($TermArgs -split ' ' | Where-Object { $_ })
    Push-Location $PiDir
    try { Invoke-Tool $py.Source $simArgs } finally { Pop-Location }
    return
}

foreach ($exe in 'ssh', 'scp') {
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) {
        throw "$exe not found. Install the Windows 'OpenSSH Client' optional feature."
    }
}
$Meter = if ($Address) { $Address } else { 23 }
Write-Host "Pi: $Target   HP 3478A module address: $Meter" -ForegroundColor Cyan

switch ($Action) {
    'push'   { Install-Kit }
    'setup'  { Install-Kit -WithDriver }
    'check'  {
        Invoke-Remote ("tr -d '\0' </proc/device-tree/model; echo; . /etc/os-release; echo `$PRETTY_NAME; " +
            "uname -m; uname -r; python3 --version; cat /opt/pi-gpibterm/INSTALLED 2>/dev/null; " +
            "systemctl is-active gpib.service; ls -l /dev/gpib0; " +
            "python3 -c 'import gpib' && echo 'python gpib module OK'; " +
            'echo "--- linux-gpib packages"; dpkg -l "libgpib*" "python3-gpib" 2>/dev/null | grep "^ii"; ' +
            'echo "--- driver options at boot"; systemctl cat gpib.service 2>/dev/null | grep modprobe; ' +
            'echo "--- GPIO chips (label, base = offset)"; for c in /sys/class/gpio/gpiochip*; do ' +
            'echo "$(cat $c/label) base $(cat $c/base)"; done; echo "--- host"; hostname; hostname -I')
    }
    'menu'   { Invoke-Remote 'pi-gpibterm' -Tty }
    'test'   { Install-Kit; Invoke-Remote "hp3478a-log -a $Meter -n 5" -Tty }
    'log'    { Install-Kit; Invoke-Remote "cd ~/$Remote && hp3478a-log -a $Meter $LogArgs" -Tty }
    'term'   { Install-Kit; Invoke-Remote "cd ~/$Remote && hpib $TermArgs" -Tty }
    'backup' {
        Invoke-Remote "mkdir -p ~/$Remote/backups && cd ~/$Remote/backups && hp3478a-cal -a $Meter backup" -Tty
        Pull-Backups
    }
    { $_ -in 'verify', 'restore' } {
        if (-not $File) { throw "give the backup file name with -File (e.g. -File calram_20261122_200000.txt)" }
        $leaf = Split-Path -Leaf $File
        $local = Join-Path $BackupDir $leaf
        if (Test-Path $local) { Invoke-Tool 'scp' @($local, "${Target}:$Remote/backups/$leaf") }
        Invoke-Remote "cd ~/$Remote/backups && hp3478a-cal -a $Meter $Action $leaf" -Tty
        if ($Action -eq 'restore') { Pull-Backups }   # brings back calram_before_restore_* too
    }
    'pull'   { Pull-Backups }
    'shell'  { Invoke-Tool 'ssh' @($Target) }
}
