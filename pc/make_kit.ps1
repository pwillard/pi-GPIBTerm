<#
.SYNOPSIS
  Builds the pi-GPIBTerm install package: dist\pi-GPIBTerm-<version>.tar.gz

.DESCRIPTION
  The package is what a GitHub release offers for download. It holds everything a fresh
  Raspberry Pi needs, with no PC involved:
      tar xzf pi-GPIBTerm-<version>.tar.gz
      cd pi-GPIBTerm-<version> && sudo bash install.sh
  It contains install.sh, uninstall.sh, README.md, LICENSE(S), VERSION, the PDF guides,
  pi\ (programs, scripts, examples, instrument modules) and docs\ (notices). It leaves out dev\
  (tests), pc\ (Windows tools), backups\ and reference-local\.
  Text files are converted to LF line endings, as Linux needs. Prints the package's path.

.EXAMPLE
  .\pc\make_kit.ps1
  .\pc\make_kit.ps1 -OutDir C:\temp

.NOTES
  SPDX-License-Identifier: GPL-3.0-only (see LICENSE)
#>
[CmdletBinding()]
param(
    [string]$OutDir = ''
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Version = (Get-Content (Join-Path $Root 'VERSION') -Raw).Trim()
if (-not $OutDir) { $OutDir = Join-Path $Root 'dist' }
$Name = "pi-GPIBTerm-$Version"
$work = Join-Path ([IO.Path]::GetTempPath()) "pi-gpibterm-kit-$PID"
$stage = Join-Path $work $Name
$textExt = '.py', '.sh', '.bas', '.md', '.txt', ''

$include = @(
    'install.sh', 'uninstall.sh', 'README.md', 'LICENSE', 'VERSION',
    'HP-IB-Terminal-Introduction.pdf', 'HP-IB-Terminal-Guide.pdf',
    'pi-GPIBTerm-Setup-Guide.pdf', 'HP3478A-Module-Guide.pdf', 'THIRD-PARTY-NOTICES.pdf',
    'LICENSES\*', 'pi\*.py', 'pi\*.sh', 'pi\examples\*.bas',
    'pi\instruments\*\*.py', 'pi\instruments\*\COMMANDS', 'pi\instruments\*\examples\*.bas',
    'docs\*.md'
)

try {
    New-Item -ItemType Directory -Force $stage, $OutDir | Out-Null
    $count = 0
    foreach ($pattern in $include) {
        $files = Get-ChildItem -Path (Join-Path $Root $pattern) -File -ErrorAction SilentlyContinue
        if (-not $files) { throw "missing from the project: $pattern" }
        foreach ($f in $files) {
            $rel = $f.FullName.Substring($Root.Length + 1)
            $dest = Join-Path $stage $rel
            New-Item -ItemType Directory -Force (Split-Path -Parent $dest) | Out-Null
            if ($f.Extension -in $textExt) {
                $text = [IO.File]::ReadAllText($f.FullName) -replace "`r`n", "`n"
                [IO.File]::WriteAllText($dest, $text, [Text.UTF8Encoding]::new($false))
            }
            else { Copy-Item -LiteralPath $f.FullName $dest }
            $count++
        }
    }
    $out = Join-Path $OutDir "$Name.tar.gz"
    $tar = Join-Path $env:SystemRoot 'System32\tar.exe'
    if (-not (Test-Path $tar)) { $tar = 'tar' }
    & $tar -czf $out -C $work $Name
    if ($LASTEXITCODE -ne 0) { throw "tar failed (exit $LASTEXITCODE)" }
    $hash = (Get-FileHash -Algorithm SHA256 $out).Hash.ToLower()
    "$hash  $Name.tar.gz" | Set-Content -Encoding ascii -NoNewline "$out.sha256"
    Write-Host "$count files -> $out ($([math]::Round((Get-Item $out).Length / 1KB)) KB)" -ForegroundColor Green
    Write-Host "sha256 $hash"
    $out
}
finally {
    Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}
