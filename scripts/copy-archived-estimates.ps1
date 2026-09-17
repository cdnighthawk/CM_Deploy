<#
.SYNOPSIS
  Copy 3_Estimate folders from the Y: archive onto this computer.

.DESCRIPTION
  Scans project folders under the listed year directories and copies any
  first-level folder whose name contains "Estimate" (for example 3_Estimate)
  into D:\Archived, keeping year and project names so jobs do not collide.

  Example source:
    Y:\2025 estimates\23044 - Kaiser Fresno\3_Estimate

  Example destination:
    D:\Archived\2025 estimates\23044 - Kaiser Fresno\3_Estimate

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\copy-archived-estimates.ps1 -DryRun

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\copy-archived-estimates.ps1
#>
[CmdletBinding()]
param(
    [string[]]$Sources = @(
        "Y:\2026 estimates",
        "Y:\2025 estimates"
    ),
    [string]$DestinationRoot = "D:\Archived",
    [switch]$DryRun,
    [switch]$SkipExisting
)

$ErrorActionPreference = "Stop"
$start = Get-Date
$logPath = Join-Path $DestinationRoot ("copy-estimates-{0:yyyyMMdd-HHmmss}.log" -f $start)

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $line = "{0:yyyy-MM-dd HH:mm:ss} [{1}] {2}" -f (Get-Date), $Level, $Message
    Write-Host $line
    if (Test-Path -LiteralPath $DestinationRoot) {
        Add-Content -LiteralPath $logPath -Value $line
    }
}

if (-not (Test-Path -LiteralPath $DestinationRoot)) {
    New-Item -ItemType Directory -Path $DestinationRoot | Out-Null
}

Write-Log "Log file: $logPath"
Write-Log ("Mode: {0}" -f $(if ($DryRun) { "DRY RUN (no files copied)" } else { "COPY" }))
Write-Log "Destination: $DestinationRoot"

$stats = [ordered]@{
    ProjectsScanned   = 0
    EstimateFolders   = 0
    MissingEstimate   = 0
    Copied            = 0
    Skipped           = 0
    Failed            = 0
    BytesCopied       = [int64]0
}
$missing = New-Object System.Collections.Generic.List[string]
$failed = New-Object System.Collections.Generic.List[string]

foreach ($sourceRoot in $Sources) {
    if (-not (Test-Path -LiteralPath $sourceRoot)) {
        Write-Log "Source not found, skipping: $sourceRoot" "WARN"
        continue
    }

    $yearName = Split-Path -Leaf $sourceRoot
    Write-Log "Scanning $sourceRoot"

    $projects = Get-ChildItem -LiteralPath $sourceRoot -Directory -ErrorAction SilentlyContinue
    foreach ($project in $projects) {
        $stats.ProjectsScanned++
        $estimateDirs = Get-ChildItem -LiteralPath $project.FullName -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match 'estimate' }

        if (-not $estimateDirs) {
            $stats.MissingEstimate++
            $missing.Add($project.FullName)
            continue
        }

        foreach ($estimateDir in $estimateDirs) {
            $stats.EstimateFolders++
            $dest = Join-Path $DestinationRoot (Join-Path $yearName (Join-Path $project.Name $estimateDir.Name))

            if ($SkipExisting -and (Test-Path -LiteralPath $dest)) {
                $stats.Skipped++
                Write-Log "Skip existing: $dest"
                continue
            }

            Write-Log ("{0} -> {1}" -f $estimateDir.FullName, $dest)

            if ($DryRun) {
                $stats.Copied++
                continue
            }

            New-Item -ItemType Directory -Path $dest -Force | Out-Null

            # /E copy subdirs including empty, /XO skip older dest files on rerun,
            # /R:2 /W:3 retry network hiccups, /XD skip Windows recycle metadata.
            $roboArgs = @(
                $estimateDir.FullName,
                $dest,
                "/E",
                "/COPY:DAT",
                "/R:2",
                "/W:3",
                "/XO",
                "/NFL",
                "/NDL",
                "/NP",
                "/NJH",
                "/NJS"
            )
            & robocopy @roboArgs | Out-Null
            $code = $LASTEXITCODE
            # Robocopy 0-7 are success/partial; 8+ is failure.
            if ($code -ge 8) {
                $stats.Failed++
                $failed.Add("$($estimateDir.FullName) (robocopy $code)")
                Write-Log "FAILED robocopy exit $code : $($estimateDir.FullName)" "ERROR"
            } else {
                $stats.Copied++
                $size = (Get-ChildItem -LiteralPath $dest -Recurse -File -ErrorAction SilentlyContinue |
                    Measure-Object -Property Length -Sum).Sum
                if ($size) { $stats.BytesCopied += [int64]$size }
            }
        }
    }
}

$elapsed = (Get-Date) - $start
Write-Log "---- Summary ----"
Write-Log ("Projects scanned:     {0}" -f $stats.ProjectsScanned)
Write-Log ("Estimate folders:     {0}" -f $stats.EstimateFolders)
Write-Log ("Projects with none:   {0}" -f $stats.MissingEstimate)
Write-Log ("Copied / planned:     {0}" -f $stats.Copied)
Write-Log ("Skipped existing:     {0}" -f $stats.Skipped)
Write-Log ("Failed:               {0}" -f $stats.Failed)
Write-Log ("Bytes at destination: {0:N0} ({1:N1} MB)" -f $stats.BytesCopied, ($stats.BytesCopied / 1MB))
Write-Log ("Elapsed:              {0:hh\:mm\:ss}" -f $elapsed)

if ($missing.Count -gt 0) {
    $missingPath = Join-Path $DestinationRoot ("projects-without-estimate-{0:yyyyMMdd-HHmmss}.txt" -f $start)
    $missing | Set-Content -LiteralPath $missingPath
    Write-Log "Projects with no Estimate folder listed in: $missingPath"
}
if ($failed.Count -gt 0) {
    $failedPath = Join-Path $DestinationRoot ("copy-failures-{0:yyyyMMdd-HHmmss}.txt" -f $start)
    $failed | Set-Content -LiteralPath $failedPath
    Write-Log "Failures listed in: $failedPath" "ERROR"
}

Write-Log "Done."
