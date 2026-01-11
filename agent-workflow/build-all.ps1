param(
  [switch]$FetchFonts,
  [switch]$CleanFirst
)

$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSCommandPath) | Out-Null
Set-Location ".." | Out-Null

if (-not (Test-Path -LiteralPath "fonts")) {
  cmd /c "mklink /J fonts project\\fonts" | Out-Null
}

if ($FetchFonts) {
  powershell -ExecutionPolicy Bypass -File project/scripts/fetch-google-fonts.ps1
}

if ($CleanFirst) {
  Set-Location project | Out-Null
  latexmk -c proof.tex | Out-Null

  Set-Location proofs | Out-Null
  Get-ChildItem -Filter "proof-*.tex" | ForEach-Object { latexmk -c $_.Name | Out-Null }
}

Set-Location project | Out-Null
latexmk -pdflua -interaction=nonstopmode -halt-on-error proof.tex

Set-Location proofs | Out-Null
Get-ChildItem -Filter "proof-*.tex" | ForEach-Object {
  latexmk -pdflua -interaction=nonstopmode -halt-on-error $_.Name
}

