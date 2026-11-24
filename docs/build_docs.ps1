<#
.SYNOPSIS
  Builds PDF (and HTML) versions of the pi-GPIBTerm guides from their Markdown sources.

.DESCRIPTION
  All the documentation lives in the docs folder (this script's folder): the .md sources,
  the .html copies and doc-print.css. Only the finished PDFs are written
  to the project's root folder.

  For each guide: pandoc turns the .md into a self-contained HTML page styled by
  docs\doc-print.css, then Microsoft Edge (or Google Chrome) prints that page to PDF in
  headless mode. Every PDF is built to a temporary file first and then copied over the
  final file, so a PDF that is open in a viewer can't make the build lose its output:
  if the copy fails, the new PDF stays in the temp folder and its path is printed.

  Every PDF starts with a cover page: plain text on a dark page, or a full-page photo
  behind the title when -Cover names one (use only a photo you have the rights to).

  Needs: pandoc (https://pandoc.org) and Edge or Chrome. No LaTeX.

.EXAMPLE
  .\docs\build_docs.ps1             # all the guides and the third-party notices
  .\docs\build_docs.ps1 -Only intro # just HP-IB-Terminal-Introduction
  .\docs\build_docs.ps1 -Cover my-bench.jpg   # a photo (in the docs folder) behind the title

.NOTES
  SPDX-License-Identifier: GPL-3.0-only (see LICENSE)
#>
[CmdletBinding()]
param(
    [ValidateSet('all', 'intro', 'guide', 'setup', 'hp3478a', 'notices')]
    [string]$Only = 'all',
    # Optional cover photo (relative paths are taken from the docs folder); none = text-only cover
    [string]$Cover = '',
    [string]$CoverAlt = 'Cover photo'
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Version = (Get-Content (Join-Path $Root 'VERSION') -Raw).Trim()

$DocsDir = $PSScriptRoot
$coverUri = ''
if ($Cover) {
    if (-not [IO.Path]::IsPathRooted($Cover)) { $Cover = Join-Path $DocsDir $Cover }
    if (-not (Test-Path -LiteralPath $Cover)) { throw "Cover image not found: $Cover" }
    # Embedded as a data URI, so the HTML stays self-contained. A PNG is re-encoded as JPEG
    # (quality 85) for the documents, which keeps each PDF small; the original is not changed.
    $mime = 'image/png'
    $coverBytes = [IO.File]::ReadAllBytes($Cover)
    if ($Cover -match '\.jpe?g$') { $mime = 'image/jpeg' }
    else {
        try {
            Add-Type -AssemblyName System.Drawing
            $img = [Drawing.Image]::FromFile($Cover)
            $enc = [Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object MimeType -eq 'image/jpeg'
            $ep = New-Object Drawing.Imaging.EncoderParameters 1
            $ep.Param[0] = New-Object Drawing.Imaging.EncoderParameter ([Drawing.Imaging.Encoder]::Quality), 85L
            $ms = New-Object IO.MemoryStream
            $img.Save($ms, $enc, $ep)
            $img.Dispose()
            $coverBytes = $ms.ToArray(); $mime = 'image/jpeg'
        }
        catch { Write-Warning "Could not convert the cover to JPEG ($($_.Exception.Message)); embedding the PNG." }
    }
    $coverUri = "data:$mime;base64," + [Convert]::ToBase64String($coverBytes)
}
$coverAlt = [Net.WebUtility]::HtmlEncode($CoverAlt)

$Docs = @(
    @{ Key = 'intro'; File = 'HP-IB-Terminal-Introduction'; Title = 'Introduction to the HP-IB Terminal' },
    @{ Key = 'guide'; File = 'HP-IB-Terminal-Guide'; Title = 'HP-IB Terminal Guide' },
    @{ Key = 'setup'; File = 'pi-GPIBTerm-Setup-Guide'; Title = 'pi-GPIBTerm Setup Guide' },
    @{ Key = 'hp3478a'; File = 'HP3478A-Module-Guide'; Title = 'HP 3478A Module Guide' },
    @{ Key = 'notices'; File = 'THIRD-PARTY-NOTICES'; Title = 'Third-party credits and notices' }
) | Where-Object { $Only -eq 'all' -or $_.Key -eq $Only }

$pandoc = Get-Command pandoc -ErrorAction SilentlyContinue
if (-not $pandoc) { throw 'pandoc not found. Install it from https://pandoc.org/installing.html' }
$browser = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $browser) { throw 'Microsoft Edge or Google Chrome is needed to print the PDFs.' }

$work = Join-Path ([IO.Path]::GetTempPath()) "pi-gpibterm-docs-$PID"
New-Item -ItemType Directory -Force $work | Out-Null
$failed = 0
try {
    foreach ($d in $Docs) {
        $md = Join-Path $DocsDir "$($d.File).md"
        $html = Join-Path $DocsDir "$($d.File).html"
        $pdf = Join-Path $Root "$($d.File).pdf"
        $css = Join-Path $work "$($d.File).css"
        $tmpHtml = Join-Path $work "$($d.File).html"
        $tmpPdf = Join-Path $work "$($d.File).pdf"
        Write-Host "== $($d.File)" -ForegroundColor Cyan

        (Get-Content (Join-Path $PSScriptRoot 'doc-print.css') -Raw).
            Replace('@VERSION@', $Version).Replace('@TITLE@', $d.Title) |
            Set-Content -Encoding utf8 $css

        # Cover page for the PDF: the title on a dark page (over the photo, with -Cover).
        # The HTML copy shows the photo, if any, above the title.
        $coverPdf = Join-Path $work "$($d.File).cover.html"
        $coverHtml = Join-Path $work "$($d.File).cover-plain.html"
        $t = [Net.WebUtility]::HtmlEncode($d.Title)
        @"
<section class="cover$(if ($coverUri) { '' } else { ' text-only' })">$(if ($coverUri) { "<img src=`"$coverUri`" alt=`"$coverAlt`">" })
<div class="cover-text"><div class="cover-project">pi-GPIBTerm</div>
<div class="cover-title">$t</div>
<div class="cover-sub">HP-IB / GPIB instruments on a Raspberry Pi with a Lightside gpib4pi board<br>Version $Version</div></div></section>
"@ | Set-Content -Encoding utf8 $coverPdf
        $(if ($coverUri) { "<p><img src=`"$coverUri`" alt=`"$coverAlt`" style=`"max-width:100%;height:auto`"></p>" } else { '' }) |
            Set-Content -Encoding utf8 $coverHtml

        # HTML for the PDF (with contents list and print style) ...
        # The .md's own "# Title" becomes the title block, so the contents list follows it.
        & $pandoc.Source $md -s --toc --toc-depth=2 --shift-heading-level-by=-1 --embed-resources --resource-path=$DocsDir `
            --css $css --metadata "pagetitle=$($d.Title)" --include-before-body=$coverPdf -o $tmpHtml
        if ($LASTEXITCODE -ne 0) { throw "pandoc failed on $md" }
        # ... and the plain HTML copy kept beside the .md
        & $pandoc.Source $md -s --metadata "title=$($d.Title)" --include-before-body=$coverHtml -o $html
        if ($LASTEXITCODE -ne 0) { throw "pandoc failed on $md (HTML copy)" }

        $profileDir = Join-Path $work 'browser-profile'
        $uri = ([Uri]$tmpHtml).AbsoluteUri
        $p = Start-Process -FilePath $browser -Wait -PassThru -WindowStyle Hidden -ArgumentList @(
            '--headless=new', '--disable-gpu', '--no-first-run', '--no-pdf-header-footer',
            "--user-data-dir=`"$profileDir`"", "--print-to-pdf=`"$tmpPdf`"", $uri)
        if (-not (Test-Path $tmpPdf) -or (Get-Item $tmpPdf).Length -lt 1000) {
            throw "the browser did not produce $tmpPdf (exit $($p.ExitCode))"
        }

        try {
            Copy-Item -Force $tmpPdf $pdf
            Write-Host "   $pdf  ($([math]::Round((Get-Item $pdf).Length / 1KB)) KB)" -ForegroundColor Green
        }
        catch {
            $keep = Join-Path ([IO.Path]::GetTempPath()) "$($d.File)-$(Get-Date -Format yyyyMMdd_HHmmss).pdf"
            Copy-Item -Force $tmpPdf $keep
            Write-Warning "$pdf is probably open in a PDF viewer. The new PDF is at $keep"
            $failed++
        }
    }
}
finally {
    Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}
if ($failed) { exit 1 }
