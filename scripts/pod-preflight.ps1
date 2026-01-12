param(
  [Parameter(Position = 0)]
  [string]$Pdf = "project/final_pass/build/final_pass.pdf",

  [string]$Trim = "5.5x8.5"
)

$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSCommandPath) | Out-Null
Set-Location ".." | Out-Null

$pythonCandidates = @(
  ".venv/Scripts/python.exe",
  "python"
)

$python = $null
foreach ($candidate in $pythonCandidates) {
  if (Get-Command $candidate -ErrorAction SilentlyContinue) {
    $python = $candidate
    break
  }
}

if (-not $python) {
  throw "Python not found (tried: $($pythonCandidates -join ', '))"
}

& $python scripts/pod-preflight.py $Pdf --trim $Trim

