param(
  [string]$SecretsPath = "$(Split-Path -Parent (Split-Path -Parent $PSScriptRoot))\\.secrets.json",
  [string]$OutDir = "$(Split-Path -Parent $PSScriptRoot)\\fonts\\google"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $SecretsPath)) {
  throw "Secrets file not found: $SecretsPath"
}

$secrets = Get-Content -LiteralPath $SecretsPath -Raw | ConvertFrom-Json
$apiKey = [string]$secrets.google_fonts_api_key
if ([string]::IsNullOrWhiteSpace($apiKey)) {
  throw "google_fonts_api_key is missing or empty in: $SecretsPath"
}

$fontsApi = "https://www.googleapis.com/webfonts/v1/webfonts?key=$apiKey"
$catalog = Invoke-RestMethod -Uri $fontsApi -Method GET
$items = @($catalog.items)

$Families = @(
  "Source Serif 4",
  "Alegreya SC",
  "Cormorant Garamond",
  "Cormorant Infant",
  "Cinzel",
  "Cinzel Decorative",
  "Crimson Pro",
  "IM Fell English SC",
  "Playfair Display",
  "Playfair Display SC",
  "Spectral"
)

function Get-VariantLabel([string]$variant) {
  $v = $variant.ToLowerInvariant()
  if ($v -eq "regular") { return "Regular" }
  if ($v -eq "italic") { return "Italic" }

  $isItalic = $v.EndsWith("italic")
  $weight = $v
  if ($isItalic) { $weight = $v.Substring(0, $v.Length - "italic".Length) }

  $label = switch ($weight) {
    "100" { "Thin" }
    "200" { "ExtraLight" }
    "300" { "Light" }
    "400" { "Regular" }
    "500" { "Medium" }
    "600" { "SemiBold" }
    "700" { "Bold" }
    "800" { "ExtraBold" }
    "900" { "Black" }
    default { $weight }
  }

  if ($isItalic) { return "${label}Italic" }
  return $label
}

function Normalize-Family([string]$family) {
  return ($family -replace "[^A-Za-z0-9]+", "")
}

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

foreach ($family in $Families) {
  $entry = $items | Where-Object { $_.family -eq $family } | Select-Object -First 1
  if (-not $entry) {
    Write-Warning "Font family not found in catalog: $family"
    continue
  }

  $norm = Normalize-Family $family
  $files = $entry.files.PSObject.Properties | ForEach-Object { @{ Variant=$_.Name; Url=$_.Value } }

  foreach ($f in $files) {
    $variantLabel = Get-VariantLabel $f.Variant
    $fileName = "$norm-$variantLabel.ttf"
    $dest = Join-Path $OutDir $fileName

    if (Test-Path -LiteralPath $dest) {
      continue
    }

    try {
      Invoke-WebRequest -Uri $f.Url -OutFile $dest -UseBasicParsing | Out-Null
      Write-Host "Downloaded $family ($($f.Variant)) -> $fileName"
    } catch {
      Write-Warning "Failed download: $family ($($f.Variant)) from $($f.Url)"
    }
  }
}

Write-Host "Fonts downloaded to: $OutDir"
